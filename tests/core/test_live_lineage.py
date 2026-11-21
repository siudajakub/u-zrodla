"""Check durable replay/live lineage with a private temporary SQLite database."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analysis.engine import analyze
from api import store

AUTHOR = "apple-podcasts:701"
CASE = AUTHOR + ":episode:original"
URL = "https://example.org/public/episode"
FEED = "https://example.org/public/rss"
ARCHIVE_TIME = "2026-11-20T10:00:00+00:00"
LIVE_TIME = "2026-11-21T11:00:00+00:00"


class LiveLineageTest(unittest.TestCase):
    def setUp(self):
        state = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(store, "STATE", Path(state)))
        store.init()

    def scan(self, mode, description=None, creators=()):
        observed = LIVE_TIME if mode == "live" else ARCHIVE_TIME
        findings = []
        if description is not None:
            capture = {
                "id": CASE, "creatorId": AUTHOR, "title": "Portfel inwestycyjny",
                "description": description, "url": URL, "module": "M1",
                "platform": "apple-podcasts", "observedAt": observed,
                "mode": mode, "provenance": {"mode": mode, "sourceUrl": FEED},
            }
            findings.append((capture, analyze(capture)))
        sources = [{
            "id": "catalogue", "name": "Katalog", "status": "ok",
            "count": len(creators) or len(findings), "lastSuccessAt": observed,
        }]
        with store.connection(True) as db:
            return store.apply_scan(db, findings, creators, sources, mode)

    def test_equal_live_capture_promotes_provenance_without_new_version_or_alert(self):
        description = "Użyj kodu polecającego PORTFEL przy otwarciu rachunku."
        self.assertEqual(self.scan("replay", description)["changedFindings"], 1)
        self.assertEqual(self.scan("live", description)["changedFindings"], 0)
        self.assertEqual(self.scan("live", description)["changedFindings"], 0)
        self.assertEqual(self.scan("replay", "Wcześniejszy opis bez kodu.")["changedFindings"], 0)

        state = store.state()
        finding, = state["findings"]
        self.assertEqual((finding["mode"], finding["version"], finding["revision"]), ("live", 1, 1))
        self.assertEqual(finding["observedAt"], LIVE_TIME)
        self.assertEqual(finding["description"], description)
        self.assertEqual(finding["evidence"][0]["url"], URL)
        self.assertEqual([event["ref"] for event in state["events"]], [CASE])
        self.assertEqual(state["sources"][0]["lastSuccessAt"], LIVE_TIME)

    def test_live_edit_keeps_decision_and_both_versions_through_later_replay(self):
        from api import server

        archive_text = "Omawiamy inwestowanie w akcje."
        live_text = "Użyj kodu polecającego PORTFEL przy otwarciu rachunku."
        self.scan("replay", archive_text)
        server.decision(CASE, server.Decision(
            status="reviewing", expectedRevision=1, note="Ustalić zasięg i warunki polecenia.",
        ))
        self.assertEqual(self.scan("live", live_text)["changedFindings"], 1)
        self.assertEqual(self.scan("replay", archive_text)["changedFindings"], 0)
        self.assertEqual(self.scan("live", live_text)["changedFindings"], 0)

        finding = server.case(CASE)
        self.assertEqual((finding["status"], finding["version"], finding["revision"]), ("reviewing", 2, 3))
        self.assertEqual(finding["mode"], "live")
        self.assertIs(finding["possibleUndisclosedPromotion"], True)
        self.assertIn("kod", finding["evidence"][0]["text"])
        self.assertEqual(finding["evidence"][0]["url"], URL)
        first = server.case_version(CASE, 1)
        second = server.case_version(CASE, 2)
        self.assertEqual(first["capture"]["description"], archive_text)
        self.assertEqual(second["capture"]["description"], live_text)
        self.assertEqual([entry["action"] for entry in finding["history"]], ["capture", "decision", "capture"])
        self.assertEqual(finding["history"][1]["note"], "Ustalić zasięg i warunki polecenia.")

    def test_creator_discovery_persists_first_live_and_later_catalogue_changes(self):
        seed = {"id": "youtube:seed", "name": "Profil startowy", "isSeed": True}
        replay = {"id": AUTHOR, "name": "Audycja z replay", "discoveredVia": "Archiwum"}
        promoted = {**replay, "name": "Audycja na żywo", "discoveredVia": "Zapytanie o ETF"}
        new = {"id": "peertube:some.example/channel", "name": "Nowy kanał",
               "discoveredVia": "Zapytanie o obligacje"}
        changed = {**new, "name": "Kanał po zmianie nazwy"}

        first = self.scan("replay", creators=(seed, replay))
        live = self.scan("live", creators=(seed, promoted, new))
        again = self.scan("live", creators=(seed, promoted, changed))
        self.scan("replay", creators=(seed, replay, new))

        self.assertEqual((first["newCreators"], first["firstLiveCreators"]), (1, 0))
        self.assertEqual((live["newCreators"], live["firstLiveCreators"]), (1, 2))
        self.assertEqual((again["newCreators"], again["firstLiveCreators"]), (0, 0))

        creators = {creator["id"]: creator for creator in store.state()["creators"]}
        self.assertEqual(len(creators), 3)
        self.assertEqual((creators[AUTHOR]["firstMode"], creators[AUTHOR]["lastMode"]), ("replay", "live"))
        self.assertEqual(creators[AUTHOR]["discoveredVia"], "Zapytanie o ETF")
        self.assertEqual(creators[AUTHOR]["name"], "Audycja na żywo")
        self.assertEqual(creators[new["id"]]["name"], changed["name"])
        self.assertEqual(creators[new["id"]]["firstMode"], "live")


if __name__ == "__main__":
    unittest.main()
