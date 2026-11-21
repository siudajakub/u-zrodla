"""M1 qualification: plan cases (projekt D §5, decyzje J) and real public inputs."""
import json
import re
from pathlib import Path
import unittest
import unittest.mock

from analysis import firm_index
from analysis.qualification import RULES_VERSION, coverage, priority, qualify

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "fixtures/raw/review-compare/qualification-inputs.json"
DISCOVERY = ROOT / "fixtures/raw/discovery/2026-11-21.json"
URL = "https://www.youtube.com/watch?v=EXAMPLE"
FULL_TRANSCRIPT = {"transcript": {"state": "full", "source": "asr", "windows": [{"start": 0, "end": 900}], "durationSec": 900}}


def cap(description="", segments=None, full_transcript=False, **extra):
    capture = {"id": "youtube:EXAMPLE", "module": "M1", "creatorId": "youtube:UCexample", "title": "Materiał",
               "url": URL, "description": description}
    if segments is not None:
        capture["segments"] = segments
    if full_transcript:
        capture["mediaCoverage"] = FULL_TRANSCRIPT
    capture.update(extra)
    return capture


def real():
    return {item["label"]: item["capture"] for item in json.loads(INPUTS.read_text(encoding="utf-8"))["items"]}


class Invariants:
    def check(self, result, capture):
        """Every quote is verbatim in the input at its locator; every refer is justified."""
        description = capture.get("description") or ""
        texts = {i: s["text"] for i, s in enumerate(capture.get("segments") or [])}
        for item in result["evidence"]:
            if item["modality"] == "description":
                loc = item["locator"]
                self.assertEqual(description[loc["charStart"]:loc["charEnd"]], item["text"])
                self.assertEqual(loc["occurrences"], description.count(item["text"]))
            elif item["modality"] == "transcript":
                if item.get("joinedSegments"):  # sliding join of consecutive auto-caption segments
                    joined = " ".join(texts[i] for i in item["joinedSegments"])
                    self.assertEqual(item["joinedSegments"], list(range(item["joinedSegments"][0],
                                                                         item["joinedSegments"][-1] + 1)))
                    self.assertIn(item["text"], joined)
                else:
                    self.assertTrue(any(item["text"] in t for t in texts.values()))
        for premise in result["premises"]:
            self.assertTrue(premise["quote"])
            self.assertTrue(premise["basis"]["source"])
            self.assertTrue(premise["counterEvidence"]["possibleExplanations"])
            self.assertEqual(premise["legalStatus"], "review_premise")
        decision = result["reviewDecision"]
        if decision["route"] == "refer":
            self.assertTrue(3 <= len(decision["reasons"]) <= 5, decision["reasons"])
            self.assertGreaterEqual(len(decision["moments"]), 1)
            self.assertTrue(decision["requirement"] and decision["claim"])
            self.assertGreaterEqual(result["reviewScore"]["value"], 60)
        self.assertIsNone(decision["queueEligible"])  # threshold is applied by the API
        self.assertNotIn("narusz", json.dumps(result, ensure_ascii=False).lower())
        self.assertEqual(result["rulesVersion"], RULES_VERSION)


