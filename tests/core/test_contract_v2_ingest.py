"""Contract v2 ingest rules (T1-T5, T17). Step S2: normalization, completeness, version reason, multi-path merge, reach series (all green).
"""
import unittest

from api import store
from collectors.discovery import merge_capture, merge_captures
from v2_helpers import StateCase, VIDEO, capture, finding


def path(method, **extra):
    return {"method": method, "adapter": method.split("_")[0], "queryKind": None, "query": None, "position": None,
            "page": None, "sourceId": "youtube", "observedAt": "2026-11-21T10:00:00+00:00",
            "responseSha256": "0" * 64, **extra}


def reach(views, observed="2026-11-21T10:00:00+00:00", state="observed"):
    return {"asOf": observed, "source": "data_api", "primary": "viewCount",
            "metrics": {"viewCount": {"value": views, "state": state, "observedAt": observed, "source": "data_api"}}}


class RepeatedScan(StateCase):
    def test_t1_same_content_twice_creates_nothing(self):
        cap = capture()
        self.assertEqual(self.put(cap)["changedFindings"], 1)
        before = (self.versions(), len(self.events()), self.case()["revision"])
        self.assertEqual(self.put(cap)["changedFindings"], 0)
        self.assertEqual((self.versions(), len(self.events()), self.case()["revision"]), before)

    def test_t1_discovery_seen_count_grows(self):
        cap = capture(discovery=[path("atom")])
        self.put(cap)
        self.put(cap)
        entry, = self.case()["discovery"]
        self.assertEqual(entry["seenCount"], 2)


class MultiplePaths(StateCase):
    def test_t2_atom_and_api_are_one_material_with_two_paths(self):
        # Both arrival orders; a different video id per order keeps them in one database.
        for key, atom_first in (("youtube:AAAAAAAAAAA", True), ("youtube:CCCCCCCCCCC", False)):
            atom = capture(key, discovery=[path("atom")], provenance={"sourceUrl": "atom", "mode": "live"})
            api = capture(key, discovery=[path("data_api_search", query="XTB", queryKind="brand", position=3, page=1)],
                          provenance={"sourceUrl": "api", "mode": "live"}, observedAt="2026-11-21T11:00:00+00:00")
            for cap in ((atom, api) if atom_first else (api, atom)):
                self.put(cap)
            found = self.case(key)
            self.assertEqual(sorted(d["method"] for d in found["discovery"]), ["atom", "data_api_search"], key)
            self.assertEqual(self.versions(key), 1)
            self.assertEqual(len(found["provenance"].get("paths", [])), 2)


class ReachIsNotContent(StateCase):
    def test_t3_statistics_only_change_keeps_version_and_revision(self):
        self.put(capture(reach=reach(10)))
        self.put(capture(reach=reach(999, "2026-11-21T12:00:00+00:00"), observedAt="2026-11-21T12:00:00+00:00"))
        found = self.case()
        self.assertEqual((found["version"], found["revision"]), (1, 1))
        self.assertEqual(found["reach"]["metrics"]["viewCount"]["value"], 999)

    def test_t3_zero_hidden_and_not_collected_are_different(self):
        # Later readings of unchanged content must update the state of the metric, not just its number.
        self.put(capture(reach=reach(5)))
        for index, (views, state) in enumerate(((0, "observed"), (None, "hidden"), (None, "not_collected"))):
            when = f"2026-11-21T1{index + 1}:00:00+00:00"
            self.put(capture(reach=reach(views, when, state), observedAt=when))
            metric = self.case()["reach"]["metrics"]["viewCount"]
            self.assertEqual((metric["value"], metric["state"]), (views, state))
        self.assertEqual(self.case()["version"], 1)

    def test_t3_current_behaviour_does_not_version_on_statistics(self):
        self.put(capture(reach=reach(10)))
        self.assertEqual(self.put(capture(reach=reach(999)))["changedFindings"], 0)
        self.assertEqual(self.versions(), 1)


class EditedContent(StateCase):
    def test_t4_description_edit_is_a_new_version_and_keeps_decision(self):
        self.put(capture())
        with store.connection(True) as db:
            db.execute("UPDATE cases SET status='closed' WHERE id=?", (VIDEO,))
        self.put(capture(description="Opis po edycji."))
        found = self.case()
        self.assertEqual((found["version"], found["revision"], found["status"]), (2, 2, "closed"))

    def test_t4_version_reason_and_observation_layer_survive(self):
        self.put(capture(discovery=[path("atom")], reach=reach(10)))
        self.put(capture(description="Opis po edycji.", discovery=[path("atom")], reach=reach(11, "2026-11-21T11:00:00+00:00")))
        found = self.case()
        self.assertEqual(found["versions"][-1]["changeKind"], "content")
        self.assertEqual(len(found["discovery"]), 1)
        self.assertEqual(found["reach"]["metrics"]["viewCount"]["value"], 11)


