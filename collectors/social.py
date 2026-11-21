"""Adapt the existing YouTube and TikTok monitor without writing to its database."""

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlsplit

from tools.watch_sources import (
    CONFIG_PATH, ReadError, Source, TikTokEmbed, load_config, parse_tiktok, parse_youtube, read_database,
)

from .common import SourceError, capture, digest, public_link, source_result, utc_now

CONFIG = load_config(CONFIG_PATH)
POST_LIMIT = 50


def social_creator(source):
    return {
        "id": source.key, "name": source.label, "platform": source.platform,
        "url": source.profile_url, "discoveredVia": "Profil monitorowany", "isSeed": True,
    }


def make_social_capture(source, post_id, url, title, description, published_at, observed_at, response_hash):
    return capture(
        f"{source.platform}:{post_id}", social_creator(source), title or description[:120] or source.label,
        url, description, observed_at=observed_at, published_at=published_at,
        source_url=source.feed_url, response_hash=response_hash, scope=source.scope,
    )


def read_social(source, fetch, clock=utc_now):
    key = source.key
    name = f"{source.label} · {'YouTube' if source.platform == 'youtube' else 'TikTok'}"
    url = source.feed_url
    try:
        body = fetch(url, {urlsplit(url).hostname})
        parse = parse_youtube if source.platform == "youtube" else parse_tiktok
        posts = parse(source, body)
    except (ReadError, SourceError) as error:
        return [], source_result(key, name, url, clock(), error=error, scope=source.scope)
    observed = clock()
    body_hash = digest(body)
    captures = [
        make_social_capture(source, post.id, post.url, post.title, post.text,
                            post.published_at, observed, body_hash)
        for post in posts
    ]
    status = source_result(key, name, url, observed, count=len(captures), scope=source.scope)
    return captures, status


def read_watch(path: Path, clock=utc_now):
    captures, statuses = [], []
    try:
        with read_database(path) as db:
            for source in CONFIG.sources:
                items, status = read_watch_source(db, source, clock)
                captures.extend(items)
                statuses.append(status)
    except sqlite3.Error:
        captures = []
        statuses = [
            source_result(
                source.key, source.label, source.feed_url, clock(), scope=source.scope,
                error=SourceError("Baza monitoringu jest niedostępna lub ma niezgodny format."),
            )
            for source in CONFIG.sources
        ]
    return captures, statuses


def read_watch_source(db, source, clock):
    check = db.execute(
        """SELECT observed_at, status, found, http_status, retry_at
           FROM source_checks WHERE source_key = ? ORDER BY run_id DESC LIMIT 1""",
        (source.key,),
    ).fetchone()
    if check is None:
        return [], source_result(
            source.key, source.label, source.feed_url, clock(), scope=source.scope,
            error=SourceError("Monitor nie zapisał jeszcze odczytu tego profilu."),
        )
    latest_success = db.execute(
        """SELECT max(observed_at) FROM source_checks WHERE source_key = ? AND status = 'ok'""",
        (source.key,),
    ).fetchone()[0]
    rows = db.execute(
        """SELECT p.post_id, p.published_at, v.url, v.observed_at, v.text_sha256,
                  v.version, t.title, t.text, s.response_sha256
           FROM posts p
           JOIN post_versions v
             ON (v.platform, v.post_id, v.version) = (p.platform, p.post_id, p.latest_version)
           JOIN source_checks s ON (s.run_id, s.source_key) = (v.run_id, v.source_key)
           JOIN post_texts t ON (t.platform, t.post_id, t.version) = (v.platform, v.post_id, v.version)
           WHERE v.source_key = ?
           ORDER BY p.last_observed_at DESC, p.published_at DESC, p.post_id DESC
           LIMIT ?""",
        (source.key, POST_LIMIT),
    )
    captures = []
    for row in rows:
        if not public_link(row["url"]) or digest(row["text"]) != row["text_sha256"]:
            continue
        item = make_social_capture(source, row["post_id"], row["url"], row["title"], row["text"],
                                   row["published_at"], row["observed_at"], row["response_sha256"])
        item["provenance"].update(storage="watch_sqlite", sourceVersion=row["version"],
                                  originalTextSha256=row["text_sha256"])
        captures.append(item)
    error = None
    if check["status"] != "ok":
        code = check["http_status"]
        error = SourceError(f"HTTP {code}" if code else "Ostatni odczyt monitora nie powiódł się.", code)
    elif check["found"] and not captures:
        error = SourceError("Brak zachowanych opisów lub podpisów.")
    result = source_result(
        source.key, source.label, source.feed_url, check["observed_at"],
        count=len(captures), raw_count=check["found"], error=error, scope=source.scope,
    )
    if latest_success:
        result["lastSuccessAt"] = latest_success
    result["transport"] = "watch_sqlite"
    if check["retry_at"]:
        result["retryAt"] = check["retry_at"]
    return captures, result


