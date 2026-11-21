"""Offline tests of the M3 offer analysis: four axes, identity states, routes and saved real offers."""

import json
from pathlib import Path
import unittest

from analysis import offers

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "fixtures" / "raw" / "discovery" / "m3-2026-11-21"
INDEX = offers.load_registers()
# A valid NIP checksum that belongs to no entity in the test fixtures.
NIP = "1234563218"


def page(text, url="https://doradca-test.pl/oferta"):
    return {"url": url, "text": text, "textSha256": "t"}


def entity(text, domain="doradca-test.pl", footer=""):
    p = page(text, f"https://{domain}/oferta")
    p["identityText"] = footer
    return {"id": f"m3:{domain}", "domain": domain, "pages": [p]}


def empty_index(**extra):
    return {"registers": [], "failures": [], "entries": [], "persons": [], "warnings": [], "checkedAt": "2026-11-21", **extra}


FULL_OFFER = (
    "Doradztwo dla Ciebie\n"
    "Po analizie Twojej sytuacji finansowej i profilu ryzyka wskażemy, co kupić, a co sprzedać.\n"
    "Rekomendujemy, które akcje z GPW trzymać, a które obligacje i fundusze ETF dokupić.\n"
    "Abonament 199 zł miesięcznie. Klienci z całej Polski, spotkania w Warszawie.\n"
    "Inwestowanie wiąże się z ryzykiem i jest dla osób, które chcą oszczędzać na emeryturę oraz budować majątek.\n"
)
FOOTER = f"Doradcza Przykładowa sp. z o.o., ul. Testowa 1, 00-001 Warszawa, NIP {NIP}"


class ActionAxis(unittest.TestCase):
    def axis(self, text):
        return offers.axis_action([page(text)], {})

    def test_hold_is_an_action(self):
        result = self.axis("Napiszemy, czy trzymać akcje spółki, czy je sprzedać.")
        self.assertEqual(result["status"], "present")
        self.assertIn("hold", result["kinds"])

    def test_buy_sell(self):
        self.assertIn("buy_sell", self.axis("Podpowiadamy co kupić i sprzedać, Ty decydujesz.")["kinds"])

    def test_equivalent_acts(self):
        for text in ("Doradzimy zamianę jednostek funduszu na fundusz obligacyjny.",
                     "Zaproponujemy skład portfela dla Ciebie.", "Pomożemy objąć akcje w ofercie publicznej.",
                     "Dobierzemy fundusze do planu."):
            with self.subTest(text=text):
                self.assertIn("equivalent", self.axis(text)["kinds"])

    def test_negative_service_description_only(self):
        result = self.axis("Firma powstała w 2010 roku. Zapraszamy do kontaktu.")
        self.assertEqual(result["status"], "absent")

    def test_advice_word_alone_is_not_an_action(self):
        self.assertEqual(self.axis("Świadczymy doradztwo inwestycyjne.")["status"], "service_only")

    def test_negated_action_is_ignored(self):
        self.assertEqual(self.axis("Nie mówimy co kupić.")["status"], "absent")

    def test_quote_has_locator(self):
        evidence = self.axis("Wstęp.\nPodpowiadamy co kupić.")["evidence"][0]
        self.assertEqual(evidence["locator"]["line"], 2)
        self.assertEqual(evidence["quote"], "Podpowiadamy co kupić.")


class PersonalAxis(unittest.TestCase):
    def axis(self, text):
        return offers.axis_personal([page(text)], {})

    def test_client_situation(self):
        self.assertEqual(self.axis("Dobierzemy strategię do Twoich celów i tolerancji ryzyka.")["status"], "present")

    def test_tailored_alone_is_weak(self):
        self.assertEqual(self.axis("Indywidualne podejście do każdej sprawy.")["status"], "weak")

    def test_absent(self):
        self.assertEqual(self.axis("Kurs pokazuje, jak działa giełda.")["status"], "absent")


class InstrumentAxis(unittest.TestCase):
    def axis(self, text):
        return offers.axis_instrument([page(text)])

    def test_catalog_classes(self):
        cases = {"derivatives": "Sygnały na kontrakty terminowe i opcje na WIG20.", "cfd": "Grupa z sygnałami na CFD i forex.",
                 "emission_allowances": "Rekomendacje dotyczące uprawnień do emisji CO2.", "bonds": "Obligacje skarbowe i korporacyjne.",
                 "funds": "Fundusze ETF i jednostki uczestnictwa.", "shares": "Akcje spółek z GPW."}
        for key, text in cases.items():
            with self.subTest(key=key):
                result = self.axis(text)
                self.assertEqual(result["status"], "catalog")
                self.assertIn(key, result["classes"])

    def test_outside_catalog_has_own_status(self):
        result = self.axis("Inwestycje w nieruchomości, złoto fizyczne i lokaty bankowe.")
        self.assertEqual(result["status"], "outside_only")
        self.assertEqual(set(result["outside"]), {"real_estate", "physical_gold", "deposits"})

    def test_crypto_is_outside(self):
        self.assertEqual(self.axis("Sygnały na bitcoin i altcoiny.")["status"], "outside_only")

    def test_generic_instrument(self):
        self.assertEqual(self.axis("Wszystkie instrumenty finansowe.")["status"], "generic")


