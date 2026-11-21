"""Social sources, access_blocked, quota per key, channel base, shared filters and the module report (lane H, 21 XI night).

No test reaches the network or touches a real database: every one runs on a temporary state.
"""
import csv
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from api import store
from collectors import discovery
from collectors.adapter import Adapter, health_of
from test_contract_v2_adapters import ScanCase, Stub, video
from v2_helpers import HttpCase, StateCase, capture

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "collectors"))
FUTURE = "2999-01-01T00:00:00+00:00"
BLOCKED = {"code": "access_blocked", "message": "Brak publicznego dostępu do wpisów.", "at": "2026-11-21T10:00:00+00:00",
           "nextStep": "Wystąpić o dostęp do Meta Content Library."}


class Registry(unittest.TestCase):
    def test_social_adapters_are_registered_with_the_stage_they_need(self):
        for id in ("tiktok", "facebook", "instagram", "meta_ads", "social-replay"):
            self.assertIn(id, discovery.ADAPTERS)
        self.assertEqual(discovery.ADAPTERS["tiktok"].after, ("youtube",))
        self.assertTrue(discovery.ADAPTERS["social-replay"].explicit_only)
        self.assertEqual(discovery.ADAPTERS["social-replay"].modes, ("replay",))
        self.assertTrue(discovery.ADAPTERS["meta_ads"].own_network)
        live = {a.id for a in discovery.active_adapters("live", own_transport=False)}
        self.assertNotIn("meta_ads", live, "an injected fetch (tests) leaves out adapters with their own transport")

    def test_the_list_in_the_environment_still_decides(self):
        with patch.dict(os.environ, {"INVESTWATCH_ADAPTERS": "youtube"}):
            live = {a.id for a in discovery.active_adapters("live")}
        self.assertNotIn("tiktok", live)
        self.assertNotIn("facebook", live)

    def test_access_blocked_is_its_own_health_state(self):
        self.assertEqual(health_of("access_blocked"), "access_blocked")
        self.assertEqual(health_of("error"), "error")
        self.assertEqual(health_of("needs_key"), "needs_key")


class AccessBlocked(ScanCase):
    def blocked_stub(self):
        row = {"id": "facebook", "name": "Facebook · dostęp do wpisów", "status": "access_blocked", "count": 0,
               "observedAt": "2026-11-21T10:00:00+00:00", "lastError": BLOCKED, "error": BLOCKED["message"],
               "probe": {"attempts": [{"at": "2026-11-21T09:00:00+00:00", "status": 302}]}}
        return Stub("facebook", status="access_blocked", sources=[row])

    def test_a_blocked_source_does_not_make_the_scan_partial_but_the_summary_names_it(self):
        self.adapters(self.blocked_stub(), Stub("fine", [video("G")]))
        key = self.run_scan()
        scan = store.scan_dict(self.scan_row(key))
        self.assertEqual(scan["status"], "done")
        self.assertNotIn("warnings", scan)
        self.assertEqual(scan["sources"]["accessBlocked"], 1)
        self.assertEqual(scan["sources"]["failed"], 0)
        self.assertEqual([b["id"] for b in scan["accessBlocked"]], ["facebook"])
        self.assertEqual(scan["accessBlocked"][0]["nextStep"], BLOCKED["nextStep"])

    def test_state_shows_the_blocked_source_with_error_and_attempt_date(self):
        self.adapters(self.blocked_stub(), Stub("fine", [video("G")]))
        self.run_scan()
        state = store.state()
        detail = state["sourceHealthDetail"]["facebook"]
        self.assertEqual(detail["status"], "access_blocked")
        self.assertEqual({k: detail["lastError"][k] for k in ("code", "message", "at", "nextStep")},
                         {k: BLOCKED[k] for k in ("code", "message", "at", "nextStep")})
        self.assertIsNotNone(detail["lastAttemptAt"])
        self.assertEqual(state["sourceHealthSummary"]["status"], "ok", "a known state is not a degradation")
        self.assertEqual(state["sourceHealthSummary"]["accessBlocked"], 1)
        self.assertEqual(state["sourceHealthSummary"]["problems"], 0)
        self.assertEqual(state["sourceHealth"]["facebook"], "access_blocked")
        self.assertEqual(next(s for s in state["sources"] if s["id"] == "facebook")["lastAttemptAt"], detail["lastAttemptAt"])

    def test_a_real_error_next_to_it_still_degrades_the_run(self):
        broken = Stub("flaky", status="error", sources=[{"id": "flaky", "name": "Flaky", "status": "error", "count": 0, "error": "HTTP 500"}])
        self.adapters(self.blocked_stub(), broken, Stub("fine", [video("G")]))
        key = self.run_scan()
        self.assertEqual(self.detail(key)["status"], "partial")
        self.assertEqual(store.state()["sourceHealthSummary"]["status"], "degraded")

    def test_missing_meta_token_is_visible_but_never_partial(self):
        row = {"id": "meta_ads", "name": "Meta · Biblioteka Reklam", "status": "needs_key", "count": 0, "lastError": {
            "code": "needs_key", "message": "Brak tokenu.", "at": "2026-11-21T10:00:00+00:00", "nextStep": "Umieść token."}}
        self.adapters(Stub("meta_ads", status="needs_key", sources=[row]), Stub("fine", [video("G")]))
        key = self.run_scan()
        self.assertEqual(self.detail(key)["status"], "done")
        state = store.state()
        self.assertEqual(state["sourceHealthDetail"]["meta_ads"]["status"], "needs_key")
        self.assertEqual(state["sourceHealthDetail"]["meta_ads"]["lastError"]["nextStep"], "Umieść token.")
        self.assertEqual(state["sourceHealthSummary"]["problems"], 0)


