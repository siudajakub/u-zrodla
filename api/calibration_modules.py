"""Calibration of the M2 card and of the M3 offers on the agent-labelled sets in fixtures/labeled.

M2: 25 pages of the archived market capture; the labels were written by an agent before the rules ran. Predictions are the
card score computed NOW by the current code on the stored captures (no browser, no network), the threshold is a parameter.
M3: 31 entities (+ controls) of the archived run; predictions are the current rules run on the stored pages and registers.
The numbers are those of the lane records at the stored thresholds (M2 30: TP 9, FP 1, TN 12, FN 3; M3 refer: TP 1, FP 0).
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELED = ROOT / "fixtures" / "labeled"
M3_RAW = ROOT / "fixtures" / "raw" / "discovery" / "m3-2026-11-21"
SERIES = tuple(range(20, 100, 5))
DISCLAIMER = ("Oceny jednego agenta, zapisane przed uruchomieniem reguł. Zbiór widział autor reguł: to zbiór strojenia, "
              "nie odłożony test i nie walidacja ekspercka.")
LABELERS = "1 agent, etykiety przed regułami"
M2_TARGET = "Strona wymaga kontroli: przesłanka z karty M2 (twierdzenie o korzyści bez ostrzeżenia, ostrzeżenie słabo widoczne i inne)"
M3_TARGET = "Oferta wymaga uwagi analityka: czynność doradcza dla klienta w Polsce bez wpisu o doradztwie w wykazie"
VIEWS = ("refer", "refer_or_complete")


def _ratio(a, b):
    return round(a / b, 3) if b else None


def _score(rows, predicted):
    tp = sum(1 for r in rows if predicted(r) and r["label"])
    fp = sum(1 for r in rows if predicted(r) and not r["label"])
    fn = sum(1 for r in rows if not predicted(r) and r["label"])
    tn = len(rows) - tp - fp - fn
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "evaluated": len(rows), "cost": 2 * fn + fp,
            "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn)}


def _file_id(*paths):
    digest = sha256()
    for path in paths:
        digest.update(Path(path).read_bytes() if Path(path).is_file() else b"-")
    return digest.hexdigest()[:12]


@lru_cache(maxsize=2)
def _m2_rows(fingerprint):
    from analysis import m2_eval
    result = m2_eval.run()
    return [{"id": p["id"], "firm": p["firm"], "entity": p["entity"], "url": p["url"], "score": p["score"],
             "premises": p["premises"], "label": p["label"], "route": "refer" if p["premises"] and p["score"] >= 30 else "no_signal"}
            for p in result["items"] if p["label"] is not None]


@lru_cache(maxsize=2)
def _m3_rows(fingerprint):
    from analysis import offers
    labels = {json.loads(l)["entityId"]: json.loads(l)["label"] for l in
              (LABELED / "m3-agent-labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    names = {e["id"]: e for e in json.loads((M3_RAW / "entities.json").read_text(encoding="utf-8"))["entities"]}
    rows = []
    for r in offers.analyze_run(M3_RAW):
        if r["entityId"] in labels and r["pages"]:
            entity = names.get(r["entityId"]) or {}
            rows.append({"id": r["entityId"], "firm": entity.get("name") or r["entityId"], "url": (r["pages"][0] or {}).get("url"),
                         "score": r["signalPoints"], "route": r["route"], "label": labels[r["entityId"]]})
    return rows


def available():
    return all(p.is_file() for p in (LABELED / "m2-agent-labels.jsonl", LABELED / "m3-agent-labels.jsonl", M3_RAW / "entities.json"))


def dataset_id(module):
    if module == "M2":
        from analysis.m2_rules import RULES_VERSION
        return _file_id(LABELED / "m2-agent-labels.jsonl") + "-" + RULES_VERSION[-6:]
    return _file_id(LABELED / "m3-agent-labels.jsonl", M3_RAW / "results.json")


def _positive(r, view="refer"):
    label = r["label"]
    if isinstance(label, bool):
        return label
    return label in (("refer",) if view == "refer" else ("refer", "complete"))


def compare(module, threshold, view="refer"):
    """One module at one threshold. M3 has two views: `refer` and `refer_or_complete`."""
    if module not in ("M2", "M3"):
        raise ValueError("Zbiór z etykietami jest tylko dla M2 i M3.")
    if view not in VIEWS:
        raise ValueError("Nieznany widok. Dostępne: refer, refer_or_complete.")
    if module == "M2":
        rows = _m2_rows(dataset_id("M2"))
        rows = [{**r, "label": bool(r["label"])} for r in rows]
        predicted = lambda r: bool(r["premises"]) and r["score"] >= threshold
        positive = lambda r: r["label"]
        views = None
        independent = len({r["firm"] for r in rows})
    else:
        rows = _m3_rows(dataset_id("M3"))
        views = {}
        for name in VIEWS:
            wanted = {"refer"} if name == "refer" else {"refer", "complete"}
            pred = (lambda w: lambda r: r["route"] in w and r["score"] >= threshold)(wanted)
            pos = (lambda w: lambda r: r["label"] in w)(wanted)
            labelled = [{**r, "label": pos(r)} for r in rows]
            views[name] = {**_score(labelled, pred), "errors": _errors_of(labelled, pred)}
        wanted = {"refer"} if view == "refer" else {"refer", "complete"}
        predicted = lambda r: r["route"] in wanted and r["score"] >= threshold
        rows = [{**r, "label": r["label"] in wanted} for r in rows]
        independent = len(rows)
    out = {"module": module, "dataset": "m2-agent-25" if module == "M2" else "m3-agent-31", "datasetId": dataset_id(module),
           "threshold": threshold, "view": view if module == "M3" else None, "n": len(rows),
           **_score(rows, predicted), "errors": _errors_of(rows, predicted),
           "labelTarget": M2_TARGET if module == "M2" else M3_TARGET, "labelers": LABELERS,
           "evaluationStatus": "agent_labels_tuning_set", "disclaimer": DISCLAIMER,
           "independentUnits": {"firms": independent} if module == "M2" else {"entities": independent},
           "labelSource": "fixtures/labeled/" + ("m2-agent-labels.jsonl" if module == "M2" else "m3-agent-labels.jsonl")}
    if views:
        out["views"] = views
    return out


def _errors_of(rows, predicted):
    return [{"id": r["id"], "title": r["id"], "firm": r["firm"], "url": r["url"], "score": r["score"], "route": r["route"],
             "predicted": bool(predicted(r)), "label": r["label"], "outcome": "fp" if predicted(r) else "fn",
             "text": f"{r['firm']} ({r['url']}): wynik reguł {r['score']}, trasa {r['route']}, "
                     f"{'agent: brak przesłanki' if predicted(r) else 'agent: przesłanka'}"}
            for r in rows if bool(predicted(r)) != bool(r["label"])]


def series(module, view="refer", thresholds=SERIES):
    """The curve in one call: counts and cost per threshold, no error lists."""
    points = []
    for value in thresholds:
        row = compare(module, value, view)
        points.append({k: row[k] for k in ("threshold", "tp", "fp", "tn", "fn", "cost", "precision", "recall")})
    return points
