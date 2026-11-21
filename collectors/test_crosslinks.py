from collections import Counter
import unittest
from urllib.parse import urlsplit

from collectors.common import SourceError
from collectors.crosslinks import CHANNEL, ChannelMetadata, extend_from_posts, profile_url
from tools.test_watch_sources import TT, YT as SEED_YT, tiktok_feed, tiktok_post, youtube_feed, youtube_post
from tools.watch_sources import Source

NOW = "2026-11-21T16:00:00+00:00"
CHANNEL_ID = "UC" + "Z" * 22
YT = Source("youtube", CHANNEL_ID, "Test")
ALIAS = "https://www.youtube.com/c/maklerskaTV"
TIKTOK_PROFILE = "https://www.tiktok.com/@comparic.example"
POST = {"id":"episode:1", "creatorId":"apple-podcasts:123", "url":"https://example.org/1",
        "description": f"Kanał: {ALIAS}, TikTok: {TIKTOK_PROFILE}."}


class CrosslinkTests(unittest.TestCase):
    def test_two_waves_and_revisit_after_link_disappears(self):
        calls = Counter()
        state = {"second": False}
        def fetch(url, allowed):
            self.assertIn(urlsplit(url).hostname, allowed)
            calls[url] += 1
            if url == ALIAS:
                return f'<head><meta itemprop="channelId" content="{CHANNEL_ID}"></head><script>"channelId":"UCxxxxxxxxxxxxxxxxxxxxxx"</script>'.encode()
            if url == YT.feed_url:
                post = "bbbbbbbbbbb" if state["second"] else "aaaaaaaaaaa"
                return youtube_feed(youtube_post(post, "Nowy film")).replace(SEED_YT.account.encode(), CHANNEL_ID.encode()).replace(SEED_YT.account[2:].encode(), CHANNEL_ID[2:].encode())
            if url == TT.feed_url:
                return tiktok_feed(tiktok_post())
            raise AssertionError(url)
        creators, first, statuses = extend_from_posts([POST, POST], [], fetch, lambda: NOW)
        self.assertEqual({c["id"] for c in creators}, {YT.key, TT.key})
        self.assertEqual(len(first), 2)
        self.assertEqual(len(next(c for c in creators if c["id"] == YT.key)["crosslinkDiscovery"]["references"]), 1)
        self.assertEqual(next(c for c in creators if c["id"] == YT.key)["crosslinkDiscovery"]["references"][0]["creatorId"], "apple-podcasts:123")
        self.assertNotIn("właściciel", str(creators).lower())
        self.assertEqual(statuses[-1]["status"], "ok")
        state["second"] = True
        second_creators, second, statuses2 = extend_from_posts([], creators, fetch, lambda: NOW)
        self.assertEqual({c["id"] for c in second_creators}, {YT.key, TT.key})
        self.assertIn("youtube:bbbbbbbbbbb", {x["id"] for x in second})
        self.assertEqual(calls[ALIAS], 1)
        self.assertEqual(calls[YT.feed_url], 2)
        self.assertEqual(statuses2[-1]["status"], "ok")

    def test_bad_profile_and_unavailable_source_are_not_false_empty(self):
        def fetch(url, _):
            if url == ALIAS:
                raise SourceError("HTTP 403", 403)
            if url == TT.feed_url:
                return tiktok_feed(tiktok_post())
            raise AssertionError(url)
        creators, items, statuses = extend_from_posts([POST], [], fetch, lambda: NOW)
        self.assertEqual([c["id"] for c in creators], [TT.key])
        self.assertEqual(len(items), 1)
        self.assertEqual(statuses[-1]["status"], "partial")
        self.assertTrue(any(s.get("httpStatus") == 403 for s in statuses))

    def test_recommendations_do_not_determine_channel(self):
        parser = ChannelMetadata()
        parser.feed('<head><meta itemprop><link rel><meta property></head><script>{"channelId":"UCxxxxxxxxxxxxxxxxxxxxxx"}</script>')
        self.assertEqual(parser.ids, set())
        parser.feed(f'<head><meta itemprop="channelId" content="{CHANNEL_ID}"></head>')
        self.assertEqual(parser.ids, {CHANNEL_ID})
        self.assertTrue(CHANNEL.fullmatch(CHANNEL_ID))

    def test_only_explicit_public_profile_links(self):
        for value in ['https://www.youtube.com/watch?v=abc', 'https://www.tiktok.com/@user/video/123',
                      'https://youtube.com.evil.test/@name', 'http://youtube.com/@name',
                      'https://www.youtube.com/@name/shorts', 'https://user@youtube.com/@name']:
            self.assertIsNone(profile_url(value), value)
        self.assertEqual(profile_url('https://m.tiktok.com/@Example.'), 'https://www.tiktok.com/@example')
        self.assertEqual(profile_url(f'https://youtube.com/channel/{CHANNEL_ID}?x=1'), YT.profile_url)


if __name__ == '__main__':
    unittest.main()
