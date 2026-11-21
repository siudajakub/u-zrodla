"""Calibration of the M1 queue on the q-v2 set: agent labels and the stored predictions of both variants.

Reads fixtures/validation/q-v2 (labels, predictions, result summary) and scores it with tools/eval_validation.py,
so the numbers are the ones of the measurement report for any threshold. Nothing is copied or duplicated.
"""
from functools import lru_cache
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SET = ROOT / "fixtures/validation/q-v2"
LABEL_TARGET = "Materiał zawiera udokumentowaną przesłankę wymagającą kontroli"
DISCLAIMER = ("Oceny agentów na zbiorze strojenia, nie walidacja ekspercka. Zbiór widział autor reguł; "
              "to zbiór, na którym wybrano wariant, nie odłożony test.")
COVERAGE = {"pelne": "pelne", "opis": "opis"}
VARIANTS = ("rules_1_2", "qual_d")
KEEP = ("tp", "fp", "tn", "fn", "evaluated", "cost", "precision", "precisionCI95", "recall", "recallCI95", "withheld",
        "withheldRate", "referredCampaigns", "truePositiveCampaigns", "independentCampaigns", "campaignLevel",
        "registryNegatives", "registryInQueue", "undetermined", "errors")


@lru_cache(maxsize=1)
def _evaluator():
    spec = importlib.util.spec_from_file_location("eval_validation", ROOT / "tools/eval_validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files():
    names = ["etykiety-agentow.jsonl", "wynik-M1-2026-11-21.json"] + [f"predykcje-{v}-{c}.jsonl" for v in VARIANTS for c in COVERAGE]
    return [SET / n for n in names]


def available():
    return all(p.is_file() for p in _files())


def dataset_id():
    digest = sha256()
    for path in _files():
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()[:12]


@lru_cache(maxsize=8)
def _loaded(fingerprint):
    tool = _evaluator()
    labels = tool.read_jsonl(SET / "etykiety-agentow.jsonl")
    predictions = {}
    for variant in VARIANTS:
        for coverage in COVERAGE:
            _, _, rows = tool.split_run(tool.read_jsonl(SET / f"predykcje-{variant}-{coverage}.jsonl"))
            predictions[(variant, coverage)] = tool.index_predictions(rows)
    report = json.loads((SET / "wynik-M1-2026-11-21.json").read_text(encoding="utf-8"))
    return labels, predictions, report


def compare(threshold, coverage="pelne"):
    """Both variants on the q-v2 set at one threshold."""
    if coverage not in COVERAGE:
        raise ValueError("Nieznany zakres pokrycia.")
    labels, predictions, report = _loaded(dataset_id())
    tool = _evaluator()
    variants = {}
    for variant in VARIANTS:
        result = tool.evaluate_group(labels, predictions[(variant, coverage)], threshold)
        by_label = {row["materialId"]: row for row in labels}
        shaped = {k: result[k] for k in KEEP if k in result}
        shaped["errors"] = [{**e, "id": e["materialId"], "title": e["materialId"], "url": by_label[e["materialId"]].get("url"),
                             "score": (predictions[(variant, coverage)].get(e["materialId"]) or {}).get("score"),
                             "text": f"Etykieta agentów: {e['label']}; trasa: "
                                     f"{(predictions[(variant, coverage)].get(e['materialId']) or {}).get('route')}"}
                            for e in result["errors"]]
        variants[variant] = shaped
    freeze = json.loads((SET.parent / "FREEZE.json").read_text(encoding="utf-8")) if (SET.parent / "FREEZE.json").is_file() else {}
    denominators = report.get("denominators") or {}
    return {"dataset": "q-v2", "datasetId": dataset_id(), "module": "M1", "coverage": coverage, "threshold": threshold,
            "n": variants["qual_d"]["evaluated"], "variants": variants,
            "campaigns": {"independent": denominators.get("independentUnits"), "positive": denominators.get("positiveCampaigns"),
                          "mediaVideos": denominators.get("mediaVideos"), "mediaCampaigns": denominators.get("mediaCampaigns")},
            "labelTarget": LABEL_TARGET, "labelers": report.get("raters"), "labelerAgreement": report.get("agreement"),
            "labelSource": report.get("referenceNote"), "referenceKind": report.get("referenceKind"),
            "split": report.get("split"), "frozenAt": freeze.get("frozenAt"), "evaluationStatus": "agent_labels_tuning_set",
            "disclaimer": DISCLAIMER, "gate": report.get("gate"), "report": "fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md"}