class PlanCases(Invariants, unittest.TestCase):
    def run_case(self, capture):
        result = qualify(capture)
        self.check(result, capture)
        return result

    def test_01_02_real_short_xtb_declarations_go_to_register_and_complete(self):
        captures = [c for c in json.loads(DISCOVERY.read_text())["captures"] if c["description"] == "Partnerem odcinka jest XTB"]
        self.assertEqual(len(captures), 2)
        for capture in captures:
            result = self.run_case(capture)
            self.assertEqual(result["adRelationship"]["status"], "declared")
            self.assertEqual({c["registryId"] for c in result["adRelationship"]["firm"]["candidates"]}, {6884980, 9439233})
            self.assertEqual(result["adRelationship"]["firm"]["identityStatus"], "candidates")
            self.assertEqual(result["adRegistry"]["state"], "included")
            self.assertEqual(result["reviewDecision"]["route"], "complete")
            self.assertEqual(result["reviewDecision"]["completeReason"], "transcript_unavailable")
            self.assertEqual(result["reviewScore"]["state"], "withheld")
            self.assertEqual(result["premises"], [])
            self.assertEqual(result["coverage"]["modalities"]["description"]["state"], "fragment")
            self.assertEqual(result["coverage"]["state"], "minimal")
            self.assertTrue(result["coverage"]["blocksConclusion"])

    def test_03_declared_promotion_without_problem_after_transcript_is_register_only(self):
        result = self.run_case(cap("Partnerem odcinka jest XTB.", [{"start": 1, "end": 4, "text": "Dziś o rynku surowców."}], True))
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        self.assertEqual(result["reviewScore"]["value"], 0)
        self.assertEqual(result["adRegistry"]["state"], "included")
        self.assertEqual(result["coverage"]["state"], "full")

    def test_04_06_profit_claim_without_warning_in_full_transcript_is_referred_without_frames(self):
        segments = [{"start": 312.4, "end": 316.9, "text": "Na ETF-ach w XTB zrobicie spokojnie 20% rocznie", "confidence": 0.9}]
        result = self.run_case(cap("Partnerem odcinka jest XTB.", segments, True))
        decision = result["reviewDecision"]
        self.assertEqual(decision["route"], "refer")
        self.assertEqual(decision["requirement"]["id"], "U4")
        moment = next(m for m in decision["moments"] if m["start"] is not None)
        self.assertEqual(moment["start"], 312.4)
        self.assertTrue(moment["deepLink"].endswith("&t=312s"))
        self.assertEqual(result["coverage"]["modalities"]["frames"]["state"], "not_collected")
        self.assertIn("kadry z momentów dowodu (opcjonalnie)", decision["missing"])

    def test_05_warning_within_window_refutes_profit_claim(self):
        segments = [{"start": 312.4, "end": 316.9, "text": "Na ETF-ach w XTB zrobicie spokojnie 20% rocznie"},
                    {"start": 332.0, "end": 336.0, "text": "Pamiętajcie, inwestowanie wiąże się z ryzykiem utraty środków."}]
        result = self.run_case(cap("Partnerem odcinka jest XTB.", segments, True))
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        self.assertEqual(next(p for p in result["premises"] if p["type"] == "U4")["status"], "refuted")
        self.assertTrue(any(c["counterKind"] == "risk_warning" for c in result["counterEvidence"]))

    def test_07_education_with_broker_name_is_not_flagged(self):
        result = self.run_case(cap("Na przykładzie XTB pokazuję, czym jest zlecenie limit."))
        self.assertEqual(result["adRelationship"]["status"], "none")
        self.assertEqual(result["adRegistry"]["state"], "none")
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")

    def test_08_opinion_without_relation_stays_outside_m1(self):
        result = self.run_case(cap("Zarobiłem 30% na akcjach w XTB."))
        premise = next(p for p in result["premises"] if p["type"] == "U4")
        self.assertEqual(premise["status"], "out_of_scope_m1")
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        self.assertEqual(result["adRegistry"]["state"], "none")

    def test_09_guarantee_without_transcript_waits_for_transcript(self):
        result = self.run_case(cap("Partnerem odcinka jest XTB.\nZ XTB masz pewny zysk na ETF."))
        premise = next(p for p in result["premises"] if p["type"] == "U5")
        self.assertEqual(premise["status"], "conditional")
        self.assertEqual(result["reviewDecision"]["route"], "complete")
        self.assertLessEqual(result["reviewScore"]["value"], 55)

    def test_10_reach_never_changes_the_result_only_priority(self):
        base = cap("Partnerem odcinka jest XTB.", [{"start": 5, "end": 9, "text": "Na ETF-ach w XTB zrobicie 20% rocznie"}], True)
        big = qualify({**base, "reach": {"metrics": {"viewCount": {"value": 2_000_000, "state": "observed"}}}})
        small = qualify({**base, "reach": {"metrics": {"viewCount": {"value": 120, "state": "observed"}}}})
        self.assertEqual(big, small)
        self.assertGreater(priority({"metrics": {"viewCount": {"value": 2_000_000}}})["review"]["rank"],
                           priority({"metrics": {"viewCount": {"value": 120}}})["review"]["rank"])
        self.assertFalse(priority(None)["affectsDecision"])

    def test_11_repeated_quote_is_located_and_counted(self):
        text = real()["XTB DETERMINACJA, pełny opis (podgląd)"]["description"]
        undisclosed = text.replace("#xtb #współpraca\n", "").replace("📢Partnerem odcinka jest XTB", "")
        result = self.run_case(cap(undisclosed))
        self.assertEqual(result["reviewDecision"]["route"], "refer")
        code = next(e for e in result["evidence"] if "kod DETERMINACJA" in e["text"])
        self.assertEqual(code["locator"]["occurrences"], 2)

    def test_12_cross_border_firm_promoted_in_polish(self):
        result = self.run_case(cap("Partnerem odcinka jest eToro. Inwestuj w akcje z eToro."))
        firm = result["adRelationship"]["firm"]
        self.assertEqual([c["registryId"] for c in firm["candidates"]], [9651212])
        self.assertIs(firm["crossBorder"], True)
        self.assertEqual(result["adRegistry"]["state"], "included")
        self.assertEqual(result["adRelationship"]["language"]["value"], "pl")

    def test_13_unknown_broker_without_register_entry_is_completed_not_referred(self):
        # An undisclosed relation (link without a disclosure) to a firm missing from the copies waits for the identity.
        result = self.run_case(cap("Otwórz konto w Saxo: https://www.home.saxo/pl-pl/open-account?cid=1234\nInwestuj w akcje."))
        premise = next(p for p in result["premises"] if p["type"] == "U3")
        self.assertEqual(premise["status"], "conditional")
        self.assertEqual(result["reviewDecision"]["route"], "complete")
        self.assertEqual(result["reviewDecision"]["completeReason"], "identity_unresolved")

    def test_13b_disclosed_cooperation_with_unresolved_identity_goes_to_the_register_not_to_incomplete(self):
        result = self.run_case(cap("Partnerem odcinka jest broker FikcyjnyTrade. Inwestuj w akcje.",
                                   [{"start": 0, "end": 5, "text": "Dzień dobry, o rynku ropy."}], True))
        self.assertFalse(any(p["type"] == "U3" for p in result["premises"]))
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        registry = result["adRegistry"]
        self.assertEqual((registry["state"], registry["identityStatus"]), ("included", "no_registry_entry"))
        self.assertIn("kopie z 21.11.2026", registry["identityNote"])
        self.assertIn("domy maklerskie", registry["identityNote"])
        self.assertEqual(result["adRelationship"]["firm"]["entityType"], "unresolved")

    def test_14_tracking_link_and_code_without_disclosure_full_transcript(self):
        description = "💰 Sprawdź XTB\n👉 https://link-pso.xtb.com/pso/ABC12\nKod „KANAL” przy rejestracji = darmowy kurs."
        result = self.run_case(cap(description, [{"start": 0, "end": 5, "text": "Dzień dobry, o rynku ropy."}], True))
        premise = next(p for p in result["premises"] if p["type"] == "U1")
        self.assertEqual(premise["status"], "documented")
        self.assertEqual(result["reviewDecision"]["route"], "refer")
        self.assertGreaterEqual(result["reviewScore"]["value"], 90)
        self.assertEqual(result["adRelationship"]["status"], "probable")  # contract R3: link/code alone
        self.assertEqual(result["adRegistry"]["state"], "candidate")

    def test_15_call_to_action_alone_is_a_register_candidate(self):
        result = self.run_case(cap("Otwórz rachunek w XTB."))
        self.assertEqual(result["adRelationship"]["status"], "probable")
        self.assertEqual(result["adRegistry"]["state"], "candidate")
        self.assertFalse(any(p["type"] == "U1" for p in result["premises"]))
        self.assertEqual(result["reviewDecision"]["route"], "complete")

    def test_16_compensation_statement_is_documented_relation(self):
        result = self.run_case(cap("Przelew od domu maklerskiego dostaję za każdy nowy rachunek otwarty przez mój formularz."))
        self.assertEqual(result["adRelationship"]["status"], "documented")
        self.assertEqual(result["adRelationship"]["firm"]["identityStatus"], "unresolved")
        self.assertEqual(result["reviewDecision"]["route"], "refer")
        self.assertIn("nieustalona", " ".join(result["reviewDecision"]["reasons"]))

    def test_17_neutral_supervision_statement_is_not_u6(self):
        result = self.run_case(cap("Partnerem odcinka jest XTB. XTB jest nadzorowany przez KNF.", [], True))
        self.assertFalse(any(p["type"] == "U6" for p in result["premises"]))
        positive = self.run_case(cap("Partnerem odcinka jest XTB.\nXTB jest bezpieczne, bo nadzoruje je KNF.",
                                     [{"start": 1, "end": 3, "text": "Witajcie."}], True))
        self.assertEqual(next(p for p in positive["premises"] if p["type"] == "U6")["status"], "documented")

    def test_18_denial_criticism_and_fraud_warning_are_not_relations(self):
        for text, kind in (("Odcinek nie powstał we współpracy z XTB.", "denial"),
                           ("Ktoś podszywa się pod XTB i mówi: otwórz rachunek. Uważaj na oszustwo.", "fraud_warning"),
                           ("Porównuję XTB z konkurencją i krytykuję czas realizacji.", None)):
            with self.subTest(text=text):
                result = self.run_case(cap(text))
                self.assertIn(result["adRelationship"]["status"], ("none",))
                self.assertEqual(result["adRegistry"]["state"], "none")
                if kind:
                    self.assertTrue(any(c["counterKind"] == kind for c in result["counterEvidence"]))
        contrast = self.run_case(cap("Nie współpracuję z eToro, ale partnerem odcinka jest XTB."))
        self.assertEqual(contrast["adRelationship"]["firm"]["mention"], "XTB")
        self.assertEqual(contrast["adRelationship"]["status"], "declared")

    def test_19_empty_material_is_insufficient(self):
        result = qualify({"id": "x", "module": "M1", "title": "", "description": ""})
        self.assertEqual(result["reviewDecision"]["route"], "insufficient")
        self.assertEqual(result["reviewScore"]["state"], "withheld")
        self.assertEqual(result["coverage"]["state"], "none")

    def test_20_disclosure_in_speech_or_frame_refutes_u1(self):
        description = "👉 https://link-pso.xtb.com/pso/ABC12\nKod „KANAL” przy rejestracji w XTB = darmowy kurs."
        speech = self.run_case(cap(description, [{"start": 2, "end": 6, "text": "Ten odcinek powstał we współpracy z XTB."}], True))
        frame = self.run_case(cap(description, frames=[{"t": 30, "text": "#reklama XTB", "method": "ocr"}]))
        without = self.run_case(cap(description))
        for result in (speech, frame):
            self.assertEqual(next(p for p in result["premises"] if p["type"] == "U1")["status"], "refuted")
            self.assertEqual(result["reviewDecision"]["route"], "no_signal")
            self.assertEqual(result["adRegistry"]["state"], "included")
        self.assertEqual(speech["adRelationship"]["disclosure"]["state"], "in_speech")
        self.assertEqual(frame["adRelationship"]["disclosure"]["state"], "in_frame")
        self.assertEqual(without["reviewDecision"]["route"], "refer")
        self.assertIn("mowy nie zbadano", " ".join(without["reviewDecision"]["reasons"]))
        self.assertIn("transkrypcja mowy", without["reviewDecision"]["missing"])

    def test_disclosure_vocabulary(self):
        for text in ("[reklama_mBank] Link mBanku wstawiamy w ramach płatnej współpracy.",
                     "Partnerem publikacji jest mBank. #PłatnaWspółpraca",
                     "Konto w mBanku (link partnerski): https://example.org/x",
                     "Materiał powstał we współpracy z mBank.",
                     "Płatna współpraca z mBank."):
            with self.subTest(text=text):
                result = self.run_case(cap(text))
                self.assertEqual(result["adRelationship"]["status"], "declared")
                self.assertEqual(result["adRelationship"]["disclosure"]["state"], "in_description")
        contact = self.run_case(cap("👉 https://c.freedom24.com/?a=abc&ref1=1\n\n✉️ Współpraca: biuro@example.pl"))
        self.assertEqual(contact["adRelationship"]["disclosure"]["state"], "not_found_in_scope")
        self.assertEqual(contact["reviewDecision"]["route"], "refer")

    def test_coverage_never_claims_absence_in_whole_film(self):
        result = coverage(cap("Opis."))
        self.assertEqual(result["modalities"]["transcript"]["state"], "unavailable")
        self.assertIn("mowa (niezbadana)", result["label"])
        partial = coverage(cap("Opis.", [{"start": 0, "end": 45, "text": "Początek audycji."}]))
        self.assertEqual(partial["modalities"]["transcript"]["state"], "partial")

    def test_firm_index_is_current(self):
        self.assertEqual(firm_index.main(["--check"]), 0)


