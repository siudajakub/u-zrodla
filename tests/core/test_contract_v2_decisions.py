"""Contract v2 decisions (T6, T7, T27): revisions, workflow queues and exports."""
import csv
import io
import threading
import unittest
from urllib.parse import quote
from urllib.request import urlopen

from fastapi import HTTPException

from api import server, store
from v2_helpers import HttpCase, StateCase, VIDEO, capture, finding


def decide(status="reviewing", revision=1, note="Sprawdzić."):
    return server.Decision(status=status, expectedRevision=revision, note=note)


class ParallelDecision(StateCase):
    def test_t6_two_writers_one_wins(self):
        self.put()
        barrier = threading.Barrier(2)
        outcomes = []

        def writer(status):
            barrier.wait()
            try:
                outcomes.append(("ok", server.decision(VIDEO, decide(status))["revision"]))
            except HTTPException as error:
                outcomes.append(("conflict", error.status_code))

        threads = [threading.Thread(target=writer, args=(s,)) for s in ("reviewing", "closed")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(sorted(o[0] for o in outcomes), ["conflict", "ok"])
        self.assertIn(("conflict", 409), outcomes)
        found = self.case()
        self.assertEqual(found["revision"], 2)
        self.assertEqual([h["action"] for h in found["history"]].count("decision"), 1)


class ConflictBody(HttpCase):
    def test_t6_conflict_carries_current_state(self):
        self.put()
        path = "/v1/cases/" + VIDEO.replace(":", "%3A")
        self.assertEqual(self.request("PATCH", path, {"status": "reviewing", "expectedRevision": 1, "note": "A"})[0], 200)
        status, body = self.request("PATCH", path, {"status": "closed", "expectedRevision": 1, "note": "B"})
        self.assertEqual(status, 409)
        self.assertIsInstance(body["detail"], str)  # old clients keep reading a string
        self.assertEqual(body["current"], {"revision": 2, "status": "reviewing", "version": 1, "workflowStage": "review"})


class ReReviewFlags(StateCase):
    def decide_closed(self):
        server.decision(VIDEO, decide("closed", self.case()["revision"], "Jawna współpraca."))

    def test_t7_new_content_after_decision_is_pending_re_review(self):
        self.put()
        self.decide_closed()
        self.put(capture(description="Opis po edycji."))
        found = self.case()
        self.assertEqual(found["status"], "closed")
        self.assertIs(found["pendingReReview"], True)
        self.assertIs(found["reviewStale"], False)
        self.assertEqual(found["lastDecision"]["version"], 1)

    def test_t27_route_change_after_decision_is_stale_not_pending(self):
        cap = capture()
        self.put(cap, reviewDecision={"route": "refer"})
        self.decide_closed()
        self.put(cap, reviewDecision={"route": "no_signal"}, summary="Nowa analiza.")
        found = self.case()
        self.assertIs(found["reviewStale"], True)
        self.assertIs(found["pendingReReview"], False)
        self.assertEqual(found["status"], "closed")

    def test_t27_next_decision_clears_both_flags(self):
        self.put()
        self.decide_closed()
        self.put(capture(description="Opis po edycji."))
        server.decision(VIDEO, decide("closed", self.case()["revision"], "Przejrzano nową wersję."))
        found = self.case()
        self.assertEqual((found["pendingReReview"], found["reviewStale"]), (False, False))

    def test_decision_survives_new_version(self):
        self.put()
        self.decide_closed()
        self.put(capture(description="Opis po edycji."))
        found = self.case()
        self.assertEqual((found["status"], found["version"]), ("closed", 2))
        self.assertEqual([h["action"] for h in found["history"]], ["capture", "decision", "capture"])


class FollowUpWorkflow(HttpCase):
    PATH = "/v1/cases/" + VIDEO.replace(":", "%3A")
    SIGNAL = {"reviewDecision": {"route": "refer", "queueEligible": True}, "reviewScore": {"value": 90}}

    def submit(self, resolution, case, note="Uzasadnienie decyzji.", **extra):
        body = {"resolution": resolution, "expectedRevision": case["revision"], "reviewedVersion": case["version"],
                "note": note, **extra}
        return self.request("PATCH", self.PATH, body)

    def assert_queues(self, card, expected):
        self.assertEqual(set(card["queues"]), expected | {"all"})
        for queue in ("review", "control", "supplement", "closed", "adRegister", "incomplete"):
            status, listing = self.request("GET", "/v1/queues/" + queue)
            self.assertEqual(status, 200)
            self.assertEqual(listing["counts"][queue], int(queue in expected))
            self.assertEqual(listing["total"], int(queue in expected))
            if queue in expected:
                self.assertEqual(listing["items"][0]["workflowStage"], card["workflowStage"])
                self.assertEqual(listing["items"][0]["revision"], card["revision"])

    def test_control_result_audit_and_repeat_after_closing(self):
        self.put(**self.SIGNAL, adRegistry={"state": "included"})
        first = self.case()
        self.assert_queues(first, {"review", "adRegister"})
        status, controlled = self.submit("refer_to_control", first, "Zweryfikować oznaczenie.", requestId="referral-1")
        self.assertEqual((status, controlled["workflowStage"], controlled["status"]), (200, "control", "reviewing"))
        self.assert_queues(controlled, {"control", "adRegister"})
        self.assertEqual(self.submit("control_result", first)[0], 409)
        status, closed = self.submit("control_result", controlled, "Firma udokumentowała oznaczenie.", requestId="result-1")
        self.assertEqual((status, closed["workflowStage"], closed["revision"]), (200, "closed", 3))
        self.assert_queues(closed, {"closed", "adRegister"})
        self.assertEqual(self.submit("refer_to_control", first, "Zweryfikować oznaczenie.", requestId="referral-1"), (200, closed))
        self.assertEqual(self.submit("refer_to_control", first, "Inna treść.", requestId="referral-1")[0], 409)
        history = [entry for entry in closed["history"] if entry["action"] == "decision"]
        self.assertEqual([(h["fromStage"], h["workflowStage"], h["resolution"], h["version"]) for h in history],
                         [("review", "control", "refer_to_control", 1), ("control", "closed", "control_result", 1)])
        self.assertEqual(history[-1]["note"], "Firma udokumentowała oznaczenie.")
        self.assertEqual(len(self.events("case")), 2)

    def test_data_received_requeues_below_threshold_and_accepts_new_decision(self):
        self.put(**self.SIGNAL)
        status, supplement = self.submit("complete_data", self.case(), "Brakuje informacji o dacie publikacji.")
        self.assertEqual((status, supplement["workflowStage"]), (200, "supplement"))
        self.assert_queues(supplement, {"supplement"})
        self.put(capture(description="Opis z wyjaśnieniem i datą."), reviewDecision={"route": "no_signal", "queueEligible": False})
        updated = self.case()
        self.assertTrue(updated["pendingReReview"])
        self.assert_queues(updated, {"supplement"})
        self.assertEqual(self.submit("data_received", supplement)[0], 409)
        status, review = self.submit("data_received", updated, "Dostarczono zrzut z datą 1 listopada.")
        self.assertEqual((status, review["workflowStage"], review["pendingReReview"]), (200, "review", False))
        self.assert_queues(review, {"review"})
        self.assertEqual(review["lastDecision"]["version"], 2)
        self.assertEqual(review["lastDecision"]["note"], "Dostarczono zrzut z datą 1 listopada.")
        status, closed = self.submit("no_signal", review)
        self.assertEqual((status, closed["lastDecision"]["resolution"]), (200, "no_signal"))
        self.assert_queues(closed, {"closed"})

    def test_new_evidence_after_closure_preserves_the_decision_until_explicit_reopen(self):
        self.put(**self.SIGNAL)
        status, closed = self.submit("close", self.case())
        self.assertEqual((status, closed["workflowStage"]), (200, "closed"))
        self.put(capture(description="Istotna zmiana treści."), **self.SIGNAL)
        next_version = self.case()
        self.assertEqual((next_version["workflowStage"], next_version["lastDecision"]["version"]), ("closed", 1))
        self.assertTrue(next_version["pendingReReview"])
        self.assert_queues(next_version, {"closed", "review"})
        status, conflict = self.submit("refer_to_control", next_version)
        self.assertEqual((status, conflict["current"]["workflowStage"]), (409, "closed"))
        status, review = self.submit("reopen", next_version, "Ponowna ocena nowego opisu.")
        self.assertEqual((status, review["workflowStage"], review["pendingReReview"]), (200, "review", False))
        self.assert_queues(review, {"review"})
        self.assertEqual(self.submit("refer_to_control", review)[1]["workflowStage"], "control")

    def test_older_resolution_is_mapped_again_when_the_projection_is_rebuilt(self):
        self.put(**self.SIGNAL)
        with store.connection(True) as db:
            db.execute("UPDATE cases SET status='reviewing',revision=2 WHERE id=?", (VIDEO,))
            store.record(db, VIDEO, "decision", "Historyczne przekazanie", {"status": "reviewing", "revision": 2,
                         "resolution": "refer_to_control", "version": 1, "route": "refer"})
            db.execute("UPDATE queue_generation SET signature='old-format'")
        store.init()
        self.assert_queues(self.request("GET", self.PATH)[1], {"control"})
        self.assertEqual(self.submit("control_result", self.case())[1]["workflowStage"], "closed")


class WorkflowReport(HttpCase):
    SOURCES = {
        "M1": capture(),
        "M2": capture("web:example.org/reklama:m2", module="M2", platform="web", url="https://example.org/reklama"),
        "M3": capture("web:example.net/oferta:m3", module="M3", platform="web", url="https://example.net/oferta"),
    }

    def setUp(self):
        super().setUp()
        self.scan([(cap, finding(cap)) for cap in self.SOURCES.values()])

    def resolve(self, module, resolution, note):
        path = "/v1/cases/" + quote(self.SOURCES[module]["id"], safe="")
        status, card = self.request("PATCH", path, {"resolution": resolution, "note": note, "expectedRevision": 1, "reviewedVersion": 1})
        self.assertEqual(status, 200, card)
        return card

    def test_mixed_control_report_downloads_audited_decisions_from_all_three_modules(self):
        note = '=1+1, "sprawdzić"'
        decisions = {module: self.resolve(module, "refer_to_control", note if module == "M1" else "Sprawdzić ofertę.")
                     for module in self.SOURCES}
        self.put({**self.SOURCES["M3"], "description": "Nowa udokumentowana treść oferty."})
        path = "/v1/report?module=all&queue=control"
        status, report = self.request("GET", path)
        self.assertEqual((status, report["module"], report["queues"], report["total"]), (200, "all", ["control"], 3))
        by_module = {row["modul"]: row for row in report["items"]}
        for module, cap in self.SOURCES.items():
            row = by_module[module]
            self.assertEqual((row["id"], row["url"], row["etap"], row["rodzajDecyzji"], row["sprawdzonaWersja"]),
                             (cap["id"], cap["url"], "control", "refer_to_control", 1))
            self.assertEqual(row["dataDecyzji"], decisions[module]["lastDecision"]["at"])
        self.assertEqual(by_module["M1"]["uzasadnienieDecyzji"], note)
        with urlopen(self.base + path + "&format=csv", timeout=4) as response:
            raw = response.read()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(response.headers["X-Total-Count"], "3")
            self.assertIn("investwatch-raport-all.csv", response.headers["Content-Disposition"])
        csv_rows = {row["modul"]: row for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))}
        self.assertEqual(set(csv_rows), set(self.SOURCES))
        self.assertEqual(csv_rows["M1"]["uzasadnienieDecyzji"], "'" + note)
        self.assertEqual(csv_rows["M3"]["url"], self.SOURCES["M3"]["url"])
        self.assertEqual(csv_rows["M3"]["sprawdzonaWersja"], "1")
        with urlopen(self.base + path + "&format=csv&limit=2", timeout=4) as response:
            self.assertEqual(response.headers["X-Next-Cursor"], "2")
        self.assertEqual(self.request("GET", path + "&platform=web")[1]["total"], 2)

    def test_module_report_stays_compatible_and_empty_legacy_decision_fields_are_safe(self):
        self.resolve("M1", "complete_data", "Brakuje daty emisji.")
        self.resolve("M2", "close", "Zakończono sprawdzenie reklamy.")
        with store.connection(True) as db:
            db.execute("UPDATE cases SET status='closed' WHERE id=?", (self.SOURCES["M3"]["id"],))
        _, legacy = self.request("GET", "/v1/report?module=M3")
        self.assertEqual(legacy["columns"], store.REPORT_COLUMNS["M3"])
        self.assertEqual(legacy["items"][0]["statusDecyzji"], "closed")
        _, one_module = self.request("GET", "/v1/report?module=M2&queue=closed")
        self.assertEqual(one_module["columns"][:len(store.REPORT_COLUMNS["M2"])], store.REPORT_COLUMNS["M2"])
        self.assertEqual(one_module["items"][0]["rodzajDecyzji"], "close")
        _, closed = self.request("GET", "/v1/report?module=all&queue=closed")
        historical = next(row for row in closed["items"] if row["modul"] == "M3")
        self.assertEqual(historical["etap"], "closed")
        self.assertTrue(all(historical[field] is None for field in store.WORKFLOW_REPORT_COLUMNS[1:]))
        with urlopen(self.base + "/v1/report?module=all&queue=closed&format=csv", timeout=4) as response:
            rows = list(csv.DictReader(io.StringIO(response.read().decode("utf-8-sig"))))
        self.assertEqual(next(row for row in rows if row["modul"] == "M3")["dataDecyzji"], "")
        _, supplement = self.request("GET", "/v1/report?module=all&queue=supplement")
        self.assertEqual((supplement["items"][0]["modul"], supplement["items"][0]["etap"]), ("M1", "supplement"))
        self.assertEqual(self.request("GET", "/v1/report?module=all")[0], 422)


if __name__ == "__main__":
    unittest.main()
