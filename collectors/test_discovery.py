from collections import Counter
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from .audio import MAX_BYTES, fetch_excerpt
from .catalogs import read_podcast
from .common import SourceError, digest
from .discovery import discover
from .sites import SITES, read_site

NOW = "2026-11-21T16:00:00+00:00"
KNOWN_FEED = "https://www.spreaker.com/show/41/episodes/feed"
NEW_FEED = "https://www.spreaker.com/show/42/episodes/feed"


def apple_record(id, feed):
    return {"kind": "podcast", "collectionId": id, "feedUrl": feed,
            "collectionName": f"Podcast o inwestowaniu {id}", "artistName": "Wydawca testowy"}


def rss_fixture(episode, language="pl"):
    return f"""<rss xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel>
    <title>Podcast</title><language>{language}</language><item>
    <title>Instrumenty inwestycyjne</title><guid>{episode}</guid>
    <link>https://example.org/episode/{episode}</link>
    <description>&lt;p&gt;Przykładowy opis ETF.&lt;/p&gt;</description>
    <pubDate>Thu, 19 Nov 2026 09:00:00 +0000</pubDate>
    <enclosure url="https://api.spreaker.com/download/episode/1/episode.mp3" type="audio/mpeg" />
    <podcast:transcript url="https://example.org/episode/{episode}.vtt" type="text/vtt" language="pl" />
    </item></channel></rss>""".encode()


class TestDiscovery(unittest.TestCase):
    def test_live_discovers_new_creator_on_later_scan_and_revisits_old_feed(self):
        state = {"records": [apple_record(41, KNOWN_FEED)], "episode": "first"}
        calls = Counter()

        def fetch(url, _):
            calls[url] += 1
            host = urlsplit(url).hostname
            if host == "itunes.apple.com":
                records = state["records"] if parse_qs(urlsplit(url).query)["term"] == ["inwestowanie"] else []
                return json.dumps({"resultCount": len(records), "results": records}).encode()
            if host == "sepiasearch.org":
                return b'{"total": 0, "data": []}'
            if url == KNOWN_FEED:
                return rss_fixture(state["episode"])
            if url == NEW_FEED:
                return rss_fixture("new-publisher")
            raise SourceError("HTTP 403", 403)

        no_monitor = {"INVESTWATCH_WATCH_DB": "/nonexistent/invalid-test.sqlite3"}
        with patch.dict("os.environ", no_monitor):
            first = discover("live", (), fetch=fetch, clock=lambda: NOW)
            known = {creator["id"] for creator in first["creators"]}
            same = discover("live", known, known_creators=first["creators"], fetch=fetch, clock=lambda: NOW)
            state.update(records=[apple_record(42, NEW_FEED)], episode="next")
            later = discover("live", known, known_creators=first["creators"], fetch=fetch, clock=lambda: NOW)

        self.assertEqual([c["id"] for c in first["creators"] if c["isNew"]], ["apple-podcasts:41"])
        self.assertEqual([c["id"] for c in same["creators"] if c["isNew"]], [])
        self.assertEqual([c["id"] for c in later["creators"] if c["isNew"]], ["apple-podcasts:42"])
        self.assertEqual(first["captures"], same["captures"])
        self.assertEqual(calls[KNOWN_FEED], 3)
        self.assertEqual({item["creatorId"] for item in later["captures"]},
                         {"apple-podcasts:41", "apple-podcasts:42"})
        self.assertNotIn(first["captures"][0]["id"], [item["id"] for item in later["captures"]])
        capture = later["captures"][0]
        self.assertEqual(capture["publishedAt"], "2026-11-19T09:00:00.000000+00:00")
        self.assertEqual(capture["description"], "Przykładowy opis ETF.")
        self.assertEqual(capture["publisher"], "Wydawca testowy")
        self.assertIs(capture["audioExcerptAvailable"], True)
        self.assertEqual(capture["transcriptSource"]["language"], "pl")
        statuses = {status["id"]: status for status in later["sources"]}
        self.assertEqual(statuses["peertube-search:ETF"]["status"], "empty")
        self.assertEqual(statuses["apple-search:inwestowanie"]["newCreators"], 1)
        self.assertEqual(statuses[SITES[0].key]["httpStatus"], 403)
        self.assertNotIn("lastSuccessAt", statuses[SITES[0].key])

    def test_replay_does_not_touch_network_and_preserves_source_scope(self):
        forbidden = Mock(side_effect=AssertionError("replay touched network"))
        first = discover("replay", (), fetch=forbidden)
        ids = {creator["id"] for creator in first["creators"]}
        second = discover("replay", ids, fetch=forbidden)
        forbidden.assert_not_called()
        self.assertFalse(any(c["isNew"] for c in second["creators"]))
        self.assertTrue(any(c["isNew"] and c["platform"] == "peertube" for c in first["creators"]))
        self.assertEqual(first["captures"], second["captures"])
        self.assertEqual(len({item["id"] for item in first["captures"]}), len(first["captures"]))
        for capture in first["captures"]:
            self.assertIn(capture["creatorId"], ids)
            self.assertEqual(capture["contentHash"], digest(capture["description"]))
            self.assertEqual(capture["provenance"]["mode"], "replay")
            self.assertRegex(capture["provenance"]["responseSha256"], "^[0-9a-f]{64}$")

    def test_non_polish_and_malformed_feed_are_distinct_from_403(self):
        creator = {"id": "apple-podcasts:41", "platform": "apple-podcasts", "name": "Test",
                   "url": "https://podcasts.apple.com/pl/podcast/id41", "feedUrl": KNOWN_FEED}
        profile, items, source = read_podcast(creator, lambda *_: rss_fixture("id", "en-US"), lambda: NOW)
        self.assertEqual(profile["qualification"], "other_language")
        self.assertEqual(source["status"], "empty")
        self.assertEqual(source["rawCount"], 1)
        self.assertEqual(source["lastSuccessAt"], NOW)
        self.assertEqual(items, [])

        _, items, source = read_podcast(creator, lambda *_: b'<!DOCTYPE rss><rss/>', lambda: NOW)
        self.assertEqual(source["status"], "error")
        self.assertNotIn("httpStatus", source)
        self.assertEqual(items, [])

        def forbidden(*_):
            raise SourceError("HTTP 403", 403)

        _, items, source = read_podcast(creator, forbidden, lambda: NOW)
        self.assertEqual(source["status"], "error")
        self.assertEqual(source["httpStatus"], 403)
        self.assertEqual(items, [])

    def test_site_follows_one_allowed_hop_and_keeps_both_provenance_hashes(self):
        site = SITES[0]
        home = b'<a href="https://private.invalid/pl/etf">Other</a><a href="/pl/etf?tracking=1">ETF</a>'
        detail = b'<title>Oferta</title><main>' + b'Tekst oferty inwestycyjnej. ' * 4 + b'</main>'
        fetch = Mock(side_effect=[home, detail])
        items, status = read_site(site, fetch, lambda: NOW)
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["rawCount"], 1)
        self.assertEqual(items[0]["module"], "M2")
        self.assertEqual(items[0]["provenance"]["indexSha256"], digest(home))
        self.assertEqual(items[0]["provenance"]["responseSha256"], digest(detail))
        self.assertEqual([args[0][0] for args in fetch.call_args_list], [site.home, f"https://{site.host}/pl/etf"])


