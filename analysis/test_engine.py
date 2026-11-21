import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from analysis.checks import marketing, LABELS, NA, OBS, OK, UNKNOWN
from analysis.engine import analyze, calibration, demo_captures, relation
from analysis.transcribe import ASR, MEDIA, MODEL, replay_file, transcribe_excerpt, transcribe_file


class Findings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {cap["id"]: cap for cap in demo_captures()}

    def test_voice_evidence_is_verbatim_and_time_addressable(self):
        cap = self.cases["demo-studio-aurora"]
        found = analyze(cap)
        self.assertTrue(found["speechOnlySignal"])
        self.assertLess(found["descriptionScore"], 35)
        quote = next(e for e in found["evidence"] if e["kind"] == "audio")
        self.assertIn(quote["text"], [s["text"] for s in replay_file(MEDIA / "studio.mp4")["segments"]])
        self.assertGreater(quote["start"], 0)
        self.assertTrue(quote["url"].startswith("/media/studio.mp4#t="))
        self.assertTrue(found["contractDemo"])
        self.assertEqual(found["publishedAt"], "2026-11-18")

    def test_same_scorer_applied_to_both_modalities(self):
        voice = self.cases["demo-studio-aurora"]
        for desc, only in [("Opis warsztatu", True), ("Partnerem programu jest Aurora.", False),
                           ("Skorzystaj z mojego kodu rabatowego.", False), ("", False)]:
            cap = dict(voice, description=desc)
            result = analyze(cap)
            baseline = analyze(dict(cap, segments=[]))
            delta = result["modalityComparison"]
            self.assertEqual(delta, {"descriptionOnly": baseline["score"], "withAudio": result["score"],
                                     "delta": result["score"]-baseline["score"]})
            self.assertEqual(result["speechOnlySignal"], only)
        silent = analyze(dict(voice, description="Opis", segments=[{"start":0, "end":2, "text":"Dzień dobry"}]))
        self.assertFalse(silent["speechOnlySignal"])
        self.assertTrue(any(e["kind"] == "audio" for e in silent["evidence"]))

    def test_single_spoken_brand_and_cta_without_disclosure(self):
        clip = self.cases["demo-aurora-kod"]
        found = analyze(clip)
        quote = found["evidence"][0]
        self.assertEqual(quote["text"].split().count("aurora"), 1)
        self.assertEqual(quote["kind"], "audio")
        self.assertEqual((quote["start"], quote["end"]), (0.33, 3.6))
        self.assertTrue(found["possibleUndisclosedPromotion"])
        self.assertEqual(found["signalType"], "brand_cta")
        self.assertEqual(found["descriptionDisclosureStatus"], "not_found")
        self.assertEqual(found["modalityComparison"], {"descriptionOnly": 12, "withAudio": 74, "delta": 62})
        disclosed = analyze(dict(clip, description="Materiał sponsorowany."))
        self.assertFalse(disclosed["possibleUndisclosedPromotion"])
        self.assertEqual(disclosed["descriptionDisclosureStatus"], "observed")
        self.assertFalse(analyze(dict(clip, description=""))["possibleUndisclosedPromotion"])
        audio = [{"start": 0.4, "end": 1.6, "text": "W zestawieniu pojawia się Aurora."}]
        neutral = analyze(dict(clip, segments=audio))
        self.assertEqual(neutral["signalType"], "neutral_mention")
        self.assertEqual(neutral["score"], 24)
        self.assertFalse(neutral["possibleUndisclosedPromotion"])
        self.assertEqual(analyze(dict(clip, segments=[], description="Otwórz rachunek w firmie Fikcyjna.",
                                      brand="Fikcyjna"))["signalType"], "brand_cta")
        other = analyze(self.cases["demo-studio-aurora"])
        self.assertEqual(other["signalType"], "declaration")
        self.assertFalse(other["possibleUndisclosedPromotion"])

    def test_negative_and_unrelated_denial(self):
        self.assertLess(relation("To nie jest reklama kursu.")[0], 35)
        self.assertLess(relation("Dziś krytykuję XTB.")[0], 35)
        self.assertGreater(relation("To nie jest reklama kursu. Partnerem odcinka jest XTB.")[0], 70)
        self.assertEqual(analyze({"description": "Partnerem programu jest XTB."})["brand"], "XTB")
        self.assertLess(analyze({"module": "M3", "description": "Nie dobiorę dla ciebie akcji."})["score"], 35)
        self.assertGreater(analyze({"module": "M3", "description": "Nie rekomenduję obligacji, ale dobiorę dla ciebie akcje."})["score"], 70)

    def test_m1_recognizes_disclosure_labels_separately_from_named_declarations(self):
        for marker in ("Materiał reklamowy XTB.", "#współpraca", "[Reklama]", "Materiał sponsorowany."):
            with self.subTest(marker=marker):
                source = "https://example.org/material"
                description = marker + "\nZałóż rachunek w XTB."
                result = analyze({"description": description, "url": source})
                self.assertEqual(result["score"], 74)
                self.assertEqual(result["descriptionDisclosureStatus"], "observed")
                self.assertEqual(result["descriptionDisclosureType"], "label")
                self.assertNotIn("descriptionDisclosedBrand", result)
                self.assertFalse(result["possibleUndisclosedPromotion"])
                self.assertTrue(any(marker in item["text"] and item["url"] == source
                                    for item in result["evidence"]))

        label_only = analyze({"description": "#współpraca"})
        self.assertEqual(label_only["signalType"], "disclosure_label")
        self.assertNotIn("brand", label_only)
        declared = analyze({"description": "Partnerem odcinka jest firma XTB. Omawiamy także eToro."})
        self.assertEqual((declared["score"], declared["descriptionDisclosureType"]), (94, "declaration"))
        self.assertEqual(declared["descriptionDisclosedBrand"], "XTB")
        self.assertEqual(declared["brand"], "XTB")
        other_brand = analyze({"description": "Partnerem odcinka jest Fikcyjna, a XTB ma inny cennik."})
        self.assertEqual(other_brand["descriptionDisclosureType"], "declaration")
        self.assertNotIn("descriptionDisclosedBrand", other_brand)
        self.assertNotIn("brand", other_brand)
        headed = analyze({"description": "Partner programu: XTB."})
        self.assertEqual(headed["descriptionDisclosedBrand"], "XTB")
        sounded = analyze({"description": "Porównanie stawek w eToro.", "segments": [
            {"start": 0.2, "end": 1.4, "text": "Partnerem odcinka jest XTB."},
        ]})
        self.assertEqual(sounded["brand"], "XTB")
        self.assertEqual(sounded["descriptionDisclosureStatus"], "not_found")

    def test_m1_neutral_discussion_and_fraud_warning_are_not_promotions(self):
        cases = (
            "W tym odcinku mówimy o tym, czym jest reklama.",
            "Czy partnerem programu jest XTB?",
            "Ktoś podszywa się pod XTB i mówi: otwórz rachunek. Uważaj na oszustwo.",
            "Otwórz rachunek w XTB. To próba wyłudzenia.",
            "Nie używaj kodu polecającego od tego nadawcy.",
            "Odcinek nie powstał we współpracy z XTB.",
        )
        for description in cases:
            with self.subTest(description=description):
                result = analyze({"description": description})
                self.assertLess(result["score"], 60)
                self.assertEqual(result["descriptionDisclosureStatus"], "not_found")
                self.assertFalse(result["possibleUndisclosedPromotion"])

    def test_m1_keeps_brand_cta_and_negation_in_their_own_clauses(self):
        independent = analyze({"description": "XTB opublikowało wyniki. otwórz rachunek w innym banku."})
        self.assertEqual(independent["signalType"], "neutral_mention")
        self.assertFalse(independent["possibleUndisclosedPromotion"])
        positive = analyze({"description": "Uważaj na oszustwa w internecie. Otwórz rachunek w XTB."})
        self.assertEqual(positive["score"], 74)
        self.assertTrue(positive["possibleUndisclosedPromotion"])
        self.assertEqual(positive["evidence"][0]["text"], "Otwórz rachunek w XTB.")

        separate = analyze({"description": "To nie jest reklama kursu. Załóż rachunek w XTB."})
        self.assertEqual(separate["score"], 74)
        self.assertEqual(separate["descriptionDisclosureStatus"], "not_found")
        self.assertTrue(separate["possibleUndisclosedPromotion"])
        contrast = analyze({"description": "Nie współpracuję z eToro, ALE partnerem odcinka jest XTB."})
        self.assertEqual(contrast["descriptionDisclosedBrand"], "XTB")
        self.assertEqual(contrast["score"], 94)

    def test_registry_entities_remain_separate(self):
        result = analyze(self.cases["public-financewell-agent"])
        self.assertEqual([e["id"] for e in result["registry"]["entries"]], [4844186, 4844187])
        self.assertTrue(all(e["principal"] == "EVO Dom Maklerski S.A." for e in result["registry"]["entries"]))
        self.assertEqual(result["registry"]["status"], "do wyjaśnienia")
        self.assertLess(analyze(self.cases["demo-pracownia-edukacja"])["score"], 35)

    def test_offer_cues_are_verbatim_and_registry_is_not_identity_proof(self):
        cap = self.cases["public-bos-profil"]
        result = analyze(cap)
        self.assertEqual({c["id"] for c in result["checks"] if c["state"] == OBS},
                         {"personalizacja", "instrument", "czynność"})
        for check in result["checks"]:
            self.assertIn(check["evidence"], cap["description"])
            self.assertEqual(check["url"], cap["url"])
        entry = result["registry"]["entries"][0]
        self.assertEqual(entry["authorizationDate"], "18-08-1994")
        self.assertIn("5", entry["scopeCodes"].split(", "))
        self.assertIn("kandydatem", result["summary"])
        self.assertEqual(result["registryStatus"], "do wyjaśnienia")
        unrelated = dict(cap, registry={**cap["registry"], "entries": [{"id": 1, "name": "Inny podmiot"}]})
        self.assertNotIn("Potwierdzono tożsamość", analyze(unrelated)["summary"])

    def test_m3_instrument_cue_uses_words_and_negation(self):
        for text in ("Transakcja w portfelu. Brak szczegółów.", "Nie dobieramy akcji dla klientów."):
            found = analyze({"module": "M3", "description": text})
            self.assertEqual(next(c for c in found["checks"] if c["id"] == "instrument")["state"], UNKNOWN)

    def test_registry_join_rejects_untrusted_source_or_conflicting_identifier(self):
        path = Path(__file__).resolve().parents[1] / "fixtures/validation/bossa-discovery-2026-11-21.json"
        cap = json.loads(path.read_text())["capture"]
        self.assertEqual(analyze(cap)["registryStatus"], "zgodność w stanie archiwalnym")
        for changed in (
            {**cap, "url": "https://other.example/oferta"},
            {**cap, "identityEvidence": {**cap["identityEvidence"], "krsCandidates": ["0000048901", "0000099999"]}},
            {**cap, "identityEvidence": {**cap["identityEvidence"], "nip": "NIP 000-00-00-000"}},
        ):
            with self.subTest(changed=changed.get("url")):
                self.assertEqual(analyze(changed)["registryStatus"], "do wyjaśnienia")
                self.assertNotIn("registry", analyze(changed))

    def test_discovered_public_material_remains_traceable_on_replay(self):
        from collectors.discovery import discover
        first = discover("replay", ())
        again = discover("replay", {c["id"] for c in first["creators"]})
        cap_id = "peertube:959e5bcc-8562-4a2c-9d78-6b8b83d8d306"
        cap = next(c for c in first["captures"] if c["id"] == cap_id)
        second = next(c for c in again["captures"] if c["id"] == cap_id)
        creator = next(c for c in first["creators"] if c["id"] == cap["creatorId"])
        self.assertTrue(creator["isNew"])
        self.assertFalse(next(c for c in again["creators"] if c["id"] == cap["creatorId"])["isNew"])
        self.assertEqual((cap["id"], cap["contentHash"]), (second["id"], second["contentHash"]))
        finding = analyze(cap)
        self.assertLess(finding["score"], 60)
        self.assertIn(finding["evidence"][0]["text"], cap["description"])
        self.assertEqual(finding["evidence"][0]["url"], cap["url"])
        self.assertEqual(finding["provenance"]["sourceUrl"], creator["discovery"]["sourceUrl"])

    def test_public_partner_declaration_has_verbatim_evidence(self):
        from collectors.discovery import discover
        cap = next(c for c in discover("replay", ())["captures"] if c["id"] == "youtube:xtMqKkFO-0M")
        finding = analyze(cap)
        self.assertEqual(finding["score"], 94)
        self.assertEqual(finding["descriptionDisclosedBrand"], "XTB")
        self.assertIn(finding["evidence"][0]["text"], cap["description"])
        self.assertEqual(finding["evidence"][0]["url"], cap["url"])

    def test_archive_evidence_resolves(self):
        from analysis.engine import SNAPSHOTS
        report = analyze(self.cases["dom-xtb-etf"])
        self.assertEqual(len(report["checks"]), 19)
        for item in report["evidence"]:
            if item["kind"] == "screenshot":
                image = SNAPSHOTS / item["url"].removeprefix("/evidence/")
                self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), item["sha256"])
        old_geometry = next(c for c in report["checks"] if c["id"] == "8")
        self.assertEqual(old_geometry["state"], UNKNOWN)
        self.assertNotIn("measurements", old_geometry)

    def test_calibration_uses_same_groups_and_exposes_mistakes(self):
        low, high = calibration(35), calibration(70)
        self.assertEqual(low["datasetId"], high["datasetId"])
        for report in (low, high):
            self.assertEqual(report["n"], sum(report[k] for k in ("tn", "fn", "tp", "fp")))
            self.assertEqual(report["n"], report["publicExamples"] + report["syntheticExamples"])
            self.assertEqual(report["n"], len({s["id"] for s in report["examples"]}))
            self.assertEqual(report["cost"], report["fp"] + 2 * report["fn"])
            self.assertTrue(report["errors"])
        self.assertGreater(high["fn"], low["fn"])


