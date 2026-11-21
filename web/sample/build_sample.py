#!/usr/bin/env python3
"""Buduje web/sample/export.json: przykładowy stan pulpitu jako eksport prawdziwego API (schemat 2).

Czyta tylko GET z działającego API (domyślnie http://127.0.0.1:18801, baza odtworzonego skanu YouTube i TikTok z 21 XI) i zapisuje:
lekki stan /v1/overview (bez spraw), kolejki ze wszystkimi stronami, pełne karty spraw (wszystkie z kolejek review, demo, M2, M3,
zamknięte oraz pierwsze z rejestru i niepełnych), historie progu i wariantu, kalibrację dla kilku progów oraz miniatury kadrów.
Dev-server (web/dev-server.mjs) i test renderowania serwują dokładnie te kształty, więc pulpit pokazuje to samo co backend.

Uruchomienie z katalogu głównego repozytorium:  python3 web/sample/build_sample.py [--api URL]
"""
import argparse
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # bez Pillow zrzuty zostają w pełnej rozdzielczości
    Image = None

OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:18801")
parser.add_argument("--registry-cards", type=int, default=12)
parser.add_argument("--incomplete-cards", type=int, default=12)
parser.add_argument("--m2-cards", type=int, default=12, help="karty stron M2 z renderu (poza kartami z kolejki review)")
parser.add_argument("--m3-cards", type=int, default=8, help="karty ofert M3 (poza kartami z kolejki review)")
args = parser.parse_args()
API = args.api.rstrip("/")


def get(path, raw=False):
    request = urllib.request.Request(API + path, headers={"X-InvestWatch-Schema": "2"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    return data if raw else json.loads(data)


state = get("/v1/overview")
state.pop("findings", None)
state.pop("calibration", None)
queues = {}
for name in ("review", "adRegister", "offersM2", "offersM3", "incomplete", "closed", "demo"):
    # kolejki z podsumowaniami z nowymi polami (band, firstReason, disclosure, completeReason, transcriptState, adRegistryInfo)
    items, cursor = [], None
    while True:
        page = get(f"/v1/queues/{name}?limit=500" + (f"&cursor={cursor}" if cursor else ""))
        items += page["items"]
        cursor = page.get("nextCursor")
        if not cursor:
            break
    queues[name] = items
    print(name, len(items))

want = []
# M2: strony z renderu (karta rynkowa) mają ciężkie pomiary; reklamy z importu są małe (dla przykładu 10).
m2_pages = [i for i in queues["offersM2"] if i["id"].startswith("web:") or i["id"].startswith("dom-")]
m2_other = [i for i in queues["offersM2"] if i not in m2_pages]
queues["_m2cards"] = m2_pages[: args.m2_cards] + m2_other[:10]
# M3: obok kart z review także podmiot uprawniony (kontrola ujemna) i po jednym przypadku braku wpisu.
queues["_m3cards"] = queues["offersM3"][: args.m3_cards] + [i for i in queues["offersM3"] if i["route"] == "no_signal"]
for name, limit in (("review", None), ("demo", None), ("_m2cards", None), ("_m3cards", None), ("closed", None),
                    ("adRegister", args.registry_cards), ("incomplete", args.incomplete_cards)):
    for item in queues[name][:limit]:
        if item["id"] not in want:
            want.append(item["id"])
for item in [i for i in queues["adRegister"] if i["platform"] == "tiktok"][:2]:  # karta TikToka z rejestru
    if item["id"] not in want:
        want.append(item["id"])
queues.pop("_m2cards")
queues.pop("_m3cards")
cases = {i: get(f"/v1/cases/{urllib.parse.quote(i, safe=':')}") for i in want}

# Kopie robocze: pomiary bloków DOM (setki pozycji na widok) zastępuje ich liczba; pulpit czyta tylko liczbę.
for case in cases.values():
    for view in ((case.get("m2Market") or {}).get("views") or {}).values():
        if isinstance(view.get("blocks"), list):
            view["blocks"] = len(view["blocks"])
    case.pop("fullText", None)

frames = OUT / "frames"
frames.mkdir(exist_ok=True)
for case in cases.values():
    for evidence in case.get("evidence", []):
        url = evidence.get("thumbnailUrl")
        if url:
            target = frames / url.removeprefix("/v1/frames/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(get(url, raw=True))

# Zrzuty dowodów M2 (/evidence/m2/market/<sha>.jpg) w małej rozdzielczości: komputer 720 px, telefon 260 px szerokości.
evidence = OUT / "evidence"
shots = {m["screenshot"] for case in cases.values() for check in case.get("checks", []) for m in check.get("measurements", []) if m.get("screenshot")}
shots |= {v["screenshotUrl"] for case in cases.values() for v in ((case.get("m2Market") or {}).get("views") or {}).values() if v.get("screenshotUrl")}
for url in sorted(shots):
    if not re.fullmatch(r"/evidence/m2/market/[0-9a-f]{64}\.jpg", url):
        continue
    target = evidence / url.removeprefix("/evidence/")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = get(url, raw=True)
    if Image is not None:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        width = 720 if image.width > 800 else 260
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=62, optimize=True)
        data = buffer.getvalue()
    target.write_bytes(data)
print("zrzuty dowodów:", len(shots))

# twórcy: tylko ci, którzy występują w eksportowanych kolejkach, oraz monitorowani
used = {i.get("creatorId") for items in queues.values() for i in items}
state["creators"] = [c for c in state["creators"] if c["id"] in used or c.get("isSeed")]
variant = state["qualification"]["variant"]
export = {
    "state": state,
    "queues": queues,
    "cases": cases,
    "thresholdHistory": get("/v1/threshold/history"),
    "qualificationHistory": get("/v1/qualification/history"),
    "trend": get("/v1/trend?days=30"),
    "scans": {s["id"]: get(f"/v1/scans/{s['id']}") for s in state["scans"][:5]},
    "calibration": {str(t): get(f"/v1/calibration?threshold={t}&variant={variant}") for t in range(0, 105, 5)},
    "platformTotals": {p: get(f"/v1/queues/all?platform={p}&limit=1")["total"] for p in ("youtube", "tiktok", "instagram", "facebook", "web")},
}
(OUT / "export.json").write_text(json.dumps(export, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("zapisano export.json:", (OUT / "export.json").stat().st_size // 1024, "kB; kart:", len(cases))
