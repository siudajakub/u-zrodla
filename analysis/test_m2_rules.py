"""Synthetic positive, negative and not-applicable/no-data cases for each of the 19 UKNF M2 criteria."""
import re
import unittest

from analysis.m2_card import build, card
from analysis.m2_fixture import FOOTER_NAME, block, material
from analysis.m2_readability import measure as readability
from analysis.m2_rules import NA, OBSERVATION, OK, ORDER, PREMISE, UNKNOWN, evaluate

H1 = block("Inwestuj w ETF", h=1, px=40, y=50)
LABEL = block("Materiał marketingowy.", y=20, px=14)
CLAIM = block("Otrzymuj dywidendy i buduj źródło dochodu z ETF.", y=120)
WARN = block("Inwestowanie w ETF wiąże się z ryzykiem utraty części lub całości kapitału.", y=160)
BODY = block("Kupuj fundusze ETF na giełdach w Europie i USA bez wychodzenia z domu.", y=220)
CTA = block("Otwórz konto", y=260, tag="button")
CLEAN = [LABEL, H1, CLAIM, WARN, BODY, CTA, FOOTER_NAME]


def state(blocks, key, phone=None, **kwargs):
    rows = {r["id"]: r for r in evaluate(material(blocks, phone, **kwargs))}
    return rows[key]["state"], rows[key]


def replace(blocks, old, new):
    return [new if b is old else b for b in blocks]


def without(blocks, *old):
    return [b for b in blocks if all(b is not o for o in old)]


class Shape(unittest.TestCase):
    def test_nineteen_rows_with_basis_and_applicability(self):
        rows = evaluate(material(CLEAN))
        self.assertEqual([r["id"] for r in rows], list(ORDER))
        for row in rows:
            self.assertIn(row["state"], {OK, PREMISE, NA, UNKNOWN})
            self.assertTrue(row["basis"].startswith("Art."))
            self.assertTrue(row["evidence"])
            if row["state"] in {NA, UNKNOWN}:
                self.assertTrue(row.get("applicability"), row["id"])

    def test_no_render_is_no_data_everywhere(self):
        rows = evaluate({"firm": {}, "url": "https://x.pl/", "views": {}})
        self.assertEqual({r["state"] for r in rows}, {UNKNOWN})

    def test_clean_page_has_no_premise(self):
        rows = evaluate(material(CLEAN))
        self.assertEqual([r["id"] for r in rows if r["state"] == PREMISE], [])


class Identity(unittest.TestCase):
    def test_1(self):
        self.assertEqual(state(CLEAN, "1")[0], OK)
        self.assertEqual(state(without(CLEAN, FOOTER_NAME), "1")[0], PREMISE)
        hidden = block(FOOTER_NAME["t"], hid="details:closed", role="footer")
        self.assertEqual(state(replace(CLEAN, FOOTER_NAME, hidden), "1")[0], PREMISE)
        m = material(CLEAN)
        m["firm"] = {}
        self.assertEqual({r["id"]: r for r in evaluate(m)}["1"]["state"], UNKNOWN)

    def test_2(self):
        self.assertEqual(state(CLEAN, "2")[0], OK)
        self.assertEqual(state(without(CLEAN, LABEL), "2")[0], OBSERVATION)  # observation: 0 points, no effect on the route
        from analysis.m2_card import build as build_card
        rows = evaluate(material(without(CLEAN, LABEL)))
        score, _, _, extra = build_card({"id": "x", "url": "https://x.pl/"}, rows)
        self.assertEqual((score, extra["m2Card"]["route"]), (0, "no_signal"))
        self.assertEqual(extra["m2Card"]["counts"].get(OBSERVATION), 1)
        self.assertEqual(sum(extra["m2Card"]["counts"].values()), 19)
        self.assertEqual([c["id"] for c in extra["reviewScore"]["components"]], [])
        education = [block("Czym jest obligacja?", h=1, px=36), block("Obligacja to papier dłużny emitowany przez Skarb Państwa lub firmy."), FOOTER_NAME]
        self.assertEqual(state(education, "2", kind="education")[0], NA)


