"""New source evidence triggers a high_risk event. Re-reading it keeps the same case and audit history."""
import json
import unittest

from websockets.sync.client import connect

from api import jobs, store
from collectors.m2_market import market_captures
from v2_helpers import HttpCase


ALERT_CASE = "web:www.bdm.pl/rachunek-emerytalny"


class ScanAlerts(HttpCase):
    def fire(self):
        captures, creators, sources = market_captures()
        saved = next(cap for cap in captures if cap["id"] == ALERT_CASE)
        with store.connection(True) as db:
            return store.apply_scan(db, [jobs.evaluate(saved)], creators, sources, "replay")

    def listen(self):
        with store.connection() as db:
            after = db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0]
        sock = self.enterContext(connect(self.base.replace("http", "ws") + f"/v1/events?after={after}"))
        self.assertEqual(json.loads(sock.recv(timeout=3))["kind"], "ready")
        return sock

    @staticmethod
    def drain(sock, wait=2.0):
        out = []
        while True:
            try:
                out.append(json.loads(sock.recv(timeout=wait)))
            except TimeoutError:
                return out

    def test_two_sessions_see_one_high_risk_and_a_repeat_adds_none(self):
        first, second = self.listen(), self.listen()
        self.fire()
        for sock in (first, second):
            alerts = [e for e in self.drain(sock) if e["kind"] == "high_risk"]
            self.assertEqual([e["ref"] for e in alerts], [ALERT_CASE])
        self.fire()  # the same saved page: nothing new
        self.assertEqual(len(self.events("high_risk")), 1)
        self.assertEqual([e for e in self.drain(first, 1.0) if e["kind"] == "high_risk"], [])

    def test_no_reset_route_can_delete_the_real_case_history(self):
        self.fire()
        self.assertEqual(self.request("POST", "/v1/demo/alert/reset")[0], 405)
        self.assertEqual(self.request("POST", "/v1/scans", {"mode":"replay", "requestId":"demo", "adapters":["demo-alert"]})[0], 422)
        self.assertEqual(self.versions(ALERT_CASE), 1)
        self.assertEqual(len(self.events("high_risk")), 1)
        self.assertIn("review", self.case(ALERT_CASE)["queues"])


if __name__ == "__main__":
    unittest.main()
