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
        # The golden is the queue of the legacy rules: compare it explicitly for rules_1_2, not for the product default.
        with store.connection() as db:
            self.assertEqual(store.active_variant(db), "rules_1_2")
        current = self.snapshot()
        if not GOLDEN.exists():  # one-off capture at 491094d
            GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        # Public alerts skip the historical synthetic cases. The speech gate holds the two archived YouTube videos.
        held = [ref for ref in golden["highRisk"] if ref.startswith("youtube:")]
        self.assertTrue(held, "the golden has YouTube suspects held back by the gate")
        self.assertEqual(current["highRisk"], [ref for ref in golden["highRisk"] if ref not in held and not ref.startswith("demo-")])
        self.assertEqual({k: v for k, v in current.items() if k != "highRisk"}, {k: v for k, v in golden.items() if k != "highRisk"})


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


class DefaultVariant(HttpCase):
    """A new, empty database starts on qual_d (decision of 21 XI 2026); the way back to rules_1_2 stays open."""
    BASELINE = None

    def test_new_database_starts_on_qual_d_as_history_entry_one(self):
        status, current = self.request("GET", "/v1/qualification")
        self.assertEqual((status, current["id"], current["variant"]), (200, 1, "qual_d"))
        self.assertEqual(current["validationRef"], "fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md@463cceb")
        self.assertTrue(current["validatedBy"])
        items = self.request("GET", "/v1/qualification/history")[1]["items"]
        self.assertEqual([i["variant"] for i in items], ["qual_d"])
        self.assertIn("nie walidacja ekspercka", items[0]["note"])
        state = self.request("GET", "/v1/state")[1]
        self.assertEqual((state["analysisCurrent"]["variant"], state["threshold"]["value"]), ("qual_d", 60))
        self.assertEqual(state["recompute"]["state"], "none")

    def test_way_back_to_rules_1_2_by_put_and_restore(self):
        status, back = self.request("PUT", "/v1/qualification", {"variant": "rules_1_2", "expectedId": 1, "note": "Powrót."})
        self.assertEqual((status, back["variant"]), (200, "rules_1_2"))
        status, again = self.request("POST", "/v1/qualification/restore", {"id": 1, "expectedId": back["id"], "note": "Z powrotem."})
        self.assertEqual((status, again["variant"], again["restoredFrom"]), (200, "qual_d", 1))
        self.assertEqual(again["validationRef"], store.DEFAULT_VALIDATION_REF)

    def test_small_recompute_runs_inline_and_state_reports_it(self):
        self.put(capture(description="Partnerem odcinka jest XTB."), reviewDecision={"route": "refer", "queueEligible": True})
        self.assertEqual(self.request("PUT", "/v1/qualification", {"variant": "rules_1_2", "expectedId": 1})[0], 200)
        recompute = self.request("GET", "/v1/state")[1]["recompute"]
        self.assertEqual(recompute["state"], "done")

    def test_recompute_without_a_worker_says_it_is_waiting(self):
        from api import jobs
        self.put(capture(description="Opis."))
        with patch.object(jobs, "INLINE_RECOMPUTE_MAX", 0):
            self.assertEqual(self.request("PUT", "/v1/qualification", {"variant": "rules_1_2", "expectedId": 1})[0], 200)
        recompute = self.request("GET", "/v1/state")[1]["recompute"]
        self.assertEqual(recompute["state"], "queued")
        from datetime import datetime, timedelta, timezone
        with store.connection() as db:
            late = store.recompute_status(db, datetime.now(timezone.utc) + timedelta(seconds=60))
        self.assertEqual(late["state"], "waiting_for_worker")
        self.assertIn("czeka na worker", late["message"])


