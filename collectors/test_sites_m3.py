"""Offline tests of the M3 crawler: budget, interval, robots.txt, redirects and offer-link ranking."""

import io
import tempfile
import unittest
from urllib.error import HTTPError

from collectors import sites


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status, self.headers = status, headers or {}


class FakeOpener:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def open(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        status, body, headers = self.pages.get(url, (404, b"", {}))
        if status != 200:
            raise HTTPError(url, status, "x", headers, io.BytesIO(body))
        return Response(body, status, headers)


HOME = b"""<html><title>Doradca Test</title><body><nav><a href="/kontakt">Kontakt</a></nav>
<a href="/oferta/doradztwo-inwestycyjne">Oferta</a><a href="/blog/wpis">Blog</a><a href="https://inna.pl/oferta">Inna</a>
<a href="/cennik">Cennik</a><main><p>Pomagamy inwestowac.</p></main><footer>Doradca Test sp. z o.o. NIP 123-456-32-18</footer></body></html>"""
OFFER = "<html><body><p>Wskażemy co kupić i sprzedać, zgodnie z Twoimi celami. Akcje i obligacje.</p></body></html>".encode()


def fetcher(pages, budget=20):
    sleeps = []
    clock = iter(range(0, 10_000)).__next__
    return sites.PoliteFetcher(budget=budget, interval=3.0, sleep=sleeps.append, opener=FakeOpener(pages),
                               clock=lambda: 0.0, now=lambda: "2026-11-21T00:00:00Z"), sleeps


class OfferLinks(unittest.TestCase):
    def test_ranks_offer_and_skips_blog_and_other_sites(self):
        links = sites.offer_links("https://doradca-test.pl/", ["/oferta/doradztwo-inwestycyjne", "/blog/wpis", "https://inna.pl/oferta", "/cennik", "/kontakt"])
        self.assertEqual(links[0], "https://doradca-test.pl/oferta/doradztwo-inwestycyjne")
        self.assertNotIn("https://inna.pl/oferta", links)
        self.assertFalse(any("blog" in link for link in links))


class Fetcher(unittest.TestCase):
    def test_interval_and_budget(self):
        f, sleeps = fetcher({"https://a.pl/": (200, b"x", {})}, budget=2)
        f.get("https://a.pl/")
        f.get("https://a.pl/")
        self.assertEqual(sleeps, [3.0])
        with self.assertRaises(sites.SourceError):
            f.get("https://a.pl/")

    def test_same_site_redirect_only(self):
        f, _ = fetcher({"https://a.pl/": (301, b"", {"Location": "https://www.a.pl/"}), "https://www.a.pl/": (200, b"ok", {}),
                        "https://b.pl/": (302, b"", {"Location": "https://evil.example/"})})
        self.assertEqual(f.get("https://a.pl/"), ("https://www.a.pl/", b"ok"))
        with self.assertRaises(sites.SourceError):
            f.get("https://b.pl/")

    def test_robots_disallow_and_absent(self):
        f, _ = fetcher({"https://a.pl/robots.txt": (200, b"User-agent: *\nDisallow: /oferta", {})})
        self.assertFalse(f.allowed("https://a.pl/oferta/x"))
        self.assertTrue(f.allowed("https://a.pl/"))
        self.assertTrue(f.allowed("https://b.pl/"))  # 404 robots.txt: no rules


class ReadFirm(unittest.TestCase):
    def test_home_and_offer_with_hash_and_footer(self):
        pages = {"https://doradca-test.pl/robots.txt": (404, b"", {}), "https://doradca-test.pl/": (200, HOME, {}),
                 "https://doradca-test.pl/oferta/doradztwo-inwestycyjne": (200, OFFER, {})}
        f, _ = fetcher(pages)
        entity = sites.read_m3_firm({"url": "https://doradca-test.pl/", "label": "doradca-test.pl"}, f, clock=lambda: "T")
        self.assertEqual([p["role"] for p in entity["pages"]], ["home", "offer"])
        self.assertEqual(len(entity["pages"][1]["sha256"]), 64)
        self.assertIn("NIP 123-456-32-18", entity["pages"][0]["identityText"])
        self.assertIn("co kupić", entity["pages"][1]["text"])

    def test_robots_block_stops_site(self):
        pages = {"https://x.pl/robots.txt": (200, b"User-agent: *\nDisallow: /", {})}
        f, _ = fetcher(pages)
        entity = sites.read_m3_firm({"url": "https://x.pl/"}, f)
        self.assertEqual(entity["pages"], [])
        self.assertIn("robots", entity["errors"][0]["error"])

    def test_discover_skips_when_budget_is_low(self):
        f, _ = fetcher({}, budget=2)
        with tempfile.TemporaryDirectory() as out:
            summary = sites.discover_m3([{"url": "https://x.pl/"}], f, out)
        self.assertIn("budżet", summary["entities"][0]["errors"][0]["error"])


if __name__ == "__main__":
    unittest.main()
