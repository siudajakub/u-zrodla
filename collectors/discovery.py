"""Return creators, publication captures and health for a live or archived scan."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path

from .catalogs import (
    PODCAST_ID, PODCAST_QUERIES, PEERTUBE_QUERIES, feed_allowed, read_apple, read_peertube, read_podcast,
)
from .common import safe_get, utc_now
from .crosslinks import extend_from_posts
from .sites import SITES, read_site
from .social import CONFIG, read_social, read_watch, social_creator

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "fixtures/raw/discovery/2026-11-21.json"
FEEDS_PER_SCAN = 8
DISCOVERY_TOPICS = ("giełda", "fundusze indeksowe", "rachunek maklerski",
                    "IKE inwestowanie", "akcje dywidendowe", "rynek kapitałowy")

def rotating_topic(observed_at):
    slot=int(datetime.fromisoformat(observed_at).timestamp())//14400
    return DISCOVERY_TOPICS[slot % len(DISCOVERY_TOPICS)]



def _read_replay():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _remember(creator, previous_creators):
    previous = previous_creators.get(creator["id"])
    if not previous:
        return creator
    merged = {**previous, **creator}
    if previous.get("feedUrl") and not creator.get("feedUrl"):
        merged["feedUrl"] = previous["feedUrl"]
    for key in ("firstDiscoveredAt", "discoveredVia", "discovery", "feedCheckedAt", "feedLanguage"):
        if previous.get(key):
            merged[key] = previous[key]
    if previous.get("feedUrl") == merged.get("feedUrl") and previous.get("qualification"):
        merged["qualification"] = previous["qualification"]
    elif creator.get("feedUrl"):
        merged.pop("feedCheckedAt", None)
        merged.pop("feedLanguage", None)
    return merged


def _live(previous_creators, fetch, clock):
    creators = {source.key: social_creator(source) for source in CONFIG.sources}
    creators.update((site.key, site.creator) for site in SITES)
    captures, statuses = {}, {}

    def collect(items, status):
        for item in items:
            captures.setdefault(item["id"], item)
        statuses[status["id"]] = status

    # Public lookups run in parallel. This keeps a failed origin from blocking the other sources.
    configured_db = os.environ.get("INVESTWATCH_WATCH_DB")
    watch_db = Path(configured_db) if configured_db else ROOT / ".runtime/watch/watch.sqlite3"
    with ThreadPoolExecutor(max_workers=4) as pool:
        apple = [pool.submit(read_apple, query, fetch, clock) for query in (*PODCAST_QUERIES, rotating_topic(clock()))]
        peer = [pool.submit(read_peertube, query, fetch, clock) for query in PEERTUBE_QUERIES]
        sites = [pool.submit(read_site, site, fetch, clock) for site in SITES]
        social_db = None
        social = []
        if configured_db or watch_db.is_file():
            social_db = pool.submit(read_watch, watch_db, clock)
        else:
            social = [pool.submit(read_social, source, fetch, clock) for source in CONFIG.sources]

        for task in apple:
            found, status = task.result()
            for creator in found:
                creators.setdefault(creator["id"], _remember(creator, previous_creators))
            collect([], status)

        # Revisit shows that fell out of search results. Oldest checks receive the next slots.
        feeds = {
            id: creator for id, creator in previous_creators.items()
            if PODCAST_ID.fullmatch(id) and creator.get("platform") == "apple-podcasts"
            and creator.get("name") and creator.get("url") and creator.get("mode") != "replay"
        }
        feeds.update((id, creator) for id, creator in creators.items() if PODCAST_ID.fullmatch(id))
        queue = sorted(
            (creator for creator in feeds.values() if feed_allowed(creator.get("feedUrl"))),
            key=lambda creator: (creator.get("feedCheckedAt") or "", creator["id"]),
        )
        podcasts = [pool.submit(read_podcast, creator, fetch, clock) for creator in queue[:FEEDS_PER_SCAN]]
        for creator in feeds.values():
            if creator["id"] in creators and not feed_allowed(creator.get("feedUrl")):
                _, _, status = read_podcast(creator, fetch, clock)
                collect([], status)

        for task in peer:
            found, items, status = task.result()
            for creator in found:
                creators.setdefault(creator["id"], _remember(creator, previous_creators))
            collect(items, status)
        for task in sites + social:
            items, status = task.result()
            collect(items, status)
        if social_db:
            items, monitor_statuses = social_db.result()
            captures.update((item["id"], item) for item in items)
            statuses.update((status["id"], status) for status in monitor_statuses)
        for task in podcasts:
            creator, items, status = task.result()
            creators[creator["id"]] = creator
            collect(items, status)
    linked, linked_posts, link_status = extend_from_posts(
        list(captures.values()), list(previous_creators.values()), fetch=fetch, clock=clock
    )
    for creator in linked:
        creators.setdefault(creator["id"],creator)
    for post in linked_posts:
        captures.setdefault(post["id"],post)
    for source in link_status:
        statuses[source["id"]]=source
    return {
        "creators": list(creators.values()),
        "captures": list(captures.values()),
        "sources": list(statuses.values()),
    }


def discover(mode, known_ids, *, known_creators=(), fetch=safe_get, clock=utc_now):
    """Find new identities relative to the caller's persisted set and report collection scope."""
    known = set(known_ids)
    previous = {creator["id"]: creator for creator in known_creators}
    if mode == "replay":
        result = _read_replay()
    elif mode == "live":
        result = _live(previous, fetch, clock)
    else:
        raise ValueError("Tryb skanu musi mieć wartość live lub replay.")
    new = set()
    for creator in result["creators"]:
        # Configured seed profiles are known from the start.
        is_new = not creator.get("isSeed") and creator["id"] not in known
        creator.update(isNew=is_new, mode=mode)
        if is_new:
            new.add(creator["id"])
    for item in result["captures"]:
        item["mode"] = mode
        item["provenance"]["mode"] = mode
        if mode == "replay":
            item["provenance"]["fixture"] = SNAPSHOT.name
    for status in result["sources"]:
        status["mode"] = mode
        if "creatorIds" in status:
            status["newCreators"] = len(new.intersection(status["creatorIds"]))
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "replay"))
    args = parser.parse_args()
    result = discover(args.mode, ())
    print(json.dumps({
        "creators": len(result["creators"]),
        "newCreators": sum(item["isNew"] for item in result["creators"]),
        "captures": len(result["captures"]),
        "sources": result["sources"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