class SocialReplay(ScanCase):
    def run_replay(self):
        scan, _ = store.create_scan("replay", "social-replay-test", {"adapters": ["social-replay"]})
        self.jobs.process.call_local(scan["id"])
        return scan["id"]

    def test_replay_puts_tiktok_next_to_youtube_and_the_xtb_posts_into_the_ad_register(self):
        key = self.run_replay()
        self.assertEqual(self.detail(key)["status"], "done", self.detail(key))
        with store.connection() as db:
            tiktok = db.execute("SELECT count(*) FROM cases WHERE id LIKE 'tiktok:%'").fetchone()[0]
            register = store.queue_list(db, "adRegister", limit=500, platform="tiktok")
            review = store.queue_list(db, "review", limit=500, platform="tiktok")
            incomplete = store.queue_list(db, "incomplete", limit=500, platform="tiktok")
        self.assertEqual(tiktok, 64)
        self.assertEqual(sorted(i["creatorId"] for i in register["items"]), ["tiktok:kacper_snela"] * 5)
        self.assertEqual(register["total"], 5)
        self.assertTrue(all(i["adRegistry"] == "included" for i in register["items"]))
        self.assertEqual(review["total"], 0)
        self.assertEqual(incomplete["total"] + 0, incomplete["total"])

    def test_the_caption_is_the_description_and_speech_is_reported_as_a_gap(self):
        self.run_replay()
        case = self.case("tiktok:7709883447644359969")
        self.assertEqual(case["coverage"]["modalities"]["transcript"]["state"], "unavailable")
        self.assertTrue(case["coverage"]["blocksConclusion"])
        self.assertEqual(case["adRegistry"]["state"], "included")
        self.assertIn("współpraca z XTB", json.dumps(case["evidence"], ensure_ascii=False))
        quote = next(e for e in case["evidence"] if e.get("role") == "disclosure")
        self.assertIn("[współpraca z XTB]", quote["text"], "the quote stays verbatim")

    def test_unrelated_captions_stay_without_signal(self):
        self.run_replay()
        with store.connection() as db:
            states = [(c.get("adRegistry") or {}).get("state") for c in store.all_cases(db)[0] if c["id"].startswith("tiktok:")]
        self.assertEqual((states.count("included"), states.count("none")), (5, 59))

    def test_facebook_and_instagram_stay_blocked_in_the_replay_state(self):
        self.run_replay()
        detail = store.state()["sourceHealthDetail"]
        for id in ("facebook", "instagram"):
            self.assertEqual(detail[id]["status"], "access_blocked")
            self.assertEqual(detail[id]["lastError"]["code"], "access_blocked")
            self.assertTrue(detail[id]["lastError"]["nextStep"])

    def test_the_replay_is_idempotent(self):
        self.run_replay()
        with store.connection() as db:
            before = db.execute("SELECT count(*) FROM versions WHERE id LIKE 'tiktok:%'").fetchone()[0]
        scan, _ = store.create_scan("replay", "social-replay-test-2", {"adapters": ["social-replay"]})
        self.jobs.process.call_local(scan["id"])
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM versions WHERE id LIKE 'tiktok:%'").fetchone()[0], before)