class RiskNextToProfit(unittest.TestCase):
    def test_3_positive_far_warning_and_wrong_product(self):
        far = block(WARN["t"], y=2100, sec=5)
        s, row = state(replace(CLEAN, WARN, far), "3")
        self.assertEqual(s, PREMISE)
        self.assertIn("px dalej", row["evidence"])
        cfd = block("Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków pieniężnych z powodu dźwigni finansowej.",
                    y=8, px=14, role="header", sec=0, fix="sticky")
        s, row = state(replace(CLEAN, WARN, cfd), "3")
        self.assertEqual(s, PREMISE)
        self.assertIn("CFD", row["evidence"])

    def test_3_negative_adjacent_generic_or_sticky_cfd_on_cfd_page(self):
        self.assertEqual(state(CLEAN, "3")[0], OK)
        cfd_claim = block("Zarabiaj na wzrostach i spadkach kursów walut.", y=120)
        cfd_warn = block("Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków pieniężnych z powodu dźwigni finansowej.",
                         y=8, px=14, role="header", sec=0, fix="sticky")
        page = [LABEL, block("Forex", h=1, px=40, y=50), cfd_claim, BODY, cfd_warn, FOOTER_NAME]
        self.assertEqual(state(page, "3", url="https://www.example-dm.pl/forex", title="Forex CFD")[0], OK)

    def test_3_not_applicable_for_fee_only_benefit(self):
        fee = block("0% prowizji na akcje i ETF do 100 000 EUR obrotu miesięcznie.", y=120)
        s, row = state(without(replace(CLEAN, CLAIM, fee), WARN), "3")
        self.assertEqual(s, NA)
        self.assertIn("nie są twierdzeniem o zysku", row["evidence"])