# --- TikTok: profiles found through YouTube links, read from the public embed -----------------------
#
# Method: no login, no cookies, no account. The profile embed (https://www.tiktok.com/embed/@name) is the
# public widget TikTok documents for embedding creator profiles. It lists the latest videos with their
# captions and play counts. Limits: at most the ~10 videos the widget shows, no publication date (the video
# id carries a creation time that is stored as a derived estimate, never as publishedAt), no speech.

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/raw/discovery/social-2026-11-21"
YOUTUBE_REPLAY = ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz"
TIKTOK_HOSTS = {"www.tiktok.com"}
TIKTOK_PROFILE_LIMIT = 8
REQUEST_PAUSE = 3.3
TIKTOK_REF = re.compile(r"(?:https?://)?(?:www\.|m\.)?tiktok\.com/@([A-Za-z0-9_][A-Za-z0-9_.]{0,31})", re.I)
POLISH_LETTERS = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
POLISH_WORDS = re.compile(r"\b(?:czy|jak|nie|się|jest|na|do|dla|oraz|przez|który|która|co|po|ale|już)\b", re.I)
PROMO_MARKERS = re.compile(
    r"kod\s+(?:promocyjny|rabatowy|polecaj\w*)|\bcode\b|rabat|\bbonus\w*|link\s+w\s+(?:bio|opisie)|\bw\s+bio\b|"
    r"#(?:reklama|sponsor\w*|wsp[oó]lpraca|ad|partner\w*)\b|wsp[oó]łpraca\s+(?:reklamowa|z)|\bpartner\w*|\bpolecam\b|"
    r"za\s+darmo|darmow\w+\s+akcj\w+|zarejestruj|załóż\s+konto", re.I)


def is_polish(text):
    text = text or ""
    return bool(POLISH_LETTERS.search(text)) or len(POLISH_WORDS.findall(text)) >= 2


def _firm_index():
    path = ROOT / "analysis/firm-index.json"
    try:
        firms = json.loads(path.read_text(encoding="utf-8"))["firms"]
        return [(f["key"], f["label"], re.compile(f["pattern"], re.I),
                 [d for d in f.get("domains", []) if isinstance(d, str)]) for f in firms]
    except (OSError, KeyError, ValueError, TypeError, re.error):
        return []


def firm_signals(text):
    """Firm mentions (name, code, link) and promotion markers in a caption, each with the matched quote."""
    mentions = []
    for key, label, pattern, domains in _firm_index():
        match = pattern.search(text)
        domain = next((d for d in domains if d in text.lower()), None)
        if match or domain:
            mentions.append({"firm": key, "label": label, "quote": match.group(0) if match else domain,
                             "kind": "name" if match else "link"})
    markers = sorted({m.group(0).strip() for m in PROMO_MARKERS.finditer(text)}, key=str.lower)[:6]
    return {"firmMentions": mentions, "promoMarkers": markers, "promotion": bool(mentions and markers)}


