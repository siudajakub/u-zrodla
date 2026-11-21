import gzip
import hashlib
import json
import re
from pathlib import Path
import tempfile
import unittest

from collectors import meta_import
from collectors.adapter import AdapterContext, validate_adapter_result

ALT = meta_import.SAMPLE_DIR / "alt"
AD_TEXT = ALT / "metaadlib-browser-body.txt"
IG_PROFILE = ALT / "ig-profile-embed.html"
NOW = "2026-11-22T08:00:00+00:00"
SAVED = "2026-11-21T21:04:00+00:00"

EN_PAGE = """Meta Ad Library
Ad Library
Poland
Results: ~1,200
Inactive
Library ID: 111111111111111
Sep 18, 2025 - Sep 1, 2026
Platforms
Instagram
This ad has multiple versions.
3 ads use this creative and text
See summary details
Inwestor Jan
Sponsored
Earn passive income. Join our course now
BESTCOURSE.COM
Learn to trade
Start today
Learn More
Active
Library ID: 222222222222222
Started running on Oct 8, 2026
Platforms
Facebook
Messenger
See summary details
XTB Online Investing
Sponsored
Invest with zero commission
Sign Up
See more
System status
"""

NO_DATES = """Biblioteka reklam
Nieaktywna
Identyfikator biblioteki: 333333333333333
Platformy
Zobacz szczegóły reklamy
Konto Testowe
Sponsorowane
Tylko treść bez reszty
"""


def ctx(mode="live", **options):
    return AdapterContext(mode=mode, state={}, budget=None, fetch=None, clock=lambda: NOW, options=options)


def write(directory, name, text):
    path = Path(directory) / name
    path.write_text(text, encoding="utf-8")
    return path


def as_html(text, spans=False):
    rows = []
    for line in text.splitlines():
        if spans and line.startswith("Identyfikator biblioteki:"):
            rows.append("<div><span>Identyfikator biblioteki:</span> <span>%s</span></div>" % line.split(":")[1].strip())
        else:
            rows.append("<div><span>%s</span></div>" % (line.replace("&", "&amp;") or "&nbsp;"))
    return ("<html><head><title>x</title><script>var a='Identyfikator biblioteki: 999999999999999';</script></head>"
            "<body><style>.a{}</style>%s</body></html>" % "".join(rows))


class AdLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = meta_import.read_file(AD_TEXT, saved_at=SAVED, imported_at=NOW)
        cls.ads = {c["adId"]: c for c in cls.result["captures"]}

    def test_all_cards_of_the_saved_text_become_captures(self):
        self.assertEqual((self.result["status"], self.result["count"], len(self.ads)), ("ok", 22, 22))
        self.assertEqual(self.result["page"], {"resultCount": 14000, "interfaceLanguage": "pl"})
        self.assertTrue(all(c["id"] == f"facebook:ad-{c['adId']}" for c in self.ads.values()))

    def test_first_card_fields_and_meta_ads_shape(self):
        ad = self.ads["1421543096020676"]
        self.assertEqual((ad["author"], ad["module"], ad["adStatus"], ad["adDeliveryStartDate"], ad["adDeliveryStopDate"]),
                         ("XTB Online Investing", "M2", "inactive", "2025-09-18", "2026-09-01"))
        self.assertEqual((ad["publishedAt"], ad["publishedAtPrecision"]), ("2025-09-18T00:00:00+00:00", "day"))
        self.assertEqual((ad["versionsCount"], ad["multipleVersions"], ad["linkDomain"], ad["callToAction"], ad["hasVideo"]),
                         (12, True, "xtb.pl", "Sign Up", False))
        self.assertEqual(ad["adTitle"], "Inwestuj w akcje i ETF-y bez prowizji")
        self.assertIn("0% prowizji", ad["adBody"])
        self.assertEqual(ad["description"].splitlines()[0], ad["adBody"])
        self.assertEqual((ad["firmRelation"]["firm"], ad["firmRelation"]["role"]), ("xtb", "advertiser"))
        self.assertEqual(ad["publisherPlatforms"], [])
        self.assertEqual((ad["publisherPlatformIcons"], "publisherPlatforms" in ad["importMissing"]), (3, True))
        self.assertEqual(ad["url"], "https://www.facebook.com/ads/library/?id=1421543096020676")
        self.assertEqual(ad["creatorId"], "facebook:page-name-xtb-online-investing")

    def test_discovery_and_provenance_name_the_file_and_its_hash(self):
        digest = hashlib.sha256(AD_TEXT.read_bytes()).hexdigest()
        ad = self.ads["1859210128043429"]
        path = ad["discovery"][0]
        self.assertEqual((path["method"], path["sourceFile"], path["savedAt"], path["importedAt"], path["import"]),
                         ("manual_import", AD_TEXT.name, SAVED, NOW, True))
        self.assertEqual((ad["provenance"]["sourceFile"], ad["provenance"]["sourceFileSha256"], ad["provenance"]["responseSha256"]),
                         (AD_TEXT.name, digest, digest))
        self.assertEqual((ad["provenance"]["collectionMethod"], ad["importLabel"], ad["coverage"]["scope"]),
                         ("manual_import", "import ręczny", "ad_text"))
        self.assertTrue(ad["hasVideo"] and ad["videoDuration"] == "0:10")

    def test_active_ad_has_only_a_start_date_and_eu_transparency_has_no_version_count(self):
        active = self.ads["846978505145299"]
        self.assertEqual((active["adStatus"], active["adDeliveryStartDate"], active["adDeliveryStopDate"], active["linkDomain"]),
                         ("active", "2026-10-08", None, "xtb.com"))
        eu = self.ads["844397757965187"]
        self.assertEqual((eu["versionsCount"], eu["euTransparencyShown"], eu["multipleVersions"]), (None, True, True))
        self.assertNotIn("versionsCount", eu["importMissing"])

    def test_cards_without_domain_keep_everything_in_the_text_and_say_so(self):
        plain = self.ads["1353099026431942"]
        self.assertIsNone(plain["adTitle"])
        self.assertIn("Pobierz aplikację XTB", plain["adBody"])
        self.assertIn("importLayoutNote", plain)
        video = self.ads["1601125314029671"]
        self.assertEqual((video["adTitle"], video["callToAction"]), ("Pobierz aplikację XTB", "Install Now"))

    def test_footer_text_does_not_leak_into_the_last_card(self):
        last = self.result["captures"][-1]
        self.assertNotIn("Wyświetl więcej", last["description"])
        self.assertNotIn("Stan systemu", last["description"])

    def test_english_page_instagram_only_and_third_party_advertiser(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.read_file(write(tmp, "en.txt", EN_PAGE), saved_at=SAVED, imported_at=NOW)
        ads = {c["adId"]: c for c in result["captures"]}
        self.assertEqual(result["page"], {"resultCount": 1200, "interfaceLanguage": "en"})
        ig = ads["111111111111111"]
        self.assertEqual((ig["id"], ig["platform"], ig["publisherPlatforms"]), ("instagram:ad-111111111111111", "instagram", ["instagram"]))
        self.assertEqual((ig["adDeliveryStartDate"], ig["adDeliveryStopDate"], ig["versionsCount"], ig["adStatus"]),
                         ("2025-09-18", "2026-09-01", 3, "inactive"))
        self.assertEqual((ig["linkDomain"], ig["adTitle"], ig["adDescription"], ig["callToAction"]),
                         ("bestcourse.com", "Learn to trade", "Start today", "Learn More"))
        self.assertEqual((ig["module"], ig["firmRelation"]), ("M1", None))
        firm = ads["222222222222222"]
        self.assertEqual((firm["module"], firm["publisherPlatforms"], firm["adStatus"], firm["adDeliveryStartDate"], firm["adDeliveryStopDate"]),
                         ("M2", ["facebook", "messenger"], "active", "2026-10-08", None))
        self.assertEqual(firm["callToAction"], "Sign Up")
        self.assertNotIn("System status", firm["description"])

    def test_third_party_mentioning_a_registered_firm_is_m1_with_a_mention(self):
        text = EN_PAGE.replace("Earn passive income. Join our course now", "Better than XTB: join our course now")
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.read_file(write(tmp, "en.txt", text), imported_at=NOW)
        ad = next(c for c in result["captures"] if c["adId"] == "111111111111111")
        self.assertEqual((ad["module"], ad["firmRelation"]["role"], ad["firmRelation"]["firm"]), ("M1", "mentioned", "xtb"))

    def test_missing_dates_platforms_and_advertiser_are_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.read_file(write(tmp, "n.txt", NO_DATES), imported_at=NOW)
        ad = result["captures"][0]
        self.assertEqual((ad["publishedAt"], ad["adDeliveryStartDate"], ad["adDeliveryStopDate"], ad["publisherPlatforms"]),
                         (None, None, None, []))
        self.assertEqual(ad["adBody"], "Tylko treść bez reszty")
        for field in ("startDate", "publisherPlatforms", "versionsCount", "title", "domain", "cta"):
            self.assertIn(field, ad["importMissing"])
        self.assertEqual(ad["importNote"], "brak danych w zapisanym pliku")
        self.assertEqual(ad["author"], "Konto Testowe")

    def test_saved_html_gives_the_same_ads_as_copied_text_scripts_ignored(self):
        text = AD_TEXT.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            plain = meta_import.read_file(write(tmp, "a.txt", text), imported_at=NOW)
            html = meta_import.read_file(write(tmp, "a.html", as_html(text)), imported_at=NOW)
            split = meta_import.read_file(write(tmp, "b.html", as_html(text, spans=True)), imported_at=NOW)
        key = lambda r: [(c["adId"], c["author"], re.sub(r"\n{2,}", "\n", c["adBody"] or ""), c["adTitle"], c["callToAction"], c["adDeliveryStartDate"],
                          c["versionsCount"], c["linkDomain"]) for c in r["captures"]]
        self.assertEqual(html["count"], 22)
        self.assertNotIn("999999999999999", [c["adId"] for c in html["captures"]])
        self.assertEqual(key(html), key(plain))
        self.assertEqual(key(split), key(plain))

    def test_html_icon_with_platform_name_gives_the_platform(self):
        page = as_html(EN_PAGE.split("Active\nLibrary ID")[0].replace("Instagram\nThis", "This"))
        page = page.replace("<div><span>Platforms</span></div>", '<div><span>Platforms</span></div><img alt="Instagram" src="x">')
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.read_file(write(tmp, "i.html", page), imported_at=NOW)
        self.assertEqual(result["captures"][0]["publisherPlatforms"], ["instagram"])

    def test_duplicate_card_is_counted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.read_file(write(tmp, "d.txt", NO_DATES + NO_DATES), imported_at=NOW)
        self.assertEqual((result["count"], result["duplicates"]), (1, 1))


class InstagramTests(unittest.TestCase):
    def read(self, text=None, name="p.html"):
        with tempfile.TemporaryDirectory() as tmp:
            path = IG_PROFILE if text is None else write(tmp, name, text)
            return meta_import.read_file(path, saved_at=SAVED, imported_at=NOW)

    def test_profile_embed_gives_six_posts_with_date_likes_and_flag(self):
        result = self.read()
        posts = {c["shortcode"]: c for c in result["captures"]}
        self.assertEqual((result["status"], result["count"], result["account"]["username"], result["account"]["followers"]),
                         ("ok", 6, "xtb_polska", 44764))
        first = posts["Df_3AHxjSqK"]
        self.assertEqual((first["id"], first["module"], first["publishedAt"], first["isPaidPartnership"], first["url"]),
                         ("instagram:Df_3AHxjSqK", "M2", "2026-11-21T09:00:04+00:00", False, "https://www.instagram.com/p/Df_3AHxjSqK/"))
        self.assertEqual(first["reach"]["metrics"]["likeCount"], {"value": 8, "state": "observed", "observedAt": NOW, "source": "instagram_embed"})
        self.assertIn("Emergency Lock", first["description"])
        self.assertEqual((first["firmRelation"]["firm"], first["firmRelation"]["role"], first["creatorId"]), ("xtb", "author", "instagram:xtb_polska"))
        self.assertEqual(first["discovery"][0]["method"], "manual_import")
        self.assertEqual(first["provenance"]["sourceFileSha256"], hashlib.sha256(IG_PROFILE.read_bytes()).hexdigest())
        self.assertEqual(first["importMissing"], [])
        self.assertEqual(result["creators"][0]["reach"]["metrics"]["followerCount"]["value"], 44764)

    def test_paid_partnership_true_and_absent_flag(self):
        html = IG_PROFILE.read_text(encoding="utf-8")
        flag = 'is_paid_partnership\\":false'
        flipped = self.read(html.replace(flag, 'is_paid_partnership\\":true', 1))
        self.assertEqual([c["isPaidPartnership"] for c in flipped["captures"]], [True] + [False] * 5)
        self.assertTrue(flipped["captures"][0]["coverage"]["modalities"]["platformFlags"]["paidPromotion"])
        absent = self.read(html.replace(flag, 'x_flag\\":false', 1))
        first = absent["captures"][0]
        self.assertIsNone(first["isPaidPartnership"])
        self.assertIn("paidPartnership", first["importMissing"])
        self.assertEqual(first["coverage"]["modalities"]["platformFlags"]["state"], "unavailable")

    def test_profile_without_posts_or_without_data_is_empty_not_an_error(self):
        etoro = meta_import.read_file(ALT / "ig-profile-embed-etoro.html", imported_at=NOW)
        self.assertEqual((etoro["status"], etoro["count"], etoro["captures"]), ("empty", 0, []))
        broken = meta_import.read_file(ALT / "ig-profile-embed-trading212_pl.html", imported_at=NOW)
        self.assertEqual((broken["status"], broken["kind"], broken["count"]), ("empty", "instagram_profile", 0))
        self.assertIn("brak danych w zapisanym pliku", broken["message"])

    def test_single_post_embed(self):
        result = meta_import.read_file(ALT / "ig-embed-captioned.html", saved_at=SAVED, imported_at=NOW)
        post = result["captures"][0]
        self.assertEqual((result["kind"], result["count"], post["id"], post["author"], post["module"]),
                         ("instagram_post", 1, "instagram:CuE2WNQs6vH", "google", "M1"))
        self.assertEqual(post["reach"]["metrics"]["likeCount"]["value"], 5077)
        self.assertTrue(post["description"].startswith("Introducing Ballroom in Focus"))
        self.assertEqual((post["publishedAt"], post["isPaidPartnership"]), (None, None))
        self.assertEqual(set(post["importMissing"]), {"publishedAt", "paidPartnership"})
        self.assertEqual(post["url"], "https://www.instagram.com/reel/CuE2WNQs6vH/")

    def test_unrecognized_page_is_reported(self):
        for name in ("fb-page-plugin.html", "firm-xtb.html"):
            result = meta_import.read_file(ALT / name, imported_at=NOW)
            self.assertEqual((result["status"], result["count"]), ("unrecognized", 0))
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.read_file(Path(tmp) / "missing.html", imported_at=NOW)
        self.assertEqual(result["status"], "error")


class AdapterTests(unittest.TestCase):
    def test_live_adapter_reads_the_import_folder_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.txt", EN_PAGE)
            write(tmp, "junk.html", "<html><body>nic</body></html>")
            result = meta_import.discover(ctx(meta_import_dir=tmp))
        self.assertEqual((result["status"], len(result["captures"])), ("ok", 2))
        rows = {s["id"]: s for s in result["sources"]}
        self.assertEqual((rows["facebook-ads"]["count"], rows["instagram-ads"]["count"]), (1, 1))
        self.assertEqual(rows["instagram"]["files"][0]["status"], "unrecognized")
        self.assertEqual(validate_adapter_result(result)["errors"], [])
        self.assertTrue(all(c["discovery"][0]["importedAt"] == NOW for c in result["captures"]))

    def test_empty_or_missing_folder_is_an_empty_status_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = meta_import.discover(ctx(meta_import_dir=Path(tmp) / "nie-ma"))
        self.assertEqual((result["status"], result["captures"]), ("empty", []))
        self.assertTrue(all(s["status"] == "empty" for s in result["sources"]))
        self.assertIn("katalog importu", result["sources"][0]["message"])

    def test_import_dir_follows_env_then_state(self):
        self.assertEqual(meta_import.import_dir({"INVESTWATCH_META_IMPORT_DIR": "/x/y"}), Path("/x/y"))
        self.assertEqual(meta_import.import_dir({"INVESTWATCH_STATE": "/s"}), Path("/s/meta-import"))

    def test_replay_fixture_counts_statuses_and_validation(self):
        result = meta_import.discover(ctx(mode="replay"))
        ads = [c for c in result["captures"] if c.get("adId")]
        posts = [c for c in result["captures"] if not c.get("adId")]
        self.assertEqual((len(ads), len(posts), len(result["creators"])), (22, 6, 3))
        self.assertTrue(all(c["mode"] == "replay" and c["provenance"]["fixture"].endswith("replay-meta.json.gz") for c in result["captures"]))
        rows = {s["id"]: s for s in result["sources"]}
        self.assertIn("22 reklam, 2026-11-21", rows["facebook-ads"]["message"])
        self.assertIn("6 postów, 2026-11-21", rows["instagram"]["message"])
        self.assertIn("odczyt automatyczny wyłączony", rows["instagram"]["message"])
        self.assertTrue(all("Ad Library API po uzyskaniu tokenu (adapter meta_ads gotowy) / Meta Content Library" == r["nextStep"] for r in rows.values()))
        self.assertEqual(validate_adapter_result(result)["errors"], [])
        self.assertEqual(sum(c["module"] == "M2" for c in result["captures"]), 28)

    def test_replay_fixture_is_the_current_parser_output_and_manifest_hashes_match(self):
        manifest = json.loads(meta_import.SAMPLE_MANIFEST.read_text(encoding="utf-8"))
        rebuilt = meta_import.build_sample(imported_at=manifest["importedAt"])
        stored = meta_import.read_sample()
        rebuilt.pop("files")
        self.assertEqual(json.loads(json.dumps(rebuilt, sort_keys=True)), json.loads(json.dumps(stored, sort_keys=True)))
        for entry in manifest["files"]:
            self.assertEqual(entry["sha256"], hashlib.sha256((meta_import.SAMPLE_DIR / entry["file"]).read_bytes()).hexdigest())

    def test_cli_writes_json_and_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.txt", EN_PAGE)
            for name in ("out.json", "out.json.gz"):
                self.assertEqual(meta_import.main([str(Path(tmp) / "a.txt"), "--out", str(Path(tmp) / name), "--imported-at", NOW]), 0)
            plain = json.loads((Path(tmp) / "out.json").read_text(encoding="utf-8"))
            packed = json.loads(gzip.decompress((Path(tmp) / "out.json.gz").read_bytes()))
            self.assertEqual(plain, packed)
            self.assertEqual(len(plain["captures"]), 2)
            self.assertEqual(meta_import.main([str(Path(tmp) / "none")]), 1)


if __name__ == "__main__":
    unittest.main()
