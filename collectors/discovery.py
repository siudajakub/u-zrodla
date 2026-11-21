"""Return creators, publication captures and health for a live or archived scan."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path

from .adapter import Adapter, MemoryRunner, execute, merge_source_rows
from .catalogs import (
    PODCAST_ID, PODCAST_QUERIES, PEERTUBE_QUERIES, feed_allowed, read_apple, read_peertube, read_podcast,
)
from .common import safe_get, utc_now
from .crosslinks import extend_from_posts
from .sites import SITES, read_site, m3_entity_captures
from .social import CONFIG, read_social, read_watch, social_creator
from . import social as social_module

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "fixtures/raw/discovery/2026-11-21.json"
FEEDS_PER_SCAN = 8
DISCOVERY_TOPICS = ("giełda", "fundusze indeksowe", "rachunek maklerski",
                    "IKE inwestowanie", "akcje dywidendowe", "rynek kapitałowy")

def rotating_topic(observed_at):
    slot=int(datetime.fromisoformat(observed_at).timestamp())//14400
    return DISCOVERY_TOPICS[slot % len(DISCOVERY_TOPICS)]



COMPLETENESS_RANK = {"partial": 1, "full": 2}
CONTENT_FIELDS = {"title", "description", "url", "publishedAt", "observedAt", "segments", "mediaUrl", "contentHash",
                  "contentCompleteness", "provenance", "materialType", "sampled"}
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _moment(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else _EPOCH


def _completeness(item):
    explicit = item.get("contentCompleteness")
    if explicit in COMPLETENESS_RANK:
        return explicit
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    return "partial" if provenance.get("truncated") or provenance.get("sampled") or item.get("sampled") else "full"


def _precedence(item):
    # Fuller content first, then the newer reading; the canonical text only breaks exact ties,
    # so the outcome never depends on the order in which sources finished.
    return (COMPLETENESS_RANK[_completeness(item)], _moment(item.get("observedAt")),
            json.dumps(item, sort_keys=True, default=str))


def _merge_discovery(first, second):
    merged = {}
    for entry in [*(first or []), *(second or [])]:
        if not isinstance(entry, dict):
            continue
        key = (entry.get("method"), entry.get("query") or "", entry.get("sourceId") or "")
        if key not in merged or _moment(entry.get("observedAt")) >= _moment(merged[key].get("observedAt")):
            merged[key] = entry
    return sorted(merged.values(), key=lambda e: (_moment(e.get("observedAt")), str(e.get("method")), str(e.get("query"))))


def _merge_reach(first, second):
    samples = [r for r in (first, second) if isinstance(r, dict) and isinstance(r.get("metrics"), dict)]
    if len(samples) < 2:
        return samples[0] if samples else (first or second)
    metrics = {}
    for sample in samples:
        for name, metric in sample["metrics"].items():
            at = metric.get("observedAt") or sample.get("asOf")
            if name not in metrics or _moment(at) >= _moment(metrics[name].get("observedAt") or metrics[name]["_asOf"]):
                metrics[name] = {**metric, "_asOf": at}
    newest = max(samples, key=lambda r: _moment(r.get("asOf")))
    return {**newest, "metrics": {k: {a: b for a, b in v.items() if a != "_asOf"} for k, v in metrics.items()}}


def merge_capture(captures, item):
    """Add a capture to {id: capture}. A second reading of the same material keeps one record that
    carries every discovery path and the newest statistic of each kind."""
    current = captures.get(item["id"])
    if current is None:
        captures[item["id"]] = item
        return item
    primary, other = (current, item) if _precedence(current) >= _precedence(item) else (item, current)
    merged = dict(primary)
    for key, value in other.items():
        # Only fields the other reading adds on top; whatever describes the content itself, its
        # completeness or its provenance stays with the reading that won.
        if key not in CONTENT_FIELDS:
            merged.setdefault(key, value)
    if "discovery" in current or "discovery" in item:
        merged["discovery"] = _merge_discovery(current.get("discovery"), item.get("discovery"))
    if "reach" in current or "reach" in item:
        merged["reach"] = _merge_reach(current.get("reach"), item.get("reach"))
    captures[item["id"]] = merged
    return merged


def merge_captures(items):
    captures = {}
    for item in items:
        merge_capture(captures, item)
    return list(captures.values())


def _read_replay():
    result = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for filename in ("bossa-discovery-2026-11-21.json", "bossa-education-2026-11-21.json"):
        archived = ROOT / "fixtures/validation" / filename
        if archived.exists():
            saved = json.loads(archived.read_text(encoding="utf-8"))
            capture = saved["capture"]
            capture["provenance"]["fixture"] = filename
            if not any(item["id"] == capture["id"] for item in result["captures"]):
                result["captures"].append(capture)
            source = {**saved["source"], "fixture": filename}
            previous = next((item for item in result["sources"] if item["id"] == source["id"]), None)
            if previous:
                source["previousObservation"] = previous
                result["sources"][result["sources"].index(previous)] = source
            else:
                result["sources"].append(source)
    known_creators = {item["id"] for item in result["creators"]}
    result["creators"].extend(site.creator for site in SITES if site.key not in known_creators)
    return result


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


# --- adapter registry (contract v2, step S3) ---
# The sources below keep their former behaviour and output; they only run through the registry,
# so every one of them is a resumable step with validated output and persisted state.
ADAPTERS = {}


def register(adapter):
    ADAPTERS[adapter.id] = adapter
    return adapter


def active_adapters(mode, only=None, own_transport=True):
    """Adapters of a mode. `only` (a scan's payload) selects explicitly and may name explicit-only ones;
    `own_transport=False` (the caller injected a fetch) leaves out adapters that bring their own network."""
    chosen = []
    for a in ADAPTERS.values():
        if mode not in a.modes or (not own_transport and a.own_network):
            continue
        if only is not None:
            if a.id in only:
                chosen.append(a)
        elif a.enabled() and not a.explicit_only:
            chosen.append(a)
    return chosen


def planned_steps(mode, only=None):
    return ["discover:" + a.id for a in active_adapters(mode, only)]


def _parallel(tasks, workers=4):
    """Run (function, args) pairs in a bounded pool; results come back in submission order."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(function, *args) for function, args in tasks]
        return [future.result() for future in futures]


def _apple(ctx):
    previous, fetch, clock = ctx.previous, ctx.fetch, ctx.clock
    creators, captures, statuses = {}, {}, {}

    def collect(items, status):
        for item in items:
            merge_capture(captures, item)
        statuses[status["id"]] = status

    with ThreadPoolExecutor(max_workers=4) as pool:
        apple = [pool.submit(read_apple, query, fetch, clock) for query in (*PODCAST_QUERIES, rotating_topic(clock()))]
        for task in apple:
            found, status = task.result()
            for creator in found:
                creators.setdefault(creator["id"], _remember(creator, previous))
            collect([], status)
        # Revisit shows that fell out of search results. Oldest checks receive the next slots.
        feeds = {
            id: creator for id, creator in previous.items()
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
        for task in podcasts:
            creator, items, status = task.result()
            creators[creator["id"]] = creator
            collect(items, status)
    return {"creators": list(creators.values()), "captures": list(captures.values()), "sources": list(statuses.values())}


def _peertube(ctx):
    creators, captures, statuses = {}, [], {}
    for found, items, status in _parallel([(read_peertube, (query, ctx.fetch, ctx.clock)) for query in PEERTUBE_QUERIES]):
        for creator in found:
            creators.setdefault(creator["id"], _remember(creator, ctx.previous))
        captures.extend(items)
        statuses[status["id"]] = status
    return {"creators": list(creators.values()), "captures": captures, "sources": list(statuses.values())}


def _sites(ctx):
    captures, statuses = [], {}
    for items, status in _parallel([(read_site, (site, ctx.fetch, ctx.clock)) for site in SITES]):
        captures.extend(items)
        statuses[status["id"]] = status
    return {"creators": [site.creator for site in SITES], "captures": captures, "sources": list(statuses.values())}


def _social(ctx):
    creators = [social_creator(source) for source in CONFIG.sources]
    configured_db = os.environ.get("INVESTWATCH_WATCH_DB")
    watch_db = Path(configured_db) if configured_db else ROOT / ".runtime/watch/watch.sqlite3"
    captures, statuses = [], {}
    if configured_db or watch_db.is_file():
        items, monitor_statuses = read_watch(watch_db, ctx.clock)
        captures.extend(items)
        statuses.update((status["id"], status) for status in monitor_statuses)
    else:
        for items, status in _parallel([(read_social, (source, ctx.fetch, ctx.clock)) for source in CONFIG.sources]):
            captures.extend(items)
            statuses[status["id"]] = status
    return {"creators": creators, "captures": captures, "sources": list(statuses.values())}


def _crosslinks(ctx):
    linked, posts, statuses = extend_from_posts(ctx.captures, list(ctx.previous.values()), fetch=ctx.fetch, clock=ctx.clock)
    return {"creators": linked, "captures": posts, "sources": list(statuses)}


def _replay(ctx):
    return _read_replay()


def _on_unless_listed(name):
    """On by default; INVESTWATCH_ADAPTERS, when set, lists exactly the optional adapters that run."""
    def enabled():
        listed = os.environ.get("INVESTWATCH_ADAPTERS")
        return listed is None or name in [x.strip() for x in listed.split(",")]
    return enabled


def _youtube_creators(previous):
    """The adapter reads only YouTube channels (youtube:UC...); creators of other platforms are not its base."""
    return tuple(c for c in previous.values()
                 if str(c.get("id", "")).startswith("youtube:UC") and str(c.get("platform") or "youtube").split(":")[0] == "youtube")


def _youtube(ctx):
    """Entry point for collectors/youtube.py (agent B). B's own Context carries the Data API settings;
    tests and tools override them through ctx.options["youtube"]. With `state_dir` the channel base is kept in
    state_dir/channels.json by the adapter, so the result's `cursor` (hundreds of kB) is not persisted a second time."""
    from . import youtube
    settings = {"mode": ctx.mode, "state": ctx.state, "known_creators": _youtube_creators(ctx.previous),
                **({"budget": ctx.budget} if ctx.budget is not None else {}), **ctx.options.get("youtube", {})}
    yctx = youtube.Context(**settings)
    yctx.heartbeat = ctx.heartbeat
    result = youtube.discover(yctx)
    if settings.get("state_dir") and isinstance(result, dict):
        result = {k: v for k, v in result.items() if k != "cursor"}
    return result


_LEGACY = dict(legacy=True)
register(Adapter("apple-podcasts", _apple, "Apple Podcasts i kanały RSS", **_LEGACY))
register(Adapter("peertube", _peertube, "PeerTube", **_LEGACY))
register(Adapter("social", _social, "Profile obserwowane", **_LEGACY))
register(Adapter("sites", _sites, "Strony firm", **_LEGACY))
register(Adapter("crosslinks", _crosslinks, "Powiązania z postów", after=("apple-podcasts", "peertube", "social", "sites"), **_LEGACY))
register(Adapter("replay", _replay, "Archiwum 21 XI", modes=("replay",), **_LEGACY))
# YouTube runs in every live scan. Without a key the source reports needs_key and costs nothing;
# with a key the run budget and the daily ledger bound the quota (defaults: 1200 units per run, 8000 per day).
if importlib.util.find_spec("collectors.youtube") is not None:
    register(Adapter("youtube", _youtube, "YouTube · Data API v3 + Atom", enabled=_on_unless_listed("youtube"),
                     daily_units_env="INVESTWATCH_YT_DAILY_UNITS", daily_units_default=8000,
                     run_units_env="INVESTWATCH_YT_RUN_UNITS", run_units_default=1200,
                     quota_tz="America/Los_Angeles", own_network=True))

    def _youtube_replay(ctx):
        """The dated YouTube event of 2026-11-21 (fixture of lane B), no network."""
        from . import youtube
        result = youtube.replay()
        extra = youtube.REPLAY.with_name("replay-media-extra.json")
        if extra.is_file():  # films of the media pack that the dated search did not return (controls, hand-listened cases)
            added = json.loads(extra.read_text(encoding="utf-8"))
            have = {item["id"] for item in result["captures"]}
            for capture in added.get("captures", []):
                if capture["id"] not in have:
                    result["captures"].append({**capture, "mode": "replay"})
            known = {item["id"] for item in result["creators"]}
            result["creators"].extend(item for item in added.get("creators", []) if item["id"] not in known)
        return result
    register(Adapter("youtube-replay", _youtube_replay, "YouTube · archiwum 21 XI", modes=("replay",),
                     explicit_only=True, own_network=False))


# --- Social sources of lane K (TikTok after the YouTube stage, Facebook and Instagram, Meta Ad Library) ---
# TikTok reads the profiles linked in YouTube descriptions, so it runs in the second stage with ctx.captures.
# Facebook and Instagram report access_blocked (a known state, not an error). Every one of them can be left out
# through INVESTWATCH_ADAPTERS, and a missing function or module only means that the adapter is not registered.
if hasattr(social_module, "discover_tiktok"):
    register(Adapter("tiktok", social_module.discover_tiktok, "TikTok · profile z odnośników", after=("youtube",),
                     enabled=_on_unless_listed("tiktok"), run_units_default=8))
for _platform, _label in (("facebook", "Facebook · dostęp do wpisów"), ("instagram", "Instagram · dostęp do wpisów")):
    if hasattr(social_module, "discover_" + _platform):
        register(Adapter(_platform, getattr(social_module, "discover_" + _platform), _label,
                         enabled=_on_unless_listed(_platform)))
if importlib.util.find_spec("collectors.meta_ads") is not None:
    from .meta_ads import discover as discover_meta_ads
    # Own transport (it needs the Graph API error bodies). Without a token file it reports needs_key and sends no request.
    register(Adapter("meta_ads", discover_meta_ads, "Meta · Biblioteka Reklam (FB i IG)", enabled=_on_unless_listed("meta_ads"),
                     run_units_env="INVESTWATCH_META_RUN_REQUESTS", run_units_default=30,
                     daily_units_env="INVESTWATCH_META_DAILY_REQUESTS", daily_units_default=300, own_network=True))

# The analyst's saved Meta pages (collectors/meta_import.py). No network in either mode. Live reads the import folder
# (INVESTWATCH_META_IMPORT_DIR or STATE/meta-import); the dated sample of 2026-11-21 is a separate, explicit-only replay
# adapter, so a default replay does not mix it in and the worker orders it like social-replay.
if importlib.util.find_spec("collectors.meta_import") is not None:
    from .meta_import import discover as discover_meta_import
    register(Adapter("meta_import", discover_meta_import, "Meta · import ręczny (FB i IG)", modes=("live",),
                     enabled=_on_unless_listed("meta_import"), own_network=False))
    register(Adapter("meta-import-replay", discover_meta_import, "Meta · import ręczny, archiwum 21 XI", modes=("replay",),
                     explicit_only=True, own_network=False))

SOCIAL_REPLAY = social_module.FIXTURES / "replay.json.gz"


def _social_replay(ctx):
    """The dated social event of 2026-11-21 (fixture of lane K), no network. TikTok captures, the language filter
    outcome of every profile and the Facebook and Instagram access probe."""
    import gzip
    result = json.loads(gzip.decompress(SOCIAL_REPLAY.read_bytes()))
    for capture in result.get("captures", []):
        capture["mode"] = "replay"
        if isinstance(capture.get("provenance"), dict):
            capture["provenance"].setdefault("fixture", "social-2026-11-21/replay.json.gz")
    result.pop("fixtureNote", None)
    return result


def _enabled_when_listed(name):
    """Off by default; INVESTWATCH_ADAPTERS must name the adapter to switch it on."""
    def enabled():
        return name in [x.strip() for x in (os.environ.get("INVESTWATCH_ADAPTERS") or "").split(",")]
    return enabled


if hasattr(social_module, "FIXTURES") and SOCIAL_REPLAY.is_file():
    register(Adapter("social-replay", _social_replay, "Social · archiwum 21 XI", modes=("replay",),
                     explicit_only=True, own_network=False))


# --- M3: advisory offers (lane F). One case per firm: the home page is the capture, every saved page travels in m3Pages ---
M3_REPLAY = ROOT / "fixtures/raw/discovery/m3-2026-11-21/entities.json"
M3_NOT_A_SEARCH = ("odkrywanie z listy ziaren; wyszukiwanie wymaga dostawcy z kluczem "
                   "(produkt nie ma własnej wyszukiwarki)")


def m3_entity_capture(entity, adapter_id, method):
    """One firm to one Capture (module M3): the home page record plus all read pages with their full text."""
    creator, items = m3_entity_captures(entity)
    if not items:
        return creator, None
    item = items[0]
    item["id"] = f"web:{entity['domain']}:m3"  # one case per firm, stable when the home page redirects
    pages = entity["pages"]
    item["m3Pages"] = [{"url": p["url"], "observedAt": p.get("observedAt"), "sha256": p.get("sha256"), "title": p.get("title"),
                        "role": p.get("role"), "text": p.get("text") or "", "textSha256": p.get("textSha256"),
                        "identityText": p.get("identityText") or ""} for p in pages]
    seed = (entity.get("seed") or {}).get("discovery") or {}
    item["discovery"] = [{"method": method, "adapter": adapter_id, "sourceId": adapter_id, "query": seed.get("query"),
                          "rank": seed.get("rank"), "sourceUrl": seed.get("resultUrl") or (entity.get("seed") or {}).get("url"),
                          "observedAt": pages[0].get("observedAt"), "responseSha256": pages[0].get("sha256")}]
    return creator, item


def _m3_result(entities, adapter_id, label, method, scope, at, extra_status=None):
    creators, captures, errors = [], [], []
    for entity in entities:
        creator, item = m3_entity_capture(entity, adapter_id, method)
        if item is None:
            errors.append(entity)
            continue
        creators.append(creator)
        captures.append(item)
    pages = sum(len(i["m3Pages"]) for i in captures)
    status = {"id": adapter_id, "name": label, "url": None, "status": "ok" if captures else "empty", "count": len(captures),
              "rawCount": len(entities), "pages": pages, "unread": len(errors), "observedAt": at, "scope": scope,
              "message": M3_NOT_A_SEARCH, **(extra_status or {})}
    return {"creators": creators, "captures": captures, "sources": [status]}


def _m3_replay(ctx):
    """The dated M3 run of 2026-11-21 (29 firms, 57 pages) from the saved pages, no network."""
    path = Path(ctx.options.get("m3_replay") or M3_REPLAY)
    data = json.loads(path.read_text(encoding="utf-8"))
    result = _m3_result(data["entities"], "m3-offers-replay", "Oferty doradcze M3 · zapis 21 XI", "search_result_replay",
                        "Tekst HTML stron firm (zapis z 21 XI)", data.get("startedAt") or ctx.clock(),
                        {"requests": data.get("requests"), "sampleDate": "2026-11-21"})
    for item in result["captures"]:
        item["provenance"].setdefault("fixture", "m3-2026-11-21/entities.json")
    return result


def read_m3_seeds(path):
    """Seeds from a file: recorded search results (queries[].results[]) or a plain list of {url, label}."""
    from .catalogs import load_m3_seeds
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [{"url": s["url"], "offerUrl": s.get("offerUrl"), "label": s.get("label") or s["url"],
                 "discoveredVia": s.get("discoveredVia") or "Lista ziaren", "discovery": s.get("discovery") or {}}
                for s in data if isinstance(s, dict) and s.get("url")]
    return load_m3_seeds(path)


def _m3_live(ctx):
    """Own transport (PoliteFetcher: robots.txt, 3 s between requests, a request budget). Disabled by default.
    Without a seeds file it reports the empty state and sends no request."""
    from .sites import PoliteFetcher, read_m3_firm, site_key
    from urllib.parse import urlsplit
    at = ctx.clock()
    seeds_path = ctx.options.get("m3_seeds") or os.environ.get("INVESTWATCH_M3_SEEDS")
    if not seeds_path or not Path(seeds_path).is_file():
        return {"creators": [], "captures": [], "sources": [{
            "id": "m3-offers", "name": "Oferty doradcze M3", "status": "empty", "count": 0, "observedAt": at,
            "message": M3_NOT_A_SEARCH, "nextStep": "Wskaż plik z listą ziaren w INVESTWATCH_M3_SEEDS."}]}
    seeds = read_m3_seeds(seeds_path)
    budget = int(ctx.budget) if ctx.budget is not None else 60
    fetcher = ctx.options.get("m3_fetcher") or PoliteFetcher(budget=budget)
    entities = []
    for seed in seeds:
        ctx.heartbeat()
        domain = site_key(urlsplit(seed["url"]).hostname)
        if fetcher.used + 3 > fetcher.budget:
            entities.append({"id": f"m3:{domain}", "domain": domain, "label": seed.get("label"), "seed": seed, "pages": [],
                             "discoveredVia": seed.get("discoveredVia"), "errors": [{"url": seed["url"], "error": "pominięty: budżet żądań"}]})
            continue
        entities.append(read_m3_firm(seed, fetcher, ctx.clock, subpages=1))
    return _m3_result(entities, "m3-offers", "Oferty doradcze M3", "seed_list", "Tekst HTML stron firm (odczyt na żywo)", at,
                      {"requests": fetcher.used, "budget": fetcher.budget})


def m3_domain(item):
    from urllib.parse import urlsplit
    host = urlsplit(item.get("url") or "").hostname or ""
    return host[4:] if host.startswith("www.") else host


def drop_legacy_duplicates(captures):
    """A firm that an older source already holds as a case (bossa.pl: id web:bossa.pl/...) is not added a second time
    by the entity reader: the older case keeps its id and decisions."""
    legacy = {m3_domain(c) for c in captures if c.get("module") == "M3" and not c.get("m3Entity")}
    return [c for c in captures if not (c.get("m3Entity") and m3_domain(c) in legacy)]


M3_FILES_OK = M3_REPLAY.is_file()
if M3_FILES_OK:
    register(Adapter("m3-offers-replay", _m3_replay, "Oferty doradcze M3 · archiwum 21 XI", modes=("replay",),
                     explicit_only=True, own_network=False))
register(Adapter("m3-offers", _m3_live, "Oferty doradcze M3 · lista ziaren", enabled=_enabled_when_listed("m3-offers"),
                 run_units_env="INVESTWATCH_M3_RUN_REQUESTS", run_units_default=60, own_network=True))


def _run(mode, previous, known_ids, fetch, clock, runner, options, only=None):
    adapters = active_adapters(mode, only, own_transport=fetch is safe_get or "youtube" in (options or {}))
    runner.plan(["discover:" + a.id for a in adapters])
    base = {"mode": mode, "previous": previous, "known_ids": frozenset(known_ids), "fetch": fetch, "clock": clock,
            "options": options or {}}
    first = [a for a in adapters if not a.after]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(4, len(first)))) as pool:
        futures = {a.id: pool.submit(execute, a, runner, base) for a in first}
        for id, future in futures.items():
            results[id] = future.result()
    first_captures = merge_captures(c for a in first for c in results[a.id]["captures"])
    for adapter in adapters:
        if adapter.after:
            results[adapter.id] = execute(adapter, runner, base, {"captures": first_captures})
    creators, captures, rows = {}, {}, []
    for adapter in adapters:
        found = results[adapter.id]
        for creator in found["creators"]:
            creators.setdefault(creator["id"], creator)
        for item in found["captures"]:
            merge_capture(captures, item)
        rows.extend((adapter.id, source) for source in found["sources"])
    # Later rows of the same id replace earlier ones, as before; the Meta sources collapse into one row with paths[].
    statuses = {}
    for source in merge_source_rows(rows):
        statuses[source.get("id") or source["name"]] = source
    return {"creators": list(creators.values()), "captures": drop_legacy_duplicates(list(captures.values())),
            "sources": list(statuses.values())}


def discover(mode, known_ids, *, known_creators=(), fetch=safe_get, clock=utc_now, runner=None, options=None, only=None):
    """Find new identities relative to the caller's persisted set and report collection scope.

    `runner` persists steps, source state and quota (api.jobs.ScanRunner); without it nothing is stored."""
    known = set(known_ids)
    previous = {creator["id"]: creator for creator in known_creators}
    if mode not in ("live", "replay"):
        raise ValueError("Tryb skanu musi mieć wartość live lub replay.")
    result = _run(mode, previous, known, fetch, clock, runner or MemoryRunner(), options, only)
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
            item["provenance"].setdefault("fixture", SNAPSHOT.name)
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
