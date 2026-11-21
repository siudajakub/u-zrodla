import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import unittest

from collectors import meta_ads
from collectors.adapter import AdapterContext, validate_adapter_result
from collectors.social import discover_facebook, discover_instagram

NOW = "2026-11-21T20:00:00+00:00"
TOKEN = "EAAB" + "secretTOKENvalue" * 3


def ctx(fetch=None, state=None, budget=None, **options):
    base = {"pause": 0, "sleep": lambda s: None, "meta_token": TOKEN, "meta_fetch": fetch,
            "env": {"INVESTWATCH_META_TOKEN_FILE": "/nonexistent/meta.token"}}
    base.update(options)
    return AdapterContext(mode="live", state=state or {}, budget=budget, fetch=None, clock=lambda: NOW, options=base)


def ad(id, page="Inwestor Jan", page_id="111", platforms=("FACEBOOK",), bodies=("Zainwestuj z nami",), **extra):
    return {"id": id, "page_id": page_id, "page_name": page, "publisher_platforms": list(platforms),
            "ad_creative_bodies": list(bodies), "ad_creative_link_captions": ["xtb.com"],
            "ad_creative_link_titles": ["Otwórz konto"], "ad_delivery_start_time": "2026-11-01",
            "eu_total_reach": 12345, "languages": ["pl"],
            "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?id={id}&access_token={TOKEN}", **extra}


def page(rows, after=None):
    body = {"data": rows}
    if after:
        body["paging"] = {"cursors": {"after": after, "before": "b"}, "next": f"https://graph.facebook.com/v21.0/ads_archive?after={after}&access_token={TOKEN}"}
    return json.dumps(body).encode()


def router(mapping, calls):
    def fetch(url):
        calls.append(url)
        query = parse_qs(urlsplit(url).query)
        key = (query["search_terms"][0], query.get("after", [None])[0])
        reply = mapping.get(key, mapping.get((key[0], "*"), page([])))
        if isinstance(reply, tuple):
            return reply
        return 200, {}, reply
    return fetch