class EntityTypes(unittest.TestCase):
    """Temat 1 definitions applied to the register copies (T1-02, T1-03): type, home country, passporting."""

    def candidates(self, key):
        index = json.loads(firm_index.OUTPUT.read_text(encoding="utf-8"))
        return {c["name"]: c for f in index["firms"] if f["key"] == key for c in f["candidates"]}

    def test_every_candidate_is_typed_from_the_register_it_came_from(self):
        xtb = self.candidates("xtb")
        self.assertEqual((xtb["XTB S.A."]["entityType"], xtb["XTB S.A."]["homeCountry"], xtb["XTB S.A."]["passporting"]),
                         ("domestic_investment_firm", "Polska", None))
        self.assertEqual((xtb["XTB Ltd"]["entityType"], xtb["XTB Ltd"]["passporting"]), ("foreign_investment_firm", "cross_border"))
        mbank, = self.candidates("mbank").values()
        self.assertEqual((mbank["entityType"], mbank["homeCountry"]), ("domestic_bank", "Polska"))
        index = json.loads(firm_index.OUTPUT.read_text(encoding="utf-8"))
        for firm in index["firms"]:
            for c in firm["candidates"]:
                self.assertIn(c["entityType"], ("domestic_investment_firm", "domestic_bank", "foreign_investment_firm"), c["name"])
                self.assertTrue(c["homeCountry"], c["name"])

    def test_mixed_candidates_stay_unresolved_and_branch_is_distinguished(self):
        from analysis import qualification
        mixed = qualification._entity_view(list(self.candidates("xtb").values()))
        self.assertEqual((mixed["entityType"], mixed["passporting"]), ("unresolved", "unresolved"))
        self.assertEqual(mixed["entityTypes"], ["domestic_investment_firm", "foreign_investment_firm"])
        branch = {"name": "IG Europe GmbH", "entityType": "foreign_investment_firm", "homeCountry": "Niemcy", "passporting": "branch"}
        self.assertEqual(qualification._entity_view([branch])["passporting"], "branch")
        self.assertIn("działa przez oddział w Polsce", qualification._candidate_phrase(branch))

    def test_trading212_with_three_foreign_rows_is_a_candidate_set_not_a_guess(self):
        result = qualify(cap("Partnerem odcinka jest Trading 212. Inwestuj w akcje."))
        firm = result["adRelationship"]["firm"]
        self.assertEqual((firm["identityStatus"], len(firm["candidates"]), firm["entityType"]), ("candidates", 3, "foreign_investment_firm"))
        self.assertEqual(firm["homeCountry"], "unresolved")


