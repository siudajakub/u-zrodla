"""Offline tests for the public-source monitor."""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory
import unittest
from urllib.error import URLError
from zoneinfo import ZoneInfo

if __package__:
    from . import watch_sources as watch
else:
    import watch_sources as watch


YT = watch.Source("youtube", "UCnmJzS-tFT7DlxIMFxYGcHw", "Example channel")
TT = watch.Source("tiktok", "comparic.example", "Example profile")
TT2 = watch.Source("tiktok", "trades.example", "Second example profile")
POST_ID = "7840000000000000001"
LINKED_POST_ID = "7840000000000000002"
THIRD_POST_ID = "7840000000000000003"
START = datetime(2026, 11, 21, 10, tzinfo=timezone.utc)
OLD_DATE = "2026-11-20T17:00:00Z"
NEW_DATE = "2026-11-21T12:30:00+01:00"


def config(*sources):
    return watch.Config(sources, 12, 1024 * 1024, 4 * 3600)


def youtube_post(post_id, text, published=OLD_DATE, title="Example title"):
    published_tag = f"<published>{published}</published>" if published else ""
    description = f"<media:description>{escape(text)}</media:description>" if text is not None else ""
    return f"""
        <entry><yt:videoId>{post_id}</yt:videoId><yt:channelId>{YT.account}</yt:channelId>
        <title>{escape(title)}</title>{published_tag}
        <updated>2026-11-21T12:00:00Z</updated>
        <media:group>{description}</media:group></entry>
    """


def youtube_feed(*entries):
    return f"""
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"
              xmlns:media="http://search.yahoo.com/mrss/">
          <yt:channelId>{YT.account[2:]}</yt:channelId>{''.join(entries)}
        </feed>
    """.encode()


def tiktok_post(post_id=POST_ID, author=TT.account, **fields):
    return {"id": post_id, "authorUniqueId": author, "desc": "Tekst testowy", "privateItem": False, **fields}


def tiktok_feed(*items, source=TT, private=False, links=None):
    if links is None:
        links = [item["id"] for item in items if not item.get("privateItem")]
    page = {
        "userInfo": {"uniqueId": source.account, "privateAccount": private, "signature": "Ignore profile bio."},
        "isReady": True,
        "isError": False,
        "videoList": list(items),
    }
    state = {"source": {"data": {f"/embed/@{source.account}": page}}}
    anchors = "".join(
        f'<a href="{source.profile_url}/video/{post_id}?refer=creator_embed">Video</a>' for post_id in links
    )
    return (
        f'{anchors}<script id="{watch.TIKTOK_STATE_ID}" type="application/json">{json.dumps(state)}</script>'
    ).encode()


