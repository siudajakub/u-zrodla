"""Contract v2, step S1: migration, compatibility view, origin, needsRecalc (T11, T12, T18, T19)."""
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from analysis.engine import analyze, demo_captures
from analysis.semantic import review_suggestion
from api import server, store
from collectors.discovery import discover
from v2_helpers import ROOT, StateCase, VIDEO, capture, finding, load_v1_store


def dump_v1_tables(path):
    db = sqlite3.connect(path)
    try:
        return {t: db.execute(f"SELECT * FROM {t} ORDER BY 1,2").fetchall()
                for t in ("cases", "versions", "history", "events", "creators", "sources", "scans")}
    finally:
        db.close()


class LegacyDatabase(unittest.TestCase):
    """A database written by the code at 491094d, opened by the current code."""

    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.dir = Path(self.temp)
        self.v1 = load_v1_store(self.dir)
        self.v1.init()
        cap = capture(provenance={"sourceUrl": "https://example.org/atom", "mode": "live"}, mode="live")
        found = {"id": cap["id"], "title": cap["title"], "module": "M1", "score": 94, "summary": "Stary wynik.",
                 "evidence": [{"kind": "description", "text": "Partnerem odcinka jest XTB", "url": cap["url"]}],
                 "rulesVersion": "investwatch-rules-pl-1.1", "reviewSuggestion": {"state": "review", "source": "rules"}}
        with self.v1.connection(True) as db:
            self.v1.apply_scan(db, [(cap, found)], [{"id": "youtube:UCexampleexampleexample00", "name": "Kanał"}],
                               [{"id": "atom", "name": "Atom", "status": "ok", "count": 1}], "live")
            db.execute("UPDATE cases SET status='closed',revision=revision+1 WHERE id=?", (VIDEO,))
            self.v1.record(db, VIDEO, "decision", "Jawna współpraca.", {"status": "closed"})
        self.before = dump_v1_tables(self.dir / "cases.sqlite3")
        self.v1_state = self.v1.state()
        self.enterContext(patch.object(store, "STATE", self.dir))

    def test_t11_old_case_gets_defaults_and_keeps_decision(self):
        self.assertEqual(sqlite3.connect(self.dir / "cases.sqlite3").execute("PRAGMA user_version").fetchone()[0], 0)
        store.init()
        state = store.state()
        found, = state["findings"]
        self.assertEqual(state["schema"]["version"], store.SCHEMA_VERSION)
        self.assertIsNotNone(state["schema"]["migratedAt"])
        self.assertEqual((found["status"], found["revision"], found["version"]), ("closed", 2, 1))
        self.assertEqual([h["action"] for h in found["history"]], ["capture", "decision"])
        self.assertEqual(found["origin"], "live")
        self.assertIs(found["needsRecalc"], True)
        self.assertEqual(found["derived"], "legacy")
        self.assertEqual(found["analysisVersion"]["schema"], 1)
        self.assertEqual(found["analysisVersion"]["rules"], "investwatch-rules-pl-1.1")
        self.assertEqual(found["requalification"]["state"], "pending")
        self.assertEqual(found["requalification"]["reasonCode"], "schema_1")
        self.assertIn("1.1", found["needsRecalcReason"])
        # A legacy record gets no invented v2 judgement.
        for field in ("reviewDecision", "reviewScore", "adRelationship", "discovery", "reach"):
            self.assertNotIn(field, found)
        self.assertEqual(found["score"], 94)
        self.assertEqual(found["reviewSuggestion"]["state"], "review")

    def test_t11_second_start_changes_nothing(self):
        store.init()
        first = dump_v1_tables(self.dir / "cases.sqlite3")
        meta = sqlite3.connect(self.dir / "cases.sqlite3").execute("SELECT * FROM schema_meta").fetchall()
        time.sleep(.01)
        store.init()
        store.init()
        self.assertEqual(dump_v1_tables(self.dir / "cases.sqlite3"), first)
        self.assertEqual(first, self.before)
        self.assertEqual(sqlite3.connect(self.dir / "cases.sqlite3").execute("SELECT * FROM schema_meta").fetchall(), meta)
        self.assertEqual(len(meta), len(store.MIGRATIONS))

    def test_t11_rollback_to_v1_code_keeps_working(self):
        store.init()
        cap = capture(description="Nowy opis po migracji.")
        with self.v1.connection(True) as db:
            result = self.v1.apply_scan(db, [(cap, {"id": cap["id"], "title": "T", "score": 10, "summary": "s", "evidence": []})],
                                        [{"id": "youtube:other", "name": "Inny"}], [], "live")
        self.assertEqual(result["changedFindings"], 1)
        self.assertEqual(self.v1.state()["findings"][0]["version"], 2)
        self.assertEqual(store.state()["findings"][0]["version"], 2)

    def test_t18_v1_state_keys_are_a_subset(self):
        store.init()
        new = store.state(1)
        self.assertLessEqual(set(self.v1_state), set(new))
        old_case, new_case = self.v1_state["findings"][0], new["findings"][0]
        self.assertLessEqual(set(old_case), set(new_case))
        for key, value in old_case.items():
            self.assertEqual(new_case[key], value, key)
        self.assertEqual(new["creators"], self.v1_state["creators"])
        self.assertEqual(new["sources"], self.v1_state["sources"])


