import gzip
import json
from pathlib import Path
import unittest

from collectors.adapter import AdapterContext, validate_adapter_result
from collectors.social import (
    FIXTURES, build_replay, classify_meta_response, discover_facebook, discover_instagram, discover_tiktok,
    firm_signals, is_polish, tiktok_references,
)
from collectors.common import SourceError
from tools.test_watch_sources import tiktok_feed, tiktok_post

NOW = "2026-11-21T20:00:00+00:00"


def context(captures, previous=None, fetch=None, **options):
    return AdapterContext(mode="live", state={}, budget=None, fetch=fetch or (lambda url, hosts: b""), clock=lambda: NOW,
                          previous=previous or {}, captures=captures, options={"pause": 0, "sleep": lambda s: None, **options})


def youtube(id, text, creator="youtube:UCaaaaaaaaaaaaaaaaaaaaaa"):
    return {"id": id, "creatorId": creator, "url": "https://www.youtube.com/watch?v=" + id[-11:], "description": text}


class ReferenceTests(unittest.TestCase):
    def test_polish_sources_only_and_ranking(self):
        pl = {"id": "youtube:UCaaaaaaaaaaaaaaaaaaaaaa", "country": "PL"}
        en = {"id": "youtube:UCbbbbbbbbbbbbbbbbbbbbbb", "country": "US"}
        caps = [youtube("youtube:aaaaaaaaaa1", "Zobacz też: https://www.tiktok.com/@Alfa.Pl oraz tiktok.com/@beta"),
                youtube("youtube:aaaaaaaaaa2", "TikTok https://www.tiktok.com/@alfa.pl."),
                youtube("youtube:bbbbbbbbbb1", "Follow https://www.tiktok.com/@english_only", "youtube:UCbbbbbbbbbbbbbbbbbbbbbb")]
        refs = tiktok_references(caps, [pl, en])
        self.assertEqual([r["account"] for r in refs], ["alfa.pl", "beta"])
        self.assertEqual(len(refs[0]["captures"]), 2)

    def test_language_and_signals(self):
        self.assertTrue(is_polish("Czy warto inwestować w ETF?"))
        self.assertFalse(is_polish("The welcome bonus is the most expensive money"))
        signal = firm_signals("[współpraca z XTB] Złoto czy ETC? Kod promocyjny w bio")
        self.assertTrue(signal["promotion"])
        self.assertEqual(signal["firmMentions"][0]["quote"], "XTB")
        self.assertFalse(firm_signals("Inwestowanie w ETF to nie XTB")["promotion"])
        self.assertEqual(firm_signals("Zwykły film")["firmMentions"], [])


class TikTokAdapterTests(unittest.TestCase):
    def test_adapter_result_is_valid_and_carries_discovery(self):
        feed = tiktok_feed(tiktok_post(desc="Czy warto inwestować w ETF? [współpraca z XTB]", playCount=1200))
        from tools.test_watch_sources import TT
        caps = [youtube("youtube:aaaaaaaaaa1", f"Nasz TikTok: https://www.tiktok.com/@{TT.account} (kanał o giełdzie)")]
        calls, pauses = [], []
        def fetch(url, hosts):
            calls.append(url)
            self.assertEqual(hosts, {"www.tiktok.com"})
            return feed
        result = discover_tiktok(context(caps, fetch=fetch, sleep=pauses.append))
        checked = validate_adapter_result(result)
        self.assertEqual(checked["errors"], [])
        self.assertEqual(len(calls), 1)
        self.assertTrue(checked["captures"])
        item = checked["captures"][0]
        self.assertEqual(item["discovery"][0]["method"], "crosslink")
        self.assertEqual(item["discovery"][0]["via"]["captureIds"], ["youtube:aaaaaaaaaa1"])
        self.assertIsNone(item["publishedAt"])
        self.assertTrue(item["promotion"])
        self.assertEqual(item["reach"]["metrics"]["viewCount"]["value"], 1200)
        self.assertEqual(item["mediaCoverage"]["transcript"]["state"], "unavailable")
        self.assertEqual(checked["creators"][0]["discoveries"][0]["method"], "crosslink")
        self.assertEqual(result["sources"][0]["id"], "tiktok")

    def test_error_is_reported_not_empty(self):
        caps = [youtube("youtube:aaaaaaaaaa1", "Zobacz nasz profil https://www.tiktok.com/@zablokowany żeby być na bieżąco")]
        def fetch(url, hosts):
            raise SourceError("HTTP 429", 429, retry_after=300)
        result = discover_tiktok(context(caps, fetch=fetch))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["captures"], [])
        self.assertEqual(result["sources"][1]["httpStatus"], 429)
        self.assertEqual(result["sources"][0]["lastError"]["code"], "tiktok_unavailable")

    def test_no_links_is_empty_and_budget_limits_requests(self):
        self.assertEqual(discover_tiktok(context([]))["status"], "empty")
        caps = [youtube("youtube:aaaaaaaaaa1", "Obserwuj nas żeby wiedzieć więcej https://www.tiktok.com/@a1 https://www.tiktok.com/@a2 https://www.tiktok.com/@a3")]
        calls = []
        ctx = context(caps, fetch=lambda url, hosts: calls.append(url) or (_ for _ in ()).throw(SourceError("HTTP 404", 404)))
        ctx.budget = 2
        result = discover_tiktok(ctx)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum(s["status"] == "skipped" for s in result["sources"]), 1)


