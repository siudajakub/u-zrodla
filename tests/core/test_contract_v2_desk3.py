"""Round 3 desk requests: one platform spelling, firm and estimated date in the queue rows, meta_ads and YouTube keys
in the overview (lane H, 21 XI night). Temporary state, no network."""
import unittest
from unittest.mock import patch

from analysis import engine
from api import store
from collectors import discovery
from collectors.m2_market import market_captures
from v2_helpers import StateCase, capture, finding


class Platform(StateCase):
    def test_www_web_and_studio_are_one_value_and_one_filter(self):
        for id, module, platform in (("web:a.pl:m3", "M3", "WWW"), ("web:b.pl/x", "M2", "web"), ("demo-studio", "M3", "Studio"),
                                     ("youtube:AAAAAAAAAAA", "M1", "youtube")):
            cap = capture(id=id, module=module, platform=platform)
            self.put(cap, mode="replay")
        with store.connection() as db:
            cases, _ = store.all_cases(db)
            self.assertEqual({c["id"]: c["platform"] for c in cases},
                             {"web:a.pl:m3": "web", "web:b.pl/x": "web", "demo-studio": "web", "youtube:AAAAAAAAAAA": "youtube"})
            for spelling in ("WWW", "web", "www"):
                listing = store.queue_list(db, "all", platform=spelling)
                self.assertEqual(sorted(i["id"] for i in listing["items"]), ["demo-studio", "web:a.pl:m3", "web:b.pl/x"], spelling)
                self.assertEqual({i["platform"] for i in listing["items"]}, {"web"})

    def test_creators_and_the_report_use_the_same_spelling(self):
        self.scan([], creators=[{"id": "www:x", "name": "X", "platform": "WWW"}])
        with store.connection() as db:
            self.assertEqual(store.creator_view(store.all_objects(db, "creators")[0])["platform"], "web")
        self.assertEqual(store.canonical_platform("tiktok:abc"), "tiktok:abc")


class Rows(StateCase):
    def test_m3_and_m2_rows_carry_the_firm(self):
        m3 = discovery.discover("replay", (), only=["m3-offers-replay"])["captures"][0]
        noble = next(c for c in market_captures()[0] if "noblesecurities.pl/klient-indywidualny" in c["id"])
        self.scan([(m3, engine.analyze(m3)), (noble, engine.analyze(noble))], mode="replay")
        with store.connection() as db:
            rows = {i["id"]: i for name in ("offersM3", "offersM2") for i in store.queue_list(db, name)["items"]}
        self.assertEqual(rows[m3["id"]]["firm"], "mBank S.A.")
        self.assertTrue(rows[noble["id"]]["firm"] and "noble" in rows[noble["id"]]["firm"].lower())

    def test_estimated_date_is_in_the_row(self):
        cap = capture(id="tiktok:7000000000000000001", platform="tiktok", publishedAt=None,
                      publishedAtDerived={"value": "2026-11-01T10:00:00+00:00", "basis": "id_timestamp"})
        self.put(cap, mode="replay")
        plain = capture(id="youtube:BBBBBBBBBBB")
        self.put(plain, mode="replay")
        with store.connection() as db:
            rows = {i["id"]: i for i in store.queue_list(db, "all")["items"]}
        row = rows["tiktok:7000000000000000001"]
        self.assertEqual((row["publishedAtBasis"], row["publishedAtDerived"]["value"]), ("id_timestamp", "2026-11-01T10:00:00+00:00"))
        self.assertEqual(rows["youtube:BBBBBBBBBBB"]["publishedAtBasis"], "platform")


class Overview(StateCase):
    def test_meta_ads_row_is_always_there_with_the_next_step(self):
        state = store.state(2, False, False)
        row = next(s for s in state["sources"] if s["id"] == "meta_ads")
        self.assertEqual(row["status"], "needs_key")
        self.assertTrue(row["nextStep"])
        self.assertEqual(state["sourceHealth"]["meta_ads"], "needs_key")
        self.assertTrue(state["sourceHealthDetail"]["meta_ads"]["optional"])
        self.assertNotEqual(state["sourceHealthSummary"]["status"], "failed")

    def test_a_stored_meta_ads_row_is_not_replaced(self):
        self.scan([], sources=[{"id": "meta_ads", "name": "Meta", "status": "ok", "count": 3}], mode="live")
        row = next(s for s in store.state(2, False, False)["sources"] if s["id"] == "meta_ads")
        self.assertEqual((row["status"], row["count"]), ("ok", 3))

    def test_youtube_keys_are_listed_with_an_empty_ledger(self):
        self.scan([], sources=[{"id": "youtube", "name": "YouTube", "status": "ok", "count": 0}], mode="live")
        with patch("collectors.youtube.load_keys", return_value=["first-key", "second-key"]):
            row = next(s for s in store.state(2, False, False)["sources"] if s["id"] == "youtube")
        keys = row["quota"]["keys"]
        self.assertEqual([k["used"] for k in keys], [0, 0])
        self.assertEqual(len({k["keyId"] for k in keys}), 2)
        self.assertTrue(all(len(k["keyId"]) == 8 for k in keys))
        with patch("collectors.youtube.load_keys", return_value=[]):
            row = next(s for s in store.state(2, False, False)["sources"] if s["id"] == "youtube")
        self.assertFalse((row.get("quota") or {}).get("keys"))
