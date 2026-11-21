"""The scripted high_risk alert of the demo (lane H): one real saved M2 page, no live scan, exactly one event, resettable."""
import json
import unittest

from websockets.sync.client import connect

from api import jobs, store
from collectors.discovery import discover
from v2_helpers import HttpCase


class DemoAlert(HttpCase):
    def fire(self):
        found = discover("replay", (), only=["demo-alert"])
        pairs = [jobs.evaluate(cap) for cap in found["captures"]]
        self.assertEqual(len(pairs), 1)
        with store.connection(True) as db:
            return store.apply_scan(db, pairs, found["creators"], found["sources"], "replay")

    def listen(self):
        with store.connection() as db:
            after = db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0]
        sock = connect(self.base.replace("http", "ws") + f"/v1/events?after={after}", legacy=True) if False else connect(self.base.replace("http", "ws") + f"/v1/events?after={after}")
        self.addCleanup(sock.close)
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
            self.assertEqual([e["ref"] for e in alerts], [store.DEMO_ALERT_CASE])
        self.fire()  # the same saved page: nothing new
        self.assertEqual(len(self.events("high_risk")), 1)
        self.assertEqual([e for e in self.drain(first, 1.0) if e["kind"] == "high_risk"], [])

    def test_reset_is_idempotent_and_arms_the_alert_again(self):
        self.assertTrue(self.request("GET", "/v1/demo/alert")[1]["armed"])
        self.fire()
        self.assertFalse(self.request("GET", "/v1/demo/alert")[1]["armed"])
        _, reset = self.request("POST", "/v1/demo/alert/reset")
        self.assertEqual((reset["removed"], reset["armed"]), (True, True))
        self.assertEqual(self.request("POST", "/v1/demo/alert/reset")[1]["removed"], False)
        self.fire()
        self.assertEqual(len(self.events("high_risk")), 2)
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cases WHERE id=?", (store.DEMO_ALERT_CASE,)).fetchone()[0], 1)

    def test_the_adapter_loads_one_real_m2_page(self):
        found = discover("replay", (), only=["demo-alert"])
        self.assertEqual([c["id"] for c in found["captures"]], [store.DEMO_ALERT_CASE])
        self.assertEqual(found["captures"][0]["module"], "M2")


if __name__ == "__main__":
    unittest.main()