class MetaAdapterTests(unittest.TestCase):
    def test_access_blocked_with_dated_probe_and_next_step(self):
        for adapter, platform in ((discover_facebook, "facebook"), (discover_instagram, "instagram")):
            result = adapter(context([]))
            source = result["sources"][0]
            self.assertEqual((result["status"], source["status"], source["id"]), ("access_blocked", "access_blocked", platform))
            self.assertEqual(source["lastError"]["code"], "access_blocked")
            self.assertIn("Meta Content Library", source["lastError"]["message"])
            self.assertTrue(source["lastError"]["nextStep"])
            self.assertTrue(source["probe"]["attempts"])
            self.assertTrue(all(a["at"].startswith("2026-11-21") for a in source["probe"]["attempts"]))
            self.assertEqual(validate_adapter_result(result)["errors"], [])
        self.assertEqual(discover_instagram(context([]))["sources"][0]["probe"]["loginRedirects"], 3)

    def test_live_probe_is_opt_in_and_classified(self):
        probe = lambda url: (302, {"Location": "https://www.instagram.com/accounts/login/?next=x"}, b"")
        source = discover_instagram(context([], meta_probe=probe))["sources"][0]
        self.assertEqual(source["probe"]["attempts"][0]["result"], "login_redirect")
        self.assertEqual(classify_meta_response(200, {}, b'<meta property="og:title" content="x">'), "metadata_only")
        self.assertEqual(classify_meta_response(200, {}, b'og:title "creation_time":1'), "content")


class ReplayTests(unittest.TestCase):
    def test_stored_replay_matches_the_raw_responses(self):
        stored = json.loads(gzip.decompress((FIXTURES / "replay.json.gz").read_bytes()))
        self.assertEqual(stored, json.loads(json.dumps(build_replay(), ensure_ascii=False)))
        self.assertEqual(validate_adapter_result({**stored, "captures": stored["captures"]})["errors"], [])
        self.assertTrue(any(c["promotion"] for c in stored["captures"]))
        self.assertNotIn("brokerchampionofficial", {c["id"].split(":")[1] for c in stored["creators"]})

    def test_raw_probe_logs_are_dated_and_complete(self):
        rows = [r for name in ("probe-1-requests.json", "probe-2-requests.json")
                for r in json.loads((FIXTURES / name).read_text(encoding="utf-8"))]
        self.assertLessEqual(len(rows), 40)
        self.assertTrue(all(r["at"].startswith("2026-11-21") and r["result"] for r in rows))
        for row in rows:
            self.assertTrue(any((FIXTURES / f"{row['name']}{ext}").exists() for ext in (".html.gz", ".gz")))


if __name__ == "__main__":
    unittest.main()
