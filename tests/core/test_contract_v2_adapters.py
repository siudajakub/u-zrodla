"""Contract v2 step S3: adapter registry, scan steps, lease heartbeat, source state, quota ledger (T8, T16)."""
import importlib.util
import json
import os
import time
import unittest
from unittest.mock import patch

from api import store
from collectors import discovery
from collectors.adapter import Adapter, LeaseLost, validate_adapter_result
from v2_helpers import HttpCase, StateCase, capture

NOW_PATH = {"method": "atom", "observedAt": "2026-11-21T10:00:00+00:00"}
FUTURE = "2999-01-01T00:00:00+00:00"


def video(letter):
    return capture("youtube:" + letter * 11, url=f"https://www.youtube.com/watch?v={letter * 11}",
                   discovery=[dict(NOW_PATH)])


class Stub:
    """Adapter double: records every call and the context it was given."""

    def __init__(self, id, captures=(), sources=None, status="ok", **extra):
        self.id, self.captures, self.status, self.extra = id, list(captures), status, extra
        self.sources = sources if sources is not None else [{"id": id, "name": id, "status": status, "count": len(self.captures)}]
        self.calls, self.contexts, self.crash = 0, [], None

    def __call__(self, ctx):
        self.calls += 1
        self.contexts.append(ctx)
        if self.crash and self.calls == 1:
            raise self.crash
        return {"creators": [], "captures": self.captures, "sources": self.sources, "status": self.status, **self.extra}

    def adapter(self, **kw):
        return Adapter(self.id, self, self.id, **kw)


class ScanCase(StateCase):
    """Full worker path (claim, build, apply) with the heavy collaborators replaced."""

    def setUp(self):
        super().setUp()
        from api import jobs
        self.jobs = jobs
        # No test in this file may reach the network: a YouTube key file on this host would spend real quota.
        if importlib.util.find_spec("collectors.youtube"):
            self.enterContext(patch("collectors.youtube.urlopen", side_effect=AssertionError("network is off in tests")))
        for target, kw in (("api.listen.sample_audio", {"return_value": {"id": "asr", "name": "asr", "status": "empty", "count": 0}}),
                           ("collectors.m2_archive.staged_captures", {"return_value": ([], [], [])}),
                           ("analysis.semantic.suggest", {"return_value": {"status": "unavailable"}})):
            self.enterContext(patch(target, **kw))

    def adapters(self, *stubs, **kw):
        self.enterContext(patch.dict(discovery.ADAPTERS, {s.id: s.adapter(**kw) for s in stubs}, clear=True))

    def run_scan(self, request_id="scan-1"):
        scan, _ = store.create_scan("live", request_id)
        self.jobs.process.call_local(scan["id"])
        return scan["id"]

    def detail(self, key):
        with store.connection() as db:
            return store.scan_detail(db, key)

    def scan_row(self, key):
        with store.connection() as db:
            return db.execute("SELECT * FROM scans WHERE id=?", (key,)).fetchone()

    def source_state(self, id):
        with store.connection() as db:
            return store.source_state(db, id)


