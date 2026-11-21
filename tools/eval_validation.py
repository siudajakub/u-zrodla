#!/usr/bin/env python3
"""Ewaluacja kolejki InvestWatch według zamrożonego protokołu walidacji.

Wejście (JSONL, jeden obiekt na linię):
  etykiety końcowe: materialId, module (M1|M2|M3), campaignId, label
      (skieruj|rejestr|bez_sygnalu|nieustalone), referenceKind (expert|agent);
      opcjonalnie discoveryChannel, split, stratum, synthetic.
  predykcje: materialId, score (liczba albo null), opcjonalnie state
      ("insufficient" oznacza wstrzymanie wniosku) albo decision
      (refer|no_refer|withheld, decyzja wariantu niezależna od progu) albo route
      (trasa kwalifikacji M1: tylko refer przechodzi do progu score; complete
      i insufficient to wstrzymanie, no_signal i uncertain to brak skierowania).
      Opcjonalny pierwszy rekord {"type": "run", ...} opisuje przebieg
      (model, dostawca, digest wag, kwantyzacja, parametry, wersja promptu,
      czas, tokeny, koszt, środowisko). Predykcja z polem etykiety jest błędem.
  oceny surowe (opcjonalne, do zgodności): materialId, raterId, label.

Pozytyw = etykieta "skieruj". Negatywy = "rejestr" i "bez_sygnalu".
"nieustalone" nie wchodzi do macierzy i jest raportowane osobno.
Wstrzymana lub brakująca predykcja liczy się jako brak skierowania.
Wynik reguł to punkty siły sygnału, nie prawdopodobieństwo.

Protokół: fixtures/validation/PROTOKOL.md. Tylko biblioteka standardowa.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ("skieruj", "rejestr", "bez_sygnalu", "nieustalone")
NEGATIVE = {"rejestr", "bez_sygnalu"}
MODULES = ("M1", "M2", "M3")
REFERENCE_KINDS = ("expert", "agent")
NO_BASIS = "brak podstaw do obliczenia"
Z95 = 1.959963984540054
GATE_PRECISION = 0.90
GATE_MIN_CAMPAIGNS = 20


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{number}: niepoprawny JSON ({error.msg})") from None
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: oczekiwano obiektu JSON")
        row["_line"] = number
        rows.append(row)
    return rows


def validate_labels(rows, source="etykiety"):
    seen = set()
    for row in rows:
        where = f"{source}:{row.get('_line', '?')}"
        for field in ("materialId", "module", "campaignId", "label", "referenceKind"):
            if not row.get(field):
                raise ValueError(f"{where}: brak pola {field}")
        if row["label"] not in LABELS:
            raise ValueError(f"{where}: nieznana etykieta {row['label']!r}")
        if row["module"] not in MODULES:
            raise ValueError(f"{where}: nieznany moduł {row['module']!r}")
        if row["referenceKind"] not in REFERENCE_KINDS:
            raise ValueError(f"{where}: referenceKind musi być expert albo agent")
        if row["materialId"] in seen:
            raise ValueError(f"{where}: zduplikowany materialId {row['materialId']!r}")
        seen.add(row["materialId"])
    return rows


RUN_FIELDS = ("variant", "rulesVersion", "codeCommit", "modelId", "provider", "weightsDigest",
              "quantization", "parameters", "promptMethod", "startedAt", "finishedAt",
              "durationSeconds", "tokens", "cost", "environment")
FORBIDDEN_IN_PREDICTIONS = {"label", "referenceKind", "raterId", "final"}
DECISIONS = {"refer", "no_refer", "withheld"}
# Trasa kwalifikacji M1 (analysis.engine): refer przechodzi do progu; complete (np. bramka mowy)
# i insufficient są wstrzymaniem; no_signal i uncertain to brak skierowania bez wstrzymania.
ROUTES = {"refer", "complete", "insufficient", "no_signal", "uncertain"}
WITHHELD_ROUTES = {"complete", "insufficient"}


def split_run(rows, source="predykcje"):
    """Oddziela rekord metadanych przebiegu (type=run) od predykcji."""
    runs = [r for r in rows if r.get("type") == "run"]
    if len(runs) > 1:
        raise ValueError(f"{source}: więcej niż jeden rekord type=run")
    run = {k: v for k, v in (runs[0] if runs else {}).items() if k not in ("type", "_line")}
    missing = [f for f in RUN_FIELDS if f not in run]
    return run, missing, [r for r in rows if r.get("type") != "run"]


def index_predictions(rows, source="predykcje"):
    result = {}
    for row in rows:
        where = f"{source}:{row.get('_line', '?')}"
        leaked = FORBIDDEN_IN_PREDICTIONS & set(row)
        if leaked:
            raise ValueError(f"{where}: predykcja zawiera pola etykiety {sorted(leaked)}; "
                             "ocena modelu nie może zastąpić etykiety")
        if "decision" in row and row["decision"] not in DECISIONS:
            raise ValueError(f"{where}: decision musi być refer, no_refer albo withheld")
        if "route" in row and row["route"] not in ROUTES:
            raise ValueError(f"{where}: route musi być jedną z {sorted(ROUTES)}")
        key = row.get("materialId")
        if not key:
            raise ValueError(f"{where}: brak pola materialId")
        if key in result:
            raise ValueError(f"{where}: zduplikowana predykcja {key!r}")
        score = row.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))
                                  or math.isnan(score)):
            raise ValueError(f"{where}: score musi być liczbą albo null")
        result[key] = row
    return result


def wilson(successes, total, z=Z95):
    """95% przedział Wilsona; None przy pustym mianowniku."""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def ratio(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else NO_BASIS


def decide(prediction, threshold):
    """Zwraca (skierowane, wstrzymane)."""
    if prediction is None:
        return False, True
    if "decision" in prediction:  # decyzja wariantu bez progu (np. reguły + model)
        return prediction["decision"] == "refer", prediction["decision"] == "withheld"
    if "route" in prediction and prediction["route"] != "refer":  # trasa kwalifikacji przed progiem
        return False, prediction["route"] in WITHHELD_ROUTES
    if prediction.get("state") == "insufficient" or prediction.get("score") is None:
        return False, True
    return prediction["score"] >= threshold, False


def evaluate_group(labels, predictions, threshold):
    counts = Counter()
    withheld = missing = undetermined = registry_negatives = registry_in_queue = 0
    referred_campaigns, tp_campaigns = set(), set()
    campaign_truth, campaign_pred = defaultdict(bool), defaultdict(bool)
    errors = []
    for row in labels:
        if row["label"] == "nieustalone":
            undetermined += 1
            continue
        prediction = predictions.get(row["materialId"])
        if prediction is None:
            missing += 1
        referred, abstained = decide(prediction, threshold)
        withheld += abstained
        positive = row["label"] == "skieruj"
        outcome = ("tp" if positive else "fp") if referred else ("fn" if positive else "tn")
        counts[outcome] += 1
        campaign = row["campaignId"]
        campaign_truth[campaign] |= positive
        campaign_pred[campaign] |= referred
        if referred:
            referred_campaigns.add(campaign)
            if positive:
                tp_campaigns.add(campaign)
        if row["label"] == "rejestr":
            registry_negatives += 1
            registry_in_queue += referred
        if outcome in ("fp", "fn"):
            errors.append({"materialId": row["materialId"], "outcome": outcome,
                           "label": row["label"], "campaignId": campaign,
                           "withheld": abstained})
    tp, fp, tn, fn = (counts[k] for k in ("tp", "fp", "tn", "fn"))
    evaluated = tp + fp + tn + fn
    campaign_counts = Counter()
    for campaign, truth in campaign_truth.items():
        pred = campaign_pred[campaign]
        campaign_counts[("tp" if truth else "fp") if pred else ("fn" if truth else "tn")] += 1
    return {
        "threshold": threshold, "labels": len(labels), "undetermined": undetermined,
        "evaluated": evaluated, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": ratio(tp, tp + fp), "precisionCI95": wilson(tp, tp + fp) or NO_BASIS,
        "recall": ratio(tp, tp + fn), "recallCI95": wilson(tp, tp + fn) or NO_BASIS,
        "withheld": withheld, "withheldRate": ratio(withheld, evaluated),
        "missingPredictions": missing, "cost": 2 * fn + fp,
        "referredCampaigns": len(referred_campaigns), "truePositiveCampaigns": len(tp_campaigns),
        "independentCampaigns": len(campaign_truth),
        "campaignLevel": {k: campaign_counts[k] for k in ("tp", "fp", "tn", "fn")},
        "registryNegatives": registry_negatives, "registryInQueue": registry_in_queue,
        "errors": sorted(errors, key=lambda e: (e["outcome"], e["materialId"])),
    }


def weighted_estimate(labels, predictions, threshold, populations):
    """Estymacja przy realnej częstości: waga warstwy = N_populacji / n_ocenionych."""
    by_stratum = defaultdict(list)
    for row in labels:
        if row["label"] != "nieustalone":
            by_stratum[row.get("stratum", "")].append(row)
    missing = sorted(set(by_stratum) - set(populations))
    if missing:
        return {"status": NO_BASIS, "reason": f"brak liczebności populacji dla warstw: {missing}"}
    totals = Counter()
    for stratum, rows in by_stratum.items():
        weight = populations[stratum] / len(rows)
        for row in rows:
            referred, _ = decide(predictions.get(row["materialId"]), threshold)
            positive = row["label"] == "skieruj"
            totals[("tp" if positive else "fp") if referred else ("fn" if positive else "tn")] += weight
    tp, fp, tn, fn = (totals[k] for k in ("tp", "fp", "tn", "fn"))
    whole = tp + fp + tn + fn
    return {"status": "estymacja ważona, bez przedziału",
            "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "prevalence": ratio(tp + fn, whole),
            "weighted": {k: round(v, 2) for k, v in (("tp", tp), ("fp", fp), ("tn", tn), ("fn", fn))}}


def gate(result, reference_kind, split):
    if reference_kind != "expert":
        return {"status": "nie dotyczy: oceny agentów nie są wzorcem eksperckim"}
    if split != "test":
        return {"status": "nie dotyczy: bramkę ocenia się wyłącznie na zamkniętym teście"}
    if result["referredCampaigns"] < GATE_MIN_CAMPAIGNS:
        return {"status": "brak podstaw do oceny",
                "reason": f"{result['referredCampaigns']} skierowań z różnych kampanii, wymagane ≥{GATE_MIN_CAMPAIGNS}"}
    precision = result["precision"]
    passed = isinstance(precision, float) and precision >= GATE_PRECISION
    return {"status": "zaliczona" if passed else "niezaliczona", "precision": precision,
            "precisionCI95": result["precisionCI95"], "referredCampaigns": result["referredCampaigns"]}


def agreement(ratings):
    """Zgodność dwóch oceniających: odsetek zgodnych i kappa Cohena."""
    by_material = defaultdict(dict)
    for row in ratings:
        by_material[row["materialId"]][row["raterId"]] = row["label"]
    pairs = [tuple(v.values())[:2] for v in by_material.values() if len(v) >= 2]
    if not pairs:
        return {"pairs": 0, "observed": NO_BASIS, "kappa": NO_BASIS}
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(first[k] * second[k] for k in set(first) | set(second)) / (n * n)
    kappa = NO_BASIS if expected == 1 else round((observed - expected) / (1 - expected), 4)
    return {"pairs": n, "observed": round(observed, 4), "kappa": kappa,
            "disagreements": sorted(m for m, v in by_material.items()
                                    if len(v) >= 2 and len(set(tuple(v.values())[:2])) > 1)}


def compare_predictions(labels, first, second, thresholds):
    """Rozbieżności dwóch przebiegów na tych samych etykietach (np. kwantyzacja, środowisko)."""
    def view(prediction, threshold):
        referred, withheld = decide(prediction, threshold)
        if prediction is None:
            return {"present": False, "referred": False, "withheld": True}
        return {"present": True, "score": prediction.get("score"), "decision": prediction.get("decision"),
                "state": prediction.get("state"), "referred": referred, "withheld": withheld}

    result = {}
    for threshold in thresholds:
        rows = []
        for row in labels:
            a = view(first.get(row["materialId"]), threshold)
            b = view(second.get(row["materialId"]), threshold)
            if (a["referred"], a["withheld"]) != (b["referred"], b["withheld"]):
                rows.append({"materialId": row["materialId"], "module": row["module"],
                             "campaignId": row["campaignId"], "label": row["label"], "a": a, "b": b})
        result[str(threshold)] = {"disagreements": len(rows), "materials": rows}
    scores = [(r["materialId"], first[r["materialId"]].get("score"), second[r["materialId"]].get("score"))
              for r in labels if r["materialId"] in first and r["materialId"] in second]
    diffs = [abs(a - b) for _, a, b in scores if isinstance(a, (int, float)) and isinstance(b, (int, float))]
    return {"byThreshold": result, "pairedMaterials": len(scores),
            "maxScoreDifference": max(diffs) if diffs else NO_BASIS,
            "onlyInA": sorted({r["materialId"] for r in labels} & set(first) - set(second)),
            "onlyInB": sorted({r["materialId"] for r in labels} & set(second) - set(first))}


def run(labels, predictions, thresholds, gate_threshold=None, split=None, reference=None,
        populations=None, ratings=None, compare=None):
    labels = validate_labels(labels)
    run_meta, run_missing, predictions = split_run(predictions)
    predictions = index_predictions(predictions)
    synthetic = [r for r in labels if r.get("synthetic")]
    labels = [r for r in labels if not r.get("synthetic")]
    if split:
        labels = [r for r in labels if r.get("split") == split]
    kinds = sorted({r["referenceKind"] for r in labels})
    if reference:
        excluded = sum(r["referenceKind"] != reference for r in labels)
        labels = [r for r in labels if r["referenceKind"] == reference]
        kind = reference
    else:
        if len(kinds) > 1:
            raise ValueError("Etykiety mieszają oceny agentów i wzorzec ekspercki; podaj --reference")
        excluded, kind = 0, (kinds[0] if kinds else None)
    thresholds = sorted(set(thresholds))
    if len(thresholds) < 2:
        raise ValueError("Protokół wymaga co najmniej dwóch progów")
    gate_threshold = thresholds[0] if gate_threshold is None else gate_threshold
    if gate_threshold not in thresholds:
        thresholds = sorted(set(thresholds) | {gate_threshold})

    def grouped(field):
        groups = defaultdict(list)
        for row in labels:
            groups[row.get(field) or "(brak)"].append(row)
        return {name: [evaluate_group(rows, predictions, t) for t in thresholds]
                for name, rows in sorted(groups.items())}

    overall = [evaluate_group(labels, predictions, t) for t in thresholds]
    gated = next(r for r in overall if r["threshold"] == gate_threshold)
    report = {
        "protocol": "fixtures/validation/PROTOKOL.md",
        "referenceKind": kind or NO_BASIS,
        "referenceNote": ("wzorzec ekspercki" if kind == "expert" else
                          "oceny agentów — nie są niezależnym wzorcem eksperckim" if kind == "agent"
                          else NO_BASIS),
        "split": split or "(wszystkie)", "thresholds": thresholds,
        "run": run_meta, "runMetadataMissing": run_missing,
        "excludedSynthetic": len(synthetic), "excludedOtherReference": excluded,
        "unmatchedPredictions": len(set(predictions) - {r["materialId"] for r in labels}),
        "overall": overall, "byModule": grouped("module"),
        "byDiscoveryChannel": grouped("discoveryChannel"), "byStratum": grouped("stratum"),
        "gate": {"threshold": gate_threshold, **gate(gated, kind, split)},
    }
    if populations:
        report["realPrevalenceEstimate"] = {
            str(t): weighted_estimate(labels, predictions, t, populations) for t in thresholds}
    if ratings is not None:
        report["raterAgreement"] = agreement(ratings)
    if compare is not None:
        other_meta, other_missing, other = split_run(compare, "predykcje B")
        other = index_predictions(other, "predykcje B")
        report["comparison"] = {
            "runA": run_meta, "runB": other_meta, "runBMetadataMissing": other_missing,
            "overallB": [evaluate_group(labels, other, t) for t in thresholds],
            **compare_predictions(labels, predictions, other, thresholds)}
    return report


def fmt(value):
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, list):
        return f"[{value[0]:.3f}; {value[1]:.3f}]"
    return str(value)


def render(report):
    out = [f"Wzorzec: {report['referenceNote']} · podział: {report['split']}",
           f"Pominięte syntetyczne: {report['excludedSynthetic']} · inny wzorzec: "
           f"{report['excludedOtherReference']} · predykcje bez etykiety: {report['unmatchedPredictions']}"]
    sections = [("Całość", {"": report["overall"]}), ("Moduł", report["byModule"]),
                ("Kanał odkrycia", report["byDiscoveryChannel"]), ("Warstwa próby", report["byStratum"])]
    for title, groups in sections:
        out.append(f"\n## {title}")
        for name, results in groups.items():
            for r in results:
                label = f"{name} " if name else ""
                out.append(
                    f"{label}próg {r['threshold']}: n={r['evaluated']} (nieustalone {r['undetermined']}) "
                    f"TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']} "
                    f"precyzja={fmt(r['precision'])} {fmt(r['precisionCI95'])} "
                    f"pełność={fmt(r['recall'])} wstrzymane={fmt(r['withheldRate'])} "
                    f"koszt={r['cost']} kampanie skierowane={r['referredCampaigns']} "
                    f"prawidłowe reklamy w kolejce={r['registryInQueue']}/{r['registryNegatives']}")
    g = report["gate"]
    out.append(f"\nBramka (próg {g['threshold']}): {g['status']}" + (f" — {g['reason']}" if g.get("reason") else ""))
    if "raterAgreement" in report:
        a = report["raterAgreement"]
        out.append(f"Zgodność oceniających: pary={a['pairs']} zgodność={fmt(a['observed'])} kappa={fmt(a['kappa'])}")
    if report.get("runMetadataMissing") and report.get("run"):
        out.append(f"Brakujące pola metadanych przebiegu A: {', '.join(report['runMetadataMissing'])}")
    if "comparison" in report:
        c = report["comparison"]
        out.append(f"\n## Porównanie przebiegów A={c['runA'].get('variant', '?')} B={c['runB'].get('variant', '?')}")
        out.append(f"Wspólne materiały: {c['pairedMaterials']} · maks. różnica punktów: {fmt(c['maxScoreDifference'])}")
        for threshold, item in c["byThreshold"].items():
            out.append(f"próg {threshold}: rozbieżne decyzje {item['disagreements']}")
            for row in item["materials"]:
                out.append(f"  {row['materialId']} [{row['label']}] A={row['a']} B={row['b']}")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--thresholds", default="30,60,80", help="co najmniej dwa progi, np. 30,60,80")
    parser.add_argument("--gate-threshold", type=float)
    parser.add_argument("--split", choices=("tuning", "test"))
    parser.add_argument("--reference", choices=REFERENCE_KINDS)
    parser.add_argument("--strata", help="JSON {warstwa: liczebność populacji}")
    parser.add_argument("--ratings", help="JSONL ocen surowych do zgodności")
    parser.add_argument("--compare", help="drugi plik predykcji na tych samych etykietach")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        thresholds = [float(t) for t in args.thresholds.split(",") if t.strip()]
        thresholds = [int(t) if t.is_integer() else t for t in thresholds]
        if args.gate_threshold is not None and args.gate_threshold.is_integer():
            args.gate_threshold = int(args.gate_threshold)
        report = run(read_jsonl(args.labels), read_jsonl(args.predictions), thresholds,
                     args.gate_threshold, args.split, args.reference,
                     json.loads(Path(args.strata).read_text(encoding="utf-8")) if args.strata else None,
                     read_jsonl(args.ratings) if args.ratings else None,
                     read_jsonl(args.compare) if args.compare else None)
    except (ValueError, OSError) as error:
        print(f"Błąd: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