class V1Fingerprints(unittest.TestCase):
    def test_s2_recognises_what_v1_stored_for_real_fixtures(self):
        """Normalization must not turn every stored case into a new version at the first S2 scan."""
        def evaluate(cap):
            found = analyze(cap)
            found["semantic"] = {"status": "unavailable"}
            if "reviewSuggestion" not in found:
                found["reviewSuggestion"] = review_suggestion(cap, found["semantic"], found)
            return cap, found

        with tempfile.TemporaryDirectory() as directory:
            v1 = load_v1_store(directory)
            v1.init()
            pairs = [evaluate(c) for c in demo_captures() + discover("replay", ())["captures"]]
            with v1.connection(True) as db:
                # v1 code never saw the shadow qualification fields of S5: it stored the legacy finding.
                v1.apply_scan(db, [(c, store.split_shadow(f)[0]) for c, f in pairs], [], [], "replay")
            with patch.object(store, "STATE", Path(directory)):
                store.init()
                with store.connection(True) as db:
                    result = store.apply_scan(db, pairs, [], [], "replay")
                self.assertEqual(result["changedFindings"], 0)
                self.assertGreater(len(store.state()["findings"]), 10)


class ParallelStart(unittest.TestCase):
    CODE = ("import sys,time;from api import store;time.sleep(max(0,float(sys.argv[1])-time.time()));"
            "store.init();print(store.schema_info(__import__('sqlite3').connect(store.STATE/'cases.sqlite3'))['version'])")

    def run_processes(self, directory, count=4):
        start = time.time() + 1.5
        env = {"INVESTWATCH_STATE": str(directory), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
        procs = [subprocess.Popen([sys.executable, "-B", "-c", self.CODE, str(start)], cwd=ROOT, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(count)]
        return [(p.communicate(timeout=60), p.returncode) for p in procs]

    def check(self, directory, results):
        for (out, err), code in results:
            self.assertEqual((code, out.strip()), (0, str(store.SCHEMA_VERSION)), err)
        db = sqlite3.connect(Path(directory) / "cases.sqlite3")
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], store.SCHEMA_VERSION)
        self.assertEqual(db.execute("SELECT count(*) FROM schema_meta").fetchone()[0], len(store.MIGRATIONS))
        self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_t12_fresh_database(self):
        with tempfile.TemporaryDirectory() as directory:
            self.check(directory, self.run_processes(directory))

    def test_t12_legacy_database(self):
        with tempfile.TemporaryDirectory() as directory:
            v1 = load_v1_store(directory)
            v1.init()
            cap = capture()
            with v1.connection(True) as db:
                v1.apply_scan(db, [(cap, {"id": cap["id"], "title": "T", "score": 10, "summary": "s", "evidence": []})], [], [], "live")
            self.check(directory, self.run_processes(directory))
            with patch.object(store, "STATE", Path(directory)):
                self.assertEqual(len(store.state()["findings"]), 1)