class PolishText(unittest.TestCase):
    def test_quote_is_cut_at_a_sentence_or_word_not_on_a_dangling_letter(self):
        from analysis.qualification import _quote
        text = ("Dzisiaj opowiem wam o tym, jak działa platforma i dlaczego warto ją znać w pracy na kanale. "
                "W kolejnych odcinkach pokażę więcej, a także zaprezentuję rzeczy dodatkowe.")
        self.assertEqual(_quote(text), "„Dzisiaj opowiem wam o tym, jak działa platforma i dlaczego warto ją znać w pracy na kanale”")
        tail = _quote("a" * 5 + " " + " ".join(["słowo"] * 19) + " w kolejnym")
        self.assertTrue(tail.endswith("słowo…”"), tail)
        self.assertNotRegex(_quote("x " + "abc " * 28 + "W dalszej części"), r"\sW…”$")

    def test_innocent_explanation_matches_the_examined_scope(self):
        from analysis.qualification import _explanations, coverage
        full = coverage(cap("Opis.", [{"start": 0, "end": 5, "text": "Mowa."}], True))
        self.assertEqual(full["gaps"][0]["modality"], "frames")
        text = _explanations("U1", full)[0]
        self.assertNotIn("w miejscu, którego nie zbadano", text)
        self.assertIn("kadry", text)
        self.assertNotIn("mowa", text)
        none = coverage(cap("Opis."))
        self.assertIn("mowa", _explanations("U1", none)[0])


class RealMaterials(Invariants, unittest.TestCase):
    EXPECTED = {
        "XTB DETERMINACJA, krótki opis (fikstura)": ("complete", "declared", "included"),
        "XTB DETERMINACJA, pełny opis (podgląd)": ("complete", "declared", "included"),
        "Comparic Rynki / XTB (1)": ("refer", "probable", "candidate"),
        "Comparic Rynki / XTB (2)": ("refer", "probable", "candidate"),
        "Comparic Rynki / XTB (3)": ("refer", "probable", "candidate"),
        "FBO 347": ("complete", "declared", "included"),
        "FBO 348": ("no_signal", "declared", "none"),
        "FBO 349": ("complete", "declared", "included"),
        "Freedom24 (kanał UCgw_3Ep…)": ("refer", "probable", "candidate"),
        "Saxo Bank (kanał UCgw_3Ep…)": ("complete", "declared", "included"),
        "XTB (kanał UCgw_3Ep…, Cymcyk)": ("refer", "probable", "candidate"),
        "XTB (kanał UCgw_3Ep…, -HpCSKp9bqk)": ("refer", "probable", "candidate"),
        "Freedom24 (kanał UCgw_3Ep…, 9Fcwo1jlwe4)": ("refer", "probable", "candidate"),
    }

    def test_real_inputs(self):
        materials = real()
        self.assertEqual(set(materials), set(self.EXPECTED))
        for label, capture in materials.items():
            with self.subTest(label=label):
                result = qualify(capture)
                self.check(result, capture)
                route, status, registry = self.EXPECTED[label]
                self.assertEqual((result["reviewDecision"]["route"], result["adRelationship"]["status"], result["adRegistry"]["state"]),
                                 (route, status, registry))

    def test_real_details(self):
        materials = real()
        full = qualify(materials["XTB DETERMINACJA, pełny opis (podgląd)"])
        self.assertEqual([c["registryId"] for c in full["adRelationship"]["firm"]["candidates"]], [6884980])
        self.assertFalse(any(p["type"] == "U1" for p in full["premises"]))
        fbo348 = qualify(materials["FBO 348"])
        self.assertIn("spoza zakresu M1", fbo348["reviewDecision"]["reason"])
        fbo349 = qualify(materials["FBO 349"])
        self.assertIn("XTB", {r["firm"]["mention"] for r in fbo349["relationships"]} | {fbo349["adRelationship"]["firm"]["mention"]})
        saxo = qualify(materials["Saxo Bank (kanał UCgw_3Ep…)"])
        self.assertEqual(saxo["adRelationship"]["firm"]["identityStatus"], "no_registry_entry")
        self.assertFalse(any(p["type"] == "U4" and p["status"] not in ("out_of_scope_m1",) for p in saxo["premises"]))
        comparic = qualify(materials["Comparic Rynki / XTB (1)"])
        kinds = {e["kind"] for e in next(p for p in comparic["premises"] if p["type"] == "U1")["relationEvidence"]}
        self.assertEqual(kinds, {"tracking_link", "creator_code"})
        freedom = qualify(materials["Freedom24 (kanał UCgw_3Ep…)"])
        self.assertIs(freedom["adRelationship"]["firm"]["crossBorder"], True)


EXCERPTS = ROOT / "fixtures/raw/review-compare/media-excerpts.json"
CACHE = ROOT / ".runtime/media-cache"
MEDIA_LABELS = {
    "CDk20n4u9Kk": "Comparic Rynki / XTB (1)",
    "xtMqKkFO-0M": "XTB DETERMINACJA, pełny opis (podgląd)",
    "-HpCSKp9bqk": "XTB (kanał UCgw_3Ep…, -HpCSKp9bqk)",
    "9Fcwo1jlwe4": "Freedom24 (kanał UCgw_3Ep…, 9Fcwo1jlwe4)",
}


def with_media(capture, video, segments):
    return {**capture, "segments": segments, "mediaCoverage": video["mediaCoverage"], "frames": video["frames"],
            "mediaVersion": video["captionsSha256"]}


