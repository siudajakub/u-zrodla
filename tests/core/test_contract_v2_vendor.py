"""The dated Instagram, Facebook and Ad Library sample of the external service in the scan, the register and the queues
(lane H, 21 XI night). Replay only: no test and no scan calls the service. Temporary state, no network."""
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from analysis import engine
from api import store
from api.jobs import evaluate
from collectors import discovery
from collectors.adapter import PATH_LABEL, merge_source_rows
from v2_helpers import StateCase

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "fixtures/raw/discovery/social-2026-11-21/vendor/replay-vendor.json.gz"


def sample():
    return json.loads(gzip.decompress(SAMPLE.read_bytes()))["captures"]


class Registry(unittest.TestCase):
    def test_adapter_is_replay_only_and_never_reaches_the_service(self):
        adapter = discovery.ADAPTERS["vendor-social-replay"]
        self.assertEqual((adapter.modes, adapter.explicit_only, adapter.own_network), (("replay",), True, False))
        self.assertNotIn("vendor-social-replay", {a.id for a in discovery.active_adapters("live")})
        with patch("collectors.vendor_social.urlopen", side_effect=AssertionError("the service must not be called")):
            result = discovery.discover("replay", (), only=["vendor-social-replay"])
        self.assertEqual(len(result["captures"]), 494)

    def test_source_row_says_which_path_and_how_large(self):
        result = discovery.discover("replay", (), only=["vendor-social-replay", "meta-import-replay"])
        row = next(s for s in result["sources"] if s["id"] == "instagram")
        self.assertEqual(PATH_LABEL["vendor_sample"], "próbka z usługi zewnętrznej")
        self.assertTrue(row["pathsSummary"].startswith("Instagram: próbka z usługi zewnętrznej (350 postów, 21 XI)"), row["pathsSummary"])
        self.assertIn("import ręczny", row["pathsSummary"])
        self.assertEqual(row["bestPath"], "vendor_sample")
        self.assertEqual({p["path"] for p in row["paths"]}, {"vendor_sample", "manual_import"})
        self.assertTrue(all(p["nextStep"] for p in row["paths"]))

    def test_the_same_ad_of_both_samples_is_one_material_with_two_paths(self):
        result = discovery.discover("replay", (), only=["vendor-social-replay", "meta-import-replay"])
        ids = [c["id"] for c in result["captures"]]
        self.assertEqual(len(ids), len(set(ids)))
        both = [c for c in result["captures"] if {"vendor_social", "meta_import"} <= {d.get("adapter") for d in c["discovery"]}
                or len({d.get("method") for d in c["discovery"]}) > 1 and c.get("adId")]
        self.assertGreaterEqual(len(both), 20)
        self.assertTrue(all(len(c["discovery"]) >= 2 for c in both))


class RealRecords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caps = {c["id"]: c for c in sample()}
        cls.found = {}
        for cap in cls.caps.values():
            cap["mode"] = "replay"
            cls.found[cap["id"]] = evaluate(cap)[1]

    def test_five_collaboration_posts_of_kacper_snela_are_in_the_register(self):
        ids = [i for i, c in self.caps.items() if c["creatorId"] == "instagram:kacper.snela" and "[współpraca z XTB]" in c["description"]]
        self.assertEqual(len(ids), 5)
        for i in ids:
            self.assertEqual(self.found[i]["adRegistry"]["state"], "included", i)
            self.assertEqual(self.found[i]["adRegistry"]["disclosureKind"], "explicit_ad")

    def test_twelve_posts_with_the_platform_flag_are_in_the_register(self):
        ids = [i for i, c in self.caps.items() if c.get("isPaidPartnership") is True and c["module"] == "M1"]
        self.assertEqual(len(ids), 12)
        for i in ids:
            f = self.found[i]
            self.assertEqual((f["adRegistry"]["state"], f["adRegistry"]["disclosureKind"], f["reviewDecision"]["route"]),
                             ("included", "platform_flag", "no_signal"), i)
            self.assertIn("Instagram oznacza post jako płatne partnerstwo", f["adRelationship"]["disclosure"]["text"])
            self.assertNotIn("YouTube", json.dumps(f["adRelationship"]) + json.dumps(f["evidence"]))

    def test_saxo_ads_with_a_warning_in_the_text_and_no_flag_are_not_referred(self):
        ids = [i for i, c in self.caps.items() if c.get("adId") and "saxo" in c["author"].lower()]
        self.assertTrue(ids)
        for i in ids:
            f = self.found[i]
            self.assertNotEqual(f["reviewSuggestion"]["state"], "review", i)
            self.assertEqual(f["coverage"]["scope"], "ad_text")
            self.assertIn("tylko tekst reklamy", f["coverage"]["label"])

    def test_a_caption_only_post_is_never_referred_without_the_strong_case(self):
        refers = [i for i, f in self.found.items() if f["module"] == "M1" and f["reviewDecision"]["route"] == "refer"]
        self.assertEqual(refers, [])


