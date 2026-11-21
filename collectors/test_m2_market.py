"""M2 market archive: discovery ranking, digest checks and the 19 criteria on real captured pages.

No network, no browser: everything is read from data/probe-snapshots/m2/market/.
"""
import json
import shutil
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from analysis.m2_card import card
from analysis.m2_rules import NA, OBSERVATION, OK, PREMISE, evaluate
from collectors.common import SourceError
from collectors.m2_discovery import FIRMS, anchors, locale_prefix, offer_score, product_family, rank_links, register_row
from collectors.m2_market import MARKET, market_captures, material, read_manifest

CAPTURES, CREATORS, SOURCES = market_captures()
BY_ID = {cap["m2Market"]["manifest"]: cap for cap in CAPTURES}


def rows(pid):
    return {row["id"]: row for row in evaluate(material(BY_ID[pid]))}


class Discovery(unittest.TestCase):
    FIRM = next(f for f in FIRMS if f.key == "xtb")

    def test_offer_links_are_ranked_from_the_home_page_only(self):
        html = """<a href="/pl/etf">ETF-y iShares</a><a href="/pl/edukacja">Edukacja</a><a href="/pl/kontakt">Kontakt</a>
                  <a href="https://evil.example/pl/akcje">Akcje</a><a href="/pl/akcje?x=1">Akcje i fundusze ETF</a>
                  <a href="/en/stocks">Stocks</a><a href="/pl/kid">KID akcje</a>""".encode()
        links, _ = anchors(html)
        ranked = rank_links(links, "https://www.xtb.com/pl", self.FIRM, prefix=locale_prefix("https://www.xtb.com/pl"))
        urls = [item["url"] for item in ranked]
        self.assertEqual(urls[0], "https://www.xtb.com/pl/akcje")  # query dropped, highest score
        self.assertIn("https://www.xtb.com/pl/etf", urls)
        for excluded in ("edukacja", "kontakt", "evil", "/en/", "/kid"):
            self.assertFalse(any(excluded in url for url in urls), excluded)
        self.assertEqual(offer_score("https://www.xtb.com/pl/blog/zysk", "Zysk", self.FIRM.home)[0], 0)
        self.assertNotEqual(product_family("https://www.xtb.com/pl/etf"), product_family("https://www.xtb.com/pl/forex"))
        self.assertEqual(locale_prefix("https://www.ig.com/ie/pl"), "/ie/pl")

    def test_firms_come_from_the_register_copies_with_entity_types(self):
        types = {register_row(firm)["entityType"] for firm in FIRMS}
        self.assertEqual(types, {"domestic_investment_firm", "domestic_bank", "foreign_investment_firm_branch"})
        self.assertGreaterEqual(len(FIRMS), 8)
        self.assertEqual(register_row(next(f for f in FIRMS if f.key == "cmc"))["name"], "CMC Markets Germany GmbH")


class Archive(unittest.TestCase):
    def test_coverage_firms_pages_and_views(self):
        self.assertEqual(len(CAPTURES), 25)
        self.assertEqual([s for s in SOURCES if s["status"] != "ok"], [])
        firms = {cap["m2Market"]["firm"]["registryId"] for cap in CAPTURES}
        self.assertGreaterEqual(len(firms), 8)
        branches = {cap["m2Market"]["firm"]["brand"] for cap in CAPTURES
                    if cap["m2Market"]["firm"]["entityType"] == "foreign_investment_firm_branch"}
        self.assertEqual(branches, {"LYNX", "Finax", "CMC Markets"})
        for cap in CAPTURES:
            views = cap["m2Market"]["views"]
            self.assertEqual(set(views), {"desktop", "phone"})
            self.assertEqual((views["phone"]["width"], views["desktop"]["width"]), (390, 1440))
            self.assertTrue(cap["m2Market"]["discovery"]["from"])
        plan = json.loads((MARKET / "discovery.json").read_text(encoding="utf-8"))
        discovered = {page["url"] for firm in plan["firms"] for page in firm["pages"]}
        self.assertEqual(len(discovered), 24)
        self.assertTrue(all(cap["url"] in discovered or cap["m2Market"]["kind"] == "archive" for cap in CAPTURES))

    def test_tampered_asset_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(MARKET / "manifests", root / "manifests")
            shutil.copytree(MARKET / "assets", root / "assets")
            manifest = json.loads((root / "manifests" / "bossa-oferta-kontrakty.json").read_text())
            target = root / "assets" / manifest["views"][0]["screenshot"]
            target.write_bytes(target.read_bytes() + b"x")
            with self.assertRaises(SourceError):
                read_manifest(root / "manifests" / "bossa-oferta-kontrakty.json", root)