class RealMedia(Invariants, unittest.TestCase):
    """Agent C samples: description suggests no disclosure, speech and frame refute it."""

    def setUp(self):
        self.videos = json.loads(EXCERPTS.read_text(encoding="utf-8"))["videos"]
        self.materials = real()

    def assert_refuted(self, result, capture, disclosed_in_description=False):
        self.check(result, capture)
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        self.assertEqual(result["adRegistry"]["state"], "included")
        u1 = [p for p in result["premises"] if p["type"] == "U1"]
        if disclosed_in_description:
            self.assertEqual(u1, [])  # disclosed in the description: no premise at all
        else:
            self.assertEqual(u1[0]["status"], "refuted")
        self.assertEqual(result["coverage"]["state"], "full")
        self.assertEqual(result["coverage"]["modalities"]["frames"]["state"], "selected_moments")

    def test_description_only_refers_then_speech_and_frame_refute(self):
        for video_id, label in MEDIA_LABELS.items():
            with self.subTest(video=video_id):
                capture = self.materials[label]
                before = qualify(capture)
                self.check(before, capture)
                expected_before = "complete" if video_id == "xtMqKkFO-0M" else "refer"
                self.assertEqual(before["reviewDecision"]["route"], expected_before)
                if expected_before == "refer":
                    self.assertIn("mowy nie zbadano", " ".join(before["reviewDecision"]["reasons"]))
                video = self.videos[video_id]
                enriched = with_media(capture, video, video["segments"])
                self.assert_refuted(qualify(enriched), enriched, video_id == "xtMqKkFO-0M")

    def test_comparic_speech_and_frame_details(self):
        video = self.videos["CDk20n4u9Kk"]
        capture = with_media(self.materials[MEDIA_LABELS["CDk20n4u9Kk"]], video, video["segments"])
        result = qualify(capture)
        self.assertEqual(result["adRelationship"]["disclosure"]["state"], "in_speech")
        found = next(p for p in result["premises"] if p["type"] == "U1")["counterEvidence"]["found"]
        self.assertIn("znajdziecie u partnera tego odcinka XTB.", found)
        self.assertIn("REKLAMA", found)
        frame = next(e for e in result["evidence"] if e["modality"] == "frame")
        self.assertEqual(frame["match"], "approximate")
        self.assertTrue(frame["sourceUrlAtTime"].endswith("&t=614s"))
        spoken = next(e for e in result["evidence"] if e["modality"] == "transcript" and "partnera" in e["text"])
        self.assertTrue(spoken["sourceUrlAtTime"].endswith("&t=614s"))
        self.assertIn("auto-napisy", spoken["caveat"])
        codes = next(p for p in result["premises"] if p["type"] == "U1")["relationEvidence"]
        self.assertTrue(any(c["kind"] == "creator_code" and "≈" in c.get("detail", "") for c in codes), codes)

    def test_frame_without_quoted_text_is_examined_but_not_a_disclosure(self):
        frame = {"time": 95.0, "observation": "Studio z logo XTB; brak etykiety reklamy ani tekstu współpracy w kadrze."}
        description = "👉 https://link-pso.xtb.com/pso/ABC12\nKod „KANAL” przy rejestracji w XTB."
        result = qualify(cap(description, frames=[frame]))
        self.assertEqual(result["coverage"]["modalities"]["frames"]["state"], "selected_moments")
        self.assertEqual(result["reviewDecision"]["route"], "refer")

    @unittest.skipUnless(all((CACHE / v / "transcript.json").is_file() for v in MEDIA_LABELS), "brak pełnych transkryptów w .runtime/media-cache")
    def test_full_cached_transcripts(self):
        for video_id, label in MEDIA_LABELS.items():
            with self.subTest(video=video_id):
                transcript = json.loads((CACHE / video_id / "transcript.json").read_text(encoding="utf-8"))
                self.assertEqual(transcript["captionsSha256"], self.videos[video_id]["captionsSha256"])
                capture = with_media(self.materials[label], self.videos[video_id], transcript["segments"])
                self.assert_refuted(qualify(capture), capture, video_id == "xtMqKkFO-0M")


REPLAY_B = ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz"
MEDIA_C = ROOT / "fixtures/raw/media/2026-11-21"


def replay_b():
    import gzip
    with gzip.open(REPLAY_B, "rt", encoding="utf-8") as stream:
        return {c["id"]: c for c in json.load(stream)["captures"]}


class PlatformFlag(Invariants, unittest.TestCase):
    """Agent B Data API records: paidPromotionFlag=true is a platform-level disclosure."""

    @classmethod
    def setUpClass(cls):
        cls.captures = replay_b()

    def test_flag_true_refutes_u1_on_real_records(self):
        for vid in ("i3QxMqyRlks", "eQYmvRfHtr8", "ePfzHQVf-lc", "o2GfnmVVkO8"):
            with self.subTest(video=vid):
                capture = self.captures[f"youtube:{vid}"]
                self.assertIs(capture["youtube"]["paidPromotionFlag"], True)
                result = qualify(capture)
                self.check(result, capture)
                u1 = [p for p in result["premises"] if p["type"] == "U1"]
                # With a refuted U1 the route is no_signal; without commercial evidence (i3QxMqyRlks) speech
                # is still needed for U4-U6, so the description-only record waits (complete), never refer.
                self.assertEqual(result["reviewDecision"]["route"], "no_signal" if u1 else "complete")
                self.assertEqual(result["adRegistry"]["state"], "included")
                self.assertEqual(result["adRelationship"]["status"], "declared")
                self.assertIn("platform_flag", result["adRelationship"]["disclosure"]["kinds"])
                platform = [c for c in result["counterEvidence"] if c["modality"] == "platform"]
                self.assertEqual(len(platform), 1)
                self.assertIn("YouTube oznacza film jako płatną promocję (odczyt z 21.11.2026", platform[0]["text"])
                self.assertEqual(platform[0]["counterKind"], "disclosure_present")
                for premise in (p for p in result["premises"] if p["type"] == "U1"):
                    self.assertEqual(premise["status"], "refuted")

    def test_flag_false_or_missing_proves_nothing(self):
        for vid in ("7M0rC6-Rueo", "AqXHkxDzSDI"):
            with self.subTest(video=vid):
                capture = self.captures[f"youtube:{vid}"]
                self.assertIs(capture["youtube"]["paidPromotionFlag"], False)
                result = qualify(capture)
                self.check(result, capture)
                self.assertEqual(result["reviewDecision"]["route"], "refer")
                self.assertEqual(result["coverage"]["modalities"]["platformFlags"],
                                 {"state": "observed", "paidPromotion": False})
                unknown = {**capture, "youtube": {**capture["youtube"], "paidPromotionFlag": None}}
                again = qualify(unknown)
                self.assertEqual(again["reviewDecision"]["route"], "refer")
                self.assertEqual(again["coverage"]["modalities"]["platformFlags"]["state"], "unavailable")

    def test_no_flagged_record_with_firm_link_is_referred(self):
        flagged = [c for c in self.captures.values() if c.get("youtube", {}).get("paidPromotionFlag") is True]
        self.assertGreater(len(flagged), 100)
        referred = [c["id"] for c in flagged if qualify(c)["reviewDecision"]["route"] == "refer"]
        self.assertEqual(referred, [])


