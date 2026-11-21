"""Contract v2 scan flow (T8, T9, T10, T16): restart, reconnect, slash identifiers, adapter contract."""
import asyncio
import json
import sqlite3
import unittest
from unittest.mock import patch
from urllib.parse import quote

from api import server, store
from v2_helpers import HttpCase, StateCase, VIDEO, capture, finding

SLASH = "web:bossa.pl/oferta/doradztwo"


class Restart(StateCase):
    def test_t8_expired_lease_is_recovered_and_finished_once(self):
        from api import jobs
        scan, _ = store.create_scan("replay", "restart-1")
        key = scan["id"]
        self.assertIsNotNone(jobs.claim(key, "owner-a"))
        self.assertIsNone(jobs.claim(key, "owner-b"))
        queued = []
        with patch.object(jobs, "enqueue", queued.append):
            jobs.recover()
        self.assertEqual(queued, [])
        with store.connection(True) as db:
            db.execute("UPDATE scans SET lease_until=0 WHERE id=?", (key,))
        with patch.object(jobs, "enqueue", queued.append):
            jobs.recover()
        self.assertEqual(queued, [key])
        with patch.object(jobs, "build", return_value=([], [], [{"name": "s", "status": "ok", "count": 0}])):
            jobs.process.call_local(key)
            jobs.process.call_local(key)
        with store.connection() as db:
            row = db.execute("SELECT status,attempts FROM scans WHERE id=?", (key,)).fetchone()
            done = [e for e in store.events_since(db, 0, 100) if e["message"] == "Skan zakończony"]
        self.assertEqual((row["status"], row["attempts"], len(done)), ("done", 2, 1))

    def test_t8_step_tables_exist(self):
        with store.connection() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"scan_steps", "source_state", "quota_ledger"} <= tables)


class FakeSocket:
    def __init__(self, after=None):
        self.headers = {"host": "testserver"}
        self.query_params = {} if after is None else {"after": str(after)}
        self.sent, self.closed, self.polls = [], None, 0

    async def accept(self):
        pass

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed = code

    async def receive(self):
        self.polls += 1
        await asyncio.sleep(.01)
        return {"type": "websocket.disconnect"} if self.polls >= 3 else {"type": "websocket.receive"}


class Reconnect(StateCase):
    def listen(self, after):
        ws = FakeSocket(after)
        asyncio.run(server.events(ws))
        return ws

    def test_t9_reconnect_delivers_missed_events_in_order_without_duplicates(self):
        self.put(capture("youtube:AAAAAAAAAAA"))
        first = self.listen(-1)
        self.assertEqual(first.sent[0]["kind"], "ready")
        seen = first.sent[0]["id"]
        self.put(capture("youtube:BBBBBBBBBBB"))
        self.put(capture("youtube:CCCCCCCCCCC"))
        second = self.listen(seen)
        ids = [m["id"] for m in second.sent[1:]]
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids, sorted(set(ids)))
        self.assertTrue(all(i > seen for i in ids))
        self.assertEqual(self.listen(ids[-1]).sent[1:], [])

    def test_t9_cursor_beyond_the_newest_event_announces_reset(self):
        self.put()
        ws = self.listen(10_000)
        self.assertIn("reset", [m["kind"] for m in ws.sent])


class SlashIdentifiers(HttpCase):
    def setUp(self):
        super().setUp()
        cap = capture(SLASH, module="M3", platform="web", url="https://bossa.pl/oferta/doradztwo")
        self.put(cap, module="M3")
        self.path = "/v1/cases/" + quote(SLASH, safe="")

    def test_t10_read_version_and_decision_on_slash_id(self):
        self.assertEqual(self.request("GET", self.path)[0], 200)
        status, version = self.request("GET", self.path + "/versions/1")
        self.assertEqual((status, version["capture"]["id"]), (200, SLASH))
        status, updated = self.request("PATCH", self.path, {"status": "reviewing", "expectedRevision": 1, "note": "Sprawdzić."})
        self.assertEqual((status, updated["revision"]), (200, 2))
        self.assertEqual(self.request("PATCH", self.path, {"status": "closed", "expectedRevision": 1, "note": "Stare."})[0], 409)

    def test_t10_version_list_and_reach_routes(self):
        status, body = self.request("GET", self.path + "/versions")
        self.assertEqual(status, 200)
        self.assertEqual([v["version"] for v in body["versions"]], [1])
        self.assertEqual(self.request("GET", self.path + "/reach")[0], 200)


class AdapterContract(StateCase):
    def test_t16_validator_keeps_good_captures_and_reports_bad_ones(self):
        from collectors.adapter import validate_adapter_result
        good = capture(discovery=[{"method": "atom", "observedAt": "2026-11-21T10:00:00+00:00"}])
        bad_id = capture("not-canonical", discovery=[{"method": "atom"}])
        no_path = capture("youtube:DDDDDDDDDDD")
        secret = capture("youtube:EEEEEEEEEEE", discovery=[{"method": "data_api_search", "sourceUrl": "https://x/?key=AIzaSECRET"}])
        result = validate_adapter_result({"creators": [], "captures": [good, bad_id, no_path, secret], "sources": [], "status": "ok"})
        self.assertEqual([c["id"] for c in result["captures"]], [good["id"]])
        self.assertEqual(len(result["errors"]), 3)
        self.assertNotIn("AIzaSECRET", json.dumps(result))

    def test_t16_rate_limited_result_persists_resume_state(self):
        from collectors.adapter import record_adapter_result
        record_adapter_result("youtube", {"status": "rate_limited", "retryAt": "2026-11-22T08:00:00+00:00",
                                         "resume": {"query": "XTB", "pageToken": "abc"}, "captures": [], "creators": [], "sources": []})
        with store.connection() as db:
            row = db.execute("SELECT body FROM source_state WHERE source_id=?", ("youtube",)).fetchone()
        self.assertEqual(json.loads(row[0])["resume"]["pageToken"], "abc")


if __name__ == "__main__":
    unittest.main()
