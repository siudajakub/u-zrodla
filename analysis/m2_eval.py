"""Small evaluation of the M2 rules against the agent's blind labels (not an expert validation).

Usage: python3 -m analysis.m2_eval [--write]

Labels in fixtures/labeled/m2-agent-labels.jsonl were written by the agent from the captured
pages BEFORE the rules were first run on the real material. The rules were developed while the
same pages were visible, so this is a development set, not a held-out test.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from analysis.m2_card import STRICT_THRESHOLD, THRESHOLD, build
from analysis.m2_rules import ORDER, PREMISE, OK, evaluate
from collectors.m2_market import MARKET, market_captures, material

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "fixtures" / "labeled" / "m2-agent-labels.jsonl"
OUTPUT = ROOT / "fixtures" / "labeled" / "m2-agent-eval.json"


def run(root=MARKET):
    labels = {row["id"]: row for row in (json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines() if line.strip())}
    captures, _, sources = market_captures(root)
    pages, per_id = [], {key: Counter() for key in ORDER}
    for cap in captures:
        rows = evaluate(material(cap))
        score, _, _, extra = build(cap, rows)
        pid = cap["m2Market"]["manifest"]
        for row in rows:
            per_id[row["id"]][row["state"]] += 1
        pages.append({"id": pid, "url": cap["url"], "firm": cap["m2Market"]["firm"]["brand"],
                      "entity": cap["m2Market"]["firm"]["entityLabel"], "kind": cap["m2Market"]["kind"], "score": score,
                      "premises": [r["id"] for r in rows if r["state"] == PREMISE], "label": labels.get(pid, {}).get("label"),
                      "reasons": extra["reviewDecision"]["reasons"]})
    result = {"labelsBy": "agent (claude-opus-5-5), blind to rule output, written before the first rule run on real pages",
              "pages": len(pages), "thresholds": {}, "perCriterion": {k: dict(v) for k, v in per_id.items()}, "items": pages,
              "sourceErrors": [s for s in sources if s["status"] != "ok"]}
    for threshold in (THRESHOLD, STRICT_THRESHOLD):
        counts = Counter()
        for page in pages:
            if page["label"] is None:
                continue
            predicted = bool(page["premises"]) and page["score"] >= threshold
            counts[("t" if predicted == page["label"] else "f") + ("p" if predicted else "n")] += 1
        result["thresholds"][str(threshold)] = {**{k: counts[k] for k in ("tp", "fp", "tn", "fn")}, "cost_2FN_plus_FP": 2 * counts["fn"] + counts["fp"]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = run()
    for page in sorted(result["items"], key=lambda p: -p["score"]):
        print(f"{page['score']:>3} {str(page['label']):>5} {page['id'][:58]:58} {','.join(page['premises'])}")
    print(json.dumps(result["thresholds"], ensure_ascii=False))
    if args.write:
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