class Interrupted(ScanCase):
    def test_t8_worker_killed_midway_resumes_from_unfinished_steps(self):
        first, second = Stub("first", [video("A")]), Stub("second", [video("B")])
        second.crash = SystemExit("worker killed")
        self.adapters(first, second)
        scan, _ = store.create_scan("live", "killed-1")
        key = scan["id"]
        with self.assertRaises(SystemExit):
            self.jobs.process.call_local(key)
        steps = {s["step"]: s["status"] for s in self.detail(key)["steps"]}
        self.assertEqual((steps["discover:first"], steps["discover:second"]), ("done", "running"))
        self.assertEqual(self.detail(key)["status"], "running")
        self.assertEqual((first.calls, second.calls), (1, 1))
        # The first worker is dead: its lease runs out and the journal re-queues the scan.
        with store.connection(True) as db:
            db.execute("UPDATE scans SET lease_until=0 WHERE id=?", (key,))
        queued = []
        with patch.object(self.jobs, "enqueue", queued.append):
            self.jobs.recover()
        self.assertEqual(queued, [key])
        self.jobs.process.call_local(key)
        self.jobs.process.call_local(key)  # a duplicate message changes nothing
        self.assertEqual((first.calls, second.calls), (1, 2), "the finished step must not run again")
        detail = self.detail(key)
        self.assertEqual((detail["status"], detail["attempts"]), ("done", 2))
        self.assertEqual(detail["progress"], {"done": len(detail["steps"]), "total": len(detail["steps"])})
        self.assertEqual([s["attempts"] for s in detail["steps"] if s["step"] == "discover:second"], [2])
        self.assertEqual([s["attempts"] for s in detail["steps"] if s["step"] == "discover:first"], [1])
        done = [e for e in self.events() if e["message"] == "Skan zakończony"]
        self.assertEqual(len(done), 1)
        self.assertEqual((self.versions("youtube:" + "A" * 11), self.versions("youtube:" + "B" * 11)), (1, 1))
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM scan_steps WHERE output IS NOT NULL").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM discoveries").fetchone()[0], 2)
        self.assertEqual(self.source_state("first")["lastScanId"], key)


class Lease(ScanCase):
    def test_heartbeat_extends_the_lease_and_stops_a_run_that_lost_it(self):
        scan, _ = store.create_scan("live", "lease-1")
        key = scan["id"]
        with patch.object(self.jobs, "LEASE", 60):
            self.assertIsNotNone(self.jobs.claim(key, "owner-a"))
        runner = self.jobs.ScanRunner(key, "owner-a")
        with store.connection(True) as db:
            db.execute("UPDATE scans SET lease_until=? WHERE id=?", (time.time() + 1, key))
        runner.heartbeat(True)
        with store.connection() as db:
            self.assertGreater(db.execute("SELECT lease_until FROM scans WHERE id=?", (key,)).fetchone()[0], time.time() + 100)
        with store.connection(True) as db:
            db.execute("UPDATE scans SET owner='owner-b' WHERE id=?", (key,))
        with self.assertRaises(LeaseLost):
            runner.heartbeat(True)

    def test_lost_lease_leaves_no_effects_and_no_failure(self):
        stub = Stub("only", [video("C")])
        self.adapters(stub)
        scan, _ = store.create_scan("live", "lease-2")
        key = scan["id"]
        real = self.jobs.ScanRunner.heartbeat

        def stolen(runner, force=False):
            with store.connection(True) as db:
                db.execute("UPDATE scans SET owner='owner-b' WHERE id=?", (key,))
            return real(runner, True)
        with patch.object(self.jobs.ScanRunner, "heartbeat", stolen):
            self.jobs.process.call_local(key)
        self.assertEqual(self.detail(key)["status"], "running")
        self.assertEqual(self.versions("youtube:" + "C" * 11), 0)
        self.assertEqual([e for e in self.events() if e["message"] == "Skan wymaga ponowienia"], [])