class SpokenDisclosureVocabulary(unittest.TestCase):
    """Verbatim description lines and auto-caption segments from agent C package 2."""

    XTB_LINK = "✅Konto maklerskie, które polecam (XTB): https://link-pso.xtb.com/pso/WtGV9"
    FULL = {"transcript": {"state": "full", "source": "auto_captions", "windows": [{"start": 0, "end": 900}],
                           "durationSec": 900}, "frames": {"state": "not_collected"}}

    def run_segments(self, description, texts, step=2.5):
        segments = [{"start": i * step, "end": i * step + step - 0.1, "text": t, "method": "auto_captions"}
                    for i, t in enumerate(texts)]
        capture = cap(description, segments, mediaCoverage=self.FULL)
        return qualify(capture), capture

    def test_partner_of_my_channel_refutes_u1_yIbtMnfP25Q(self):
        result, _ = self.run_segments(self.XTB_LINK, [
            "do tego celu używam i polecam konto XTB,", "które jest partnerem mojego kanału. W",
            "XTB założyłem swoje pierwsze konto"])
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        self.assertEqual(result["adRelationship"]["disclosure"]["kind"], "partner_mention")
        self.assertEqual(result["adRegistry"]["disclosureKind"], "partner_mention")

    def test_phrase_split_across_segments_o2GfnmVVkO8(self):
        description = "Inwestuj globalnie:\nhttps://c.freedom24.com/?a=t9fkwo&i=fvk7z5&ref1=2111"
        result, capture = self.run_segments(description, [
            "dostępem do rynków to sprawdzacie", "koniecznie Freedom partnera tego", "odcinka. Masa instrumentów tam jest"])
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        spoken = next(e for e in result["evidence"] if e["modality"] == "transcript" and e["role"] == "disclosure")
        self.assertEqual(spoken["text"], "koniecznie Freedom partnera tego odcinka. Masa instrumentów tam jest")
        self.assertEqual(spoken["joinedSegments"], [1, 2])
        Invariants.check(self, result, capture)

    def test_affiliate_link_mention_with_single_firm_O5YmmKadQQw(self):
        result, _ = self.run_segments("W tym odcinku robimy praktyczną część eToro krok po kroku!", [
            "Oczywiście jeżeli rejestrujcie się z", "linku partnerskiego to jak najbardziej",
            "was to uprawnia do bonusu. Dlatego"])
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        self.assertEqual(result["adRegistry"]["state"], "included")
        self.assertEqual(result["adRegistry"]["disclosureKind"], "affiliate_link_mention")
        self.assertEqual(result["adRelationship"]["firm"]["mention"], "eToro")

    def test_sponsored_by_is_explicit_ad(self):
        result, _ = self.run_segments(self.XTB_LINK, ["ten materiał jest sponsorowany przez XTB, polską aplikację"])
        self.assertEqual(result["adRelationship"]["disclosure"]["kind"], "explicit_ad")
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")

    def test_other_channel_partner_does_not_disclose_firm(self):
        # ePfzHQVf-lc: "partnerem technologicznym kanału jest Lantre" is about another sponsor.
        result, _ = self.run_segments(self.XTB_LINK, [
            "zarabiacie. Link w opisie. A partnerem", "technologicznym kanału jest z kolei", "Lantry, autoryzowany sprzedawca"])
        self.assertEqual(result["reviewDecision"]["route"], "refer")

    def test_short_link_and_code_next_to_firm_name_AqXHkxDzSDI(self):
        description = ('👇ZACZNIJ INWESTOWAĆ👇\n\n🥇XTB: https://bit.ly/44BfO3V (Użyj kodu "TRADEXTB", aby uzyskać '
                       'materiały edukacyjne)\n🥈XM: https://bit.ly/4l0vliM')
        result, capture = self.run_segments(description, [
            "24. A jeśli chcesz otworzyć konto,", "znajdziesz linki do specjalnych ofert w", "opisie poniżej. Zaczynajmy. XTB jest"])
        decision = result["reviewDecision"]
        self.assertEqual(decision["route"], "refer")
        kinds = {c["kind"] for c in next(p for p in result["premises"] if p["type"] == "U1")["relationEvidence"]}
        self.assertEqual(kinds, {"short_link", "creator_code"})
        self.assertTrue(all(m["start"] is not None or m.get("locator") for m in decision["moments"]))
        call = [m for m in decision["moments"] if m["kind"] == "time"]
        self.assertEqual(call[0]["label"], "Wezwanie w mowie do linku w opisie")
        self.assertIn("&t=2s", call[0]["deepLink"])
        self.assertIn("w całej transkrypcji (0:00–15:00)", " ".join(decision["reasons"]))
        Invariants.check(self, result, capture)

    def test_newsletter_short_link_without_firm_is_not_a_relation(self):
        result = qualify(cap("Link do zapisu na newsletter, poniżej :)\nhttps://rb.gy/sgrnw\nO inwestowaniu w XTB."))
        self.assertNotIn("U1", [p["type"] for p in result["premises"]])

    def test_contact_line_is_not_a_disclosure(self):
        result, _ = self.run_segments(self.XTB_LINK + "\n✉️ Współpraca: biuro@dnarynkow.pl", ["Dziś o rynku."])
        self.assertEqual(result["reviewDecision"]["route"], "refer")


EXPECTED_C2 = {
    "7M0rC6-Rueo": "refer", "OIyPE0z2mng": "refer", "ZJrT-X08Xwc": "refer", "AqXHkxDzSDI": "refer",
    "yIbtMnfP25Q": "no_signal", "O5YmmKadQQw": "no_signal", "eQYmvRfHtr8": "no_signal", "YQH4FEP9exI": "no_signal",
    "ePfzHQVf-lc": "no_signal", "o2GfnmVVkO8": "no_signal", "p_ui_fqLdV0": "no_signal", "i3QxMqyRlks": "no_signal",
    "_aqCM37gK1U": "no_signal",  # Saxo Bank: openly disclosed; identity not in the register copies, noted in the ad register
}


