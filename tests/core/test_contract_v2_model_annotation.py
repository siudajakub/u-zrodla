"""Model annotation (lane H): INVESTWATCH_MODEL_ANNOTATE=1 adds a descriptive `model` field and nothing else.
No network, no weights: the classifier is replaced."""
import os
import unittest
from unittest.mock import patch

from analysis import material_classifier
from analysis.engine import analyze
from analysis.semantic import review_suggestion
from api import store
from v2_helpers import StateCase, VIDEO, capture

DECLARED = "Partnerem odcinka jest XTB."
READY = {"task": "material_type", "engine": "e5-logreg", "status": "ready", "label": "reklama", "confidence": 0.9, "quote": None,
         "modelId": "e5", "version": "mt-test-1", "digest": "d", "promptVersion": None, "latencyMs": 3, "affectsDecision": False}


def refer_capture():
    return capture(description=DECLARED)


def plain_capture():
    return capture("youtube:BBBBBBBBBBB", description="Spokojny film o gotowaniu.", url="https://www.youtube.com/watch?v=BBBBBBBBBBB")


class ModelAnnotation(StateCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("network is off in tests")))
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_LLM": "0"}))
        self.calls = []

        def ready(cap):
            self.calls.append(cap["id"])
            return dict(READY)
        self.enterContext(patch.object(material_classifier, "classify", ready))

    def flagged(self, cap, flag="1"):
        with patch.dict(os.environ, {"INVESTWATCH_MODEL_ANNOTATE": flag}):
            return analyze(cap)

    def test_without_the_flag_nothing_changes(self):
        found = analyze(refer_capture())
        self.assertNotIn("model", found)
        self.assertIsNone(found["analysisVersion"]["model"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.flagged(refer_capture(), "0"), found)

    def test_the_flag_does_not_change_route_score_queues_or_the_content_signature(self):
        cap = refer_capture()
        off, on = analyze(cap), self.flagged(cap)
        self.assertEqual(on["model"]["label"], "reklama")
        self.assertFalse(on["model"]["affectsDecision"])
        self.assertEqual(on["analysisVersion"]["model"]["materialType"], "mt-test-1")
        rest = lambda f: {k: v for k, v in f.items() if k not in ("model", "analysisVersion")}
        self.assertEqual(rest(on), rest(off))
        self.assertEqual({k: v for k, v in on["analysisVersion"].items() if k != "model"},
                         {k: v for k, v in off["analysisVersion"].items() if k != "model"})
        self.assertEqual(store.signature_parts(cap, on)["signature"], store.signature_parts(cap, off)["signature"])
        self.assertEqual((on["reviewDecision"]["route"], on["score"]), (off["reviewDecision"]["route"], off["score"]))

    def test_queues_and_the_case_are_the_same_and_the_field_reaches_case_view_2(self):
        def run(flag):
            with patch.dict(os.environ, {"INVESTWATCH_MODEL_ANNOTATE": flag}):
                cap = refer_capture()
                found = analyze(cap)
                found["semantic"] = {"status": "unavailable"}
                found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
                self.scan([(cap, found)])
                with store.connection() as db:
                    row = db.execute("SELECT * FROM cases WHERE id=?", (VIDEO,)).fetchone()
                    return store.case_dict(db, row, schema=2)
        off = run("0")
        self.assertNotIn("model", off)
        with store.connection(True) as db:
            for table in ("cases", "versions", "version_meta", "qualification_results", "media_state"):
                db.execute("DELETE FROM " + table)
        on = run("1")
        self.assertEqual(on["model"]["label"], "reklama")
        for key in ("queues", "reviewDecision", "reviewScore", "score"):
            self.assertEqual(on.get(key), off.get(key), key)

    def test_a_failing_or_missing_model_is_a_status_never_a_scan_error(self):
        with patch.object(material_classifier, "classify", side_effect=RuntimeError("boom")):
            found = self.flagged(refer_capture())
        self.assertEqual(found["model"]["status"], "unavailable")
        with patch("analysis.inference.annotate", side_effect=RuntimeError("no weights")):
            found = self.flagged(refer_capture())
        self.assertEqual((found["model"]["status"], found["model"]["affectsDecision"]), ("unavailable", False))
        self.assertIn("model niedostępny", found["model"]["reason"])
        self.assertEqual(found["reviewDecision"]["route"], analyze(refer_capture())["reviewDecision"]["route"])

    def test_only_queue_material_is_annotated(self):
        self.assertIn("model", self.flagged(refer_capture()))
        self.assertNotIn("model", self.flagged(plain_capture()))
        self.assertEqual(self.calls, ["youtube:AAAAAAAAAAA"], "the classifier is not called for material outside the queues")


if __name__ == "__main__":
    unittest.main()
