#!/usr/bin/env python3
"""Ścieżki pulpitu Astryx w Chromium (jeden proces, kolejno) na prawdziwym API schematu 2.

Użycie:
  /home/codexdev/.venvs/playwright/bin/python tests/ui/desk-flow.py --base http://127.0.0.1:18802 [--dev http://127.0.0.1:18791]
--base: własna instancja API na KOPII bazy (test zapisuje decyzje, próg i przywraca je; nigdy nie wskazuj działającego podglądu).
--dev: opcjonalnie `node web/dev-server.mjs --port 18791` (alert WebSocket high_risk i stan „starsze API” z --legacy na --legacy-base).
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
parser.add_argument("--dev", default="")
parser.add_argument("--legacy-base", default="")
parser.add_argument("--chromium", default="")
args = parser.parse_args()
BASE = args.base.rstrip("/")
results = []
console = []
failed = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""), flush=True)


def call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"X-InvestWatch-Schema": "2", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(request, timeout=30))


def case(cid):
    return call(f"{BASE}/v1/cases/{cid}")


with sync_playwright() as p:
    binary = args.chromium or next(iter(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))), None)
    browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=["--no-sandbox"])

    def new(width=1440, height=1000):
        ctx = browser.new_context(viewport={"width": width, "height": height}, locale="pl-PL", timezone_id="Europe/Warsaw", has_touch=width < 500)
        page = ctx.new_page()
        page.set_default_timeout(20000)
        page.on("console", lambda m: console.append((m.type, m.text)) if m.type == "error" and "favicon" not in m.text else None)
        page.on("pageerror", lambda e: console.append(("pageerror", str(e))))
        page.on("response", lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None)
        return ctx, page

    def ready(page, text="Co wymaga sprawdzenia"):
        page.wait_for_selector(f"h1:has-text('{text}')")
        page.wait_for_timeout(900)

    # 1. Wejście: nagłówek kolejki
    ctx, page = new()
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(f"{BASE}/", wait_until="networkidle")
    ready(page)
    page.wait_for_selector("a:has-text('Ile trzeba mieć')")
    body = page.inner_text("body")
    check("licznik 4 i jedna linia różnicy", re.search(r"Co wymaga sprawdzenia\s*4", body) and "Poprawna współpraca trafia do rejestru" in body)
    check("skan: tryb, data i liczba materiałów", "odtworzenie skanu z 21 XI" in body and "1313 materiałów" in body)
    check("aktywny wariant reguł i od kiedy", "kwalifikacja D" in body and re.search(r"od 21 XI \d\d:\d\d", body))
    page.wait_for_selector("text=czeka na transkrypcję")
    check("ile czeka na transkrypcję, link do Niepełnych danych", page.get_by_role("link", name=re.compile("czeka na transkrypcję")).count() == 1)
    check("cztery wiersze kolejki", page.locator("a[id^='row-']").count() == 4)
    check("siła i dowód w wierszu", "100 z 100 pkt" in body and page.get_by_role("link", name=re.compile(r"od \d+:\d\d|opis")).count() >= 4)
    check("liczniki z API (rejestr 264, niepełne 208)", "264" in body and "208" in body)
    check("brak słowa naruszenie jako werdyktu", "naruszenie" not in body.replace("prawdopodobieństwo naruszenia", "").replace("prawdopodobieństwa naruszenia", ""))
    check("brak „(znaki” i kodów reguł w widoku", "(znaki" not in body and "U1" not in body)
    full_state = [u for u in requests if "/v1/state" in u]
    check("jednorazowy odczyt /v1/state?compact=1, kolejki z /v1/queues", len(full_state) == 1 and "compact=1" in full_state[0] and any("/v1/queues/review" in u for u in requests), str(full_state))

    # 2. Karta: kafelki, momenty, kadry
    page.get_by_role("link", name=re.compile("Freedom24 Alternatywy")).first.click()
    page.wait_for_selector("h2:has-text('Freedom24 Alternatywy')")
    page.wait_for_timeout(700)
    panel = page.locator("[role=complementary]")
    text = panel.inner_text()
    for part in ("Dlaczego tutaj", "Momenty do sprawdzenia", "Co zbadano", "Firma", "Twórca i zasięg", "Decyzja"):
        check(f"kafel: {part}", part in text)
    check("pasek nagłówka: siła i przyciski", "Siła: mocna · 95/100" in text and page.get_by_role("link", name="Otwórz w filmie od 0:15").count() + page.get_by_role("button", name="Otwórz w filmie od 0:15").count() >= 1)
    check("najwyżej 3 punkty, reszta pod „Pokaż wszystkie”", text.count("•") == 3 and "Pokaż wszystkie (4)" in text)
    check("moment 0:15 z linkiem do sekundy", panel.locator("a[href*='AqXHkxDzSDI'][href*='t=15s']").count() >= 1)
    thumbs = panel.locator("img[src*='/v1/frames/AqXHkxDzSDI/']")
    check("dwie miniatury kadrów z API", thumbs.count() == 2 and all(thumbs.nth(i).evaluate("e => e.complete && e.naturalWidth > 0") for i in range(thumbs.count())))
    check("podpis: tekst z obrazu nieodczytywany", "Tekst z obrazu nie jest odczytywany automatycznie" in text)
    check("co zbadano: opis, mowa 0:00–3:24, kadry", "0:00–3:24" in text and "2 kadry" in text and "Oznaczenie YouTube" in text)
    check("firma: XTB, 2 wpisy w wykazie", "XTB" in text and "2 wpisy" in text)
    check("zasięg z datą i droga odkrycia", "22 wyświetleń" in text and "Freedom24" in text and "pozycja 5" in text)
    check("sekcje „Więcej” zamknięte", page.get_by_text("Historia", exact=True).count() == 0 or not page.get_by_text("Historia", exact=True).first.is_visible())
    page.get_by_text("Więcej: historia, punktacja, źródło, surowe dane").click()
    page.get_by_role("tab", name="Punktacja").click()
    page.wait_for_timeout(300)
    check("„Więcej”: składniki punktacji", "przeszukano pełną transkrypcję" in panel.inner_text())

    # 3. Klawiatura: Tab → Enter → Escape, fokus wraca do wiersza
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    ready(page)
    page.wait_for_selector("a:has-text('Ile trzeba mieć')")
    for _ in range(30):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.id.startsWith('row-')"):
            break
    focused = page.evaluate("document.activeElement.id")
    check("Tab dochodzi do pierwszego wiersza listy", focused.startswith("row-"), focused)
    outline = page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle + '|' + s.outlineWidth; })()")
    check("widoczny fokus (obrys)", outline.startswith("solid") and outline.split("|")[1] not in ("0px", ""), outline)
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    row_id = page.evaluate("document.activeElement.id")
    page.keyboard.press("Enter")
    page.wait_for_selector("h2")
    page.wait_for_timeout(500)
    check("Enter otwiera kartę, fokus na tytule", page.evaluate("document.activeElement.tagName") == "H2" and "case=" in page.url)
    page.keyboard.press("Tab")
    check("Tab idzie dalej po karcie", page.evaluate("document.activeElement.tagName") != "BODY")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    check("Escape zamyka kartę i wraca do wiersza", "case=" not in page.url and page.evaluate("document.activeElement.id") == row_id, page.evaluate("document.activeElement.id"))

    # 4. Filtry (po stronie API) i adres
    page.goto(f"{BASE}/#review?q=Freedom24", wait_until="networkidle")
    ready(page)
    page.wait_for_selector("text=Pokazano 1 z 1")
    check("filtr tekstu: jeden wiersz", page.locator("a[id^='row-']").count() == 1 and "Pokazano 1 z 1" in page.inner_text("body"))
    page.goto(f"{BASE}/#review?module=M2", wait_until="networkidle")
    page.wait_for_selector("text=Brak materiałów dla wybranych filtrów")
    check("filtr bez wyników: komunikat i przycisk", page.get_by_role("button", name="Wyczyść filtry").count() >= 1)
    page.get_by_role("button", name="Wyczyść filtry").first.click()
    page.wait_for_timeout(500)
    check("czyszczenie filtrów usuwa je z adresu", "module=" not in page.url)

    # 5. Rejestr: stronicowanie, typ ujawnienia
    sizes = []
    page.on("request", lambda r: sizes.append(r.url) if "/v1/queues/adRegister" in r.url else None)
    page.goto(f"{BASE}/#register", wait_until="networkidle")
    ready(page, "Rejestr reklam")
    page.wait_for_selector("text=Pokazano 50 z 264")
    check("rejestr: pierwsza strona 50 z 264, nie wszystkie", page.locator("a[id^='row-']").count() == 50)
    page.get_by_role("button", name="Pokaż więcej").click()
    page.wait_for_selector("text=Pokazano 100 z 264")
    check("rejestr: kolejna strona przez kursor", any("cursor=50" in u for u in sizes) and page.locator("a[id^='row-']").count() == 100)
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    check("rejestr: typ ujawnienia i zdanie z API", ("flaga płatnej promocji YouTube" in body or "w mowie" in body) and "w opisie" in body)
    check("rejestr: odsyłacz do sekundy", page.locator("a[href*='youtube.com/watch'][href*='t=']").count() >= 1)
    check("rejestr: komunikat o jawnej współpracy", "Jawna współpraca nie jest uchybieniem" in body)

    # 6. Niepełne dane
    page.goto(f"{BASE}/#incomplete", wait_until="networkidle")
    ready(page, "Niepełne dane")
    page.wait_for_selector("text=Pokazano 50 z 208")
    check("niepełne: 208 z paginacją i liczba czekających", "czeka na transkrypcję" in page.inner_text("body"))

    # 7. Źródła i trend
    page.goto(f"{BASE}/#sources", wait_until="networkidle")
    ready(page, "Źródła")
    body = page.inner_text("body")
    check("źródła: kafel na źródło ze stanem i kwotą", "Stan źródeł (6)" in body and "Kwota" in body and "27 z 60" in body and "Następny krok" in body)
    check("źródła: podsumowanie stanu", "Wszystkie źródła działają" in body)
    check("źródła: kroki skanu", "Krok skanu" in body and "Analiza i kwalifikacja" in body)
    check("źródła: trend", "Trend skanów" in body and "Do sprawdzenia" in body)
    check("źródła: droga odkrycia twórcy", "zapytanie" in body and "pozycja" in body)

    # 8. Decyzje na kopii: rodzaj, walidacja, zapis, 409, zamknięcie
    page.goto(f"{BASE}/#review?case=youtube%3AAqXHkxDzSDI", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Freedom24')")
    panel = page.locator("[role=complementary]")
    before = case("youtube:AqXHkxDzSDI")["revision"]
    panel.get_by_role("button", name="Zapisz decyzję").scroll_into_view_if_needed()
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_timeout(300)
    check("walidacja: brak rodzaju decyzji", "Wybierz rodzaj decyzji." in page.inner_text("body"))
    panel.get_by_role("button", name="Przekaż do kontroli").click()
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_timeout(300)
    check("walidacja: pusty tekst uzasadnienia", "Wpisz uzasadnienie decyzji." in page.inner_text("body"))
    panel.get_by_label("Uzasadnienie decyzji").fill("Link partnerski bez oznaczenia, przekazuję do kontroli.")
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Decyzja została zapisana.")
    c = case("youtube:AqXHkxDzSDI")
    check("API: resolution refer_to_control, status reviewing, rewizja +1", c["status"] == "reviewing" and c["lastDecision"].get("resolution") == "refer_to_control" and c["revision"] == before + 1, json.dumps(c["lastDecision"], ensure_ascii=False)[:120])
    check("karta: ostatnia decyzja w jednym wierszu", "Ostatnia: Przekaż do kontroli" in page.locator("[role=complementary]").inner_text())
    # druga sesja zapisuje decyzję; ta karta (odświeżona zdarzeniem) zostaje celowo z nieaktualną rewizją przez podmianę pola w żądaniu
    call(f"{BASE}/v1/cases/youtube:AqXHkxDzSDI", "PATCH", {"resolution": "complete_data", "note": "Druga sesja.", "expectedRevision": c["revision"]})
    stale = {"on": True}

    def make_stale(route):
        request = route.request
        if request.method == "PATCH" and stale["on"]:
            body = json.loads(request.post_data)
            body["expectedRevision"] = c["revision"]
            return route.continue_(post_data=json.dumps(body))
        return route.continue_()

    page.route("**/v1/cases/**", make_stale)
    panel.get_by_role("button", name="Uzupełnij dane").click()
    panel.get_by_label("Uzasadnienie decyzji").fill("Decyzja po zmianie rewizji.")
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Sprawa zmieniła się podczas edycji")
    stale["on"] = False
    check("409: komunikat i zachowany szkic", panel.get_by_label("Uzasadnienie decyzji").input_value().startswith("Decyzja po zmianie"))
    panel.get_by_role("button", name="Uzupełnij dane").click()
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Decyzja została zapisana.")
    check("ponowienie po 409 zapisuje", case("youtube:AqXHkxDzSDI")["revision"] >= before + 3)
    page.goto(f"{BASE}/#review?case=youtube%3AOIyPE0z2mng", wait_until="networkidle")
    page.wait_for_selector("[role=complementary] h2")
    panel = page.locator("[role=complementary]")
    panel.get_by_role("button", name="Zamknij", exact=True).click()
    panel.get_by_label("Uzasadnienie decyzji").fill("Po przejrzeniu: zwykły polecający link, zamykam.")
    panel.get_by_role("button", name="Zapisz decyzję").click()
    page.wait_for_selector("text=Decyzja została zapisana.")
    page.wait_for_timeout(1500)
    counts = call(f"{BASE}/v1/queues/review?limit=1")["counts"]
    check("zamknięcie przenosi sprawę do Zamkniętych (review 3, closed 1)", counts["review"] == 3 and counts["closed"] == 1, json.dumps(counts))
    check("karta odświeżona po zapisie", page.locator("[role=complementary]").count() >= 1)

    # 9. Kalibracja: wariant z historią, próg z przywracaniem
    page.goto(f"{BASE}/#calibration", wait_until="networkidle")
    ready(page, "Kalibracja")
    page.wait_for_selector("text=Pomiar przy progu")
    body = page.inner_text("body")
    check("kalibracja: zastrzeżenie o ocenach agentów", "Oceny agentów, nie walidacja ekspercka" in body)
    check("kalibracja: wariant, odnośnik do pomiaru, cel i liczebność", "kwalifikacja D" in body and "WYNIK-M1-2026-11-21.md" in body and "Cel etykiety" in body and re.search(r"\d+ przykładów", body))
    page.get_by_text("Historia wariantu (2)").click()
    check("kalibracja: historia wariantu z przywracaniem", page.get_by_role("button", name="Przywróć").count() >= 1)
    page.get_by_text("Historia progu (1)").click()
    slider = page.get_by_role("slider")
    slider.focus()
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    page.wait_for_selector("text=Zastosuj 65 pkt")
    page.get_by_role("button", name="Zastosuj 65 pkt").click()
    page.get_by_role("button", name="Potwierdź zmianę progu").click()
    page.wait_for_selector("text=Próg ustawiony na 65 pkt.")
    check("API: próg 65 zapisany", call(f"{BASE}/v1/threshold")["value"] == 65)
    page.wait_for_timeout(1200)
    page.get_by_text(re.compile(r"Historia progu \(\d\)")).click() if page.get_by_role("button", name="Przywróć").count() == 0 else None
    page.get_by_role("button", name="Przywróć").last.click()
    page.wait_for_selector("text=Przywrócono próg 60 pkt.")
    check("API: przywrócony próg 60 (nowy wpis w historii)", call(f"{BASE}/v1/threshold")["value"] == 60 and len(call(f"{BASE}/v1/threshold/history")["items"]) >= 3)

    # 10. Dodaj dowód
    page.goto(f"{BASE}/#evidence", wait_until="networkidle")
    check("Dodaj dowód: formularz pliku", page.get_by_text("Plik audio lub wideo").count() >= 1)
    ctx.close()

    # 11. Telefon: lista, karta jako osobny ekran, pasek, powrót z filtrem, brak poziomego przewijania
    ctx, page = new(390, 844)
    page.goto(f"{BASE}/#review?from=2026-01-01", wait_until="networkidle")
    page.wait_for_selector("text=Ile trzeba mieć")
    check("telefon: brak poziomego przewijania", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), str(page.evaluate("document.documentElement.scrollWidth")))
    page.get_by_role("link", name=re.compile("Ile trzeba mieć")).first.click()
    page.wait_for_selector("h2:has-text('Ile trzeba mieć')")
    page.wait_for_timeout(600)
    check("telefon: karta z Wróć do listy i paskiem Momenty · Decyzja", page.get_by_role("button", name="Wróć do listy").count() == 1 and page.get_by_role("button", name="Momenty", exact=True).count() == 1 and page.get_by_role("button", name="Decyzja", exact=True).count() >= 1)
    check("telefon: karta bez poziomego przewijania", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    page.get_by_role("button", name="Decyzja", exact=True).last.click()
    page.wait_for_timeout(700)
    check("telefon: pasek przewija do decyzji", page.get_by_role("button", name="Zapisz decyzję").is_visible())
    page.get_by_role("button", name="Wróć do listy").click()
    page.wait_for_timeout(500)
    check("telefon: powrót zachowuje filtr", "from=2026-01-01" in page.url and "case=" not in page.url)
    ctx.close()

    # 12. Błąd i starsze API (przechwycenie tras)
    console_before = list(console)
    failed_real = list(failed)
    ctx, page = new()
    page.route("**/v1/state**", lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail":"Baza niedostępna"}'))
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_selector("text=Nie można pobrać danych")
    body = page.inner_text("body")
    check("błąd bez danych: baner, bez pustej kolejki", "Baza niedostępna" in body and "Brak danych nie oznacza braku spraw" in body and "Brak materiałów z mocną" not in body)
    ctx.close()
    ctx, page = new()
    page.route("**/v1/queues/**", lambda route: route.fulfill(status=404, content_type="application/json", body='{"detail":"Not Found"}'))
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_selector("text=Starsze API")
    check("404 kolejek: stan „starsze API”", "Starsze API: brak kolejek" in page.inner_text("body"))
    ctx.close()

    # 13. Dev-server: alert WebSocket w drugiej sesji
    if args.dev:
        dev = args.dev.rstrip("/")
        ctx, page = new()
        ctx2, page2 = new()
        page.goto(f"{dev}/#review", wait_until="networkidle")
        page2.goto(f"{dev}/#sources", wait_until="networkidle")
        page.wait_for_timeout(1200)
        urllib.request.urlopen(f"{dev}/dev/alert?ref=youtube:7M0rC6-Rueo")
        page2.wait_for_selector("text=Nowy alert wysokiego ryzyka", timeout=8000)
        check("alert wysokiego ryzyka w drugiej sesji", "Ile trzeba mieć" in page2.inner_text("body"))
        page2.get_by_role("button", name="Otwórz").first.click()
        page2.wait_for_timeout(800)
        check("alert otwiera sprawę w Co wymaga sprawdzenia", "#review" in page2.url and "case=" in page2.url)
        ctx2.close()
        ctx.close()
    if args.legacy_base:
        ctx, page = new()
        page.goto(f"{args.legacy_base.rstrip('/')}/#review", wait_until="networkidle")
        page.wait_for_selector("text=Starsze API")
        check("dev-server --legacy: stan „starsze API”", True)
        ctx.close()
    browser.close()

unexpected = [f for f in failed_real if f[0] != 409]
check("odpowiedzi 4xx tylko celowy 409 (konflikt rewizji)", not [f for f in unexpected if "18802" in f[1]], json.dumps(unexpected[:6]))
check("konsola przeglądarki bez błędów (poza celowym 409)", not [c for c in console_before if "409" not in c[1]], json.dumps(console_before, ensure_ascii=False)[:500])
print(f"{sum(results)}/{len(results)} sprawdzeń OK")
sys.exit(0 if all(results) else 1)
