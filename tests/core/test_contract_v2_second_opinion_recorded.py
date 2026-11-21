"""The recorded second opinion in a dated replay: attached with its origin, never changes route, score or queues (lane H)."""
import unittest
from unittest.mock import patch

from analysis.engine import analyze
from api import second_opinion_recorded as rec
from v2_helpers import HttpCase, StateCase, capture


class Recorded(unittest.TestCase):
    def test_m1_video_gets_the_recorded_verdict_with_origin(self):
        second = rec.recorded("youtube:CDk20n4u9Kk", "M1", True)  # rules said: no disclosure; the model read "ujawnione"
        self.assertEqual((second["runtime"], second["status"], second["verdict"]), ("recorded", "ready", "ujawnione"))
        self.assertTrue(second["needsReview"])
        self.assertEqual(second["reviewLabel"], "rozbieżność — do przeglądu")
        self.assertEqual(second["modelId"], "qwen/qwen3.8-27b")
        self.assertTrue(second["source"].startswith("fixtures/labeled/ai-second-opinion-m1-"))
        self.assertTrue(second["quote"] and second["locator"]["seconds"] is not None)
        agree = rec.recorded("youtube:7M0rC6-Rueo", "M1", True)
        self.assertEqual((agree["verdict"], agree["needsReview"]), ("brak_ujawnienia", False))

    def test_rejected_primary_falls_back_and_unknown_or_m2_is_none(self):
        self.assertEqual(rec.recorded("youtube:yIbtMnfP25Q", "M1", False)["modelId"], "google/gemma-4-31b-it")
        self.assertIsNone(rec.recorded("youtube:zzzzzzzzzzz", "M1", False))
        self.assertIsNone(rec.recorded("web:xtb.com/pl", "M2", True))
        self.assertEqual(rec.recorded("web:mbank.pl:m3", "M3", False)["task"], "m3_offer")

    def test_attaching_it_changes_nothing_but_the_field(self):
        cap = capture("youtube:CDk20n4u9Kk", mode="replay", description="Opis. Współpraca z XTB: https://link-pso.xtb.com/pso/abc")
        with patch("api.second_opinion_recorded.recorded", return_value=None):
            plain = analyze(cap)
        with_second = analyze(cap)
        self.assertIn("secondOpinion", with_second)
        self.assertNotIn("secondOpinion", plain)
        strip = lambda f: {k: v for k, v in f.items() if k != "secondOpinion"}
        self.assertEqual(strip(with_second), plain)

    def test_models_block_reads_the_numbers_from_the_summary(self):
        block = rec.models_block({"status": "unavailable"})
        second = block["secondOpinion"]
        self.assertEqual(second["mode"], "recorded")
        self.assertEqual((second["measured"]["M3"]["costRules"], second["measured"]["M3"]["costVeto"]), (10, 1))
        self.assertEqual(second["measured"]["M1"]["broken"], 0)
        self.assertEqual(block["materialType"]["measured"]["correct"], 30)


class Stored(StateCase):
    def test_a_recorded_opinion_added_by_a_recompute_is_stored_and_a_repeat_adds_nothing(self):
        self.put()
        self.assertEqual(self.versions(), 1)
        second = {"status": "ready", "verdict": "ujawnione", "needsReview": False, "runtime": "recorded", "affectsRoute": False}
        self.put(secondOpinion=second)
        self.assertEqual(self.versions(), 2)
        self.assertEqual(self.case()["secondOpinion"]["runtime"], "recorded")
        self.put(secondOpinion=second)
        self.assertEqual(self.versions(), 2)


class Overview(HttpCase):
    def test_overview_has_the_models_block(self):
        _, body = self.request("GET", "/v1/overview?schema=2")
        self.assertEqual(body["models"]["secondOpinion"]["measured"]["M3"]["costVeto"], 1)
        self.assertIn(body["models"]["materialType"]["status"], ("ready", "unavailable"))


if __name__ == "__main__":
    unittest.main()
