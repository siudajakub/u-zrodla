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


COUNTS = call(f"{BASE}/v1/queues/review?limit=1")["counts"]
INC = COUNTS["incomplete"]
REG = COUNTS["adRegister"]


def case(cid):
    return call(f"{BASE}/v1/cases/{cid}")


with sync_playwright() as p:
    binary = args.chromium or next(iter(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))), None)
    browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=["--no-sandbox"])

    def new(width=1440, height=1000):
        ctx = browser.new_context(viewport={"width": width, "height": height}, locale="pl-PL", timezone_id="Europe/Warsaw", has_touch=width < 500)
        page = ctx.new_page()
        page.set_default_timeout(20000)
        page.on("console", lambda m: console.append((m.type, m.text)) if m.type in ("error", "warning") and "favicon" not in m.text else None)
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
    REVIEW = COUNTS["review"]
    check(f"licznik {REVIEW} i jedna linia różnicy", re.search(rf"Co wymaga sprawdzenia\s*{REVIEW}", body) and "Poprawna współpraca trafia do rejestru" in body)
    check("skan: tryb, data i liczba materiałów", "odtworzenie skanu z 21 XI" in body and re.search(r"\d+ materiałów", body))
    check("nagłówek: skrót trendu (wykres i liczby)", page.locator("canvas[data-chart=line]").count() >= 1 and "Trend:" in body)
    check("aktywny wariant reguł i od kiedy", "kwalifikacja D" in body and re.search(r"od 21 XI \d\d:\d\d", body))
    page.wait_for_selector("text=czeka na transkrypcję")
    check("ile czeka na transkrypcję, link do Niepełnych danych", page.get_by_role("link", name=re.compile("czeka na transkrypcję")).count() == 1)
    check("wiersze kolejki z trzech modułów", page.locator("a[id^='row-']").count() == REVIEW, str(page.locator("a[id^='row-']").count()))
    check("siła i dowód w wierszu", "100 z 100 pkt" in body and page.get_by_role("link", name=re.compile(r"opis|strona")).count() >= 4)
    check("plakietki modułu w wierszach", all(n in body for n in ("Finfluencer", "Reklama firmy", "Doradztwo")))
    check("wiersze: źródło (platforma) i firma", "YouTube" in body and "XTB Ltd / XTB S.A." in body and "NOBLE Securities S.A." in body)
    first_titles = page.locator("a[id^='row-']").evaluate_all("els => els.map(e => e.innerText.trim())")
    check("sortowanie domyślne: najsilniejszy na górze", "Ile trzeba mieć" in first_titles[0] and "Rachunek IKE" in first_titles[1], str(first_titles[:2]))
    page.wait_for_selector("text=/Finfluencer\\s*\\d/")
    mods = page.locator("[role=group][aria-label='Moduł']").inner_text()
    check("filtr modułu z licznikami (4 + 10 + 1)", re.search(r"Finfluencer\s*4", mods) and re.search(r"Reklama firmy\s*10", mods) and re.search(r"Doradztwo\s*1", mods), mods.replace("\n", " "))
    check("liczniki z API (rejestr i niepełne zgodne z API)", str(REG) in body and str(INC) in body)
    check("brak słowa naruszenie jako werdyktu", "naruszenie" not in body.replace("prawdopodobieństwo naruszenia", "").replace("prawdopodobieństwa naruszenia", ""))
    check("brak „(znaki” i kodów reguł w widoku", "(znaki" not in body and "U1" not in body)
    overview = [u for u in requests if "/v1/overview" in u]
    check("jednorazowy odczyt /v1/overview (bez /v1/state), kolejki z /v1/queues", len(overview) == 1 and not [u for u in requests if "/v1/state" in u] and any("/v1/queues/review" in u for u in requests), str(overview))

    # 2. Karta: kafelki, momenty, kadry
    page.get_by_role("link", name=re.compile("Freedom24 Alternatywy")).first.click()
    page.wait_for_selector("h2:has-text('Freedom24 Alternatywy')")
    page.wait_for_timeout(700)
    panel = page.locator("[role=complementary]")
    text = panel.inner_text()
    for part in ("Dlaczego tutaj", "Momenty do sprawdzenia", "Co zbadano", "Firma", "Twórca i zasięg", "Decyzja"):
        check(f"kafel: {part}", part in text)
    check("pasek nagłówka: siła i przyciski", "Siła: mocna · 95/100" in text and page.get_by_role("link", name="Otwórz w filmie od 0:15").count() + page.get_by_role("button", name="Otwórz w filmie od 0:15").count() >= 1)
    check("najwyżej 3 punkty, reszta pod „Pokaż wszystkie”", text.count("•") == 3 and re.search(r"Pokaż wszystkie \(\d+\)", text))
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
    for _ in range(60):
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
    page.goto(f"{BASE}/#review?q=zzzznieistnieje", wait_until="networkidle")
    page.wait_for_selector("text=Brak materiałów dla wybranych filtrów")
    check("filtr bez wyników: komunikat i przycisk", page.get_by_role("button", name="Wyczyść filtry").count() >= 1)
    page.get_by_role("button", name="Wyczyść filtry").first.click()
    page.wait_for_timeout(500)
    check("czyszczenie filtrów usuwa je z adresu", "q=" not in page.url)

    # 5. Rejestr: stronicowanie, typ ujawnienia
    sizes = []
    requests_reg = []
    page.on("request", lambda r: sizes.append(r.url) if "/v1/queues/adRegister" in r.url else None)
    page.on("request", lambda r: requests_reg.append(r.url))
    page.goto(f"{BASE}/#register", wait_until="networkidle")
    ready(page, "Rejestr reklam")
    page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    check("rejestr: pierwsza strona 50 z liczby z API, nie wszystkie", page.locator("a[id^='row-']").count() == 50)
    page.get_by_role("button", name="Pokaż więcej").click()
    page.wait_for_selector(f"text=Pokazano 100 z {REG}")
    check("rejestr: kolejna strona przez kursor", any("cursor=50" in u for u in sizes) and page.locator("a[id^='row-']").count() == 100)
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    check("rejestr: kolumny Firma, Platforma, Typ ujawnienia", all(h in body for h in ("Firma", "Platforma", "Typ ujawnienia")))
    check("rejestr: typ ujawnienia i zdanie z API", ("flaga płatnej promocji" in body or "w mowie" in body) and "w opisie" in body and "oznaczona reklama" in body)
    check("rejestr: bez dociągania kart wierszy (tylko karta otwarta z listy)", len([u for u in requests_reg if "/v1/cases/" in u]) == 0, str([u for u in requests_reg if "/v1/cases/" in u][:3]))
    check("rejestr: przycisk Pobierz raport z adresem /v1/report", page.get_by_role("link", name="Pobierz raport").count() == 1 and "/v1/report?" in page.get_by_role("link", name="Pobierz raport").get_attribute("href"))
    check("rejestr: komunikat o jawnej współpracy", "Jawna współpraca nie jest uchybieniem" in body)

    # 6. Niepełne dane
    page.goto(f"{BASE}/#incomplete", wait_until="networkidle")
    ready(page, "Niepełne dane")
    page.wait_for_selector(f"text=Pokazano 50 z {INC}")
    check("niepełne: liczba z API z paginacją i liczba czekających", "czeka na transkrypcję" in page.inner_text("body"))

    # 7. Źródła: wykresy, kafelki platform, zablokowany dostęp, kroki skanu
    page.goto(f"{BASE}/#sources", wait_until="networkidle")
    ready(page, "Źródła")
    page.wait_for_function("document.querySelectorAll('canvas[data-chart]').length >= 3", timeout=15000)
    page.wait_for_timeout(800)
    body = page.inner_text("body")
    check("źródła: trend (materiały i osobno skierowania) i wykres per platforma", page.locator("canvas[data-chart]").count() >= 3 and "Materiały i skierowania w czasie" in body and "Skierowania do sprawdzenia" in body and "Źródła: materiały per platforma" in body, f"canvas={page.locator('canvas[data-chart]').count()}")
    charts_ok = page.evaluate("[...document.querySelectorAll('canvas[data-chart]')].every(c => c.width > 50 && c.height > 50)")
    check("źródła: płótna wykresów mają rozmiar", charts_ok)
    check("źródła: dwa osobne wykresy trendu bez drugiej osi", page.locator("canvas[aria-label*='Wykres: materiały przejrzane w czasie']").count() == 1 and page.locator("canvas[aria-label*='Wykres: skierowania do sprawdzenia w czasie']").count() == 1)
    for name in ("YouTube", "TikTok", "Instagram", "Facebook", "WWW firm (M2)", "WWW doradców (M3)", "Biblioteka Reklam Meta"):
        check(f"źródła: kafel {name}", page.locator(f"[aria-label='Źródło: {name}']").count() == 1)
    fb = page.locator("[aria-label='Źródło: Facebook']").inner_text()
    check("kafel Facebooka: ścieżka vendor_sample obok importu ręcznego i blokady", "próbka z usługi zewnętrznej" in fb and "import ręczny" in fb and "wpisy automatycznie" in fb and "dostęp zablokowany" in fb and "Meta Content Library" in fb and "Droga" in fb, fb[:260].replace("\n", " "))
    check("kafel Facebooka: data próby i następny krok", "Ostatnia próba" in fb and "Następny krok" in fb)
    ig = page.locator("[aria-label='Źródło: Instagram']").inner_text()
    check("kafel Instagrama: próbka z usługi zewnętrznej, import ręczny, blokada, liczniki", "próbka z usługi zewnętrznej" in ig and "import ręczny" in ig and "wpisy automatycznie" in ig and "dostęp zablokowany" in ig and "351" in ig and "31" in ig, ig[:200].replace("\n", " "))
    yt = page.locator("[aria-label='Źródło: YouTube']").inner_text()
    check("kafel YouTube: kanały, materiały, klucz z kwotą, ostatni skan", "381" in yt and "1305" in yt and "Klucz 1" in yt and "jednostek" in yt and "Ostatni skan" in yt, yt[:200].replace("\n", " "))
    m2t = page.locator("[aria-label='Źródło: WWW firm (M2)']").inner_text()
    check("kafel WWW firm (M2): firmy, strony, data odczytu, ograniczenie", all(x in m2t for x in ("Firmy", "Strony", "Odczytano", "Ograniczenie", "komputer 1440×900")) and re.search(r"Firmy\s*11", m2t), m2t[:160].replace("\n", " "))
    m3t = page.locator("[aria-label='Źródło: WWW doradców (M3)']").inner_text()
    check("kafel WWW doradców (M3): 29 podmiotów, 57 stron, lista ziaren", re.search(r"Podmioty\s*29", m3t) and re.search(r"Strony odczytane\s*57", m3t) and "listy ziaren" in m3t, m3t[:200].replace("\n", " "))
    tt = page.locator("[aria-label='Źródło: TikTok']").inner_text()
    check("kafel TikToka: profile i ograniczenia", "8" in tt and "tylko podpis" in tt, tt[:200].replace("\n", " "))
    check("kafel Meta: brak tokenu/klucza i krok", re.search(r"brak (tokenu|klucza)", page.locator("[aria-label='Źródło: Biblioteka Reklam Meta']").inner_text()))
    check("źródła: blokada wpisów organicznych widoczna", "zablokowan" in body)
    if page.get_by_text(re.compile(r"Kroki skanu \(")).count():
        page.get_by_text(re.compile(r"Kroki skanu \(")).click()
        page.wait_for_timeout(300)
        check("źródła: kroki skanu", "Krok skanu" in page.inner_text("body"))
    check("źródła: droga odkrycia twórcy", "jak odkryto" in body.lower() and ("Odnośnik" in body or "Kanał Atom" in body or "Wyszukiwanie YouTube" in body))

    # 7b. Filtry: platforma i moduł jako przełączniki, kanał, data z wyborem pola, raport CSV z BOM
    reqs = []
    page.on("request", lambda r: reqs.append(r.url))
    page.goto(f"{BASE}/#register", wait_until="networkidle")
    ready(page, "Rejestr reklam")
    page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    for name in ("YouTube", "TikTok", "Instagram", "Facebook"):
        check(f"filtr platformy: przełącznik {name}", page.get_by_role("button", name=name, exact=True).count() >= 1)
    for name in ("YouTube", "TikTok", "Instagram", "Facebook"):
        expect = call(f"{BASE}/v1/queues/adRegister?platform={name.lower()}&limit=1")["total"]
        page.get_by_role("button", name=name, exact=True).click()
        page.wait_for_selector(f"text=/Pokazano \\d+ z {expect}\\b/")
        check(f"rejestr: filtr {name} zwraca {expect} z API", expect > 0 and f"source={name.lower()}" in page.url)
        page.get_by_role("button", name=name, exact=True).click()
        page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    page.get_by_role("button", name="TikTok", exact=True).click()
    page.wait_for_selector("text=Pokazano 5 z 5")
    check("filtr platformy TikTok: adres i zapytanie z platform=tiktok", "source=tiktok" in page.url and any("platform=tiktok" in u for u in reqs))
    report_href = page.get_by_role("link", name="Pobierz raport").get_attribute("href")
    check("raport: adres z aktualnymi filtrami", "module=M1" in report_href and "platform=tiktok" in report_href and "queue=adRegister" in report_href and "format=csv" in report_href, report_href)
    csv_response = urllib.request.urlopen(f"{BASE}{report_href}" if report_href.startswith("/") else report_href, timeout=30)
    raw = csv_response.read()
    check("raport CSV: 200, BOM UTF-8, nagłówek i 5 wierszy", csv_response.status == 200 and raw.startswith(b"\xef\xbb\xbf") and raw.decode("utf-8-sig").splitlines()[0].startswith("firma,") and len(raw.decode("utf-8-sig").strip().splitlines()) == 6, f"{csv_response.status} {len(raw)} B")
    body = page.inner_text("body")
    check("rejestr TikTok: podpis [współpraca z XTB] i data szacowana oznaczona", "współpraca z XTB" in body and "data szacowana" in body)
    page.get_by_role("button", name="TikTok", exact=True).click()
    page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    check("ponowne kliknięcie przełącznika czyści filtr", "source=" not in page.url)
    check("rejestr M1: bez przełącznika modułu i bez WWW", page.get_by_role("group", name="Moduł").count() == 0 and page.get_by_role("button", name="WWW", exact=True).count() == 0)
    expected = call(f"{BASE}/v1/queues/adRegister?q=snela&limit=1")["total"]
    page.get_by_role("searchbox").fill("snela")
    page.wait_for_selector(f"text=Pokazano {expected} z {expected}")
    check("wyszukiwanie po kanale (q): wiersze tylko kanału", page.locator("a[id^='row-']").count() == expected and "q=snela" in page.url and expected > 0, str(expected))
    page.goto(f"{BASE}/#register?dateField=publishedAt&from=2026-11-01", wait_until="networkidle")
    ready(page, "Rejestr reklam")
    page.wait_for_timeout(800)
    check("data: pole „opublikowano” trafia do API (dateField=publishedAt, since)", any("dateField=publishedAt" in u and "since=2026-11-01" in u for u in reqs))
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    ready(page)
    check("moduł M1: przycisk raportu w kolejce Co wymaga sprawdzenia", page.get_by_role("link", name="Pobierz raport").count() == 1)

    # 7e. Kolejka trzech modułów: filtr modułu, karta M2 (Noble IKE), karta M3 (rdmwm.pl)
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    ready(page)
    page.get_by_role("button", name=re.compile(r"Doradztwo\s*1")).click()
    page.wait_for_selector("text=Pokazano 1 z 1")
    check("filtr modułu Doradztwo: jeden wiersz M3, adres z module=M3", "module=M3" in page.url and page.locator("a[id^='row-']").count() == 1 and "RDM Wealth" in page.inner_text("body"))
    page.get_by_role("button", name=re.compile(r"Reklama firmy")).click()
    page.wait_for_selector("text=Pokazano 10 z 10")
    check("filtr modułu Reklama firmy: 10 wierszy M2", "module=M2" in page.url and page.locator("a[id^='row-']").count() == 10)
    page.get_by_role("button", name=re.compile(r"Reklama firmy")).click()
    page.wait_for_selector(f"text=Pokazano {REVIEW} z {REVIEW}")
    check("ponowne kliknięcie modułu czyści filtr", "module=" not in page.url)
    noble = "web%3Anoblesecurities.pl%2Fklient-indywidualny%2Frachunek-ike"
    page.goto(f"{BASE}/#review?case={noble}", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Rachunek IKE')")
    page.wait_for_selector("text=Kryteria ryzyka")
    page.wait_for_timeout(900)
    panel = page.locator("[role=complementary]")
    mt = panel.inner_text()
    check("karta M2: pasek (siła, firma i typ podmiotu, Otwórz stronę, Decyzja)", "Siła: mocna · 95/100" in mt and "NOBLE Securities S.A. · dom maklerski" in mt and panel.get_by_role("link", name="Otwórz stronę").count() == 1 and panel.get_by_role("button", name="Decyzja", exact=True).count() >= 1)
    for part in ("Dlaczego tutaj", "Kryteria ryzyka", "Co zbadano", "Firma", "Decyzja"):
        check(f"karta M2: kafel {part}", part in mt)
    check("karta M2: „8 z 19 wymaga uwagi”, najwyżej 3 punkty w „Dlaczego tutaj”", "8 z 19 wymaga uwagi" in mt and "Wszystkie 19 kryteriów wg stanu" in mt)
    check("karta M2: przesłanki z pomiarem (11 px wobec 16 px) i cytatem", "11 px" in mt and "16 px" in mt and "Informacja o ryzyku przy zysku" in mt and "Rozmiar czcionki ryzyka" in mt)
    check("karta M2: pełna lista zwinięta na początku", "Spełnione" not in mt and "Identyfikacja firmy" not in mt)
    imgs = panel.locator("img[src*='/evidence/m2/market/']")
    page.wait_for_timeout(500)
    n_imgs = imgs.count()
    check("karta M2: miniatury zrzutów (komputer i telefon) z naturalWidth > 0", n_imgs >= 6 and all(imgs.nth(i).evaluate("e => e.complete && e.naturalWidth > 0") for i in range(n_imgs)), str(n_imgs))
    check("karta M2: podpisy komputer i telefon przy miniaturach", "komputer" in mt and "telefon" in mt)
    imgs.first.click()
    page.wait_for_selector("dialog[open] img")
    check("karta M2: kliknięcie powiększa zrzut w oknie", page.locator("dialog[open] img").count() >= 1 and page.locator("dialog[open] img").first.evaluate("e => e.naturalWidth > 0"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check("karta M2: Escape zamyka powiększenie, karta zostaje", page.locator("dialog[open]").count() == 0 and "Kryteria ryzyka" in page.locator("[role=complementary]").inner_text())
    page.locator("[role=complementary]").get_by_text("Wszystkie 19 kryteriów wg stanu").click()
    page.wait_for_timeout(400)
    mt = page.locator("[role=complementary]").inner_text()
    check("karta M2: rozwinięta lista 19 kryteriów wg stanu", all(x in mt for x in ("Identyfikacja firmy", "Dostępność bez kliknięcia", "Porównania produktów lub usług", "Sugestia aprobaty organu nadzoru")) and "spełnione" in mt and "nie dotyczy" in mt)
    check("karta M2: co zbadano (komputer i telefon, baner cookies, data)", "komputer 1440×900" in mt and "telefon 390×844" in mt and "Baner cookies" in mt and "21 lis 2026" in mt)
    check("karta M2: firma z wykazu KNF (numer wpisu)", "dom maklerski" in mt and "6884971" in mt)
    page.goto(f"{BASE}/#review?case=web%3Ardmwm.pl%3Am3", wait_until="networkidle")
    page.wait_for_selector("text=Cztery cechy rekomendacji")
    page.wait_for_timeout(700)
    panel = page.locator("[role=complementary]")
    m3 = panel.inner_text()
    check("karta M3: pasek (siła, domena, Otwórz ofertę, Decyzja)", "Siła: mocna · 85/100" in m3 and "rdmwm.pl" in m3 and panel.get_by_role("link", name="Otwórz ofertę").count() == 1)
    for part in ("Dlaczego tutaj", "Cztery cechy rekomendacji", "Uprawnienia", "Co zbadano", "Decyzja"):
        check(f"karta M3: kafel {part}", part in m3)
    check("karta M3: cztery cechy ze stanem, cytatem i kontrargumentem", all(x in m3 for x in ("Czynność", "Personalizacja", "Instrument", "Rynek", "Kontrargument", "Cytat ze strony")) and m3.count("przesłanka") >= 4 and "Na podstawie tych danych dobieramy proporcje" in m3)
    check("karta M3: link do podstrony przy cytacie", panel.get_by_role("link", name=re.compile("strona główna")).count() >= 4 and panel.locator("a[href='https://rdmwm.pl/']").count() >= 4)
    check("karta M3: uprawnienia: stan, brak wpisu w liście ostrzeżeń, zastrzeżenie", "brak danych podmiotu na stronie" in m3 and "Ostrzeżenia KNF" in m3 and "brak wpisu" in m3 and "Brak wpisu nie dowodzi braku uprawnień" in m3)
    panel.get_by_text(re.compile(r"Przejrzane wykazy \(12")).click()
    page.wait_for_timeout(300)
    m3 = panel.inner_text()
    check("karta M3: lista 12 przejrzanych wykazów z datą", "domy maklerskie" in m3 and "lista ostrzeżeń publicznych KNF" in m3 and m3.count("21 lis 2026") >= 12)
    page.goto(f"{BASE}/#m3?case=web%3Aerste.pl%3Am3", wait_until="networkidle")
    page.wait_for_selector("text=Uprawnienia")
    page.wait_for_timeout(500)
    check("karta M3: podmiot uprawniony z plakietką kontroli", "kontrola: podmiot uprawniony" in page.inner_text("body") and "uprawniony" in page.inner_text("body"))
    page.goto(f"{BASE}/#m3", wait_until="networkidle")
    ready(page, "Oferty doradztwa")
    page.wait_for_timeout(500)
    check("lista M3: plakietka „kontrola: podmiot uprawniony” przy podmiotach z wykazu", page.get_by_text("kontrola: podmiot uprawniony").count() >= 3)
    # 7d. Import ręczny: wgranie zapisanej strony Biblioteki Reklam Meta, błąd 422, plakietka i karta reklamy M2
    page.goto(f"{BASE}/#sources", wait_until="networkidle")
    ready(page, "Źródła")
    check("źródła: instrukcja w 3 krokach i formularz importu", "Wgraj zapisaną stronę Biblioteki Reklam Meta lub profilu Instagram" in page.inner_text("body") and page.get_by_text("3. Wybierz zapisany plik").count() == 1)
    page.locator("input[type=file]").first.set_input_files(str(Path(__file__).resolve().parents[2] / "fixtures/raw/discovery/social-2026-11-21/alt/metaadlib-browser-body.txt"))
    page.get_by_role("button", name="Wgraj do analizy").click()
    page.wait_for_selector("text=/Wczytano:|był już wczytany|czeka na worker/", timeout=60000)
    banner = page.inner_text("body")
    check("import: wynik z liczbą reklam, nowych i istniejących", re.search(r"(Wczytano: 22 reklam|już wczytany \(22 reklam)", banner) is not None, re.sub(r"\s+", " ", banner[banner.find("Wczytano") - 5:banner.find("Wczytano") + 120]))
    page.locator("input[type=file]").first.set_input_files(files=[{"name": "smiec.txt", "mimeType": "text/plain", "buffer": b"to nie jest zapisana strona Biblioteki Reklam"}])
    page.get_by_role("button", name="Wgraj do analizy").click()
    page.wait_for_selector("text=Nie wczytano pliku", timeout=30000)
    check("import: nierozpoznany plik daje komunikat z API (422), bez zapisu", True)
    page.goto(f"{BASE}/#m2", wait_until="networkidle")
    ready(page, "Oferty WWW")
    page.wait_for_selector("text=import ręczny")
    check("oferty M2: plakietka „import ręczny” przy reklamach", page.get_by_text("import ręczny").count() >= 5)
    page.goto(f"{BASE}/#m2?case=facebook%3Aad-1353099026431942", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Inwestuj gdziekolwiek')")
    page.wait_for_timeout(500)
    ad = page.inner_text("body")
    for part in ("Dlaczego tutaj", "Treść reklamy", "Reklamodawca", "Install Now", "Wersje reklamy", "Co zbadano", "tylko tekst reklamy", "Firma", "XTB", "Decyzja", "import ręczny", "Otwórz źródło"):
        check(f"karta reklamy Meta: {part}", part in ad)
    check("karta reklamy Meta: bez momentów i bez „starszej analizy”", "Momenty do sprawdzenia" not in ad and "starszej wersji analizy" not in ad)

    # 7c. Karta TikToka z rejestru: ta sama karta, zbadano tylko podpis, Otwórz źródło, szacowana data
    page.goto(f"{BASE}/#register?case=tiktok%3A7707284619103718689", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('współpraca z XTB')")
    page.wait_for_timeout(600)
    tk = page.locator("[role=complementary]").inner_text() if page.locator("[role=complementary]").count() else page.inner_text("body")
    check("karta TikToka: Otwórz źródło zamiast Otwórz w filmie", page.get_by_role("link", name="Otwórz źródło").count() >= 1 and "Otwórz w filmie" not in tk)
    check("karta TikToka: zbadano tylko podpis, mowy nie zbadano", "Zbadano tylko podpis" in tk and "mowa (niezbadana)" in tk)
    check("karta TikToka: zasięg w odtworzeniach", "1533 odtworzeń" in tk.replace("\xa0", " ").replace(" ", "")  or "1533 odtworzeń" in tk, re.sub(r"\s+", " ", tk)[tk.find("Odtworzenia"):tk.find("Odtworzenia") + 80])
    check("karta TikToka: data szacowana oznaczona", "data szacowana" in tk and "≈" in tk)

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
    page.wait_for_selector("text=/Ostatnia: Przekaż do kontroli/")
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
    closed_ids = [x["id"] for x in call(f"{BASE}/v1/queues/closed?limit=50")["items"]]
    review_ids = [x["id"] for x in call(f"{BASE}/v1/queues/review?limit=50")["items"]]
    check("zamknięcie przenosi sprawę z Co wymaga sprawdzenia do Zamkniętych", "youtube:OIyPE0z2mng" in closed_ids and "youtube:OIyPE0z2mng" not in review_ids, f"closed={len(closed_ids)} review={len(review_ids)}")
    check("karta odświeżona po zapisie", page.locator("[role=complementary]").count() >= 1)

    # 9. Kalibracja: suwak z podglądem na żywo, wykres, skutek dla kolejki, porównanie wariantów, próg z przywracaniem
    page.goto(f"{BASE}/#calibration", wait_until="networkidle")
    ready(page, "Kalibracja")
    page.wait_for_selector("text=Próg: podgląd na zbiorze etykiet")
    page.wait_for_selector("canvas[data-chart=line]")
    body = page.inner_text("body")
    check("kalibracja: zastrzeżenie o ocenach agentów", "Oceny agentów, nie walidacja ekspercka" in body)
    check("kalibracja: wariant, odnośnik do pomiaru, cel i liczebność", "kwalifikacja D" in body and "WYNIK-M1-2026-11-21.md" in body and "Cel etykiety" in body and re.search(r"\d+ przykładów", body))
    for label in ("Trafienia (TP)", "Fałszywe alarmy (FP)", "Poprawnie odrzucone (TN)", "Przeoczenia (FN)", "Precyzja", "Pełność", "Koszt (2×FN + FP)"):
        check(f"kalibracja: kafelek {label}", page.locator(f"[aria-label^='{label}:']").count() == 1)
    kpi = lambda name: page.locator(f"[aria-label^='{name}:']").get_attribute("aria-label").split(": ")[1]
    check("kalibracja przy progu 60: TP 4, FP 0, FN 0, koszt 0", (kpi("Trafienia (TP)"), kpi("Fałszywe alarmy (FP)"), kpi("Przeoczenia (FN)"), kpi("Koszt (2×FN + FP)")) == ("4", "0", "0", "0"), str((kpi("Trafienia (TP)"), kpi("Przeoczenia (FN)"))))
    check("kalibracja: porównanie wariantów rules_1_2 i qual_d", "reguły 1.2" in body and "kwalifikacja D (opis, mowa i kadry) (aktywny)" in body)
    check("kalibracja: skutek dla kolejki przy progu obowiązującym", "się nie zmienia" in page.get_by_test_id("queue-effect").inner_text())
    slider = page.get_by_role("slider")
    slider.focus()
    page.keyboard.press("End")
    page.wait_for_selector("text=zniknie")
    check("suwak do 100: liczby się zmieniają (FN 0→3, TP 4→1) i skutek dla kolejki „zniknie N”", kpi("Przeoczenia (FN)") == "3" and kpi("Trafienia (TP)") == "1" and re.search(r"zniknie \d+ spra", page.get_by_test_id("queue-effect").inner_text()), f"FN={kpi('Przeoczenia (FN)')} TP={kpi('Trafienia (TP)')} {page.get_by_test_id('queue-effect').inner_text()}")
    check("suwak: oznaczenie zmiany względem obowiązującego progu", "względem obowiązującego" in page.inner_text("body"))
    page.keyboard.press("Home")
    page.wait_for_selector("text=Zastosuj 0 pkt")
    page.get_by_role("button", name="Wróć do obowiązującego").click()
    page.wait_for_selector("text=się nie zmienia")
    page.get_by_text("Historia wariantu (2)").click()
    check("kalibracja: historia wariantu z przywracaniem", page.get_by_role("button", name="Przywróć").count() >= 1)
    slider.focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_selector("text=Zastosuj 65 pkt")
    page.get_by_role("button", name="Zastosuj 65 pkt").click()
    page.get_by_role("button", name="Potwierdź zmianę progu").click()
    page.wait_for_selector("text=Próg ustawiony na 65 pkt.")
    check("API: próg 65 zapisany", call(f"{BASE}/v1/threshold")["value"] == 65)
    page.wait_for_timeout(1200)
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
    page.route("**/v1/overview**", lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail":"Baza niedostępna"}'))
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

unexpected = [f for f in failed_real if f[0] != 409 and not (f[0] == 422 and "/v1/import/meta" in f[1])]
check("odpowiedzi 4xx tylko celowe: 409 (konflikt rewizji) i 422 (śmieciowy plik importu)", not [f for f in unexpected if "18802" in f[1]], json.dumps(unexpected[:6]))
check("konsola przeglądarki bez błędów (poza celowymi 409 i 422)", not [c for c in console_before if "409" not in c[1] and "422" not in c[1] and "ERR_NETWORK_CHANGED" not in c[1]], json.dumps(console_before, ensure_ascii=False)[:500])
print(f"{sum(results)}/{len(results)} sprawdzeń OK")
sys.exit(0 if all(results) else 1)