def _creator_is_polish(creator):
    if not isinstance(creator, dict):
        return False
    sample = creator.get("languageSample") if isinstance(creator.get("languageSample"), dict) else {}
    return (creator.get("country") == "PL" or str(creator.get("defaultLanguage") or "").lower().startswith("pl")
            or (sample.get("pl") or 0) > 0)


def tiktok_references(captures, creators=()):
    """Profiles linked from the descriptions of captures of Polish-language sources, with the linking items.

    A source counts as Polish when its creator record says so (country, language, language sample) or the
    linking description itself is Polish. Links from English sources are left out, not guessed at."""
    by_id = {c.get("id"): c for c in creators if isinstance(c, dict)}
    found = {}
    for item in captures:
        text = item.get("description") if isinstance(item, dict) else None
        if not isinstance(text, str) or "tiktok.com" not in text.lower():
            continue
        if not (_creator_is_polish(by_id.get(item.get("creatorId"))) or is_polish(text)):
            continue
        for match in TIKTOK_REF.finditer(text):
            account = match.group(1).rstrip(".").lower()
            entry = found.setdefault(account, {"account": account, "captures": {}, "creators": set()})
            entry["captures"].setdefault(item.get("id"), item.get("url"))
            entry["creators"].add(item.get("creatorId"))
    ranked = sorted(found.values(), key=lambda e: (-len(e["captures"]), e["account"]))
    return ranked


def _embed_state(source, body):
    parser = TikTokEmbed(source)
    parser.feed(body.decode("utf-8"))
    parser.close()
    page = json.loads("".join(parser.state_parts))["source"]["data"][urlsplit(source.feed_url).path]
    return page["userInfo"], {item["id"]: item for item in page["videoList"] if isinstance(item, dict) and "id" in item}


def _metric(value, observed, source="tiktok_embed"):
    if type(value) is int:
        return {"value": value, "state": "observed", "observedAt": observed, "source": source}
    return {"value": None, "state": "not_collected", "observedAt": observed, "source": source}


