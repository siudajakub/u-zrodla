#!/usr/bin/env python3
"""Sprawdzenie ścieżek pulpitu Astryx w Chromium (jeden proces, kolejno): stany, filtry, decyzja, 409, skan, alert WS.

Użycie:  /home/codexdev/.venvs/playwright/bin/python tests/ui/desk-flow.py --base http://127.0.0.1:18790 [--base2 http://127.0.0.1:18791]
Wymaga serwera deweloperskiego `node web/dev-server.mjs` (trasa /dev/* do sztucznych zdarzeń i zmian rewizji).
Drugi adres (--base2) to ten sam serwer z flagą --queues: sprawdza trasę GET /v1/queues/{name} zamiast adaptera.
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
parser.add_argument("--base2", default="")
parser.add_argument("--chromium", default="")
args = parser.parse_args()
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""), flush=True)


def get(url):
    return json.load(urllib.request.urlopen(url, timeout=5))


with sync_playwright() as p:
    binary = args.chromium or next(iter(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))), None)
    browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=["--no-sandbox"])

    def new(width=1440, height=1000):
        ctx = browser.new_context(viewport={"width": width, "height": height}, locale="pl-PL", timezone_id="Europe/Warsaw", has_touch=width < 500)
        page = ctx.new_page()
        page.set_default_timeout(8000)
        return ctx, page

    # 1. Główne wejście: licznik, skan, powód, siła ze skalą
    ctx, page = new()
    page.goto(f"{args.base}/", wait_until="networkidle")
    page.wait_for_selector("h1:has-text('Co wymaga sprawdzenia')")
    body = page.inner_text("body")
    check("wejście / otwiera Co wymaga sprawdzenia", "Co wymaga sprawdzenia" in body)
    check("liczba i skan w nagłówku", re.search(r"4 materiały z mocną przesłanką", body) and "Skan na żywo" in body)
    check("siła z opisem skali", "punkty 0–100" in body and "nie prawdopodobieństwo" in body and "100 z 100 pkt" in body)
    check("jawna współpraca nie jest w kolejce", "Kupiłem te spółki" not in body)
    check("link do dowodu w wierszu", page.get_by_role("link", name=re.compile("Dowód")).count() >= 4)
    check("brak słowa naruszenie jako werdyktu", "naruszenie" not in body.replace("prawdopodobieństwa naruszenia", "").replace("prawdopodobieństwo naruszenia", ""))

    # 2. Filtr bez wyników + adres
    page.goto(f"{args.base}/#review?module=M2", wait_until="networkidle")
    page.wait_for_selector("text=Brak materiałów dla wybranych filtrów")
    check("filtr bez wyników: komunikat i przycisk", page.get_by_role("button", name="Wyczyść filtry").count() >= 1)
    page.get_by_role("button", name="Wyczyść filtry").first.click()
    page.wait_for_timeout(300)
    check("czyszczenie filtrów usuwa je z adresu", "module=" not in page.url)

    # 3. Szczegół: otwarcie, fokus, odświeżenie
    page.goto(f"{args.base}/#review?from=2026-01-01", wait_until="networkidle")
    page.wait_for_selector("a:has-text('Ile trzeba mieć')")
    page.get_by_role("link", name=re.compile("Freedom24 Alternatywy")).first.click()
    page.wait_for_timeout(600)
    check("adres niesie case i filtr", "case=" in page.url and "from=2026-01-01" in page.url, page.url[-80:])
    check("fokus na tytule szczegółu", page.evaluate("document.activeElement && document.activeElement.tagName") == "H2")
    check("uzasadnienie: co najmniej 3 punkty", page.inner_text("[role=complementary]").count("•") >= 3)
    check("zakres analizy widoczny", "zakres analizy" in page.inner_text("[role=complementary]"))
    page.reload(wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Freedom24 Alternatywy')")
    check("odświeżenie zachowuje szczegół", True)

    # 4. Decyzja: walidacja, zapis, 409
    panel = page.locator("[role=complementary]")
    case_id = re.search(r"case=([^&]+)", page.url).group(1).replace("%3A", ":")
    revision_before = get(f"{args.base}/v1/cases/{case_id}")["revision"]
    panel.get_by_role("button", name="Zapisz decyzję").scroll_into_view_if_needed()
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_timeout(300)
    check("walidacja pustego uzasadnienia", "Wpisz uzasadnienie decyzji." in page.inner_text("body"))
    panel.get_by_label("Uzasadnienie decyzji").fill("Przekazuję do kontroli: link partnerski bez oznaczenia.")
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Decyzja została zapisana.")
    check("zapis decyzji i wpis w historii", "Decyzja analityka" in page.inner_text("body"))
    case = get(f"{args.base}/v1/cases/{case_id}")
    check("API: status reviewing, rewizja +1", case["status"] == "reviewing" and case["revision"] == revision_before + 1, str(case["revision"]))
    urllib.request.urlopen(f"{args.base}/dev/bump?id={case_id}")  # druga sesja zmienia sprawę
    panel.get_by_label("Uzasadnienie decyzji").fill("Druga decyzja po zmianie rewizji.")
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Sprawa zmieniła się podczas edycji")
    check("409: komunikat i zachowany szkic", panel.get_by_label("Uzasadnienie decyzji").input_value().startswith("Druga decyzja"))
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Decyzja została zapisana.")
    check("ponowienie po 409 zapisuje", get(f"{args.base}/v1/cases/{case_id}")["revision"] >= revision_before + 3)

    # 5. Rejestr: czas w mowie i link do sekundy
    page.goto(f"{args.base}/#register", wait_until="networkidle")
    page.wait_for_selector("text=w mowie")
    links = page.locator("a[href*='youtube.com/watch'][href*='t=']")
    check("rejestr: odsyłacz do sekundy YouTube", links.count() >= 3, links.first.get_attribute("href") if links.count() else "")
    check("rejestr: komunikat o jawnej współpracy", "Jawna współpraca nie jest uchybieniem" in page.inner_text("body"))
    page.get_by_role("button", name=re.compile("Rozwiń|Expand", re.I)).first.click()
    page.wait_for_timeout(300)
    check("rejestr: rozwinięcie wiersza", page.get_by_role("button", name="Otwórz kartę").count() >= 1)

    # 6. Źródła, skan z postępem, przyciski wyłączone
    page.goto(f"{args.base}/#sources", wait_until="networkidle")
    body = page.inner_text("body")
    check("źródła: błąd HTTP 302 z wyjaśnieniem", "przekierowanie do strony zgody" in body)
    check("źródła: droga odkrycia twórcy", "zapytanie" in body and "pozycja" in body)
    page.get_by_role("button", name="Skanuj na żywo").click()
    page.wait_for_selector("text=w toku od")
    check("skan w toku: baner z postępem", re.search(r"przejrzano \d+ z 8 źródeł", page.inner_text("body")) is not None)
    check("skan w toku: przyciski wyłączone", page.get_by_role("button", name="Skanuj na żywo").first.get_attribute("aria-disabled") == "true")

    # 7. Kalibracja i Dodaj dowód
    page.goto(f"{args.base}/#calibration", wait_until="networkidle")
    page.wait_for_selector("text=Zbiór etykiet")
    body = page.inner_text("body")
    check("kalibracja: cel etykiet, liczebność, mała próba", "cel etykiet nieopisany" in body and "Próba zbyt mała" in body and "13 przykładów" in body)
    page.goto(f"{args.base}/#evidence", wait_until="networkidle")
    check("Dodaj dowód: formularz pliku", page.get_by_text("Plik audio lub wideo").count() >= 1)

    # 8. Alert WebSocket w drugiej sesji
    ctx2, page2 = new()
    page.goto(f"{args.base}/#review", wait_until="networkidle")
    page2.goto(f"{args.base}/#sources", wait_until="networkidle")
    page.wait_for_timeout(500)
    urllib.request.urlopen(f"{args.base}/dev/alert?ref=youtube:7M0rC6-Rueo")
    page2.wait_for_selector("text=Nowy alert wysokiego ryzyka", timeout=6000)
    check("alert wysokiego ryzyka w drugiej sesji", "Ile trzeba mieć" in page2.inner_text("body"))
    page2.get_by_role("button", name="Otwórz").first.click()
    page2.wait_for_timeout(500)
    check("alert otwiera sprawę w Co wymaga sprawdzenia", "#review" in page2.url and "case=" in page2.url)
    ctx2.close()
    ctx.close()

    # 9. Stany: błąd, pusto, oczekiwanie (przechwycenie /v1/state)
    ctx, page = new()
    page.route("**/v1/state", lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail":"Baza niedostępna"}'))
    page.goto(f"{args.base}/", wait_until="networkidle")
    page.wait_for_selector("text=Nie można pobrać danych")
    body = page.inner_text("body")
    check("błąd bez danych: baner, bez pustej kolejki", "Baza niedostępna" in body and "Brak danych nie oznacza braku spraw" in body and "Brak materiałów z mocną" not in body)
    ctx.close()

    ctx, page = new()
    state = get(f"{args.base}/v1/state")
    state["findings"] = [f for f in state["findings"] if f["module"] != "M1" or f.get("reviewDecision", {}).get("route") != "refer"]
    page.route("**/v1/state", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(state)))
    page.goto(f"{args.base}/", wait_until="networkidle")
    page.wait_for_selector("text=Brak materiałów z mocną przesłanką")
    body = page.inner_text("body")
    check("pusta kolejka: to nie jest błąd, linki do rejestru", "To nie jest błąd" in body and "Rejestrze reklam" in body)
    ctx.close()

    ctx, page = new()
    holder = {}

    def slow(route):
        holder["seen"] = True
        import time
        time.sleep(1.5)
        route.continue_()

    page.route("**/v1/state", slow)
    page.goto(f"{args.base}/", wait_until="commit")
    page.wait_for_selector("text=Pobieranie danych…", timeout=3000)
    check("oczekiwanie: Pobieranie danych, bez zer w licznikach", "0" not in page.inner_text("[role=tablist]") if page.locator("[role=tablist]").count() else True)
    ctx.close()

    # 10. Telefon: lista, szczegół, powrót z filtrami, brak poziomego przewijania
    ctx, page = new(390, 844)
    page.goto(f"{args.base}/#review?from=2026-01-01", wait_until="networkidle")
    page.wait_for_selector("text=Ile trzeba mieć")
    check("telefon: brak poziomego przewijania", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), str(page.evaluate("document.documentElement.scrollWidth")))
    page.get_by_role("link", name=re.compile("Ile trzeba mieć")).first.click()
    page.wait_for_selector("h2:has-text('Ile trzeba mieć')")
    check("telefon: szczegół z Wróć do listy", page.get_by_role("button", name="Wróć do listy").count() == 1)
    page.get_by_role("button", name="Wróć do listy").click()
    page.wait_for_timeout(500)
    check("telefon: powrót zachowuje filtr", "from=2026-01-01" in page.url and "case=" not in page.url)
    check("telefon: fokus wraca do wiersza", page.evaluate("(document.activeElement.textContent||'').includes('Ile trzeba mieć')"))
    ctx.close()

    # 11. Trasa kolejek API zamiast adaptera
    if args.base2:
        ctx, page = new()
        page.goto(f"{args.base2}/#review", wait_until="networkidle")
        page.wait_for_selector("h1:has-text('Co wymaga sprawdzenia')")
        body = page.inner_text("body")
        check("GET /v1/queues/{name} zamiast adaptera", "lista zbudowana w przeglądarce" not in body and "4 materiały z mocną" in body)
        ctx.close()
    browser.close()

print(f"{sum(results)}/{len(results)} sprawdzeń OK")
sys.exit(0 if all(results) else 1)
