"""Media step of a scan (contract v2, steps S8 and the speech gate): transcript for every video with a signal.

A video reaches "Co wymaga sprawdzenia" only after the description and the speech were examined. So the transcript is
fetched for EVERY YouTube M1 capture that carries a relation proof or names a firm of the registry in the description
or title (relation evidence first, then by reach). The per-scan limit is a time and count budget; what does not fit
stays in the media backlog (table `media_state` and the stored case) and is taken by the next scan or by a light
`mode=enrich` scan, which calls no discovery adapter and spends no YouTube Data API quota.

Frames come only for a video that is still `refer` after the speech was examined: 2-3 frames at the moments of the
call to the description link or of a firm mention, else the beginning, the middle and the end. There is no OCR: a
frame is evidence for the analyst, and the coverage says so. A media error is a gap in `mediaCoverage`, never a
failed scan. Replay makes no request: it reads the replay media pack (`api.replay_pack`, outside Git) with the
transcripts and frames of the dated event. Without the pack the transcript is a gap ("brak paczki") and the scan
reports it as a source status, not as an error.
"""
import os
from pathlib import Path
import time

from . import replay_pack, store

PROMO_KINDS = {"reklama", "wspolpraca", "partner", "sponsor", "link_w_opisie", "kod", "promocja"}
BLOCKING = {"rate_limited", "login_required"}  # host-wide refusal stops the step; a 429 of one video (scope video) does not
MAX_TRIES = 3  # failed attempts after which a video is permanently unavailable, with the reason


def cache_dir():
    return Path(os.environ.get("INVESTWATCH_MEDIA_CACHE") or store.STATE / "media-cache")


def replay_cache(pack):
    """Replay reads the pack when it is intact, else the state cache (which may be empty: then it is a gap)."""
    return Path(pack["pack"]) if pack and pack["state"] == "present" else cache_dir()


def pack_source(summary):
    """Source row for the media pack of a replay scan (status `empty`/`ok`: a missing pack is a gap, not an error)."""
    pack = summary.get("replayPack")
    if not pack:
        return None
    present = pack["state"] == "present"
    return {"id": "replay-media", "name": "Paczka mediów replay", "kind": "asr", "status": "ok" if present else "empty",
            "count": len(pack.get("videos") or []), "target": pack.get("pack"),
            "scope": ("transkrypcje i kadry z paczki poza Gitem, bez sieci" if present else
                      "brak paczki mediów: transkrypcje filmów to luka pokrycia (" + "; ".join(pack.get("problems") or []) + ")"),
            "manifestSha256": pack.get("manifestSha256"), "observedAt": store.utc()}


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _offline_client(media):
    def run(args, timeout):
        return 127, "", "offline: odczyt wyłącznie z cache"

    def fetch(url, timeout):
        raise OSError("offline: odczyt wyłącznie z cache")
    return media.Client(run=run, fetch=fetch)


def signal_of(finding):
    """relation (proof of a commercial relation), firm (a firm of the registry is named) or None."""
    relation = finding.get("adRelationship") if isinstance(finding.get("adRelationship"), dict) else {}
    if (relation.get("status") in ("declared", "documented", "probable")
            or (finding.get("adRegistry") or {}).get("state") in ("candidate", "included")
            or any(isinstance(p, dict) and p.get("type") == "U1" for p in finding.get("premises") or [])):
        return "relation"
    firm = relation.get("firm") if isinstance(relation.get("firm"), dict) else {}
    if firm.get("mention") or firm.get("candidates") or finding.get("relationships"):
        return "firm"
    return None


def _rank(capture, signal):
    views = (((capture.get("reach") or {}).get("metrics") or {}).get("viewCount") or {}).get("value")
    rank = (((capture.get("priority") or {}).get("acquisition") or {}).get("rank")) or 10 ** 9
    return (0 if signal == "relation" else 1, -(views if isinstance(views, (int, float)) else -1), rank, capture["id"])


def _is_video(capture):
    return capture.get("module", "M1") == "M1" and str(capture.get("id", "")).startswith("youtube:")


def _cached(media, capture, cache):
    vid = media.video_id(capture.get("url")) or media.video_id(str(capture.get("id", ""))[8:])
    return bool(vid) and ((cache / vid / "transcript.json").is_file() or (cache / vid / "meta.json").is_file())


