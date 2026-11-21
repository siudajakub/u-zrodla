"""Offline tests for the YouTube adapter on recorded-shape responses (no network)."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from .youtube import Context, QUERIES, description_signals, detect_language, discover, load_key, rank_videos, replay

KEY = "AIzaTESTKEYtestkeyTESTKEYtestkey12345"
NOW = "2026-11-21T19:00:00+00:00"
CH_A = "UC" + "a" * 22
CH_B = "UC" + "b" * 22
CH_C = "UC" + "c" * 22


def video(vid, channel, title, description, views=1000, *, duration="PT8M", audio="pl", likes=10, privacy="public",
          paid=None, hide_likes=False):
    stats = {"viewCount": str(views), "commentCount": "3"}
    if not hide_likes:
        stats["likeCount"] = str(likes)
    item = {"id": vid, "snippet": {"channelId": channel, "channelTitle": f"Kanał {channel[2]}", "title": title,
                                   "description": description, "publishedAt": "2026-11-10T10:00:00Z",
                                   "defaultAudioLanguage": audio, "liveBroadcastContent": "none"},
            "statistics": stats, "contentDetails": {"duration": duration}, "status": {"privacyStatus": privacy}}
    if paid is not None:
        item["paidProductPlacementDetails"] = {"hasPaidProductPlacement": paid}
    return item


def hit(vid, channel, title="t"):
    return {"id": {"kind": "youtube#video", "videoId": vid},
            "snippet": {"channelId": channel, "channelTitle": f"Kanał {channel[2]}", "title": title,
                        "description": "Skrócony opis…", "publishedAt": "2026-11-10T10:00:00Z"}}


def atom(channel, entries):
    rows = "".join(
        f"""<entry><yt:videoId>{vid}</yt:videoId><yt:channelId>{channel[2:]}</yt:channelId><title>{title}</title>
        <link rel="alternate" href="https://www.youtube.com/{'shorts/' + vid if short else 'watch?v=' + vid}"/>
        <published>2026-11-10T10:00:00+00:00</published><media:group><media:description>{desc}</media:description>
        <media:community><media:statistics views="{views}"/></media:community></media:group></entry>"""
        for vid, title, desc, views, short in entries)
    return f"""<?xml version="1.0"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
    xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
    <yt:channelId>{channel[2:]}</yt:channelId><author><name>Kanał</name></author>{rows}</feed>""".encode()


class FakeYouTube:
    def __init__(self):
        self.search = {}       # (q, pageToken|None) -> (items, nextPageToken)
        self.videos = {}
        self.channels = {}
        self.playlists = {}
        self.atom = {}
        self.calls = []
        self.quota_after = None  # number of successful API calls before quotaExceeded

    def fetch(self, url):
        parts = urlsplit(url)
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        self.calls.append((parts.path, query))
        if parts.hostname == "www.youtube.com":
            body = self.atom.get(query["channel_id"])
            return (200, body) if body else (404, b"")
        assert query.get("key") == KEY
        if self.quota_after is not None:
            if self.quota_after <= 0:
                return 403, json.dumps({"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}).encode()
            self.quota_after -= 1
        method = parts.path.rsplit("/", 1)[-1]
        if method == "search":
            items, token = self.search.get((query["q"], query.get("pageToken")), ([], None))
            body = {"items": items, **({"nextPageToken": token} if token else {})}
        elif method == "videos":
            body = {"items": [self.videos[i] for i in query["id"].split(",") if i in self.videos]}
        elif method == "channels":
            body = {"items": [self.channels[i] for i in query["id"].split(",") if i in self.channels]}
        elif method == "playlistItems":
            body = {"items": [{"contentDetails": {"videoId": v}} for v in self.playlists.get(query["playlistId"], [])]}
        else:
            return 404, b"{}"
        return 200, json.dumps(body).encode()


def channel(cid, subs, hidden=False):
    stats = {"viewCount": "100", "videoCount": "10", "hiddenSubscriberCount": hidden}
    if not hidden:
        stats["subscriberCount"] = str(subs)
    return {"id": cid, "snippet": {"title": f"Kanał {cid[2]}", "customUrl": f"@kanal{cid[2]}", "country": "PL"},
            "statistics": stats, "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}}}


def world():
    yt = FakeYouTube()
    pl = "Dlaczego inwestowanie w akcje jest ważne? Zacznij z XTB: https://link-pso.xtb.com/pso/abc kodem TEST"
    yt.search[("XTB", None)] = ([hit("AAAAAAAAAAA", CH_A), hit("BBBBBBBBBBB", CH_B)], "PAGE2")
    yt.search[("XTB", "PAGE2")] = ([hit("CCCCCCCCCCC", CH_A), hit("DDDDDDDDDDD", CH_C)], None)
    yt.search[("giełda", None)] = ([hit("AAAAAAAAAAA", CH_A), hit("EEEEEEEEEEE", CH_B)], None)
    yt.videos.update({
        "AAAAAAAAAAA": video("AAAAAAAAAAA", CH_A, "Giełda dla początkujących", pl, 5000, paid=False),
        "BBBBBBBBBBB": video("BBBBBBBBBBB", CH_B, "Stock market basics", "How to invest in stocks with a broker today.",
                             900, audio="en"),
        "CCCCCCCCCCC": video("CCCCCCCCCCC", CH_A, "Krótko o ETF", "Czy ETF jest dla każdego? #shorts", 70000,
                             duration="PT45S"),
        # DDDDDDDDDDD is missing from videos.list: removed or private.
        "EEEEEEEEEEE": video("EEEEEEEEEEE", CH_B, "Dywidendy w praktyce", "Jak działają dywidendy i czy warto?", 300,
                             audio=None, hide_likes=True),
        "FFFFFFFFFFF": video("FFFFFFFFFFF", CH_A, "Starszy film z kanału", "Opis starszego filmu o obligacjach.", 10),
    })
    yt.channels.update({CH_A: channel(CH_A, 120000), CH_B: channel(CH_B, 0, hidden=True), CH_C: channel(CH_C, 50)})
    yt.playlists["UU" + CH_A[2:]] = ["AAAAAAAAAAA", "FFFFFFFFFFF"]
    yt.atom[CH_A] = atom(CH_A, [("AAAAAAAAAAA", "Giełda dla początkujących", pl, 5100, False),
                                ("CCCCCCCCCCC", "Krótko o ETF", "Czy ETF jest dla każdego? #shorts", 70500, True)])
    return yt


QS = (("brand", "XTB", 2), ("topic", "giełda", 1))


class Offline(unittest.TestCase):
    """Hard network guard: even with a real key on the host no test can reach the network,
    and the default key lookup returns nothing unless a test passes a fake key explicitly."""

    def setUp(self):
        self.enterContext(patch("collectors.youtube.urlopen", side_effect=AssertionError("sieć wyłączona w testach")))
        self.enterContext(patch("collectors.youtube.load_key", return_value=None))


def run(yt, **extra):
    options = {"key": KEY, "fetch": yt.fetch, "clock": lambda: NOW, "budget": 1000, "queries": QS,
               "playlist_channels": 1, "atom_channels": 1, **extra}
    return discover(Context(**options))


def by_id(result):
    return {c["id"]: c for c in result["captures"]}


class Discovery(Offline):
    def test_next_page_is_read_and_positions_continue(self):
        yt = world()
        caps = by_id(run(yt))
        path = next(d for d in caps["youtube:CCCCCCCCCCC"]["discovery"] if d["method"] == "data_api_search")
        self.assertEqual((path["query"], path["page"], path["position"], path["queryKind"]), ("XTB", 2, 51, "brand"))
        self.assertIn(("/youtube/v3/search", "PAGE2"), [(p, q.get("pageToken")) for p, q in yt.calls])

    def test_one_capture_per_video_with_every_search_path(self):
        caps = by_id(run(world()))
        queries = sorted(d["query"] for d in caps["youtube:AAAAAAAAAAA"]["discovery"] if d["method"] == "data_api_search")
        self.assertEqual(queries, ["XTB", "giełda"])
        self.assertEqual(caps["youtube:AAAAAAAAAAA"]["contentCompleteness"], "full")
        self.assertEqual(caps["youtube:AAAAAAAAAAA"]["creatorId"], f"youtube:{CH_A}")

    def test_atom_duplicate_is_second_path_of_same_material(self):
        result = run(world())
        caps = by_id(result)
        methods = [d["method"] for d in caps["youtube:AAAAAAAAAAA"]["discovery"]]
        self.assertIn("atom", methods)
        self.assertEqual(sum(1 for c in result["captures"] if c["id"] == "youtube:AAAAAAAAAAA"), 1)
        self.assertEqual(caps["youtube:AAAAAAAAAAA"]["reach"]["source"], "data_api")
        atom_path = next(d for d in caps["youtube:AAAAAAAAAAA"]["discovery"] if d["method"] == "atom")
        self.assertEqual(atom_path["atomViews"], 5100)

    def test_playlist_adds_older_upload_with_its_own_path(self):
        caps = by_id(run(world()))
        self.assertEqual([d["method"] for d in caps["youtube:FFFFFFFFFFF"]["discovery"]], ["data_api_playlist"])
        self.assertIn("data_api_playlist", [d["method"] for d in caps["youtube:AAAAAAAAAAA"]["discovery"]])

    def test_removed_or_private_video_is_explicit(self):
        cap = by_id(run(world()))["youtube:DDDDDDDDDDD"]
        self.assertEqual(cap["availability"]["state"], "unavailable")
        self.assertEqual(cap["contentCompleteness"], "partial")
        self.assertEqual(cap["reach"]["metrics"]["viewCount"]["state"], "not_collected")
        yt = world()
        yt.videos["AAAAAAAAAAA"]["status"]["privacyStatus"] = "private"
        self.assertEqual(by_id(run(yt))["youtube:AAAAAAAAAAA"]["availability"]["state"], "private")

    def test_wrong_language_is_kept_but_out_of_scope(self):
        caps = by_id(run(world()))
        self.assertEqual(caps["youtube:BBBBBBBBBBB"]["youtube"]["languageStatus"], "out_of_scope")
        self.assertEqual(caps["youtube:EEEEEEEEEEE"]["youtube"]["detectedLanguage"], "pl")
        self.assertEqual(caps["youtube:EEEEEEEEEEE"]["youtube"]["languageMethod"], "text_heuristic")
        self.assertEqual(detect_language((None,), "Stock market today", "Best stocks to buy now for beginners")[0], "other")
        # Uploader left en-US, but the material is Polish.
        self.assertEqual(detect_language(("en-US", "en"), "Twoje oszczędności zarabiają za mało?",
                                         "Sprawdź, gdzie je trzymać i jak działają obligacje."),
                         ("pl", "text_heuristic_over_declared_en-us"))
        self.assertEqual(detect_language(("zxx",), "KNF chce zniszczyć XTB?", "#inwestowanie #giełda dlaczego tak jest")[0], "pl")

    def test_hidden_statistics_are_not_zero(self):
        result = run(world())
        caps, creators = by_id(result), {c["id"]: c for c in result["creators"]}
        likes = caps["youtube:EEEEEEEEEEE"]["reach"]["metrics"]["likeCount"]
        self.assertEqual((likes["value"], likes["state"]), (None, "hidden"))
        subs = creators[f"youtube:{CH_B}"]["reach"]["metrics"]["subscriberCount"]
        self.assertEqual((subs["value"], subs["state"]), (None, "hidden"))

    def test_shorts_from_duration_and_atom_link(self):
        caps = by_id(run(world()))
        short = caps["youtube:CCCCCCCCCCC"]["youtube"]
        self.assertTrue(short["isShort"])
        self.assertEqual(short["shortsBasis"], "atom_link")
        ranked = [c["id"] for c in run(world())["captures"]]
        self.assertGreater(ranked.index("youtube:CCCCCCCCCCC"), ranked.index("youtube:AAAAAAAAAAA"))  # own bucket

    def test_channel_scan_order_by_subscribers_with_reason(self):
        creators = run(world())["creators"]
        self.assertEqual(creators[0]["id"], f"youtube:{CH_A}")
        self.assertIn("120000 subskrybentów", creators[0]["scanPriority"]["reason"])
        self.assertIn("ukryci", creators[-1]["scanPriority"]["reason"])
        first = creators[0]["discoveries"][0]
        self.assertEqual((first["method"], first["query"]), ("data_api_search", "XTB"))

    def test_paid_flag_is_true_false_or_unchecked(self):
        caps = by_id(run(world()))
        self.assertIs(caps["youtube:AAAAAAAAAAA"]["youtube"]["paidPromotionFlag"], False)
        self.assertIsNone(caps["youtube:CCCCCCCCCCC"]["youtube"]["paidPromotionFlag"])


class Versions(Offline):
    def test_statistics_only_change_keeps_content_hash(self):
        yt = world()
        first = by_id(run(yt))["youtube:AAAAAAAAAAA"]
        yt.videos["AAAAAAAAAAA"]["statistics"]["viewCount"] = "9999"
        second = by_id(run(yt))["youtube:AAAAAAAAAAA"]
        self.assertEqual(first["contentHash"], second["contentHash"])
        self.assertEqual(second["reach"]["metrics"]["viewCount"]["value"], 9999)

    def test_description_edit_changes_content_hash_same_id(self):
        yt = world()
        first = by_id(run(yt))["youtube:AAAAAAAAAAA"]
        yt.videos["AAAAAAAAAAA"]["snippet"]["description"] += " Materiał reklamowy XTB."
        second = by_id(run(yt))["youtube:AAAAAAAAAAA"]
        self.assertNotEqual(first["contentHash"], second["contentHash"])
        self.assertEqual(first["id"], second["id"])


class QuotaAndResume(Offline):
    def test_quota_exceeded_returns_cursor_and_resumes_from_it(self):
        yt = world()
        yt.quota_after = 1  # first search page succeeds, second gets 403 quotaExceeded
        result = run(yt)
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(result["resume"], {"queryIndex": 0, "query": "XTB", "pageToken": "PAGE2", "page": 2})
        source = result["sources"][0]
        self.assertEqual(source["status"], "limit")
        self.assertEqual(source["retryAt"], "2026-11-22T08:00:00+00:00")
        self.assertEqual(result["quota"]["used"], 200)  # failed requests are charged too
        yt.quota_after = None
        yt.calls.clear()
        resumed = run(yt, state={"resume": result["resume"]})
        searches = [(q["q"], q.get("pageToken")) for p, q in yt.calls if p.endswith("/search")]
        self.assertEqual(searches, [("XTB", "PAGE2"), ("giełda", None)])
        self.assertEqual(resumed["status"], "ok")

    def test_hard_budget_stops_before_overspending(self):
        yt = world()
        result = run(yt, budget=150)
        self.assertLessEqual(result["quota"]["used"], 150)
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(result["resume"]["query"], "XTB")
        self.assertEqual(result["sources"][0]["lastError"]["code"], "budget")
        self.assertNotEqual(result["sources"][0]["status"], "limit")
        self.assertNotIn("retryAt", result["sources"][0])

    def test_missing_key_reports_needs_key_without_requests(self):
        yt = world()
        result = discover(Context(key=None, key_source=lambda: None, fetch=yt.fetch, clock=lambda: NOW))
        self.assertEqual(result["status"], "needs_key")
        self.assertEqual(result["sources"][0]["status"], "needs_key")
        self.assertEqual(yt.calls, [])

    def test_patched_load_key_is_honoured_and_default_budget_spends_nothing(self):
        from unittest.mock import patch
        from collectors import youtube
        yt = world()
        with patch.object(youtube, "load_key", return_value=None):
            self.assertEqual(discover(Context(fetch=yt.fetch, clock=lambda: NOW))["status"], "needs_key")
        with patch.dict("os.environ", {"INVESTWATCH_YT_RUN_UNITS": ""}):
            result = discover(Context(key=KEY, fetch=yt.fetch, clock=lambda: NOW, queries=QS))
        self.assertEqual((result["quota"]["used"], result["status"]), (0, "rate_limited"))
        self.assertFalse([c for c in yt.calls if c[0].startswith("/youtube/v3/")])

    def test_cache_hit_spends_no_units(self):
        with TemporaryDirectory() as tmp:
            yt = world()
            first = run(yt, cache_dir=tmp)
            second = run(yt, cache_dir=tmp)
            self.assertGreater(first["quota"]["used"], 0)
            self.assertEqual(second["quota"]["used"], 0)


class Secrets(Offline):
    def test_key_never_appears_in_result_or_raw_files(self):
        with TemporaryDirectory() as tmp:
            result = run(world(), raw_dir=tmp)
            blob = json.dumps(result) + "".join(p.read_text(errors="replace") for p in Path(tmp).iterdir())
            self.assertNotIn(KEY, blob)
            self.assertIn("key=REDACTED", blob)

    def test_key_file_inside_repository_is_refused(self):
        inside = Path(__file__).resolve()
        self.assertIsNone(load_key({"YOUTUBE_API_KEY_FILE": str(inside)}))  # imported name: the real function

    def test_network_guard_is_active(self):
        from collectors import youtube
        self.assertIsNone(youtube.load_key())
        with self.assertRaises(AssertionError):
            youtube.http_fetch("https://www.googleapis.com/youtube/v3/search?part=snippet")


class Signals(Offline):
    def test_tracking_link_code_and_missing_disclosure(self):
        text = "Inwestuj globalnie: https://c.freedom24.com/?a=t9&i=x Rejestrując się w XTB z kodem ZERO otrzymasz kurs."
        found = description_signals(text)
        self.assertIn("Freedom Finance Europe Ltd", found["firms"])
        self.assertTrue(found["firms"]["Freedom Finance Europe Ltd"]["crossBorder"])
        self.assertEqual(found["codes"], ["ZERO"])
        self.assertEqual(found["disclosure"], [])
        self.assertTrue(description_signals("Partnerem publikacji jest Saxo Bank. #PłatnaWspółpraca")["disclosure"])
        kinds = {(e["firm"], e["kind"]) for e in found["firmEvidence"]}
        self.assertIn(("Freedom Finance Europe Ltd", "firm_tracking_link"), kinds)
        self.assertIn(("XTB S.A.", "code_near_mention"), kinds)

    def test_own_utm_link_and_lowercase_words_are_not_firm_evidence(self):
        text = ("Książka: https://finansowaforteca.pl/?utm_source=youtube Konto w XTB opisuję w odcinku. "
                "Kod rabatowego nie ma. Zaloguj się kodem SMS w PKO BP.")
        found = description_signals(text)
        self.assertEqual(found["firmEvidence"], [])
        self.assertEqual(found["codes"], [])

    def test_business_contact_line_is_not_a_disclosure(self):
        self.assertEqual(description_signals("✉️ Współpraca: biuro@example.pl\nKontakt i reklama: x@y.pl")["disclosure"], [])
        self.assertTrue(description_signals("Odcinek powstał we współpracy z XTB.\n✉️ Współpraca: biuro@example.pl")["disclosure"])

    def test_default_queries_cover_three_families(self):
        self.assertEqual({k for k, _, _ in QUERIES}, {"brand", "promo", "topic"})


class Replay(Offline):
    def test_replay_fixture_has_contract_shape(self):
        path = Path(__file__).resolve().parents[1] / "fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz"
        if not path.exists():
            self.skipTest("brak fikstury replay")
        result = replay(path)
        self.assertTrue({"creators", "captures", "sources"} <= set(result))
        for cap in result["captures"]:
            self.assertRegex(cap["id"], r"^youtube:[A-Za-z0-9_-]{11}$")
            self.assertRegex(cap["creatorId"], r"^youtube:UC[A-Za-z0-9_-]{22}$")
            self.assertTrue(cap["discovery"])
            self.assertEqual(cap["mode"], "replay")
        self.assertNotIn("key=AIza", json.dumps(result))
        self.assertGreater(len(result["captures"]), 100)


if __name__ == "__main__":
    unittest.main()
