"""Read-only comparison of the active rules (rules_1_2) and the shadow qualification (qual_d) per M1 case.

    python -m api.shadow_report --state <directory with cases.sqlite3> [--json] [--case ID]

Input for the G measurement and for the Fable decision. Opens the database read-only and imports nothing
from the application, so it cannot start a migration or create files.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROUTE_OF_SUGGESTION = {"review": "refer", "uncertain": "complete", "no_signal": "no_signal", "unavailable": "insufficient"}


def rows(state):
    path = Path(state) / "cases.sqlite3"
    if not path.is_file():
        raise SystemExit(f"Brak bazy: {path}")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=1")
    try:
        have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for case in db.execute("SELECT id,body,status FROM cases ORDER BY id"):
            body = json.loads(case["body"])
            if body.get("module", "M1") != "M1":
                continue
            shadow = None
            if "qualification_results" in have:
                found = db.execute("SELECT body FROM qualification_results WHERE case_id=? AND version=?",
                                   (case["id"], body.get("version"))).fetchone()
                shadow = json.loads(found[0]) if found else None
            yield case["id"], case["status"], body, shadow
    finally:
        db.close()


def report(state, only=None):
    out = []
    for key, status, body, shadow in rows(state):
        if only and key != only:
            continue
        suggestion = (body.get("reviewSuggestion") or {}).get("state")
        old = ((shadow or {}).get("variants") or {}).get("rules_1_2", {}).get("route") or ROUTE_OF_SUGGESTION.get(suggestion)
        item = {"id": key, "title": body.get("title"), "origin": body.get("origin") or body.get("mode"), "status": status,
                "version": body.get("version"), "rules_1_2": {"route": old, "score": body.get("score"),
                                                             "reviewSuggestion": suggestion}}
        if shadow is None:
            item["qual_d"] = None
        else:
            decision, score = shadow.get("reviewDecision") or {}, shadow.get("reviewScore") or {}
            item["qual_d"] = {"route": decision.get("route"), "completeReason": decision.get("completeReason"),
                              "reviewScore": score.get("value"), "queueEligible": decision.get("queueEligible"),
                              "reason": decision.get("reason"), "reasons": decision.get("reasons"),
                              "moments": decision.get("moments"),
                              "registry": (shadow.get("adRegistry") or {}).get("state"),
                              "coverage": ((shadow.get("coverage") or {}).get("label"))}
            item["differs"] = old != decision.get("route")
        out.append(item)
    return out


def text(items):
    lines = []
    for item in items:
        new = item["qual_d"]
        lines.append(f"{item['id']}  [{item['origin']}]  {item['title']}")
        lines.append(f"  stara (rules_1_2): {item['rules_1_2']['route']}  (wynik {item['rules_1_2']['score']})")
        if new is None:
            lines.append("  nowa (qual_d): brak, sprawa sprzed kwalifikacji w cieniu")
            continue
        lines.append(f"  nowa (qual_d): {new['route']}" + (f" / {new['completeReason']}" if new["completeReason"] else "")
                     + f"  (wynik {new['reviewScore']}, rejestr: {new['registry']})" + ("  <- RÓŻNICA" if item["differs"] else ""))
        lines.append(f"  zakres: {new['coverage']}")
        for reason in new["reasons"] or ([new["reason"]] if new["reason"] else []):
            lines.append(f"    - {reason}")
        for moment in new["moments"] or []:
            at = "opis" if moment.get("start") is None else f"{moment['start']} s"
            lines.append(f"    @ {at}: {moment.get('label')} -> {moment.get('deepLink')}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--state", required=True, help="katalog z cases.sqlite3 (tylko do odczytu)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--case")
    args = parser.parse_args(argv)
    items = report(args.state, args.case)
    summary = {"cases": len(items), "differ": sum(bool(i.get("differs")) for i in items),
               "withoutShadow": sum(i["qual_d"] is None for i in items)}
    print(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1) if args.json
          else text(items) + f"\nRazem: {summary['cases']} spraw M1, różnic tras: {summary['differ']}, bez cienia: {summary['withoutShadow']}")


if __name__ == "__main__":
    sys.exit(main())