class NoFalseVersions(StateCase):
    def test_t5_same_instant_in_other_notation(self):
        self.put(capture(publishedAt="2026-11-01T10:00:00+00:00"))
        self.assertEqual(self.put(capture(publishedAt="2026-11-01T10:00:00Z"))["changedFindings"], 0)
        self.assertEqual(self.versions(), 1)

    def test_t5_partial_description_after_full_creates_no_version(self):
        full = capture(description="Pełny opis filmu z linkiem.", contentCompleteness="full")
        partial = capture(description="Pełny opis filmu z...", contentCompleteness="partial",
                          discovery=[path("data_api_search")])
        self.put(full)
        self.assertEqual(self.put(partial)["changedFindings"], 0)
        self.assertEqual(self.put(full)["changedFindings"], 0)
        self.assertEqual(self.versions(), 1)
        self.assertEqual(self.case()["discovery"][0]["method"], "data_api_search")

    def test_t5_full_description_replaces_a_partial_first_version(self):
        self.put(capture(description="Pełny opis...", contentCompleteness="partial"))
        self.assertEqual(self.put(capture(description="Pełny opis filmu.", contentCompleteness="full"))["changedFindings"], 1)
        self.assertEqual(self.case()["versions"][-1]["changeKind"], "content")


class ModesDoNotOverwriteLive(StateCase):
    def test_t17_replay_after_live_keeps_live_case(self):
        self.put(capture(description="Opis z żywego odczytu."), mode="live")
        self.put(capture(description="Opis z archiwum.", observedAt="2026-11-20T10:00:00+00:00"), mode="replay")
        found = self.case()
        self.assertEqual((found["description"], found["mode"], found["version"]), ("Opis z żywego odczytu.", "live", 1))

    def test_t17_replay_does_not_overwrite_live_reach(self):
        self.put(capture(reach=reach(500, "2026-11-21T12:00:00+00:00")), mode="live")
        self.put(capture(reach=reach(5, "2026-11-20T12:00:00+00:00")), mode="replay")
        self.assertEqual(self.case()["reach"]["metrics"]["viewCount"]["value"], 500)

    def test_t17_replay_adds_no_path_to_a_live_case(self):
        # Green today because the first capture is stored verbatim; guards the S2 merge.
        self.put(capture(discovery=[path("atom")]), mode="live")
        self.put(capture(discovery=[path("fixture")]), mode="replay")
        self.assertEqual([d["method"] for d in self.case()["discovery"]], ["atom"])


class VersionReasons(StateCase):
    def kinds(self):
        return [v["changeKind"] for v in self.case()["versions"]]

    def test_content_evidence_and_analysis_levels(self):
        self.put(capture())
        self.put(capture(description="Nowy opis."))
        self.put(capture(description="Nowy opis.", segments=[{"start": 1, "end": 2, "text": "Partnerem jest XTB."}]))
        self.put(capture(description="Nowy opis.", segments=[{"start": 1, "end": 2, "text": "Partnerem jest XTB."}]),
                 score=50, rulesVersion="investwatch-rules-pl-1.3")
        self.assertEqual(self.kinds(), ["content", "content", "evidence", "analysis"])
        details = self.case()["versions"][-1]["details"]
        self.assertEqual((details["rulesFrom"], details["rulesTo"], details["scoreFrom"], details["scoreTo"]),
                         ("investwatch-rules-pl-1.2", "investwatch-rules-pl-1.3", 30, 50))
        self.assertEqual([h.get("changeKind") for h in self.case()["history"]], self.kinds())

    def test_versions_stored_before_s2_are_classified_from_their_rows(self):
        self.put(capture())
        self.put(capture(description="Nowy opis."))
        with store.connection(True) as db:
            db.execute("DELETE FROM version_meta")
        self.assertEqual(self.kinds(), ["content", "content"])

    def test_youtube_link_notation_is_not_a_change(self):
        self.put(capture(url="https://youtu.be/AAAAAAAAAAA?si=abc"))
        self.assertEqual(self.put(capture(url="https://m.youtube.com/watch?v=AAAAAAAAAAA&t=5s"))["changedFindings"], 0)
        self.assertEqual(self.case()["url"], "https://www.youtube.com/watch?v=AAAAAAAAAAA")

    def test_line_endings_and_unicode_form_are_not_a_change(self):
        self.put(capture(description="Linia jeden.\nLinia dwa. Za\u017c\u00f3\u0142\u0107"))
        self.assertEqual(self.put(capture(description="Linia jeden.\r\nLinia dwa. Zaz\u0307o\u0301\u0142c\u0301"))["changedFindings"], 0)

    def test_later_source_keeps_the_provenance_that_defined_the_content(self):
        self.put(capture(provenance={"sourceUrl": "atom", "mode": "live"}, discovery=[path("atom")]))
        self.put(capture(provenance={"sourceUrl": "api", "mode": "live"}, observedAt="2026-11-21T11:00:00+00:00",
                         discovery=[path("data_api_search", query="XTB")]))
        found = self.case()
        self.assertEqual(found["provenance"]["sourceUrl"], "atom")
        self.assertEqual(found["observedAt"], "2026-11-21T11:00:00+00:00")
        self.assertEqual([p["method"] for p in found["provenance"]["paths"]], ["atom", "data_api_search"])

    def test_scan_id_is_recorded_on_the_path(self):
        cap = capture(discovery=[path("atom")])
        with store.connection(True) as db:
            store.apply_scan(db, [(cap, finding(cap))], [], [], "live", scan_id="scan-1")
        self.assertEqual(self.case()["discovery"][0]["scanId"], "scan-1")