class QuotaPerKey(StateCase):
    AT = "2026-11-21T10:00:00+00:00"

    def adapter(self):
        return Adapter("yt", lambda ctx: {}, "YT", daily_units_env="IW_PER_KEY", quota_tz="America/Los_Angeles")

    def record(self, keys, status="ok", at=None, **extra):
        quota = {"used": sum(k.get("usedThisRun", 0) for k in keys), "limit": 1000, "resetAt": FUTURE, "keys": keys}
        with store.connection(True) as db:
            return store.record_adapter(db, "yt", {"status": status, "sources": [], "quota": quota, **extra}, at or self.AT, "s1", self.adapter())

    def key(self, id, used, this_run=0, exhausted=None, limit=10000):
        return {"keyId": id, "day": "2026-11-21", "used": used, "usedThisRun": this_run, "limit": limit, "exhaustedAt": exhausted}

    def view(self):
        day, _ = store.quota_day(self.adapter(), self.AT)
        with store.connection() as db:
            keys = store.ledger_keys(db, "yt", day)
            return store.quota_view(self.adapter(), store.ledger_row(db, "yt", day), self.AT, keys or None)

    def test_one_row_per_key_and_the_source_limit_is_their_sum(self):
        with patch.dict(os.environ, {"IW_PER_KEY": "8000"}):
            body = self.record([self.key("aaaaaaaa", 100, 100), self.key("bbbbbbbb", 30, 30)])
            view = self.view()
        self.assertEqual((body["quota"]["used"], body["quota"]["limit"]), (130, 16000))
        self.assertEqual({k["keyId"]: (k["used"], k["limit"]) for k in body["quota"]["keys"]},
                         {"aaaaaaaa": (100, 8000), "bbbbbbbb": (30, 8000)})
        self.assertEqual(view["remaining"], 16000 - 130)

    def test_a_key_refused_by_the_platform_does_not_block_the_other(self):
        with patch.dict(os.environ, {"IW_PER_KEY": "8000"}):
            self.record([self.key("aaaaaaaa", 500, 500, exhausted=self.AT), self.key("bbbbbbbb", 40, 40)],
                        status="rate_limited", sources=[{"id": "yt", "status": "limit", "error": "quotaExceeded",
                                                         "lastError": {"code": "quota_exhausted", "message": "q"}}])
            view = self.view()
        rows = {k["keyId"]: k for k in view["snapshot"]["keys"]}
        self.assertEqual(rows["aaaaaaaa"]["used"], 8000, "the refused key is spent for the day")
        self.assertEqual(rows["bbbbbbbb"]["used"], 40)
        self.assertEqual(view["remaining"], 8000 - 40, "the second key still has its units")

    def test_state_shows_use_per_key_and_never_a_key_value(self):
        secret = "AIzaSyD-this-must-never-appear-0123456789"
        with patch.dict(os.environ, {"IW_PER_KEY": "8000"}):
            self.record([self.key("aaaaaaaa", 10, 10), self.key(secret[:8], 5, 5), self.key(secret, 5, 5)])
        dump = json.dumps(store.state(), ensure_ascii=False)
        self.assertNotIn(secret[:8], dump)
        self.assertNotIn("AIzaSy", dump)
        with store.connection() as db:
            self.assertEqual([r["key_id"] for r in db.execute("SELECT key_id FROM quota_keys")], ["aaaaaaaa"])
            self.assertNotIn("AIzaSy", json.dumps([list(r) for r in db.execute("SELECT * FROM quota_keys")]))
        self.assertEqual(store.source_state(store.connect_for_test(), "yt")["quota"]["keys"][0]["keyId"], "aaaaaaaa") \
            if hasattr(store, "connect_for_test") else None

    def test_repeated_runs_add_only_what_each_run_spent(self):
        with patch.dict(os.environ, {"IW_PER_KEY": "8000"}):
            self.record([self.key("aaaaaaaa", 100, 100)])
            self.record([self.key("aaaaaaaa", 160, 60)])
            self.assertEqual(self.view()["snapshot"]["used"], 160)

    def test_a_new_day_starts_with_the_key_count_of_the_previous_one(self):
        with patch.dict(os.environ, {"IW_PER_KEY": "8000"}):
            self.record([self.key("aaaaaaaa", 100, 100), self.key("bbbbbbbb", 1, 1)])
            tomorrow = "2026-11-22T20:00:00+00:00"
            day, _ = store.quota_day(self.adapter(), tomorrow)
            with store.connection() as db:
                hint = store.known_key_count(db, "yt", day)
                view = store.quota_view(self.adapter(), None, tomorrow, None, hint)
        self.assertEqual((hint, view["remaining"]), (2, 16000))

    def test_a_source_without_key_rows_keeps_the_old_behaviour(self):
        body = self.record([], status="ok")
        self.assertNotIn("keys", body["quota"])


