"""Fields the pitch needs from the desk (lane H): funnel, proofPath, scanMode and scanLabel in the overview. No network."""
from pathlib import Path
import unittest

from api import store
from api.enrich import with_probe_frames
from api.proof_path import proof_path
from v2_helpers import StateCase, capture

SPEECH = {"module": "M1", "url": "https://www.youtube.com/watch?v=CDk20n4u9Kk", "route": "no_signal",
          "discovery": [{"reason": "wynik wyszukiwania (brand)", "query": "XTB"}],
          "adRelationship": {"status": "documented", "basis": "link firmowy",
                             "disclosure": {"state": "in_speech", "where": "transcript", "kind": "partner_mention", "evidenceId": "ev-1",
                                            "text": "znajdziecie u partnera tego odcinka XTB."},
                             "firm": {"candidates": [{"name": "XTB S.A."}]}},
          "evidence": [{"id": "ev-1", "start": 614.0}],
          "coverage": {"modalities": {"transcript": {"state": "full", "durationSec": 1065}, "platformFlags": {"state": "unavailable"},
                                      "frames": {"state": "not_collected"}, "description": {"state": "full"}}},
          "reviewDecision": {"route": "no_signal", "reason": "Współpraca jest oznaczona w mowie."}}
SURVIVED = {**SPEECH, "route": "refer", "url": "https://www.youtube.com/watch?v=AqXHkxDzSDI",
            "adRelationship": {"status": "probable", "basis": "kod twórcy", "disclosure": {"state": "not_found_in_scope", "where": None},
                               "firm": {"candidates": [{"name": "XTB S.A."}]}},
            "coverage": {"modalities": {"transcript": {"state": "full", "durationSec": 204}, "platformFlags": {"state": "observed", "paidPromotion": False},
                                        "frames": {"state": "selected_moments", "moments": [15.84, 186.17]}, "description": {"state": "full"}}},
            "reviewDecision": {"route": "refer", "reason": "Nieoznaczona współpraca."}}


class ProofPath(unittest.TestCase):
    def test_refuted_in_speech_has_the_second_and_a_deep_link(self):
        steps = {s["id"]: s for s in proof_path(SPEECH)}
        self.assertEqual(list(steps), ["discovery", "description", "platformFlag", "speech", "frames", "firm", "decision"])
        self.assertEqual((steps["speech"]["state"], steps["speech"]["at"]), ("refuted", 614.0))
        self.assertTrue(steps["speech"]["deepLink"].endswith("t=614s"))
        self.assertEqual(steps["platformFlag"]["state"], "gap")
        self.assertTrue(all(set(s) >= {"id", "label", "state", "detail"} for s in steps.values()))

    def test_survivor_checks_the_whole_speech_and_the_frames(self):
        steps = {s["id"]: s for s in proof_path(SURVIVED)}
        self.assertEqual(steps["speech"]["state"], "suspect")
        self.assertIn("3:24", steps["speech"]["detail"])
        self.assertEqual((steps["platformFlag"]["state"], steps["frames"]["state"], steps["decision"]["state"]), ("ok", "ok", "suspect"))

    def test_m2_and_m3_lists(self):
        m3 = proof_path({"module": "M3", "route": "refer", "axes": {"action": {"evidence": [{"quote": "dobieramy proporcje"}]}},
                         "identity": {"licensed": False, "label": "brak danych podmiotu"}, "reviewDecision": {"route": "refer"}})
        self.assertEqual([s["id"] for s in m3], ["discovery", "action", "personalisation", "identity", "decision"])
        m2 = proof_path({"module": "M2", "route": "no_signal", "m2Card": {"rows": [], "viewports": ["komputer 1440×900"], "firm": {"name": "XTB S.A.", "registryId": 1}}})
        self.assertEqual([s["id"] for s in m2], ["read", "claim", "warning", "firm", "decision"])


class Overview(StateCase):
    def test_scan_mode_names_a_replay_and_funnel_counts_the_register(self):
        with store.connection(True) as db:
            db.execute("INSERT INTO scans(id,request_id,mode,status,created,updated,payload,result) VALUES('s1','r1','replay','done',"
                       "'2026-11-21T21:00:00+00:00','2026-11-21T21:01:00+00:00','{}','{}')")
        self.put(module="M1")
        state = store.state(2, False, False)
        self.assertEqual((state["scanMode"], state["scanLabel"]), ("replay", "odtworzenie skanu z 21 listopada 2026"))
        funnel = state["funnel"]
        self.assertEqual(set(funnel), {"materials", "adRegister", "review", "explainedAutomatically", "adRegisterUnexplained",
                                       "heldBySpeechGate", "byModule", "byPlatform"})
        self.assertEqual(funnel["byModule"]["M1"], funnel["materials"] - funnel["byModule"]["M2"] - funnel["byModule"]["M3"])
        self.assertEqual(set(funnel["explainedAutomatically"]), {"bySpeech", "byPlatformFlag", "byFrame", "byDescription"})


class ProbeFrames(unittest.TestCase):
    PACK = Path(__file__).resolve().parents[2] / ".runtime/replay-media/2026-11-21"

    def test_the_614_second_frame_of_comparic_is_attached_as_a_frame_with_the_observation(self):
        if not (self.PACK / "CDk20n4u9Kk/frames/stream_360p_000614.jpg").is_file():
            self.skipTest("brak paczki mediów na tym hoście")
        from analysis.engine import analyze
        cap = capture("youtube:CDk20n4u9Kk", description="Opis. Współpraca z XTB https://link-pso.xtb.com/pso/abc")
        framed = with_probe_frames([cap], self.PACK)[0]
        self.assertEqual([f["time"] for f in framed["frames"]], [614.0])
        found = analyze(framed)
        frame = next(e for e in found["evidence"] if e["kind"] == "frame")
        self.assertEqual(frame["start"], 614.0)
        self.assertIn("REKLAMA", frame["text"])
        self.assertEqual(with_probe_frames([{**cap, "frames": [{"time": 1}]}], self.PACK)[0]["frames"], [{"time": 1}])

    def test_without_the_pack_nothing_is_attached(self):
        cap = capture("youtube:CDk20n4u9Kk")
        self.assertNotIn("frames", with_probe_frames([cap], Path("/nonexistent-pack"))[0])


if __name__ == "__main__":
    unittest.main()
