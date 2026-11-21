#!/usr/bin/env python3
"""Buduje web/sample/export.json: przykładowy stan pulpitu jako eksport prawdziwego API (schemat 2).

Czyta tylko GET z działającego API (domyślnie http://127.0.0.1:18801, baza odtworzonego skanu YouTube z 21 XI) i zapisuje:
stan skompresowany (bez spraw), kolejki ze wszystkimi stronami, pełne karty spraw (wszystkie z kolejek review, demo, M2, M3,
zamknięte oraz pierwsze z rejestru i niepełnych), historie progu i wariantu, kalibrację dla kilku progów oraz miniatury kadrów.
Dev-server (web/dev-server.mjs) i test renderowania serwują dokładnie te kształty, więc pulpit pokazuje to samo co backend.

Uruchomienie z katalogu głównego repozytorium:  python3 web/sample/build_sample.py [--api URL]
"""
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:18801")
parser.add_argument("--registry-cards", type=int, default=12)
parser.add_argument("--incomplete-cards", type=int, default=12)
args = parser.parse_args()
API = args.api.rstrip("/")


def get(path, raw=False):
    request = urllib.request.Request(API + path, headers={"X-InvestWatch-Schema": "2"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    return data if raw else json.loads(data)


state = get("/v1/state?compact=1")
state.pop("findings", None)
state.pop("calibration", None)
queues = {}
for name in ("review", "adRegister", "offersM2", "offersM3", "incomplete", "closed", "demo"):
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
for name, limit in (("review", None), ("demo", None), ("offersM2", None), ("offersM3", None), ("closed", None),
                    ("adRegister", args.registry_cards), ("incomplete", args.incomplete_cards)):
    for item in queues[name][:limit]:
        if item["id"] not in want:
            want.append(item["id"])
cases = {i: get(f"/v1/cases/{urllib.parse.quote(i, safe=':')}") for i in want}

frames = OUT / "frames"
frames.mkdir(exist_ok=True)
for case in cases.values():
    for evidence in case.get("evidence", []):
        url = evidence.get("thumbnailUrl")
        if url:
            target = frames / url.removeprefix("/v1/frames/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(get(url, raw=True))

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
    "calibration": {str(t): get(f"/v1/calibration?threshold={t}&variant={variant}") for t in range(40, 95, 5)},
}
(OUT / "export.json").write_text(json.dumps(export, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("zapisano export.json:", (OUT / "export.json").stat().st_size // 1024, "kB; kart:", len(cases))