def _id_time(post_id):
    """TikTok video ids carry the creation time in their upper bits. An estimate, flagged as derived."""
    try:
        moment = datetime.fromtimestamp(int(post_id) >> 32, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return moment.replace(microsecond=0).isoformat() if 2016 <= moment.year < 2100 else None


def read_tiktok_profile(entry, fetch, clock=utc_now):
    """One profile through the public embed. Returns (creator, captures, status)."""
    account = entry["account"]
    source = Source("tiktok", account, account)
    key, url = source.key, source.feed_url
    scope = "Podpisy ostatnich filmów z publicznego osadzenia profilu TikTok"
    try:
        body = fetch(url, TIKTOK_HOSTS)
        posts = parse_tiktok(source, body)
        user, stats = _embed_state(source, body)
    except (ReadError, SourceError, KeyError, TypeError, ValueError) as error:
        error = error if isinstance(error, SourceError) else SourceError(str(error)[:200] or "Nie odczytano osadzenia TikToka.")
        return None, [], source_result(key, f"TikTok @{account}", url, clock(), error=error, scope=scope)
    observed, digest_value = clock(), digest(body)
    pl = sum(is_polish(post.text) for post in posts)
    via = {"creatorIds": sorted(c for c in entry["creators"] if c), "captureIds": sorted(entry["captures"])[:8],
           "urls": [u for u in entry["captures"].values() if u][:8]}
    path = {"method": "crosslink", "adapter": "tiktok", "sourceId": "tiktok", "sourceUrl": url, "observedAt": observed,
            "responseSha256": digest_value, "reason": "profil TikTok wskazany w opisach polskojęzycznych materiałów YouTube",
            "via": via, "quotaUnits": 0, "import": False}
    creator = {
        "id": key, "name": str(user.get("nickname") or account)[:200], "platform": "tiktok",
        "url": source.profile_url, "handle": "@" + account,
        "discoveredVia": "Odnośnik w opisie publikacji YouTube", "status": "confirmed", "profileVerified": True,
        "isSeed": False, "bio": str(user.get("signature") or "")[:300], "discoveries": [path],
        "crosslinkDiscovery": {"profileUrl": source.profile_url, "references": via["captureIds"],
                               "description": "Profil wskazany w opisie; własność konta i związek z autorem opisu wymagają potwierdzenia.",
                               "discoveredAt": observed, "method": "crosslink"},
        "languageSample": {"pl": pl, "total": len(posts), "basis": "podpisy ostatnich filmów (litery i słowa polskie)"},
        "reach": {"asOf": observed, "source": "tiktok_embed", "primary": "followerCount", "metrics": {
            "followerCount": _metric(user.get("followerCount"), observed),
            "heartCount": _metric(user.get("heartCount"), observed)}},
    }
    captures = []
    for post in posts:
        video = stats.get(post.id, {})
        signals = firm_signals(post.text)
        estimate = _id_time(post.id)
        item = capture(
            f"tiktok:{post.id}", creator, post.text.strip()[:120] or f"@{account}", post.url, post.text,
            observed_at=observed, published_at=post.published_at, source_url=url, response_hash=digest_value,
            scope="tiktok_embed_caption", contentCompleteness="full", discovery=[path],
            reach={"asOf": observed, "source": "tiktok_embed", "primary": "viewCount",
                   "metrics": {"viewCount": _metric(video.get("playCount"), observed)}},
            mediaCoverage={"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                          "reason": "TikTok: odczytano tylko podpis, mowy nie pobrano"},
                           "frames": {"state": "not_collected", "moments": [], "intervalSec": None}},
            author=creator["name"], **signals,
        )
        if estimate and not post.published_at:
            item["publishedAtDerived"] = {"value": estimate, "basis": "tiktok_id_timestamp",
                                          "note": "Szacunek z identyfikatora filmu, nie data z platformy."}
        captures.append(item)
    status = source_result(key, f"TikTok @{account}", url, observed, count=len(captures), raw_count=len(posts), scope=scope)
    status["language"] = creator["languageSample"]
    return creator, captures, status


def discover_tiktok(ctx):
    """Adapter: profiles linked from YouTube descriptions, no manual seeds. Needs the YouTube stage first."""
    clock, fetch = ctx.clock, ctx.fetch
    pause = ctx.options.get("pause", REQUEST_PAUSE)
    sleep = ctx.options.get("sleep", time.sleep)
    limit = TIKTOK_PROFILE_LIMIT if ctx.budget is None else max(0, min(TIKTOK_PROFILE_LIMIT, int(ctx.budget)))
    known = {c for c in (ctx.previous or {})}
    entries = tiktok_references(ctx.captures, list((ctx.previous or {}).values()))
    creators, captures, statuses, skipped_language = [], [], [], 0
    for index, entry in enumerate(entries[:limit]):
        if index:
            sleep(pause)
        ctx.heartbeat()
        creator, items, status = read_tiktok_profile(entry, fetch, clock)
        status["crosslink"] = True
        if creator and creator["languageSample"]["pl"] == 0:
            statuses.append({**status, "status": "skipped", "count": 0,
                             "error": "Pominięto: podpisy nie są po polsku (filtr języka)."})
            skipped_language += 1
            continue
        statuses.append(status)
        if creator:
            creators.append(creator)
            captures.extend(items)
    for entry in entries[limit:]:
        statuses.append(source_result(f"tiktok:{entry['account']}", f"TikTok @{entry['account']}",
                                      f"https://www.tiktok.com/@{entry['account']}", clock(), scope="limit przebiegu"))
        statuses[-1].update(status="skipped", error="Pominięto: limit profili TikTok w tym przebiegu.")
    failed = sum(s["status"] == "error" for s in statuses)
    summary = source_result("tiktok", "TikTok · profile z odnośników", "https://www.tiktok.com/", clock(),
                            count=len(captures), raw_count=len(entries),
                            scope="Publiczne osadzenie profilu; podpisy, bez dat i mowy")
    if entries and not creators:
        summary["status"], summary["error"] = "error", "Nie odczytano żadnego profilu TikTok z odnośników."
    elif failed or entries[limit:]:
        summary["status"] = "partial"
        summary["error"] = f"Nie odczytano {failed} profili, pominięto {len(entries[limit:])} (limit)."
    elif not entries:
        summary["status"] = "empty"
    if summary["status"] in ("error", "partial"):
        summary.pop("lastSuccessAt", None)
        summary["lastError"] = {"code": "tiktok_partial" if creators else "tiktok_unavailable", "message": summary["error"],
                                "at": clock(), "nextStep": "Sprawdź statusy profili; odczyt powtórzy się w następnym skanie."}
    summary["languageFiltered"] = skipped_language
    return {"creators": creators, "captures": captures, "sources": [summary, *statuses],
            "status": summary["status"]}


# --- Facebook and Instagram: dated access attempt without a login ----------------------------------

META_PATH = {
    "name": "Meta Content Library i Content Library API",
    "url": "https://developers.facebook.com/docs/content-library-and-api/get-access",
    "audience": "naukowcy i instytucje badawcze (kwalifikowana afiliacja), wniosek w Research Tools Manager, weryfikacja wniosku przez CASD",
    "alternative": "Graph API: funkcja Page Public Content Access (strony Facebooka) i Instagram oEmbed Read po przeglądzie aplikacji",
    "dsa": "Art. 40 DSA (dostęp badawczy do danych publicznych) jako podstawa wniosku",
}
META_NEXT_STEP = ("Wystąpić o dostęp do Meta Content Library (Research Tools Manager) jako instytucja badawcza albo "
                  "o aplikację Meta z funkcją Page Public Content Access; do czasu decyzji wpisy z tej platformy "
                  "wprowadza się oznaczonym importem ręcznym.")
META_PROBE_FILES = ("probe-1-requests.json", "probe-2-requests.json")


def classify_meta_response(status, headers, body):
    """What a public profile request returned: login_redirect, metadata_only, content or other."""
    location = {k.lower(): v for k, v in (headers or {}).items()}.get("location", "")
    if status in (301, 302, 303, 307, 308) and "/login" in location:
        return "login_redirect"
    if status in (301, 302, 303, 307, 308):
        return "redirect"
    if status == 200 and b"og:title" in body:
        has_posts = bool(re.search(rb'"(?:message|story)"\s*:\s*\{"text"|creation_time', body))
        return "content" if has_posts else "metadata_only"
    return "other"


def documented_probe(platform, root=FIXTURES):
    """Datowana próba z zachowanych surowych odpowiedzi (probe-*-requests.json)."""
    rows = []
    for name in META_PROBE_FILES:
        path = Path(root) / name
        if path.is_file():
            rows.extend(r for r in json.loads(path.read_text(encoding="utf-8")) if r.get("name", "").startswith(platform))
    out = []
    for row in rows:
        entry = {k: row.get(k) for k in ("url", "at", "status", "bytes", "sha256")}
        headers = {k.lower(): v for k, v in (row.get("headers") or {}).items()}
        entry["location"] = headers.get("location")
        entry["result"] = row.get("result")
        out.append(entry)
    return out


def meta_blocked_result(platform, label, clock, probes):
    at = clock()
    logins = sum(1 for p in probes if p.get("result") == "login_redirect")
    meta = sum(1 for p in probes if p.get("result") == "metadata_only")
    if platform == "instagram":
        what = "przekierowanie do logowania (HTTP 302 → /accounts/login/)"
    else:
        what = "strona profilu zwraca tylko metadane (nazwa, liczba obserwujących, opis), bez wpisów"
    message = (f"{label}: wpisy organiczne niedostępne bez logowania: {what}. Reklamy pobiera osobne źródło (Biblioteka Reklam Meta). "
               f"Właściwa ścieżka: {META_PATH['name']} ({META_PATH['audience']}).")
    last = {"code": "access_blocked", "message": message[:300], "at": at, "nextStep": META_NEXT_STEP}
    source = {"id": platform, "name": f"{label} · wpisy organiczne", "url": f"https://www.{platform}.com/",
              "status": "access_blocked", "count": 0, "observedAt": at, "error": message[:300], "lastError": last,
              "scope": "Wpisy organiczne z publicznych profili bez logowania; reklamy to osobne źródło (Biblioteka Reklam Meta)",
              "blockedScope": "organic_posts",
              "accessPath": META_PATH, "probe": {"attempts": probes, "loginRedirects": logins, "metadataOnly": meta}}
    return {"creators": [], "captures": [], "sources": [source], "status": "access_blocked"}


def _meta_probe_live(platform, urls, fetch_raw, clock, sleep, pause):
    rows = []
    for index, url in enumerate(urls):
        if index:
            sleep(pause)
        at = clock()
        try:
            status, headers, body = fetch_raw(url)
        except SourceError as error:
            rows.append({"url": url, "at": at, "status": error.status, "result": "error", "error": str(error)})
            continue
        rows.append({"url": url, "at": at, "status": status, "bytes": len(body), "sha256": digest(body),
                     "location": {k.lower(): v for k, v in headers.items()}.get("location"),
                     "result": classify_meta_response(status, headers, body)})
    return rows


def make_meta_adapter(platform, label):
    def discover(ctx):
        probes = documented_probe(platform)
        live = ctx.options.get("meta_probe")  # callable (url) -> (status, headers, body); off by default
        if live:
            urls = [p["url"] for p in probes][:1] or [f"https://www.{platform}.com/"]
            probes = _meta_probe_live(platform, urls, live, ctx.clock, ctx.options.get("sleep", time.sleep),
                                      ctx.options.get("pause", REQUEST_PAUSE))
        return meta_blocked_result(platform, label, ctx.clock, probes)
    return discover


discover_facebook = make_meta_adapter("facebook", "Facebook")
discover_instagram = make_meta_adapter("instagram", "Instagram")


# --- Replay built from the stored raw responses -----------------------------------------------------

def build_replay(root=FIXTURES, youtube_replay=YOUTUBE_REPLAY):
    """The dated social event of 2026-11-21 rebuilt from the saved raw responses, without network."""
    youtube = json.loads(gzip.decompress(Path(youtube_replay).read_bytes()))
    entries = {e["account"]: e for e in tiktok_references(youtube["captures"], youtube["creators"])}
    log = {r["name"]: r for name in META_PROBE_FILES if (Path(root) / name).is_file()
           for r in json.loads((Path(root) / name).read_text(encoding="utf-8"))}
    creators, captures, sources = [], [], []
    for name, row in sorted(log.items()):
        if not name.startswith("tiktok-embed-"):
            continue
        account = name[len("tiktok-embed-"):]
        body = gzip.decompress((Path(root) / f"{name}.html.gz").read_bytes())
        entry = entries.get(account) or {"account": account, "captures": {}, "creators": set()}
        creator, items, status = read_tiktok_profile(entry, lambda url, hosts, b=body: b, lambda r=row: r["at"])
        status["language"] = (creator or {}).get("languageSample")
        if creator and creator["languageSample"]["pl"] == 0:
            status.update(status="skipped", count=0, error="Pominięto: podpisy nie są po polsku (filtr języka).")
            sources.append(status)
            continue
        sources.append(status)
        if creator:
            creators.append({**creator, "mode": "replay"})
            captures.extend({**item, "mode": "replay"} for item in items)
    for platform, label in (("facebook", "Facebook"), ("instagram", "Instagram")):
        probes = documented_probe(platform, root)
        blocked = meta_blocked_result(platform, label, lambda: "2026-11-21T20:37:49+00:00", probes)
        sources.extend(blocked["sources"])
    return {"creators": creators, "captures": captures, "sources": sources, "status": "partial",
            "fixtureNote": "Zdarzenie social z 2026-11-21 odtworzone z surowych odpowiedzi (TikTok embed; próby FB i IG bez logowania)."}