class MetaAdsTests(unittest.TestCase):
    def test_no_token_is_needs_key_with_next_step_and_no_request(self):
        calls = []
        result = meta_ads.discover(ctx(router({}, calls), meta_token=None))
        self.assertEqual((result["status"], calls), ("needs_key", []))
        row = result["sources"][0]
        self.assertEqual((row["id"], row["status"], row["lastError"]["code"]), ("meta_ads", "needs_key", "needs_key"))
        self.assertIn("meta.token", row["lastError"]["nextStep"])
        self.assertEqual({r["id"]: r["status"] for r in result["sources"][1:]}, {"facebook-ads": "needs_key", "instagram-ads": "needs_key"})
        self.assertEqual(validate_adapter_result(result)["errors"], [])

    def test_token_file_is_read_outside_the_repo(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "meta.token")
            Path(path).write_text(TOKEN + "\n")
            os.chmod(path, 0o600)
            self.assertEqual(meta_ads.load_token({"INVESTWATCH_META_TOKEN_FILE": path}), (TOKEN, None))
            self.assertFalse(meta_ads.token_file_mode_warning({"INVESTWATCH_META_TOKEN_FILE": path}))
            os.chmod(path, 0o644)
            self.assertTrue(meta_ads.token_file_mode_warning({"INVESTWATCH_META_TOKEN_FILE": path}))
            Path(path).write_text("zły token ze spacjami")
            self.assertIsNone(meta_ads.load_token({"INVESTWATCH_META_TOKEN_FILE": path})[0])

    def test_firm_page_third_party_payer_instagram_only_and_second_page(self):
        calls = []
        first = page([ad("1", page="XTB S.A.", page_id="10", platforms=("FACEBOOK", "INSTAGRAM")),
                      ad("2", page="Inwestor Jan", platforms=("INSTAGRAM",),
                         beneficiary_payers=[{"beneficiary": "Jan", "payer": "XTB S.A."}])], after="CUR1")
        second = page([ad("3", page="Kasia Finanse", page_id="222", bodies=("Kod rabatowy, więcej na xtb.com",))])
        result = meta_ads.discover(ctx(router({("XTB", None): first, ("XTB", "CUR1"): second}, calls)))
        checked = validate_adapter_result(result)
        self.assertEqual(checked["errors"], [])
        by_id = {c["id"]: c for c in result["captures"]}
        self.assertEqual(set(by_id), {"facebook:ad-1", "instagram:ad-2", "facebook:ad-3"})
        self.assertEqual((by_id["facebook:ad-1"]["module"], by_id["facebook:ad-1"]["firmRelation"]["role"]), ("M2", "advertiser"))
        self.assertEqual(by_id["facebook:ad-1"]["publisherPlatforms"], ["facebook", "instagram"])
        self.assertEqual((by_id["instagram:ad-2"]["platform"], by_id["instagram:ad-2"]["module"], by_id["instagram:ad-2"]["firmRelation"]["role"]),
                         ("instagram", "M1", "payer"))
        self.assertEqual(by_id["facebook:ad-3"]["firmRelation"]["role"], "mentioned")
        first_ad = by_id["facebook:ad-1"]
        self.assertEqual(first_ad["url"], "https://www.facebook.com/ads/library/?id=1")
        self.assertEqual(first_ad["publishedAt"], "2026-11-01T00:00:00+00:00")
        self.assertEqual(first_ad["reach"]["metrics"]["euTotalReach"]["value"], 12345)
        self.assertEqual(by_id["facebook:ad-3"]["links"], [])  # caption "xtb.com" has no scheme: no link invented
        path = first_ad["discovery"][0]
        self.assertEqual((path["method"], path["query"], path["rank"], path["page"]), ("ad_library", "XTB", 1, 1))
        self.assertTrue(any("after=CUR1" in c for c in calls))
        platform_rows = {r["id"]: r["count"] for r in result["sources"] if r["id"].endswith("-ads")}
        self.assertEqual(platform_rows, {"facebook-ads": 2, "instagram-ads": 1})

    def test_token_never_appears_in_result_urls_or_messages(self):
        calls = []
        result = meta_ads.discover(ctx(router({("XTB", None): page([ad("1")])}, calls)))
        self.assertNotIn(TOKEN, json.dumps(result, ensure_ascii=False))
        self.assertIn("access_token=REDACTED", json.dumps(result))
        self.assertTrue(any(TOKEN in c for c in calls))  # sent on the wire, stored nowhere
        broken = meta_ads.discover(ctx(router({}, []), meta_fetch=lambda url: (400, {}, json.dumps(
            {"error": {"message": f"Invalid token {TOKEN}", "type": "OAuthException", "code": 190}}).encode())))
        self.assertNotIn(TOKEN, json.dumps(broken))

    def test_oauth_190_stops_with_reason(self):
        calls = []
        error = json.dumps({"error": {"message": "Error validating access token: Session has expired", "type": "OAuthException", "code": 190}}).encode()
        result = meta_ads.discover(ctx(lambda url: calls.append(url) or (400, {}, error)))
        self.assertEqual((result["status"], len(calls)), ("error", 1))
        self.assertEqual(result["sources"][0]["lastError"]["code"], "oauth_190")
        self.assertIn("meta.token", result["sources"][0]["lastError"]["nextStep"])
        self.assertEqual(result["captures"], [])

    def test_rate_limit_613_sets_retry_and_keeps_cursor(self):
        calls = []
        limited = json.dumps({"error": {"message": "Calls to this api have exceeded the rate limit.", "code": 613}}).encode()
        first = page([ad("1")], after="CUR9")
        def fetch(url):
            calls.append(url)
            if "after=CUR9" in url:
                return 400, {}, limited
            return 200, {}, first
        result = meta_ads.discover(ctx(fetch))
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(result["retryAt"], "2026-11-21T21:00:00+00:00")
        self.assertEqual(len(result["captures"]), 1)
        self.assertEqual(result["resume"]["next"]["after"], "CUR9")
        self.assertEqual(result["sources"][0]["lastError"]["code"], "rate_limited")

    def test_budget_partial_then_resume_and_cache(self):
        calls = []
        fetch = router({}, calls)
        first = meta_ads.discover(ctx(fetch, budget=3))
        self.assertEqual((first["status"], len(calls)), ("partial", 3))
        self.assertIsNotNone(first["resume"]["next"])
        calls.clear()
        second = meta_ads.discover(ctx(fetch, state={"resume": first["resume"]}, budget=2))
        asked = [parse_qs(urlsplit(u).query)["search_terms"][0] for u in calls]
        queries = [q for _k, q, _f in meta_ads.queries()]
        self.assertEqual(asked, queries[3:5])  # the first three are fresh in the cache
        self.assertEqual(second["status"], "partial")

    def test_all_queries_fresh_in_cache_costs_nothing(self):
        done = {q: NOW for _k, q, _f in meta_ads.queries()}
        calls = []
        result = meta_ads.discover(ctx(router({}, calls), state={"resume": {"done": done, "next": None}}))
        self.assertEqual((calls, result["status"]), ([], "ok"))

    def test_query_list_has_firms_and_polish_phrases_within_limits(self):
        asked = meta_ads.queries()
        names = [q for _k, q, _f in asked]
        self.assertIn("XTB", names)
        self.assertIn("konto maklerskie", names)
        self.assertTrue(all(len(q) <= 100 for q in names))
        self.assertEqual(len(names), len(set(n.lower() for n in names)))

    def test_organic_rows_stay_blocked_and_separate_from_ads(self):
        fb = discover_facebook(ctx())["sources"][0]
        ig = discover_instagram(ctx())["sources"][0]
        for row, platform in ((fb, "facebook"), (ig, "instagram")):
            self.assertEqual((row["id"], row["status"], row["blockedScope"]), (platform, "access_blocked", "organic_posts"))
            self.assertIn("wpisy organiczne", row["name"])
            self.assertIn("Biblioteka Reklam", row["lastError"]["message"] + row["scope"])


if __name__ == "__main__":
    unittest.main()