class Presentation(unittest.TestCase):
    def far_claim_page(self, warning):
        return [LABEL, H1, CLAIM, BODY, CTA, warning, FOOTER_NAME]

    def test_4(self):
        self.assertEqual(state(CLEAN, "4")[0], OK)
        small = block(WARN["t"], y=160, px=10)
        self.assertEqual(state(replace(CLEAN, WARN, small), "4")[0], PREMISE)
        self.assertEqual(state(without(CLEAN, WARN), "4")[0], UNKNOWN)
        info = [block("O nas", h=1, px=36), block("Jesteśmy domem maklerskim od 1995 roku."), FOOTER_NAME]
        self.assertEqual(state(info, "4", kind="education")[0], NA)

    def test_5(self):
        self.assertEqual(state(CLEAN, "5")[0], OK)
        pale = block(WARN["t"], y=160, cr=2.3)
        s, row = state(replace(CLEAN, WARN, pale), "5")
        self.assertEqual(s, PREMISE)
        self.assertIn("kontrast", row["evidence"])
        phone = replace(CLEAN, WARN, block(WARN["t"], y=1200, sec=1))
        s, row = state(CLEAN, "5", phone=phone)
        self.assertEqual(s, PREMISE)
        self.assertIn("po przewinięciu", row["evidence"])
        self.assertEqual(state(without(CLEAN, WARN), "5")[0], UNKNOWN)

    def test_6(self):
        self.assertEqual(state(CLEAN, "6")[0], OK)
        footer = block(WARN["t"], y=2850, px=11, role="footer", sec=9)
        self.assertEqual(state(self.far_claim_page(footer), "6")[0], PREMISE)
        legal = block(WARN["t"], y=600, px=11, role="footnote", sec=2)
        self.assertEqual(state(self.far_claim_page(legal), "6")[0], PREMISE)
        self.assertEqual(state(without(CLEAN, WARN), "6")[0], UNKNOWN)

    def test_7(self):
        self.assertEqual(state(CLEAN, "7")[0], OK)
        folded = block(WARN["t"], hid="details:closed")
        s, row = state(replace(CLEAN, WARN, folded), "7")
        self.assertEqual(s, PREMISE)
        self.assertIn("rozwin", row["evidence"])
        m = material(without(CLEAN, WARN))
        for v in m["views"].values():
            v["riskLinks"] = [{"t": "Ostrzeżenie o ryzyku", "href": "https://www.example-dm.pl/ryzyko.pdf"}]
        self.assertEqual({r["id"]: r for r in evaluate(m)}["7"]["state"], PREMISE)
        self.assertEqual(state(without(CLEAN, WARN), "7")[0], UNKNOWN)

    def test_8(self):
        self.assertEqual(state(CLEAN, "8")[0], OK)
        cut = replace(CLEAN, WARN, block(WARN["t"], y=160, trunc="ellipsis"))
        self.assertEqual(state(CLEAN, "8", phone=cut)[0], PREMISE)
        tiny = replace(CLEAN, WARN, block(WARN["t"], y=160, px=10))
        self.assertEqual(state(CLEAN, "8", phone=tiny)[0], PREMISE)
        m = material(CLEAN)
        m["views"]["phone"]["scrollWidth"] = 640
        self.assertEqual({r["id"]: r for r in evaluate(m)}["8"]["state"], PREMISE)
        self.assertEqual(state(CLEAN, "8", phone=False)[0], UNKNOWN)

    def test_9(self):
        self.assertEqual(state(CLEAN, "9")[0], OK)
        hard = block("Fundusze ETF oparte na instrumentach pochodnych charakteryzują się podwyższoną zmiennością, co powoduje, że niewielka zmienność kursu instrumentu bazowego "
                     "może skutkować nieproporcjonalnie wysokimi stratami przekraczającymi wartość depozytu zabezpieczającego, "
                     "a ekspozycja inwestora nie jest ograniczona wysokością zaangażowanych środków.", y=160)
        s, row = state(replace(CLEAN, WARN, hard), "9")
        self.assertEqual(s, PREMISE)
        self.assertIn("FOG-PL", row["evidence"])
        self.assertTrue(row["measurements"][0]["readability"]["difficult"])
        self.assertEqual(state(without(CLEAN, WARN), "9")[0], UNKNOWN)

    def test_10(self):
        self.assertEqual(state(CLEAN, "10")[0], OK)
        english = block("Investing in ETFs involves the risk of loss of your capital and you may lose money.", y=160, lang="en")
        self.assertEqual(state(replace(CLEAN, WARN, english), "10")[0], PREMISE)
        self.assertEqual(state(without(CLEAN, WARN), "10")[0], UNKNOWN)


