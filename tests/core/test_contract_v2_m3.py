"""M3 offers and M2 market cards in the scan, the queues, the recompute and the report (lane H, 21 XI night).

Real fixtures: the dated M3 run of 21 XI (29 firms, 57 pages) and the M2 market archive. No network, no browser,
every test on a temporary state.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from analysis import engine
from api import store
from collectors import discovery
from collectors.adapter import MemoryRunner
from collectors.m2_market import market_captures
from test_contract_v2_adapters import ScanCase
from v2_helpers import HttpCase

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("naruszeni", "nielegaln")


def texts_of(finding):
    """Wording the product writes itself (not quotes of the pages)."""
    d, s, c = finding["reviewDecision"], finding["reviewScore"], finding.get("coverage") or {}
    return [d["reason"], d.get("wording") or "", s.get("meaning") or "", c.get("label") or "", finding.get("summary") or "",
            (finding.get("identity") or {}).get("label") or "", (finding.get("identity") or {}).get("badge") or "",
            *[m["label"].split(":")[0] for m in d["moments"]], *[r["label"] for r in finding["checks"]]]


class Adapters(unittest.TestCase):
    def test_replay_adapter_is_explicit_and_reads_29_firms_with_57_pages(self):
        adapter = discovery.ADAPTERS["m3-offers-replay"]
        self.assertTrue(adapter.explicit_only)
        self.assertEqual(adapter.modes, ("replay",))
        result = discovery.discover("replay", (), only=["m3-offers-replay"])
        self.assertEqual(len(result["captures"]), 29)
        self.assertEqual(sum(len(c["m3Pages"]) for c in result["captures"]), 57)
        self.assertEqual(result["sources"][0]["pages"], 57)
        self.assertIn("wymaga dostawcy z kluczem", result["sources"][0]["message"])
        self.assertTrue(all(c["discovery"][0]["method"] for c in result["captures"]))

    def test_live_adapter_is_off_by_default_and_says_it_has_no_search(self):
        live = {a.id for a in discovery.active_adapters("live")}
        self.assertNotIn("m3-offers", live)
        with patch.dict("os.environ", {"INVESTWATCH_ADAPTERS": "m3-offers"}):
            self.assertIn("m3-offers", {a.id for a in discovery.active_adapters("live")})
        result = discovery.discover("live", (), only=["m3-offers"])
        self.assertEqual(result["captures"], [])
        self.assertEqual(result["sources"][0]["status"], "empty")
        self.assertIn("wyszukiwanie wymaga dostawcy z kluczem", result["sources"][0]["message"])

    def test_live_adapter_reads_a_seed_list_through_its_own_fetcher_within_the_budget(self):
        page = "<html><head><title>Firma</title></head><body><p>Doradztwo inwestycyjne dla klientów indywidualnych.</p></body></html>".encode()

        class Fetcher:
            budget, interval, used = 3, 3.0, 0

            def allowed(self, url):
                return True

            def get(self, url):
                self.used += 1
                return url, page

        seeds = ROOT / "fixtures" / "raw" / "discovery" / "m3-2026-11-21" / "seeds-test.json"
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seeds.json"
            path.write_text(json.dumps([{"url": "https://firma-a.example/", "label": "A"},
                                        {"url": "https://firma-b.example/", "label": "B"}]), encoding="utf-8")
            result = discovery.discover("live", (), only=["m3-offers"], options={"m3_seeds": str(path), "m3_fetcher": Fetcher()})
        self.assertEqual([c["id"] for c in result["captures"]], ["web:firma-a.example:m3"])
        self.assertEqual(result["sources"][0]["unread"], 1, "the second firm is skipped: no budget left")
        self.assertFalse(seeds.exists())

    def test_a_firm_that_an_older_source_holds_is_not_duplicated(self):
        legacy = {"id": "web:bossa.pl/oferta/doradztwo", "module": "M3", "url": "https://bossa.pl/oferta/doradztwo"}
        entity = {"id": "web:bossa.pl:m3", "module": "M3", "url": "https://bossa.pl/", "m3Entity": "m3:bossa.pl"}
        other = {"id": "web:x.pl:m3", "module": "M3", "url": "https://x.pl/", "m3Entity": "m3:x.pl"}
        kept = discovery.drop_legacy_duplicates([legacy, entity, other])
        self.assertEqual([c["id"] for c in kept], [legacy["id"], other["id"]])


class Analysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = {c["id"]: engine.analyze(c) for c in discovery.discover("replay", (), only=["m3-offers-replay"])["captures"]}

    def test_rdmwm_is_referred_with_quotes_urls_and_no_identity(self):
        f = self.found["web:rdmwm.pl:m3"]
        d = f["reviewDecision"]
        self.assertEqual((d["route"], f["identity"]["state"]), ("refer", "no_identity"))
        self.assertTrue(3 <= len(d["reasons"]) <= 5)
        self.assertTrue(d["moments"])
        for moment in d["moments"]:
            self.assertTrue(moment["quote"] and moment["url"].startswith("https://rdmwm.pl") and moment["locator"]["line"])
        self.assertEqual([r["id"] for r in f["checks"]], ["action", "personalisation", "instrument", "market"])
        self.assertTrue(f["identity"]["reviewedRegisters"] and f["identity"]["checkedAt"])
        self.assertEqual(f["identity"]["knfWarning"]["state"], "none")
        self.assertTrue(f["counterEvidence"])
        self.assertEqual(f["coverage"]["scope"], "public_html_text")
        self.assertTrue(d["queueEligible"])

    def test_licensed_firms_are_no_signal_with_the_licence_label(self):
        for key in ("web:mbank.pl:m3", "web:erste.pl:m3"):
            f = self.found[key]
            self.assertEqual(f["reviewDecision"]["route"], "no_signal", key)
            self.assertEqual((f["identity"]["state"], f["identity"]["badge"]), ("authorized_advice", "podmiot uprawniony"))
        bos = engine.analyze(json.loads((ROOT / "fixtures/validation/bossa-discovery-2026-11-21.json").read_text(encoding="utf-8"))["capture"])
        self.assertEqual(bos["reviewDecision"]["route"], "no_signal")
        self.assertEqual(bos["identity"]["badge"], "podmiot uprawniony")

    def test_financewell_is_a_name_collision(self):
        cap = next(c for c in engine.demo_captures() if c["id"] == "public-financewell-agent")
        f = engine.analyze(cap)
        self.assertEqual(f["identity"]["state"], "name_collision")
        self.assertEqual(f["reviewDecision"]["route"], "no_signal")

    def test_complete_names_the_gap_and_the_wording_is_not_a_verdict(self):
        complete = [f for f in self.found.values() if f["reviewDecision"]["route"] == "complete"]
        self.assertTrue(complete)
        for f in self.found.values():
            for text in texts_of(f):
                self.assertFalse(any(w in text.lower() for w in FORBIDDEN), text)
        for f in complete:
            self.assertTrue(f["reviewDecision"]["missing"] and f["reviewDecision"]["completeReason"])

    def test_the_result_is_stable(self):
        cap = discovery.discover("replay", (), only=["m3-offers-replay"])["captures"][0]
        self.assertEqual(json.dumps(engine.analyze(cap), sort_keys=True), json.dumps(engine.analyze(dict(cap)), sort_keys=True))

    def test_every_analysis_is_stamped_with_the_rules_of_its_module(self):
        for f in self.found.values():
            self.assertEqual((f["analysisVersion"]["rules"], f["analysisVersion"]["schema"]), ("m3-offers-1", 2))
        caps, _, _ = market_captures()
        self.assertEqual(engine.analyze(caps[0])["analysisVersion"]["module"], "M2")


class MarketCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = {c["id"]: engine.analyze(c) for c in market_captures()[0]}

    def test_noble_ike_is_referred_with_a_quote_and_criterion_4(self):
        f = self.found["web:noblesecurities.pl/klient-indywidualny/rachunek-ike"]
        self.assertEqual(f["reviewDecision"]["route"], "refer")
        self.assertTrue(f["reviewDecision"]["moments"])
        self.assertEqual(next(r for r in f["checks"] if r["id"] == "4")["state"], "przesłanka")
        self.assertTrue(any(e["text"] for e in f["evidence"] if e.get("criterionId") == "4"))

    def test_education_and_lynx_cfd_are_not_referred(self):
        for key in ("web:www.xtb.com/pl/edukacja", "web:www.lynxbroker.pl/online-broker/cfd-broker"):
            self.assertEqual(self.found[key]["reviewDecision"]["route"], "no_signal", key)

    def test_the_xtb_pair_both_carry_criterion_3(self):
        for key in ("web:www.xtb.com/pl/akcje", "dom-xtb-etf"):
            self.assertEqual(next(r for r in self.found[key]["checks"] if r["id"] == "3")["state"], "przesłanka", key)

    def test_the_old_counters_still_see_the_premises(self):
        f = self.found["web:www.xtb.com/pl/akcje"]
        self.assertEqual(sum(f["checkCounts"].values()), 19)  # the sum is the 19 criteria; "obserwacja" is its own state (criterion 2)


class Worker(ScanCase):
    """The whole path: replay scan with the M3 adapter and the market archive, queues, recompute, report."""

    def setUp(self):
        super().setUp()
        self.enterContext(patch("analysis.semantic.suggest", return_value={"status": "unavailable"}))
        from analysis import engine as eng
        # the market archive and the M3 fixture are the only inputs; the media pack of this host is not used
        scan, _ = store.create_scan("replay", "m3-1", {"adapters": ["m3-offers-replay"]})
        self.jobs.process.call_local(scan["id"])

    def cases(self):
        with store.connection() as db:
            cases, _ = store.all_cases(db)
        return {c["id"]: c for c in cases}

    def test_queues_of_m3_and_m2(self):
        cases = self.cases()
        rd = cases["web:rdmwm.pl:m3"]
        self.assertEqual(set(rd["queues"]), {"all", "review", "offersM3"})
        self.assertFalse(rd["needsRecalc"])
        complete = [c for c in cases.values() if c.get("module") == "M3" and c["route"] == "complete" and c["id"].endswith(":m3")]
        self.assertTrue(complete)
        for c in complete:
            self.assertTrue({"offersM3", "incomplete"} <= set(c["queues"]), c["id"])
            self.assertNotIn("review", c["queues"])
        licensed = cases["web:mbank.pl:m3"]
        self.assertEqual(set(licensed["queues"]), {"all", "offersM3"})
        plain = cases["web:kursyszkolenia24.pl:m3"]
        self.assertEqual(set(plain["queues"]), {"all"})
        noble = cases["web:noblesecurities.pl/klient-indywidualny/rachunek-ike"]
        self.assertEqual(set(noble["queues"]), {"all", "review", "offersM2"})
        self.assertEqual(set(cases["web:www.xtb.com/pl/edukacja"]["queues"]), {"all", "offersM2"})
        refers = [k for k, c in cases.items() if "review" in c["queues"] and c["module"] in ("M2", "M3")]
        self.assertEqual(len([k for k in refers if k.startswith("web:") and not k.endswith(":m3")]), 8)  # criterion 2 is an observation: a page that only lacked the ad label is no longer a referral

    def test_no_case_waits_for_a_recompute_after_a_scan(self):
        stale = [k for k, c in self.cases().items() if c["module"] in ("M2", "M3") and c["needsRecalc"]]
        self.assertEqual(stale, [])

    def test_recompute_clears_needs_recalc_of_m2_and_m3(self):
        with store.connection(True) as db:
            for row in db.execute("SELECT id,body FROM cases WHERE json_extract(body,'$.module') IN ('M2','M3')").fetchall():
                body = json.loads(row["body"])
                body.pop("analysisVersion", None)
                body["rulesVersion"] = "investwatch-rules-pl-1.2"
                db.execute("UPDATE cases SET body=? WHERE id=?", (json.dumps(body), row["id"]))
            db.execute("DELETE FROM qualification_results WHERE case_id IN (SELECT id FROM cases WHERE json_extract(body,'$.module')='M3')")
        before = self.cases()
        marked = [k for k, c in before.items() if c["module"] in ("M2", "M3") and c["needsRecalc"]]
        self.assertTrue(len(marked) > 30)
        self.assertTrue(all("incomplete" not in before[k]["queues"] for k in marked if before[k]["module"] == "M2"),
                        "a mere wait for the recompute is not a concrete gap")
        scan, _ = store.create_scan("recompute", "rc-1")
        self.jobs.process.call_local(scan["id"])
        after = self.cases()
        self.assertEqual([k for k, c in after.items() if c["module"] in ("M2", "M3") and c["needsRecalc"]], [])
        self.assertIn("review", after["web:rdmwm.pl:m3"]["queues"])
        self.assertEqual(len(after), len(before), "no case is duplicated or lost")

    def test_report_of_m3_has_the_brief_columns(self):
        with store.connection() as db:
            report = store.report_list(db, "M3", queue="offersM3", limit=500)
        self.assertEqual(report["columns"][:5], ["podmiot", "daneRejestrowe", "trescOferty", "url", "stanUprawnien"])
        rows = {r["id"]: r for r in report["items"]}
        row = rows["web:rdmwm.pl:m3"]
        self.assertEqual(row["trasa"], "refer")
        self.assertTrue(row["trescOferty"] and row["url"].startswith("https://rdmwm.pl") and row["przejrzaneWykazy"] and row["dataWykazow"])
        self.assertIn("podmiot uprawniony", rows["web:mbank.pl:m3"]["stanUprawnien"])
        self.assertIsInstance(row["silaSygnalu"], int)
        with store.connection() as db:
            csv_text = store.report_csv(report)
        self.assertTrue(csv_text.startswith("﻿podmiot"))