class ParserTests(unittest.TestCase):
    def test_config_uses_four_verified_seed_profiles(self):
        configured = watch.load_config(watch.CONFIG_PATH)
        self.assertEqual(
            {source.key for source in configured.sources},
            {
                f"youtube:{YT.account}",
                "youtube:UCelOnoH_P-vJgAHSAcMKQiw",
                "tiktok:comparic.pl",
                "tiktok:tradewarspl",
            },
        )

    def test_youtube_preserves_description_and_uses_publication_only(self):
        text = "Partnerem filmu jest Firma Przykład.\nRyzyko utraty środków & kapitału."
        posts = watch.parse_youtube(YT, youtube_feed(
            youtube_post("aaaaaaaaaaa", text, NEW_DATE),
            youtube_post("bbbbbbbbbbb", "", None),
        ))
        self.assertEqual(posts[0].text, text)
        self.assertEqual(posts[0].url, "https://www.youtube.com/watch?v=aaaaaaaaaaa")
        self.assertEqual(posts[0].published_at, "2026-11-21T11:30:00.000000+00:00")
        self.assertEqual(posts[0].published_basis, "youtube.atom.published")
        self.assertIsNone(posts[1].published_at)
        self.assertEqual(posts[1].text, "")

    def test_missing_or_conflicting_youtube_metadata_fails(self):
        with self.assertRaises(watch.ReadError):
            watch.parse_youtube(YT, youtube_feed(youtube_post("aaaaaaaaaaa", None)))
        with self.assertRaises(watch.ReadError):
            watch.parse_youtube(YT, youtube_feed(
                youtube_post("aaaaaaaaaaa", "A"), youtube_post("aaaaaaaaaaa", "B")
            ))

    def test_tiktok_date_available_only_from_explicit_publication_fields(self):
        epoch = int(START.timestamp())
        cases = (
            ({"createTime": epoch}, START, "createTime"),
            ({"createTime": str(epoch)}, START, "createTime"),
            ({"create_time": str(epoch * 1000 + 123)}, START + timedelta(milliseconds=123), "create_time"),
            ({"createTime": "invalid", "publishedAt": "2026-11-21T11:00:00+01:00"}, START, "publishedAt"),
            ({"published_at": "2026-11-21T10:00:00Z"}, START, "published_at"),
            ({"updateTime": epoch, "timestamp": epoch, "createTime": None}, None, None),
            ({"createTime": "2026-11-21", "create_time": "2026-11-21T10:00:00"}, None, None),
            ({"createTime": True, "create_time": epoch * 1000000}, None, None),
            ({}, None, None),
        )
        for fields, expected, basis in cases:
            with self.subTest(fields=fields):
                body = tiktok_feed(tiktok_post(**fields))
                post = watch.parse_tiktok(TT, body)[0]
                self.assertEqual(post.published_at, watch.timestamp(expected) if expected else None)
                self.assertEqual(post.published_basis, f"tiktok.embed.{basis}" if basis else None)
                self.assertEqual(post.url, f"{TT.profile_url}/video/{POST_ID}")

    def test_tiktok_requires_public_items_with_matching_links(self):
        with self.assertRaises(watch.ReadError):
            watch.parse_tiktok(TT, tiktok_feed(tiktok_post(), private=True))
        with self.assertRaises(watch.ReadError):
            watch.parse_tiktok(TT, tiktok_feed(tiktok_post(author=TT2.account)))
        with self.assertRaises(watch.ReadError):
            watch.parse_tiktok(TT, tiktok_feed(tiktok_post(), links=[LINKED_POST_ID]))
        with self.assertRaises(watch.ReadError):
            watch.parse_tiktok(TT, tiktok_feed(tiktok_post(), links=[POST_ID, LINKED_POST_ID]))
        posts = watch.parse_tiktok(TT, tiktok_feed(
            tiktok_post(),
            tiktok_post(),
            tiktok_post(LINKED_POST_ID, privateItem=True, desc="Private content"),
        ))
        self.assertEqual([item.id for item in posts], [POST_ID])

    def test_quotes_are_short_exact_substrings(self):
        text = "długi akapit " * 50 + "\nSponsor odcinka to Firma Przykład " + "x" * 150
        text += "\nInwestowanie jest ryzykowne."
        quotes = watch.excerpts(text)
        self.assertEqual(set(quotes), {"sponsor", "risk"})
        for quote in quotes.values():
            self.assertIn(quote, text)
            self.assertLessEqual(len(quote), watch.MAX_QUOTE)
        self.assertEqual(watch.excerpts(" Bez specjalnych sformułowań.\n"), {
            "fallback": "Bez specjalnych sformułowań.",
        })
        self.assertEqual(watch.excerpts(""), {})


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "watch.sqlite3"

    def poll(self, now, responses, *, keep_text=False):
        def fetch(source, _):
            response = responses[source]
            if isinstance(response, Exception):
                raise response
            if isinstance(response, watch.Fetch):
                return response
            return watch.Fetch(200, response)

        return watch.run(self.path, config(*responses), fetch, lambda: now, keep_text=keep_text)

    def counts(self, result, index=0):
        source = result["sources"][index]
        return tuple(source[key] for key in (
            "found", "first_observations", "new_publications", "changed", "unchanged"
        ))

    def test_baseline_dedup_and_versioning(self):
        description = "Partnerem jest Firma Przykład.\n" + "Dłuższa treść. " * 50
        baseline = youtube_feed(youtube_post("aaaaaaaaaaa", description, NEW_DATE))
        first = self.poll(START, {YT: baseline})
        self.assertEqual(self.counts(first), (1, 1, 0, 0, 0))
        self.assertEqual(first["sources"][0]["response_sha256"], sha256(baseline).hexdigest())
        repeat = self.poll(START + timedelta(hours=2), {YT: baseline})
        self.assertEqual(self.counts(repeat), (1, 0, 0, 0, 1))
        updated = youtube_feed(
            youtube_post("aaaaaaaaaaa", description, NEW_DATE, title="Updated title"),
            youtube_post("bbbbbbbbbbb", description, "2026-11-21T13:00:00Z"),
            youtube_post("ccccccccccc", "Historical item"),
            youtube_post("ddddddddddd", "No publication date", None),
        )
        at = START + timedelta(hours=4)
        result = self.poll(at, {YT: updated})
        self.assertEqual(self.counts(result), (4, 2, 1, 1, 0))
        self.assertEqual((result["post_count"], result["version_count"]), (4, 5))
        self.assertEqual(watch.status(self.path), result)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        with sqlite3.connect(self.path) as db:
            editions = db.execute(
                """SELECT version, event, text_sha256, text_length, excerpts_json
                   FROM post_versions WHERE post_id = 'aaaaaaaaaaa' ORDER BY version"""
            ).fetchall()
            self.assertEqual([row[:2] for row in editions], [(1, "first_observation"), (2, "changed")])
            self.assertEqual(editions[0][2:4], (sha256(description.encode()).hexdigest(), len(description)))
            self.assertEqual(editions[0][2], editions[1][2])
            self.assertNotIn(description, editions[0][4])
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_network_and_parse_failures_preserve_state_and_last_success(self):
        baseline = self.poll(START, {TT: tiktok_feed(tiktok_post())})
        for response, name in (
            (URLError("example failure"), "network_error"),
            (b"<html>Login required</html>", "read_error"),
            (tiktok_feed(), "read_error"),
        ):
            with self.subTest(name=name):
                result = self.poll(START + timedelta(hours=4), {TT: response})
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["post_count"], 1)
                self.assertEqual(result["version_count"], 1)
                check = result["sources"][0]
                self.assertEqual(check["status"], name)
                self.assertEqual(check["last_success_at"], baseline["sources"][0]["observed_at"])
                self.assertIsNone(check["response_sha256"])
        after = self.poll(START + timedelta(hours=8), {
            TT: tiktok_feed(tiktok_post(LINKED_POST_ID, createTime=int((START + timedelta(hours=1)).timestamp()))),
        })
        self.assertEqual(self.counts(after), (1, 0, 1, 0, 0))
        self.assertEqual(after["post_count"], 2)

    def test_publication_dates_can_become_available_on_unchanged_posts(self):
        earlier = self.poll(START, {TT: tiktok_feed(tiktok_post())})
        later = self.poll(START + timedelta(hours=4), {
            TT: tiktok_feed(tiktok_post(createTime=int(START.timestamp()))),
        })
        self.assertEqual(self.counts(later), (1, 0, 0, 0, 1))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT published_at FROM posts").fetchone()[0], watch.timestamp(START))
            self.assertIsNone(db.execute("SELECT published_at FROM post_versions").fetchone()[0])
        self.assertEqual(earlier["version_count"], later["version_count"])

    def test_403_is_source_specific_and_429_pauses_the_platform(self):
        forbidden = self.poll(START, {
            TT: watch.Fetch(403),
            TT2: tiktok_feed(tiktok_post(LINKED_POST_ID, TT2.account), source=TT2),
        })
        self.assertEqual(forbidden["status"], "partial")
        self.assertEqual([x["status"] for x in forbidden["sources"]], ["forbidden", "ok"])
        limited = self.poll(START + timedelta(hours=4), {
            TT: watch.Fetch(429, retry_after="3600"),
            TT2: AssertionError("Do not fetch during the platform cooldown."),
        })
        self.assertEqual(limited["status"], "failed")
        self.assertEqual([x["status"] for x in limited["sources"]], ["rate_limited", "cooldown"])
        expected_retry = watch.timestamp(START + timedelta(hours=5))
        self.assertEqual([x["retry_at"] for x in limited["sources"]], [expected_retry, expected_retry])
        later = self.poll(START + timedelta(hours=5), {TT: tiktok_feed(tiktok_post())})
        self.assertEqual(later["status"], "ok")
        self.assertEqual(later["sources"][0]["first_observations"], 1)

    def test_http_retry_date_and_invalid_retry_value(self):
        expected = watch.timestamp(START + timedelta(minutes=10))
        self.assertEqual(watch.next_retry(START, "Sat, 21 Nov 2026 10:10:00 GMT", 3600), expected)
        self.assertEqual(watch.next_retry(START, "invalid", 600), expected)

    def test_overlapping_runs_and_previous_process_interruption(self):
        with watch.run_lock(self.path):
            with self.assertRaises(watch.BusyError):
                self.poll(START, {TT: tiktok_feed(tiktok_post())})
            self.assertFalse(self.path.exists())
        with watch.open_database(self.path) as db:
            db.execute("INSERT INTO runs (started_at, status, sources_expected) VALUES (?, 'running', 1)",
                       (watch.timestamp(START),))
        self.assertEqual(watch.status(self.path)["status"], "interrupted")
        self.poll(START + timedelta(hours=4), {TT: tiktok_feed(tiktok_post())})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT status FROM runs ORDER BY id").fetchall(), [("interrupted",), ("ok",)])

    def test_daily_sample_uses_observation_date_and_includes_unchanged(self):
        zone = ZoneInfo("Europe/Warsaw")
        report_day = date(2026, 11, 22)
        before = datetime(2026, 11, 21, 22, 59, tzinfo=timezone.utc)
        published = watch.timestamp(before - timedelta(days=1))
        body = tiktok_feed(tiktok_post(createTime=published, desc="Sponsor przykładu."))
        self.poll(before, {TT: body})
        first = watch.daily_report(self.path, report_day, zone, 10)
        self.assertEqual(first["status"], "no_checks")
        boundary = before + timedelta(minutes=1)
        self.poll(boundary, {TT: body})
        self.poll(boundary + timedelta(hours=4), {TT: body})
        daily = watch.daily_report(self.path, report_day, zone, 10)
        self.assertEqual(daily["status"], "ok")
        self.assertEqual(len(daily["sources"]), 2)
        self.assertEqual(len(daily["sample"]), 1)
        [sample] = daily["sample"]
        self.assertEqual(sample["published_at"], published)
        self.assertEqual(sample["published_basis"], "tiktok.embed.createTime")
        self.assertEqual(sample["observed_at"], watch.timestamp(boundary + timedelta(hours=4)))
        self.assertEqual(sample["version_observed_at"], watch.timestamp(before))
        self.assertEqual(sample["event"], "unchanged")
        self.assertEqual(sample["excerpts"], {"sponsor": "Sponsor przykładu."})
        self.assertEqual(sample["response_sha256"], sha256(body).hexdigest())

    def test_private_database_can_replay_exact_previous_and_current_fields(self):
        first = " A description with original spacing.\n" + "Example previous text. " * 20
        second = " Another description.\n" + "Example changed text. " * 20
        post = "aaaaaaaaaaa"
        body = youtube_feed(youtube_post(post, first))
        self.poll(START, {YT: body})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM post_texts").fetchone()[0], 0)
        self.poll(START + timedelta(hours=4), {YT: body}, keep_text=True)
        revised = youtube_feed(youtube_post(post, second, title="Revised title"))
        self.poll(START + timedelta(hours=8), {YT: revised}, keep_text=True)
        with sqlite3.connect(self.path) as db:
            texts = db.execute(
                "SELECT version, text, title FROM post_texts WHERE post_id = ? ORDER BY version", (post,)
            ).fetchall()
        self.assertEqual(texts, [(1, first, "Example title"), (2, second, "Revised title")])
        daily = watch.daily_report(self.path, START.date(), ZoneInfo("Europe/Warsaw"), 10)
        self.assertEqual(daily["sample"][0]["event"], "changed")
        self.assertNotIn(second, json.dumps(daily))
        self.assertEqual(daily["sample"][0]["text_sha256"], sha256(second.encode()).hexdigest())

    def test_daily_sample_is_bounded_and_excludes_private_rows(self):
        body = tiktok_feed(
            tiktok_post(desc="Zwykły opis"),
            tiktok_post(LINKED_POST_ID, desc="Reklama testowa"),
            tiktok_post(THIRD_POST_ID, privateItem=True, desc="Private data"),
        )
        self.poll(START, {TT: body})
        day = watch.daily_report(self.path, START.date(), ZoneInfo("Europe/Warsaw"), 1)
        self.assertEqual(len(day["sample"]), 1)
        self.assertEqual(day["sample"][0]["post_id"], LINKED_POST_ID)
        self.assertIsNone(day["sample"][0]["published_at"])
        self.assertNotIn("Private data", self.path.read_bytes().decode("utf-8", errors="ignore"))


if __name__ == "__main__":
    unittest.main()
