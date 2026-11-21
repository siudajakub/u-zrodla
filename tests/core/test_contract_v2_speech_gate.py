"""Speech gate and media backlog (decision of the product owner): properties, not scores.

A video reaches "Co wymaga sprawdzenia" only after description and speech were examined, or when the transcript is
permanently unobtainable. A suspicion from the description alone waits in `incomplete` as transcript_pending and
raises no high_risk. `incomplete` holds only material with a signal. The `enrich` scan fetches the backlog without
any discovery adapter and without YouTube Data API quota.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from analysis import engine
from analysis.engine import analyze, permanent_gap, transcript_phase
from analysis.semantic import review_suggestion
from api import enrich, jobs, store
from v2_helpers import NO_CAPTIONS, StateCase, VIDEO, capture

UNMARKED = "Zacznij z XTB: https://link-pso.xtb.com/pso/abc Kod KANAL przy rejestracji daje kurs."
DECLARED = "Partnerem odcinka jest XTB."
NEUTRAL = "Na przykładzie XTB pokazuję, czym jest zlecenie limit."
PLAIN = "Rozmowa o cierpliwości i kosztach funduszy."
SPEECH = [{"start": 10.0, "end": 14.0, "text": "Dzisiaj o ETF-ach i cierpliwości", "method": "auto_captions", "language": "pl", "windowId": "w0"}]
LINK_CALL = [{"start": 60.0, "end": 64.0, "text": "link w opisie, zerknijcie", "method": "auto_captions", "language": "pl", "windowId": "w0"}]
DISCLOSURE = [{"start": 5.0, "end": 9.0, "text": "Ten film powstał we współpracy z firmą XTB.", "method": "auto_captions", "language": "pl", "windowId": "w0"}]
FULL = {"transcript": {"state": "full", "source": "auto_captions", "windows": [{"start": 0, "end": 900}], "durationSec": 900, "reason": None},
        "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}


def evaluate(cap, previous=None):
    found = analyze(cap)
    found["semantic"] = {"status": "unavailable"}
    found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
    return cap, found


class NoNetwork(StateCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("network is off in tests")))
        self.enterContext(patch("collectors.media.urlopen", side_effect=AssertionError("network is off in tests")))

    def queue(self, name, key=VIDEO):
        with store.connection() as db:
            return key in [i["id"] for i in store.queue_list(db, name)["items"]]

    def activate(self, variant):
        with store.connection(True) as db:
            current = store.qualification_current(db)
            store.set_qualification(db, variant, current["id"], "Test.", "q-v1", "J")


class Phases(unittest.TestCase):
    def test_transcript_phase_separates_pending_from_permanent(self):
        self.assertEqual(transcript_phase(capture(mediaCoverage=None))["state"], "pending")
        self.assertEqual(transcript_phase(capture())["state"], "unavailable")
        self.assertEqual(transcript_phase(capture(segments=SPEECH, mediaCoverage=FULL))["state"], "full")
        for reason in ("rate_limited: 429", "timeout: limit", "error: yt-dlp", "limit filmów na skan"):
            cover = {"transcript": {"state": "unavailable", "reason": reason}}
            self.assertEqual(transcript_phase(capture(mediaCoverage=cover))["state"], "pending", reason)
        for reason in ("private: film prywatny", "unavailable: usunięty", "Brak napisów po polsku; ASR nie został zażądany"):
            self.assertTrue(permanent_gap(reason), reason)
        self.assertIsNone(transcript_phase({"id": "web:x", "module": "M1"}))


class Gate(NoNetwork):
    def test_refer_from_the_description_alone_waits_as_transcript_pending(self):
        found = analyze(capture(description=UNMARKED, mediaCoverage=None))
        decision = found["reviewDecision"]
        self.assertEqual((decision["route"], decision["completeReason"], decision["queueEligible"]), ("complete", "transcript_pending", False))
        self.assertEqual(found["variants"]["qual_d"]["gated"], "transcript_pending")
        self.assertEqual(found["coverage"]["modalities"]["transcript"]["state"], "pending")
        self.assertTrue(decision["reasons"] and decision["moments"], "the suspicion stays readable for the analyst")

    def test_refer_after_the_speech_was_examined_or_is_unobtainable(self):
        examined = analyze(capture(description=UNMARKED, segments=SPEECH, mediaCoverage=FULL))["reviewDecision"]
        self.assertEqual((examined["route"], examined["speechBasis"]), ("refer", "examined"))
        gone = analyze(capture(description=UNMARKED))["reviewDecision"]
        self.assertEqual((gone["route"], gone["speechBasis"]), ("refer", "unavailable"))
        self.assertTrue(any("nie da się uzyskać" in r for r in gone["reasons"]), "explicit reason: transcript unobtainable")
        self.assertLessEqual(len(gone["reasons"]), 5)

    def test_disclosure_found_in_speech_removes_the_suspicion(self):
        found = analyze(capture(description=UNMARKED, segments=DISCLOSURE, mediaCoverage=FULL))
        self.assertEqual(found["reviewDecision"]["route"], "no_signal")

    def test_queues_and_high_risk_follow_the_gate_in_both_variants(self):
        pending = capture("youtube:PPPPPPPPPPP", description=UNMARKED, mediaCoverage=None, url="https://www.youtube.com/watch?v=PPPPPPPPPPP")
        rules = capture("youtube:RRRRRRRRRRR", description=DECLARED, mediaCoverage=None, url="https://www.youtube.com/watch?v=RRRRRRRRRRR")
        self.scan([evaluate(pending), evaluate(rules)])
        self.assertTrue(self.queue("incomplete", rules["id"]))
        self.assertEqual(analyze(rules)["variants"]["rules_1_2"]["gated"], "transcript_pending")
        for key in (pending["id"], rules["id"]):
            self.assertFalse(self.queue("review", key), key)
        self.assertEqual(self.events("high_risk"), [], "a suspicion without the speech raises no high_risk")
        self.activate("qual_d")
        self.scan([evaluate(pending)])
        self.assertFalse(self.queue("review", pending["id"]))
        self.assertTrue(self.queue("incomplete", pending["id"]))
        self.assertEqual(self.events("high_risk"), [])

    def test_the_transcript_arrives_and_releases_review_and_high_risk(self):
        cap = capture(description=UNMARKED, mediaCoverage=None)
        self.scan([evaluate(cap)])
        self.assertFalse(self.queue("review"))
        examined = {**cap, "segments": SPEECH, "mediaCoverage": FULL}
        self.scan([evaluate(examined)])
        self.activate("qual_d")
        with patch.object(engine, "ACTIVE_VARIANT", "qual_d"):
            self.scan([evaluate(examined)])
        self.assertTrue(self.queue("review"))
        self.assertTrue(self.queue("review") and not self.queue("incomplete"))
        self.assertEqual(self.case()["versions"][-1]["changeKind"], "evidence")

    def test_rules_high_risk_fires_when_the_gate_is_released_without_a_new_version(self):
        cap = capture(description=DECLARED, mediaCoverage=None)
        self.scan([evaluate(cap)])
        self.assertEqual(self.events("high_risk"), [])
        gone = {**cap, "mediaCoverage": NO_CAPTIONS}  # captions turned out not to exist: same content, gate released
        self.scan([evaluate(gone)])
        self.assertEqual(self.versions(), 1)
        self.assertEqual(len(self.events("high_risk")), 1)
        self.scan([evaluate(gone)])
        self.assertEqual(len(self.events("high_risk")), 1)


class Incomplete(NoNetwork):
    def test_incomplete_holds_only_material_with_a_signal(self):
        quiet = capture("youtube:QQQQQQQQQQQ", description=PLAIN, mediaCoverage=None, url="https://www.youtube.com/watch?v=QQQQQQQQQQQ")
        firm = capture("youtube:FFFFFFFFFFF", description=NEUTRAL, mediaCoverage=None, url="https://www.youtube.com/watch?v=FFFFFFFFFFF")
        suspect = capture("youtube:SSSSSSSSSSS", description=UNMARKED, mediaCoverage=None, url="https://www.youtube.com/watch?v=SSSSSSSSSSS")
        self.scan([evaluate(quiet), evaluate(firm), evaluate(suspect)])
        self.activate("qual_d")
        self.assertEqual(analyze(quiet)["reviewDecision"]["route"], "no_signal")
        self.assertFalse(self.queue("incomplete", quiet["id"]), "no signal: stays out of incomplete")
        self.assertTrue(self.queue("all", quiet["id"]))
        self.assertEqual(self.case(quiet["id"])["coverage"]["modalities"]["transcript"]["state"], "pending",
                         "no_signal keeps the coverage 'speech not examined'")
        self.assertTrue(self.queue("incomplete", suspect["id"]))
        self.assertEqual(self.queue("incomplete", firm["id"]), analyze(firm)["reviewDecision"]["route"] in ("complete", "insufficient"))

    def test_blocked_coverage_alone_does_not_make_a_case_incomplete(self):
        cap = capture(description=PLAIN, mediaCoverage=None)
        self.scan([evaluate(cap)])
        self.assertTrue(self.case()["coverage"]["blocksConclusion"])
        self.assertFalse(self.queue("incomplete"))


class MediaBacklog(NoNetwork):
    def setUp(self):
        super().setUp()
        self.cache = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.cache, ignore_errors=True))
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_MEDIA_CACHE": self.cache}))
        self.calls = []

    def video(self, letter, text, **extra):
        vid = letter * 11
        return capture(f"youtube:{vid}", description=text, url=f"https://www.youtube.com/watch?v={vid}", **{"mediaCoverage": None, **extra})

    def fake(self, segments=SPEECH, status="ok", error=None, duration=900):
        def enrich_one(cap, ctx=None, **kwargs):
            self.calls.append((cap["id"], kwargs.get("frames_at")))
            frames = [{"id": f"frame-{cap['id'][8:]}-{int(t)}", "kind": "frame", "time": t, "method": "storyboard", "sha256": "a" * 64,
                       "deepLink": f"{cap['url']}&t={int(t)}s", "path": ".runtime/x.jpg", "available": True} for t in kwargs.get("frames_at") or []]
            if error:
                return {"status": error, "segments": [], "frames": [], "error": {"status": error, "reason": "x"}, "stats": {"bytes": 0, "requests": 1},
                        "mediaCoverage": {"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                                         "reason": f"{error}: x"}, "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}
            cover = {**FULL, "transcript": {**FULL["transcript"], "durationSec": duration}} if segments else {
                **NO_CAPTIONS, "transcript": {**NO_CAPTIONS["transcript"], "durationSec": duration}}
            cover["frames"] = {"state": "selected_moments" if frames else "not_collected", "moments": [f["time"] for f in frames], "intervalSec": None}
            return {"status": status, "segments": [dict(s) for s in segments], "frames": frames, "mediaCoverage": cover,
                    "stats": {"bytes": 1000, "requests": 2}}
        return patch("collectors.media.enrich", enrich_one)

    def test_every_signal_video_is_a_target_relation_first_and_no_signal_is_not(self):
        caps = [self.video("A", PLAIN), self.video("B", NEUTRAL), self.video("C", UNMARKED)]
        with self.fake():
            out, summary = enrich.enrich_media(caps, "live")
        fetched = [c for c, _ in self.calls if _ is None]
        self.assertEqual(fetched[0], "youtube:" + "C" * 11, "relation evidence before a firm mention")
        self.assertIn("youtube:" + "B" * 11, fetched)
        self.assertNotIn("youtube:" + "A" * 11, fetched)
        self.assertEqual(summary["noSignal"], 1)
        self.assertNotIn("segments", out[0])

    def test_time_budget_defers_the_rest_to_the_next_scan(self):
        caps = [self.video(c, UNMARKED) for c in "CDEF"]
        ticks = iter(range(0, 10_000, 400))  # every clock read advances 400 s; the budget is 600 s
        with patch.dict(os.environ, {"INVESTWATCH_MEDIA_SCAN_SECONDS": "600", "INVESTWATCH_MEDIA_PER_SCAN": "99"}), self.fake():
            out, summary = enrich.enrich_media(caps, "live", clock=lambda: next(ticks))
        self.assertLess(len([c for c in self.calls if c[1] is None]), 4)
        self.assertGreater(summary["deferred"], 0)
        pending = [c for c in out if c["mediaCoverage"]["transcript"]["state"] == "pending"]
        self.assertEqual(len(pending), summary["deferred"])

    def test_a_rate_limit_stops_the_run_and_keeps_the_rest_pending(self):
        caps = [self.video(c, UNMARKED) for c in "CDE"]
        with self.fake(error="rate_limited"):
            out, summary = enrich.enrich_media(caps, "live")
        self.assertEqual(len(self.calls), 1, "no further request after a 429")
        self.assertEqual(summary["blocked"], "rate_limited")
        self.assertTrue(all(transcript_phase(c)["state"] == "pending" for c in out))

    def test_transient_failure_is_retried_and_the_third_one_is_final(self):
        cap = self.video("C", UNMARKED)
        with self.fake(error="error"):
            out, _ = enrich.enrich_media([cap], "live", known={})
            self.assertEqual(transcript_phase(out[0])["state"], "pending")
            out, _ = enrich.enrich_media([cap], "live", known={cap["id"]: {"attempts": 2, "state": "failed"}})
        self.assertEqual(transcript_phase(out[0])["state"], "unavailable")
        self.assertEqual(analyze(out[0])["reviewDecision"]["route"], "refer")

    def test_frames_only_for_a_video_that_stays_refer_at_the_link_call_else_begin_middle_end(self):
        with_call = self.video("C", UNMARKED)
        no_marker = self.video("D", UNMARKED)
        with self.fake(LINK_CALL + SPEECH):
            out, summary = enrich.enrich_media([with_call], "live")
        self.assertEqual(self.calls[-1][1], [60.0])
        self.assertTrue(out[0]["framesAttempted"])
        self.calls.clear()
        with self.fake(SPEECH):
            out, summary = enrich.enrich_media([no_marker], "live")
        self.assertEqual(self.calls[-1][1], [10.0, 450.0, 885.0])
        found = analyze(out[0])
        frames = [e for e in found["evidence"] if e.get("kind") == "frame"]
        self.assertEqual(len(frames), 3)
        self.assertTrue(all(f["role"] == "context" and "nieodczytany automatycznie" in f["text"] for f in frames))
        self.assertEqual(found["coverage"]["modalities"]["frames"]["state"], "selected_moments")
        self.assertIn("tekst z obrazu nieodczytany automatycznie", found["coverage"]["modalities"]["frames"]["reason"])
        self.assertTrue({m["evidenceId"] for m in found["reviewDecision"]["moments"]} >= {f["id"] for f in frames})
        self.calls.clear()
        with self.fake(DISCLOSURE):
            enrich.enrich_media([self.video("E", UNMARKED)], "live")
        self.assertEqual([c for c in self.calls if c[1] is not None], [], "no frames once the speech carries the label")

    def test_media_state_is_stored_and_a_rescan_does_not_lose_the_transcript(self):
        cap = self.video("C", UNMARKED)
        with self.fake():
            out, _ = enrich.enrich_media([cap], "live")
        self.scan([evaluate(out[0])])
        with store.connection() as db:
            state = store.media_states(db)[cap["id"]]
        self.assertEqual(state["state"], "done")
        self.assertEqual(state["segments"][0]["start"], 10.0)
        self.assertEqual(self.versions(cap["id"]), 1)
        with store.connection() as db:
            known = store.media_states(db)
        self.calls.clear()
        again, summary = enrich.enrich_media([cap], "live", known=known)  # a bare rescan of the same video
        self.assertEqual(self.calls, [])
        self.assertEqual(again[0]["segments"], out[0]["segments"])
        self.scan([evaluate(again[0])])
        self.assertEqual(self.versions(cap["id"]), 1, "no version churn")

    def test_a_stale_gap_is_not_stored_as_an_attempt_but_a_real_failure_is(self):
        stale = self.video("C", UNMARKED, mediaCoverage={"transcript": {"state": "unavailable", "reason": "limit filmów na skan"}})
        self.scan([evaluate(stale)])
        with store.connection() as db:
            self.assertEqual(store.media_states(db), {})
        with self.fake(error="error"):
            out, _ = enrich.enrich_media([self.video("D", UNMARKED)], "live")
        self.scan([evaluate(out[0])])
        with store.connection() as db:
            states = store.media_states(db)
        self.assertEqual({k: (v["state"], v["attempts"]) for k, v in states.items()}, {out[0]["id"]: ("failed", 1)})

    def test_enrich_scan_fetches_the_backlog_without_discovery_and_without_quota(self):
        signal = self.video("C", UNMARKED)
        quiet = self.video("A", PLAIN)
        self.scan([evaluate(signal), evaluate(quiet)])
        with store.connection(True) as db:
            ledger_before = db.execute("SELECT * FROM quota_ledger").fetchall()
        with self.fake(), patch("collectors.discovery.discover", side_effect=AssertionError("no discovery in an enrich scan")), \
             patch("analysis.semantic.suggest", return_value={"status": "unavailable"}):
            scan, _ = store.create_scan("enrich", "enrich-1")
            jobs.process.call_local(scan["id"])
        with store.connection() as db:
            detail = store.scan_detail(db, scan["id"])
            states = store.media_states(db)
            ledger_after = db.execute("SELECT * FROM quota_ledger").fetchall()
        self.assertEqual(detail["status"], "done")
        self.assertEqual([s["step"] for s in detail["steps"]], ["enrich", "analyze", "apply"])
        self.assertEqual(ledger_before, ledger_after, "the YouTube Data API ledger is untouched")
        self.assertEqual(list(states), [signal["id"]], "only the video with a signal was fetched")
        self.assertEqual(self.case(signal["id"])["versions"][-1]["changeKind"], "evidence")
        self.activate("qual_d")
        self.assertEqual(self.case(signal["id"])["variants"]["qual_d"]["route"], "refer")
        self.calls.clear()
        with self.fake(), patch("analysis.semantic.suggest", return_value={"status": "unavailable"}):
            scan, _ = store.create_scan("enrich", "enrich-2")
            jobs.process.call_local(scan["id"])
        self.assertEqual([c for c in self.calls if c[1] is None], [], "the backlog is empty: nothing left to fetch")


if __name__ == "__main__":
    unittest.main()
