#!/usr/bin/env python3
"""Predykcje q-v2: rules_1_2 i qual_d tym samym kodem produktu (analysis.engine.analyze).

Bez sieci i bez modeli (semantic=None: E5 i Vosk nie są uruchamiane). Dla każdego materiału M1 z
etykiety-agentow.jsonl buduje wejście z datowanych danych w repozytorium i .runtime/media-cache:

- pelne: opis (yt-dlp meta.json) + pełna auto-transkrypcja (transcript.json) + kadry z przeglądem agenta C
  (fixtures/raw/media/2026-11-21/<id>.json) + flaga płatnej promocji (replay B albo surowa odpowiedź API);
- opis: ten sam rekord bez mowy, kadrów i mediaCoverage (bramka mowy powinna wstrzymać refer).

Materiały q-v1 bez mediów (podcasty, PeerTube, TikTok, 2 filmy YouTube) idą z replay
fixtures/raw/discovery/2026-11-21.json w obu stanach tak samo.

Uruchomienie z katalogu głównego repo:  python3 -B fixtures/validation/q-v2/uruchom_warianty.py
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from analysis import engine  # noqa: E402
from analysis import qualification  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = ROOT / ".runtime" / "media-cache"
MEDIA = ROOT / "fixtures" / "raw" / "media" / "2026-11-21"
API_DIR = ROOT / "fixtures" / "raw" / "discovery" / "youtube-api-2026-11-21"
QV1_REPLAY = ROOT / "fixtures" / "raw" / "discovery" / "2026-11-21.json"
VARIANTS = ("rules_1_2", "qual_d")


def load_json(path):
    with (gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")) as f:
        return json.load(f)


def api_flags():
    """hasPaidProductPlacement z surowych odpowiedzi videos.list (dla filmów spoza replay)."""
    flags = {}
    for path in sorted(glob.glob(str(API_DIR / "*videos*.json*"))):
        for item in load_json(path).get("items", []):
            value = (item.get("paidProductPlacementDetails") or {}).get("hasPaidProductPlacement")
            if value is not None:
                flags.setdefault(item["id"], (value, Path(path).name))
    return flags


def media_capture(vid, replay, flags, full=True):
    meta = load_json(CACHE / vid / "meta.json")
    base = dict(replay.get(f"youtube:{vid}") or {})
    cap = {**base, "id": f"youtube:{vid}", "module": "M1", "platform": "youtube",
           "url": f"https://www.youtube.com/watch?v={vid}", "title": base.get("title") or meta.get("title"),
           "description": meta.get("description") or base.get("description") or ""}
    youtube = dict(base.get("youtube") or {"videoId": vid})
    if youtube.get("paidPromotionFlag") is None and vid in flags:
        youtube["paidPromotionFlag"] = flags[vid][0]
    youtube.setdefault("paidPromotionFlag", None)
    cap["youtube"] = youtube
    if not full:
        for key in ("segments", "mediaCoverage", "frames", "mediaVersion"):
            cap.pop(key, None)
        return cap
    video = load_json(MEDIA / f"{vid}.json")
    transcript = load_json(CACHE / vid / "transcript.json")
    cap.update(observedAt=cap.get("observedAt") or video.get("observedAt"),
               segments=[{k: s[k] for k in ("start", "end", "text", "method", "windowId") if k in s}
                         for s in transcript["segments"]],
               mediaCoverage=video["mediaCoverage"], frames=video.get("frames") or [],
               mediaVersion=transcript.get("captionsSha256"))
    return cap


def predict(capture, variant):
    finding = engine.analyze(capture, semantic=None, variant=variant)
    view = finding["variants"][variant]
    score = (view.get("reviewScore") or {}).get("value")
    if variant == "rules_1_2" and score is None:
        score = finding.get("score")
    decision = finding.get("reviewDecision") or {}
    quote = None
    for item in finding.get("evidence") or []:
        if isinstance(item, dict) and item.get("role") in ("premise", "relation", "primary") and item.get("text"):
            quote = item["text"][:200]
            break
    row = {"materialId": capture["id"], "score": score, "route": view.get("route"), "gated": view.get("gated"),
           "rulesScore": finding.get("score"), "transcriptPhase": (engine.transcript_phase(capture) or {}).get("state"),
           "speechBasis": decision.get("speechBasis") if variant == "qual_d" else None,
           "adRelationship": (finding.get("adRelationship") or {}).get("status"),
           "reason": (view.get("reason") if variant == "rules_1_2" else decision.get("reason")),
           "evidenceQuote": quote}
    return row


def run_record(variant, state, started, finished, commit):
    return {"type": "run", "variant": variant, "coverageState": state,
            "rulesVersion": engine.RULESET if variant == "rules_1_2" else qualification.RULES_VERSION,
            "codeCommit": commit,
            "modelId": None, "provider": None, "weightsDigest": None, "quantization": None,
            "parameters": {"semantic": "None (E5 nie uruchomiony)", "asr": "nie (Vosk pominięty; auto-napisy YouTube z cache)",
                           "defaultThreshold": engine.DEFAULT_THRESHOLD},
            "promptMethod": None, "startedAt": started, "finishedAt": finished, "durationSeconds": None,
            "tokens": None, "cost": {"amount": 0, "currency": "PLN", "source": "brak zewnętrznych wywołań"},
            "environment": {"host": platform.node() and "devbox", "system": platform.system(), "arch": platform.machine(),
                            "python": platform.python_version(),
                            "path": "analysis.engine.analyze(capture, semantic=None, variant=...) na wejściach z uruchom_warianty.py; bez sieci"}}


def main():
    labels = [json.loads(l) for l in (HERE / "etykiety-agentow.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    replay = {c["id"]: c for c in load_json(API_DIR / "replay.json.gz")["captures"]}
    qv1 = {c["id"]: c for c in load_json(QV1_REPLAY)["captures"]}
    flags = api_flags()
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "analysis", "collectors", "api"],
                               capture_output=True, text=True).stdout.strip()
        commit += (" + niezacommitowane zmiany: " + dirty.replace("\n", "; ")[:300]) if dirty else " (analysis/, collectors/, api/ bez zmian względem HEAD)"
    except OSError:
        commit = "nieznany"
    inputs = {"pelne": {}, "opis": {}}
    for row in labels:
        mid = row["materialId"]
        if row.get("sourceSet") == "media-2026-11-21":
            vid = mid.split(":", 1)[1]
            inputs["pelne"][mid] = media_capture(vid, replay, flags, True)
            inputs["opis"][mid] = media_capture(vid, replay, flags, False)
        else:
            cap = dict(qv1[mid])
            cap.setdefault("module", "M1")
            inputs["pelne"][mid] = inputs["opis"][mid] = cap
    summary = {}
    for state, caps in inputs.items():
        for variant in VARIANTS:
            started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            t0 = time.monotonic()
            rows = [predict(caps[r["materialId"]], variant) for r in labels]
            finished = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            record = run_record(variant, state, started, finished, commit)
            record["durationSeconds"] = round(time.monotonic() - t0, 3)
            out = HERE / f"predykcje-{variant}-{state}.jsonl"
            with out.open("w", encoding="utf-8") as f:
                for item in [record, *rows]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            summary[f"{variant}/{state}"] = {r["materialId"]: (r["route"], r["score"], r["gated"]) for r in rows}
    inputs_digest = {state: {mid: {"description": len(c.get("description") or ""), "segments": len(c.get("segments") or []),
                                   "frames": len(c.get("frames") or []),
                                   "paidPromotionFlag": (c.get("youtube") or {}).get("paidPromotionFlag")}
                             for mid, c in caps.items()} for state, caps in inputs.items()}
    (HERE / "wejscia-podsumowanie.json").write_text(json.dumps(inputs_digest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