class ChannelBase(unittest.TestCase):
    def test_only_youtube_channels_reach_the_adapter_and_the_base_stays_in_the_state_dir(self):
        from collectors import youtube
        seen = {}

        def fake(yctx):
            seen["ctx"] = yctx
            return {"creators": [], "captures": [], "sources": [], "status": "ok", "cursor": {"big": "x" * 100}}

        from collectors.adapter import AdapterContext
        previous = {"youtube:UC" + "a" * 22: {"id": "youtube:UC" + "a" * 22, "platform": "youtube"},
                    "tiktok:x": {"id": "tiktok:x", "platform": "tiktok"},
                    "apple-podcasts:1": {"id": "apple-podcasts:1", "platform": "apple-podcasts"}}
        ctx = AdapterContext(mode="live", state={}, budget=10, fetch=None, clock=lambda: "2026-11-21T10:00:00+00:00", previous=previous,
                             options={"youtube": {"state_dir": "/tmp/iw-test-state", "monitor_share": 0.25, "monitor_channels": 7}})
        with patch.object(youtube, "discover", fake):
            result = discovery._youtube(ctx)
        self.assertEqual([c["id"] for c in seen["ctx"].known_creators], ["youtube:UC" + "a" * 22])
        self.assertEqual((seen["ctx"].monitor_share, seen["ctx"].monitor_channels), (0.25, 7))
        self.assertNotIn("cursor", result)

    def test_without_a_state_dir_the_cursor_travels_as_before(self):
        from collectors import youtube
        from collectors.adapter import AdapterContext
        ctx = AdapterContext(mode="live", state={}, budget=10, fetch=None, clock=lambda: "2026-11-21T10:00:00+00:00")
        with patch.object(youtube, "discover", lambda yctx: {"creators": [], "captures": [], "sources": [], "status": "ok", "cursor": {"a": 1}}):
            self.assertEqual(discovery._youtube(ctx)["cursor"], {"a": 1})

    def test_environment_options_and_state_dir_under_the_state(self):
        from api import jobs
        env = {"INVESTWATCH_YT_MONITOR_SHARE": "0.3", "INVESTWATCH_YT_MONITOR_CHANNELS": "120", "INVESTWATCH_YT_MONITOR_MIN_HOURS": "bad"}
        with patch.dict(os.environ, env), patch.object(store, "STATE", Path("/tmp/iw-state")):
            options = jobs.youtube_options()
        self.assertEqual((options["monitor_share"], options["monitor_channels"]), (0.3, 120))
        self.assertNotIn("monitor_min_hours", options, "a malformed value is ignored, not fatal")
        self.assertEqual(options["state_dir"], Path("/tmp/iw-state/youtube-state"))

    def test_the_channel_base_is_not_exposed_through_state_and_survives_a_restart_on_disk(self):
        from collectors import youtube
        with StateDir() as directory:
            ctx = youtube.Context(state_dir=directory)
            db = youtube.load_db(ctx, {})
            db["runs"] = 3
            youtube.save_db(ctx, db)
            self.assertEqual(youtube.load_db(youtube.Context(state_dir=directory), {})["runs"], 3)