class Marketing(unittest.TestCase):
    def states(self, text="", **kwargs):
        rows = marketing({"description": text, **kwargs})
        self.assertEqual([r["id"] for r in rows], list(LABELS))
        self.assertTrue(all(r["evidence"] for r in rows))
        return {r["id"]: r["state"] for r in rows}

    def test_missing_modalities_abstain(self):
        self.assertEqual(set(self.states().values()), {UNKNOWN})

    def test_name_marking_risk(self):
        m = self.states("Aurora S.A. Reklama. Możliwy zysk. Ryzyko utraty kapitału.", legalName="Aurora S.A.", fullText=True)
        self.assertEqual([m[k] for k in ("1", "2", "3")], [OK, OK, OBS])
        n = self.states("Warsztat dla inwestorów.", legalName="Aurora S.A.", fullText=True)
        self.assertEqual([n[k] for k in ("1", "2", "3")], [OBS, OBS, UNKNOWN])

    def test_verified_ad_region(self):
        region = {"complete": True, "warningPx": 8, "warningRole": "footer", "before": False, "after": True,
                  "nodes": [{"px": 16, "visible": True, "text": "Warunki promocji"},
                            {"px": 8, "visible": True, "text": "Menu " * 55, "navigation": True}]}
        a = self.states(adRegion=region, verifiedLanguages={"offer": "pl", "warning": "en"})
        self.assertEqual([a[k] for k in ("4", "6", "7", "10")], [OBS]*4)
        region.update(warningPx=16, before=True, warningRole="body")
        b = self.states(adRegion=region, verifiedLanguages={"offer": "pl", "warning": "pl"})
        self.assertEqual([b[k] for k in ("4", "6", "7", "10")], [OK]*4)
        region["nodes"].append({"px": 11, "visible": True, "text": "Warunki promocji"})
        self.assertEqual(self.states(adRegion=region)["4"], UNKNOWN)

    def test_historical_and_conditional_rules(self):
        raw = "W porównaniu z innymi. Wyniki historyczne w USD brutto. Prognoza zysku. Podatek."
        audited = self.states(raw, fullText=True)
        self.assertEqual([audited[k] for k in ("11", "12a", "12b", "13", "14", "15", "16")], [OBS]*7)
        clear = raw + " Zmiany kursów walut wpływają na wynik. Opłaty obniżają wynik. Wyniki nie gwarantują przyszłych wyników. Prognoza nie stanowi gwarancji. Podatki zależą od indywidualnej sytuacji i mogą ulec zmianie."
        checks = self.states(clear, fullText=True)
        self.assertEqual([checks[k] for k in ("12b", "14", "15", "16")], [OK]*4)
        for key in ("11", "12a", "12b", "13", "14", "15", "16"):
            self.assertEqual(self.states("Wykład.", fullText=True)[key], NA)

    def test_neutral_supervision(self):
        negative = self.states("Firma podlega nadzorowi KNF.", fullText=True)
        positive = self.states("KNF poleca naszą ofertę. KNF gwarantuje jej bezpieczeństwo.", fullText=True)
        self.assertEqual([negative["17"], negative["18"]], [OK, OK])
        self.assertEqual([positive["17"], positive["18"]], [OBS, OBS])


