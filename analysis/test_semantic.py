import os
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from .semantic import LOCK, MAX_FRAGMENTS, MODEL_DIR_ENV, _fragments, suggest, review_suggestion


class TestSemantic(unittest.TestCase):
    def test_m1_review_uses_rule_evidence_not_model_label(self):
        from .engine import analyze
        for text, expected in (("Partnerem odcinka jest XTB.", "review"),
                               ("Załóż rachunek w XTB.", "review"),
                               ("XTB opublikowało wyniki.", "no_signal"),
                               ("Odcinek nie powstał we współpracy z XTB.", "no_signal")):
            capture = {"module": "M1", "description": text, "url": "https://example.org/material"}
            finding = analyze(capture)
            suggestion = review_suggestion(capture, {"status": "unavailable"}, finding)
            self.assertEqual((suggestion["state"], suggestion["source"]), (expected, "rules"))
            if expected == "review":
                self.assertIn(suggestion["evidence"]["text"], text)
                self.assertEqual(suggestion["evidence"]["url"], capture["url"])
        capture = {"module": "M1", "description": "Rozmowa o finansach.", "mediaUrl": "/media/demo.mp4",
                   "segments": [{"start": 3.0, "end": 5.0, "text": "Partnerem odcinka jest XTB."}]}
        suggestion = review_suggestion(capture, {"status": "unavailable"}, analyze(capture))
        self.assertEqual((suggestion["state"], suggestion["evidence"]["start"], suggestion["evidence"]["end"]),
                         ("review", 3.0, 5.0))
        self.assertEqual(suggestion["evidence"]["url"], "/media/demo.mp4#t=3.0,5.0")

    def test_full_page_tail_and_false_positive_controls(self):
        text = ("Zdanie o informacjach ogólnych. " * 240) + "Dobierzemy klientowi akcje."
        self.assertIn("Dobierzemy klientowi akcje.", _fragments({"description": text}))
        def result(module, quote, kind):
            semantic = {"status": "ready", "class": kind, "evidence": {"text": quote}}
            return review_suggestion({"module": module}, semantic)["state"]
        self.assertEqual(result("M3", "Lista instrumentów: akcje i obligacje.", "personalized_advice"), "uncertain")
        self.assertEqual(result("M3", "My podpowiadamy co kupić i sprzedać, Ty decydujesz.", "personalized_advice"), "review")
        self.assertEqual(result("M3", "Nie dobieramy akcji dla klientów.", "personalized_advice"), "uncertain")
        self.assertEqual(result("M1", "XTB notuje wyniki.", "partnership"), "unavailable")
    def test_readiness_and_bounded_exact_quotes(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {MODEL_DIR_ENV: directory}):
            self.assertEqual(suggest({"module": "M1", "description": "Tekst o firmie maklerskiej."})["status"],
                             "unavailable")
            self.assertEqual(suggest({"module": "M1", "description": ""})["status"], "empty")
        cap = {
            "module": "M1", "title": "Informacja o emisji akcji",
            "description": "\n".join(f"Bardzo długi i interesujący fragment o obligacjach numer {i}." for i in range(10_000)),
            "segments": [{"text": "Fragment rozmowy o obligacjach.", "start": 3, "end": 6}],
        }
        source = _fragments(cap)
        self.assertLessEqual(len(source), MAX_FRAGMENTS)
        self.assertGreater(len(source), 16)
        timed = source["Fragment rozmowy o obligacjach."]
        self.assertEqual((timed["field"], timed["start"], timed["end"]), ("transcript", 3, 6))

    def test_near_tie_does_not_suggest_a_named_category(self):
        responses = [("partnership", 0.85), ("neutral", 0.847), ("no_partnership", 0.7)]
        with TemporaryDirectory() as directory, patch.dict(os.environ, {MODEL_DIR_ENV: directory}):
            for name in LOCK["files"]:
                (Path(directory) / name).touch()
            with patch("analysis.semantic.runtime", return_value=Mock(similar=Mock(return_value=responses))):
                result = suggest({"module": "M1", "description": "Neutralna informacja o wynikach spółki."})
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["class"], "uncertain")
        self.assertEqual(result["leadingClass"], "partnership")
        self.assertEqual(result["runnerUp"]["class"], "neutral")
        self.assertEqual(result["cosineSimilarity"], 0.85)


@unittest.skipUnless(os.getenv(MODEL_DIR_ENV), "Set INVESTWATCH_SEMANTIC_DIR to run the local model test.")
class TestLocalModel(unittest.TestCase):
    def test_discovered_offer_and_education_control(self):
        root = Path(__file__).resolve().parents[1] / "fixtures/validation"
        results = []
        for name in ("bossa-discovery-2026-11-21.json", "bossa-education-2026-11-21.json"):
            capture = json.loads((root / name).read_text())["capture"]
            result = suggest(capture)
            self.assertEqual(result["status"], "ready")
            self.assertFalse(result["scope"]["limited"])
            self.assertIn(result["fragment"], capture["description"])
            results.append(review_suggestion(capture, result)["state"])
        self.assertEqual(results[0], "review")
        self.assertIn(results[1], ("no_signal", "uncertain"))

    def test_offline_recorded_quote_paraphrase_negation_and_education(self):
        cases = (
            ("M1", "partnership", "Partnerem odcinka jest XTB"),
            ("M1", "partnership", "Rachunek za realizację audycji pokrył internetowy dom maklerski."),
            ("M1", "no_partnership", "Odcinek przygotowaliśmy niezależnie."),
            ("M1", "uncertain", "W tym tygodniu spółka opublikowała wyniki, a indeks polskich akcji zakończył sesję wyżej."),
            ("M2", "risk_warning", "Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków pieniężnych."),
            ("M3", "personalized_advice", "Przyjrzymy się temu, na co odkładasz, i wskażemy Ci, których obligacji potrzebujesz."),
            ("M3", "general_education", "Między innymi opisujemy fundusze, ale nie zalecamy zakupu konkretnych instrumentów."),
        )
        with patch("socket.create_connection", side_effect=AssertionError("unexpected network use")):
            for module, expected, text in cases:
                with self.subTest(expected=expected, fragment=text):
                    result = suggest({"module": module, "description": text})
                    self.assertEqual(result["status"], "ready")
                    self.assertEqual(result["class"], expected)
                    self.assertEqual(result["fragment"], text)
                    self.assertGreaterEqual(result["cosineSimilarity"], -1)
                    self.assertLessEqual(result["cosineSimilarity"], 1)
