#!/usr/bin/env python3
"""Buduje web/sample/state.json: przykładowy stan pulpitu z rzeczywistych rekordów (21 XI 2026).

Tylko odczyt repozytorium: opisy i napisy z .runtime/media-cache, wyszukiwania i kanały z
fixtures/raw/discovery/youtube-api-2026-11-21, kadry z fixtures/raw/media/2026-11-21, sprawy FBO
z fixtures/raw/review-compare. Wynik każdego filmu liczy aktualny kod (api.enrich z cache offline
oraz analysis.engine.analyze), więc pola v2 mają kształt z kontraktu.

Uruchomienie z katalogu głównego repozytorium:  python3 web/sample/build_sample.py
"""
import glob
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("INVESTWATCH_MEDIA_CACHE", str(ROOT / ".runtime/media-cache"))

from analysis.engine import analyze  # noqa: E402
from api import enrich  # noqa: E402

OUT = ROOT / "web/sample"
API = ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21"
MEDIA = ROOT / "fixtures/raw/media/2026-11-21"
OBSERVED = "2026-11-21T19:20:06+00:00"
SCAN_ID = "887f077481d240b28397afa28587ea60"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


snapshot = load(OUT / "snapshot-v1.json")
channels = {c["channelId"]: c for c in load(API / "channels-by-subscribers.json")}

# --- ścieżki odkrycia filmów z zapisanych wyników wyszukiwania ---
paths = {}
snippets = {}
for file in sorted(API.glob("*search*.json")):
    data = load(file)
    if not isinstance(data, dict):
        continue
    match = re.match(r"\d+-search-(brand|topic|promo)-(.+)-p(\d+)\.json", file.name)
    if not match:
        continue
    kind, slug, page = match.group(1), match.group(2), int(match.group(3))
    for position, item in enumerate(data.get("items", []), 1):
        ident = item.get("id")
        vid = ident.get("videoId") if isinstance(ident, dict) else None
        if not vid:
            continue
        snippets.setdefault(vid, item.get("snippet", {}))
        paths.setdefault(vid, []).append({
            "method": "data_api_search", "adapter": "collectors/youtube.py",
            "queryKind": {"brand": "marka", "topic": "temat", "promo": "fraza promocyjna"}[kind],
            "query": slug.replace("-", " "), "position": position, "page": page,
            "sourceId": f"youtube-search:{slug}", "observedAt": "2026-11-21T19:03:47+00:00"})

# kanały, których nie ma w wyszukiwaniu filmów (DETERMINACJA, Konopskyy)
EXTRA_CHANNEL = {"xtMqKkFO-0M": "UCnmJzS-tFT7DlxIMFxYGcHw"}

TITLES = {}
for vid_file in MEDIA.glob("*.json"):
    if vid_file.name.startswith("kandydaci"):
        continue
    TITLES[vid_file.stem] = load(vid_file)

# Filmy: kolejność = kolejność prezentacji
VIDEOS = ["7M0rC6-Rueo", "OIyPE0z2mng", "ZJrT-X08Xwc", "yIbtMnfP25Q", "AqXHkxDzSDI", "CDk20n4u9Kk",
          "eQYmvRfHtr8", "YQH4FEP9exI", "ePfzHQVf-lc", "o2GfnmVVkO8", "_aqCM37gK1U", "p_ui_fqLdV0",
          "i3QxMqyRlks", "xtMqKkFO-0M", "O5YmmKadQQw"]
results = {r["videoId"]: r for r in load(MEDIA / "kandydaci-wyniki.json")["results"]}


def channel_of(vid, meta):
    cid = snippets.get(vid, {}).get("channelId") or EXTRA_CHANNEL.get(vid)
    if cid:
        return cid
    for row in channels.values():
        if row["name"].casefold() == (meta.get("channel") or "").casefold():
            return row["channelId"]
    return None


