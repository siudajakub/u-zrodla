"""Media queue properties (lane H): a 429 of one video does not stop the queue, attempts rotate, a host block stops,
no_captions is permanent and never "pending". No network: collectors.media.enrich is replaced."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from api import enrich, store
from v2_helpers import StateCase, capture

UNMARKED = "Zacznij z XTB: https://link-pso.xtb.com/pso/abc Kod KANAL przy rejestracji daje kurs."
IDS = ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"]


def video(vid, **extra):
    return capture("youtube:" + vid, description=UNMARKED, mediaCoverage=None, url="https://www.youtube.com/watch?v=" + vid, **extra)


def limited(scope):
    return {"status": "rate_limited", "segments": [], "error": {"status": "rate_limited", "scope": scope},
            "mediaCoverage": {"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                             "reason": "HTTP 429"}, "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}


def no_captions():
    return {"status": "no_transcript", "segments": [], "error": {"status": "no_captions"},
            "mediaCoverage": {"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                             "reason": "no_captions: Brak napisów po polsku"},
                              "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}


def transcript(source="transcript_api"):
    return {"status": "ok", "segments": [{"start": 0.0, "end": 5.0, "text": "Dzień dobry, partnerem odcinka jest XTB."}],
            "mediaCoverage": {"transcript": {"state": "full", "source": source, "windows": [{"start": 0, "end": 5}], "durationSec": 5},
                              "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}}


class MediaQueue(StateCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("network is off in tests")))
        cache = Path(self.temp) / "cache"
        cache.mkdir()
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_MEDIA_CACHE": str(cache), "INVESTWATCH_MEDIA_FRAMES": "0"}))
        self.calls = []

    def run_step(self, results, caps, known=None):
        def fake(cap, ctx=None, **kwargs):
            self.calls.append(cap["id"][8:])
            return results[cap["id"][8:]]
        with patch("collectors.media.enrich", fake):
            return enrich.enrich_media(caps, "live", known=known or {}, backlog=True)

    def test_a_429_of_one_video_does_not_stop_the_queue(self):
        out, summary = self.run_step({"AAAAAAAAAAA": limited("video"), "BBBBBBBBBBB": transcript(), "CCCCCCCCCCC": transcript()},
                                     [video(v) for v in IDS])
        self.assertEqual(sorted(self.calls), sorted(IDS))
        self.assertNotIn("blocked", summary)
        first = next(c for c in out if c["id"].endswith("AAAAAAAAAAA"))
        self.assertEqual((first["mediaCoverage"]["transcript"]["state"], first["mediaAttempts"]), ("pending", 1))
        self.assertEqual(store.media_outcome(first), "failed", "a pending video with tries counts as an attempt")
        self.assertEqual(summary["videoLimited"], 1)
        done = next(c for c in out if c["id"].endswith("BBBBBBBBBBB"))
        self.assertEqual(done["mediaCoverage"]["transcript"]["source"], "transcript_api")
        self.assertEqual(store.media_outcome(done), "done")

    def test_fewest_attempts_go_first_and_a_third_429_is_final_with_a_reason(self):
        known = {"youtube:AAAAAAAAAAA": {"attempts": 2}, "youtube:BBBBBBBBBBB": {"attempts": 1}}
        out, _ = self.run_step({v: limited("video") for v in IDS}, [video(v) for v in IDS], known)
        self.assertEqual(self.calls, ["CCCCCCCCCCC", "BBBBBBBBBBB", "AAAAAAAAAAA"], "rotation by attempts, then the ranking")
        last = next(c for c in out if c["id"].endswith("AAAAAAAAAAA"))
        self.assertEqual(last["mediaCoverage"]["transcript"]["state"], "unavailable")
        self.assertIn("nieudane 3 próby", last["mediaCoverage"]["transcript"]["reason"])
        self.assertEqual(store.media_outcome(last), "unavailable")
        middle = next(c for c in out if c["id"].endswith("BBBBBBBBBBB"))
        self.assertEqual((middle["mediaAttempts"], middle["mediaCoverage"]["transcript"]["state"]), (2, "pending"))

    def test_a_host_block_stops_the_step_and_defers_the_rest(self):
        out, summary = self.run_step({v: limited("host") for v in IDS}, [video(v) for v in IDS])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(summary["blocked"], "rate_limited")
        self.assertTrue(all(c["mediaCoverage"]["transcript"]["state"] == "pending" for c in out))

    def test_no_captions_is_permanent_and_not_pending(self):
        out, _ = self.run_step({"AAAAAAAAAAA": no_captions()}, [video("AAAAAAAAAAA")])
        cap = out[0]
        self.assertEqual(store.media_outcome(cap), "unavailable")
        from analysis.engine import transcript_phase
        self.assertNotEqual(transcript_phase(cap)["state"], "pending")
        again, _ = self.run_step({"AAAAAAAAAAA": no_captions()}, [cap], {"youtube:AAAAAAAAAAA": {"attempts": 1}})
        self.assertEqual(self.calls, ["AAAAAAAAAAA"], "the permanent gap is not requested again")


if __name__ == "__main__":
    unittest.main()