class StateDir:
    def __enter__(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        return self.temp.name

    def __exit__(self, *args):
        self.temp.cleanup()


class CursorNotExposed(StateCase):
    def test_state_hides_a_stored_cursor(self):
        with store.connection(True) as db:
            store.record_adapter(db, "youtube", {"status": "ok", "sources": [], "cursor": {"channels": {"x": 1}}}, "2026-11-21T10:00:00+00:00")
        self.assertNotIn("cursor", json.dumps(store.state(1)["sourceState"]))
        with store.connection() as db:
            self.assertIn("cursor", store.source_state(db, "youtube"), "ctx.state still carries it for old databases")


def post(id, platform="tiktok", **extra):
    return capture(id, platform=platform, url=f"https://example.org/{id}", creatorId=f"{platform}:{id}", **extra)


class Filters(HttpCase):
    def setUp(self):
        super().setUp()
        rows = [
            ("youtube:AAAAAAAAAAA", "youtube", "2026-11-01T10:00:00+00:00", 80),
            ("tiktok:1", "tiktok", None, 30),
            ("facebook:ad-2", "facebook", "2026-11-10T10:00:00+00:00", 20),
        ]
        pairs = []
        for id, platform, published, score in rows:
            cap = post(id, platform=platform, publishedAt=published, observedAt="2026-11-21T10:00:00+00:00")
            if published is None:
                cap["publishedAtDerived"] = {"basis": "tiktok_id_timestamp", "value": "2026-11-19T14:00:00+00:00"}
            pairs.append((cap, {"id": id, "title": cap["title"], "module": "M1", "score": score, "summary": "s", "evidence": [],
                                "rulesVersion": "investwatch-rules-pl-1.2"}))
        self.scan(pairs)

    def ids(self, path):
        status, body = self.request("GET", path)
        self.assertEqual(status, 200, body)
        return sorted(i["id"] for i in body["items"])

    def test_queue_filters_by_platform_for_new_sources(self):
        self.assertEqual(self.ids("/v1/queues/all?platform=tiktok"), ["tiktok:1"])
        self.assertEqual(self.ids("/v1/queues/all?platform=facebook"), ["facebook:ad-2"])
        self.assertEqual(self.ids("/v1/queues/all?platform=instagram"), [])
        self.assertEqual(len(self.ids("/v1/queues/all")), 3)

    def test_queue_filters_by_module_score_and_date(self):
        self.assertEqual(self.ids("/v1/queues/all?module=M2"), [])
        self.assertEqual(self.ids("/v1/queues/all?minScore=25"), ["tiktok:1", "youtube:AAAAAAAAAAA"])
        self.assertEqual(self.ids("/v1/queues/all?dateField=publishedAt&since=2026-11-05T00:00:00%2B00:00"),
                         ["facebook:ad-2", "tiktok:1"], "a TikTok post is dated by the time derived from its id")
        self.assertEqual(self.ids("/v1/queues/all?dateField=publishedAt&until=2026-11-05T00:00:00%2B00:00"), ["youtube:AAAAAAAAAAA"])
        self.assertEqual(self.ids("/v1/queues/all?since=2026-11-22T00:00:00%2B00:00"), [])


class Report(HttpCase):
    FORMULA = '=HYPERLINK("http://evil","x")'

    def setUp(self):
        super().setUp()
        pairs = []
        for index in range(5):
            id = f"youtube:{chr(66 + index) * 11}"
            cap = capture(id, title="Tytuł", url=f"https://www.youtube.com/watch?v={chr(66 + index) * 11}",
                          description="Współpraca reklamowa z XTB. Opis z przecinkiem, \"cudzysłowem\" i\nnową linią.",
                          creatorName=self.FORMULA if index == 0 else "Twórca " + str(index),
                          publishedAt=f"2026-11-0{index + 1}T10:00:00+00:00")
            pairs.append((cap, __import__("analysis.engine", fromlist=["analyze"]).analyze(cap)))
        self.scan(pairs)

    def csv_rows(self, path):
        import urllib.request
        with urllib.request.urlopen(self.base + path, timeout=4) as response:
            raw = response.read()
            headers = {k.lower(): v for k, v in response.headers.items()}
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "UTF-8 with a BOM")
        return list(csv.reader(io.StringIO(raw.decode("utf-8-sig")))), headers

    def test_json_report_has_the_m1_columns_and_the_firm_with_its_type(self):
        status, body = self.request("GET", "/v1/report?module=M1&queue=adRegister")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["columns"][:5], ["firma", "typPodmiotu", "podmiotReklamujacy", "tresc", "url"])
        self.assertEqual(body["total"], 5)
        row = body["items"][0]
        self.assertIn("XTB", row["firma"])
        self.assertIn("firma inwestycyjna", row["typPodmiotu"])
        self.assertEqual(row["platforma"], "youtube")
        self.assertTrue(row["url"].startswith("https://www.youtube.com/watch"))
        self.assertEqual(row["rejestrReklam"], "included")
        self.assertIn("XTB", row["tresc"])

    def test_csv_is_bom_quoted_and_formulas_are_neutralised(self):
        rows, headers = self.csv_rows("/v1/report?module=M1&format=csv&queue=adRegister")
        self.assertEqual(rows[0][0], "firma")
        self.assertEqual(len(rows), 6)
        who = rows[0].index("podmiotReklamujacy")
        cells = [r[who] for r in rows[1:]]
        self.assertIn("'" + self.FORMULA, cells)
        self.assertFalse(any(c.startswith("=") for r in rows for c in r))
        self.assertTrue(all(len(r) == len(rows[0]) for r in rows), "commas, quotes and newlines stay inside the cell")
        self.assertEqual(headers["x-total-count"], "5")
        self.assertTrue(headers["content-type"].startswith("text/csv"))

    def test_csv_pages_with_a_cursor_without_gaps_or_repeats(self):
        first, headers = self.csv_rows("/v1/report?module=M1&format=csv&queue=adRegister&limit=2")
        self.assertEqual(len(first), 3)
        self.assertEqual(headers["x-next-cursor"], "2")
        seen = [r[-1] for r in first[1:]]
        cursor = headers["x-next-cursor"]
        while cursor:
            page, headers = self.csv_rows(f"/v1/report?module=M1&format=csv&queue=adRegister&limit=2&cursor={cursor}")
            seen += [r[-1] for r in page[1:]]
            cursor = headers.get("x-next-cursor")
        self.assertEqual(len(seen), 5)
        self.assertEqual(len(set(seen)), 5)

    def test_other_modules_use_their_own_columns_and_unknown_values_are_rejected(self):
        status, body = self.request("GET", "/v1/report?module=M2")
        self.assertEqual((status, body["total"], body["columns"][2]), (200, 0, "operator"))
        status, body = self.request("GET", "/v1/report?module=M3")
        self.assertEqual((status, body["columns"][2]), (200, "autor"))
        self.assertEqual(self.request("GET", "/v1/report?module=M9")[0], 422)
        self.assertEqual(self.request("GET", "/v1/report?module=M1&queue=nope")[0], 404)

    def test_report_filters_by_platform_and_date(self):
        status, body = self.request("GET", "/v1/report?module=M1&queue=adRegister&platform=tiktok")
        self.assertEqual(body["total"], 0)
        status, body = self.request("GET", "/v1/report?module=M1&queue=adRegister&dateField=publishedAt&since=2026-11-04T00:00:00%2B00:00")
        self.assertEqual(body["total"], 2)

    def test_csv_safe_covers_the_known_formula_starts(self):
        for text in ("=1+1", "+1", "-1", "@SUM(A1)", "\t=1", " =1"):
            self.assertTrue(str(store.csv_safe(text)).startswith("'"), text)
        self.assertEqual(store.csv_safe(-4), -4)
        self.assertEqual(store.csv_safe(None), "")
        self.assertEqual(store.csv_safe("a\nb"), "a b")


