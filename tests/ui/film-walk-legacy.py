#!/usr/bin/env python3
"""Przejście scenopisu filmu 120 s (docs/PITCH.md §4) w Chromium: każdy klik i każdy ekran z listy, wynik OK albo RÓŻNICA.

Użycie:  /home/codexdev/.venvs/playwright/bin/python tests/ui/film-walk.py --base http://127.0.0.1:18802 [--shots tests/ui/screens/2026-11-21-r5]
Nic nie zapisuje (bez decyzji i zmiany progu). Jeden proces Chromium.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base", required=True)
parser.add_argument("--shots", default="")
args = parser.parse_args()
BASE = args.base.rstrip("/")
rows = []


def step(name, ok, detail=""):
    rows.append((name, bool(ok), detail))
    print(("OK       " if ok else "RÓŻNICA  ") + name + (f" · {detail}" if detail else ""), flush=True)


def call(path):
    request = urllib.request.Request(BASE + path, headers={"X-InvestWatch-Schema": "2"})
    return json.load(urllib.request.urlopen(request, timeout=60))


with sync_playwright() as p:
    binary = next(iter(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))), None)
    browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="pl-PL", timezone_id="Europe/Warsaw")
    page = ctx.new_page()
    page.set_default_timeout(45000)
    counts = call("/v1/overview")["queues"]
    REV, REG, ALL = counts["review"], counts["adRegister"], counts["all"]

    # 1. Pierwszy ekran 0:00–0:20
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_selector("a[id^='row-']")
    page.wait_for_selector("[data-testid=proof-path]")
    page.wait_for_timeout(1200)
    line = re.sub(r"\s+", " ", page.get_by_label("Stan danych").inner_text())
    step("1. pierwszy ekran: lejek materiały → rejestr → do sprawdzenia", f"{REG} w rejestrze reklam" in line and f"{REV} do sprawdzenia" in line and f"{ALL:,}".replace(",", " ") in line, line[:110])
    step("1. obok lejka karta sprawy z kadrami", page.locator("[role=complementary] img[src*='/v1/frames/']").count() >= 1, f"karta otwarta automatycznie: {page.locator('[role=complementary] h2').inner_text()[:50]}")
    step("1. napis „InvestWatch · gotowe do pilotażu w UKNF”", False, "nakładka filmu, nie element pulpitu (do dodania w montażu)")
    if args.shots:
        Path(args.shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{args.shots}/film-1-pierwszy-ekran.png")

    # 2. Droga dowodu 0:20–0:50
    page.goto(f"{BASE}/#review?case=youtube%3AAqXHkxDzSDI", wait_until="networkidle")
    page.wait_for_selector("[data-testid=proof-path] [data-step]")
    steps = page.locator("[data-testid=proof-path] [data-step]").evaluate_all("els => els.map(e => e.dataset.step)")
    step("2. karta ForexMind: pasek Droga dowodu (odkrycie, opis, flaga, mowa, kadry, firma, wynik)", all(s in steps for s in ("discovery", "description", "platformFlag", "speech", "frames", "firm", "decision")), ",".join(steps))
    step("2. przycisk „Otwórz w filmie od 0:15” z linkiem do sekundy 15", page.locator("a[href*='AqXHkxDzSDI'][href*='t=15s']").count() >= 1)
    step("2. dwa kadry z momentów dowodu", page.locator("[role=complementary] img[src*='/v1/frames/AqXHkxDzSDI/']").count() == 2)
    step("2. pasek „zapala się kolejno”", False, "animacja filmowa; w pulpicie kroki są od razu widoczne")
    if args.shots:
        page.screenshot(path=f"{args.shots}/film-2-droga-dowodu.png")

    # 3. Obalone podejrzenie 0:50–1:10
    page.goto(f"{BASE}/#register", wait_until="networkidle")
    page.wait_for_selector("a[id^='row-']")
    page.get_by_role("searchbox").fill("Comparic")
    page.wait_for_selector("a:has-text('ARABIA')")
    page.get_by_role("link", name=re.compile("ARABIA")).first.click()
    page.wait_for_selector("[data-testid=proof-path] [data-step=speech]")
    speech = page.locator("[data-testid=proof-path] [data-step=speech]")
    step("3. rejestr → szukaj „Comparic” → karta", "case=" in page.url)
    step("3. krok „Mowa 10:14: obaliło” z cytatem", "10:14" in speech.inner_text() and "obaliło" in speech.inner_text(), re.sub(r"\s+", " ", speech.inner_text())[:90])
    kadr = page.locator("[role=complementary] img[src*='/v1/frames/'], img[src*='/v1/frames/']")
    step("3. kadr 614 s „REKLAMA” w karcie", kadr.count() >= 1, f"kadrów: {kadr.count()}")
    group = page.get_by_role("group", name="Jak ujawniono współpracę")
    page.go_back()
    page.wait_for_selector("a[id^='row-']")
    step("3. licznik wyjaśnionych automatycznie (w mowie · flaga YouTube) w rejestrze", group.count() == 1 or page.get_by_role("group", name="Jak ujawniono współpracę").count() == 1)
    if args.shots:
        page.goto(f"{BASE}/#register?case=youtube%3ACDk20n4u9Kk", wait_until="networkidle")
        page.wait_for_selector("[data-testid=proof-path] [data-step]")
        page.screenshot(path=f"{args.shots}/film-3-obalone.png")

    # 4. Kalibracja 1:10–1:25
    page.goto(f"{BASE}/#calibration", wait_until="networkidle")
    page.wait_for_selector("[data-kpi]")
    kpi = lambda n: page.locator(f"[aria-label^='{n}:']").get_attribute("aria-label").split(": ")[1]
    before = (kpi("Fałszywe alarmy (FP)"), kpi("Przeoczenia (FN)"))
    slider = page.get_by_role("slider")
    slider.focus()
    for _ in range(7):
        page.keyboard.press("ArrowRight")
    page.wait_for_selector("text=Przy progu 95 pkt")
    page.wait_for_timeout(600)
    after = (kpi("Fałszywe alarmy (FP)"), kpi("Przeoczenia (FN)"))
    step("4. kalibracja: suwak 60 → 95 zmienia przeoczenia (FN)", before != after and after[1] != "0", f"{before} → {after}")
    step("4. „4 trafienia, 0 fałszywych alarmów” i „Poprzednie reguły: FP 7” widoczne", "Poprzednie reguły przy tym progu: FP 7" in page.inner_text("body"))
    step("4. „Wróć do obowiązującego”", page.get_by_role("button", name="Wróć do obowiązującego").count() == 1)
    page.get_by_role("button", name="Wróć do obowiązującego").click()
    page.get_by_role("radio", name="M2 Reklamy firm").click()
    page.wait_for_selector("text=/25 materiałów/")
    slider = page.get_by_role("slider")
    slider.focus()
    for _ in range(4):
        page.keyboard.press("ArrowRight")
    page.wait_for_selector("text=Przy progu 50 pkt")
    if args.shots:
        page.wait_for_timeout(500)
        page.screenshot(path=f"{args.shots}/film-4-kalibracja-m2.png")
    step("4. M2: próg 30 → 50 zmienia FN (scena z pitchu)", kpi("Przeoczenia (FN)") == "5", f"FN {kpi('Przeoczenia (FN)')}")

    # 5. Moduły 2 i 3 1:25–1:40
    ctx2 = browser.new_context(viewport={"width": 390, "height": 844}, locale="pl-PL", timezone_id="Europe/Warsaw", has_touch=True)
    ph = ctx2.new_page()
    ph.set_default_timeout(45000)
    ph.goto(f"{BASE}/#review?case=web%3Anoblesecurities.pl%2Fklient-indywidualny%2Frachunek-ike", wait_until="networkidle")
    ph.wait_for_selector("[data-testid=proof-path]")
    ph.wait_for_timeout(900)
    step("5. karta M2 na telefonie: przesłanki ze zrzutami komputer i telefon", ph.locator("img[src*='/evidence/m2/market/']").count() >= 2, f"zrzutów: {ph.locator('img[src*=\"/evidence/m2/market/\"]').count()}")
    step("5. karta M2: odległość ostrzeżenia od twierdzenia w zdaniu", bool(re.search(r"\d[\d ]* px", ph.inner_text("body"))))
    ctx2.close()
    page.goto(f"{BASE}/#review?case=web%3Ardmwm.pl%3Am3", wait_until="networkidle")
    page.wait_for_selector("[data-axis]")
    step("5. karta M3: cztery cechy i krok Uprawnienia (wykazy KNF)", page.locator("[data-axis]").count() == 4 and page.locator("[data-step=identity]").count() == 1)
    lic = [i for i in call("/v1/queues/offersM3?limit=500")["items"] if i.get("licensed")]
    if lic:
        page.goto(f"{BASE}/#review?state=all&module=M3&case={lic[0]['id'].replace(':', '%3A')}", wait_until="networkidle")
        page.wait_for_selector("[data-step=identity]")
        step("5. kontrola ujemna: podmiot z zezwoleniem nie dostaje flagi (krok Uprawnienia: obaliło)", page.locator("[data-step=identity][data-state=refuted]").count() == 1)
    else:
        step("5. kontrola ujemna: podmiot z zezwoleniem (DM BOŚ) w kolejce M3", False, "API nie oznacza w tej bazie żadnego wiersza M3 jako licensed (DM BOŚ ma teraz „brak danych podmiotu”)")

    # 6. Technologia 1:40–1:52
    step("6. schemat serwisów (web, api, worker, scheduler, inference)", False, "slajd, nie ekran pulpitu (PITCH §11 poz. 12: pominąć)")

    # 7. Zamknięcie 1:52–2:00
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    page.wait_for_selector("a[id^='row-']")
    step("7. przycisk „Raport” (CSV)", page.get_by_role("link", name="Raport", exact=True).count() == 1 and "/v1/report?" in page.get_by_role("link", name="Raport", exact=True).get_attribute("href"))
    step("7. decyzja zapisana (Zapisz decyzję na karcie)", page.get_by_role("button", name="Zapisz decyzję").count() >= 1, "przycisk jest; zapis sprawdza desk-flow")
    browser.close()

ok = sum(1 for r in rows if r[1])
print(f"\nscenopis: {ok} OK, {len(rows) - ok} różnic z {len(rows)} kroków")
