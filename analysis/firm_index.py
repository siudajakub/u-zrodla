"""Build the M1 firm alias index from dated KNF register snapshots.

Usage: python -m analysis.firm_index [--check]

The curated part (ALIASES) says which brand words point to which register
rows. Names, categories and file fingerprints are always copied from the
snapshot files, so a stale or missing row is visible instead of invented.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "data" / "probe-snapshots" / "knf"
OUTPUT = Path(__file__).resolve().with_name("firm-index.json")
CHECKED_AT = "2026-11-21"
SOURCES = (
    "knf_domy_maklerskie.json", "knf_banki_maklerskie.json",
    "knf_notyfikacje_zagr_FI.json", "knf_oddzialy_zagr_FI.json",
)
CROSS_BORDER = {"knf_notyfikacje_zagr_FI.json", "knf_oddzialy_zagr_FI.json"}
# What each copied register says about the entity (Temat 1 definitions; the copies do not split foreign credit
# institutions from other foreign investment firms, so no row is typed as one on its name).
REGISTERS = {
    "knf_domy_maklerskie.json": {"name": "domy maklerskie", "entityType": "domestic_investment_firm", "passporting": None},
    "knf_banki_maklerskie.json": {"name": "banki prowadzące działalność maklerską", "entityType": "domestic_bank", "passporting": None},
    "knf_oddzialy_zagr_FI.json": {"name": "oddziały zagranicznych firm inwestycyjnych", "entityType": "foreign_investment_firm",
                                  "passporting": "branch"},
    "knf_notyfikacje_zagr_FI.json": {"name": "notyfikacje zagranicznych firm inwestycyjnych (bez oddziału)",
                                     "entityType": "foreign_investment_firm", "passporting": "cross_border"},
}

# key, brand pattern (case-insensitive unless noted), register ids, firm domains,
# legal-name patterns that select one of several ids.
ALIASES = [
    {"key": "xtb", "label": "XTB", "pattern": r"\bXTB\b|X-Trade Brokers",
     "ids": [6884980, 9439233], "domains": ["xtb.com", "xtb.pl"],
     "legal": {r"\bXTB\s+S\.?\s?A\b": 6884980, r"\bXTB\s+Ltd\b": 9439233}},
    {"key": "mbank", "label": "mBank", "pattern": r"\bmBank\w*|\beMakler\w*", "ids": [7410390],
     "domains": ["mbank.pl"]},
    {"key": "pekao", "label": "Pekao", "pattern": r"\bPekao\b", "ids": [7976968, 6884978],
     "domains": ["pekao.com.pl"], "legal": {r"Biuro Maklerskie Pekao|Bank Pekao": 7976968,
                                             r"Pekao Investment Banking": 6884978}},
    {"key": "bos", "label": "DM BOŚ (bossa)", "pattern": r"\bDM\s+BOŚ\b|\bbossa\b|Dom Maklerski Banku Ochrony Środowiska",
     "ids": [8353437], "domains": ["bossa.pl"]},
    {"key": "pkobp", "label": "PKO BP", "pattern": r"\bPKO\s?BP\b|Biuro Maklerskie PKO", "ids": [7410386],
     "domains": ["pkobp.pl"]},
    {"key": "ing", "label": "ING", "pattern": r"\bING\s+Bank\w*|\bBM\s+ING\b", "ids": [8387348], "domains": ["ing.pl"]},
    {"key": "millennium", "label": "Millennium", "pattern": r"\bBank\w* Millennium\b|Biuro Maklerskie Banku Millennium",
     "ids": [7410389], "domains": ["bankmillennium.pl"]},
    {"key": "alior", "label": "Alior", "pattern": r"\bAlior\b", "ids": [8291662], "domains": ["aliorbank.pl"]},
    {"key": "santander", "label": "Santander", "pattern": r"\bSantander\b", "ids": [8911104], "domains": ["santander.pl"]},
    {"key": "etoro", "label": "eToro", "pattern": r"\beToro\b", "ids": [9651212], "domains": ["etoro.com", "etoro.tw"]},
    {"key": "trading212", "label": "Trading 212", "pattern": r"\bTrading\s?212\b",
     "ids": [9439196, 9439202, 9439209], "domains": ["trading212.com"]},
    {"key": "freedom24", "label": "Freedom24", "pattern": r"\bFreedom\s?24\b|\bFreedom Finance\b|\bPlatformie Freedom\b",
     "ids": [9439434], "domains": ["freedom24.com"]},
    {"key": "ibkr", "label": "Interactive Brokers", "pattern": r"\bInteractive Brokers\b|\bIBKR\b", "ids": [9439550],
     "domains": ["interactivebrokers.com", "ibkr.com"]},
    {"key": "revolut", "label": "Revolut", "pattern": r"\bRevolut\b", "ids": [9439516], "domains": ["revolut.com"]},
    {"key": "lightyear", "label": "Lightyear", "pattern": r"\bLightyear\b", "ids": [9439188], "domains": ["lightyear.com"]},
    # Investment service by its own description; no row in the dated snapshot (checked 2026-11-21).
    {"key": "saxo", "label": "Saxo Bank", "pattern": r"\bSaxo\w*", "ids": [], "domains": ["home.saxo", "saxo.com", "saxobank.com"]},
]
# Advertisers that are not investment firms within M1 (brief §2). They stay out of the ad register.
OUT_OF_SCOPE = [
    {"key": "hipoteka-direct", "label": "Hipoteka Direct", "pattern": r"\bHipoteka[_\s]+Direct\b",
     "reason": "pośrednictwo kredytu hipotecznego, nie firma inwestycyjna"},
    {"key": "3deals", "label": "3deals", "pattern": r"\b3deals\b", "reason": "porównywarka lokat bankowych"},
    {"key": "investingpro", "label": "InvestingPro", "pattern": r"\bInvestingPro\b|investing-referral\.com",
     "reason": "narzędzie analityczne, nie firma inwestycyjna"},
]


def _clean(name):
    name = re.sub(r"<strike>.*?</strike>", " ", name, flags=re.S | re.I)
    name = re.sub(r"<[^>]+>", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _home_country(row, domestic):
    if domestic:
        return "Polska"
    for attribute in row.get("attributes") or []:
        if attribute.get("name") == "Państwo macierzyste" and attribute.get("value"):
            return _clean(attribute["value"])
    return None


def _rows():
    rows, files, counts = {}, {}, {}
    for name in SOURCES:
        path = SNAPSHOTS / name
        data = path.read_bytes()
        files[name] = sha256(data).hexdigest()
        parsed = json.loads(data)
        counts[name] = len(parsed)
        for row in parsed:
            rows.setdefault(row["id"], (name, row))
    return rows, files, counts


def build():
    rows, files, counts = _rows()
    firms, missing = [], []
    for alias in ALIASES:
        candidates = []
        for registry_id in alias["ids"]:
            if registry_id not in rows:
                missing.append(registry_id)
                continue
            source, row = rows[registry_id]
            kind = REGISTERS[source]
            candidates.append({"registryId": registry_id, "name": _clean(row["name"]),
                               "category": row.get("subcategoryName"), "sourceFile": f"data/probe-snapshots/knf/{source}",
                               "checkedAt": CHECKED_AT, "crossBorder": source in CROSS_BORDER,
                               "entityType": kind["entityType"], "homeCountry": _home_country(row, kind["passporting"] is None),
                               "passporting": kind["passporting"]})
        firms.append({**{k: alias[k] for k in ("key", "label", "pattern", "domains")},
                      "legal": alias.get("legal", {}), "candidates": candidates, "inScope": True})
    registers = [{"file": f"data/probe-snapshots/knf/{name}", "name": REGISTERS[name]["name"], "rows": counts[name]}
                 for name in SOURCES]
    return {"generatedBy": "analysis/firm_index.py", "checkedAt": CHECKED_AT, "sourceFiles": files, "registers": registers,
            "firms": firms, "outOfScope": OUT_OF_SCOPE, "missingIds": missing}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the written index differs from a rebuild")
    args = parser.parse_args(argv)
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        print("firm-index.json aktualny" if current == text else "firm-index.json nieaktualny")
        return 0 if current == text else 1
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"Zapisano {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