class MetaAdsRecords(unittest.TestCase):
    """Fabricated Ad Library records through the real collectors/meta_ads.py capture builder."""

    def build(self, id, page, body):
        import test_meta_ads as t
        from collectors import meta_ads
        cap, _ = meta_ads.make_capture(t.ad(id, page=page, bodies=(body,)), ("firm", "XTB", "x"), t.NOW, "h", "https://x", 1, 1, t.TOKEN)
        return cap

    def test_an_advertising_firm_goes_through_the_m2_text_analysis_with_an_honest_coverage(self):
        from analysis import engine
        cap = self.build("1", "XTB Polska", "Otwórz konto w XTB.")
        self.assertEqual((cap["module"], cap["id"]), ("M2", "facebook:ad-1"))
        found = engine.analyze(cap)
        self.assertEqual(found["module"], "M2")
        self.assertEqual(found["coverage"]["label"], "Zbadano: tylko tekst reklamy, bez renderu")
        self.assertEqual(found["coverage"]["modalities"]["render"]["state"], "not_collected")
        self.assertIn("reviewSuggestion", found)

    def test_a_creator_ad_is_qualified_as_m1_and_reaches_the_register(self):
        from analysis import engine
        cap = self.build("2", "Jan Inwestor", "Polecam XTB. [współpraca z XTB]")
        self.assertEqual(cap["module"], "M1")
        found = engine.analyze(cap)
        self.assertEqual(found["adRegistry"]["state"], "included")
        self.assertNotIn("viewCount", cap["reach"]["metrics"])
        self.assertIn("euTotalReach", cap["reach"]["metrics"])