class Validator(StateCase):
    def test_legacy_result_is_kept_whole_but_a_leaked_key_is_not(self):
        legacy = Adapter("old", lambda c: None, legacy=True)
        plain = {"id": "apple-podcasts:1:episode:x", "title": "t"}
        leaked = {"id": "apple-podcasts:2", "discovery": [{"method": "apple_search", "sourceUrl": "https://x/?key=AIzaSECRET"}]}
        result = validate_adapter_result({"captures": [plain, leaked]}, legacy, "2026-11-21T10:00:00+00:00")
        self.assertEqual([c["id"] for c in result["captures"]], [plain["id"]])
        self.assertNotIn("AIzaSECRET", json.dumps(result))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sources"][0]["lastError"]["code"], "adapter_invalid")

    def test_malformed_results_are_reported_not_raised(self):
        adapter = Adapter("bad", lambda c: None)
        for raw in (None, "text", {"captures": "x", "creators": [1], "sources": [{}]}):
            result = validate_adapter_result(raw, adapter, "2026-11-21T10:00:00+00:00")
            self.assertTrue(result["errors"])
            self.assertEqual((result["captures"], result["creators"]), ([], []))
        self.assertEqual(validate_adapter_result({"captures": [capture("youtube:AAAAAAAAAAA", discovery=[{"x": 1}])]}, adapter)["captures"], [])

    def test_exception_in_one_adapter_does_not_fail_the_others(self):
        broken = Stub("broken")
        broken.crash = RuntimeError("zerwane połączenie https://x/?key=AIzaSECRET")
        fine = Stub("fine", [video("D")])
        with patch.dict(discovery.ADAPTERS, {"broken": broken.adapter(), "fine": fine.adapter()}, clear=True):
            result = discovery.discover("live", ())
        self.assertEqual([c["id"] for c in result["captures"]], ["youtube:" + "D" * 11])
        source = next(s for s in result["sources"] if s["id"] == "broken")
        self.assertEqual((source["status"], source["lastError"]["code"]), ("error", "adapter_exception"))
        self.assertNotIn("AIzaSECRET", json.dumps(result))

    def test_second_stage_adapter_sees_the_first_stage_captures(self):
        first, late = Stub("first", [video("E")]), Stub("late")
        with patch.dict(discovery.ADAPTERS, {"first": first.adapter(), "late": late.adapter(after=("first",))}, clear=True):
            discovery.discover("live", ())
        self.assertEqual([c["id"] for c in late.contexts[0].captures], ["youtube:" + "E" * 11])