class Content(unittest.TestCase):
    def test_11(self):
        self.assertEqual(state(CLEAN, "11")[0], NA)
        cheap = block("Najniższe prowizje na rynku dla inwestorów w ETF.", y=300, sec=3)
        self.assertEqual(state(CLEAN + [cheap], "11")[0], PREMISE)
        sourced = block("Najniższe prowizje na rynku według rankingu Gazety Giełdy 2025.", y=300, sec=3)
        self.assertEqual(state(CLEAN + [sourced], "11")[0], OK)

    HIST = block("W 2023 roku fundusz zyskał 12% wartości.", y=400, sec=4)

    def test_12a(self):
        self.assertEqual(state(CLEAN, "12a")[0], NA)
        s, row = state(CLEAN + [self.HIST], "12a")
        self.assertEqual(s, PREMISE)
        self.assertIn("ostatnie 5 lat", row["evidence"])
        full = block("Stopa zwrotu za lata 2020–2024: 2020 4%, 2021 9%, 2022 -6%, 2023 12%, 2024 7%. Źródło: dane własne, okres 2020–2024.", y=400, sec=4)
        self.assertEqual(state(CLEAN + [full], "12a")[0], OK)

    def test_12b(self):
        self.assertEqual(state(CLEAN, "12b")[0], NA)
        self.assertEqual(state(CLEAN + [self.HIST], "12b")[0], PREMISE)
        usd = block("W 2023 roku fundusz zyskał 12% w USD. Wyniki nie uwzględniają opłat i prowizji.", y=400, sec=4)
        s, row = state(CLEAN + [usd], "12b")
        self.assertEqual(s, PREMISE)
        self.assertIn("kursów walut", row["evidence"])
        ok = block("W 2023 roku fundusz zyskał 12% w USD. Wyniki nie uwzględniają opłat i prowizji. Zmiany kursów walut mogą wpływać na wynik w PLN.",
                   y=400, sec=4)
        self.assertEqual(state(CLEAN + [ok], "12b")[0], OK)

    def test_13(self):
        self.assertEqual(state(CLEAN, "13")[0], NA)
        headline = block("Fundusz zyskał 38% w 2024 roku", h=1, px=44, y=40, sec=1)
        self.assertEqual(state(replace(CLEAN, H1, headline), "13")[0], PREMISE)
        self.assertEqual(state(CLEAN + [block(self.HIST["t"], y=1500, px=14, sec=4)], "13")[0], OK)

    def test_14(self):
        self.assertEqual(state(CLEAN, "14")[0], NA)
        self.assertEqual(state(CLEAN + [self.HIST], "14")[0], PREMISE)
        disclaimer = block("Wyniki historyczne nie są wiarygodnym wskaźnikiem przyszłych wyników.", y=430, sec=4)
        s, row = state(CLEAN + [self.HIST, disclaimer], "14")
        self.assertEqual(s, OK)
        self.assertEqual(row["mode"], "automatyczny")

    def test_15(self):
        self.assertEqual(state(CLEAN, "15")[0], NA)
        forecast = block("Prognozujemy, że portfel przyniesie 8% rocznie w najbliższych latach.", y=500, sec=5)
        s, row = state(CLEAN + [forecast], "15")
        self.assertEqual(s, PREMISE)
        self.assertEqual(row["flags"], ["wykryto prognozę"])
        caveat = block("Prognoza nie jest wiarygodnym wskaźnikiem przyszłych wyników.", y=530, sec=5)
        s, row = state(CLEAN + [forecast, caveat], "15")
        self.assertEqual(s, OK)
        self.assertEqual(row["flags"], ["wykryto prognozę"])  # detection is reported even when the warning exists

    def test_16(self):
        self.assertEqual(state(CLEAN, "16")[0], NA)
        tax = block("Na IKE nie zapłacisz podatku Belki od zysków.", y=600, sec=6)
        self.assertEqual(state(CLEAN + [tax], "16")[0], PREMISE)
        both = block("Korzyść podatkowa zależy od indywidualnej sytuacji klienta, a przepisy mogą ulec zmianie.", y=630, sec=6)
        self.assertEqual(state(CLEAN + [tax, both], "16")[0], OK)


class Supervision(unittest.TestCase):
    NO_AUTH = [LABEL, H1, CLAIM, WARN, BODY, CTA, block("EXAMPLE DOM MAKLERSKI S.A. z siedzibą w Warszawie.", y=2900, role="footer", sec=9)]

    def test_17(self):
        self.assertEqual(state(self.NO_AUTH, "17")[0], NA)
        self.assertEqual(state(CLEAN, "17")[0], OK)
        approved = block("Produkt zatwierdzony przez KNF.", y=700, sec=7)
        self.assertEqual(state(CLEAN + [approved], "17")[0], PREMISE)
        prospectus = block("Prospekt zatwierdzony przez Komisję Nadzoru Finansowego. Zatwierdzenia prospektu nie należy rozumieć jako poparcia papierów wartościowych.",
                           y=700, sec=7)
        self.assertEqual(state(CLEAN + [prospectus], "17")[0], OK)

    def test_18(self):
        self.assertEqual(state(self.NO_AUTH, "18")[0], NA)
        self.assertEqual(state(CLEAN, "18")[0], OK)
        safe = block("Twoje środki są bezpieczne, bo jesteśmy nadzorowani przez KNF.", y=800, sec=8)
        self.assertEqual(state(CLEAN + [safe], "18")[0], PREMISE)
        heading = block("Bezpieczeństwo przede wszystkim", h=2, px=28, y=900, sec=10)
        regulated = block("Działamy pod nadzorem Komisji Nadzoru Finansowego i europejskich regulatorów.", y=950, sec=10)
        self.assertEqual(state(CLEAN + [heading, regulated], "18")[0], PREMISE)
        login = block("Bezpieczne logowanie, nadzorowany przez KNF dom maklerski.", y=950, sec=11)
        self.assertEqual(state(CLEAN + [login], "18")[0], OK)