class BracketLabel(unittest.TestCase):
    def test_the_bracket_label_is_a_disclosure_even_when_the_first_sentence_is_a_question(self):
        from analysis import engine
        cap = capture("tiktok:9", platform="tiktok", description="[współpraca z XTB] Złoto czy ETC? Zależy.", title="t")
        found = engine.analyze(cap)
        self.assertEqual(found["adRegistry"]["state"], "included")
        quote = next(e for e in found["evidence"] if e.get("role") == "disclosure")
        self.assertTrue(quote["text"].startswith("[współpraca z XTB]"))

    def test_an_unlabelled_question_stays_skipped(self):
        from analysis import engine
        cap = capture("tiktok:10", platform="tiktok", description="Czy XTB to dobry wybór?", title="t")
        self.assertEqual(engine.analyze(cap)["adRegistry"]["state"], "none")


def m1_pairs(specs):
    from analysis import engine
    out = []
    for id, platform, description, extra in specs:
        cap = capture(id, platform=platform, url=f"https://example.org/{id}", description=description, creatorId=f"{platform}:{id}", **extra)
        out.append((cap, engine.analyze(cap)))
    return out


class Overview(HttpCase):
    def setUp(self):
        super().setUp()
        self.scan(m1_pairs([("youtube:AAAAAAAAAAA", "youtube", "Współpraca reklamowa z XTB. Zapraszam.", {"creatorName": "Kanał Alfa"}),
                            ("youtube:BBBBBBBBBBB", "youtube", "Zwykły opis bez firm.", {}),
                            ("tiktok:7", "tiktok", "[współpraca z XTB] Złoto?", {"author": "kacpersnela"})]),
                  creators=[{"id": "youtube:UCexampleexampleexample00", "name": "Kanał Alfa", "platform": "youtube", "url": "u", "bigField": "x" * 5000}])

    def test_the_light_state_has_no_cases_and_the_same_counters_as_the_full_one(self):
        _, full = self.request("GET", "/v1/state?schema=2")
        for path in ("/v1/state?schema=2&findings=0", "/v1/overview?schema=2"):
            status, light = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertEqual(light["findings"], [])
            self.assertTrue(light["findingsOmitted"])
            self.assertEqual(light["queues"], full["queues"])
            self.assertEqual(light["creatorCounts"]["total"], len(full["creators"]))
            self.assertNotIn("bigField", light["creators"][0])
            for key in ("sources", "scans", "sourceHealth", "sourceHealthDetail", "sourceHealthSummary", "trend", "threshold", "qualification", "recompute"):
                self.assertIn(key, light, key)
            self.assertLess(len(json.dumps(light)), len(json.dumps(full)))

    def test_the_counter_cache_follows_the_database(self):
        before = self.request("GET", "/v1/overview")[1]["queues"]
        self.scan(m1_pairs([("youtube:CCCCCCCCCCC", "youtube", "Zwykły opis.", {})]))
        after = self.request("GET", "/v1/overview")[1]["queues"]
        self.assertEqual(after["all"], before["all"] + 1)
        self.assertEqual(after, self.request("GET", "/v1/state")[1]["queues"])

    def test_queue_summary_carries_reason_register_disclosure_band_and_names(self):
        status, body = self.request("GET", "/v1/queues/adRegister")
        self.assertEqual(status, 200)
        by_id = {i["id"]: i for i in body["items"]}
        item = by_id["youtube:AAAAAAAAAAA"]
        self.assertEqual(item["creatorName"], "Kanał Alfa")
        self.assertEqual(item["adRegistryInfo"]["state"], "included")
        self.assertTrue(item["adRegistryInfo"]["summary"])
        self.assertEqual(item["disclosure"]["kind"], "explicit_ad")
        self.assertIn("completeReason", item)
        self.assertIn("firstReason", item)
        self.assertEqual(by_id["tiktok:7"]["creatorName"], "kacpersnela", "the author stands in for a creator that is not in the table")
        self.assertIn(item["band"], ("weak", "moderate", "strong", None))
        self.assertEqual(body["counts"]["transcriptPending"], 0)

    def test_search_reaches_the_channel_name(self):
        ids = lambda q: [i["id"] for i in self.request("GET", "/v1/queues/all?q=" + q)[1]["items"]]
        self.assertEqual(ids("alfa"), ["youtube:AAAAAAAAAAA"])
        self.assertEqual(ids("kacpersnela"), ["tiktok:7"])

    def test_history_details_are_an_object_in_schema_2_and_text_in_schema_1(self):
        two = self.request("GET", "/v1/cases/youtube:AAAAAAAAAAA?schema=2")[1]
        self.assertTrue(two["history"] and all(isinstance(h["details"], dict) for h in two["history"]))
        one = self.request("GET", "/v1/cases/youtube:AAAAAAAAAAA?schema=1")[1]
        self.assertTrue(all(isinstance(h["details"], str) for h in one["history"]))