class Media(unittest.TestCase):
    def test_replay_rejects_other_bytes(self):
        with tempfile.NamedTemporaryFile() as sample:
            sample.write(b"inne dane")
            sample.flush()
            with self.assertRaises(ValueError):
                replay_file(sample.name)

    @unittest.skipUnless(shutil.which("ffmpeg") and (ASR / MODEL / "am" / "final.mdl").is_file(),
                         "wymaga ffmpeg i pobranego modelu PL")
    def test_inference_on_new_file_and_partial_mp3(self):
        with tempfile.TemporaryDirectory() as d:
            wav, mp3 = Path(d)/"new.wav", Path(d)/"partial.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", "4", "-i", str(MEDIA/"studio.mp4"),
                            "-t", "4", "-ar", "22050", str(wav)], check=True)
            report = transcribe_file(wav)
            self.assertIn("aurora", " ".join(item["text"] for item in report))
            self.assertLess(report[0]["start"], 1)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(MEDIA/"studio.mp4"), "-q:a", "4", str(mp3)], check=True)
            data = mp3.read_bytes()
            mp3.write_bytes(data[:len(data)*2//3])
            partial = transcribe_excerpt(mp3, seconds=8)
            self.assertTrue(any("partnerem programu" in item["text"] for item in partial))
            self.assertLessEqual(partial[-1]["end"], 8)

    def test_invalid_media(self):
        with tempfile.NamedTemporaryFile() as sample:
            with self.assertRaises(ValueError):
                transcribe_file(sample.name)
        with self.assertRaises(ValueError):
            transcribe_excerpt("sample", 121)


if __name__ == "__main__":
    unittest.main()