class SourceHealth(ScanCase):
    def test_needs_key_is_reported_and_does_not_fail_the_scan(self):
        error = {"code": "needs_key", "message": "Brak klucza.", "at": "2026-11-21T10:00:00+00:00", "nextStep": "Ustaw klucz."}
        stub = Stub("keyed", status="needs_key", sources=[{"id": "keyed", "name": "Źródło z kluczem", "status": "needs_key",
                                                           "count": 0, "lastError": error}])
        self.adapters(stub)
        key = self.run_scan()
        self.assertEqual(self.detail(key)["status"], "partial")  # decision of 21 XI: a source without a key is a visible gap
        self.assertIn("Brak klucza.", store.scan_dict(self.scan_row(key)).get("warnings", []))
        state = store.state()
        self.assertEqual(state["sourceHealth"]["keyed"], "needs_key")
        entry = next(s for s in state["sourceState"] if s["sourceId"] == "keyed")
        self.assertEqual((entry["health"], entry["lastError"]["code"], entry["lastError"]["nextStep"]),
                         ("needs_key", "needs_key", "Ustaw klucz."))
        self.assertNotIn("lastSuccessAt", entry)

    def test_error_then_success_keeps_the_last_error_and_records_the_success(self):
        stub = Stub("flaky", status="error", sources=[{"id": "flaky", "name": "Flaky", "status": "error", "count": 0, "error": "HTTP 500"}])
        self.adapters(stub)
        self.run_scan("flaky-1")
        entry = self.source_state("flaky")
        self.assertEqual((entry["health"], entry["lastError"]["message"], entry["consecutiveErrors"]), ("error", "HTTP 500", 1))
        stub.status, stub.sources = "ok", [{"id": "flaky", "name": "Flaky", "status": "ok", "count": 0}]
        self.run_scan("flaky-2")
        entry = self.source_state("flaky")
        self.assertEqual((entry["health"], entry["consecutiveErrors"], entry["lastError"]["message"]), ("ok", 0, "HTTP 500"))
        self.assertIsNotNone(entry["lastSuccessAt"])

    def test_daily_quota_ledger_budgets_the_run_and_blocks_an_exhausted_source(self):
        stub = Stub("metered", [video("F")], quota={"used": 60, "limit": 100, "resetAt": FUTURE})
        with patch.dict(os.environ, {"IW_TEST_DAILY": "100"}):
            self.adapters(stub, daily_units_env="IW_TEST_DAILY")
            self.run_scan("quota-1")
            self.assertEqual(stub.contexts[0].budget, 100)
            self.assertEqual(self.source_state("metered")["quota"]["used"], 60)
            self.run_scan("quota-2")
            self.assertEqual(stub.contexts[1].budget, 40)
            self.assertEqual(self.source_state("metered")["quota"]["used"], 120)
            self.run_scan("quota-3")
        self.assertEqual(stub.calls, 2, "an exhausted source is not called")
        state = store.state()
        self.assertEqual(state["sourceHealth"]["metered"], "quota_exhausted")
        entry = next(s for s in state["sourceState"] if s["sourceId"] == "metered")
        self.assertEqual(entry["health"], "quota_exhausted")
        source = next(s for s in state["sources"] if s["id"] == "metered")
        self.assertEqual((source["status"], source["quota"]["limit"]), ("limit", 100))

    def test_rate_limited_cursor_waits_for_retry_and_then_resumes(self):
        stub = Stub("paged", status="rate_limited", retryAt=FUTURE, resume={"query": "XTB", "pageToken": "abc"},
                    sources=[{"id": "paged", "name": "Paged", "status": "limit", "count": 0,
                              "lastError": {"code": "quotaExceeded", "message": "Limit.", "at": "2026-11-21T10:00:00+00:00", "nextStep": "Czekaj."}}],
                    quota={"used": 100, "limit": 100, "resetAt": FUTURE})
        self.adapters(stub)
        self.run_scan("paged-1")
        self.assertEqual(self.source_state("paged")["resume"]["pageToken"], "abc")
        self.run_scan("paged-2")
        self.assertEqual(stub.calls, 1, "the retry time has not passed")
        self.assertEqual(self.source_state("paged")["resume"]["pageToken"], "abc")
        with store.connection(True) as db:
            body = store.source_state(db, "paged")
            body["retryAt"] = "2000-01-01T00:00:00+00:00"
            db.execute("UPDATE source_state SET body=? WHERE source_id='paged'", (store.dump(body),))
        stub.status, stub.extra, stub.sources = "ok", {}, [{"id": "paged", "name": "Paged", "status": "ok", "count": 0}]
        self.run_scan("paged-3")
        self.assertEqual(stub.calls, 2)
        self.assertEqual(stub.contexts[1].state["resume"], {"query": "XTB", "pageToken": "abc"})
        entry = self.source_state("paged")
        self.assertEqual((entry["health"], entry["resume"]), ("ok", None))


class ScanRoute(HttpCase):
    def test_scan_route_returns_steps_progress_and_404(self):
        from api import jobs
        stub = Stub("routed", [video("G")])
        with patch.dict(discovery.ADAPTERS, {"routed": stub.adapter()}, clear=True), \
             patch("api.listen.sample_audio", return_value={"id": "asr", "name": "asr", "status": "empty", "count": 0}), \
             patch("collectors.m2_archive.staged_captures", return_value=([], [], [])), \
             patch("analysis.semantic.suggest", return_value={"status": "unavailable"}):
            scan, _ = store.create_scan("live", "route-1")
            jobs.process.call_local(scan["id"])
        status, body = self.request("GET", "/v1/scans/" + scan["id"])
        self.assertEqual((status, body["status"]), (200, "done"))
        self.assertEqual([s["step"] for s in body["steps"]], ["discover:routed", "enrich", "analyze", "apply"])
        self.assertEqual(body["progress"], {"done": 4, "total": 4})
        self.assertEqual(body["steps"][0]["summary"]["captures"], 1)
        self.assertEqual(self.request("GET", "/v1/scans/nope")[0], 404)
        status, state = self.request("GET", "/v1/state")
        self.assertEqual((status, state["sourceHealth"]["routed"]), (200, "ok"))