creators = {c["id"]: c for c in snapshot["creators"]}
findings = []
shown_frames = {}
for vid in VIDEOS:
    cache = ROOT / ".runtime/media-cache" / vid
    if not (cache / "meta.json").is_file():
        print("pominięto (brak cache):", vid)
        continue
    meta = load(cache / "meta.json")
    cid = channel_of(vid, meta)
    creator_id = f"youtube:{cid}" if cid else f"youtube:kanał-{re.sub('[^a-z0-9]+', '-', meta['channel'].casefold())}"
    row = channels.get(cid, {})
    upload = meta.get("uploadDate") or "20260101"
    published = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}T00:00:00+00:00"
    capture = {
        "id": f"youtube:{vid}", "creatorId": creator_id, "title": meta["title"],
        "url": f"https://www.youtube.com/watch?v={vid}", "platform": "youtube", "description": meta.get("description") or "",
        "module": "M1", "observedAt": OBSERVED, "publishedAt": published, "contentHash": results.get(vid, {}).get("videoId", vid),
        "materialType": "youtube_data_api_full",
        "provenance": {"sourceUrl": "https://www.googleapis.com/youtube/v3/videos", "observedAt": OBSERVED, "truncated": False},
    }
    captures, _ = enrich.enrich_media([capture], "replay")
    found = analyze(captures[0])
    # kadry: obserwacje agenta C oraz zapisane miniatury (3-4 na film)
    frames = []
    for frame in (results.get(vid) or {}).get("frames", []):
        src = ROOT / frame["path"]
        if frame["method"] != "stream_ffmpeg_360p" and "stream" not in frame["path"] and (results[vid]["frames"] and len(frames) >= 3):
            continue
        if src.is_file() and len(frames) < 3:
            name = f"{vid}-{int(frame['time']):05d}.jpg"
            shutil.copyfile(src, OUT / "frames" / name)
            frames.append({"t": frame["time"], "text": frame["observation"], "method": frame["method"],
                           "deepLink": frame["deepLink"], "thumbnailUrl": f"/sample/frames/{name}",
                           "frameSha256": frame["sha256"]})
    evidence = list(found.get("evidence") or [])
    for index, frame in enumerate(frames, 1):
        evidence.append({"id": f"fr-{index}", "kind": "frame", "role": "context", "modality": "frame", "text": frame["text"],
                         "url": capture["url"], "sourceUrlAtTime": frame["deepLink"], "start": frame["t"],
                         "thumbnailUrl": frame["thumbnailUrl"], "method": frame["method"], "sourceVersion": 1,
                         "observedAt": OBSERVED, "available": True})
    creator = creators.setdefault(creator_id, {
        "id": creator_id, "name": row.get("name") or meta["channel"], "platform": "youtube",
        "url": f"https://www.youtube.com/channel/{cid}" if cid else None,
        "status": "confirmed" if cid else "candidate", "persistentId": cid,
        "handle": row.get("handle"), "firstSeenScanId": SCAN_ID, "isNew": not row.get("seeded", False),
        "reach": ({"metric": "subscribers", "value": row.get("subscribers"), "hidden": row.get("subscribersState") == "hidden",
                   "observedAt": row.get("subscribersAsOf"), "source": "youtube-data-api"} if row else None),
        "discovery": ([{"method": "data_api_search", "query": row["discovery"]["query"], "position": row["discovery"]["position"],
                        "page": row["discovery"]["page"], "at": row["discovery"]["observedAt"], "sourceId": "youtube-search",
                        "queryKind": row["discovery"]["queryKind"]}] if row.get("discovery") else []),
        "seed": bool(row.get("seeded")),
    })
    body = {**found, "evidence": evidence, "id": f"youtube:{vid}", "creatorId": creator_id, "creatorName": creator["name"],
            "status": "new", "revision": 1, "version": 1, "mode": "replay", "origin": "replay",
            "needsRecalc": False, "firstScanId": SCAN_ID, "lastScanId": SCAN_ID,
            "discovery": paths.get(vid, []), "frames": frames,
            "history": [{"seq": 1, "at": OBSERVED, "action": "capture", "changeKind": "content",
                         "note": "Zachowano wersję materiału", "details": {"version": 1}}],
            "versions": [{"version": 1, "observedAt": OBSERVED, "changeKind": "content", "details": {}}]}
    if row.get("subscribers") is not None:
        body["reach"] = {"metric": "subscribers", "value": row["subscribers"], "hidden": False,
                         "observedAt": row.get("subscribersAsOf"), "source": "youtube-data-api (kanał)"}
    findings.append(body)