class Origin(StateCase):
    def test_t19_derivation(self):
        derive = store.derive_origin
        self.assertEqual(derive({"mode": "replay", "synthetic": True}), "synthetic")
        self.assertEqual(derive({"mode": "live", "contractDemo": True}), "synthetic")
        self.assertEqual(derive({"mode": "upload", "platform": "upload"}), "upload")
        self.assertEqual(derive({"platform": "upload"}), "upload")
        self.assertEqual(derive({"mode": "live"}), "live")
        self.assertEqual(derive({"mode": "replay"}), "replay")
        self.assertEqual(derive({"provenance": {"mode": "live"}}), "live")

    def test_t19_stored_cases_read_with_origin(self):
        real = capture("youtube:BBBBBBBBBBB")
        fake = capture("demo-1", platform="demo", synthetic=True)
        self.scan([(real, finding(real)), (fake, finding(fake, synthetic=True))], mode="replay")
        up = capture("upload-1", platform="upload")
        self.scan([(up, finding(up))], mode="upload")
        self.assertEqual(self.case("youtube:BBBBBBBBBBB")["origin"], "replay")
        self.assertEqual(self.case("demo-1")["origin"], "synthetic")
        self.assertEqual(self.case("upload-1")["origin"], "upload")

    def test_t19_promotion_to_live_changes_origin(self):
        cap = capture()
        self.put(cap, mode="replay")
        self.assertEqual(self.case()["origin"], "replay")
        self.put(cap, mode="live")
        self.assertEqual(self.case()["origin"], "live")


class NeedsRecalc(StateCase):
    def test_current_record_is_not_stale(self):
        rules = store.analysis_current()["rules"]
        version = {"rules": rules, "model": None, "schema": store.ANALYSIS_SCHEMA, "variant": store.ANALYSIS_VARIANT}
        self.put(rulesVersion=rules, analysisVersion=version)
        found = self.case()
        self.assertIs(found["needsRecalc"], False)
        self.assertEqual(found["requalification"]["state"], "current")
        self.assertNotIn("derived", found)

    def test_old_rules_are_stale_even_with_current_schema(self):
        version = {"rules": "investwatch-rules-pl-1.1", "model": None, "schema": store.ANALYSIS_SCHEMA, "variant": "rules_1_2"}
        self.put(rulesVersion="investwatch-rules-pl-1.1", analysisVersion=version)
        found = self.case()
        self.assertIs(found["needsRecalc"], True)
        self.assertEqual(found["requalification"]["reasonCode"], "rules_changed")

    def test_m2_is_compared_with_its_own_rules(self):
        cap = capture("web:example.org/m2", module="M2")
        self.put(cap, module="M2", rulesVersion=store.M2_RULES,
                 analysisVersion={"rules": store.M2_RULES, "schema": store.ANALYSIS_SCHEMA, "variant": "rules_1_2"})
        self.assertIs(self.case("web:example.org/m2")["needsRecalc"], False)

    def test_state_and_health_report_schema(self):
        state = store.state()
        self.assertEqual(state["schema"]["version"], store.SCHEMA_VERSION)
        self.assertEqual(state["analysisCurrent"]["schema"], store.ANALYSIS_SCHEMA)
        self.assertEqual(state["analysisCurrent"]["variant"], "rules_1_2")
        self.assertEqual(server.health(), {"status": "ok", "schema": store.SCHEMA_VERSION})


if __name__ == "__main__":
    unittest.main()