def _pending(capture, reason):
    """Not attempted (budget, replay, blocked): the speech is still to be examined."""
    return {**capture, "mediaCoverage": {
        "transcript": {"state": "pending", "source": "none", "windows": [], "durationSec": None, "reason": reason},
        "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}


def _gap(capture, reason):
    """An attempt that failed: retried by a later scan unless the reason is permanent."""
    return {**capture, "mediaCoverage": {
        "transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None, "reason": reason},
        "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}


def _merge(capture, result):
    merged = dict(capture)
    if result.get("segments"):
        merged["segments"] = result["segments"]
        merged["mediaVersion"] = result.get("mediaVersion")
    merged["mediaCoverage"] = result["mediaCoverage"]
    if result.get("frames"):
        merged["frames"] = result["frames"]
    return merged


def merge_known(captures, states):
    """Re-use what an earlier scan fetched: a rescanned video must not lose its transcript or coverage."""
    out = []
    for cap in captures:
        known = states.get(cap.get("id")) if states else None
        if known and _is_video(cap):
            cap = {**cap, **{k: known[k] for k in store.MEDIA_KEYS if k in known and not (k == "segments" and cap.get("segments"))}}
        out.append(cap)
    return out


def _fallback_moments(capture):
    """Beginning, middle and end when the speech does not point to a moment."""
    transcript = ((capture.get("mediaCoverage") or {}).get("transcript") or {})
    duration = transcript.get("durationSec") or (capture.get("youtube") or {}).get("durationSec")
    if not isinstance(duration, (int, float)) or duration <= 0:
        segments = capture.get("segments") or []
        duration = max((s.get("end") or 0 for s in segments), default=0)
    if not duration:
        return [5.0]
    return [round(min(10.0, max(1.0, duration * 0.02)), 1), round(duration / 2, 1), round(max(duration - 15.0, duration * 0.9), 1)]


def _frame_moments(media, capture, finding, limit):
    """The call to the description link and firm mentions in the speech, then the moments the qualification points to."""
    link, firm, other = [], [], []
    for mark in media.find_markers(capture.get("segments") or [], ""):
        if mark["modality"] != "transcript":
            continue
        kinds = set(mark["kinds"])
        (link if "link_w_opisie" in kinds else firm if "broker" in kinds else other if PROMO_KINDS & kinds else []).append(mark["start"])
    pointed = [m["start"] for m in (finding.get("reviewDecision") or {}).get("moments", []) if m.get("start") is not None]
    chosen = []
    for t in [*link, *pointed, *firm, *other]:
        if all(abs(float(t) - c) > 5 for c in chosen):
            chosen.append(float(t))
    chosen = sorted(chosen[:limit])
    return chosen or _fallback_moments(capture)[:limit]


def _refer(finding):
    return (finding.get("reviewDecision") or {}).get("route") == "refer"


def _framed(capture):
    return bool(capture.get("frames") or capture.get("framesAttempted"))


def enrich_media(captures, mode, runner=None, *, media=None, analyze=None, heartbeat=None, known=None, backlog=False,
                 clock=time.monotonic):
    """Return (captures with transcript, coverage and optional frames, summary). Never raises.

    `known` maps case id to the stored media state. With `backlog=True` the captures are the stored cases of an
    `enrich` scan: only changed ones come back, and defaults give a larger budget."""
    summary = {"examined": 0, "transcripts": 0, "frames": 0, "gaps": 0, "network": 0, "cached": 0, "deferred": 0,
               "noSignal": 0, "bytes": 0, "requests": 0, "seconds": 0.0}
    try:
        if media is None:
            from collectors import media
        if analyze is None:
            from analysis.engine import analyze
        from analysis.engine import transcript_phase
    except Exception as exc:  # the adapter module is optional
        summary["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return captures, summary
    live = mode in ("live", "enrich")
    pack = None if live or mode != "replay" else replay_pack.inspect()
    if pack and any(_is_video(c) for c in captures):
        summary["replayPack"] = {k: pack[k] for k in ("state", "pack", "files", "manifestSha256", "problems")} | {"videos": pack["videos"]}
    cache = replay_cache(pack)
    framing = live or bool(pack and pack["state"] == "present")
    budget = _int("INVESTWATCH_MEDIA_PER_SCAN", 150 if backlog else 25)
    window = _int("INVESTWATCH_MEDIA_SCAN_SECONDS", 1800 if backlog else 600)  # time budget of the whole step
    seconds = _int("INVESTWATCH_MEDIA_SECONDS", 120)
    frame_limit = _int("INVESTWATCH_MEDIA_FRAMES", 3)
    known = known or {}
    began = clock()
    captures = merge_known(captures, known)
    ranked = []
    for cap in captures:
        if not _is_video(cap):
            continue
        try:
            found = analyze(cap)
        except Exception:
            found = {}
        signal = signal_of(found)
        phase = transcript_phase(cap)["state"]
        if signal is None:
            summary["noSignal"] += 1
        elif (phase == "pending" and not cap.get("segments")) or (framing and phase != "pending" and _refer(found) and not _framed(cap)):
            ranked.append((_rank(cap, signal), cap))
    done = {}
    blocked = None
    # fewest attempts first (rotation: a video that was refused yesterday does not block the head of the queue),
    # within one count the earlier ranking
    order = sorted(ranked, key=lambda pair: (int((known.get(pair[1]["id"]) or {}).get("attempts") or 0), pair[0]))
    for _, cap in order:
        summary["examined"] += 1
        if heartbeat:
            heartbeat()
        merged = cap
        if transcript_phase(cap)["state"] == "pending":
            cached = _cached(media, cap, cache)
            if not cached and (not live or budget <= 0 or clock() - began > window or blocked):
                reason = ((f"replay: brak paczki mediów ({'; '.join(pack['problems'])})" if pack and pack["state"] != "present"
                           else "replay: film poza paczką mediów, transkrypcja niedostępna offline") if not live else
                          f"YouTube zablokował pobieranie ({blocked})" if blocked else
                          "limit filmów na skan; transkrypcja w kolejnym skanie")
                done[cap["id"]] = _pending(cap, reason)
                summary["deferred"] += 1
                continue
            tries = int((known.get(cap["id"]) or {}).get("attempts") or 0)
            try:
                options = {"cache_dir": cache, "allow_asr": False, "max_seconds": seconds}
                kwargs = {} if live else {"client": _offline_client(media)}
                result = media.enrich(cap, {"media": options}, **kwargs)
                merged = {**_merge(cap, result), "mediaAttempts": tries + 1}
                stats = result.get("stats") or {}
                summary["cached" if cached else "network"] += 1
                summary["bytes"] += stats.get("bytes", 0) or 0
                summary["requests"] += stats.get("requests", 0) or 0
                if not cached:
                    budget -= 1
                if result.get("segments"):
                    summary["transcripts"] += 1
                else:
                    summary["gaps"] += 1
                status = (result.get("error") or {}).get("status")
                scope = (result.get("error") or {}).get("scope", "host")
                if status == "login_required" or (status == "rate_limited" and scope == "host"):
                    blocked = summary["blocked"] = status
                    done[cap["id"]] = _pending(cap, f"YouTube zablokował pobieranie ({status})")
                    summary["deferred"] += 1
                    continue
                if status == "rate_limited" and not result.get("segments"):  # this video only: count the try, go on
                    summary["videoLimited"] = summary.get("videoLimited", 0) + 1
                    if tries + 1 >= MAX_TRIES:  # persistent refusal of one video: permanently unavailable, with the reason
                        done[cap["id"]] = {**_gap(cap, f"unavailable: nieudane {MAX_TRIES} próby (YouTube odmawia napisów tego filmu: 429)"),
                                           "mediaAttempts": tries + 1}
                    else:
                        done[cap["id"]] = {**_pending(cap, "YouTube odmówił napisów tego filmu (429); ponowienie w kolejnym skanie"),
                                           "mediaAttempts": tries + 1}
                        summary["deferred"] += 1
                    continue
                if status and not result.get("segments") and tries + 1 >= MAX_TRIES:  # the last failure is final
                    merged = {**_gap(cap, f"unavailable: nieudane {MAX_TRIES} próby ({merged['mediaCoverage']['transcript']['reason']})"[:240]),
                              "mediaAttempts": tries + 1}
            except Exception as exc:  # media failure is a coverage gap, not a scan failure
                reason = f"media: {type(exc).__name__}: {exc}"[:200]
                done[cap["id"]] = {**_gap(cap, f"unavailable: nieudane {MAX_TRIES} próby ({reason})" if tries + 1 >= MAX_TRIES else reason),
                                   "mediaAttempts": tries + 1}
                summary["gaps"] += 1
                continue
        if framing and frame_limit > 0 and not blocked and not _framed(merged) and transcript_phase(merged)["state"] != "pending":
            try:
                finding = analyze(merged)
                if _refer(finding) and budget > 0 and clock() - began <= window:
                    moments = _frame_moments(media, merged, finding, frame_limit)
                    framed = media.enrich(merged, {"media": {"cache_dir": cache, "allow_asr": False, "max_seconds": seconds,
                                                             "frames_at": moments}}, frames_at=moments,
                                          **({} if live else {"client": _offline_client(media)}))
                    stats = framed.get("stats") or {}
                    summary["bytes"] += stats.get("bytes", 0) or 0
                    summary["requests"] += stats.get("requests", 0) or 0
                    summary["frameFetches"] = summary.get("frameFetches", 0) + 1
                    budget -= 1
                    ferr = framed.get("error") or {}
                    if ferr.get("status") == "login_required" or (ferr.get("status") == "rate_limited" and ferr.get("scope", "host") == "host"):
                        blocked = summary["blocked"] = ferr["status"]
                    else:
                        coverage = merged.get("mediaCoverage")
                        merged = {**_merge(merged, framed), "framesAttempted": True}
                        if not framed.get("segments") and coverage:  # frames never overwrite the transcript state
                            merged["mediaCoverage"] = {**merged["mediaCoverage"], "transcript": coverage["transcript"]}
                        summary["frames"] += len(framed.get("frames") or [])
            except Exception:  # frames are optional
                merged = {**merged, "framesAttempted": True}
                summary["gaps"] += 1
        done[cap["id"]] = merged
    summary["seconds"] = round(clock() - began, 1)
    if backlog:
        return [done[c["id"]] for c in captures if c["id"] in done], summary
    return [done.get(c["id"], c) for c in captures], summary