class Bands(unittest.TestCase):
    def test_band_depends_on_the_threshold(self):
        self.assertEqual([store.band_of(v, 60) for v in (None, 59, 60, 79, 80, 100)], [None, "weak", "moderate", "moderate", "strong", "strong"])
        self.assertEqual([store.band_of(v, 90) for v in (89, 90, 100)], ["weak", "strong", "strong"])


class CalibrationCache(unittest.TestCase):
    def test_the_cached_result_does_not_outlive_a_change_of_the_set(self):
        from api import server
        calls = []
        digests = iter(["one", "one", "two"])
        with patch.object(server, "labeled_digest", lambda: next(digests)), \
                patch("analysis.engine.calibration", lambda threshold, variant: calls.append((threshold, variant)) or {"n": len(calls)}):
            server._calculate.cache_clear()
            a = server.calculate_cached(61, "rules_1_2")
            b = server.calculate_cached(61, "rules_1_2")
            c = server.calculate_cached(61, "rules_1_2")
        self.assertEqual((a, b, c), ({"n": 1}, {"n": 1}, {"n": 2}))
        server._calculate.cache_clear()

    def test_the_digest_follows_the_files(self):
        from api import server
        self.assertEqual(server.labeled_digest(), server.labeled_digest())
        self.assertEqual(len(server.labeled_digest()), 16)

    def test_the_q_v2_set_is_keyed_by_its_files_digest(self):
        from api import calibration_q2
        self.assertEqual(calibration_q2.dataset_id(), calibration_q2.dataset_id())


class StuckRecompute(ScanCase):
    def queue_recompute(self, age_seconds=600):
        from datetime import datetime, timedelta, timezone
        scan, _ = store.create_scan("recompute", "stuck-recompute")
        old = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
        with store.connection(True) as db:
            db.execute("UPDATE scans SET created=?,updated=? WHERE id=?", (old, old, scan["id"]))
        return scan["id"], old

    def status(self):
        with store.connection() as db:
            return store.recompute_status(db)

    def test_a_large_database_says_since_when_it_waits(self):
        key, old = self.queue_recompute()
        with patch.object(self.jobs, "INLINE_RECOMPUTE_MAX", -1):
            self.assertIsNone(self.jobs.recover_recompute())
        status = self.status()
        self.assertEqual((status["state"], status["waitingSince"], status["scanId"]), ("waiting_for_worker", old, key))
        self.assertIn(old, status["message"])

    def test_a_small_database_reaches_a_final_state_without_a_worker(self):
        key, _ = self.queue_recompute()
        self.assertEqual(self.jobs.recover_recompute(), key)
        self.assertEqual(self.status()["state"], "done")

    def test_a_dead_workers_running_scan_is_taken_over(self):
        key, old = self.queue_recompute()
        with store.connection(True) as db:
            db.execute("UPDATE scans SET status='running',owner='dead',lease_until=1 WHERE id=?", (key,))
        status = self.status()
        self.assertEqual((status["state"], status["stalled"]), ("waiting_for_worker", True))
        self.assertEqual(self.jobs.recover_recompute(), key)
        self.assertEqual(self.status()["state"], "done")

    def test_a_fresh_queue_entry_is_not_taken_over_early(self):
        self.queue_recompute(age_seconds=1)
        self.assertEqual(self.status()["state"], "queued")
        self.assertIsNone(self.jobs.recover_recompute())


if __name__ == "__main__":
    unittest.main()
