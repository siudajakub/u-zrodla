"""The second opinion of the dated replay: the RECORDED result of the 21 XI 2026 measurement, attached to a case with its
origin (`runtime: "recorded"`, model, licence, local tag, source file). Nothing is called here: no API, no key, no model.

M1: qwen3.8-27b for the 17 videos of the measurement (gemma-4-31b where qwen's answer was rejected). M3: qwen3.8-27b for the
entities of the measurement. M2: nothing (the measurement showed no value). The field never changes route, score or queues.
"""
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELED = ROOT / "fixtures" / "labeled"
SUMMARY = "fixtures/labeled/ai-second-opinion-summary.json"
PRIMARY = "qwen/qwen3.8-27b"
FALLBACK = {"M1": "google/gemma-4-31b-it"}
POSITIVE = {"M1": "brak_ujawnienia", "M3": "oferta_rekomendacji"}
TASK = {"M1": "m1_disclosure", "M3": "m3_offer"}
REVIEW_LABEL = "rozbieżność — do przeglądu"
CARDS = {"qwen/qwen3.8-27b": ("Qwen3.8 27B", "Apache-2.0", "qwen3.8:27b-q4_K_M", 22),
         "google/gemma-4-31b-it": ("Gemma 4 31B", "Apache-2.0", "gemma4:31b-it-q4_K_M", 24)}


def _file(module, model):
    return LABELED / f"ai-second-opinion-{module.lower()}-{model.split('/')[1]}.json"


@lru_cache(maxsize=8)
def _items(module, model):
    path = _file(module, model)
    if not path.is_file():
        return {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    run = (data.get("runs") or [{}])[-1]
    return {item["id"]: item for item in run.get("items") or []}, {**{k: run.get(k) for k in ("measuredOn", "promptVersion")},
                                                                    "source": f"fixtures/labeled/{path.name}"}


def lookup_id(case_id, module):
    if module == "M3" and case_id.startswith("web:") and case_id.endswith(":m3"):
        return "m3:" + case_id[4:-3]
    return case_id


def recorded(case_id, module, rules_positive):
    """The recorded second opinion of one case, or None (no measurement for it, or module M2)."""
    if module not in POSITIVE:
        return None
    key = lookup_id(case_id, module)
    for model in (PRIMARY, FALLBACK.get(module)):
        if model is None:
            continue
        items, meta = _items(module, model)
        item = items.get(key)
        if item is None or item.get("status") != "ready" or not item.get("verdict"):
            continue
        name, licence, tag, memory = CARDS.get(model, (model, "licencja nieustalona", None, None))
        verdict = item["verdict"]
        agreement = (verdict == POSITIVE[module]) == bool(rules_positive)
        return {"task": TASK[module], "status": "ready", "verdict": verdict, "quote": item.get("quote"), "locator": item.get("locator"),
                "confidence": item.get("confidence"), "explanation": item.get("explanation"),
                "rulesVerdict": POSITIVE[module] if rules_positive else "zgodne_z_regulami",
                "agreement": agreement, "needsReview": not agreement, "reviewLabel": None if agreement else REVIEW_LABEL,
                "modelId": model, "weightsLicense": licence, "localModel": tag, "localMemoryGb": memory,
                "runtime": "recorded", "measuredAt": meta["measuredOn"], "promptVersion": meta["promptVersion"], "source": meta["source"],
                "displayLabel": f"zapisany wynik pomiaru z {meta['measuredOn']} · model {name} · {licence}; lokalnie: ollama pull {tag}",
                "affectsRoute": False}
    return None


def _summary():
    path = ROOT / SUMMARY
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def models_block(semantic, annotate_on=False, local_model=None, use_recorded=False):
    """/v1/overview.models: the E5 classifier and the second opinion, numbers read from the measurement summary."""
    summary = _summary().get("modules") or {}
    measured = {}
    for module, label in (("m1", "M1"), ("m3", "M3")):
        run = ((summary.get(module) or {}).get(PRIMARY) or {}).get("all") or {}
        policy = run.get("policy") or {}
        measured[label] = {"n": run.get("n"), "ready": run.get("ready"), "rejected": run.get("rejected"),
                           "rulesErrors": run.get("rulesErrors"), "fixed": run.get("fixed"), "broken": run.get("broken"),
                           "costRules": (policy.get("rules") or {}).get("cost"), "costVeto": (policy.get("veto") or {}).get("cost"),
                           "costUsd": run.get("costUsd")}
    from analysis.second_opinion import model_card

    if local_model:
        details = model_card(local_model, "local")
        name, licence, tag, memory = local_model, details["weightsLicense"], local_model, details["localMemoryGb"]
        mode, label = "local", "lokalnie (Ollama)"
    elif use_recorded:
        name, licence, tag, memory = CARDS[PRIMARY]
        mode, label = "recorded", "zapisany pomiar z 21 XI 2026"
    else:
        name = licence = tag = memory = None
        mode, label = "disabled", "wyłączony"

    e5 = {"id": "material_type_e5", "name": "multilingual-e5-small (ONNX)", "task": "typ materiału", "status": (semantic or {}).get("status"),
          "affectsDecision": False, "runtime": "local", "annotation": "on" if annotate_on else "off",
          "measured": _e5_measure(), "source": "fixtures/labeled/ai-material-type-result-e5.json"}
    second = {"id": "second_opinion", "name": name, "task": "drugi głos: ujawnienie (M1), oferta rekomendacji (M3)",
              "weightsLicense": licence, "localModel": tag, "localMemoryGb": memory,
              "mode": mode, "modeLabel": label,
              "affectsRoute": False, "measured": measured, "measuredModel": PRIMARY, "labels": _summary().get("labels"),
              "source": SUMMARY}
    return {"materialType": e5, "secondOpinion": second}


def _e5_measure():
    path = LABELED / "ai-material-type-result-e5.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    model = data.get("model") or {}
    keywords = data.get("keywordRules") or {}
    return {"correct": model.get("correct"), "n": model.get("n"), "accuracy": model.get("accuracy"), "split": data.get("split"),
            "keywordRulesAccuracy": keywords.get("accuracy"), "majorityAccuracy": (data.get("majorityClass") or {}).get("accuracy"),
            "version": data.get("version")}
