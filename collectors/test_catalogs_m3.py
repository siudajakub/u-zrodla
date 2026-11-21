"""Offline tests of the M3 seed selection from recorded search results."""

import json
from pathlib import Path
import tempfile
import unittest

from collectors import catalogs

RECORDED = Path(__file__).resolve().parents[1] / "fixtures" / "raw" / "discovery" / "m3-2026-11-21" / "search-results.json"


class Seeds(unittest.TestCase):
    def test_filters_press_regulators_documents_and_foreign_paths(self):
        self.assertFalse(catalogs.m3_seed_allowed("https://www.analizy.pl/puls-rynku/1"))
        self.assertFalse(catalogs.m3_seed_allowed("https://www.knf.gov.pl/x.pdf"))
        self.assertFalse(catalogs.m3_seed_allowed("https://family-office.example.com/en/home/"))
        self.assertFalse(catalogs.m3_seed_allowed("http://doradca.pl/"))
        self.assertTrue(catalogs.m3_seed_allowed("https://rdmwm.pl/"))

    def test_one_seed_per_site_keeps_deep_link_as_hint(self):
        data = {"observedAt": "2026-11-21", "queries": [{"id": "q", "query": "wealth", "results": [
            "https://ppcg.com.pl/portfele-inwestycyjne/", "https://ppcg.com.pl/abonament/", "https://rdmwm.pl/"]}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            seeds = catalogs.load_m3_seeds(path)
        self.assertEqual([s["url"] for s in seeds], ["https://ppcg.com.pl/", "https://rdmwm.pl/"])
        self.assertEqual(seeds[0]["offerUrl"], "https://ppcg.com.pl/portfele-inwestycyjne/")
        self.assertIsNone(seeds[1]["offerUrl"])
        self.assertEqual(seeds[0]["discovery"]["rank"], 1)

    def test_recorded_run_has_at_least_25_sites(self):
        self.assertGreaterEqual(len(catalogs.load_m3_seeds(RECORDED)), 25)


if __name__ == "__main__":
    unittest.main()