class CaptionGate(unittest.TestCase):
    BASE = next(c for c in sample() if c["id"] == "instagram:Df7QRf4jI99")

    def post(self, text, flag):
        cap = dict(self.BASE, description=text, title=text[:40], isPaidPartnership=flag)
        cap["disclosure"] = {"platformFlag": flag, "labelled": False, "textMarkers": [], "coauthors": []}
        return engine.analyze(cap)

    def test_tracking_link_and_a_false_flag_stay_a_refer_with_the_scope_said(self):
        f = self.post("Otwórz konto w XTB przez ten link: https://www.xtb.com/pl?utm_source=ig&ref=abc123 i odbierz bonus.", False)
        d = f["reviewDecision"]
        self.assertEqual((d["route"], d["captionBasis"]), ("refer", "caption_only_strong"))
        self.assertIn("Zbadano tylko podpis posta", d["reasons"][-1])
        self.assertIn("flagę płatnego partnerstwa: nie", d["reasons"][-1])

    def test_without_the_flag_the_route_is_complete_and_names_the_picture(self):
        f = self.post("Otwórz konto w XTB przez ten link: https://www.xtb.com/pl?utm_source=ig&ref=abc123 i odbierz bonus.", None)
        d = f["reviewDecision"]
        self.assertEqual((d["route"], d["completeReason"], d["gatedFrom"], d["queueEligible"]), ("complete", "visual_unexamined", "refer", False))
        self.assertIn("obraz i wideo posta", d["missing"])
        self.assertIn("sprawdź materiał wideo lub grafikę", d["reason"])

    def test_a_creator_code_with_a_false_flag_is_strong_too(self):
        self.assertEqual(self.post("Kod rabatowy KACPER10 w XTB, otwórz konto.", False)["reviewDecision"]["route"], "refer")

    def test_a_true_flag_discloses_even_a_strong_relation(self):
        f = self.post("Otwórz konto w XTB przez ten link: https://www.xtb.com/pl?utm_source=ig&ref=abc123", True)
        self.assertNotEqual(f["reviewDecision"]["route"], "refer")
        self.assertEqual(f["adRegistry"]["state"], "included")


class Scan(StateCase):
    BASELINE = None  # the product default variant

    def test_the_sample_enters_the_queues_by_platform(self):
        from api import jobs
        with patch("analysis.semantic.suggest", return_value={"status": "unavailable"}), \
                patch("collectors.m2_market.market_captures", return_value=([], [], [])):
            scan, _ = store.create_scan("replay", "vendor-1", {"adapters": ["vendor-social-replay"]})
            jobs.process.call_local(scan["id"])
        with store.connection() as db:
            cases, _ = store.all_cases(db, 2, full=False)
        mine = [c for c in cases if c["platform"] in ("instagram", "facebook")]
        self.assertGreaterEqual(len(mine), 480)
        self.assertEqual(sum(1 for c in mine if "adRegister" in c["queues"] and c["module"] == "M1"), 21)
        self.assertFalse([c for c in mine if "review" in c["queues"]])
        self.assertFalse([c for c in mine if c["needsRecalc"]])
