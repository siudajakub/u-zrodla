import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from .semantic import LOCK, MAX_FRAGMENTS, MODEL_DIR_ENV, _fragments, suggest


class TestSemantic(unittest.TestCase):
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
        self.assertEqual(len(source), MAX_FRAGMENTS)
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
