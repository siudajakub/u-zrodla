"""Contract v2 steps S4, S6, S7: queues, variant switch, thresholds, recompute, schema views. Properties, not scores."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from analysis import engine
from analysis.engine import analyze
from analysis.semantic import review_suggestion
from api import enrich, store
from v2_helpers import HttpCase, StateCase, VIDEO, capture

DECLARED = "Partnerem odcinka jest XTB."
UNMARKED = "Zacznij z XTB: https://link-pso.xtb.com/pso/abc Kod KANAL przy rejestracji daje kurs."
OTHER = "youtube:BBBBBBBBBBB"


def evaluate(cap):
    found = analyze(cap)
    found["semantic"] = {"status": "unavailable"}
    found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
    return cap, found


def video(id, description, **extra):
    return capture(id, description=description, url="https://www.youtube.com/watch?v=" + id[8:], **extra)


class Both(StateCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("network is off in tests")))
        self.enterContext(patch.object(engine, "ACTIVE_VARIANT", "rules_1_2"))  # jobs.build sets it per scan
        self.scan([evaluate(video(VIDEO, DECLARED)), evaluate(video(OTHER, UNMARKED))])

    def queue(self, name):
        with store.connection() as db:
            return [i["id"] for i in store.queue_list(db, name)["items"]]

    def switch(self, variant):
        with store.connection(True) as db:
            current = store.qualification_current(db)
            return store.set_qualification(db, variant, current["id"], "Test.", "q-v1", "J")[0]


class Variants(Both):
    def test_default_variant_is_rules_and_the_review_queue_follows_it(self):
        with store.connection() as db:
            self.assertEqual(store.active_variant(db), "rules_1_2")
        self.assertEqual(self.queue("review"), [VIDEO])  # rules_1_2 refers the declaration, not the unmarked link

    def test_switching_the_variant_changes_the_queue_and_switching_back_restores_it(self):
        self.switch("qual_d")
        self.assertEqual(self.queue("review"), [OTHER])  # qual_d refers the unmarked collaboration
        self.assertIn(VIDEO, self.queue("adRegister"))
        with store.connection(True) as db:
            current = store.qualification_current(db)
            store.restore_qualification(db, 1, current["id"], "Cofnięcie.")
        self.assertEqual(self.queue("review"), [VIDEO])
        with store.connection() as db:
            self.assertEqual([h["variant"] for h in store.qualification_history(db)], ["rules_1_2", "qual_d", "rules_1_2"])

    def test_threshold_is_per_variant_with_history_and_decides_eligibility(self):
        self.switch("qual_d")
        with store.connection(True) as db:
            cur = store.threshold_current(db, "qual_d")
            store.set_threshold(db, "qual_d", 100, "Zaostrzenie.", cur["id"])
            self.assertEqual(store.threshold_value(db, "rules_1_2"), 60)
        self.assertEqual(self.queue("review"), [])
        with store.connection(True) as db:
            history = store.threshold_history(db, "qual_d")
            store.restore_threshold(db, history[0]["id"], history[-1]["id"], "Cofnięcie.")
        self.assertEqual(self.queue("review"), [OTHER])

    def test_high_risk_for_qual_d_fires_once_on_the_transition(self):
        self.switch("qual_d")
        before = len(self.events("high_risk"))
        third = video("youtube:CCCCCCCCCCC", UNMARKED)
        with patch.object(engine, "ACTIVE_VARIANT", "qual_d"):
            self.scan([evaluate(third)])
            self.scan([evaluate(third)])
            self.scan([evaluate(third)], mode="live")
        self.assertEqual(len(self.events("high_risk")) - before, 1)

    def test_default_scan_leaves_the_variant_alone_and_unmarked_stays_out_of_rules_high_risk(self):
        self.assertEqual([e["ref"] for e in self.events("high_risk")], [VIDEO])

    def test_unknown_variant_and_missing_approval_are_refused_and_model_is_unavailable(self):
        with store.connection(True) as db:
            current = store.qualification_current(db)
            for args in (("zly", current["id"], "", "q", "J"), ("qual_d", current["id"], "", None, None),
                         ("qual_d_model", current["id"], "", "q", "J")):
                with self.assertRaises(store.Invalid):
                    store.set_qualification(db, *args)
            with self.assertRaises(store.Conflict):
                store.set_qualification(db, "qual_d", current["id"] + 5, "", "q", "J")


class Recompute(Both):
    def test_recompute_updates_analysis_without_touching_decisions_or_versions(self):
        from api import jobs
        with store.connection(True) as db:
            db.execute("UPDATE cases SET status='closed',revision=revision+1 WHERE id=?", (VIDEO,))
            store.record(db, VIDEO, "decision", "Zamknięte.", {"status": "closed", "version": 1, "route": "refer"})
            db.execute("UPDATE qualification_results SET body='{}'")  # a case analysed before the shadow existed
        self.switch("qual_d")
        scan, _ = store.create_scan("recompute", "rc-1")
        jobs.process.call_local(scan["id"])
        with store.connection() as db:
            detail = store.scan_detail(db, scan["id"])
        self.assertEqual(detail["status"], "done")
        found = self.case(VIDEO)
        self.assertEqual((found["status"], found["lastDecision"]["note"]), ("closed", "Zamknięte."))
        self.assertEqual(self.versions(VIDEO), 1)
        self.assertEqual(found["analysisVersion"]["variant"], "qual_d")
        self.assertTrue(found["reviewDecision"]["route"])
        self.assertTrue(found["reviewStale"], "rules_1_2 referred it, qual_d registers it: the decision was taken on another route")
        # the observation layer is not replayed
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM discoveries").fetchone()[0], 0)


class Views(Both, HttpCase):
    def test_schema_views_and_compact_state(self):
        self.put_text = None
        old = store.state(1)
        new = store.state(2)
        case1 = next(c for c in old["findings"] if c["id"] == OTHER)
        case2 = next(c for c in new["findings"] if c["id"] == OTHER)
        self.assertNotIsInstance(case1.get("coverage"), dict)  # the old desk keeps working
        self.assertIn("coverageV2", case1)
        self.assertIsInstance(case2["coverage"], dict)
        self.assertTrue(case2["coverage"]["label"])
        self.assertTrue(all("role" in e for e in case2["evidence"]))
        compact = store.state(2, True)
        self.assertTrue(all("history" not in c and "evidence" not in c for c in compact["findings"]))
        self.assertEqual(compact["queues"], new["queues"])
        self.assertEqual(new["schema"]["views"], [1, 2])
        self.assertEqual(new["qualification"]["variant"], "rules_1_2")

    def test_queue_routes_filters_cursor_and_counters(self):
        status, page = self.request("GET", "/v1/queues/all?limit=1")
        self.assertEqual((status, len(page["items"]), page["total"]), (200, 1, 2))
        status, second = self.request("GET", "/v1/queues/all?limit=1&cursor=" + page["nextCursor"])
        self.assertEqual((status, second["nextCursor"]), (200, None))
        self.assertNotEqual(page["items"][0]["id"], second["items"][0]["id"])
        self.assertEqual(self.request("GET", "/v1/queues/nope")[0], 404)
        self.assertEqual(self.request("GET", "/v1/queues/all?module=M3")[1]["total"], 0)
        self.assertEqual(self.request("GET", "/v1/queues/all?q=" + "Tytu")[1]["total"], 2)
        self.assertEqual(self.request("GET", "/v1/queues/review")[1]["counts"]["review"], 1)
        status, state = self.request("GET", "/v1/state?compact=1&schema=2")
        self.assertEqual((status, state["queues"]["all"]), (200, 2))

    def test_http_settings_routes_and_stale_decision_body(self):
        with patch("api.jobs.enqueue"):
            status, current = self.request("GET", "/v1/qualification")
            self.assertEqual((status, current["variant"]), (200, "rules_1_2"))
            body = {"variant": "qual_d", "expectedId": current["id"], "note": "Bramka."}
            self.assertEqual(self.request("PUT", "/v1/qualification", body)[0], 422)
            status, changed = self.request("PUT", "/v1/qualification", {**body, "validationRef": "q-v1", "approvedBy": "J"})
            self.assertEqual((status, changed["variant"]), (200, "qual_d"))
            self.assertEqual(self.request("PUT", "/v1/qualification", {**body, "validationRef": "q-v1", "approvedBy": "J"})[0], 409)
            with store.connection() as db:
                scans = db.execute("SELECT mode FROM scans").fetchall()
            self.assertEqual([r[0] for r in scans], ["recompute"])
        status, case = self.request("GET", "/v1/cases/" + OTHER.replace(":", "%3A"))
        self.assertEqual(status, 200)
        status, stale = self.request("PATCH", "/v1/cases/" + OTHER.replace(":", "%3A"),
                                     {"status": "closed", "expectedRevision": case["revision"], "reviewedVersion": 7, "note": "Zamknięcie."})
        self.assertEqual((status, stale["current"]["version"]), (409, 1))


class Youtube(StateCase):
    def test_default_queries_cover_the_new_topics(self):
        from collectors import youtube
        queries = {q for _, q, _ in youtube.QUERIES}
        for phrase in ("kryptowaluty", "bitcoin", "analiza techniczna", "forex", "złoto srebro inwestowanie",
                       "kod polecający giełda kryptowalut"):
            self.assertIn(phrase, queries)

    def test_media_order_puts_relation_evidence_first_then_reach(self):
        quiet = video("youtube:DDDDDDDDDDD", "Zwykły opis. Rozmowa o XTB.", mediaCoverage=None, reach={"metrics": {"viewCount": {"value": 9_000_000, "state": "observed"}}})
        linked_small = video("youtube:EEEEEEEEEEE", UNMARKED, mediaCoverage=None, reach={"metrics": {"viewCount": {"value": 10, "state": "observed"}}})
        linked_big = video("youtube:FFFFFFFFFFF", UNMARKED, mediaCoverage=None, reach={"metrics": {"viewCount": {"value": 5_000, "state": "observed"}}})
        seen = []

        def fake(cap, ctx=None, **kwargs):
            seen.append(cap["id"])
            return {"status": "no_transcript", "segments": [], "frames": [], "mediaCoverage": {
                "transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None, "reason": "test"},
                "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}
        with TemporaryCache(), patch("collectors.media.enrich", fake), patch("subprocess.run", side_effect=AssertionError("off")):
            enrich.enrich_media([quiet, linked_small, linked_big], "live")
        self.assertEqual(seen, ["youtube:FFFFFFFFFFF", "youtube:EEEEEEEEEEE", "youtube:DDDDDDDDDDD"])
        self.assertEqual(enrich._int("INVESTWATCH_MEDIA_PER_SCAN", 25), 25)


class TemporaryCache:
    def __enter__(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.patch = patch.dict(os.environ, {"INVESTWATCH_MEDIA_CACHE": self.dir.name})
        self.patch.start()

    def __exit__(self, *exc):
        self.patch.stop()
        self.dir.cleanup()


if __name__ == "__main__":
    unittest.main()