class MarketAxis(unittest.TestCase):
    def test_poland(self):
        result = offers.axis_market([page(FULL_OFFER)], "doradca-test.pl")
        self.assertEqual(result["status"], "poland")
        self.assertIn("currency", result["cues"])

    def test_foreign(self):
        result = offers.axis_market([page("We help families in London manage wealth and invest in stocks.")], "example.co.uk")
        self.assertNotEqual(result["status"], "poland")


class Identity(unittest.TestCase):
    def identity(self, footer, domain="doradca-test.pl", index=INDEX, text="Oferta."):
        return offers.match_identity(offers.extract_identity([{**page(text, f"https://{domain}/"), "identityText": footer}], domain), index)

    def test_nip_checksum(self):
        self.assertTrue(offers.valid_nip(NIP))
        self.assertFalse(offers.valid_nip("1234563219"))

    def test_authorized_bos_is_control(self):
        result = self.identity("Dom Maklerski Banku Ochrony Środowiska S.A., KRS 0000048901", "bossa.pl")
        self.assertEqual(result["state"], "authorized_advice")

    def test_other_scope(self):
        result = self.identity("© AIXON INVESTMENT MANAGEMENT SP. Z O.O.")
        self.assertEqual(result["state"], "authorized_other_scope")
        self.assertTrue(result["scopeKnown"])

    def test_agent(self):
        result = self.identity("© 2023 iMERCADO AFI SP. Z O.O.", "imercado.pl")
        self.assertEqual(result["state"], "investment_firm_agent")
        self.assertIn("iX Asset Management", result["label"])

    def test_financewell_name_collision(self):
        # The brand matches two agent rows (sp. z o.o. and sp. k.); the page gives no legal form.
        result = self.identity("Copyright FinanceWell Group sp. z o.o. Oferta", "financewell.pl")
        self.assertEqual(result["state"], "name_collision")
        self.assertGreaterEqual(len(result["matches"]), 2)

    def test_not_found_says_to_be_established(self):
        result = self.identity(FOOTER)
        self.assertEqual(result["state"], "not_found")
        self.assertIn("uprawnienia do ustalenia", result["label"])
        self.assertTrue(result["reviewedRegisters"])

    def test_partner_mention_is_not_the_operator(self):
        # A data supplier or partner named on the page must not clear the operator.
        result = self.identity("Notowania dostarcza Dom Maklerski BDM S.A.\n© 2026 Doradcza Przykładowa sp. z o.o.")
        self.assertEqual(result["state"], "not_found")
        self.assertIn("Dom Maklerski BDM S.A.", result["operator"]["mentioned"])

    def test_registry_failure(self):
        index = empty_index(failures=[{"file": "x", "name": "domy maklerskie", "error": "OSError"}])
        self.assertEqual(self.identity(FOOTER, index=index)["state"], "registry_error")

    def test_no_identity(self):
        self.assertEqual(self.identity("")["state"], "no_identity")

    def test_warning_list_is_separate_signal(self):
        index = empty_index(warnings=[{"id": 1, "domains": ["doradca-test.pl"], "nameKeys": [], "krs": [], "nip": []}])
        result = self.identity(FOOTER, index=index)
        self.assertEqual(result["state"], "not_found")
        self.assertEqual(result["warning"][0]["id"], 1)

    def test_adviser_person_hashed_match(self):
        key = offers.hashed("KOWALSKI JAN")
        index = empty_index(persons=[{"nameSha256": key, "number": "999", "register": "doradcy inwestycyjni (osoby)"}])
        result = self.identity("Jan Kowalski – doradca inwestycyjny", index=index)
        self.assertEqual(result["state"], "authorized_advice")


