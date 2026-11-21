"""Manual Meta import (lane H, 21 XI late evening): adapter registration, one source row with paths[], text-only
qualification of imported records and POST /v1/import/meta.

No test reaches the network (the import reads saved files) or a real database: every one runs on a temporary state.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from api import import_meta, jobs, store  # jobs first: its queue file must open in the process state, not in a test directory
from collectors import discovery
from collectors.adapter import merge_source_rows
from test_contract_v2_adapters import ScanCase
from v2_helpers import HttpCase

ROOT = Path(__file__).resolve().parents[2]
ALT = ROOT / "fixtures/raw/discovery/social-2026-11-21/alt"
ADS_FILE = ALT / "metaadlib-browser-body.txt"
IG_FILE = ALT / "ig-profile-embed.html"
BLOCKED = {"code": "access_blocked", "message": "Brak publicznego dostępu do wpisów.", "at": "2026-11-21T10:00:00+00:00",
           "nextStep": "Meta Content Library."}


def row(id, status, **extra):
    return {"id": id, "name": id.split("-")[0].capitalize() + " · test", "status": status, "count": extra.pop("count", 0),
            "observedAt": "2026-11-21T22:00:00+00:00", **extra}


class Registry(unittest.TestCase):
    def test_import_is_live_and_its_dated_sample_is_a_separate_explicit_replay_adapter(self):
        self.assertEqual(discovery.ADAPTERS["meta_import"].modes, ("live",))
        self.assertFalse(discovery.ADAPTERS["meta_import"].own_network)
        replay = discovery.ADAPTERS["meta-import-replay"]
        self.assertEqual((replay.modes, replay.explicit_only, replay.own_network), (("replay",), True, False))
        self.assertEqual(discovery.planned_steps("replay", ["meta-import-replay"]), ["discover:meta-import-replay"])
        self.assertNotIn("meta-import-replay", discovery.planned_steps("replay"), "a default replay does not mix the sample in")
        self.assertIn("discover:meta_import", discovery.planned_steps("live"))

    def test_the_worker_orders_the_replay_next_to_the_social_one(self):
        source = (ROOT / "api/jobs.py").read_text(encoding="utf-8")
        self.assertIn('submit("replay","bootstrap-meta-import-replay-v1",{"adapters":["meta-import-replay"]})', source)


class SourcePaths(unittest.TestCase):
    def rows(self, with_import=True, import_rows=None):
        out = [("meta_ads", row("facebook-ads", "needs_key", lastError={"code": "needs_key", "message": "Brak tokenu.",
                                                                          "nextStep": "Umieść token."})),
               ("meta_ads", row("instagram-ads", "needs_key", lastError={"code": "needs_key", "message": "Brak tokenu."})),
               ("facebook", row("facebook", "access_blocked", lastError=BLOCKED)),
               ("instagram", row("instagram", "access_blocked", lastError=BLOCKED))]
        if with_import:
            out += import_rows or [
                ("meta_import", row("facebook-ads", "ok", count=22, sampleDate="2026-11-21", message="22 reklamy")),
                ("meta_import", row("instagram-ads", "ok", count=0, sampleDate="2026-11-21")),
                ("meta_import", row("instagram", "ok", count=6, sampleDate="2026-11-21", message="6 postów"))]
        return merge_source_rows(out)

    def by_id(self, rows):
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)), "one row per source")
        return {r["id"]: r for r in rows}

    def test_one_row_per_source_with_the_best_path_and_a_sentence_for_the_desk(self):
        rows = self.by_id(self.rows())
        instagram = rows["instagram"]
        self.assertEqual((instagram["status"], instagram["bestPath"], instagram["count"]), ("ok", "manual_import", 6))
        self.assertEqual({p["path"]: p["status"] for p in instagram["paths"]},
                         {"manual_import": "ok", "organic_posts": "access_blocked"})
        self.assertEqual(instagram["pathsSummary"],
                         "Instagram: próbka z importu ręcznego (6 postów, 21 XI) · wpisy automatycznie: blokada dostępu")
        ads = rows["facebook-ads"]
        self.assertEqual({p["path"]: p["status"] for p in ads["paths"]}, {"manual_import": "ok", "ad_library_api": "needs_key"})
        self.assertIn("API reklam: brak tokenu", ads["pathsSummary"])
        for path in ads["paths"]:
            self.assertEqual(set(path) - {"row"}, {"path", "status", "detail", "at", "nextStep", "count", "sampleDate"})
            self.assertTrue(path["nextStep"])

    def test_the_first_path_in_the_list_is_the_best_one(self):
        paths = self.by_id(self.rows())["instagram"]["paths"]
        self.assertEqual(paths[0]["path"], "manual_import")

    def test_without_a_sample_an_empty_import_never_hides_the_block(self):
        rows = self.by_id(self.rows(import_rows=[("meta_import", row("instagram", "empty", message="brak plików")),
                                                  ("meta_import", row("facebook-ads", "empty"))]))
        self.assertEqual(rows["instagram"]["status"], "access_blocked")
        self.assertEqual(rows["facebook-ads"]["status"], "needs_key")
        self.assertIn("import ręczny: brak plików", rows["instagram"]["pathsSummary"])
        self.assertEqual(rows["facebook"]["status"], "access_blocked")
        self.assertEqual([p["path"] for p in rows["facebook"]["paths"]], ["organic_posts"])

    def test_the_import_alone_still_reports_one_path(self):
        rows = merge_source_rows([("meta_import", row("instagram", "ok", count=6, sampleDate="2026-11-21"))])
        self.assertEqual([p["path"] for p in rows[0]["paths"]], ["manual_import"])

    def test_other_sources_are_untouched(self):
        plain = row("youtube", "ok")
        self.assertEqual(merge_source_rows([("youtube", plain)]), [plain])


class StoredPaths(ScanCase):
    """Replays and imports arrive in separate scans: the stored row keeps the paths the new scan does not report."""

    def apply(self, rows, mode="live"):
        with store.connection(True) as db:
            store.apply_scan(db, [], [], merge_source_rows(rows), mode)

    def test_a_later_import_keeps_the_block_and_the_token_state_of_the_other_paths(self):
        self.apply([("meta_ads", row("facebook-ads", "needs_key")), ("instagram", row("instagram", "access_blocked", lastError=BLOCKED))])
        self.apply([("meta_import", row("facebook-ads", "ok", count=22, sampleDate="2026-11-21")),
                    ("meta_import", row("instagram", "ok", count=6, sampleDate="2026-11-21"))])
        state = store.state(findings=False)
        rows = {s["id"]: s for s in state["sources"]}
        self.assertEqual({p["path"] for p in rows["instagram"]["paths"]}, {"manual_import", "organic_posts"})
        self.assertEqual({p["path"] for p in rows["facebook-ads"]["paths"]}, {"manual_import", "ad_library_api"})
        self.assertEqual(rows["instagram"]["status"], "ok")
        self.assertTrue(all("row" not in p for s in state["sources"] for p in s.get("paths", [])), "snapshots stay in the database")
        self.assertEqual(state["sourceHealth"]["instagram"], "ok")
        self.assertNotIn("instagram", state["sourceHealthSummary"]["accessBlockedSources"])

    def test_a_new_reading_of_a_path_replaces_the_old_one(self):
        self.apply([("instagram", row("instagram", "access_blocked", lastError=BLOCKED)),
                    ("meta_import", row("instagram", "ok", count=6, sampleDate="2026-11-21"))])
        self.apply([("meta_import", row("instagram", "ok", count=9, sampleDate="2026-11-22"))])
        instagram = next(s for s in store.state(findings=False)["sources"] if s["id"] == "instagram")
        self.assertEqual((instagram["count"], len(instagram["paths"])), (9, 2))

    def test_a_row_stored_before_paths_existed_becomes_the_organic_path(self):
        with store.connection(True) as db:
            for id, status in (("instagram", "access_blocked"), ("facebook", "access_blocked")):
                db.execute("INSERT INTO sources VALUES(?,?)", (id, store.dump({"id": id, "name": id.capitalize(), "status": status,
                                                                                "mode": "replay", "lastError": BLOCKED})))
        rows = {s["id"]: s for s in store.state(findings=False)["sources"]}
        self.assertEqual([p["path"] for p in rows["facebook"]["paths"]], ["organic_posts"], "derived on read for the desk")
        self.assertEqual(rows["facebook"]["paths"][0]["derived"], "legacy")
        self.apply([("meta_import", row("instagram", "ok", count=6, sampleDate="2026-11-21"))], mode="replay")
        instagram = next(s for s in store.state(findings=False)["sources"] if s["id"] == "instagram")
        self.assertEqual((instagram["status"], [p["path"] for p in instagram["paths"]]), ("ok", ["manual_import", "organic_posts"]))
        self.assertIn("wpisy automatycznie: blokada dostępu", instagram["pathsSummary"])


class ReplayOfTheSample(ScanCase):
    def run_replay(self, request_id="meta-replay"):
        scan, _ = store.create_scan("replay", request_id, {"adapters": ["meta-import-replay"]})
        self.jobs.process.call_local(scan["id"])
        return scan["id"]

    def test_the_dated_sample_fills_the_m2_offers_of_facebook_and_instagram(self):
        key = self.run_replay()
        self.assertEqual(self.detail(key)["status"], "done", self.detail(key))
        with store.connection() as db:
            facebook = store.queue_list(db, "offersM2", limit=500, platform="facebook")
            instagram = store.queue_list(db, "offersM2", limit=500, platform="instagram")
            report = store.report_list(db, "M2", platform="facebook")
        self.assertEqual((facebook["total"], instagram["total"]), (21, 5))  # one ad and one post fall outside the Polish investment scope (see m2_scope)
        self.assertEqual(report["total"], 21)
        self.assertTrue(all(i["importLabel"] == "import ręczny" and i["origin"] == "replay" for i in facebook["items"] + instagram["items"]))

    def test_the_sample_is_idempotent(self):
        self.run_replay()
        with store.connection() as db:
            before = db.execute("SELECT count(*) FROM versions").fetchone()[0]
        self.run_replay("meta-replay-2")
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM versions").fetchone()[0], before)

    def test_the_state_row_of_instagram_names_the_manual_import_as_its_best_path(self):
        self.run_replay()
        rows = {s["id"]: s for s in store.state(findings=False)["sources"]}
        self.assertEqual(rows["instagram"]["bestPath"], "manual_import")
        self.assertEqual(rows["instagram"]["count"], 6)
        self.assertEqual(rows["facebook-ads"]["count"], 22)

    def test_an_ad_with_a_benefit_claim_and_no_warning_in_its_text_is_not_a_strong_flag_but_a_creative_check(self):
        self.run_replay()
        case = self.case("facebook:ad-1421543096020676")
        suggestion = case["reviewSuggestion"]
        self.assertEqual((suggestion["state"], suggestion["criterionId"]), ("uncertain", "3"))
        self.assertIn("Uzupełnij: sprawdź kreację", suggestion["reason"])
        self.assertIn("grafice lub wideo", suggestion["reason"])
        self.assertEqual(case["route"], "complete")
        self.assertLess(case["score"], 60, "no strong flag from the text alone")
        self.assertEqual(case["coverage"]["label"], "Zbadano: tylko tekst reklamy z zapisanej strony, bez obrazu, wideo i renderu")
        self.assertEqual(case["coverage"]["modalities"]["render"]["state"], "not_collected")
        with store.connection() as db:
            item = next(i for i in store.queue_list(db, "offersM2", limit=500, platform="facebook")["items"]
                        if i["id"] == "facebook:ad-1421543096020676")
        self.assertIn("sprawdź kreację", item["reason"])

    def test_a_caption_with_the_risk_warning_keeps_the_gap_and_says_so(self):
        self.run_replay()
        case = self.case("instagram:DfrQqayEanl")
        self.assertEqual(case["module"], "M2")
        self.assertEqual(case["coverage"]["label"], "Zbadano: tylko tekst podpisu posta z zapisanej strony, bez obrazu i renderu")
        self.assertEqual(case["reviewSuggestion"]["state"], "unavailable")
        self.assertIn("nie wykryto twierdzenia", case["reviewSuggestion"]["reason"])

    def test_an_ad_without_any_claim_says_what_was_not_examined(self):
        cap = {"importLabel": "import ręczny", "adId": "1", "adBody": "Otwórz konto.", "description": "Otwórz konto."}
        finding = {"module": "M2", "reviewSuggestion": {"state": "unavailable", "reason": "Brak pomiaru."}}
        import_meta.qualify_import(cap, finding)
        self.assertEqual(finding["reviewSuggestion"]["state"], "unavailable")
        self.assertIn("nie wykryto twierdzenia", finding["reviewSuggestion"]["reason"])

    def test_a_claim_with_a_warning_in_the_text_still_needs_the_render_to_judge_their_distance(self):
        cap = {"importLabel": "import ręczny", "adId": "1", "adBody": "Zyskaj z nami. 79% rachunków traci pieniądze."}
        finding = {"module": "M2", "reviewSuggestion": {"state": "unavailable", "reason": "Brak pomiaru."}}
        import_meta.qualify_import(cap, finding)
        self.assertEqual(finding["reviewSuggestion"]["state"], "unavailable")
        self.assertIn("ostrzeżenie", finding["reviewSuggestion"]["reason"])

    def test_what_the_text_analysis_itself_concluded_is_kept(self):
        cap = {"importLabel": "import ręczny", "adId": "1", "adBody": "Zyskaj. KNF poleca nas."}
        finding = {"module": "M2", "checkCounts": {"obserwacja": 1}, "reviewSuggestion": {"state": "unavailable", "reason": "x"}}
        import_meta.qualify_import(cap, finding)
        self.assertEqual(finding["reviewSuggestion"], {"state": "unavailable", "reason": "x"})

    def test_records_without_the_import_label_are_not_touched(self):
        finding = {"module": "M2", "reviewSuggestion": {"state": "unavailable"}}
        self.assertIs(import_meta.qualify_import({"adId": "1", "adBody": "Zyskaj"}, finding), finding)
        self.assertNotIn("coverage", finding)


class Names(unittest.TestCase):
    def test_a_path_in_the_name_cannot_leave_the_folder(self):
        for hostile in ("../../etc/passwd.txt", "..\\..\\windows\\system32\\x.html", "/abs/olute/path.htm", ".hidden.txt",
                        "a b;rm -rf.txt", "ł ó ź.html", "x" * 400 + ".txt", ""):
            name = import_meta.safe_name(hostile)
            self.assertRegex(name, r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,90}$")
            self.assertTrue(name.lower().endswith((".html", ".htm", ".txt")), name)
        self.assertEqual(import_meta.safe_name("../../etc/passwd.txt"), "passwd.txt")

    def test_multipart_gives_its_first_file(self):
        body = (b"--B\r\nContent-Disposition: form-data; name=\"note\"\r\n\r\nx\r\n--B\r\n"
                b"Content-Disposition: form-data; name=\"file\"; filename=\"../a.txt\"\r\nContent-Type: text/plain\r\n\r\nhello\r\n--B--\r\n")
        self.assertEqual(import_meta.split_multipart(body, "multipart/form-data; boundary=B"), ("../a.txt", b"hello"))


class Endpoint(HttpCase):
    def setUp(self):
        super().setUp()
        from api import jobs
        self.jobs = jobs
        self.enterContext(patch("collectors.youtube.urlopen", side_effect=AssertionError("network is off in tests")))
        for target, kw in (("api.listen.sample_audio", {"return_value": {"id": "asr", "name": "asr", "status": "empty", "count": 0}}),
                           ("collectors.m2_archive.staged_captures", {"return_value": ([], [], [])}),
                           ("analysis.semantic.suggest", {"return_value": {"status": "unavailable"}})):
            self.enterContext(patch(target, **kw))

    def post(self, data, filename="xtb.txt", content_type="text/plain; charset=utf-8"):
        from urllib.parse import quote
        req = Request(self.base + "/v1/import/meta?filename=" + quote(filename), data=data, method="POST",
                      headers={"Content-Type": content_type})
        try:
            with urlopen(req, timeout=60) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, {"raw": raw.decode("utf-8", "replace")}

    def queue(self, name="offersM2", platform="facebook"):
        with store.connection() as db:
            return store.queue_list(db, name, limit=500, platform=platform)

    def test_the_ad_library_page_gives_22_ads_in_the_m2_offers_with_the_import_label(self):
        status, body = self.post(ADS_FILE.read_bytes())
        self.assertEqual(status, 200, body)
        self.assertEqual((body["kind"], body["ads"], body["posts"], body["recognized"], body["new"]), ("ad_library", 22, 0, 22, 22))
        self.assertEqual(body["scan"]["status"], "done")
        self.assertEqual(len(body["sha256"]), 64)
        self.assertTrue(body["storedAs"].startswith(body["sha256"][:16] + "-"))
        self.assertTrue(any("platformy" in w.lower() for w in body["warnings"]))
        offers = self.queue()
        self.assertEqual(offers["total"], 21)
        self.assertTrue(all(i["importLabel"] == "import ręczny" and i["origin"] == "live" and i["module"] == "M2" for i in offers["items"]))
        with store.connection() as db:
            report = store.report_list(db, "M2", platform="facebook")
        self.assertEqual(report["total"], 21)
        self.assertTrue((store.STATE / "meta-import" / body["storedAs"]).is_file())
        self.assertEqual((store.STATE / "meta-import" / body["storedAs"]).read_bytes(), ADS_FILE.read_bytes())

    def test_a_second_import_of_the_same_file_creates_no_duplicates(self):
        _, first = self.post(ADS_FILE.read_bytes())
        with store.connection() as db:
            versions = db.execute("SELECT count(*) FROM versions").fetchone()[0]
            cases = db.execute("SELECT count(*) FROM cases").fetchone()[0]
        status, second = self.post(ADS_FILE.read_bytes())
        self.assertEqual(status, 200, second)
        self.assertTrue(second["alreadyImported"])
        self.assertEqual((second["new"], second["existing"]), (0, 22))
        self.assertEqual(second["storedAs"], first["storedAs"])
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM versions").fetchone()[0], versions)
            self.assertEqual(db.execute("SELECT count(*) FROM cases").fetchone()[0], cases)
        self.assertEqual(self.queue()["total"], 21)
        self.assertEqual(len(list((store.STATE / "meta-import").iterdir())), 1)

    def test_the_same_content_under_another_name_adds_no_ads_either(self):
        self.post(ADS_FILE.read_bytes(), filename="a.txt")
        status, body = self.post(ADS_FILE.read_bytes() + b"\n", filename="b.txt")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["new"], 0)
        self.assertEqual(self.queue()["total"], 21)

    def test_instagram_profile_embed_gives_six_posts_and_the_source_row_names_the_import(self):
        status, body = self.post(IG_FILE.read_bytes(), filename="ig.html", content_type="text/html")
        self.assertEqual(status, 200, body)
        self.assertEqual((body["kind"], body["posts"], body["ads"]), ("instagram_profile", 6, 0))
        self.assertEqual(self.queue(platform="instagram")["total"], 5)
        instagram = next(s for s in store.state(findings=False)["sources"] if s["id"] == "instagram")
        self.assertEqual((instagram["status"], instagram["bestPath"]), ("ok", "manual_import"))
        self.assertIn("próbka z importu ręcznego (6 postów", instagram["pathsSummary"])

    def test_rubbish_gives_422_with_a_readable_message_and_stores_nothing(self):
        for data in (b"to nie jest zapisana strona Meta", b"<html><body>Zaloguj sie</body></html>", b""):
            status, body = self.post(data, filename="smiec.html")
            self.assertEqual(status, 422, body)
            self.assertTrue(body["detail"])
        self.assertEqual(list((store.STATE / "meta-import").glob("*")) if (store.STATE / "meta-import").exists() else [], [])
        self.assertEqual(self.queue()["total"], 0)

    def test_only_text_files_of_the_listed_kinds_are_accepted(self):
        self.assertEqual(self.post(b"x", filename="a.png", content_type="image/png")[0], 415)
        self.assertEqual(self.post(ADS_FILE.read_bytes(), filename="a.txt", content_type="application/pdf")[0], 415)
        self.assertEqual(self.post(ADS_FILE.read_bytes(), filename="a.exe", content_type="text/plain")[0], 415)
        self.assertEqual(self.post(b"\x00\x01\x02binary", filename="a.txt")[0], 415)
        self.assertEqual(self.queue()["total"], 0)

    def test_a_path_traversal_in_the_name_is_stored_under_a_safe_name(self):
        status, body = self.post(ADS_FILE.read_bytes(), filename="../../../../tmp/evil.txt")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["file"], "evil.txt")
        self.assertRegex(body["storedAs"], r"^[0-9a-f]{16}-evil\.txt$")
        folder = store.STATE / "meta-import"
        self.assertEqual([p.name for p in folder.iterdir()], [body["storedAs"]])
        case = self.case(self.queue()["items"][0]["id"])
        self.assertEqual(case["provenance"]["sourceFile"], body["storedAs"])

    def test_a_file_over_the_limit_is_refused(self):
        with patch.object(import_meta.meta_import, "MAX_FILE", 1000):
            status, body = self.post(ADS_FILE.read_bytes())
        self.assertEqual(status, 413, body)

    def test_multipart_works_like_the_raw_body(self):
        boundary = "XBOUNDARY"
        data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"../xtb.txt\"\r\n"
                f"Content-Type: text/plain\r\n\r\n").encode() + ADS_FILE.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        status, body = self.post(data, filename="form.txt", content_type=f"multipart/form-data; boundary={boundary}")
        self.assertEqual(status, 200, body)
        self.assertEqual((body["ads"], body["file"]), (22, "xtb.txt"))

    def test_without_a_worker_a_large_file_stays_queued_and_the_answer_says_so(self):
        with patch.object(import_meta, "INLINE_MAX", 10):
            status, body = self.post(ADS_FILE.read_bytes())
        self.assertEqual(status, 202, body)
        self.assertEqual(body["scan"]["status"], "queued")
        self.assertEqual(body["ads"], 22)

    def test_the_import_runs_only_the_meta_import_adapter(self):
        _, body = self.post(ADS_FILE.read_bytes())
        with store.connection() as db:
            steps = [s["step"] for s in store.scan_steps(db, body["scan"]["id"])]
        self.assertEqual([s for s in steps if s.startswith("discover:")], ["discover:meta_import"])


if __name__ == "__main__":
    unittest.main()