class ReachSeries(StateCase):
    def test_series_keeps_every_reading_and_latest_wins_per_metric(self):
        self.put(capture(reach={**reach(10, "2026-11-21T10:00:00+00:00"),
                                "metrics": {"viewCount": reach(10)["metrics"]["viewCount"],
                                            "likeCount": {"value": 2, "state": "observed", "observedAt": "2026-11-21T10:00:00+00:00", "source": "atom"}}}))
        self.put(capture(reach=reach(99, "2026-11-21T12:00:00+00:00")))
        found = self.case()
        self.assertEqual(found["reach"]["metrics"]["viewCount"]["value"], 99)
        self.assertEqual(found["reach"]["metrics"]["likeCount"]["value"], 2)
        with store.connection() as db:
            self.assertEqual(len(store.reach_series(db, VIDEO)), 2)

    def test_older_reading_arriving_late_does_not_replace_the_newer(self):
        self.put(capture(reach=reach(99, "2026-11-21T12:00:00+00:00")))
        self.put(capture(reach=reach(10, "2026-11-21T09:00:00+00:00")))
        self.assertEqual(self.case()["reach"]["metrics"]["viewCount"]["value"], 99)


class MergeCaptures(unittest.TestCase):
    ATOM = capture(discovery=[path("atom")], reach=reach(10), contentCompleteness="full")
    API = capture(discovery=[path("data_api_search", query="XTB", position=3)], reach=reach(99, "2026-11-21T12:00:00+00:00"),
                  observedAt="2026-11-21T12:00:00+00:00", youtube={"channelId": "UCx", "durationSec": 600})
    SEARCH = capture(description="Skrócony opis...", contentCompleteness="partial", observedAt="2026-11-21T13:00:00+00:00",
                     discovery=[path("data_api_search", query="ETF")])

    def test_order_does_not_matter(self):
        one, = merge_captures([self.ATOM, self.API, self.SEARCH])
        for order in ([self.SEARCH, self.API, self.ATOM], [self.API, self.SEARCH, self.ATOM], [self.ATOM, self.SEARCH, self.API]):
            self.assertEqual(merge_captures(order), [one])

    def test_one_record_all_paths_newest_statistic_fuller_content(self):
        one, = merge_captures([self.ATOM, self.API, self.SEARCH])
        self.assertEqual(sorted(d["query"] or "-" for d in one["discovery"]), ["-", "ETF", "XTB"])
        self.assertEqual(one["reach"]["metrics"]["viewCount"]["value"], 99)
        self.assertEqual(one["description"], "Opis filmu.")        # the partial reading never wins
        self.assertEqual(one["youtube"]["durationSec"], 600)        # fields only one source knows are kept

    def test_distinct_ids_stay_distinct_and_plain_captures_pass_through(self):
        other = capture("youtube:BBBBBBBBBBB")
        merged = {c["id"]: c for c in merge_captures([self.ATOM, other])}
        self.assertEqual(set(merged), {VIDEO, "youtube:BBBBBBBBBBB"})
        self.assertNotIn("discovery", merged["youtube:BBBBBBBBBBB"])


if __name__ == "__main__":
    unittest.main()