class FakeAudio(BytesIO):
    def __init__(self, data, status=200, range_header=None):
        super().__init__(data)
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = "audio/mpeg"
        if range_header:
            self.headers["Content-Range"] = range_header


class TestAudio(unittest.TestCase):
    capture = {
        "mode": "live",
        "platform": "apple-podcasts",
        "materialType": "podcast_rss_title_description",
        "audioUrl": "https://api.spreaker.com/download/episode/1/episode.mp3",
        "audioMimeType": "audio/mpeg",
    }

    def test_full_response_without_range_support_is_size_bounded(self):
        opener = Mock()
        opener.open.return_value = FakeAudio(b"ID3" + b"0" * (MAX_BYTES * 2))
        with TemporaryDirectory() as directory, patch("collectors.audio.build_opener", return_value=opener):
            output = Path(directory) / "excerpt.mp3"
            self.assertTrue(fetch_excerpt(self.capture, output))
            self.assertEqual(output.stat().st_size, MAX_BYTES)
            sent = opener.open.call_args.args[0]
            self.assertEqual(sent.get_header("Range"), f"bytes=0-{MAX_BYTES - 1}")

    def test_refuses_disallowed_redirect_and_replay(self):
        opener = Mock()
        headers = Message()
        headers["Location"] = "https://unexpected.invalid/audio.mp3"
        opener.open.side_effect = HTTPError(self.capture["audioUrl"], 302, "redirect", headers, BytesIO())
        with TemporaryDirectory() as directory, patch("collectors.audio.build_opener", return_value=opener):
            output = Path(directory) / "excerpt.mp3"
            self.assertFalse(fetch_excerpt(self.capture, output))
            self.assertFalse(fetch_excerpt({**self.capture, "mode": "replay"}, output))
            self.assertFalse(output.exists())
            opener.open.assert_called_once()

    def test_rejects_partial_response_starting_after_zero(self):
        opener = Mock()
        opener.open.return_value = FakeAudio(b"ID3test", 206, "bytes 1-7/8")
        with TemporaryDirectory() as directory, patch("collectors.audio.build_opener", return_value=opener):
            output = Path(directory) / "excerpt.mp3"
            self.assertFalse(fetch_excerpt(self.capture, output))
            self.assertFalse(output.exists())