def media_capture(vid):
    """Description + full cached auto-captions + C frames + B platform flag, as for G."""
    video = json.loads((MEDIA_C / f"{vid}.json").read_text(encoding="utf-8"))
    meta = json.loads((CACHE / vid / "meta.json").read_text(encoding="utf-8"))
    transcript = json.loads((CACHE / vid / "transcript.json").read_text(encoding="utf-8"))
    return {"id": f"youtube:{vid}", "module": "M1", "url": f"https://www.youtube.com/watch?v={vid}",
            "title": meta.get("title"), "description": meta.get("description") or "", "observedAt": video.get("observedAt"),
            "segments": [{k: s[k] for k in ("start", "end", "text", "method", "windowId") if k in s} for s in transcript["segments"]],
            "mediaCoverage": video["mediaCoverage"], "frames": video.get("frames") or [],
            "mediaVersion": transcript.get("captionsSha256"),
            "youtube": {"videoId": vid, "paidPromotionFlag": video.get("paidPromotionFlagApi"),
                        "observedAt": video.get("observedAt")}}


@unittest.skipUnless(all((CACHE / v / "transcript.json").is_file() and (CACHE / v / "meta.json").is_file()
                         for v in EXPECTED_C2), "brak transkryptów i opisów pakietu C2 w .runtime/media-cache")
class MediaPackage2(Invariants, unittest.TestCase):
    def test_final_routes_description_speech_frames(self):
        for vid, route in EXPECTED_C2.items():
            with self.subTest(video=vid):
                capture = media_capture(vid)
                result = qualify(capture)
                self.check(result, capture)
                self.assertEqual(result["reviewDecision"]["route"], route)
                if route == "no_signal":
                    self.assertEqual(result["adRegistry"]["state"], "included")
                if vid == "_aqCM37gK1U":
                    self.assertEqual(result["adRelationship"]["disclosure"]["state"], "in_description")
                    self.assertNotEqual(result["reviewDecision"].get("completeReason"), "identity_unresolved")

    def entity(self, vid):
        result = qualify(media_capture(vid))
        return result, result["adRelationship"]["firm"]

    def test_saxo_bank_is_not_guessed_and_is_in_the_ad_register(self):
        result, firm = self.entity("_aqCM37gK1U")
        self.assertEqual((firm["identityStatus"], firm["candidates"], firm["entityType"]), ("no_registry_entry", [], "unresolved"))
        self.assertIn("kopie z 21.11.2026", firm["reason"])
        self.assertIn("notyfikacje zagranicznych firm inwestycyjnych", firm["entitySentence"])
        self.assertEqual(result["reviewDecision"]["route"], "no_signal")
        registry = result["adRegistry"]
        self.assertEqual((registry["state"], registry["identityStatus"]), ("included", "no_registry_entry"))
        self.assertIn("nie dowodzi", registry["identityNote"])
        self.assertFalse(any(p["type"] == "U3" for p in result["premises"]))

    def test_freedom24_and_etoro_are_foreign_firms_operating_cross_border(self):
        for vid, name, country in (("9Fcwo1jlwe4", "Freedom Finance Europe Ltd", "Cypr"), ("O5YmmKadQQw", "Etoro (Europe) Ltd", "Cypr")):
            with self.subTest(video=vid):
                result, firm = self.entity(vid)
                self.assertEqual([c["name"] for c in firm["candidates"]], [name])
                self.assertEqual((firm["entityType"], firm["homeCountry"], firm["passporting"], firm["crossBorder"]),
                                 ("foreign_investment_firm", country, "cross_border", True))
                self.assertIn("zagraniczna firma inwestycyjna", firm["entitySentence"])
                self.assertIn("transgranicznie", firm["entitySentence"])
                self.assertIn("kopia z 21.11.2026", firm["entitySentence"])
                self.assertEqual(result["adRegistry"]["entityType"], "foreign_investment_firm")
                self.assertEqual(result["adRegistry"]["state"], "included")

    def test_routes_do_not_depend_on_segment_boundaries(self):
        import analysis.qualification as q
        for size in (3, 5, 7):
            with self.subTest(window=size), unittest.mock.patch.object(q, "SPEECH_WINDOW", size):
                for vid, route in EXPECTED_C2.items():
                    capture = media_capture(vid)
                    capture["youtube"]["paidPromotionFlag"] = None  # speech alone must decide
                    self.assertEqual(qualify(capture)["reviewDecision"]["route"], route, vid)

    def test_spoken_disclosure_moments(self):
        result = qualify(media_capture("yIbtMnfP25Q"))
        spoken = result["adRelationship"]["disclosure"]
        self.assertEqual((spoken["state"], spoken["kind"]), ("in_speech", "partner_mention"))
        self.assertIn("partnerem mojego kanału", spoken["text"])
        result = qualify(media_capture("O5YmmKadQQw"))
        self.assertEqual(result["adRegistry"]["disclosureKind"], "affiliate_link_mention")


FORBIDDEN = [re.compile(p) for p in (r"znaki \d", r"_code", r"tracking_", r"\bU\d\b", r"\[\d", r"\bNone\b", r"\bnull\b",
                                      r"\b(?:true|false)\b", r"https?://", r"\bregistryId\b")]


def human_texts(result):
    """Every text meant for the analyst (verbatim quotes of the material are excluded)."""
    decision, relation, registry = result["reviewDecision"], result["adRelationship"], result["adRegistry"]
    texts = [decision["reason"], decision.get("alternative"), result["coverage"]["label"], result["reviewScore"]["meaning"],
             result["reviewScore"].get("notComputableReason"), relation.get("basis"), relation["disclosure"].get("summary"),
             registry.get("summary")] + decision["reasons"] + decision["missing"]
    texts += [m["label"] for m in decision["moments"]] + [g["reason"] for g in result["coverage"]["gaps"]]
    if decision.get("requirement"):
        texts += [decision["requirement"]["label"], decision["requirement"]["scope"]]
    for firm in [relation.get("firm")] + [r["firm"] for r in result.get("relationships", [])]:
        texts.append((firm or {}).get("reason"))
    for premise in result["premises"]:
        texts += [premise["claim"], premise["basis"]["transfer"], *premise["scope"]["requires"], *premise["counterEvidence"]["searched"],
                  *premise["counterEvidence"]["possibleExplanations"], *(c[0] for c in premise["strength"]["components"])]
    texts += [c["effect"] for c in result["counterEvidence"] if c.get("effect")]
    texts += [e["text"] for e in result["evidence"] if e["modality"] == "platform"]
    return [t for t in texts if t]


def field_names(value, found=None):
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            if re.fullmatch(r"[a-z]+[A-Z]\w*", key):
                found.add(key)
            field_names(item, found)
    elif isinstance(value, list):
        for item in value:
            field_names(item, found)
    return found


