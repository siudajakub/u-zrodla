"""Calibration of M2 and M3 in the API (lane H): labelled sets, module thresholds, series, queue effect. No network, no browser."""
import unittest

from api import calibration_modules as modules, store
from v2_helpers import HttpCase


class ModuleCalibration(HttpCase):
    def setUp(self):
        super().setUp()
        modules.compare("M2", 30)  # warm the cached archive reads (about 4 s each) so a request stays within the client timeout
        modules.compare("M3", 60)

    def test_m2_matches_the_lane_numbers_and_the_curve_moves(self):
        _, at30 = self.request("GET", "/v1/calibration?module=M2&threshold=30")
        self.assertEqual([at30[k] for k in ("tp", "fp", "tn", "fn")], [9, 1, 12, 3])
        self.assertEqual(at30["n"], 25)
        self.assertEqual(at30["labelers"], "1 agent, etykiety przed regułami")
        self.assertEqual(at30["independentUnits"], {"firms": 11})
        self.assertTrue(all(e["firm"] and e["url"] for e in at30["errors"]))
        _, at50 = self.request("GET", "/v1/calibration?module=M2&threshold=50")
        self.assertEqual([at50[k] for k in ("tp", "fp", "fn")], [7, 0, 5])
        self.assertNotEqual(at30["cost"], at50["cost"])

    def test_series_in_one_call_and_m3_views(self):
        _, body = self.request("GET", "/v1/calibration?module=M2&series=1")
        self.assertEqual([p["threshold"] for p in body["series"]], list(range(20, 100, 5)))
        self.assertGreater(len({p["fn"] for p in body["series"]}), 2)
        _, m3 = self.request("GET", "/v1/calibration?module=M3&threshold=60&view=refer_or_complete&series=1")
        self.assertEqual((m3["n"], m3["tp"]), (31, 1))
        self.assertEqual(set(m3["views"]), {"refer", "refer_or_complete"})
        self.assertEqual(self.request("GET", "/v1/calibration?module=M9")[0], 422)

    def test_module_threshold_is_its_own_entry_with_history_and_restore(self):
        _, entry = self.request("GET", "/v1/threshold?variant=m2_card")
        self.assertEqual(entry["value"], 30)
        status, saved = self.request("PUT", "/v1/threshold", {"variant": "m2_card", "value": 50, "expectedId": entry["id"], "note": "test"})
        self.assertEqual(status, 200)
        _, again = self.request("PUT", "/v1/threshold", {"variant": "m2_card", "value": 40, "expectedId": saved["id"]})
        _, history = self.request("GET", "/v1/threshold/history?variant=m2_card")
        self.assertEqual([h["value"] for h in history["items"]], [50, 40])
        status, restored = self.request("POST", "/v1/threshold/restore", {"id": saved["id"], "expectedId": again["id"], "note": ""})
        self.assertEqual((status, restored["value"]), (200, 50))
        self.assertEqual(self.request("GET", "/v1/calibration?module=M2")[1]["storedThreshold"], 50)

    def test_module_threshold_filters_the_review_queue_of_that_module_only(self):
        with store.connection(True) as db:
            store.set_threshold(db, "m2_card", 80, "", 0)
        with store.connection() as db:
            self.assertEqual(store.threshold_value(db, "qual_d"), 60)
            self.assertEqual(store.threshold_value(db, "m2_card"), 80)
            effect = store.module_queue_effect(db, "M2", 30)
        self.assertEqual(effect["storedThreshold"], 80)

    def test_m2_case_enters_and_leaves_the_review_queue_with_the_card_threshold(self):
        from v2_helpers import capture
        cap = capture("web:example.pl/oferta", module="M2", platform="web", origin="replay", mode="replay",
                      url="https://example.pl/oferta", mediaCoverage=None)
        decision = {"route": "refer", "reason": "x", "reasons": [], "queueEligible": True, "decidedBy": "rules", "version": "t", "moments": []}
        from analysis import engine
        stamped = {}
        engine._stamp(stamped, "M2")
        self.put(cap, module="M2", score=45, reviewDecision=decision, origin="replay", **stamped, rulesVersion=engine.M2_RULES,
                 reviewScore={"state": "computed", "value": 45, "scale": "0-100", "components": [{"id": "3", "points": 35}]})
        with store.connection() as db:
            at30 = store.module_queue_effect(db, "M2", 30)
            at50 = store.module_queue_effect(db, "M2", 50)
        self.assertEqual((at30["reviewQueueAtThreshold"], at50["reviewQueueAtThreshold"], at50["lost"]),
                         (1, 0, ["web:example.pl/oferta"]))


if __name__ == "__main__":
    unittest.main()