# --- sprawy FBO (Apple Podcasts), z zapisanych wejść D ---
inputs = load(ROOT / "fixtures/raw/review-compare/qualification-inputs.json")["items"]
for item in inputs:
    if not item["capture"]["id"].startswith("apple-podcasts:946719109"):
        continue
    found = analyze(item["capture"])
    body = {**found, "id": item["capture"]["id"], "creatorName": "Finanse Bardzo Osobiste", "status": "new", "revision": 1,
            "version": 1, "mode": "replay", "origin": "replay", "needsRecalc": False, "firstScanId": SCAN_ID, "lastScanId": SCAN_ID,
            "history": [{"seq": 1, "at": OBSERVED, "action": "capture", "changeKind": "content",
                         "note": "Zachowano wersję materiału", "details": {"version": 1}}],
            "versions": [{"version": 1, "observedAt": OBSERVED, "changeKind": "content", "details": {}}]}
    findings.append(body)

# --- DETERMINACJA (pełny opis z fikstury discovery) ---
state_full = None

# --- starsze rekordy (kształt v1: bez reviewDecision) ---
for old in snapshot["legacyFindings"]:
    old = dict(old)
    old.setdefault("origin", "synthetic" if old["id"].startswith("demo-") or old.get("synthetic") else old.get("mode", "live"))
    if old.get("module") == "M1" and old.get("rulesVersion"):
        old["needsRecalc"] = True
        old["needsRecalcReason"] = f"Wynik z reguł {old['rulesVersion'].replace('investwatch-rules-pl-', '')}; bieżące investwatch-m1-qual-1.0"
    if old["id"] in ("demo-studio-aurora", "demo-aurora-kod", "demo-pracownia-edukacja"):
        old["origin"] = "synthetic"
    findings.append(old)

# Przykładowa decyzja w „Zamkniętych” (jawnie oznaczona jako przypadek testowy interfejsu)
for body in findings:
    if body["id"] == "youtube:o2GfnmVVkO8":
        body["status"] = "closed"
        body["revision"] = 3
        body["lastDecision"] = {"status": "closed", "at": "2026-11-21T19:40:00+00:00", "version": 1, "revision": 3,
                                "route": body["reviewDecision"]["route"],
                                "note": "Przykład zamkniętej sprawy (przypadek testowy interfejsu, nie decyzja analityka)."}
        body["history"].append({"seq": 2, "at": "2026-11-21T19:40:00+00:00", "action": "decision",
                                "changeKind": "decision", "note": body["lastDecision"]["note"], "details": {"status": "closed"}})

scans = snapshot["scans"]
scans[0] = {**scans[0], "sources": {"ok": 24, "empty": 2, "partial": 1, "failed": 7, "total": 35, "candidate": 1},
            "referred": sum(1 for f in findings if (f.get("reviewDecision") or {}).get("route") == "refer"),
            "progress": None}
state = {
    "asOf": "2026-11-21T19:30:00+00:00",
    "creators": list(creators.values()),
    "sources": snapshot["sources"],
    "scans": scans,
    "events": snapshot["events"],
    "calibration": snapshot["calibration"],
    "findings": findings,
    "analysisCurrent": {"rules": "investwatch-m1-qual-1.0", "model": None, "schema": 2, "variant": "qual_d"},
    "threshold": {"id": "default-qual_d", "variant": "qual_d", "value": 60, "setAt": "2026-11-21T00:00:00Z"},
    "qualification": {"id": "shadow", "variant": "qual_d", "setAt": "2026-11-21T00:00:00Z", "validatedBy": None},
}
(OUT / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
print("rekordów:", len(findings), "twórców:", len(creators))
for f in findings:
    d = f.get("reviewDecision") or {}
    print(f["id"][:42].ljust(42), f["module"], d.get("route", "-").ljust(9), (f.get("reviewScore") or {}).get("value"),
          (f.get("adRegistry") or {}).get("state"), (f.get("adRelationship") or {}).get("status"))
