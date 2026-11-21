"""The card of view 2 and the list rows tell one story (lane H, UX audit): v1 fields under `legacy`, human measurement text,
short distinct moment labels, module scale for the band, firm names, no cut title. Pure functions, no network."""
import unittest

from api import store
from api.card_view import card_view, human_text

M1 = {"id": "youtube:7M0rC6-Rueo", "module": "M1", "score": 24, "summary": "v1", "signalType": "x", "route": "refer",
      "reviewSuggestion": {"state": "no_signal", "reason": "stare"},
      "reviewDecision": {"route": "refer", "reason": "nowe", "alternative": "Mogło być inaczej.",
                         "reasons": ["a", "Mogło być inaczej."],
                         "moments": [{"evidenceId": "e1", "label": "Nieoznaczona współpraca", "start": 12.0},
                                     {"evidenceId": "e2", "label": "Nieoznaczona współpraca"}]},
      "evidence": [{"id": "e1", "text": "kod KANAL przy rejestracji w XTB"}, {"id": "e2", "text": "https://bit.ly/abc"}],
      "adRelationship": {"disclosure": {"where": "transcript", "kind": "platform_flag", "state": "in_speech"}},
      "coverage": {"modalities": {"platformFlags": {"paidPromotion": True}}}}


class Card(unittest.TestCase):
    def test_one_story_old_fields_move_under_legacy(self):
        card = card_view(M1)
        self.assertEqual(card["legacy"]["score"], 24)
        self.assertTrue(all(k not in card for k in ("score", "reviewSuggestion", "summary", "signalType")))
        self.assertEqual(card["reviewDecision"]["route"], "refer")
        self.assertIn("score", M1)  # the input (and so view 1 and the rows) is untouched

    def test_reasons_do_not_repeat_the_alternative_and_moments_have_short_distinct_labels(self):
        card = card_view(M1)
        self.assertEqual(card["reviewDecision"]["reasons"], ["a"])
        labels = [m["label"] for m in card["reviewDecision"]["moments"]]
        self.assertEqual(len(set(labels)), 2)
        self.assertTrue(labels[0].startswith("0:12 „kod KANAL"))
        self.assertNotIn("Nieoznaczona współpraca", labels)

    def test_disclosure_kind_agrees_with_where_and_lists_channels_by_strength(self):
        disclosure = card_view(M1)["adRelationship"]["disclosure"]
        self.assertEqual(disclosure["kinds"], ["speech", "platform_flag"])
        self.assertEqual(disclosure["kind"], "speech_marking")

    def test_m2_post_without_a_card_gets_the_same_route_and_score_as_its_row(self):
        post = {"id": "facebook:ad-1", "module": "M2", "route": "insufficient", "score": 20, "rulesVersion": "r",
                "reviewSuggestion": {"state": "unavailable", "reason": "Brak pomiaru Chromium dla tego materiału."}}
        card = card_view(post)
        self.assertEqual((card["reviewDecision"]["route"], card["reviewDecision"]["completeReason"]), ("insufficient", "media_unexamined"))
        self.assertEqual(card["reviewScore"]["value"], 20)

    def test_measurement_texts_are_human(self):
        three = {"id": "3", "state": "przesłanka", "measurements": [
            {"distancePx": 222, "warningQuote": "x", "viewport": "desktop 1440×900"}, {"distancePx": 864, "warningQuote": "x", "viewport": "phone 390×844"}]}
        self.assertEqual(human_text(three), "ostrzeżenie 864 px poniżej twierdzenia na telefonie")
        four = {"id": "4", "state": "przesłanka", "measurements": [{"px": 11, "dominantPx": 16, "ratio": .69}]}
        self.assertEqual(human_text(four), "ostrzeżenie mniejszą czcionką: 11 px wobec 16 px treści")
        nine = {"id": "9", "state": "przesłanka", "measurements": [{"readability": {"difficult": True, "signals": {"sentenceWords": True}}}]}
        self.assertEqual(human_text(nine), "tekst trudny: długie zdania")


class Rows(unittest.TestCase):
    M2 = {"id": "web:x/y", "module": "M2", "title": "Rachunek IKE -", "status": "new", "revision": 1, "queues": ["all"],
          "pendingReReview": False, "reviewStale": False, "route": "refer", "score": 45, "activeVariant": "rules_1_2",
          "reviewDecision": {"route": "refer", "queueEligible": True, "reasons": []}, "reviewScore": {"value": 45},
          "m2Card": {"firm": {"name": "BANK PEKAO S.A. (BANK …", "brand": "Bank Pekao"}}}

    def test_band_uses_the_module_scale(self):
        row = store.summary_of_case(self.M2, 60, {"m2_card": 30})
        self.assertEqual(row["band"], "moderate")  # above the card threshold: never "weak"
        self.assertEqual(store.summary_of_case(self.M2, 60)["band"], "weak")  # the M1 scale would say weak

    def test_title_firm_names_and_licensed(self):
        row = store.summary_of_case(self.M2, 60, {"m2_card": 30})
        self.assertEqual((row["title"], row["firmShort"], row["firm"]), ("Rachunek IKE", "Bank Pekao", "Bank Pekao"))
        self.assertTrue(row["firmLegal"].startswith("BANK PEKAO S.A."))
        self.assertEqual(store.clean_firm("BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.) iuro Maklerskie PEKAO"),
                         "BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.) Biuro Maklerskie PEKAO")
        self.assertIsNone(row["licensed"])
        m3 = {**self.M2, "id": "web:bank.pl:m3", "module": "M3", "identity": {"licensed": True}}
        self.assertTrue(store.summary_of_case(m3, 60)["licensed"])


if __name__ == "__main__":
    unittest.main()
