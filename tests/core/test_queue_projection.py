"""Persisted summaries reflect case changes and keep historical examples out of the desk."""
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import sqlite3
import subprocess
from unittest.mock import patch

from api import jobs, store
from api.card_view import card_view
from ops.demo.state_pack import code_fingerprint, remove_synthetic_cases
from v2_helpers import StateCase, VIDEO, capture, finding


class QueueProjection(StateCase):
    def listing(self, name="review", **filters):
        with store.connection() as db:
            return store.queue_list(db, name, **filters)

    def test_reopened_database_reads_persisted_rows_and_rolls_back_failed_writes(self):
        cap = capture(title="Żółte ETF")
        self.put(cap, reviewDecision={"route": "refer", "queueEligible": True}, reviewScore={"value": 70})
        with self.assertRaisesRegex(RuntimeError, "cancel"):
            with store.connection(True) as db:
                db.execute("UPDATE cases SET status='closed' WHERE id=?", (VIDEO,))
                raise RuntimeError("cancel")
        with patch.object(store, "case_dict", side_effect=AssertionError("classification on read")):
            store.init()
            self.assertEqual(self.listing(q="ŻÓŁTE")["items"][0]["id"], VIDEO)
            self.assertEqual(store.state(findings=False)["queues"]["review"], 1)
        with store.connection(True) as db:
            db.execute("UPDATE cases SET status='closed',revision=revision+1 WHERE id=?", (VIDEO,))
            store.record(db, VIDEO, "decision", "Decyzja", {"status":"closed","version":1,"route":"refer"})
        self.assertEqual(self.listing()["total"], 0)
        self.assertEqual(self.listing("closed")["items"][0]["revision"], 2)

    def test_upsert_and_metadata_only_refresh_follow_the_author(self):
        cap = capture()
        pair = (cap, finding(cap, reviewDecision={"route":"refer","queueEligible":True}, reviewScore={"value":75}))
        first = {"id":cap["creatorId"],"name":"Stara nazwa"}
        self.scan([pair], creators=[first])
        self.scan([pair], creators=[{**first,"name":"Nowa nazwa"}])
        self.assertEqual(self.listing(q="Nowa")["items"][0]["creatorName"], "Nowa nazwa")
        self.assertEqual(self.listing(q="Stara")["total"], 0)

    def test_synthetic_history_is_preserved_while_operational_views_exclude_it(self):
        fake = capture("demo-historical", platform="demo", synthetic=True)
        self.put(fake, synthetic=True, score=99)
        self.assertEqual(self.listing("all")["total"], 0)
        self.assertEqual(self.listing("demo")["items"][0]["id"], fake["id"])
        self.assertEqual(store.state()["queues"]["demo"], 0)
        self.assertEqual(store.state()["findings"], [])
        self.assertEqual(self.events(), [])
        self.assertEqual(self.versions(fake["id"]), 1)
        with store.connection() as db:
            self.assertEqual(store.report_list(db, "M1", queue="demo")["total"], 0)

    def test_card_presents_the_same_active_route_score_and_band_as_the_queue(self):
        cap = capture()
        decision = {"route":"no_signal","reason":"Wynik wariantu D."}
        variants = {"rules_1_2":{"route":"refer","reason":"Wynik aktywnych reguł.","reviewScore":{"value":94}},
                    "qual_d":{"route":"no_signal","reviewScore":{"value":0}}}
        self.put(cap, reviewDecision=decision, reviewScore={"value":0}, variants=variants)
        row = self.listing()["items"][0]
        card = card_view(self.case())
        self.assertEqual((card["reviewDecision"]["route"],card["reviewScore"]["value"],card["reviewScore"]["band"]),
                         (row["route"],row["reviewScore"],row["band"]))
        self.assertEqual(card["reviewDecision"]["reason"], row["reason"])

    def test_unread_frames_are_presented_as_checks_for_the_analyst(self):
        decision = {"route":"refer","reasons":["Nie znaleziono oznaczenia reklamy ani współpracy: w opisie ani w 3 sprawdzonych kadrach."]}
        card = card_view({"reviewDecision":decision,"coverage":{"modalities":{"frames":{"state":"selected_moments"}}},
                          "adRelationship":{"disclosure":{"where":None,"checked":["description","frames"],"notChecked":[]}}})
        self.assertNotIn("sprawdzonych kadrach", card["reviewDecision"]["reasons"][0])
        self.assertIn("oceny wzrokowej", card["reviewDecision"]["reasons"][0])
        self.assertEqual(card["adRelationship"]["disclosure"]["checked"], ["description"])
        self.assertEqual(card["adRelationship"]["disclosure"]["notChecked"], ["frames"])


class StateArchiveFingerprint(StateCase):
    def test_transfer_snapshot_excludes_synthetic_dependencies_and_preserves_real_history(self):
        fake = capture("demo-archive", platform="demo", synthetic=True)
        self.put(fake, score=95, synthetic=True)
        self.put()
        with store.connection(True) as db:
            store.record(db, VIDEO, "decision", "Zachowaj", {"status": "reviewing"})
        snapshot = store.STATE / "share.sqlite3"
        with store.connection() as db, closing(sqlite3.connect(snapshot)) as copy:
            db.backup(copy)
        remove_synthetic_cases(snapshot)
        with closing(sqlite3.connect(snapshot)) as copy:
            self.assertEqual(copy.execute("SELECT id FROM cases").fetchall(), [(VIDEO,)])
            for table, column in (("versions","id"),("history","case_id"),("events","ref"),("queue_members","id")):
                self.assertFalse(copy.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (fake["id"],)).fetchone())
            self.assertEqual(copy.execute("SELECT note FROM history WHERE action='decision'").fetchone()[0], "Zachowaj")
            self.assertEqual(copy.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.versions(fake["id"]), 1)

    def test_worker_keeps_the_restored_archive_without_replaying_sources(self):
        (store.STATE / "state-pack.json").write_text("{}")
        with patch.object(jobs, "submit") as submit:
            jobs.bootstrap_replay()
            submit.assert_not_called()

    def test_new_projection_module_changes_fingerprint_while_private_cache_does_not(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "api").mkdir()
            baseline = code_fingerprint(root)
            (root / "api/queue_view.py").write_text("FORMAT = 1\n")
            updated = code_fingerprint(root)
            self.assertNotEqual(baseline, updated)
            (root / ".runtime").mkdir()
            (root / ".runtime/private.json").write_text("{}")
            self.assertEqual(updated, code_fingerprint(root))
