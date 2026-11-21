"""Contract v2 handoff to the desk (lane H): replay media pack, frame thumbnails, resolution, scan summary, trend.

No network, no subprocess, private temporary state. The real replay pack of the host is never read.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from analysis.engine import analyze
from analysis.semantic import review_suggestion
from api import enrich, replay_pack, store
from v2_helpers import HttpCase, StateCase, VIDEO, capture

UNMARKED = "Zacznij z XTB: https://link-pso.xtb.com/pso/abc Kod KANAL przy rejestracji daje kurs."
CODE_SEGMENT = {"start": 614.0, "end": 618.0, "text": "z kodem KANAL otworzycie konto w XTB", "method": "auto_captions",
                "modality": "speech", "language": "pl", "windowId": "w0"}
FULL = {"transcript": {"state": "full", "source": "auto_captions", "windows": [{"start": 0, "end": 900}], "durationSec": 900},
        "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 60 + b"\xff\xd9"


def evaluate(cap):
    found = analyze(cap)
    found["semantic"] = {"status": "unavailable"}
    found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
    return cap, found


def make_cache(root, video="AAAAAAAAAAA"):
    folder = Path(root) / video
    (folder / "frames").mkdir(parents=True)
    (folder / "meta.json").write_text('{"status":"ok","videoId":"%s"}' % video)
    (folder / "transcript.json").write_text('{"segments":[]}')
    (folder / "frames" / "storyboard_320x180_000614.jpg").write_bytes(JPEG)
    (folder / "frames" / "sheet_sb0_6.jpg").write_bytes(JPEG * 50)  # a sheet is never packed
    return Path(root)


class Pack(StateCase):
    def setUp(self):
        super().setUp()
        self.source = make_cache(Path(self.temp) / "cache")
        self.out = Path(self.temp) / "pack"

    def test_build_lists_every_file_with_sha256_and_leaves_storyboard_sheets_out(self):
        manifest = replay_pack.build(self.source, ["AAAAAAAAAAA"], self.out, Path(self.temp) / "repo-manifest.json")
        names = {f["path"] for f in manifest["files"]}
        self.assertEqual(names, {"AAAAAAAAAAA/meta.json", "AAAAAAAAAAA/transcript.json", "AAAAAAAAAAA/frames/storyboard_320x180_000614.jpg"})
        self.assertTrue(all(len(f["sha256"]) == 64 for f in manifest["files"]))
        report = replay_pack.inspect(self.out, Path(self.temp) / "repo-manifest.json")
        self.assertEqual((report["state"], report["videos"], report["problems"]), ("present", ["AAAAAAAAAAA"], []))

    def test_missing_corrupt_and_foreign_manifest_are_states_not_exceptions(self):
        self.assertEqual(replay_pack.inspect(self.out)["state"], "missing")
        replay_pack.build(self.source, ["AAAAAAAAAAA"], self.out, Path(self.temp) / "m.json")
        (self.out / "AAAAAAAAAAA/transcript.json").write_text('{"segments":[1]}')
        damaged = replay_pack.inspect(self.out)
        self.assertEqual(damaged["state"], "corrupt")
        self.assertIn("SHA-256", damaged["problems"][0])
        (self.out / "MANIFEST.json").write_text("not json")
        self.assertEqual(replay_pack.inspect(self.out)["state"], "corrupt")

    def test_build_refuses_a_video_without_metadata(self):
        with self.assertRaises(SystemExit):
            replay_pack.build(self.source, ["BBBBBBBBBBB"], self.out, None)


class ReplayMedia(StateCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("network is off in tests")))
        self.state_cache = Path(self.temp) / "state-cache"
        self.state_cache.mkdir()
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_MEDIA_CACHE": str(self.state_cache)}))
        self.calls = []

    def fake(self):
        def enrich_one(cap, ctx=None, **kwargs):
            media = (ctx or {}).get("media", {})
            self.calls.append({"cache": str(media.get("cache_dir")), "frames_at": kwargs.get("frames_at"), "offline": "client" in kwargs})
            frames = [{"time": t, "sha256": "x" * 64, "available": True} for t in kwargs.get("frames_at") or []]
            return {"status": "ok", "segments": [dict(CODE_SEGMENT)], "frames": frames,
                    "mediaCoverage": {**FULL, "frames": {"state": "selected_moments" if frames else "not_collected",
                                                         "moments": [f["time"] for f in frames], "intervalSec": None}}}
        return patch("collectors.media.enrich", enrich_one)

    def pack(self, video="AAAAAAAAAAA"):
        out = Path(self.temp) / "pack"
        replay_pack.build(make_cache(Path(self.temp) / "src", video), [video], out, None)
        return out

    def test_replay_reads_transcript_and_frames_from_the_pack_without_network(self):
        out = self.pack()
        cap = capture(description=UNMARKED, mediaCoverage=None)
        with patch.dict(os.environ, {"INVESTWATCH_REPLAY_MEDIA": str(out)}), self.fake():
            captures, summary = enrich.enrich_media([cap], "replay")
        self.assertEqual(summary["replayPack"]["state"], "present")
        self.assertEqual([c["cache"] for c in self.calls], [str(out)] * 2, "transcript and frames both come from the pack")
        self.assertTrue(all(c["offline"] for c in self.calls), "an offline client guards every call")
        self.assertEqual(self.calls[1]["frames_at"], [614.0])
        self.assertEqual((summary["cached"], summary["network"], summary["frames"]), (1, 0, 1))
        self.assertEqual(enrich.pack_source(summary)["status"], "ok")
        self.assertEqual(captures[0]["mediaCoverage"]["frames"]["state"], "selected_moments")

    def test_missing_pack_is_a_source_status_and_a_gap_not_an_error(self):
        cap = capture(description=UNMARKED, mediaCoverage=None)
        with patch.dict(os.environ, {"INVESTWATCH_REPLAY_MEDIA": str(Path(self.temp) / "nope")}), self.fake():
            captures, summary = enrich.enrich_media([cap], "replay")
        self.assertEqual(summary["replayPack"]["state"], "missing")
        self.assertEqual(self.calls, [])
        reason = captures[0]["mediaCoverage"]["transcript"]["reason"]
        self.assertIn("brak paczki mediów", reason)
        source = enrich.pack_source(summary)
        self.assertEqual(source["status"], "empty", "empty, not error: the scan stays done")
        self.assertIn("luka", source["scope"])
        self.assertEqual(store.health_of(source["status"]), "ok")

    def test_a_video_outside_the_pack_stays_pending_and_other_materials_report_no_pack(self):
        out = self.pack("CCCCCCCCCCC")
        cap = capture(description=UNMARKED, mediaCoverage=None)
        with patch.dict(os.environ, {"INVESTWATCH_REPLAY_MEDIA": str(out)}), self.fake():
            captures, summary = enrich.enrich_media([cap], "replay")
        self.assertEqual(captures[0]["mediaCoverage"]["transcript"]["state"], "pending")
        self.assertIn("poza paczką", captures[0]["mediaCoverage"]["transcript"]["reason"])
        with patch.dict(os.environ, {"INVESTWATCH_REPLAY_MEDIA": str(out)}):
            _, none = enrich.enrich_media([capture("upload-1", module="M3", platform="web")], "replay")
        self.assertNotIn("replayPack", none, "no YouTube film, no media source row")


class ReplayEvent(unittest.TestCase):
    PACK = "7M0rC6-Rueo AqXHkxDzSDI OIyPE0z2mng ZJrT-X08Xwc CDk20n4u9Kk -HpCSKp9bqk 9Fcwo1jlwe4 xtMqKkFO-0M yIbtMnfP25Q O5YmmKadQQw eQYmvRfHtr8 YQH4FEP9exI ePfzHQVf-lc o2GfnmVVkO8 _aqCM37gK1U p_ui_fqLdV0 i3QxMqyRlks reaI2uNoGSk ysRd-DFgqwo zsfT3OIO-9c 5e0D6XJUF84 q7pHqpsve14 5OuFrlmcQ5E".split()

    def test_the_replay_event_holds_every_film_of_the_media_pack_and_marks_the_ones_it_added(self):
        from collectors.discovery import ADAPTERS
        result = ADAPTERS["youtube-replay"].discover(None)
        by_id = {c["id"]: c for c in result["captures"]}
        self.assertEqual([v for v in self.PACK if "youtube:" + v not in by_id], [])
        extra = [c for c in result["captures"] if (c.get("provenance") or {}).get("fixture") == "replay-media-extra.json"]
        self.assertEqual({c["id"][8:] for c in extra}, {"CDk20n4u9Kk", "-HpCSKp9bqk", "9Fcwo1jlwe4", "xtMqKkFO-0M", "YQH4FEP9exI", "q7pHqpsve14", "5OuFrlmcQ5E"})
        creators = {c["id"] for c in result["creators"]}
        self.assertTrue(all(c["creatorId"] in creators for c in extra), "every added film has its creator")
        self.assertTrue(all(c["mode"] == "replay" and c["discovery"][0]["import"] for c in extra))
        self.assertEqual(len([c for c in result["captures"] if c["id"] == "youtube:7M0rC6-Rueo"]), 1)


class DeskApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch("subprocess.run", side_effect=AssertionError("subprocess is off in tests")))
        self.cache = Path(self.temp) / "media"
        make_cache(self.cache)
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_MEDIA_CACHE": str(self.cache)}))
        digest = store.sha256(JPEG).hexdigest()
        self.cap = capture(description=UNMARKED, mediaCoverage={**FULL, "frames": {"state": "selected_moments", "moments": [614.0], "intervalSec": None}},
                           segments=[dict(CODE_SEGMENT)],
                           frames=[{"id": "frame-AAAAAAAAAAA-614-storyboard_320x180", "kind": "frame", "modality": "frame", "time": 614.0,
                                    "path": ".runtime/replay-media/2026-11-21/AAAAAAAAAAA/frames/storyboard_320x180_000614.jpg",
                                    "sha256": digest, "deepLink": "https://www.youtube.com/watch?v=AAAAAAAAAAA&t=614s",
                                    "sourceUrlAtTime": "https://www.youtube.com/watch?v=AAAAAAAAAAA&t=614s",
                                    "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA&t=614s", "available": True}])
        self.scan([evaluate(self.cap)])

    def raw(self, path, headers=None):
        try:
            with urlopen(Request(self.base + path, headers=headers or {}), timeout=4) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def test_frame_evidence_has_a_thumbnail_url_and_the_route_serves_exactly_that_jpeg(self):
        status, body = self.request("GET", "/v1/cases/" + VIDEO + "?schema=2")
        frames = [e for e in body["evidence"] if e.get("modality") == "frame"]
        self.assertTrue(frames)
        url = frames[0]["thumbnailUrl"]
        self.assertEqual(url, "/v1/frames/AAAAAAAAAAA/storyboard_320x180_000614.jpg")
        code, headers, data = self.raw(url)
        self.assertEqual((code, headers["Content-Type"], data), (200, "image/jpeg", JPEG))
        code, _, _ = self.raw(url.replace("storyboard", "stream"))
        self.assertEqual(code, 404, "a name the case does not list is not served")

    def test_frame_route_is_read_only_and_refuses_traversal_other_files_and_wrong_hash(self):
        (self.cache / "AAAAAAAAAAA" / "secret.txt").write_text("x")
        (self.cache / "AAAAAAAAAAA" / "frames" / "other.jpg").write_bytes(JPEG)
        for path in ("/v1/frames/AAAAAAAAAAA/other.jpg",           # on disk but not listed by the case
                     "/v1/frames/AAAAAAAAAAA/..%2Fmeta.json",
                     "/v1/frames/AAAAAAAAAAA/%2e%2e/meta.json",
                     "/v1/frames/AAAAAAAAAAA/secret.txt",
                     "/v1/frames/..%2F..%2Fetc/passwd.jpg",
                     "/v1/frames/BBBBBBBBBBB/storyboard_320x180_000614.jpg"):
            self.assertEqual(self.raw(path)[0], 404, path)
        self.assertEqual(self.request("POST", "/v1/frames/AAAAAAAAAAA/storyboard_320x180_000614.jpg", {})[0], 405)
        (self.cache / "AAAAAAAAAAA" / "frames" / "storyboard_320x180_000614.jpg").write_bytes(JPEG + b"tampered")
        self.assertEqual(self.raw("/v1/frames/AAAAAAAAAAA/storyboard_320x180_000614.jpg")[0], 404, "a changed file is not served")

    def test_resolution_is_recorded_implies_a_status_and_old_clients_keep_working(self):
        _, case = self.request("GET", "/v1/cases/" + VIDEO)
        rev = case["revision"]
        status, body = self.request("PATCH", "/v1/cases/" + VIDEO, {"resolution": "refer_to_control", "expectedRevision": rev, "note": "Do kontroli."})
        self.assertEqual((status, body["status"], body["lastDecision"]["resolution"]), (200, "reviewing", "refer_to_control"))
        status, body = self.request("PATCH", "/v1/cases/" + VIDEO, {"status": "closed", "resolution": "no_signal", "expectedRevision": rev + 1, "note": "Bez sygnału."})
        self.assertEqual((status, body["status"]), (200, "closed"))
        history = [h for h in body["history"] if h["action"] == "decision"]
        self.assertEqual([h.get("resolution") for h in history], ["refer_to_control", "no_signal"])
        status, body = self.request("PATCH", "/v1/cases/" + VIDEO, {"status": "reviewing", "expectedRevision": rev + 2, "note": "Stary klient."})
        self.assertEqual((status, body["status"], body["lastDecision"]["resolution"]), (200, "reviewing", None))
        self.assertEqual(self.request("PATCH", "/v1/cases/" + VIDEO, {"expectedRevision": rev + 3, "note": "x"})[0], 422)
        self.assertEqual(self.request("PATCH", "/v1/cases/" + VIDEO, {"resolution": "bogus", "expectedRevision": rev + 3, "note": "x"})[0], 422)

    def test_schema_by_query_or_header_and_the_default_stays_v1(self):
        _, one = self.request("GET", "/v1/state")
        self.assertEqual(one["schema"]["served"], 1)
        self.assertIsInstance(one["sourceHealth"], dict)
        _, two = self.request("GET", "/v1/state?schema=2")
        self.assertEqual(two["schema"]["served"], 2)
        code, _, data = self.raw("/v1/state", {"X-InvestWatch-Schema": "2"})
        self.assertEqual(json.loads(data)["schema"]["served"], 2)
        self.assertEqual(json.loads(self.raw("/v1/state", {"X-InvestWatch-Schema": "zzz"})[2])["schema"]["served"], 1)
        self.assertEqual(json.loads(self.raw("/v1/cases/" + VIDEO, {"X-InvestWatch-Schema": "2"})[2])["coverage"]["scope"], "description+transcript")

    def test_scan_summary_steps_progress_trend_and_the_source_and_creator_views(self):
        src = {"id": "youtube", "name": "YouTube", "status": "limit", "count": 0, "url": "https://www.googleapis.com/youtube/v3",
               "lastError": {"code": "quotaExceeded", "message": "Dzienny limit", "nextStep": "Poczekaj do resetu"}}
        ok = {"id": "replay-media", "name": "Paczka", "status": "ok", "count": 3}
        creator = {"id": "peertube:h/c", "name": "Kanał", "platform": "peertube", "url": "https://h/c",
                   "discovery": {"query": "etf", "rank": 4, "observedAt": "2026-11-21T10:00:00+00:00", "sourceUrl": "https://h/s"}}
        scan, _ = store.create_scan("replay", "r1")
        with store.connection(True) as db:
            store.plan_steps(db, scan["id"], ["discover:youtube-replay", "enrich", "analyze", "apply"])
            store.step_finish(db, scan["id"], "enrich", "done", {})
            other = capture("youtube:BBBBBBBBBBB", description=UNMARKED, url="https://www.youtube.com/watch?v=BBBBBBBBBBB")
            result = store.apply_scan(db, [evaluate(other)], [creator], [src, ok, {"id": "e", "name": "E", "status": "empty", "count": 0}],
                                      "live", scan_id=scan["id"])
            db.execute("UPDATE scans SET status='done',result=? WHERE id=?", (store.dump(result), scan["id"]))
        self.assertEqual(result["sources"], {"ok": 1, "empty": 1, "partial": 0, "failed": 1, "total": 3})
        self.assertEqual(result["referred"], 0, "rules_1_2 refers a declaration, not an unmarked link; the speech gate holds it too")
        _, state = self.request("GET", "/v1/state?schema=2")
        first = state["scans"][0]
        self.assertEqual((first["sources"]["failed"], first["referred"], first["progress"]), (1, 0, {"done": 1, "total": 4}))
        _, detail = self.request("GET", "/v1/scans/" + scan["id"])
        self.assertEqual([s["id"] for s in detail["steps"]], ["discover:youtube-replay", "enrich", "analyze", "apply"])
        self.assertTrue(all(s["name"] and s["status"] for s in detail["steps"]))
        self.assertEqual(detail["progress"], {"done": 1, "total": 4})
        row = next(s for s in state["sources"] if s["id"] == "youtube")
        self.assertEqual((row["lastError"]["code"], row["kind"], row["target"]), ("quotaExceeded", "search", "https://www.googleapis.com/youtube/v3"))
        self.assertIn("quota", row)
        self.assertEqual(state["sourceHealthSummary"]["status"], "degraded")
        self.assertEqual(state["sourceHealthDetail"]["youtube"]["status"], "quota_exhausted")
        self.assertEqual(state["sourceHealth"]["youtube"], "quota_exhausted", "the v1 map keeps its strings")
        made = next(c for c in state["creators"] if c["id"] == "peertube:h/c")
        self.assertEqual((made["discoveries"][0]["method"], made["discoveries"][0]["position"], made["discoveries"][0]["derived"]),
                         ("peertube_search", 4, "legacy"))
        self.assertEqual(made["reach"]["metrics"]["subscriberCount"]["state"], "not_collected")
        _, trend = self.request("GET", "/v1/trend?days=7")
        self.assertEqual(trend["byScan"][-1]["scanId"], scan["id"])
        self.assertEqual(trend["byDay"][-1]["scans"], 1)
        self.assertEqual(state["trend"]["byDay"], trend["byDay"][-14:])
        self.assertGreaterEqual(sum(d["newMaterials"] for d in trend["byDay"]), 2)

    def test_referred_counts_a_new_eligible_refer_once(self):
        declared = capture("youtube:CCCCCCCCCCC", description="Partnerem odcinka jest XTB.", url="https://www.youtube.com/watch?v=CCCCCCCCCCC")
        first = self.scan([evaluate(declared)])
        again = self.scan([evaluate(declared)])
        self.assertEqual((first["referred"], again["referred"]), (1, 0))

    def test_versions_carry_change_kind_and_details(self):
        _, versions = self.request("GET", "/v1/cases/" + VIDEO + "/versions")
        self.assertEqual(versions["versions"][0]["changeKind"], "content")
        self.assertIn("details", versions["versions"][0])


if __name__ == "__main__":
    unittest.main()
