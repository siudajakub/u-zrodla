import tempfile
import unittest
from pathlib import Path
from api import store

class CaseStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr,store,"STATE",store.STATE)
        store.STATE=Path(self.tmp.name)
        store.init()

    def test_capture_versions_survive_replay_and_change(self):
        capture={"id":"c","description":"one","title":"Sample"}
        finding={"id":"f","title":"Sample","score":30}
        creator={"id":"outside","name":"new"}
        for text in ["one","one","two","one"]:
            capture["description"]=text
            with store.connection(True) as db:
                store.apply_scan(db,[(capture,finding)],[creator],[],"replay")
        state=store.state()
        self.assertEqual(len(state["creators"]),1)
        self.assertEqual(state["findings"][0]["version"],3)
        self.assertEqual(len(state["findings"][0]["history"]),3)

    def test_request_identity(self):
        a,created=store.create_scan("replay","1")
        self.assertTrue(created)
        b,created=store.create_scan("replay","1")
        self.assertFalse(created)
        self.assertEqual(a["id"],b["id"])
        with self.assertRaises(ValueError):
            store.create_scan("live","1")

    def test_retry_failed_upload_has_single_stable_scan(self):
        initial,_=store.create_scan("upload","media-same")
        with store.connection(True) as db:
            db.execute("UPDATE scans SET status='failed' WHERE id=?",(initial["id"],))
        retry,queued=store.create_scan("upload","media-same",retry_failed=True)
        duplicate,queued_twice=store.create_scan("upload","media-same",retry_failed=True)
        self.assertTrue(queued)
        self.assertFalse(queued_twice)
        self.assertEqual(retry["id"],initial["id"])
        self.assertEqual(duplicate["id"],initial["id"])
