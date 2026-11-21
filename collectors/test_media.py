"""Offline tests for collectors.media: tiny VTT/JSON files, fake yt-dlp and fake storyboard fetch."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from collectors import media

VID = "abcDEF12345"
MANUAL = """WEBVTT

00:00:01.000 --> 00:00:03.000
Dzień dobry, to jest reklama.

00:00:04.000 --> 00:00:06.500
Partnerem odcinka jest XTB, link w opisie.
"""
AUTO = ("WEBVTT\nKind: captions\nLanguage: pl\n\n"
        "00:00:00.200 --> 00:00:02.490 align:start position:0%\n \n"  # whitespace-only line, as YouTube writes it
        "Filmka.<00:00:00.800><c> Aktualna</c><00:00:01.400><c> wartość</c>\n\n"
        "00:00:02.490 --> 00:00:02.500 align:start position:0%\nFilmka. Aktualna wartość\n \n\n"
        "00:00:02.500 --> 00:00:04.890 align:start position:0%\nFilmka. Aktualna wartość\n"
        "Partnerem<00:00:03.000><c> odcinka</c><00:00:04.000><c> jest</c><00:00:04.400><c> XTB</c>\n\n"
        "00:00:04.890 --> 00:00:04.900 align:start position:0%\nPartnerem odcinka jest XTB\n \n\n"
        "00:00:04.900 --> 00:00:07.000 align:start position:0%\nPartnerem odcinka jest XTB\n"
        "z kodem &amp; DETERMINACJA\n")


class Clock:
    def __init__(self):
        self.now, self.sleeps = 100.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def info(duration=60, subtitles=(), auto=("pl", "pl-orig"), boards=True, language="pl"):
    data = {"id": VID, "title": "T", "duration": duration, "channel": "K", "upload_date": "20261101",
            "language": language, "availability": "public", "age_limit": 0, "description": "Opis: kod XTB123",
            "subtitles": {k: [] for k in subtitles}, "automatic_captions": {k: [] for k in auto}, "formats": []}
    if boards:
        data["formats"].append({"format_id": "sb0", "format_note": "storyboard", "width": 64, "height": 36,
                                "rows": 2, "columns": 2, "fragments": [
                                    {"url": "https://i.ytimg.com/sb/x/M0.jpg", "duration": 20.0},
                                    {"url": "https://i.ytimg.com/sb/x/M1.jpg", "duration": 20.0}]})
    return data


class FakeYtDlp:
    """Records every command and writes the files the real yt-dlp would write."""

    def __init__(self, data=None, files=None, stderr="", code=0):
        self.data = data if data is not None else info()
        self.files = files if files is not None else {"pl-orig": AUTO, "pl": AUTO}
        self.stderr, self.code, self.calls = stderr, code, []

    def __call__(self, args, timeout):
        self.calls.append(list(args))
        if "--version" in args:
            return 0, "2099.01.01\n", ""
        if self.code:
            return self.code, "", self.stderr
        if "--write-info-json" in args:
            base = Path(args[args.index("-o") + 1].replace("%(id)s", VID))
            base.parent.mkdir(parents=True, exist_ok=True)
            Path(f"{base}.info.json").write_text(json.dumps(self.data))
            for lang, text in self.files.items():
                Path(f"{base}.{lang}.vtt").write_text(text)
            return 0, "", ""
        if "worstaudio[ext=m4a]/worstaudio" in args:
            target = Path(args[args.index("-o") + 1].replace("%(ext)s", "m4a"))
            target.write_bytes(b"audio-bytes")
            return 0, "", ""
        return 1, "", "ERROR: unexpected"


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.clock = Clock()
        media._STATE["last"] = None

    def client(self, run, fetch=None, **kw):
        return media.Client(run=run, fetch=fetch, sleep=self.clock.sleep, clock=self.clock, ytdlp="yt-dlp", **kw)

    def run_enrich(self, run, **kw):
        return media.enrich({"url": f"https://www.youtube.com/watch?v={VID}"}, None, cache_dir=self.tmp,
                            client=kw.pop("client", None) or self.client(run), **kw)

    # parsing
    def test_manual_vtt_segments(self):
        segments = media.parse_vtt(MANUAL)
        self.assertEqual([s["start"] for s in segments], [1.0, 4.0])
        self.assertEqual(segments[1]["end"], 6.5)
        self.assertIn("link w opisie", segments[1]["text"])

    def test_auto_rolling_dedup_and_tags(self):
        segments = media.parse_vtt(AUTO, rolling=True)
        self.assertEqual([s["text"] for s in segments],
                         ["Filmka. Aktualna wartość", "Partnerem odcinka jest XTB", "z kodem & DETERMINACJA"])
        self.assertEqual(segments[1]["start"], 2.5)

    def test_video_id_variants(self):
        for value in (VID, f"https://youtu.be/{VID}?t=5", f"https://www.youtube.com/watch?v={VID}&t=9s",
                      f"https://www.youtube.com/shorts/{VID}", f"https://m.youtube.com/embed/{VID}"):
            self.assertEqual(media.video_id(value), VID)
        for value in ("https://example.com/watch?v=" + VID, "https://www.youtube.com/@kanal", "", None, "krotki"):
            self.assertIsNone(media.video_id(value))

    def test_deep_link(self):
        self.assertEqual(media.deep_link(VID, 125.9), f"https://www.youtube.com/watch?v={VID}&t=125s")
        self.assertEqual(media.deep_link(VID, -3), f"https://www.youtube.com/watch?v={VID}&t=0s")

    def test_markers(self):
        segments = [{"start": 4.0, "end": 6.0, "text": "Partnerem odcinka jest XTB, z kodem ABC"},
                    {"start": 9.0, "end": 10.0, "text": "pogoda jest ładna"}]
        found = media.find_markers(segments, "Reklama: link w opisie\nzwykła linia")
        self.assertEqual([m["modality"] for m in found], ["transcript", "description"])
        self.assertEqual({"partner", "broker", "kod"}, set(found[0]["kinds"]))

    def test_classify_error(self):
        cases = {"ERROR: [youtube] x: Private video. Sign in": "private",
                 "ERROR: [youtube] x: Video unavailable": "unavailable",
                 "ERROR: Sign in to confirm your age. This video may be inappropriate": "age_restricted",
                 "ERROR: Sign in to confirm you’re not a bot": "login_required",
                 "ERROR: HTTP Error 429: Too Many Requests": "rate_limited",
                 "ERROR: something odd": "error"}
        for text, status in cases.items():
            self.assertEqual(media.classify_error(text)[0], status, text)

    # enrich: captions, coverage, cache
    def test_captions_coverage_version_and_cache(self):
        fake = FakeYtDlp()
        first = self.run_enrich(fake)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["transcript"]["method"], "auto_captions")
        segment = first["segments"][1]
        self.assertEqual((segment["modality"], segment["method"], segment["language"]), ("speech", "auto_captions", "pl"))
        self.assertEqual(segment["deepLink"], f"https://www.youtube.com/watch?v={VID}&t=2s")
        self.assertEqual(first["sourceVersion"]["videoId"], VID)
        self.assertEqual(first["sourceVersion"]["captionsSha256"], first["mediaVersion"])
        self.assertTrue(first["sourceVersion"]["readAt"])
        self.assertEqual(first["coverage"]["checked"], ["description", "speech"])
        self.assertEqual(first["mediaCoverage"]["transcript"]["state"], "full")
        self.assertEqual(first["mediaCoverage"]["frames"]["state"], "not_collected")
        calls = len(fake.calls)
        second = self.run_enrich(fake)
        self.assertEqual(len(fake.calls), calls)  # no request at all
        self.assertEqual(second["stats"]["requests"], 0)
        self.assertEqual(second["segments"], first["segments"])

    def test_author_captions_preferred(self):
        fake = FakeYtDlp(data=info(subtitles=("pl",)), files={"pl": MANUAL, "pl-orig": AUTO})
        result = self.run_enrich(fake)
        self.assertEqual(result["transcript"]["method"], "author_captions")
        self.assertEqual(len(result["segments"]), 2)

    def test_no_captions_gap_without_asr(self):
        result = self.run_enrich(FakeYtDlp(data=info(auto=()), files={}))
        self.assertEqual(result["status"], "no_transcript")
        self.assertEqual(result["coverage"]["gaps"][0]["code"], "no_captions")
        self.assertTrue(result["coverage"]["blocksConclusion"])
        self.assertEqual(result["mediaCoverage"]["transcript"]["state"], "unavailable")

    def test_asr_fallback_is_injected_and_marked_partial(self):
        calls = []

        def fake_asr(path, seconds):
            calls.append((Path(path).name, seconds))
            return [{"start": 1.0, "end": 2.0, "text": "wasze pieniądze", "confidence": 0.8}]

        result = self.run_enrich(FakeYtDlp(data=info(duration=300, auto=()), files={}), allow_asr=True, asr=fake_asr)
        self.assertEqual(calls, [("audio.m4a", 120)])
        self.assertEqual(result["segments"][0]["method"], "asr")
        self.assertEqual(result["mediaCoverage"]["transcript"]["state"], "partial")
        self.assertEqual(result["mediaCoverage"]["transcript"]["windows"], [{"start": 0, "end": 120}])
        again = self.run_enrich(FakeYtDlp(data=info(duration=300, auto=()), files={}), allow_asr=True,
                                asr=lambda *a: self.fail("ASR must come from cache"))
        self.assertEqual(again["segments"][0]["text"], "wasze pieniądze")

    def test_asr_failure_is_a_status_not_an_exception(self):
        def broken(path, seconds):
            raise RuntimeError("Brak modelu języka polskiego.")

        result = self.run_enrich(FakeYtDlp(data=info(auto=()), files={}), allow_asr=True, asr=broken)
        self.assertEqual(result["status"], "no_transcript")
        self.assertEqual(result["coverage"]["gaps"][0]["code"], "asr_unavailable")

    # enrich: failures
    def test_unavailable_statuses(self):
        for text, status in (("ERROR: [youtube] x: Private video", "private"),
                             ("ERROR: Sign in to confirm your age", "age_restricted"),
                             ("ERROR: Sign in to confirm you're not a bot", "login_required"),
                             ("ERROR: HTTP Error 429: Too Many Requests", "rate_limited")):
            with self.subTest(status=status):
                shutil.rmtree(self.tmp / VID, ignore_errors=True)
                result = self.run_enrich(FakeYtDlp(stderr=text, code=1))
                self.assertEqual(result["status"], status)
                self.assertEqual(result["segments"], [])
                self.assertEqual(result["mediaCoverage"]["transcript"]["state"], "unavailable")
                self.assertTrue(result["coverage"]["blocksConclusion"])

    def test_terminal_status_cached_transient_is_not(self):
        private = FakeYtDlp(stderr="ERROR: Private video", code=1)
        self.run_enrich(private)
        calls = len(private.calls)
        self.assertEqual(self.run_enrich(private)["status"], "private")
        self.assertEqual(len(private.calls), calls)
        shutil.rmtree(self.tmp / VID)
        limited = FakeYtDlp(stderr="ERROR: HTTP Error 429", code=1)
        self.run_enrich(limited)
        self.run_enrich(limited)
        self.assertEqual(len(limited.calls), 2)  # resumes: tries again

    def test_timeout_and_deadline(self):
        result = self.run_enrich(FakeYtDlp(stderr="timeout", code=124))
        self.assertEqual(result["status"], "timeout")
        spent = self.client(FakeYtDlp(), max_seconds=0)
        result = media.enrich({"url": VID}, None, cache_dir=self.tmp / "late", client=spent)
        self.assertEqual(result["status"], "timeout")

    def test_unsupported_url_and_no_exception(self):
        result = media.enrich({"url": "https://example.com/x"}, None, cache_dir=self.tmp)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["segments"], [])

    def test_ctx_options(self):
        class Ctx:
            media = {"cache_dir": str(self.tmp)}

        result = media.enrich({"extra": {"youtube": {"videoId": VID}}}, Ctx(), client=self.client(FakeYtDlp()))
        self.assertEqual(result["status"], "ok")

    def test_min_gap_between_requests(self):
        fake = FakeYtDlp()
        client = self.client(fake)
        client.command(["a"])
        client.command(["b"])
        self.assertEqual(len(self.clock.sleeps), 1)
        self.assertGreaterEqual(self.clock.sleeps[0], 2.0 - 1e-9)

    # frames
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
    def test_storyboard_frame_evidence_and_cache(self):
        sheet = self.tmp / "sheet.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=128x72:rate=1", "-frames:v", "1",
                        str(sheet)], check=True)
        fetched = []

        def fetch(url, timeout):
            fetched.append(url)
            return sheet.read_bytes()

        run = FakeYtDlp()
        result = media.enrich({"url": VID}, None, cache_dir=self.tmp / "c", frames_at=[11.0, 26.0],
                              client=self.client(run, fetch))
        self.assertEqual(len(result["frames"]), 2)
        first = result["frames"][0]
        self.assertEqual((first["kind"], first["width"], first["height"]), ("frame", 64, 36))
        self.assertEqual(first["time"], 10.0)  # tiles are 5 s apart
        self.assertEqual(first["deepLink"], f"https://www.youtube.com/watch?v={VID}&t=10s")
        self.assertEqual(len(first["sha256"]), 64)
        self.assertEqual(first["sourceVersion"]["videoId"], VID)
        self.assertTrue((media.ROOT / first["path"]).is_file() or Path(first["path"]).is_file())
        self.assertEqual(result["mediaCoverage"]["frames"]["state"], "selected_moments")
        self.assertEqual(result["coverage"]["checked"], ["description", "speech", "frames_selected"])
        self.assertEqual(len(fetched), 2)  # frames come from two different sheets
        again = media.enrich({"url": VID}, None, cache_dir=self.tmp / "c", frames_at=[11.0, 26.0],
                             client=self.client(run, fetch))
        self.assertEqual(len(fetched), 2)
        self.assertEqual(again["stats"]["requests"], 0)
        self.assertEqual(again["frames"][1]["sha256"], result["frames"][1]["sha256"])

    def test_frames_failure_is_a_gap(self):
        def fetch(url, timeout):
            raise OSError("HTTP 403")

        result = media.enrich({"url": VID}, None, cache_dir=self.tmp / "g", frames_at=[5],
                              client=self.client(FakeYtDlp(), fetch))
        self.assertEqual(result["frames"], [])
        self.assertEqual(result["mediaCoverage"]["frames"]["state"], "not_collected")
        self.assertEqual(result["coverage"]["gaps"][-1]["modality"], "frames")
        self.assertEqual(result["status"], "ok")  # transcript still delivered

    def test_jpeg_size_parser(self):
        jpeg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffc0000b08002400400100ffd9")
        self.assertEqual(media._jpeg_size(jpeg), (64, 36))


if __name__ == "__main__":
    unittest.main()