class Readability(unittest.TestCase):
    def test_indicator_components_and_esma_standard(self):
        easy = readability("Inwestowanie wiąże się z ryzykiem. Możesz stracić część pieniędzy.")
        self.assertFalse(easy["difficult"])
        self.assertLess(easy["fog"], 9)
        esma = readability("Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków pieniężnych z powodu dźwigni finansowej.")
        self.assertTrue(esma["esmaStandard"])
        self.assertIn("dźwigni finansowej", esma["jargon"])
        self.assertIsNone(readability(""))


def capture_of(blocks, phone=None, **kwargs):
    m = material(blocks, phone, **kwargs)
    return {"id": "web:www.example-dm.pl/etf", "url": m["url"], "observedAt": m["observedAt"], "title": m["title"],
            "m2Market": {"firm": m["firm"], "kind": m["kind"], "views": m["views"], "manifestSha256": "0" * 64, "htmlSha256": "1" * 64}}


class Card(unittest.TestCase):
    def test_referral_reasons_are_plain_and_three(self):
        far = block(WARN["t"], y=2100, sec=5, px=11)
        safe = block("Twoje środki są bezpieczne, bo jesteśmy nadzorowani przez KNF.", y=800, sec=8)
        score, summary, evidence, extra = card(capture_of(replace(CLEAN, WARN, far) + [safe]))
        decision, table = extra["reviewDecision"], extra["m2Card"]
        self.assertEqual(decision["route"], "refer")
        self.assertEqual(len(decision["reasons"]), 3)
        for reason in decision["reasons"]:
            self.assertNotRegex(reason, r"\bID\b|\bK-\d|naruszen|checks|state|\b1[0-8]\b(?!\s?%)")
        self.assertTrue(decision["reasons"][0].startswith("Przesłanka do sprawdzenia"))
        self.assertEqual(len(table["rows"]), 19)
        self.assertEqual(table["firm"]["entityLabel"], "dom maklerski")
        self.assertEqual(table["viewports"], ["komputer 1440×900", "telefon 390×844"])
        self.assertGreaterEqual(score, 30)
        self.assertTrue(decision["moments"] and decision["moments"][0]["evidenceId"].startswith("m2:"))
        self.assertTrue(all(e["available"] and e["sourceUrlAtTime"] for e in evidence))
        self.assertEqual(extra["coverage"]["state"], "full")
        self.assertIn("Wynik reguł", summary)

    def test_controls_do_not_refer(self):
        _, _, _, clean = card(capture_of(CLEAN))
        self.assertEqual(clean["reviewDecision"]["route"], "no_signal")
        self.assertEqual(len(clean["reviewDecision"]["reasons"]), 3)
        education = [block("Akademia inwestora", h=1, px=36), block("Czym jest obligacja? To papier dłużny."), FOOTER_NAME]
        _, _, _, edu = card(capture_of(education, kind="education", url="https://www.example-dm.pl/edukacja"))
        self.assertEqual(edu["reviewDecision"]["route"], "no_signal")

    def test_threshold_variant(self):
        rows = evaluate(material(replace(CLEAN, WARN, block(WARN["t"], y=2100, sec=5))))
        cap = capture_of(CLEAN)
        self.assertEqual(build(cap, rows, threshold=30)[3]["reviewDecision"]["route"], "refer")
        self.assertEqual(build(cap, rows, threshold=90)[3]["reviewDecision"]["route"], "no_signal")


if __name__ == "__main__":
    unittest.main()