class HumanWording(unittest.TestCase):
    """No field name, enum code, position or null leaks into text for the analyst (all real records)."""

    def captures(self):
        yield from ((f"input:{label}", capture) for label, capture in real().items())
        for vid in EXPECTED_C2:
            if (CACHE / vid / "transcript.json").is_file() and (CACHE / vid / "meta.json").is_file():
                yield f"media:{vid}", media_capture(vid)

    def test_no_technical_wording_in_any_real_record(self):
        checked = 0
        for label, capture in self.captures():
            result = qualify(capture)
            camel = field_names(result) - {"adRelationship"} | {"completeReason", "reviewDecision", "evidenceId", "sourceUrlAtTime"}
            for text in human_texts(result):
                checked += 1
                with self.subTest(record=label, text=text[:80]):
                    for pattern in FORBIDDEN:
                        self.assertIsNone(pattern.search(text), pattern.pattern)
                    for name in camel:
                        self.assertNotIn(name, text)
        self.assertGreater(checked, 150)

    def test_reasons_use_clock_format_and_answer_the_analyst(self):
        capture = media_capture("AqXHkxDzSDI") if (CACHE / "AqXHkxDzSDI" / "meta.json").is_file() else None
        self.assertIsNotNone(capture, "brak pakietu C2 w .runtime/media-cache")
        capture["youtube"]["paidPromotionFlag"] = False
        reasons = qualify(capture)["reviewDecision"]["reasons"]
        self.assertTrue(3 <= len(reasons) <= 5)
        joined = " ".join(reasons)
        self.assertRegex(joined, r"\(0:00–\d+:\d{2}\)")
        self.assertIn("YouTube nie oznacza filmu jako płatnej promocji", joined)
        self.assertIn("Możliwe niewinne wyjaśnienie", joined)
        self.assertNotIn("naruszeni", joined.lower())


class LanguageScope(unittest.TestCase):
    """Owner decision of 21 XI: only Polish material is in scope. Records taken from the live trial (s4-live)."""
    XTB_IT = ("▶️contatto: becurious.business@gmail.com \n\nServizi che uso e consiglio\nBroker\n✅XTB: https://link-pso.xtb.com/pso/kuTy7\n\n"
              "La Norvegia è uno dei Paesi più ricchi al mondo e possiede il fondo sovrano più grande della storia.")
    ETORO_PL = ("► Link do eToro z 100 000 $ w wirtualnych środkach : https://tiny.cc/m-etoro-pl\neToro to platforma inwestycyjna oferująca "
                "wiele aktywów. Wartość Twoich inwestycji może wzrosnąć lub spaść. Twój kapitał jest narażony na ryzyko.\n\n"
                "W tym kompletnym poradniku krok po kroku dla początkujących dowiesz się, jak kupować i sprzedawać ETF-y na platformie eToro.")
    IBKR_EN = ("Finally AI can trade your Interactive Brokers Stocks account with amazing results.\n"
               "✪ IBKR (affiliate link): https://ibkr.com/referral/mihail314\n✪ Claude: https://claude.ai")
    UNAVAILABLE = {"transcript": {"state": "unavailable", "source": "none", "reason": "brak napisów po polsku", "windows": []}}

    def video(self, vid, title, description, language, **extra):
        youtube = {"videoId": vid, "detectedLanguage": language, "languageMethod": "declared",
                   "defaultLanguage": language, "defaultAudioLanguage": language,
                   "languageStatus": "in_scope" if language == "pl" else "out_of_scope"}
        return {"id": f"youtube:{vid}", "module": "M1", "creatorId": "youtube:UC" + vid, "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}", "description": description, "youtube": youtube,
                "mediaCoverage": self.UNAVAILABLE, **extra}

    def test_italian_video_with_xtb_link_is_out_of_scope(self):
        result = qualify(self.video("1K-444KBaos", "Come la Norvegia è Diventata Ricchissima", self.XTB_IT, "it"))
        decision = result["reviewDecision"]
        self.assertEqual(decision["route"], "no_signal")
        self.assertIn("poza zakresem: materiał nie jest po polsku (rozpoznany język: włoski, it)", decision["reason"])
        self.assertEqual(result["adRegistry"], {"state": "none"})
        self.assertEqual(result["premises"], [])
        self.assertEqual(result["scope"]["code"], "language")

    def test_same_description_in_polish_video_still_refers(self):
        result = qualify(self.video("reaI2uNoGSk", "Jak KUPIĆ ETF na eToro (Poradnik dla Początkujących)", self.ETORO_PL, "pl"))
        self.assertEqual(result["reviewDecision"]["route"], "refer")
        self.assertNotIn("scope", result)

    def test_foreign_original_with_polish_dubbing_is_out_of_scope(self):
        segments = [{"modality": "speech", "method": "auto_captions", "language": "pl", "lang": "pl", "start": 0.1, "end": 1.5,
                     "text": "Czy faktycznie można handlować", "windowId": "w0"}]
        capture = self.video("J5DqR1DZrFw", "Claude + IBKR: Finally FULL AI Stock Portfolio Automation", self.IBKR_EN, "en",
                             segments=segments)
        capture["mediaCoverage"] = {"transcript": {"state": "full", "source": "auto_captions", "durationSec": 1422,
                                                   "windows": [{"start": 0, "end": 1422}]}}
        decision = qualify(capture)["reviewDecision"]
        self.assertEqual(decision["route"], "no_signal")
        self.assertIn("angielski, en", decision["reason"])

    def test_missing_or_unknown_language_is_not_out_of_scope(self):
        for language in (None, "unknown", "und"):
            capture = self.video("reaI2uNoGSk", "Jak KUPIĆ ETF na eToro", self.ETORO_PL, language)
            self.assertEqual(qualify(capture)["reviewDecision"]["route"], "refer", language)
        capture = self.video("reaI2uNoGSk", "Jak KUPIĆ ETF na eToro", self.ETORO_PL, "pl")
        capture.pop("youtube")
        self.assertEqual(qualify(capture)["reviewDecision"]["route"], "refer")

    def test_polish_video_without_captions_keeps_refer(self):
        capture = self.video("reaI2uNoGSk", "Jak KUPIĆ ETF na eToro", self.ETORO_PL, "pl")
        result = qualify(capture)
        self.assertEqual(result["coverage"]["modalities"]["transcript"]["state"], "unavailable")
        self.assertEqual(result["reviewDecision"]["route"], "refer")


if __name__ == "__main__":
    unittest.main()