class RealCriteria(unittest.TestCase):
    """Real positive and negative examples (premise / met) per criterion, where the archive has them."""

    def check(self, pid, key, state, contains=None):
        row = rows(pid)[key]
        self.assertEqual(row["state"], state, f"{pid} {key}: {row['evidence']}")
        if contains:
            self.assertIn(contains, row["evidence"])
        return row

    def test_profit_claim_needs_the_same_products_warning_on_xtb_stocks_and_etf(self):
        self.check("xtb-pl-akcje", "3", PREMISE, "CFD")       # only the CFD warning: not a stock warning
        self.check("xtb-pl-etf", "3", PREMISE, "dywidend")     # ETF warning exists, too far on the phone
        self.check("lynx-online-broker-cfd-broker", "3", OK)   # CFD claim with the CFD warning next to it
        self.check("bossa-oferta-akcje-obligacje", "3", NA)    # fee benefits only

    def test_presentation_rows(self):
        self.check("noble-klient-indywidualny-rachunek-ike", "4", PREMISE, "11 px")
        self.check("bossa-oferta-akcje-obligacje", "4", OK)
        self.check("finax-pl-produkty-inwestowanie-w-etf", "5", PREMISE, "po przewinięciu")
        self.check("bossa-oferta-kontrakty", "5", OK)
        self.check("noble-klient-indywidualny-rachunek-ike", "6", PREMISE, "stopce")
        self.check("bossa-oferta-akcje-obligacje", "6", OK)
        self.check("pekao-biuro-maklerskie-nowy-klient-rachunek-inwestycyjny-w-bm-peka", "7", PREMISE, "rozwin")
        self.check("bossa-oferta-akcje-obligacje", "7", OK)
        self.check("bdm-obligacje", "8", PREMISE, "nie dopasowuje się do telefonu")
        self.check("bossa-oferta-akcje-obligacje", "8", OK)
        self.check("bossa-oferta-kontrakty", "9", PREMISE, "FOG-PL")
        self.check("lynx-online-broker-cfd-broker", "9", OK)
        self.check("bossa-oferta-akcje-obligacje", "10", OK)

    def test_content_rows(self):
        self.check("bdm-obligacje", "1", OK)
        self.check("cmc-pl-pl-akcje", "2", OBSERVATION)
        self.check("ing-indywidualni-oferta-emerytalna-ike-funduszowe", "2", OK, "marketingowy")
        self.check("tms-fundusze-etf", "11", PREMISE)
        self.check("xtb-pl-edukacja", "11", OK)
        self.check("bdm-rachunek-emerytalny", "15", PREMISE, "Wykryto prognozę")
        self.check("bdm-rachunek-emerytalny", "16", PREMISE, "podatku")
        self.check("noble-oferta-best-s-a-obligacje-serii-af4", "17", OK)
        self.check("tms-oferta-kryptowaluty", "18", PREMISE, "Komisji Nadzoru Finansowego")
        self.check("bossa-oferta-akcje-obligacje", "18", OK)
        for key in ("12a", "12b", "13", "14"):
            self.check("xtb-pl-etf", key, NA)

    def test_controls_and_card(self):
        for control in ("xtb-pl-edukacja", "lynx-online-broker-cfd-broker"):
            self.assertEqual(card(BY_ID[control])[3]["reviewDecision"]["route"], "no_signal", control)
        _, _, evidence, extra = card(BY_ID["noble-klient-indywidualny-rachunek-ike"])
        self.assertEqual(extra["reviewDecision"]["route"], "refer")
        self.assertEqual(len(extra["reviewDecision"]["reasons"]), 3)
        self.assertEqual(extra["m2Card"]["firm"]["entityLabel"], "dom maklerski")
        self.assertTrue(any(e["url"].startswith("/evidence/m2/market/") for e in evidence))
        branch = card(BY_ID["cmc-pl-pl-akcje"])[3]["m2Card"]["firm"]
        self.assertEqual(branch["entityLabel"], "oddział zagranicznej firmy inwestycyjnej")


if __name__ == "__main__":
    unittest.main()
