"""Small, rate-limited YouTube discovery probe (task B, reconnaissance wave).

Not a production adapter. Records every raw response (without secrets) and one
row per discovered video so the routes can be compared on the same queries.

Routes:
  api      YouTube Data API v3 search.list -> videos.list -> channels.list ->
           playlistItems.list (uploads). Needs YOUTUBE_API_KEY in the environment
           (or YOUTUBE_API_KEY_FILE pointing to a file outside the repo). Without
           a key, a single unauthenticated call documents the refusal.
  keyless  Apple Podcasts search -> RSS -> YouTube links -> channel ID -> Atom;
           Wikidata P2397 query; oEmbed confirmation of explicit video URLs.

Usage:
  python3 tools/youtube_probe.py keyless [--video URL ...]
  YOUTUBE_API_KEY_FILE=~/.config/investwatch/youtube.key python3 tools/youtube_probe.py api --max-units 1500
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.crosslinks import profile_url, video_id  # noqa: E402
from tools.watch_sources import load_config, CONFIG_PATH  # noqa: E402

OUT = ROOT / "fixtures/raw/discovery/youtube-probe-2026-11-21"
UA = "InvestWatch-SourceMonitor/1.0 (research probe)"
MAX_BYTES = 4 * 1024 * 1024
PAUSE = 1.5
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"
API = "https://www.googleapis.com/youtube/v3/"
COST = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}

QUERIES = {
    "brand": ["XTB", "eToro", "Trading 212"],
    "promo": ["partnerem odcinka inwestowanie", "kod rabatowy inwestowanie", "link w opisie giełda"],
    "topic": ["inwestowanie", "giełda", "ETF"],
}
# Aliases from KNF registers in data/probe-snapshots/knf (domestic DM and cross-border notifications).
DOMESTIC = ["XTB", "X-Trade Brokers", "mBank", "bossa", "DM BOŚ", "Pekao", "PKO BP"]
CROSS_BORDER = ["eToro", "Trading 212", "Trading212", "Freedom24", "Freedom Finance", "Interactive Brokers",
                "IBKR", "Finax", "Lightyear", "Capital.com", "Plus500", "Admiral Markets", "Admirals",
                "IG Europe", "Revolut", "Exante", "Saxo", "DEGIRO", "Scalable Capital", "Conotoxia"]
BRAND = re.compile(r"(?<![\w-])(" + "|".join(re.escape(x) for x in DOMESTIC + CROSS_BORDER) + r")(?![\w-])", re.I)
PROMO = re.compile(
    r"(?i)(partner(?:em|ką|ka)?\s+(?:odcinka|materiału|filmu|kanału)|sponsor\w*|współprac\w*|"
    r"kod\w*\s+(?:rabatow\w*|polecając\w*|promocyjn\w*)|link\w*\s+afiliac\w*|link\w*\s+partnersk\w*|"
    r"z\s+mojego\s+linku|z\s+linku\s+w\s+opisie|materiał\s+sponsorowany|płatn\w+\s+promocj\w*|reklama|#ad\b)"
)
CANONICAL = re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})"')
OG_URL = re.compile(r'<meta property="og:url" content="https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})"')
IDENTIFIER = re.compile(r'<meta itemprop="identifier" content="(UC[A-Za-z0-9_-]{22})"')
YT_URL = re.compile(r"https://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/[^\s\"'<>)\]]+")


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact(url):
    return re.sub(r"([?&]key=)[^&]+", r"\1REDACTED", url)


class Recorder:
    def __init__(self, out):
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.index = (out / "requests.jsonl").open("a", encoding="utf-8")
        self.n = len((out / "requests.jsonl").read_text(encoding="utf-8").splitlines()) if (out / "requests.jsonl").exists() else 0
        self.last = {}

    def get(self, url, label, ext):
        host = urlsplit(url).hostname
        wait = PAUSE - (time.monotonic() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self.last[host] = time.monotonic()
        self.n += 1
        observed = now()
        status, body, error = None, b"", None
        try:
            with urlopen(Request(url, headers={"User-Agent": UA, "Accept-Language": "pl"}), timeout=15) as r:
                status = r.status
                body = r.read(MAX_BYTES + 1)
        except HTTPError as e:
            status = e.code
            body = e.read(MAX_BYTES + 1)
            error = f"HTTP {e.code}"
        except (URLError, OSError) as e:
            error = type(e).__name__
        if len(body) > MAX_BYTES:
            body, error = body[:MAX_BYTES], (error or "truncated")
        name = f"{self.n:03d}-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')[:60]}.{ext}"
        if body:
            (self.out / name).write_bytes(body)
        row = {"n": self.n, "label": label, "url": redact(url), "observedAt": observed, "status": status,
               "bytes": len(body), "sha256": sha256(body).hexdigest(), "file": name if body else None, "error": error}
        self.index.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.index.flush()
        print(f"[{row['n']:03d}] {status} {label} {len(body)}B", file=sys.stderr)
        return status, body, observed


def seeded_channels():
    return {s.account for s in load_config(CONFIG_PATH).sources if s.platform == "youtube"}


def signals(text):
    return {"promo": sorted({m.group(0).lower() for m in PROMO.finditer(text or "")}),
            "brands": sorted({m.group(0) for m in BRAND.finditer(text or "")})}


def parse_atom(body):
    feed = ElementTree.fromstring(body)
    channel = feed.findtext(f"{YT}channelId")
    # Atom emits yt:channelId without the "UC" prefix (as handled in tools/watch_sources.py).
    if channel and len(channel) == 22:
        channel = "UC" + channel
    author = feed.findtext(f"{ATOM}author/{ATOM}name")
    videos = []
    for pos, e in enumerate(feed.findall(f"{ATOM}entry"), 1):
        vid = e.findtext(f"{YT}videoId")
        link_el = e.find(f"{ATOM}link")
        link = link_el.get("href") if link_el is not None else None
        group = e.find(f"{MEDIA}group")
        stats = group.find(f"{MEDIA}community/{MEDIA}statistics") if group is not None else None
        stars = group.find(f"{MEDIA}community/{MEDIA}starRating") if group is not None else None
        desc = group.findtext(f"{MEDIA}description") if group is not None else ""
        videos.append({"position": pos, "videoId": vid, "url": link, "title": e.findtext(f"{ATOM}title"),
                       "published": e.findtext(f"{ATOM}published"), "updated": e.findtext(f"{ATOM}updated"),
                       "shorts": bool(link and "/shorts/" in link),
                       "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
                       "ratingCount": int(stars.get("count")) if stars is not None and stars.get("count") else None,
                       "description": desc})
    return channel, author, videos


class Probe:
    def __init__(self, out):
        self.rec = Recorder(out)
        self.rows = []
        self.routes = {}
        self.seeds = seeded_channels()
        self.channels = {}
        cache = out / "resolved-handles.json"
        self.resolved = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
        self.tag = None

    def route(self, name, **counts):
        r = self.routes.setdefault(name, {"requests": 0, "ok": 0, "errors": [], "results": 0})
        for k, v in counts.items():
            if k == "errors":
                r["errors"].extend(v)
            else:
                r[k] = r.get(k, 0) + v

    def fetch(self, route, url, label, ext):
        status, body, observed = self.rec.get(url, label, ext)
        self.route(route, requests=1, ok=int(status == 200), errors=[] if status == 200 else [f"{label}: {status}"])
        return status, body, observed

    def add(self, **row):
        row["seeded"] = row.get("channelId") in self.seeds
        row["signals"] = signals(" ".join(filter(None, [row.get("title"), row.pop("description", "")])))
        self.rows.append(row)
        self.route(row["route"], results=1)

    # ---------- Data API v3 ----------
    def api(self, key, max_units, pages):
        used = 0
        if not key:
            url = API + "search?" + urlencode({"part": "snippet", "q": "inwestowanie", "type": "video", "maxResults": 1})
            status, _, _ = self.fetch("data_api_v3", url, "data-api-search-without-key", "json")
            self.routes["data_api_v3"]["status"] = "wymaga klucza" if status in (400, 401, 403) else f"HTTP {status}"
            return
        hits = []
        for kind, queries in QUERIES.items():
            for q in queries:
                token = None
                for page in range(pages):
                    if used + COST["search"] > max_units:
                        self.routes.setdefault("data_api_v3", {})["stoppedBy"] = "budżet kwoty"
                        break
                    params = {"part": "snippet", "q": q, "type": "video", "maxResults": 25, "regionCode": "PL",
                              "relevanceLanguage": "pl", "safeSearch": "none", "key": key}
                    if token:
                        params["pageToken"] = token
                    status, body, observed = self.fetch("data_api_v3", API + "search?" + urlencode(params), f"search {kind} {q} p{page + 1}", "json")
                    used += COST["search"]
                    if status != 200:
                        self.routes["data_api_v3"]["status"] = "limit" if b"quotaExceeded" in body else f"HTTP {status}"
                        return
                    data = json.loads(body)
                    for pos, item in enumerate(data.get("items", []), 1 + page * 25):
                        hits.append((kind, q, observed, pos, item))
                    token = data.get("nextPageToken")
                    if not token:
                        break
        videos = list(dict.fromkeys(h[4]["id"]["videoId"] for h in hits if h[4]["id"].get("videoId")))
        vmeta = {}
        for i in range(0, len(videos), 50):
            ids = ",".join(videos[i:i + 50])
            status, body, observed = self.fetch("data_api_v3", API + "videos?" + urlencode({"part": "snippet,statistics,contentDetails,status", "id": ids, "key": key}), f"videos {i}", "json")
            used += COST["videos"]
            for it in json.loads(body).get("items", []) if status == 200 else []:
                vmeta[it["id"]] = (it, observed)
        chans = list(dict.fromkeys(h[4]["snippet"]["channelId"] for h in hits))
        cmeta = {}
        for i in range(0, len(chans), 50):
            status, body, observed = self.fetch("data_api_v3", API + "channels?" + urlencode({"part": "snippet,statistics,contentDetails", "id": ",".join(chans[i:i + 50]), "key": key}), f"channels {i}", "json")
            used += COST["channels"]
            for it in json.loads(body).get("items", []) if status == 200 else []:
                cmeta[it["id"]] = (it, observed)
        for kind, q, observed, pos, item in hits:
            vid = item["id"].get("videoId")
            v, vobs = vmeta.get(vid, ({}, None))
            c, cobs = cmeta.get(item["snippet"]["channelId"], ({}, None))
            stats, cstats = v.get("statistics", {}), c.get("statistics", {})
            self.add(route="data_api_v3", queryKind=kind, query=q, observedAt=observed, position=pos,
                     channelId=item["snippet"]["channelId"], videoId=vid, url=f"https://www.youtube.com/watch?v={vid}",
                     author=item["snippet"].get("channelTitle"), title=v.get("snippet", {}).get("title") or item["snippet"].get("title"),
                     description=v.get("snippet", {}).get("description", ""),
                     language=v.get("snippet", {}).get("defaultAudioLanguage"),
                     stats={"views": stats.get("viewCount"), "likes": stats.get("likeCount"), "statsObservedAt": vobs,
                            "subscribers": None if cstats.get("hiddenSubscriberCount") else cstats.get("subscriberCount"),
                            "hiddenSubscriberCount": cstats.get("hiddenSubscriberCount")},
                     duration=v.get("contentDetails", {}).get("duration"))
        # Uploads playlist of the five largest channels (pagination check on the first).
        ranked = sorted(cmeta.values(), key=lambda x: -int(x[0].get("statistics", {}).get("subscriberCount") or 0))[:5]
        for c, _ in ranked:
            uploads = c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
            if uploads and used + 1 <= max_units:
                self.fetch("data_api_v3", API + "playlistItems?" + urlencode({"part": "contentDetails", "playlistId": uploads, "maxResults": 50, "key": key}), f"uploads {c['id']}", "json")
                used += 1
        self.routes["data_api_v3"].update(status="działa", unitsUsed=used)

    # ---------- keyless ----------
    def atom(self, channel, query, kind, how):
        if channel in self.channels:
            return self.channels[channel]
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel}"
        status, body, observed = self.fetch("atom", url, f"atom {channel}", "xml")
        if status != 200:
            self.channels[channel] = None
            return None
        try:
            cid, author, videos = parse_atom(body)
        except ElementTree.ParseError:
            self.route("atom", errors=[f"{channel}: parse"])
            return None
        self.channels[channel] = (author, videos, observed)
        for v in videos:
            self.add(route="atom", via=how, queryKind=kind, query=query, observedAt=observed, position=v["position"],
                     channelId=cid, videoId=v["videoId"], url=v["url"], author=author, title=v["title"],
                     description=v["description"], published=v["published"], shorts=v["shorts"],
                     stats={"views": v["views"], "ratingCount": v["ratingCount"], "statsObservedAt": observed})
        return self.channels[channel]

    def resolve(self, url):
        norm = profile_url(url)
        if not norm:
            return None
        if "/channel/" in norm:
            return norm.rsplit("/", 1)[-1]
        if norm in self.resolved:
            return self.resolved[norm]
        status, body, _ = self.fetch("channel_page", norm, f"profile {norm.rsplit('/', 1)[-1]}", "html")
        self.resolved[norm] = None
        if status == 200:
            # Since 2026 YouTube emits canonical/og:url/identifier after </head>, so
            # collectors.crosslinks.ChannelMetadata (head-only) finds nothing. Accept only
            # these document-level tags and require one distinct value.
            text = body.decode("utf-8", "replace")
            ids = set(CANONICAL.findall(text)) | set(OG_URL.findall(text)) | set(IDENTIFIER.findall(text))
            self.resolved[norm] = next(iter(ids)) if len(ids) == 1 else None
            if len(ids) != 1:
                self.route("channel_page", errors=[f"{norm}: {len(ids)} identyfikatorów"])
        return self.resolved[norm]

    def oembed(self, video_url):
        vid = video_id(video_url)
        if not vid:
            return None
        url = "https://www.youtube.com/oembed?" + urlencode({"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
        status, body, observed = self.fetch("oembed", url, f"oembed {vid}", "json")
        if status != 200:
            return {"videoId": vid, "status": status, "observedAt": observed}
        data = json.loads(body)
        return {"videoId": vid, "status": 200, "observedAt": observed, "title": data.get("title"),
                "author": data.get("author_name"), "authorUrl": data.get("author_url")}

    def keyless(self, max_feeds, max_profiles, videos, handles=(), skip_catalogs=False):
        if not skip_catalogs:
            self.catalogs(max_feeds, max_profiles)
        self.manual(videos, handles)

    def catalogs(self, max_feeds, max_profiles):
        self.api(None, 0, 0)
        feeds = {}
        for kind, queries in QUERIES.items():
            for q in queries:
                url = "https://itunes.apple.com/search?" + urlencode({"term": q, "country": "PL", "media": "podcast", "entity": "podcast", "limit": 10})
                status, body, observed = self.fetch("apple_podcasts", url, f"apple {kind} {q}", "json")
                if status != 200:
                    continue
                for pos, it in enumerate(json.loads(body).get("results", []), 1):
                    if it.get("feedUrl", "").startswith("https://"):
                        feeds.setdefault(it["feedUrl"], (kind, q, pos, it.get("collectionName")))
        links = {}
        for feed, (kind, q, pos, name) in list(feeds.items())[:max_feeds]:
            status, body, _ = self.fetch("podcast_rss", feed, f"rss {name}", "xml")
            if status != 200:
                continue
            for m in YT_URL.findall(body.decode("utf-8", "replace")):
                m = m.replace("&amp;", "&")
                links.setdefault(m.rstrip(".,;:!?"), (kind, q, name))
        profiles = {u: v for u, v in links.items() if profile_url(u)}
        vids = {u: v for u, v in links.items() if video_id(u)}
        self.routes.setdefault("podcast_rss", {})["youtubeLinks"] = {"profiles": sorted(profiles), "videos": len(vids)}
        resolved = {}
        for u, (kind, q, name) in list(profiles.items())[:max_profiles]:
            cid = self.resolve(u)
            if cid:
                resolved[cid] = (kind, q, f"RSS podcastu „{name}” -> {u}")
        for u, (kind, q, name) in list(vids.items())[:3]:
            o = self.oembed(u)
            if o and o.get("authorUrl"):
                cid = self.resolve(o["authorUrl"])
                if cid:
                    resolved.setdefault(cid, (kind, q, f"RSS podcastu „{name}” -> film {u} -> oEmbed"))
        # Wikidata: open knowledge base, items with a YouTube channel ID (P2397) and a Polish finance description.
        sparql = ('SELECT ?item ?label ?yt ?desc WHERE { ?item wdt:P2397 ?yt; schema:description ?desc; rdfs:label ?label. '
                  'FILTER(LANG(?desc)="pl" && LANG(?label)="pl") FILTER(REGEX(?desc,"inwestor|inwestow|giełd|makler|trader|finansow","i")) '
                  '?item wdt:P27|wdt:P17 wd:Q36. } LIMIT 50')
        status, body, observed = self.fetch("wikidata", "https://query.wikidata.org/sparql?" + urlencode({"query": sparql, "format": "json"}), "wikidata p2397 pl finance", "json")
        if status == 200:
            for pos, b in enumerate(json.loads(body)["results"]["bindings"], 1):
                self.add(route="wikidata", queryKind="topic", query="P2397 + PL + opis finansowy", observedAt=observed,
                         position=pos, channelId=b["yt"]["value"], videoId=None,
                         url=f"https://www.youtube.com/channel/{b['yt']['value']}", author=b["label"]["value"],
                         title=b["desc"]["value"], description="", stats={})
        for cid, (kind, q, how) in resolved.items():
            self.atom(cid, q, kind, how)

    def manual(self, videos, handles):
        for i, (handle, source) in enumerate(handles, 1):
            cid = self.resolve(f"https://www.youtube.com/{handle}")
            self.add(route="ranking_handles", via=source, queryKind="topic", query=f"publiczny ranking: {source}",
                     observedAt=now(), position=i, channelId=cid, videoId=None,
                     url=f"https://www.youtube.com/{handle}", author=handle, title=None, description="", stats={},
                     resolved=bool(cid))
            if cid:
                self.atom(cid, f"ranking: {source}", "topic", f"{source} -> {handle} -> strona kanału -> Atom")
        for i, v in enumerate(videos, 1):
            o = self.oembed(v)
            if not o:
                continue
            self.add(route="oembed", via="ręczny trop (wyszukiwarka agenta)", queryKind=None, query=None,
                     observedAt=o["observedAt"], position=i, channelId=None, videoId=o["videoId"], url=v,
                     author=o.get("author"), title=o.get("title"), description="", stats={}, oembedStatus=o["status"],
                     authorUrl=o.get("authorUrl"))
            if o.get("authorUrl"):
                cid = self.resolve(o["authorUrl"])
                self.rows[-1]["channelId"] = cid
                self.rows[-1]["seeded"] = cid in self.seeds
                if cid:
                    self.atom(cid, v, "manual", f"oEmbed {o['videoId']} -> {o['authorUrl']}")

    def save(self, mode):
        out = self.rec.out
        mode = self.tag or mode
        stamp = now()
        with (out / f"results-{mode}.jsonl").open("w", encoding="utf-8") as f:
            for row in self.rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        summary = {"mode": mode, "finishedAt": stamp, "seededChannels": sorted(self.seeds), "routes": self.routes,
                   "results": len(self.rows),
                   "uniqueChannels": len({r["channelId"] for r in self.rows if r.get("channelId")}),
                   "uniqueVideos": len({r["videoId"] for r in self.rows if r.get("videoId")}),
                   "promoWithBrand": [{k: r.get(k) for k in ("route", "channelId", "author", "videoId", "url", "title", "signals", "stats", "seeded")}
                                      for r in self.rows if r["signals"]["promo"] and r["signals"]["brands"]]}
        (out / "resolved-handles.json").write_text(json.dumps(self.resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / f"summary-{mode}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: summary[k] for k in ("results", "uniqueChannels", "uniqueVideos")}, ensure_ascii=False))


def api_key():
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"].strip()
    path = os.environ.get("YOUTUBE_API_KEY_FILE")
    if path and Path(path).expanduser().is_file():
        resolved = Path(path).expanduser().resolve()
        if ROOT in resolved.parents:
            raise SystemExit("Plik klucza musi leżeć poza repozytorium.")
        return resolved.read_text(encoding="utf-8").strip()
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=("api", "keyless"))
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--max-units", type=int, default=1500, help="budżet jednostek Data API na przebieg")
    p.add_argument("--pages", type=int, default=1, help="strony search.list na zapytanie (po 100 jednostek)")
    p.add_argument("--max-feeds", type=int, default=12)
    p.add_argument("--max-profiles", type=int, default=8)
    p.add_argument("--video", action="append", default=[], help="jawny URL filmu do potwierdzenia przez oEmbed")
    p.add_argument("--handle", action="append", default=[], help="@handle=źródło (np. publiczny ranking twórców)")
    p.add_argument("--tag", help="nazwa pliku wyników (results-TAG.jsonl)")
    p.add_argument("--skip-catalogs", action="store_true", help="pomiń Apple/RSS/Wikidata (drugi przebieg)")
    a = p.parse_args()
    probe = Probe(a.out)
    probe.tag = a.tag
    if a.mode == "api":
        probe.api(api_key(), a.max_units, a.pages)
    else:
        handles = [tuple(h.split("=", 1)) if "=" in h else (h, "ręcznie") for h in a.handle]
        probe.keyless(a.max_feeds, a.max_profiles, a.video, handles, a.skip_catalogs)
    probe.save(a.mode)




# ---------- wave 2: report on a collectors.youtube scan (no network) ----------

def _firm_promo(capture):
    from collectors.youtube import description_signals
    sig = description_signals(capture.get("description"))
    promo = bool(sig["firmEvidence"]) or (bool(sig["firms"]) and bool(sig["disclosure"]))
    return sig, promo


def report(scan_path, previous_path, out_dir):
    from collectors.youtube import _value
    scan = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    caps, creators = scan["captures"], {c["id"]: c for c in scan["creators"]}
    by_creator = {}
    for cap in caps:
        by_creator.setdefault(cap["creatorId"], []).append(cap)

    def family_stats(kind):
        found = {c["creatorId"] for c in caps if any(d["method"] == "data_api_search" and d["queryKind"] == kind for d in c["discovery"])}
        pl = {cid for cid in found if _pl_channel(by_creator[cid])}
        promo = {cid for cid in found if any(_firm_promo(c)[1] for c in by_creator[cid])}
        # Charged search pages of this family (also correct when the scan was served from cache).
        units = 100 * len({(d["query"], d["page"]) for c in caps for d in c["discovery"]
                           if d["method"] == "data_api_search" and d["queryKind"] == kind})
        vids = {c["id"] for c in caps if any(d["method"] == "data_api_search" and d["queryKind"] == kind for d in c["discovery"])}
        big = {cid for cid in pl if (_value(creators.get(cid, {}).get("reach"), "subscriberCount") or 0) >= 100_000}
        return {"searchUnits": units, "videos": len(vids), "channels": len(found), "polishChannels": len(pl),
                "polishChannelsWithFirmPromotion": len(pl & promo), "polishChannels100k": len(big)}

    comparison = {k: family_stats(k) for k in ("brand", "topic", "promo")}
    channels = []
    for cid, creator in creators.items():
        first = (creator.get("discoveries") or [None])[0]
        subs = creator["reach"]["metrics"]["subscriberCount"]
        channels.append({"channelId": creator["persistentId"], "name": creator["name"], "handle": creator.get("handle"),
                         "subscribers": subs["value"], "subscribersState": subs["state"], "subscribersAsOf": subs["observedAt"],
                         "country": creator.get("country"), "polish": _pl_channel(by_creator.get(cid, [])),
                         "seeded": creator["persistentId"] in seeded_channels(),
                         "videosFound": len(by_creator.get(cid, [])),
                         "firmPromotionVideos": sum(1 for c in by_creator.get(cid, []) if _firm_promo(c)[1]),
                         "discovery": {k: first.get(k) for k in ("method", "queryKind", "query", "position", "page", "observedAt")} if first else None})
    channels.sort(key=lambda c: (c["subscribers"] is None, -(c["subscribers"] or 0), c["channelId"]))
    flags = []
    for cap in caps:
        sig, _ = _firm_promo(cap)
        info = cap["youtube"]
        if not sig["firmEvidence"] or sig["disclosure"] or info.get("paidPromotionFlag") is True:
            continue
        if info.get("languageStatus") != "in_scope":
            continue
        creator = creators.get(cap["creatorId"], {})
        subs = _value(creator.get("reach"), "subscriberCount")
        flags.append({"videoId": info["videoId"], "url": cap["url"], "channel": creator.get("name") or cap.get("author"),
                      "channelId": info["channelId"], "subscribers": subs, "views": _value(cap["reach"], "viewCount"),
                      "publishedAt": info.get("publishedAt"), "paidPromotionFlag": info.get("paidPromotionFlag"),
                      "firms": sig["firms"], "firmEvidence": sig["firmEvidence"][:4],
                      "quote": _quote(cap["description"], sig), "title": cap["title"],
                      "crossBorder": any(sig["firms"].get(e["firm"], {}).get("crossBorder") is True for e in sig["firmEvidence"]),
                      "isShort": info.get("isShort")})
    # Prefer small and medium channels, cross-border firms, then views; one per channel first.
    flags.sort(key=lambda f: (not f["crossBorder"], (f["subscribers"] or 0) >= 300_000, -(f["views"] or 0)))
    picked, per_channel = [], {}
    for f in flags:  # at most two per channel so one creator does not fill the list
        if per_channel.get(f["channelId"], 0) < 2 and len(picked) < 15:
            picked.append(f)
            per_channel[f["channelId"]] = per_channel.get(f["channelId"], 0) + 1
    reread = None
    if previous_path:
        prev = {c["id"]: c for c in json.loads(Path(previous_path).read_text(encoding="utf-8"))["captures"]}
        both = [c for c in caps if c["id"] in prev]
        reread = {"compared": len(both),
                  "contentHashUnchanged": sum(1 for c in both if c["contentHash"] == prev[c["id"]]["contentHash"]),
                  "viewCountChanged": sum(1 for c in both if _value(c["reach"], "viewCount") != _value(prev[c["id"]]["reach"], "viewCount")),
                  "asOf": [prev[both[0]["id"]]["reach"]["asOf"], both[0]["reach"]["asOf"]] if both else None}
    langs = {}
    for cap in caps:
        langs[cap["youtube"]["languageStatus"]] = langs.get(cap["youtube"]["languageStatus"], 0) + 1
    summary = {"scan": str(scan_path), "status": scan["status"], "quota": {k: scan["quota"][k] for k in ("used", "limit", "resetAt")},
               "captures": len(caps), "channels": len(creators), "polishChannels": sum(1 for c in channels if c["polish"]),
               "languageStatus": langs, "comparisonSameBudget": comparison, "reread": reread,
               "shorts": sum(1 for c in caps if c["youtube"].get("isShort")),
               "paidPromotionFlagTrue": sum(1 for c in caps if c["youtube"].get("paidPromotionFlag") is True),
               "flagCandidates": picked}
    out = Path(out_dir)
    (out / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "channels-by-subscribers.json").write_text(json.dumps(channels, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return summary, channels


def _pl_channel(captures):
    statuses = [c["youtube"].get("languageStatus") for c in captures]
    return bool(statuses) and statuses.count("in_scope") * 2 > len(statuses)


def _quote(text, sig):
    for needle in [e["value"] for e in sig["firmEvidence"]]:
        at = text.find(needle)
        if at >= 0:
            start = text.rfind("\n", 0, max(0, at - 160)) + 1
            return " ".join(text[start:at + len(needle) + 120].split())[:360]
    return " ".join(text[:300].split())


def report_main():
    p = argparse.ArgumentParser()
    p.add_argument("scan")
    p.add_argument("--previous")
    p.add_argument("--out", default=str(ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21"))
    a = p.parse_args(sys.argv[2:])
    summary, channels = report(a.scan, a.previous, a.out)
    print(json.dumps({k: v for k, v in summary.items() if k != "flagCandidates"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report_main()
    else:
        main()
