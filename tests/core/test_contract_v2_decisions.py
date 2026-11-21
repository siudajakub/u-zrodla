"""Contract v2 decisions (T6, T7, T27): revisions, parallel writers, stale review flags."""
import threading
import unittest

from fastapi import HTTPException

from api import server
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
        self.assertEqual(body["current"], {"revision": 2, "status": "reviewing", "version": 1})


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


if __name__ == "__main__":
    unittest.main()
