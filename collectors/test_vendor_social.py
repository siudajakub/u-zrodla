"""Offline tests of the one-off vendor sample (ScrapeCreators): parsers on the stored raw responses, error mapping,
credit counter, key handling and replay. No test opens a network connection."""

import gzip
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from collectors import vendor_social as vs
from collectors.adapter import AdapterContext, validate_adapter_result

NOW = "2026-11-21T22:00:00+00:00"
SAMPLE = vs.SAMPLE_DIR


def raw(op, **params):
    log = json.loads((SAMPLE / "requests.json").read_text(encoding="utf-8"))
    for entry in log["requests"]:
        if entry.get("ok") and entry["step"]["op"] == op and all(entry["step"]["params"].get(k) == v for k, v in params.items()):
            return entry, vs._load_raw(SAMPLE, entry)
    raise AssertionError(f"brak odpowiedzi {op} {params}")


def ctx(mode="replay", **options):
    return AdapterContext(mode=mode, state={}, budget=None, fetch=None, clock=lambda: NOW, options=options)


class Fetch:
    """Fake transport: returns queued (status, body dict) pairs and remembers the headers it was given."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        status, body = self.responses.pop(0)
        return status, {}, json.dumps(body).encode()


def ok(credits_left, **extra):
    return 200, {"success": True, "credits_charged": 1, "credits_remaining": credits_left, **extra}


KEY = "k" * 32


class InstagramParserTests(unittest.TestCase):
    def test_firm_profile_posts_are_m2_with_reach_and_flag(self):
        entry, data = raw("ig_profile", handle="xtb_polska")
        user = data["data"]["user"]
        creator = vs.ig_creator(user, entry, NOW)
        self.assertEqual((creator["id"], creator["handle"]), ("instagram:xtb_polska", "@xtb_polska"))
        self.assertEqual(creator["reach"]["metrics"]["followerCount"]["value"], 44817)
        self.assertEqual(creator["firmRelation"]["firm"], "xtb")
        nodes = [e["node"] for e in user["edge_owner_to_timeline_media"]["edges"]]
        item = vs.ig_post(next(n for n in nodes if n["shortcode"] == "DfrQqayEanl"), creator, entry, NOW)
        self.assertEqual(item["id"], "instagram:DfrQqayEanl")
        self.assertEqual(item["module"], "M2")
        self.assertEqual(item["url"], "https://www.instagram.com/p/DfrQqayEanl/")
        self.assertEqual(item["publishedAt"], "2026-11-20T14:00:02+00:00")
        self.assertEqual(item["reach"]["metrics"]["likeCount"]["value"], 22)
        self.assertIs(item["isPaidPartnership"], False)
        self.assertEqual(item["discovery"][0]["method"], "vendor_api")
        self.assertEqual(item["discovery"][0]["vendor"], "scrapecreators")
        self.assertEqual(item["provenance"]["vendor"], "scrapecreators")
        self.assertEqual(item["firmRelation"]["role"], "author")
        self.assertIn("79%", item["description"])
        self.assertTrue(item["textSignals"]["riskWarningInText"])

    def test_third_party_post_is_m1_with_text_label_and_firm_mention(self):
        entry, data = raw("ig_profile", handle="kacper.snela")
        creator = vs.ig_creator(data["data"]["user"], entry, NOW)
        self.assertIsNone(creator["firmRelation"])
        node = next(e["node"] for e in data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
                    if "[współpraca z XTB]" in vs._ig_caption(e["node"]))
        item = vs.ig_post(node, creator, entry, NOW)
        self.assertEqual(item["module"], "M1")
        self.assertEqual(item["firmRelation"]["firm"], "xtb")
        self.assertEqual(item["firmRelation"]["role"], "mentioned")
        self.assertIs(item["isPaidPartnership"], False)
        self.assertTrue(item["disclosure"]["labelled"])
        self.assertIn("[współpraca", item["disclosure"]["textMarkers"])
        self.assertTrue(item["promotion"])
        self.assertEqual(item["discovery"][1 - 1]["query"], {"handle": "kacper.snela"})

    def test_v2_posts_shape_and_missing_fields(self):
        entry = {"step": {"op": "ig_posts", "params": {"handle": "a"}, "role": "creator"}, "url": "u", "bodySha256": "h"}
        user = {"username": "A", "full_name": "A B", "follower_count": 10}
        creator = vs.ig_creator(user, entry, NOW)
        creator["handle"] = "@a"
        item = vs.ig_post({"code": "XyZ", "caption": {"text": "kod XTB #reklama https://xtb.com/x"}, "taken_at": 1795000000,
                           "like_count": 3, "comment_count": 1, "play_count": 9, "is_paid_partnership": True,
                           "usertags": {"in": [{"user": {"username": "xtb_polska"}}]},
                           "coauthor_producers": [{"username": "xtb_polska"}]}, creator, entry, NOW)
        self.assertEqual(item["reach"]["metrics"]["viewCount"]["value"], 9)
        self.assertTrue(item["isPaidPartnership"])
        self.assertEqual(item["taggedAccounts"], ["xtb_polska"])
        self.assertEqual(item["disclosure"]["coauthors"], ["xtb_polska"])
        self.assertEqual(item["hashtags"], ["#reklama"])
        self.assertEqual(item["links"], ["https://xtb.com/x"])
        bare = vs.ig_post({"shortcode": "Nope"}, creator, entry, NOW)  # no caption, no counts, no date, no flag
        self.assertEqual(bare["description"], "")
        self.assertIsNone(bare["publishedAt"])
        self.assertIsNone(bare["isPaidPartnership"])
        self.assertEqual(bare["reach"]["metrics"]["likeCount"]["state"], "not_collected")
        self.assertIsNone(vs.ig_post({}, creator, entry, NOW))
        hidden = vs.ig_post({"shortcode": "H", "edge_media_preview_like": {"count": -1}}, creator, entry, NOW)
        self.assertIsNone(hidden["reach"]["metrics"]["likeCount"]["value"])


class FacebookParserTests(unittest.TestCase):
    def test_page_post(self):
        entry, data = raw("fb_posts", url="https://www.facebook.com/ComparicPL")
        creator = vs.fb_creator(data["posts"][0], entry, NOW)
        self.assertEqual(creator["id"], "facebook:page-100063958146973")
        item = vs.fb_post(data["posts"][0], creator, entry, NOW)
        self.assertEqual(item["id"], f"facebook:{data['posts'][0]['id']}")
        self.assertEqual(item["platform"], "facebook")
        self.assertEqual(item["module"], "M1")
        self.assertEqual(item["publishedAt"], "2026-11-19T15:30:25+00:00")
        self.assertEqual(item["reach"]["metrics"]["reactionCount"]["value"], 2)
        self.assertEqual(item["reach"]["metrics"]["viewCount"]["value"], 1102)
        self.assertIsNone(item["isPaidPartnership"])
        self.assertEqual(item["discovery"][0]["method"], "vendor_api")

    def test_firm_page_and_missing_fields(self):
        entry = {"step": {"op": "fb_posts", "params": {"url": "https://www.facebook.com/xtbpl"}, "role": "firm", "firm": "xtb"},
                 "url": "u", "bodySha256": "h"}
        post = {"id": "7", "permalink": "https://www.facebook.com/xtbpl/posts/7", "text": "Zyskaj z XTB", "author": {"id": "1", "name": "XTB"}}
        creator = vs.fb_creator(post, entry, NOW)
        item = vs.fb_post(post, creator, entry, NOW)
        self.assertEqual(item["module"], "M2")
        self.assertEqual(item["firmRelation"]["role"], "author")
        self.assertIsNone(item["publishedAt"])
        self.assertEqual(item["reach"]["metrics"]["commentCount"]["state"], "not_collected")
        self.assertIsNone(vs.fb_post({"id": "8", "text": "bez adresu"}, creator, entry, NOW))


class AdParserTests(unittest.TestCase):
    def test_company_ads_dynamic_creative_and_detail(self):
        entry, data = raw("fb_company_ads", pageId="155747967133")
        ad = next(a for a in data["results"] if a["ad_archive_id"] == "1421543096020676")
        self.assertEqual(ad["snapshot"]["body"]["text"], "{{product.brand}}")  # the template, not the content
        _e, detail = raw("fb_ad_detail", id="1421543096020676")
        item, creator = vs.ad_capture(ad, entry, NOW, 1, {"1421543096020676": detail})
        self.assertEqual(item["id"], "facebook:ad-1421543096020676")
        self.assertEqual(item["module"], "M2")
        self.assertEqual(item["firmRelation"]["role"], "advertiser")
        self.assertNotIn("{{", item["description"])
        self.assertIn("Nie tylko zarabiaj pieniądze", item["description"])
        self.assertTrue(item["dynamicCreative"])
        self.assertEqual(item["adDeliveryStartDate"], "2025-09-18")
        self.assertEqual(item["adStatus"], "inactive")
        self.assertEqual(item["publisherPlatforms"], ["facebook", "instagram", "audience_network"])
        self.assertEqual(item["linkDomain"], "akcje.xtb.com")
        self.assertEqual(item["callToAction"], "Sign up")
        self.assertEqual(item["euTotalReach"], 5279218)
        self.assertEqual(item["beneficiaryPayers"][0]["payer"], "XTB Online Trading")
        self.assertEqual(item["targeting"]["locations"], ["Poland"])
        self.assertEqual(item["discovery"][0]["endpoint"], "/v1/facebook/adLibrary/company/ads")
        self.assertEqual(creator["id"], "facebook:page-155747967133")
        self.assertEqual(creator["firmRelation"]["firm"], "xtb")
        self.assertTrue(item["textSignals"]["benefitClaim"])
        self.assertFalse(item["textSignals"]["riskWarningInText"])

    def test_ad_without_detail_or_text_and_third_party_brand(self):
        entry = {"step": {"op": "fb_ads_search", "params": {"query": "x"}}, "url": "u", "bodySha256": "h"}
        item, _c = vs.ad_capture({"ad_archive_id": "9", "page_id": "5", "page_name": "Ktoś", "snapshot": {}}, entry, NOW, 1, {})
        self.assertEqual(item["description"], "")
        self.assertIsNone(item["euTotalReach"])
        self.assertEqual(item["reach"]["metrics"]["euTotalReach"]["state"], "not_collected")
        self.assertEqual(item["module"], "M1")
        self.assertIsNone(item["firmRelation"])
        third, _c = vs.ad_capture({"ad_archive_id": "10", "page_id": "6", "page_name": "Afiliant", "publisher_platform": ["INSTAGRAM"],
                                   "snapshot": {"body": {"text": "Załóż konto w Trading 212, kod promocyjny ABC"}}}, entry, NOW, 2, {})
        self.assertEqual(third["module"], "M1")
        self.assertEqual(third["firmRelation"]["firm"], "trading212")
        self.assertEqual(third["firmRelation"]["role"], "mentioned")
        self.assertEqual(third["platform"], "instagram")
        self.assertEqual(third["id"], "instagram:ad-10")
        self.assertIsNone(vs.ad_capture({"page_id": "1"}, entry, NOW, 3, {})[0])


class ErrorAndCreditTests(unittest.TestCase):
    def call(self, status, body=None):
        return vs.call("ig_profile", {"handle": "x"}, KEY, Fetch((status, body or {})))

    def test_error_mapping_and_no_key_in_messages(self):
        for status, code in ((401, "auth"), (403, "auth"), (402, "no_credits"), (429, "rate_limited"), (404, "not_found"),
                             (400, "bad_request"), (500, "error")):
            with self.assertRaises(vs.VendorError) as caught:
                self.call(status, {"message": f"zły klucz {KEY}"})
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn(KEY, str(caught.exception))
        with self.assertRaises(vs.VendorError) as caught:
            self.call(200, {"success": False, "message": "x"})
        self.assertEqual(caught.exception.code, "error")
        with self.assertRaises(vs.VendorError):
            vs.call("ig_profile", {}, KEY, Fetch())  # missing parameter: no request is made
        self.assertEqual(vs.VendorError("rate_limited", "x", 429, retry_after=60).retry_after, 60)

    def test_key_goes_only_into_the_header(self):
        fetch = Fetch(ok(50, data={"user": {}}))
        vs.call("ig_profile", {"handle": "x"}, KEY, fetch)
        url, headers = fetch.calls[0]
        self.assertNotIn(KEY, url)
        self.assertEqual(headers["x-api-key"], KEY)
        self.assertTrue(url.startswith("https://api.scrapecreators.com/v1/instagram/profile?handle=x"))

    def test_collect_counts_credits_stops_at_reserve_and_resumes(self):
        plan = {"steps": [{"op": "ig_profile", "params": {"handle": h}} for h in "abcde"]}
        with tempfile.TemporaryDirectory() as tmp:
            fetch = Fetch(ok(18, data={"x": 1}), ok(17, data={"x": 2}), ok(16, data={"x": 3}), ok(15, data={"x": 4}))
            log = vs.collect(plan, tmp, KEY, 10, reserve=15, pause=0, fetch=fetch, sleep=lambda s: None, clock=lambda: NOW)
            self.assertEqual(log["creditsSpent"], 4)
            self.assertEqual(log["creditsRemaining"], 15)
            self.assertEqual(log["stopped"]["reason"], "reserve")
            self.assertEqual(len(fetch.calls), 4)  # the balance reached the reserve: the fifth call is not made
            # resume: the four done steps are skipped; the balance already at the reserve blocks the rest
            again = vs.collect(plan, tmp, KEY, 10, reserve=15, pause=0, fetch=Fetch(), sleep=lambda s: None, clock=lambda: NOW)
            self.assertEqual(again["creditsSpent"], 4)
            self.assertEqual(again["stopped"]["reason"], "reserve")
            files = sorted(p.name for p in (Path(tmp) / "raw").iterdir())
            self.assertEqual(len(files), 4)
            text = (Path(tmp) / "requests.json").read_text(encoding="utf-8")
            self.assertNotIn(KEY, text)
            self.assertIn('"x-api-key": "REDACTED"', text)

    def test_collect_stops_on_auth_credit_and_rate_errors(self):
        for status, reason in ((401, "auth"), (402, "no_credits"), (429, "rate_limited")):
            with tempfile.TemporaryDirectory() as tmp:
                plan = {"steps": [{"op": "ig_profile", "params": {"handle": "a"}}, {"op": "ig_profile", "params": {"handle": "b"}}]}
                fetch = Fetch((status, {"message": "x"}))
                log = vs.collect(plan, tmp, KEY, 5, pause=0, fetch=fetch, sleep=lambda s: None, clock=lambda: NOW)
                self.assertEqual(log["stopped"]["reason"], reason)
                self.assertEqual(len(fetch.calls), 1)
                self.assertEqual(log["creditsSpent"], 0)

    def test_collect_respects_max_credits_and_survives_a_not_found(self):
        plan = {"steps": [{"op": "ig_profile", "params": {"handle": "a"}}, {"op": "ig_profile", "params": {"handle": "b"}},
                          {"op": "ig_profile", "params": {"handle": "c"}}]}
        with tempfile.TemporaryDirectory() as tmp:
            fetch = Fetch((404, {"message": "brak"}), ok(90, data={}), ok(89, data={}))
            log = vs.collect(plan, tmp, KEY, 1, pause=0, fetch=fetch, sleep=lambda s: None, clock=lambda: NOW)
            self.assertEqual(log["creditsSpent"], 1)
            self.assertEqual(log["stopped"]["reason"], "max_credits")
            self.assertEqual([r["ok"] for r in log["requests"]], [False, True])

    def test_sanitize_drops_comments_followers_and_signed_media(self):
        data = {"topComments": [{"text": "komentarz"}], "profile_pic_url": "https://cdn/x?sig=1", "caption": "ok",
                "edge_media_to_tagged_user": {"edges": [{"node": {"id": "1", "user": {"username": "konto", "full_name": "Osoba"}}}]},
                "edge_media_to_comment": {"count": 3, "edges": [{"node": {"text": "x"}}]},
                "edge_mutual_followed_by": {"edges": [1]}, "nested": [{"video_url": "u", "keep": 1}]}
        clean = vs.sanitize(data)
        self.assertEqual(clean, {"caption": "ok", "edge_media_to_comment": {"count": 3}, "nested": [{"keep": 1}],
                                 "edge_media_to_tagged_user": {"edges": [{"node": {"user": {"username": "konto"}}}]}})


class KeyTests(unittest.TestCase):
    def test_key_file_problems_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t"
            env = {"INVESTWATCH_SCRAPECREATORS_TOKEN_FILE": str(path)}
            self.assertEqual(vs.load_key(env), (None, "brak pliku z kluczem"))
            path.write_text("\n")
            self.assertEqual(vs.load_key(env), (None, "plik z kluczem jest pusty"))
            path.write_text("ma spacje i znaki !!!")
            self.assertEqual(vs.load_key(env)[1], "plik z kluczem ma nieoczekiwany format")
            path.write_text(KEY + "\n")
            self.assertEqual(vs.load_key(env), (KEY, None))

    def test_cli_without_key_is_needs_key_and_makes_no_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.json"
            plan.write_text(json.dumps({"steps": [{"op": "ig_profile", "params": {"handle": "a"}}]}))
            env = {"INVESTWATCH_SCRAPECREATORS_TOKEN_FILE": str(Path(tmp) / "brak")}
            with mock.patch.dict("os.environ", env), mock.patch.object(vs, "_default_fetch", side_effect=AssertionError("sieć")), \
                    mock.patch("sys.stderr"):
                code = vs.main(["collect", "--plan", str(plan), "--max-credits", "1", "--out-dir", str(Path(tmp) / "out")])
            self.assertEqual(code, 3)
            self.assertFalse((Path(tmp) / "out").exists())

    def test_default_transport_refuses_other_hosts(self):
        with self.assertRaises(vs.SourceError):
            vs._default_fetch("https://www.instagram.com/x/", {})
        with self.assertRaises(vs.SourceError):
            vs._default_fetch("https://graph.facebook.com/v21.0/x", {})


class ReplayTests(unittest.TestCase):
    def test_replay_is_the_current_parser_output_of_the_stored_raw_responses(self):
        rebuilt = json.loads(json.dumps(vs.build_result(SAMPLE), ensure_ascii=False, sort_keys=True))
        self.assertEqual(rebuilt, vs.read_sample())

    def test_manifest_hashes_match_files(self):
        from hashlib import sha256
        manifest = json.loads(vs.SAMPLE_MANIFEST.read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            self.assertEqual(sha256((SAMPLE / entry["file"]).read_bytes()).hexdigest(), entry["gzSha256"])
            payload = gzip.decompress((SAMPLE / entry["file"]).read_bytes())
            self.assertEqual(sha256(payload).hexdigest(), entry["storedJsonSha256"])
        self.assertEqual(manifest["replay"]["gzSha256"], sha256(vs.SAMPLE_REPLAY.read_bytes()).hexdigest())
        self.assertEqual(manifest["creditsSpent"] + manifest["creditsRemaining"], vs.TOTAL_CREDITS)
        self.assertLessEqual(manifest["creditsSpent"], 85)

    def test_sample_counts_and_ids(self):
        result = vs.read_sample()
        summary = result["vendorSample"]
        self.assertGreaterEqual(summary["instagram"]["accounts"], 20)
        self.assertGreaterEqual(summary["facebook"]["pages"], 8)
        self.assertGreaterEqual(summary["ads"]["count"], 50)
        ids = [c["id"] for c in result["captures"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith(("instagram:", "facebook:")) for i in ids))
        self.assertEqual(sum(c["module"] == "M2" for c in result["captures"]), summary["m2"])
        self.assertTrue(all(c["module"] == "M2" for c in result["captures"] if c.get("firmRelation", {}) and c["firmRelation"]["role"] in ("author", "advertiser")))
        self.assertTrue(all(c["provenance"]["vendor"] == "scrapecreators" for c in result["captures"]))
        self.assertTrue(all(c["discovery"][0]["method"] == "vendor_api" for c in result["captures"]))

    def test_discarded_noise_and_unrelated_search_ads_are_not_in_the_sample(self):
        result = vs.read_sample()
        authors = {c["author"] for c in result["captures"] if c.get("adId")}
        self.assertNotIn("The Conqueror Challenges", authors)  # query "Lightyear": Buzz Lightyear, discarded
        self.assertNotIn("Polymarket Sports", authors)  # keyword search hit without a firm relation
        self.assertTrue(all(c.get("firmRelation") for c in result["captures"] if c.get("adId") and c["module"] == "M1"))

    @staticmethod
    def find(value, key):
        found = []
        if isinstance(value, dict):
            for k, v in value.items():
                if k == key:
                    found.append(v)
                found.extend(ReplayTests.find(v, key))
        elif isinstance(value, list):
            for v in value:
                found.extend(ReplayTests.find(v, key))
        return found

    def test_raw_files_have_no_comments_and_no_key(self):
        for path in (SAMPLE / "raw").iterdir():
            data = json.loads(gzip.decompress(path.read_bytes()))
            self.assertEqual(self.find(data, "topComments"), [])
            self.assertTrue(all("edges" not in block for block in self.find(data, "edge_media_to_comment")))
            self.assertEqual(self.find(data, "edge_followed_by_edges"), [])
            self.assertTrue(all(set(user) == {"username"} for tag in self.find(data, "edge_media_to_tagged_user")
                                for edge in tag.get("edges", []) for user in [edge["node"]["user"]]))
        key_file = vs.token_path()
        if key_file.exists():
            key = key_file.read_text().strip()
            for path in SAMPLE.rglob("*"):
                if path.is_file():
                    data = path.read_bytes()
                    self.assertNotIn(key.encode(), data)
                    if path.suffix == ".gz":
                        self.assertNotIn(key.encode(), gzip.decompress(data))

    def test_adapter_reads_only_the_sample_and_never_the_network(self):
        with mock.patch.object(vs, "_default_fetch", side_effect=AssertionError("sieć")), \
                mock.patch.object(socket, "socket", side_effect=AssertionError("gniazdo")), \
                mock.patch("collectors.vendor_social.load_key", side_effect=AssertionError("klucz")):
            for mode in ("replay", "live"):
                result = vs.discover(ctx(mode))
                self.assertTrue(result["captures"])
                self.assertTrue(all(c["mode"] == "replay" for c in result["captures"]))
                self.assertTrue(all(c["provenance"]["fixture"].endswith("replay-vendor.json.gz") for c in result["captures"]))
                self.assertNotIn("fixtureNote", result)
        self.assertEqual(validate_adapter_result(result)["errors"], [])

    def test_missing_sample_is_empty_not_an_error(self):
        result = vs.discover(ctx(vendor_social_sample="/nie/ma/replay.json.gz"))
        self.assertEqual((result["captures"], result["status"]), ([], "empty"))

    def test_source_rows_describe_a_dated_sample_from_an_external_service(self):
        rows = {r["id"]: r for r in vs.discover(ctx())["sources"]}
        for sid in ("instagram", "facebook", "facebook-ads", "instagram-ads"):
            self.assertEqual(rows[sid]["sampleDate"], "2026-11-21")
            self.assertIn("próbka datowana z 21 XI zebrana przez usługę zewnętrzną", rows[sid]["message"])
            self.assertIn("import ręczny lub oficjalne API po uzyskaniu dostępu", rows[sid]["message"])
            self.assertEqual(rows[sid]["path"], "vendor_sample")
        self.assertGreater(rows["instagram"]["count"], 0)
        self.assertGreater(rows["facebook-ads"]["count"], 0)
        self.assertEqual(rows["vendor_social"]["creditsRemaining"], 26)


class SignalTests(unittest.TestCase):
    def test_text_signals_and_disclosure_patterns(self):
        self.assertTrue(vs.text_signals("Zarabiaj z nami, zysk gwarantowany")["benefitClaim"])
        self.assertFalse(vs.text_signals("Strategie szachowe w biznesie")["riskWarningInText"])
        self.assertTrue(vs.text_signals("Inwestowanie wiąże się z ryzykiem utraty kapitału")["riskWarningInText"])
        self.assertTrue(vs.text_signals("79% rachunków detalicznych CFD odnotowuje straty")["riskWarningInText"])
        self.assertTrue(vs.text_signals("Rzeczywisty wynik może być inny, także ujemny.")["riskWarningInText"])
        labelled = vs.disclosure_of("#współpracareklamowa #Freedom24", None)
        self.assertTrue(labelled["labelled"])
        self.assertIsNone(labelled["platformFlag"])
        self.assertFalse(vs.disclosure_of("Link w bio", False)["labelled"])
        self.assertTrue(vs.disclosure_of("bez tekstu", True)["labelled"])


if __name__ == "__main__":
    unittest.main()
