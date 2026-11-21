"""M2 social posts and ads enter the Polish M2 queue only when they are about the firm's investment offer (lane H)."""
import unittest

from analysis.engine import analyze, m2_scope
from api import store
from v2_helpers import StateCase


def post(id, text, platform="instagram", **extra):
    return {"id": id, "title": text[:60], "description": text, "module": "M2", "platform": platform, "creatorId": "instagram:xtb",
            "url": "https://example.org/" + id, "publishedAt": "2026-11-01T10:00:00+00:00", "observedAt": "2026-11-21T10:00:00+00:00",
            "provenance": {"sourceUrl": "https://example.org", "mode": "replay", "scope": "vendor_instagram_caption"}, "mode": "replay",
            "origin": "replay", "firmRelation": {"firm": "xtb", "label": "XTB", "role": "author"},
            "textSignals": {"benefitClaim": False, "riskWarningInText": False}, **extra}


BASKET = post("instagram:basket", "Polska vs Chorwacja już 27 listopada w Gliwicach! Przed nami kolejne koszykarskie emocje.")
SLOVAK = post("facebook:ad-sk", "Viac ako 1 000 000 investorov. Začnite investovať s XTB", platform="facebook")
OFFER = post("instagram:etf", "Zacznij inwestować w ETF na rachunku maklerskim XTB. Kapitał jest zagrożony.")


class Scope(StateCase):
    def test_scope_codes(self):
        self.assertEqual(m2_scope(BASKET)["code"], "not_investment")
        self.assertEqual(m2_scope(SLOVAK)["code"], "other_market")
        self.assertEqual(m2_scope(OFFER)["code"], "in_scope")
        self.assertEqual(m2_scope({**OFFER, "firmRelation": None})["code"], "no_registry_firm")

    def test_out_of_scope_posts_are_no_signal_and_only_in_all(self):
        for cap in (BASKET, SLOVAK, OFFER):
            self.scan([(cap, {**analyze(cap), "semantic": {"status": "unavailable"}})], "replay")
        queues = {k: self.case(k)["queues"] for k in (BASKET["id"], SLOVAK["id"], OFFER["id"])}
        self.assertEqual(queues[BASKET["id"]], ["all"])
        self.assertEqual(queues[SLOVAK["id"]], ["all"])
        self.assertIn("offersM2", queues[OFFER["id"]])
        self.assertEqual(self.case(BASKET["id"])["route"], "no_signal")
        self.assertEqual(self.case(SLOVAK["id"])["m2Scope"]["label"], "inny rynek lub język: poza kolejkami PL")


if __name__ == "__main__":
    unittest.main()
