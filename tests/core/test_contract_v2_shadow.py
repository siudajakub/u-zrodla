"""Contract v2 steps S5 and S8: qualification D in shadow mode, side table, media step, shadow report."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from analysis.engine import analyze
from analysis.semantic import review_suggestion
from api import enrich, shadow_report, store
from v2_helpers import StateCase, VIDEO, capture

UNMARKED = "Zacznij z XTB: https://link-pso.xtb.com/pso/abc Kod KANAL przy rejestracji daje kurs."
CODE_SEGMENT = {"start": 614.0, "end": 618.0, "text": "z kodem KANAL otworzycie konto w XTB", "method": "auto_captions",
                "modality": "speech", "language": "pl", "windowId": "w0"}
DISCLOSURE_SEGMENT = {"start": 5.0, "end": 9.0, "text": "Ten film powstał we współpracy z firmą XTB.", "method": "auto_captions",
                      "modality": "speech", "language": "pl", "windowId": "w0"}
FULL = {"transcript": {"state": "full", "source": "auto_captions", "windows": [{"start": 0, "end": 900}], "durationSec": 900},
        "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}


def evaluate(cap):
    found = analyze(cap)
    found["semantic"] = {"status": "unavailable"}
    found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
    return cap, found


def view(test, key=VIDEO, schema=1):
    with store.connection() as db:
        return store.case_dict(db, db.execute("SELECT * FROM cases WHERE id=?", (key,)).fetchone(), schema=schema)


class NoNetwork(StateCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("network is off in tests")))
        self.enterContext(patch("collectors.media.urlopen", side_effect=AssertionError("network is off in tests")))


class ShadowStorage(NoNetwork):
    def test_v2_fields_live_beside_the_case_and_legacy_fields_stay(self):
        cap = capture(description=UNMARKED)
        pair = evaluate(cap)
        self.scan([pair])
        with store.connection() as db:
            raw = json.loads(db.execute("SELECT body FROM cases WHERE id=?", (VIDEO,)).fetchone()[0])
            side = db.execute("SELECT count(*) FROM qualification_results WHERE case_id=?", (VIDEO,)).fetchone()[0]
        for key in store.SHADOW_KEYS:
            self.assertNotIn(key, raw)
        self.assertTrue(all("role" not in e for e in raw["evidence"]))
        self.assertEqual(side, 1)
        found = view(self)
        self.assertEqual(found["reviewDecision"]["route"], "refer")
        self.assertEqual(found["variants"]["rules_1_2"]["route"], ROUTE[pair[1]["reviewSuggestion"]["state"]])
        self.assertEqual(found["variants"]["qual_d"]["route"], "refer")
        self.assertTrue(found["evidenceV2"])
        self.assertEqual(found["coverageV2"]["scope"], "description+transcript")
        self.assertEqual((found["score"], found["reviewSuggestion"]["state"]), (pair[1]["score"], pair[1]["reviewSuggestion"]["state"]))
        self.assertEqual(found["analysisVersion"]["variant"], "rules_1_2")
        self.assertFalse(found["needsRecalc"])

    def test_rescan_keeps_one_version_and_refreshes_the_shadow(self):
        cap = capture(description=UNMARKED)
        self.scan([evaluate(cap)])
        again = self.scan([evaluate(cap)])
        self.assertEqual((again["changedFindings"], self.versions()), (0, 1))
        with store.connection(True) as db:
            db.execute("UPDATE qualification_results SET body='{}'")
        self.scan([evaluate(cap)])
        self.assertEqual(self.case()["reviewDecision"]["route"], "refer")

    def test_shadow_does_not_change_queue_or_high_risk(self):
        declaration = capture("youtube:BBBBBBBBBBB", description="Partnerem odcinka jest XTB.")
        self.scan([evaluate(declaration)])
        found = self.case("youtube:BBBBBBBBBBB")
        self.assertEqual(found["reviewSuggestion"]["state"], "review")  # rules_1_2 still refers it
        self.assertNotEqual(found["reviewDecision"]["route"], "refer")  # qual_d: a declaration is a registry entry
        self.assertEqual(found["adRegistry"]["state"], "included")
        self.assertEqual([e["ref"] for e in self.events("high_risk")], ["youtube:BBBBBBBBBBB"])

    def test_qualify_failure_is_insufficient_not_an_exception(self):
        with patch("analysis.qualification.qualify", side_effect=RuntimeError("boom")):
            found = analyze(capture(description=UNMARKED))
        self.assertEqual(found["reviewDecision"]["route"], "insufficient")
        self.assertIsNone(found["reviewScore"]["value"])

    def test_reach_changes_priority_only(self):
        small = analyze(capture(description=UNMARKED, reach={"metrics": {"viewCount": {"value": 10, "state": "observed"}}}))
        large = analyze(capture(description=UNMARKED, reach={"metrics": {"viewCount": {"value": 10 ** 7, "state": "observed"}}}))
        self.assertNotEqual(small["priority"]["review"], large["priority"]["review"])
        self.assertEqual(small["reviewDecision"], large["reviewDecision"])


ROUTE = {"review": "refer", "uncertain": "complete", "no_signal": "no_signal", "unavailable": "insufficient"}


class MediaStep(NoNetwork):
    def setUp(self):
        super().setUp()
        self.cache = Path(self.temp) / "media-cache"
        self.cache.mkdir()
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_MEDIA_CACHE": str(self.cache)}))
        self.calls = []

    def fake(self, segments=(CODE_SEGMENT,), status="ok"):
        def enrich_one(cap, ctx=None, **kwargs):
            self.calls.append((cap["id"], kwargs.get("frames_at"), "client" in kwargs))
            frames = [{"time": t, "sha256": "x" * 64, "available": True} for t in kwargs.get("frames_at") or []]
            return {"status": status, "segments": [dict(s) for s in segments], "frames": frames,
                    "mediaCoverage": {**FULL, "frames": {"state": "selected_moments" if frames else "not_collected",
                                                         "moments": [f["time"] for f in frames], "intervalSec": None}}}
        return patch("collectors.media.enrich", enrich_one)

    def cached(self, vid="AAAAAAAAAAA"):
        (self.cache / vid).mkdir()
        (self.cache / vid / "transcript.json").write_text("{}")

    def test_live_adds_transcript_and_frames_only_at_marker_moments_for_a_suspect(self):
        cap = capture(description=UNMARKED, mediaCoverage=None)
        with self.fake():
            out, summary = enrich.enrich_media([cap], "live")
        self.assertEqual(self.calls[0][1:], (None, False))
        self.assertEqual(self.calls[1][1], [614.0], "frames are requested for the marked moment only")
        self.assertEqual(out[0]["segments"][0]["start"], 614.0)
        self.assertEqual(out[0]["mediaCoverage"]["frames"]["state"], "selected_moments")
        self.assertEqual((summary["transcripts"], summary["frames"], summary["network"]), (1, 1, 1))

    def test_no_frames_when_the_speech_carries_the_disclosure(self):
        cap = capture(description=UNMARKED, mediaCoverage=None)
        with self.fake((DISCLOSURE_SEGMENT,)):
            out, summary = enrich.enrich_media([cap], "live")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(summary["frames"], 0)
        self.assertEqual(analyze(out[0])["reviewDecision"]["route"], "no_signal")
        self.assertEqual(analyze(out[0])["adRegistry"]["state"], "included")

    def test_replay_reads_the_cache_only_and_never_asks_for_frames(self):
        known, unknown = capture(description=UNMARKED, mediaCoverage=None), capture("youtube:BBBBBBBBBBB", description=UNMARKED, mediaCoverage=None, url="https://www.youtube.com/watch?v=BBBBBBBBBBB")
        self.cached("AAAAAAAAAAA")
        with self.fake():
            out, summary = enrich.enrich_media([known, unknown], "replay")
        self.assertEqual(self.calls, [(VIDEO, None, True)], "an offline client is injected and only the cached film is read")
        self.assertIn("segments", out[0])
        self.assertEqual(out[1]["mediaCoverage"]["transcript"]["state"], "pending")
        self.assertIn("replay", out[1]["mediaCoverage"]["transcript"]["reason"])
        self.assertEqual((summary["cached"], summary["deferred"]), (1, 1))

    def test_per_scan_limit_and_error_are_gaps_not_failures(self):
        caps = [capture(f"youtube:{c * 11}", description="Opis. Partnerem odcinka jest XTB.", mediaCoverage=None) for c in "CDE"]
        with patch.dict(os.environ, {"INVESTWATCH_MEDIA_PER_SCAN": "1"}), self.fake(()):
            out, summary = enrich.enrich_media(caps, "live")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((summary["gaps"], summary["deferred"]), (1, 2))
        self.assertTrue(all(c["mediaCoverage"]["transcript"]["state"] in ("full", "unavailable", "pending") for c in out))
        self.assertEqual(sum(c["mediaCoverage"]["transcript"]["state"] == "pending" for c in out), 2, "the rest waits for the next scan")
        with patch("collectors.media.enrich", side_effect=RuntimeError("yt-dlp padł")):
            out, summary = enrich.enrich_media([capture(description="Partnerem odcinka jest XTB.", mediaCoverage=None)], "live")
        self.assertIn("yt-dlp padł", out[0]["mediaCoverage"]["transcript"]["reason"])

    def test_transcript_makes_an_evidence_version_and_closes_the_coverage_gap(self):
        cap = capture(description=UNMARKED, mediaCoverage=None)
        self.scan([evaluate(cap)])
        with self.fake((DISCLOSURE_SEGMENT,)):
            enriched, _ = enrich.enrich_media([cap], "live")
        self.scan([evaluate(enriched[0])])
        found = self.case()
        self.assertEqual(found["versions"][-1]["changeKind"], "evidence")
        self.assertEqual(found["reviewDecision"]["route"], "no_signal")
        self.assertEqual(view(self)["coverageV2"]["modalities"]["transcript"]["state"], "full")
        self.assertEqual(view(self, schema=2)["coverage"]["modalities"]["transcript"]["state"], "full")

    def test_scan_records_the_media_summary_in_the_enrich_step(self):
        from api import jobs
        from collectors import discovery
        from collectors.adapter import Adapter
        cap = capture(description=UNMARKED, mediaCoverage=None, discovery=[{"method": "atom", "observedAt": "2026-11-21T10:00:00+00:00"}])
        stub = Adapter("stub", lambda ctx: {"creators": [], "captures": [cap], "sources": [{"id": "stub", "name": "s", "status": "ok", "count": 1}]})
        with patch.dict(discovery.ADAPTERS, {"stub": stub}, clear=True), self.fake((DISCLOSURE_SEGMENT,)), \
             patch("api.listen.sample_audio", return_value={"id": "asr", "name": "asr", "status": "empty", "count": 0}), \
             patch("collectors.m2_archive.staged_captures", return_value=([], [], [])), \
             patch("analysis.semantic.suggest", return_value={"status": "unavailable"}):
            scan, _ = store.create_scan("live", "media-1")
            jobs.process.call_local(scan["id"])
        with store.connection() as db:
            detail = store.scan_detail(db, scan["id"])
        step = next(s for s in detail["steps"] if s["step"] == "enrich")
        self.assertEqual(step["summary"]["media"]["transcripts"], 1)
        self.assertEqual(detail["status"], "done")
        self.assertEqual(self.case()["reviewDecision"]["route"], "no_signal")


class ShadowReport(NoNetwork):
    def test_report_lists_old_and_new_route_read_only(self):
        self.scan([evaluate(capture(description=UNMARKED)),
                   evaluate(capture("youtube:BBBBBBBBBBB", description="Partnerem odcinka jest XTB."))])
        db_file = Path(self.temp) / "cases.sqlite3"
        before = db_file.stat().st_mtime_ns
        items = {i["id"]: i for i in shadow_report.report(self.temp)}
        self.assertEqual(db_file.stat().st_mtime_ns, before)
        unmarked = items[VIDEO]
        self.assertEqual((unmarked["rules_1_2"]["route"], unmarked["qual_d"]["route"]), ("no_signal", "refer"))
        self.assertTrue(unmarked["differs"])
        self.assertTrue(unmarked["qual_d"]["reasons"] and unmarked["qual_d"]["moments"])
        declared = items["youtube:BBBBBBBBBBB"]
        self.assertEqual((declared["rules_1_2"]["route"], declared["qual_d"]["registry"]), ("refer", "included"))
        self.assertIn("RÓŻNICA", shadow_report.text(list(items.values())))

    def test_cli_prints_text_and_json_and_rejects_a_missing_state(self):
        import contextlib
        import io
        self.scan([evaluate(capture(description=UNMARKED))])
        for argv in (["--state", self.temp], ["--state", self.temp, "--json"]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                shadow_report.main(argv)
            self.assertIn("refer", out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["summary"], {"cases": 1, "differ": 1, "withoutShadow": 0})
        with self.assertRaises(SystemExit):
            shadow_report.report(Path(self.temp) / "missing")


if __name__ == "__main__":
    unittest.main()