class Routes(unittest.TestCase):
    def test_refer_full_offer_without_entry(self):
        result = offers.analyze_entity(entity(FULL_OFFER, footer=FOOTER), INDEX)
        self.assertEqual(result["route"], "refer")
        self.assertTrue(3 <= len(result["reasons"]) <= 5)
        self.assertGreaterEqual(result["signalPoints"], 60)

    def test_complete_names_missing_personalisation(self):
        text = "Sygnały kupna akcji z GPW w abonamencie 99 zł. Klienci w Polsce, Warszawa."
        result = offers.analyze_entity(entity(text, footer=FOOTER), INDEX)
        self.assertEqual(result["route"], "complete")
        self.assertTrue(any("personalizacji" in m for m in result["missing"]))

    def test_complete_on_name_collision(self):
        result = offers.analyze_entity(entity(FULL_OFFER, "financewell.pl", footer="FinanceWell, wszystkie prawa zastrzeżone"), INDEX)
        self.assertEqual(result["route"], "complete")
        self.assertIn("kolizję nazw", result["summary"])

    def test_authorized_bos_is_negative_control(self):
        result = offers.analyze_entity(entity(FULL_OFFER, "bossa.pl", footer="Dom Maklerski Banku Ochrony Środowiska S.A."), INDEX)
        self.assertEqual(result["route"], "no_signal")

    def test_education_with_instrument_list(self):
        text = ("Kurs inwestowania: poznasz akcje, obligacje, fundusze ETF, kontrakty terminowe i CFD.\n"
                "Materiał ma charakter wyłącznie edukacyjny i nie stanowi rekomendacji. Cena kursu 299 zł.")
        result = offers.analyze_entity(entity(text, footer=FOOTER), INDEX)
        self.assertEqual(result["route"], "no_signal")

    def test_outside_catalog(self):
        text = "Dobierzemy dla Ciebie mieszkanie pod wynajem i złoto inwestycyjne, zgodnie z Twoimi celami. Warszawa, 500 zł."
        result = offers.analyze_entity(entity(text, footer=FOOTER), INDEX)
        self.assertEqual(result["route"], "no_signal")

    def test_wording_never_states_violation(self):
        result = offers.analyze_entity(entity(FULL_OFFER, footer=FOOTER), INDEX)
        text = json.dumps(result, ensure_ascii=False).casefold()
        self.assertNotIn("naruszeni", text)
        self.assertNotIn("nielegaln", text)

    def test_form_and_initiative(self):
        result = offers.form_and_initiative([page("Alerty wysyłamy SMS-em. Umów konsultację telefoniczną.")])
        self.assertIn("electronic", result["forms"])
        self.assertIn("firm", result["initiative"])
        self.assertIn("client", result["initiative"])


@unittest.skipUnless((RUN / "entities.json").exists(), "brak zapisanego przebiegu odkrywania M3")
class SavedOffers(unittest.TestCase):
    """Real pages saved on 2026-11-21 (fixtures/raw/discovery/m3-2026-11-21)."""

    @classmethod
    def setUpClass(cls):
        cls.results = {r["entityId"]: r for r in offers.analyze_run(RUN, INDEX)}

    def test_every_result_has_locators_and_route(self):
        for key, result in self.results.items():
            with self.subTest(entity=key):
                self.assertIn(result["route"], ("refer", "complete", "no_signal"))
                for axis in result["axes"].values():
                    for evidence in axis["evidence"]:
                        self.assertTrue(evidence["locator"]["url"].startswith("https://"))

    def test_portfolio_offer_without_operator_data_is_referred(self):
        result = self.results["m3:rdmwm.pl"]
        self.assertEqual(result["route"], "refer")
        self.assertEqual(result["identity"]["state"], "no_identity")
        self.assertIn("uprawnienia do ustalenia", result["summary"])

    def test_authorized_and_agent_controls(self):
        expected = {"control:web:bossa.pl/oferta/doradztwo": "authorized_advice", "m3:mbank.pl": "authorized_advice",
                    "m3:erste.pl": "authorized_advice", "m3:imercado.pl": "investment_firm_agent", "m3:phinance.pl": "investment_firm_agent"}
        for key, state in expected.items():
            with self.subTest(entity=key):
                self.assertEqual(self.results[key]["identity"]["state"], state)
                self.assertEqual(self.results[key]["route"], "no_signal")

    def test_education_control(self):
        self.assertEqual(self.results["control:web:bossa.pl/edukacja/rynek-i-inwestycje/instrumenty-finansowe"]["route"], "no_signal")

    def test_signal_service_without_personalisation_needs_completion(self):
        for key in ("m3:ppcg.com.pl", "m3:inwestowaniegpw.pl"):
            with self.subTest(entity=key):
                self.assertEqual(self.results[key]["route"], "complete")

    def test_notified_firm_without_advice_code(self):
        result = self.results["m3:deriv.com"]
        self.assertEqual(result["identity"]["state"], "authorized_other_scope")
        self.assertNotEqual(result["route"], "refer")


if __name__ == "__main__":
    unittest.main()
