"""Regressions for measured M2 evidence, pairing, stale observations and restricted reads."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analysis.engine import analyze
from api import store
from collectors.common import SourceError, digest
from collectors.m2_archive import (
    REPLAY, TARGETS, VIEWPORTS, apply_rendered, asset_bytes, encode, read_bundle, staged_captures, write_once,
)
from collectors.m2_browser import allowed_resource


class Archive(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(store, "STATE", self.root))
        store.init()

    @staticmethod
    def proof(cap, number):
        return next(check for check in analyze(cap)["checks"] if check["id"] == number)

    def test_two_publishers_three_materials_real_sizes_and_scopes(self):
        captures, creators, sources = staged_captures("replay", self.root)
        self.assertEqual(len(captures), 3)
        self.assertEqual(len(creators), 2)
        self.assertEqual({s["status"] for s in sources}, {"ok"})
        self.assertEqual({c["provenance"]["registryId"] for c in captures}, {6884980, 6884964})
        for cap in captures:
            self.assertEqual({(v["width"], v["height"]) for v in cap["m2Views"] if v["state"] == "initial"}, set(VIEWPORTS))
            self.assertEqual(len(analyze(cap)["checks"]), 19)
            self.assertEqual(self.proof(cap, "1")["state"], "spełnione")
        xtb, stocks, bdm = captures
        check = self.proof(xtb, "3")
        self.assertEqual(check["state"], "obserwacja")
        self.assertIn("dywidendy", check["evidence"])
        profit = [m for m in check["measurements"] if m["focus"] == "profit"]
        self.assertEqual(len(profit), 3)
        self.assertTrue(all(m["profitRelation"] == "same_product" and m["profitDistancePx"] > 100 for m in profit))
        self.assertIn("CFD", check["evidence"])
        self.assertEqual(self.proof(stocks, "3")["state"], "brak danych")
        self.assertEqual(self.proof(bdm, "3")["state"], "brak danych")
        suggestion = analyze(xtb)["reviewSuggestion"]
        self.assertEqual((suggestion["source"], suggestion["state"], suggestion["criterionId"]), ("rules", "review", "3"))
        self.assertIn("dywidendy", suggestion["evidence"]["text"])
        self.assertTrue(any(m["width"] == 390 and m["url"] == suggestion["evidence"]["url"] for m in profit))
        self.assertEqual(analyze(stocks)["reviewSuggestion"]["state"], "no_signal")
        self.assertEqual(analyze({"module": "M2", "description": "Rachunek inwestycyjny"})["reviewSuggestion"]["state"], "unavailable")
        geometry = self.proof(xtb, "8")["measurements"]
        self.assertEqual([m["px"] for m in geometry], ["16px", "14px", "14px"])
        self.assertTrue(all(m["inFrame"] and m["warning"]["contrast"] >= 4.5 for m in geometry))
        self.assertTrue(all(m["contentHash"] == xtb["m2EvidenceRevision"] for m in geometry))
        for measurement in geometry:
            self.assertEqual(digest(asset_bytes(REPLAY, measurement["url"].split("/")[-1])), measurement["screenshotHash"])
            self.assertEqual(digest(asset_bytes(REPLAY, measurement["domUrl"].split("/")[-1])), measurement["domHash"])

    def test_understanding_uses_verified_product_warning_only(self):
        etf, _ = read_bundle(REPLAY, "xtb-etf", "replay")
        etf["audience"] = "klient detaliczny"
        row = self.proof(etf, "9")
        self.assertEqual((row["mode"], row["state"]), ("ręczny", "brak danych"))
        self.assertIn("klient detaliczny", row["evidence"])
        self.assertIn("Oferowane instrumenty finansowe są ryzykowne.", row["evidence"])
        self.assertNotIn("dźwign", row["evidence"])
        proof, = row["measurements"]
        self.assertEqual(proof["focus"], "warning")
        self.assertEqual(proof["warning"]["productScope"], ["etf"])
        self.assertTrue(proof["inFrame"])

        stocks, _ = read_bundle(REPLAY, "xtb-akcje", "replay")
        row = self.proof(stocks, "9")
        self.assertEqual((row["mode"], row["state"]), ("ręczny", "brak danych"))
        self.assertIn("Brak potwierdzonego ostrzeżenia", row["evidence"])
        self.assertNotIn("dźwign", row["evidence"])
        self.assertNotIn("measurements", row)

    def test_crossed_frame_and_tampered_bytes_abstain(self):
        name = "xtb-etf"
        manifest = REPLAY / "manifests" / f"{name}.json"
        import json
        crossed = json.loads(manifest.read_bytes())
        crossed["frames"][0]["domHash"] = crossed["frames"][1]["domHash"]
        with self.assertRaises(SourceError):
            read_bundle(REPLAY, name, "replay", raw=encode(crossed))
        checksum = crossed["frames"][0]["screenshotHash"]
        write_once(self.root / "assets" / f"{checksum}.png", b"modified")
        with self.assertRaises(SourceError):
            asset_bytes(self.root, f"{checksum}.png")

    def test_live_403_leaves_last_material_and_does_not_attach_new_html(self):
        archive = self.root / "m2"
        name = "xtb-etf"
        archived, _ = read_bundle(REPLAY, name, "replay")
        for view in archived["m2Views"]:
            for key in ("url", "domUrl"):
                asset = view[key].rsplit("/", 1)[-1]
                write_once(archive / "assets" / asset, asset_bytes(REPLAY, asset))
        record = Path("manifests") / f"{name}.json"
        write_once(archive / record, (REPLAY / record).read_bytes())

        def forbidden(name, root):
            raise SourceError("HTTP 403", 403)

        results = staged_captures("live", archive, forbidden)
        live, _, sources = results
        self.assertEqual(len(live), 1)
        self.assertEqual(sources[0]["status"], "stale")
        self.assertEqual(sources[0]["httpStatus"], 403)
        self.assertEqual(sources[1]["status"], "forbidden")
        newer_text = {"id": "text-only", "module": "M2", "url": TARGETS[name][0], "description": "Nowy tekst"}
        discovery = {"captures": [newer_text], "creators": [], "sources": []}
        apply_rendered(discovery, results)
        preserved, = discovery["captures"]
        self.assertEqual(preserved["m2EvidenceRevision"], archived["m2EvidenceRevision"])
        self.assertEqual(preserved["observedAt"], archived["observedAt"])
        self.assertNotEqual(preserved["description"], newer_text["description"])

    def test_same_frame_new_timestamp_stale_version_and_old_assets(self):
        original, creator = read_bundle(REPLAY, "xtb-etf", "replay")
        later = deepcopy(original)
        later["observedAt"] = "2026-11-22T16:00:00+00:00"
        older = deepcopy(original)
        older["observedAt"] = "2026-11-20T16:00:00+00:00"
        older["m2EvidenceRevision"] = "1" * 64
        text_only = {key: original[key] for key in ("id", "module", "title", "url", "creatorId")}
        changed, _ = read_bundle(REPLAY, "xtb-akcje", "replay")
        changed = {**later, "m2Views": changed["m2Views"], "m2EvidenceRevision": changed["m2EvidenceRevision"]}
        changed["observedAt"] = "2026-11-23T16:00:00+00:00"

        with store.connection(True) as db:
            def ingest(cap, mode):
                return store.apply_scan(db, [(cap, analyze(cap))], [creator], [], mode)["changedFindings"]

            self.assertEqual(ingest(original, "replay"), 1)
            self.assertEqual(ingest(later, "live"), 0)
            self.assertEqual(ingest(older, "live"), 0)
            self.assertEqual(ingest(text_only, "live"), 0)
            self.assertEqual(ingest(changed, "live"), 1)
            self.assertEqual(ingest(original, "replay"), 0)
            self.assertEqual(db.execute("SELECT count(*) FROM versions").fetchone()[0], 2)
        from api.server import case_version, m2_asset
        stored_first = case_version(original["id"], 1)
        archived_image = stored_first["finding"]["evidence"][1]
        m2_name = archived_image["url"].split("/")[-1]
        restored = m2_asset(m2_name)
        self.assertEqual(restored.media_type, "image/png")
        self.assertEqual(digest(restored.body), archived_image["sha256"])


class BrowserScope(unittest.TestCase):
    def test_read_only_target_and_assets(self):
        target = TARGETS["xtb-etf"][0]
        hosts = {"www.xtb.com", "xas-cdn.xtb.com"}
        self.assertTrue(allowed_resource(target, "GET", "document", target, hosts, True))
        cases = [
            (target, "POST", "document", True), (target + "/redirect", "GET", "document", True),
            (target, "GET", "document", False), ("http://xas-cdn.xtb.com/a", "GET", "script", True),
            ("https://127.0.0.1/a", "GET", "script", True),
            ("https://www.xtb.com/a", "GET", "fetch", True), ("https://www.bdm.pl/a", "GET", "font", True),
        ]
        for url, method, kind, main in cases:
            self.assertFalse(allowed_resource(url, method, kind, target, hosts, main))
        self.assertTrue(allowed_resource("https://xas-cdn.xtb.com/a", "GET", "font", target, hosts, True))