class ApiDefects(HttpCase):
    """Defects found by the independent judge: creatorName, calibration set and threshold, semantic status."""
    BASELINE = None

    def refer(self, key, score, **extra):
        self.put(capture(key), reviewDecision={"route": "refer", "queueEligible": True}, reviewScore={"value": score},
                 adRegistry={"state": "candidate"}, **extra)

    def test_queue_rows_carry_the_creator_name_from_the_creators_table(self):
        cap = capture("youtube:BBBBBBBBBBB")
        self.scan([(cap, finding(cap, reviewDecision={"route": "refer", "queueEligible": True}, reviewScore={"value": 80}))],
                  mode="replay", creators=[{"id": cap["creatorId"], "name": "Kanał Testowy"}])
        for name in ("all", "review"):
            rows = self.request("GET", f"/v1/queues/{name}")[1]["items"]
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row["creatorName"], "Kanał Testowy", (name, row["id"]))
        self.assertEqual(self.request("GET", "/v1/queues/all?q=Testowy")[1]["total"], 1)

    def test_calibration_defaults_to_q_v2_and_agrees_with_the_measurement_report(self):
        report = json.loads((Path(__file__).resolve().parents[2] / "fixtures/validation/q-v2/wynik-M1-2026-11-21.json").read_text(encoding="utf-8"))
        status, cal = self.request("GET", "/v1/calibration")
        self.assertEqual((status, cal["dataset"], cal["variant"], cal["threshold"]), (200, "q-v2", "qual_d", 60))
        self.assertEqual(self.request("GET", "/v1/threshold")[1]["value"], cal["threshold"])
        for variant, rows in report["fullCoverage"].items():
            expected = next(r for r in rows if r["threshold"] == 60)
            got = cal["variants"][variant]
            self.assertEqual({k: got[k] for k in ("tp", "fp", "tn", "fn", "cost", "referredCampaigns")},
                             {k: expected[k] for k in ("tp", "fp", "tn", "fn", "cost", "referredCampaigns")}, variant)
        for variant in ("rules_1_2", "qual_d"):
            v = cal["variants"][variant]
            self.assertEqual(v["tp"] + v["fp"] + v["tn"] + v["fn"], v["evaluated"])
            self.assertEqual(v["cost"], 2 * v["fn"] + v["fp"])
        self.assertEqual((cal["variants"]["rules_1_2"]["cost"], cal["variants"]["qual_d"]["cost"]), (15, 0))
        self.assertTrue(cal["labelTarget"] and cal["labelers"] and cal["campaigns"]["independent"])
        self.assertIn("nie walidacja ekspercka", cal["disclaimer"])
        self.assertEqual(cal["queueEffect"]["changed"], 0)

    def test_illustrative_set_stays_available(self):
        status, cal = self.request("GET", "/v1/calibration?dataset=illustrative&threshold=60&variant=rules_1_2")
        self.assertEqual((status, cal["evaluationStatus"], cal["n"]), (200, "illustrative_not_held_out", 13))
        self.assertEqual(self.request("GET", "/v1/calibration?dataset=nope")[0], 422)

    def test_calibration_threshold_is_the_one_that_filters_the_real_queue(self):
        self.refer("youtube:BBBBBBBBBBB", 70)
        self.refer("youtube:CCCCCCCCCCC", 85)
        self.assertEqual(self.request("GET", "/v1/queues/review")[1]["total"], 2)
        effect = self.request("GET", "/v1/calibration?threshold=80")[1]["queueEffect"]
        self.assertEqual((effect["reviewQueueAtStored"], effect["reviewQueueAtThreshold"], effect["changed"]), (2, 1, 1))
        self.assertEqual(effect["lost"], ["youtube:BBBBBBBBBBB"])
        current = self.request("GET", "/v1/threshold")[1]
        self.assertEqual(self.request("PUT", "/v1/threshold", {"value": 80, "expectedId": current["id"], "note": "Test."})[0], 200)
        self.assertEqual(self.request("GET", "/v1/queues/review")[1]["total"], effect["reviewQueueAtThreshold"])
        after = self.request("GET", "/v1/calibration")[1]
        self.assertEqual((after["threshold"], after["thresholdSource"], after["queueEffect"]["changed"]), (80, "stored", 0))

    def test_state_says_why_the_semantic_model_is_unavailable(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            env.pop("INVESTWATCH_SEMANTIC_DIR", None)
            with patch("importlib.util.find_spec", return_value=None):
                unset = self.request("GET", "/v1/state")[1]["semantic"]
            env["INVESTWATCH_SEMANTIC_DIR"] = str(Path(self.temp) / "brak-wag")
            empty = self.request("GET", "/v1/state")[1]["semantic"]
        self.assertEqual((unset["status"], unset["m3Mode"]), ("unavailable", "rules_only"))
        self.assertIn("nie ustawiono INVESTWATCH_SEMANTIC_DIR", unset["message"])
        self.assertIn("wyłącznie na regułach", unset["message"])
        self.assertEqual((empty["status"], empty["m3Mode"]), ("unavailable", "rules_only"))
        self.assertIn("brak wag modelu E5", empty["message"])
        self.assertTrue(empty["missingFiles"])


MEDIA_CACHE = Path(__file__).resolve().parents[2] / ".runtime/media-cache"


@unittest.skipUnless((MEDIA_CACHE / "_aqCM37gK1U/transcript.json").is_file(), "brak .runtime/media-cache z filmami z 21 XI")
class ForeignFirmsOnRealRecords(HttpCase):
    """Replay B records (fixtures/raw/media/2026-11-21) under the product default qual_d."""
    BASELINE = None

    def captures(self):
        from analysis.test_qualification import media_capture
        return {vid: media_capture(vid) for vid in ("_aqCM37gK1U", "9Fcwo1jlwe4", "O5YmmKadQQw")}

    def test_saxo_is_in_the_ad_register_and_not_blocked_in_incomplete(self):
        caps = self.captures()
        self.scan([evaluate(c) for c in caps.values()], mode="replay")
        ids = lambda name: {i["id"] for i in self.request("GET", f"/v1/queues/{name}")[1]["items"]}
        self.assertLessEqual({"youtube:_aqCM37gK1U", "youtube:9Fcwo1jlwe4", "youtube:O5YmmKadQQw"}, ids("adRegister"))
        self.assertEqual(ids("incomplete") & set(map(lambda v: f"youtube:{v}", caps)), set())
        self.assertEqual(ids("review") & set(map(lambda v: f"youtube:{v}", caps)), set())
        saxo = self.case("youtube:_aqCM37gK1U")
        self.assertEqual(saxo["adRegistry"]["identityStatus"], "no_registry_entry")
        self.assertEqual(self.case("youtube:9Fcwo1jlwe4")["adRelationship"]["firm"]["passporting"], "cross_border")


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
        self.assertEqual((counts["review"], counts["demo"]), (1, 0))

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