@unittest.skipUnless(importlib.util.find_spec("collectors.youtube"), "adapter B is not present")
class YoutubeEntryPoint(ScanCase):
    def test_on_by_default_in_live_off_when_not_listed_and_never_with_an_injected_fetch(self):
        self.assertIn("youtube", discovery.ADAPTERS)
        env = {k: v for k, v in os.environ.items() if k != "INVESTWATCH_ADAPTERS"}
        with patch.dict(os.environ, env, clear=True):
            self.assertIn("youtube", [a.id for a in discovery.active_adapters("live")])
            self.assertNotIn("youtube", [a.id for a in discovery.active_adapters("live", own_transport=False)])
        with patch.dict(os.environ, {"INVESTWATCH_ADAPTERS": ""}):
            self.assertNotIn("youtube", [a.id for a in discovery.active_adapters("live")])
        self.assertNotIn("youtube", [a.id for a in discovery.active_adapters("replay")])
        self.assertEqual([a.id for a in discovery.active_adapters("replay", ["youtube-replay"])], ["youtube-replay"])

    def test_replay_fixture_of_b_passes_the_validator_without_network(self):
        from collectors.adapter import validate_adapter_result
        result = validate_adapter_result(discovery.ADAPTERS["youtube-replay"].discover(None), discovery.ADAPTERS["youtube-replay"], "2026-11-21T20:00:00+00:00")
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["captures"])
        self.assertTrue(all(c["mode"] == "replay" for c in result["captures"]))

    def test_context_carries_state_budget_and_heartbeat_to_the_adapter(self):
        from collectors import youtube
        seen = []

        def fake(ctx):
            seen.append(ctx)
            ctx.heartbeat()
            return {"creators": [], "captures": [], "status": "ok", "resume": None, "sources": [
                {"id": "youtube", "name": "YouTube", "status": "empty", "count": 0}]}
        with patch.dict(os.environ, {"INVESTWATCH_ADAPTERS": "youtube", "INVESTWATCH_YT_DAILY_UNITS": "500"}), \
             patch.dict(discovery.ADAPTERS, {"youtube": discovery.ADAPTERS["youtube"]}, clear=True), \
             patch.object(youtube, "discover", fake):
            with store.connection(True) as db:
                store.record_adapter(db, "youtube", {"status": "ok", "resume": {"queryIndex": 2}}, "2026-11-21T10:00:00+00:00")
            self.run_scan("yt-ctx")
        ctx = seen[0]
        self.assertEqual((ctx.mode, ctx.state["resume"], ctx.budget), ("live", {"queryIndex": 2}, 500))
        self.assertTrue(callable(ctx.heartbeat))

    def test_missing_key_is_needs_key_without_an_exception(self):
        from collectors import youtube
        real = youtube.discover

        def without_key(ctx):
            # The real adapter, with the key source and the transport replaced: no key file, no request.
            ctx.key_source = lambda: None
            ctx.fetch = lambda url: (_ for _ in ()).throw(AssertionError("request without a key"))
            return real(ctx)
        with patch.dict(os.environ, {"INVESTWATCH_ADAPTERS": "youtube"}), \
             patch.dict(discovery.ADAPTERS, {"youtube": discovery.ADAPTERS["youtube"]}, clear=True), \
             patch.object(youtube, "discover", without_key):
            key = self.run_scan("yt-nokey")
        self.assertEqual(self.detail(key)["status"], "partial")
        state = store.state()
        self.assertEqual(state["sourceHealth"]["youtube"], "needs_key")
        self.assertEqual(next(s for s in state["sourceState"] if s["sourceId"] == "youtube")["health"], "needs_key")


if __name__ == "__main__":
    unittest.main()
