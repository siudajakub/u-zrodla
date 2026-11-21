"""Contract v2 qualification, queues, thresholds and variants (T13-T15, T20-T26, T28-T33).

T21 is green: it freezes today's queue and high_risk behaviour (golden file captured at 491094d) and must
stay green through the shadow step S5. The rest are expectedFailure skeletons for steps S5-S8.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from analysis.engine import analyze, calibration, demo_captures
from analysis.semantic import review_suggestion
from collectors.discovery import discover
from api import store
from v2_helpers import HttpCase, StateCase, VIDEO, capture, finding

GOLDEN = Path(__file__).with_name("golden_shadow_v1.json")
DECLARATION = "Partnerem odcinka jest XTB."
UNMARKED = "Zacznij z XTB: https://link-pso.xtb.com/pso/abc Kod KANAL przy rejestracji daje kurs."
CLAIM_SEGMENTS = [{"start": 312.4, "end": 316.9, "text": "Na ETF-ach w tej aplikacji zrobicie dwadzieścia procent rocznie",
                   "confidence": .86}]


def evaluate(cap):
    """What jobs.build does when the local model is absent."""
    found = analyze(cap)
    found["semantic"] = {"status": "unavailable"}
    if "reviewSuggestion" not in found:
        found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
    return cap, found


def analyzed(text, **extra):
    return analyze(capture(description=text, **extra))


class ShadowKeepsBehaviour(StateCase):
    def snapshot(self):
        # Showcase fixtures plus the dated real discovery archive (two XTB declarations among them).
        captures = demo_captures() + discover("replay", ())["captures"]
        pairs = [evaluate(cap) for cap in captures]
        self.scan(pairs, mode="replay")
        high_risk = sorted(e["ref"] for e in self.events("high_risk"))
        rows = sorted((f["id"], f["score"], f["reviewSuggestion"]["state"]) for _, f in pairs)
        review = sorted(r[0] for r in rows if r[2] == "review")
        return {"highRisk": high_risk, "review": review, "rows": [list(r) for r in rows]}

    def test_t21_queue_and_high_risk_equal_the_v1_golden(self):
        current = self.snapshot()
        if not GOLDEN.exists():  # one-off capture at 491094d
            GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        # The only intended difference since 491094d is the speech gate: a YouTube video whose transcript is still
        # to be fetched (replay has no cache) raises no high_risk until the speech is examined.
        held = [ref for ref in golden["highRisk"] if ref.startswith("youtube:")]
        self.assertTrue(held, "the golden has YouTube suspects held back by the gate")
        self.assertEqual(current["highRisk"], [ref for ref in golden["highRisk"] if ref not in held])
        self.assertEqual({k: v for k, v in current.items() if k != "highRisk"}, {k: v for k, v in golden.items() if k != "highRisk"})
        self.assertTrue(current["highRisk"])


class SingleCallSite(unittest.TestCase):
    def test_t20_analyze_returns_v2_fields_and_calibration_sees_the_same_route(self):
        cap = capture(description=UNMARKED)
        found = analyze(cap)
        self.assertIn(found["reviewDecision"]["route"], {"refer", "complete", "no_signal", "insufficient"})
        row = next(e for e in calibration(60)["examples"] if e["module"] == "M1")
        self.assertIn("route", row)


class QualificationRules(unittest.TestCase):
    def test_t26_reach_does_not_change_the_decision(self):
        small = analyze(capture(description=UNMARKED, reach={"metrics": {"viewCount": {"value": 10, "state": "observed"}}}))
        large = analyze(capture(description=UNMARKED, reach={"metrics": {"viewCount": {"value": 10 ** 7, "state": "observed"}}}))
        self.assertEqual(small["reviewDecision"], large["reviewDecision"])
        self.assertEqual(small["reviewScore"], large["reviewScore"])

    def test_t28_registry_inclusion_follows_declared_or_documented_relation(self):
        declared = analyze(capture(description=DECLARATION))
        cta_only = analyze(capture(description="Otwórz rachunek w XTB."))
        neutral = analyze(capture(description="Na przykładzie XTB pokazuję, czym jest zlecenie limit."))
        self.assertEqual(declared["adRegistry"]["state"], "included")
        self.assertEqual(cta_only["adRegistry"]["state"], "candidate")
        self.assertEqual(neutral["adRegistry"]["state"], "none")
        names = {c["registryId"] for c in declared["adRelationship"]["firm"]["candidates"]}
        self.assertEqual(names, {6884980, 9439233})

    def test_t31_unmarked_collaboration_is_referred_even_when_identity_is_open(self):
        found = analyze(capture(description=UNMARKED))
        self.assertEqual(found["reviewDecision"]["route"], "refer")
        self.assertEqual(found["adRegistry"]["state"], "candidate")
        self.assertTrue(any("mowy nie zbadano" in r for r in found["reviewDecision"]["reasons"]))
        marked = analyze(capture(description=UNMARKED, segments=[
            {"start": 5, "end": 9, "text": "Ten film powstał we współpracy z firmą XTB.", "confidence": .9}]))
        self.assertEqual(marked["reviewDecision"]["route"], "no_signal")
        self.assertEqual(marked["adRegistry"]["state"], "included")

    def test_t32_opinion_without_relation_is_outside_the_queue(self):
        found = analyze(capture(description="Zarobiłem 30% na akcjach w XTB."))
        self.assertEqual(found["reviewDecision"]["route"], "no_signal")
        self.assertEqual(found["adRegistry"]["state"], "none")

    def test_t33_every_refer_has_reasons_and_moments(self):
        for cap in (capture(description=UNMARKED),
                    capture(description=DECLARATION, segments=CLAIM_SEGMENTS)):
            found = analyze(cap)
            decision = found["reviewDecision"]
            if decision["route"] != "refer":
                continue
            self.assertTrue(3 <= len(decision["reasons"]) <= 5)
            self.assertTrue(decision["moments"])
            ids = {e["id"] for e in found["evidence"] if "id" in e}  # shadow: v1 items keep no id
            for moment in decision["moments"]:
                self.assertIn(moment["evidenceId"], ids)
                self.assertTrue(moment["deepLink"])
        self.assertEqual(analyze(capture(description=UNMARKED))["reviewDecision"]["route"], "refer")

    def test_t25_transcript_scope(self):
        no_text = analyze(capture(description=DECLARATION))
        self.assertNotEqual(no_text["reviewDecision"]["route"], "no_signal")
        self.assertIn(no_text["reviewDecision"]["completeReason"], {"transcript_pending", "transcript_unavailable"})
        with_speech = analyze(capture(description=DECLARATION, segments=CLAIM_SEGMENTS,
                                      mediaCoverage={"transcript": {"state": "full", "source": "asr"}, "frames": {"state": "not_collected"}}))
        self.assertEqual(with_speech["reviewDecision"]["route"], "refer")
        self.assertEqual(with_speech["coverage"]["modalities"]["frames"]["state"], "not_collected")


class Highrisk(StateCase):
    def test_t24_high_risk_fires_once_on_transition_to_eligible_refer(self):
        cap = capture()
        refer = {"analysisVersion": {"rules": "q", "schema": 2, "variant": "qual_d"},
                 "reviewDecision": {"route": "refer", "queueEligible": True}, "score": 10}
        self.put(cap, **{**refer, "reviewDecision": {"route": "no_signal", "queueEligible": False}})
        self.assertEqual(len(self.events("high_risk")), 0)
        self.put(cap, **refer, summary="Zmiana analizy.")
        self.assertEqual(len(self.events("high_risk")), 1)
        self.put(cap, **refer, summary="Zmiana analizy.")
        self.put(cap, **refer, summary="Zmiana analizy 2.")
        self.assertEqual(len(self.events("high_risk")), 1)

    def test_t24_legacy_rule_is_unchanged(self):
        self.put(capture("youtube:BBBBBBBBBBB"), score=94)
        self.put(capture("youtube:CCCCCCCCCCC"), score=69)
        self.assertEqual([e["ref"] for e in self.events("high_risk")], ["youtube:BBBBBBBBBBB"])


class QueuesAndThresholds(HttpCase):
    def test_t14_queues_are_computed_by_the_api(self):
        self.put(capture("youtube:BBBBBBBBBBB"), reviewDecision={"route": "refer", "queueEligible": True},
                 reviewScore={"value": 70}, adRegistry={"state": "included"})
        self.put(capture("youtube:CCCCCCCCCCC"), reviewDecision={"route": "complete"}, adRegistry={"state": "included"})
        self.put(capture("demo-1", platform="demo", synthetic=True), synthetic=True)
        status, review = self.request("GET", "/v1/queues/review")
        self.assertEqual(status, 200)
        self.assertEqual([i["id"] for i in review["items"]], ["youtube:BBBBBBBBBBB"])
        self.assertEqual([i["id"] for i in self.request("GET", "/v1/queues/incomplete")[1]["items"]], ["youtube:CCCCCCCCCCC"])
        self.assertEqual(len(self.request("GET", "/v1/queues/adRegister")[1]["items"]), 2)
        self.assertEqual([i["id"] for i in self.request("GET", "/v1/queues/demo")[1]["items"]], ["demo-1"])
        counts = self.request("GET", "/v1/state")[1]["queues"]
        self.assertEqual((counts["review"], counts["demo"]), (1, 1))

    def test_t15_threshold_history_is_append_only_and_restorable(self):
        status, current = self.request("GET", "/v1/threshold")
        self.assertEqual((status, current["value"]), (200, 60))
        status, first = self.request("PUT", "/v1/threshold", {"value": 75, "expectedId": current["id"], "note": "Test."})
        self.assertEqual(status, 200)
        self.assertEqual(self.request("PUT", "/v1/threshold", {"value": 80, "expectedId": current["id"], "note": "Stare."})[0], 409)
        status, restored = self.request("POST", "/v1/threshold/restore", {"id": current["id"], "expectedId": first["id"], "note": "Cofnięcie."})
        self.assertEqual((status, restored["value"]), (200, 60))
        history = self.request("GET", "/v1/threshold/history")[1]["items"]
        self.assertEqual([h["value"] for h in history][-3:], [60, 75, 60])
        self.assertEqual(history[-1]["restoredFrom"], current["id"])

    def test_t13_recompute_scan_keeps_decisions_and_is_idempotent(self):
        self.put(capture(), rulesVersion="investwatch-rules-pl-1.1")
        status, scan = self.request("POST", "/v1/scans", {"mode": "recompute", "requestId": "recompute-test"})
        self.assertEqual(status, 202)
        self.assertEqual(self.request("POST", "/v1/scans", {"mode": "recompute", "requestId": "recompute-test"})[1]["scanId"], scan["scanId"])

    def test_t22_variant_switch_requires_validation_and_is_logged(self):
        status, current = self.request("GET", "/v1/qualification")
        self.assertEqual((status, current["variant"]), (200, "rules_1_2"))
        body = {"variant": "qual_d", "expectedId": current["id"], "note": "Bramka."}
        self.assertEqual(self.request("PUT", "/v1/qualification", body)[0], 422)
        self.assertEqual(self.request("PUT", "/v1/qualification", {**body, "variant": "qual_d_model", "validationRef": "q-v1", "approvedBy": "J"})[0], 422)
        status, changed = self.request("PUT", "/v1/qualification", {**body, "validationRef": "q-v1", "approvedBy": "J"})
        self.assertEqual((status, changed["variant"]), (200, "qual_d"))
        items = self.request("GET", "/v1/qualification/history")[1]["items"]
        self.assertEqual([i["variant"] for i in items][-2:], ["rules_1_2", "qual_d"])

    def test_t23_model_variant_falls_back_to_rules_reproducibly(self):
        from analysis import qualification
        self.assertTrue(hasattr(qualification, "qualify"))
        cap = capture(description=UNMARKED)
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-v1-NEVERREAD"}):
            found = analyze(cap, variant="qual_d_model")
        self.assertEqual(found["variants"]["qual_d_model"]["variantUsed"], "qual_d")
        self.assertIsNotNone(found["variants"]["qual_d_model"]["fallback"])

    def test_t29_analyst_transcript_creates_evidence_version_without_changing_origin(self):
        self.put()
        body = {"caseId": VIDEO, "kind": "transcript", "source": "analyst", "note": "Transkrypt za zgodą.",
                "segments": CLAIM_SEGMENTS, "expectedRevision": 1}
        status, result = self.request("POST", "/v1/evidence", body)
        self.assertEqual(status, 200)
        found = self.case()
        self.assertEqual((found["version"], found["origin"]), (2, "live"))
        self.assertEqual(found["versions"][-1]["changeKind"], "evidence")
        self.assertEqual(found["coverage"]["modalities"]["transcript"]["source"], "analyst")
        self.assertEqual(self.request("POST", "/v1/evidence", body)[0], 409)

    def test_t30_availability_changes_without_a_new_version_and_language_is_out_of_scope(self):
        self.put(capture(availability={"state": "available", "observedAt": "2026-11-21T10:00:00+00:00"}))
        removed = capture(availability={"state": "removed", "observedAt": "2026-11-21T12:00:00+00:00"},
                          observedAt="2026-11-21T12:00:00+00:00")
        self.assertEqual(self.put(removed)["changedFindings"], 0)
        self.assertEqual(self.case()["availability"]["state"], "removed")
        self.put(capture("youtube:BBBBBBBBBBB", language={"detected": "en", "method": "text"}, outOfScope="language"),
                 reviewDecision={"route": "refer", "queueEligible": True})
        self.assertEqual(self.request("GET", "/v1/queues/review")[1]["items"], [])
        self.assertIn("youtube:BBBBBBBBBBB", [i["id"] for i in self.request("GET", "/v1/queues/all")[1]["items"]])


if __name__ == "__main__":
    unittest.main()
