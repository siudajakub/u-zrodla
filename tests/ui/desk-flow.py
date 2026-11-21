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
        page.set_default_timeout(40000)
        page.on("console", lambda m: console.append((m.type, m.text)) if m.type in ("error", "warning") and "favicon" not in m.text else None)
        page.on("pageerror", lambda e: console.append(("pageerror", str(e))))
        page.on("response", lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None)
        return ctx, page

    def ready(page, text="Do sprawdzenia"):
        page.wait_for_selector(f"h1:has-text('{text}')", state="attached")
        page.wait_for_timeout(900)

    def pick(page, label, option):
        page.mouse.move(5, 5)
        page.wait_for_timeout(250)
        page.get_by_role("combobox", name=label).click()
        page.get_by_role("option", name=option, exact=True).click()
        page.wait_for_timeout(500)

    # 1. Wejście: linia stanu danych, filtry w jednym rzędzie, wiersze listy
    ctx, page = new(1440, 900)
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(f"{BASE}/", wait_until="networkidle")
    ready(page)
    page.wait_for_selector("a:has-text('Ile trzeba mieć')")
    body = page.inner_text("body")
    REVIEW = COUNTS["review"]
    tabs = page.get_by_role("tab").all_inner_texts()
    check("cztery zakładki: Do sprawdzenia, Rejestr reklam, Źródła, Kalibracja", len(tabs) == 4 and re.match(r"Do sprawdzenia\s*" + str(REVIEW), tabs[0]) and tabs[1].startswith("Rejestr reklam") and tabs[2] == "Źródła" and tabs[3] == "Kalibracja", str(tabs))
    stage = re.sub(r"\s+", " ", page.get_by_label("Stan danych").inner_text())
    ALL = COUNTS["all"]
    check("linia stanu danych: lejek materiały → rejestr → do sprawdzenia", f"{ALL:,}".replace(",", " ") in stage and f"{REG} w rejestrze reklam" in stage and f"{REVIEW} do sprawdzenia" in stage, stage)
    check("tryb: „odtworzenie skanu z 21 XI” (nie zielone „na żywo”)", "odtworzenie skanu z 21 XI" in stage and "na żywo" not in body.replace("alerty na żywo", ""), stage)
    funnel = call(f"{BASE}/v1/overview")["funnel"] if "funnel" in call(f"{BASE}/v1/overview") else None
    if funnel:
        e = funnel["explainedAutomatically"]
        total = e["bySpeech"] + e["byPlatformFlag"] + e["byFrame"]
        check("licznik „wyjaśnione automatycznie” z rozbiciem po najechaniu", f"{total} wyjaśnione automatycznie" in stage)
    else:
        print("INFO  brak pola funnel w API: licznik „wyjaśnione automatycznie” pominięty")
    check("miniwykres trendu w linii stanu", page.get_by_label("Stan danych").locator("canvas[data-chart=line]").count() == 1)
    check("kropka połączenia: „połączono”", "połączono" in body)
    filters = page.locator("[role=group][aria-label='Moduł'], [role=radiogroup][aria-label='Moduł']")
    ys = page.evaluate("""() => ['Stan', 'Źródło', 'Siła'].map(n => { const e = [...document.querySelectorAll('[role=combobox]')].find(x => (x.getAttribute('aria-label') || x.innerText || '').includes(n)); return e ? Math.round(e.getBoundingClientRect().top) : null; })""")
    search_y = page.evaluate("Math.round(document.querySelector('input[type=search]').getBoundingClientRect().top)")
    check("filtry Stan, Moduł, Źródło, Siła, Data, Szukaj i Raport w jednym rzędzie", len(set(ys)) == 1 and abs(ys[0] - search_y) < 12 and page.get_by_role("button", name="Data").count() == 1 and page.get_by_role("link", name="Raport", exact=True).count() == 1, f"{ys} {search_y}")
    check("brak przycisku „Dodaj dowód” w górnym pasku i przycisku JSON", page.get_by_role("button", name="Dodaj dowód").count() == 0 and page.get_by_role("link", name="JSON").count() == 0)
    check("brak nagłówka z liczbą, zdania objaśniającego i linii reguł", "Reguły:" not in body and "Finfluencerzy, reklamy firm" not in body and "czeka na transkrypcję:" not in body)
    check("wiersze kolejki z trzech modułów", page.locator("a[id^='row-']").count() == REVIEW, str(page.locator("a[id^='row-']").count()))
    heads = page.locator("th").all_inner_texts()[:4]
    check("lista: cztery kolumny Materiał, Firma, Dlaczego tutaj, Siła", [h.strip() for h in heads] == ["Materiał", "Firma", "Dlaczego tutaj", "Siła"], str(heads))
    check("siła jako jedna plakietka „mocna 100”", "mocna 100" in body and "mocna 95" in body and "100 z 100 pkt" not in body)
    check("plakietki modułu ze słownika", all(n in body for n in ("M1 Twórcy", "M2 Reklamy firm", "M3 Doradztwo")) and not any(n in body for n in ("Finfluencer", "Reklama firmy")))
    check("wiersze: źródło, marka firmy", "YouTube" in body and "XTB" in body and "XTB Ltd / XTB S.A." not in body and "Noble Securities" in body)
    first_titles = page.locator("a[id^='row-']").evaluate_all("els => els.map(e => e.innerText.trim())")
    check("sortowanie domyślne: najsilniejszy na górze (mocna 100 pierwsza)", "Ile trzeba mieć" in first_titles[0], str(first_titles[:2]))
    page.wait_for_selector("text=/M1 Twórcy\\s*\\d/")
    mods = page.get_by_role("radiogroup", name="Moduł").inner_text()
    check("filtr modułu z licznikami (4 + 9 + 1)", re.search(r"M1 Twórcy\s*4", mods) and re.search(r"M2 Reklamy firm\s*9", mods) and re.search(r"M3 Doradztwo\s*1", mods), mods.replace("\n", " "))
    check("liczniki zakładek z API (Do sprawdzenia, Rejestr reklam)", str(REG) in tabs[1] and str(REVIEW) in tabs[0])
    check("brak słowa naruszenie jako werdyktu", "naruszenie" not in body.replace("prawdopodobieństwo naruszenia", "").replace("prawdopodobieństwa naruszenia", ""))
    check("brak kodów, ścieżek i nazw pól na ekranie", not re.search(r"docs/|fixtures/|\.token|no_signal|\brefer\b|qual_d|m2Card|tiktok_embed|data_api|\(znaki", body))
    overview = [u for u in requests if "/v1/overview" in u]
    check("jednorazowy odczyt /v1/overview (bez /v1/state), kolejki z /v1/queues", len(overview) == 1 and not [u for u in requests if "/v1/state" in u] and any("/v1/queues/review" in u for u in requests), str(overview))

    # 2. Karta M1 z flagą: Droga dowodu, Dlaczego tutaj, Dowód, Decyzja bez przewijania
    page.get_by_role("link", name=re.compile("Freedom24 Alternatywy")).first.click()
    page.wait_for_selector("h2:has-text('Freedom24 Alternatywy')")
    page.wait_for_selector("[data-testid=proof-path] [data-step]")
    page.wait_for_timeout(900)
    panel = page.locator("[role=complementary]")
    text = panel.inner_text()
    for part in ("Dlaczego tutaj", "Dowód", "Decyzja", "Możliwe wyjaśnienie"):
        check(f"karta: {part}", part in text)
    for gone in ("Co zbadano", "Twórca i zasięg", "Momenty do sprawdzenia", "Zasięg kanału", "Jak odkryto"):
        check(f"karta bez kafla: {gone}", gone not in text)
    check("nagłówek: plakieta siły, moduł, jedna linia metadanych i przycisk", "mocna 95" in text and "M1 Twórcy" in text and "ForexMind" in text and "22 wyśw." in text and "Firma: XTB (2 wpisy KNF)" in text and (page.get_by_role("link", name="Otwórz w filmie od 0:15").count() + page.get_by_role("button", name="Otwórz w filmie od 0:15").count()) >= 1)
    steps = panel.locator("[data-testid=proof-path] [data-step]")
    states = steps.evaluate_all("els => els.map(e => e.dataset.step + ':' + e.dataset.state)")
    check("Droga dowodu: kroki Odkrycie, Opis, Flaga, Mowa, Kadry, Firma, Wynik", len(states) >= 6 and all(any(x.startswith(k) for x in states) for k in ("discovery", "description", "speech", "frames", "firm", "decision")), str(states))
    check("Droga dowodu w karcie flagi: bez kroku obalającego", not any(x.endswith(":refuted") for x in states), str(states))
    save = panel.get_by_role("button", name="Zapisz decyzję")
    box = save.bounding_box()
    check("Decyzja na 1440×900 widoczna bez przewijania (Zapisz decyzję w oknie)", box and box["y"] + box["height"] <= 900 and panel.get_by_role("button", name="Przekaż do kontroli").is_visible(), str(box))
    check("najwyżej 3 punkty w „Dlaczego tutaj”, bez rozwijania", text.count("•") == 3 and "Pokaż wszystkie" not in text)
    check("moment 0:15 z linkiem do sekundy", panel.locator("a[href*='AqXHkxDzSDI'][href*='t=15s']").count() >= 1)
    thumbs = panel.locator("img[src*='/v1/frames/AqXHkxDzSDI/']")
    check("dwie miniatury kadrów z API", thumbs.count() == 2 and all(thumbs.nth(i).evaluate("e => e.complete && e.naturalWidth > 0") for i in range(thumbs.count())))
    check("zastrzeżenie prawne raz, w stopce strony", text.count("nie ocena prawna") == 0 and page.inner_text("body").count("nie ocena prawna") == 1)
    check("sekcje „Więcej” zamknięte", page.get_by_role("tab", name="Historia").count() == 0 or not page.get_by_role("tab", name="Historia").first.is_visible())
    page.get_by_text("Więcej: historia, punktacja, szczegóły").click()
    check("„Więcej” ma 3 zakładki: Historia, Punktacja, Szczegóły", page.get_by_role("tab", name="Historia").count() == 1 and page.get_by_role("tab", name="Punktacja").count() == 1 and page.get_by_role("tab", name="Szczegóły").count() == 1 and page.get_by_role("tab", name="Surowe dane").count() == 0)
    page.get_by_role("tab", name="Punktacja").click()
    page.wait_for_timeout(300)
    check("„Więcej”: składniki punktacji", "przeszukano pełną transkrypcję" in panel.inner_text())
    page.get_by_role("tab", name="Szczegóły").click()
    page.wait_for_timeout(300)
    det = panel.inner_text()
    check("„Szczegóły”: droga odkrycia, pochodzenie i identyfikator, bez ścieżek plików", "Droga odkrycia" in det and "Pochodzenie" in det and "Identyfikator" in det and "docs/" not in det)

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

    # 4b. Filtr Stan: kolejki API (Niepełne, Wszystkie, Zamknięte, Demo) i przekierowania starych adresów
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    ready(page)
    page.wait_for_selector("a[id^='row-']")
    pick(page, "Stan", re.compile(r"^Niepełne"))
    page.wait_for_selector(f"text=Pokazano 50 z {INC}")
    check("filtr Stan „Niepełne”: kolejka incomplete z API (liczba z API), adres state=incomplete", "state=incomplete" in page.url and f"Pokazano 50 z {INC}" in page.inner_text("body"))
    check("Niepełne: kolumna „Czego brakuje” z powodem", "Czego brakuje" in page.inner_text("body"))
    pick(page, "Stan", re.compile(r"^Demo"))
    page.wait_for_selector(f"text=Pokazano {COUNTS['demo']} z {COUNTS['demo']}")
    check("filtr Stan „Demo”: kolejka demo", "state=demo" in page.url and f"Pokazano {COUNTS['demo']} z {COUNTS['demo']}" in page.inner_text("body"))
    pick(page, "Stan", re.compile(r"^Zamknięte"))
    page.wait_for_timeout(700)
    check("filtr Stan „Zamknięte”: pusty stan lub lista z API", "state=closed" in page.url and ("Nie ma jeszcze zamkniętych spraw" in page.inner_text("body") or "Pokazano" in page.inner_text("body")))
    pick(page, "Stan", "Wszystkie")
    page.wait_for_selector(f"text=/Pokazano 50 z {ALL}/")
    check("filtr Stan „Wszystkie”: kolejka all", "state=all" in page.url and f"Pokazano 50 z {ALL}" in page.inner_text("body"))
    for old, expect in (("#m2", "state=all&module=M2"), ("#m3", "state=all&module=M3"), ("#niepelne", "state=incomplete"), ("#zamkniete", "state=closed"), ("#demo", "state=demo")):
        page.goto(f"{BASE}/{old}", wait_until="networkidle")
        page.wait_for_timeout(700)
        check(f"stary adres {old} przekierowuje na filtr", expect in page.url and page.url.split("#")[1].startswith("review"), page.url)
    page.goto(f"{BASE}/#m3", wait_until="networkidle")
    page.wait_for_selector(f"text=/Pokazano \\d+ z {COUNTS['offersM3']}/")
    check("#m3: lista ofert doradczych z API (kolejka offersM3)", page.get_by_text(re.compile(r"Pokazano \d+ z %d" % COUNTS["offersM3"])).count() == 1)
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    page.goto(f"{BASE}/#m2?case=web%3Anoblesecurities.pl%2Fklient-indywidualny%2Frachunek-ike", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Rachunek IKE')")
    check("stary adres z kartą (#m2?case=…) otwiera kartę po przekierowaniu", "case=" in page.url and page.url.split("#")[1].startswith("review"), page.url)
    page.goto(f"{BASE}/#evidence", wait_until="networkidle")
    page.wait_for_selector("[data-section=add-file]")
    check("#evidence → Źródła z otwartą sekcją „Dodaj materiał”", page.url.split("#")[1].startswith("sources") and page.locator("[data-section=add-file]").is_visible() and "Plik audio lub wideo" in page.inner_text("body"), page.url)

    # 5. Rejestr: stronicowanie, jak ujawniono, liczniki „wyjaśnione automatycznie” z filtrem
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
    check("rejestr: kolumny Materiał, Firma, Jak ujawniono (bez kolumny Platforma)", all(h in body for h in ("Materiał", "Firma", "Jak ujawniono")) and "Typ ujawnienia" not in body)
    check("rejestr: jak ujawniono i cytat z API w jednej linii", ("flaga YouTube" in body or "w mowie" in body) and "w opisie" in body and "REKLAMA" in body)
    check("rejestr: bez dociągania kart wierszy", len([u for u in requests_reg if "/v1/cases/" in u]) == 0, str([u for u in requests_reg if "/v1/cases/" in u][:3]))
    check("rejestr: przycisk Raport z adresem /v1/report", page.get_by_role("link", name="Raport", exact=True).count() == 1 and "/v1/report?" in page.get_by_role("link", name="Raport", exact=True).get_attribute("href"))
    check("rejestr: bez przełącznika modułu", page.get_by_role("radiogroup", name="Moduł").count() == 0)
    if funnel:
        e = funnel["explainedAutomatically"]
        group = page.get_by_role("group", name="Jak ujawniono współpracę")
        check("rejestr: liczniki w jednej linii (w opisie, w mowie, flaga YouTube, czeka na mowę)", all(t in group.inner_text() for t in (f"w opisie {e['byDescription']}", f"w mowie {e['bySpeech']}", f"flaga YouTube {e['byPlatformFlag']}", "czeka na mowę")), group.inner_text().replace("\n", " "))
        group.get_by_role("button", name=re.compile(r"^w mowie")).click()
        page.wait_for_selector(f"text=Pokazano {e['bySpeech']} z {e['bySpeech']}")
        check("licznik „w mowie” zawęża listę do tylu wierszy, ile pokazuje", page.locator("a[id^='row-']").count() == e["bySpeech"] and "disc=in_speech" in page.url and "w mowie" in page.inner_text("body"), str(page.locator("a[id^='row-']").count()))
        group.get_by_role("button", name=re.compile(r"^w mowie")).click()
        page.wait_for_selector(f"text=Pokazano 50 z {REG}")
        check("ponowne kliknięcie licznika czyści zawężenie", "disc=" not in page.url)

    # 7. Źródła: wykresy, tabela platform, modele, kroki skanu
    page.goto(f"{BASE}/#sources", wait_until="networkidle")
    ready(page, "Źródła")
    page.wait_for_function("document.querySelectorAll('canvas[data-chart]').length >= 2", timeout=15000)
    page.wait_for_timeout(800)
    body = page.inner_text("body")
    check("źródła: trend (materiały i osobno skierowania), bez wykresu per platforma", page.locator("canvas[data-chart]").count() == 2 and "Materiały i skierowania w czasie" in body and "Skierowania do sprawdzenia" in body and "materiały per platforma" not in body, f"canvas={page.locator('canvas[data-chart]').count()}")
    check("źródła: płótna wykresów mają rozmiar", page.evaluate("[...document.querySelectorAll('canvas[data-chart]')].every(c => c.width > 50 && c.height > 50)"))
    check("źródła: dwa osobne wykresy trendu bez drugiej osi", page.locator("canvas[aria-label*='Wykres: materiały przejrzane w czasie']").count() == 1 and page.locator("canvas[aria-label*='Wykres: skierowania do sprawdzenia w czasie']").count() == 1)
    table = page.get_by_role("table", name="Platformy i drogi odczytu")
    check("źródła: jedna tabela platform z kolumnami platforma, stan, droga odczytu, materiały, ostatni odczyt, następny krok", all(h in table.inner_text() for h in ("Platforma", "Stan", "Droga odczytu", "Materiały", "Ostatni odczyt", "Następny krok")))
    rows = table.locator("tbody tr").all_inner_texts()
    check("źródła: siedem wierszy platform", len(rows) == 7 and all(any(n in r for r in rows) for n in ("YouTube", "TikTok", "Instagram", "Facebook", "WWW firm (M2)", "WWW doradców (M3)", "Biblioteka Reklam Meta")), str(len(rows)))
    trow = lambda name: next(r for r in rows if name in r).replace("\n", " ")
    check("wiersz Instagram: próbka z usługi zewnętrznej, import ręczny, liczba materiałów z API", "próbka z usługi zewnętrznej" in trow("Instagram") and "import ręczny" in trow("Instagram") and str(call(f"{BASE}/v1/queues/all?platform=instagram&limit=1")["total"]) in trow("Instagram"), trow("Instagram")[:160])
    check("wiersz YouTube: działa, liczba materiałów z API", "działa" in trow("YouTube") and str(call(f"{BASE}/v1/queues/all?platform=youtube&limit=1")["total"]) in trow("YouTube"), trow("YouTube")[:120])
    check("wiersz Meta: brak tokenu i krok bez ścieżki pliku", re.search(r"brak (tokenu|klucza)", trow("Biblioteka Reklam Meta")) and "meta.token" not in body and "docs/lanes" not in body, trow("Biblioteka Reklam Meta")[:160])
    check("źródła: nowy wiersz TikTok z ograniczeniem (sam podpis)", "sam podpis" in trow("TikTok"))
    table.get_by_role("button", name="Drogi").nth(3).click()
    page.wait_for_timeout(400)
    fb = page.get_by_label("Drogi odczytu: Facebook").inner_text()
    check("rozwinięcie drogi Facebooka: próbka z usługi, import ręczny, wpisy automatycznie, blokada, następny krok", all(x in fb for x in ("próbka z usługi zewnętrznej", "import ręczny", "wpisy automatycznie", "dostęp zablokowany", "Następny krok")), fb[:220].replace("\n", " "))
    scan_line = page.get_by_test_id("scan-line").inner_text()
    check("źródła: jedna linia ostatniego skanu i przycisk „Skanuj na żywo” jako główny", "Ostatni skan" in scan_line and "odtworzenie skanu z 21 XI" in scan_line and page.get_by_role("button", name="Skanuj na żywo").count() == 1 and page.get_by_role("button", name="Przelicz materiały").count() == 1, scan_line)
    ms = page.inner_text("body")
    check("źródła: tabela Modele (klasyfikator, drugi głos, licencja, tryb, zmierzone)", all(x in ms for x in ("Modele", "Drugi głos modelu", "Apache-2.0", "Zmierzone")) if "models" in call(f"{BASE}/v1/overview") else True)
    check("źródła: twórcy z filtrem „nowi w skanie”", page.get_by_role("button", name="nowi w skanie").count() == 1)
    if page.get_by_text(re.compile(r"Kroki ostatniego skanu \(")).count():
        page.get_by_text(re.compile(r"Kroki ostatniego skanu \(")).click()
        page.wait_for_timeout(300)
        check("źródła: kroki skanu", "Krok skanu" in page.inner_text("body"))
    check("źródła: droga odkrycia twórcy", "jak odkryto" in page.inner_text("body").lower() and ("Odnośnik" in body or "Kanał Atom" in body or "Wyszukiwanie YouTube" in body))

    # 7b. Filtry: źródło, kanał, data z wyborem pola, raport CSV z BOM
    reqs = []
    page.on("request", lambda r: reqs.append(r.url))
    page.goto(f"{BASE}/#register", wait_until="networkidle")
    ready(page, "Rejestr reklam")
    page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    for name in ("YouTube", "TikTok", "Instagram", "Facebook"):
        expect = call(f"{BASE}/v1/queues/adRegister?platform={name.lower()}&limit=1")["total"]
        pick(page, "Źródło", name)
        page.wait_for_selector(f"text=/Pokazano \\d+ z {expect}\\b/")
        check(f"rejestr: filtr źródła {name} zwraca {expect} z API", expect > 0 and f"source={name.lower()}" in page.url)
        pick(page, "Źródło", "Wszystkie")
        page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    pick(page, "Źródło", "TikTok")
    page.wait_for_selector("text=Pokazano 5 z 5")
    check("filtr źródła TikTok: adres i zapytanie z platform=tiktok", "source=tiktok" in page.url and any("platform=tiktok" in u for u in reqs))
    report_href = page.get_by_role("link", name="Raport", exact=True).get_attribute("href")
    check("raport: adres z aktualnymi filtrami", "module=M1" in report_href and "platform=tiktok" in report_href and "queue=adRegister" in report_href and "format=csv" in report_href, report_href)
    csv_response = urllib.request.urlopen(f"{BASE}{report_href}" if report_href.startswith("/") else report_href, timeout=30)
    raw = csv_response.read()
    check("raport CSV: 200, BOM UTF-8, nagłówek i 5 wierszy", csv_response.status == 200 and raw.startswith(b"\xef\xbb\xbf") and raw.decode("utf-8-sig").splitlines()[0].startswith("firma,") and len(raw.decode("utf-8-sig").strip().splitlines()) == 6, f"{csv_response.status} {len(raw)} B")
    body = page.inner_text("body")
    check("rejestr TikTok: podpis [współpraca z XTB] i data szacowana „≈”", "współpraca z XTB" in body and "≈" in body)
    pick(page, "Źródło", "Wszystkie")
    page.wait_for_selector(f"text=Pokazano 50 z {REG}")
    check("wybranie „Wszystkie” czyści filtr źródła", "source=" not in page.url)
    expected = call(f"{BASE}/v1/queues/adRegister?q=snela&limit=1")["total"]
    page.get_by_role("searchbox").fill("snela")
    page.wait_for_selector(f"text=Pokazano {expected} z {expected}")
    check("wyszukiwanie po autorze (q): wiersze tylko kanału", page.locator("a[id^='row-']").count() == expected and "q=snela" in page.url and expected > 0, str(expected))
    page.goto(f"{BASE}/#register?dateField=publishedAt&from=2026-11-01", wait_until="networkidle")
    ready(page, "Rejestr reklam")
    page.wait_for_timeout(800)
    check("data: pole „opublikowano” trafia do API (dateField=publishedAt, since)", any("dateField=publishedAt" in u and "since=2026-11-01" in u for u in reqs))
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    ready(page)
    check("moduł M1: przycisk Raport w liście Do sprawdzenia", page.get_by_role("link", name="Raport", exact=True).count() == 1)

    # 7e. Moduły w jednej liście: filtr modułu, Droga dowodu z krokiem obalającym w karcie z rejestru, karta M2, karta M3
    page.goto(f"{BASE}/#review", wait_until="networkidle")
    ready(page)
    page.get_by_role("radio", name=re.compile(r"M3 Doradztwo")).click()
    page.wait_for_selector("text=Pokazano 1 z 1")
    check("filtr modułu M3: jeden wiersz, adres z module=M3", "module=M3" in page.url and page.locator("a[id^='row-']").count() == 1 and "RDM Wealth" in page.inner_text("body"))
    page.get_by_role("radio", name=re.compile(r"M2 Reklamy firm")).click()
    page.wait_for_selector("text=Pokazano 9 z 9")
    check("filtr modułu M2: 9 wierszy", "module=M2" in page.url and page.locator("a[id^='row-']").count() == 9)
    page.get_by_role("radio", name=re.compile(r"^Wszystkie")).click()
    page.wait_for_selector(f"text=Pokazano {REVIEW} z {REVIEW}")
    check("„Wszystkie” czyści filtr modułu", "module=" not in page.url)
    page.goto(f"{BASE}/#register?case=youtube%3ACDk20n4u9Kk", wait_until="networkidle")
    page.wait_for_selector("[data-testid=proof-path] [data-step]")
    page.wait_for_timeout(700)
    rg = page.inner_text("body")
    rs = page.locator("[data-testid=proof-path] [data-step]").evaluate_all("els => els.map(e => e.dataset.step + ':' + e.dataset.state)")
    speech = page.locator("[data-testid=proof-path] [data-step=speech]")
    check("karta z rejestru (Comparic): Droga dowodu z krokiem Mowa „obaliło”", "speech:refuted" in rs and "obaliło" in speech.inner_text(), str(rs))
    check("krok Mowa z czasem 10:14 i cytatem", "10:14" in speech.inner_text() and "partnera tego odcinka" in speech.inner_text())
    check("krok Mowa z czasem otwiera film w tej sekundzie", page.locator("[data-testid=proof-path] a[href*='CDk20n4u9Kk'][href*='t=614s']").count() >= 1, str(page.locator("[data-testid=proof-path] a").evaluate_all("els => els.map(e => e.href)")))
    check("karta Comparic: przycisk „Otwórz w filmie od 10:14” i cytat w Dowodzie", (page.get_by_role("link", name="Otwórz w filmie od 10:14").count() + page.get_by_role("button", name="Otwórz w filmie od 10:14").count()) >= 1 and "znajdziecie u partnera" in rg)
    check("karta Comparic: wynik „Bez przesłanki” w rejestrze, bez plakietki siły 0", "Bez przesłanki" in rg and "słaba 0" not in rg)
    noble = "web%3Anoblesecurities.pl%2Fklient-indywidualny%2Frachunek-ike"
    page.goto(f"{BASE}/#review?case={noble}", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Rachunek IKE')")
    page.wait_for_selector("[data-testid=proof-path] [data-step]")
    page.wait_for_timeout(900)
    panel = page.locator("[role=complementary]")
    mt = panel.inner_text()
    check("karta M2: nagłówek (siła, moduł, firma i typ podmiotu, Otwórz stronę)", "mocna 95" in mt and "M2 Reklamy firm" in mt and "NOBLE Securities S.A. · dom maklerski" in mt and panel.get_by_role("link", name="Otwórz stronę").count() == 1)
    for part in ("Dlaczego tutaj i dowód", "Decyzja"):
        check(f"karta M2: {part}", part in mt)
    check("karta M2: Droga dowodu (render, twierdzenie, ostrzeżenie, firma, wynik)", panel.locator("[data-testid=proof-path] [data-step]").count() >= 4)
    check("karta M2: trzy przesłanki w Dowodzie, reszta pod „+ 5 przesłanek”", "Informacja o ryzyku przy zysku" in mt and "Informacja podatkowa" in mt and "Rozmiar czcionki ryzyka" in mt and re.search(r"\+ \d+ przesłan", mt) and panel.locator("[data-premise]:visible").count() == 3, str(panel.locator("[data-premise]:visible").count()))
    check("karta M2: pomiar czytelny (11 px wobec 16 px), bez „y=” i progu w nawiasie", "11 px" in mt and "16 px" in mt and "y=" not in mt and "próg: pół ekranu" not in mt)
    check("karta M2: pełna lista 19 kryteriów zwinięta na początku", "Wszystkie 19 kryteriów wg stanu" in mt and "Identyfikacja firmy" not in mt)
    check("karta M2: Decyzja widoczna bez przewijania na 1440×900", panel.get_by_role("button", name="Zapisz decyzję").bounding_box()["y"] < 900)
    imgs = panel.locator("img[src*='/evidence/m2/market/']")
    page.wait_for_timeout(500)
    n_imgs = imgs.count()
    check("karta M2: miniatury zrzutów (komputer i telefon) z naturalWidth > 0", n_imgs >= 3 and all(imgs.nth(i).evaluate("e => e.complete && e.naturalWidth > 0") for i in range(n_imgs)), str(n_imgs))
    check("karta M2: podpisy komputer i telefon przy miniaturach", "komputer" in mt and "telefon" in mt)
    imgs.first.click()
    page.wait_for_selector("dialog[open] img")
    check("karta M2: kliknięcie powiększa zrzut w oknie", page.locator("dialog[open] img").count() >= 1 and page.locator("dialog[open] img").first.evaluate("e => e.naturalWidth > 0"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check("karta M2: Escape zamyka powiększenie, karta zostaje", page.locator("dialog[open]").count() == 0 and "Dlaczego tutaj i dowód" in page.locator("[role=complementary]").inner_text())
    page.locator("[role=complementary]").get_by_text("Wszystkie 19 kryteriów wg stanu").click()
    page.wait_for_timeout(400)
    mt = page.locator("[role=complementary]").inner_text()
    check("karta M2: rozwinięta lista 19 kryteriów wg stanu", all(x in mt for x in ("Identyfikacja firmy", "Dostępność bez kliknięcia", "Porównania produktów lub usług", "Sugestia aprobaty organu nadzoru")) and "spełnione" in mt and "nie dotyczy" in mt)
    page.locator("[role=complementary]").get_by_text("Więcej: historia, punktacja, szczegóły").click()
    page.get_by_role("tab", name="Szczegóły").click()
    page.wait_for_timeout(300)
    mt = page.locator("[role=complementary]").inner_text()
    check("karta M2: „Szczegóły” z firmą z wykazu KNF (numer wpisu) i odczytem", "dom maklerski" in mt and "6884971" in mt and "Baner cookies" in mt)
    page.goto(f"{BASE}/#review?case=web%3Ardmwm.pl%3Am3", wait_until="networkidle")
    page.wait_for_selector("[data-axis]")
    page.wait_for_timeout(700)
    panel = page.locator("[role=complementary]")
    m3 = panel.inner_text()
    check("karta M3: nagłówek (siła, moduł, domena, Otwórz ofertę)", "mocna 85" in m3 and "M3 Doradztwo" in m3 and "rdmwm.pl" in m3 and panel.get_by_role("link", name="Otwórz ofertę").count() == 1)
    for part in ("Dlaczego tutaj", "Dowód", "Decyzja"):
        check(f"karta M3: {part}", part in m3)
    check("karta M3: cztery cechy po jednej linii z cytatem i podstroną", panel.locator("[data-axis]").count() == 4 and all(x in m3 for x in ("Czynność", "Personalizacja", "Instrument", "Rynek")) and "Na podstawie tych danych dobieramy proporcje" in m3 and panel.locator("a[href='https://rdmwm.pl/']").count() >= 4)
    check("karta M3: Droga dowodu z krokiem Uprawnienia", panel.locator("[data-testid=proof-path] [data-step=identity]").count() == 1 and "brak danych podmiotu" in panel.locator("[data-testid=proof-path]").inner_text())
    check("karta M3: Decyzja widoczna bez przewijania na 1440×900", panel.get_by_role("button", name="Zapisz decyzję").bounding_box()["y"] < 900)
    panel.get_by_text("Więcej: historia, punktacja, szczegóły").click()
    page.get_by_role("tab", name="Szczegóły").click()
    page.wait_for_timeout(300)
    m3 = panel.inner_text()
    check("karta M3: „Szczegóły”: dane podmiotu na stronie, 12 przejrzanych wykazów, zastrzeżenie o braku wpisu", "Dane podmiotu na stronie" in m3 and "Przejrzane wykazy" in m3 and "domy maklerskie" in m3 and "Brak wpisu nie dowodzi braku uprawnień" in m3)
    licensed = [i for i in call(f"{BASE}/v1/queues/offersM3?limit=500")["items"] if i.get("licensed")]
    if licensed:
        lid = licensed[0]["id"].replace(":", "%3A")
        page.goto(f"{BASE}/#review?state=all&module=M3&case={lid}", wait_until="networkidle")
        page.wait_for_selector("[data-axis]")
        page.wait_for_timeout(500)
        check("karta M3: podmiot uprawniony: krok „Uprawnienia: obaliło” i plakietka kontroli na liście", page.locator("[data-testid=proof-path] [data-step=identity][data-state=refuted]").count() == 1 and page.get_by_text("kontrola: podmiot uprawniony").count() >= 1)
        names = [n for n in (call(f"{BASE}/v1/cases/{licensed[0]['id']}").get("identity", {}).get("operator", {}).get("names") or [])]
        check("karta M3 (kontrola ujemna): nazwa podmiotu z identity.operator.names w nagłówku", not names or any(n.split()[0] in page.inner_text("body") for n in names), str(names[:2]))
    else:
        print("INFO  brak podmiotów z licensed=true w offersM3: kontrola ujemna pominięta")

    # 7d. Import ręczny w sekcji „Dodaj materiał” (Źródła): wgranie zapisanej strony Biblioteki Reklam Meta, błąd 422, karta reklamy
    page.goto(f"{BASE}/#sources", wait_until="networkidle")
    ready(page, "Źródła")
    check("źródła: sekcja „Dodaj materiał” zwinięta, po otwarciu formularz pliku i import Meta", page.locator("[data-section=add-file]").count() == 0 or not page.locator("[data-section=add-file]").is_visible())
    page.get_by_text("Dodaj materiał").click()
    page.wait_for_selector("[data-section=meta-import]")
    check("„Dodaj materiał”: dwie karty (nagranie, zapisana strona Meta) i zwijana instrukcja w 3 krokach", page.locator("[data-section=add-file]").is_visible() and "Zapisana strona Biblioteki Reklam Meta lub profilu Instagram" in page.inner_text("body") and page.get_by_text("Jak zapisać stronę").count() == 1)
    page.get_by_text("Jak zapisać stronę").click()
    check("instrukcja zapisu strony rozwija się", page.get_by_text("3. Wybierz zapisany plik").count() == 1)
    meta_input = page.locator("[data-section=meta-import] input[type=file]")
    meta_input.set_input_files(str(Path(__file__).resolve().parents[2] / "fixtures/raw/discovery/social-2026-11-21/alt/metaadlib-browser-body.txt"))
    page.locator("[data-section=meta-import]").get_by_role("button", name="Wgraj do analizy").click()
    page.wait_for_selector("text=/Wczytano:|był już wczytany|czeka w kolejce/", timeout=60000)
    banner = page.inner_text("body")
    check("import: wynik z liczbą reklam, nowych i istniejących", re.search(r"(Wczytano: 22 reklam|już wczytany \(22 reklam)", banner) is not None, re.sub(r"\s+", " ", banner[banner.find("Wczytano") - 5:banner.find("Wczytano") + 120]))
    meta_input.set_input_files(files=[{"name": "smiec.txt", "mimeType": "text/plain", "buffer": b"to nie jest zapisana strona Biblioteki Reklam"}])
    page.locator("[data-section=meta-import]").get_by_role("button", name="Wgraj do analizy").click()
    page.wait_for_selector("text=Nie wczytano pliku", timeout=30000)
    check("import: nierozpoznany plik daje komunikat z API (422), bez zapisu", True)
    page.goto(f"{BASE}/#review?state=all&module=M2", wait_until="networkidle")
    page.wait_for_selector("a[id^='row-']")
    check("lista Wszystkie + M2: wiersze stron i reklam z importu (kolejka offersM2)", f"Pokazano 50 z {COUNTS['offersM2']}" in page.inner_text("body"))
    page.goto(f"{BASE}/#review?state=all&module=M2&case=facebook%3Aad-1353099026431942", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Inwestuj gdziekolwiek')")
    page.wait_for_selector("[data-testid=proof-path] [data-step]")
    page.wait_for_timeout(500)
    ad = page.inner_text("body")
    for part in ("Dlaczego tutaj", "Dowód", "Emisja", "Obraz i wideo", "XTB", "Decyzja", "Otwórz źródło"):
        check(f"karta reklamy Meta: {part}", part in ad)
    check("karta reklamy Meta: kadry i Droga dowodu także w karcie importu, bez „Treść reklamy” i „starszej analizy”", "Treść reklamy" not in ad and "starszej wersji analizy" not in ad and page.locator("[data-testid=proof-path] [data-step]").count() >= 4)
    page.get_by_text("Więcej: historia, punktacja, szczegóły").click()
    page.get_by_role("tab", name="Szczegóły").click()
    page.wait_for_timeout(300)
    check("reklama: „Szczegóły” z wezwaniem, wersjami i notą importu", "Install Now" in page.inner_text("body") and "Wersje reklamy" in page.inner_text("body"))

    # 7c. Karta TikToka z rejestru: ta sama karta, Otwórz źródło, krok Mowa niedostępna, szacowana data
    page.goto(f"{BASE}/#register?case=tiktok%3A7707284619103718689", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('współpraca z XTB')")
    page.wait_for_selector("[data-testid=proof-path] [data-step]")
    page.wait_for_timeout(600)
    tk = page.locator("[role=complementary]").inner_text() if page.locator("[role=complementary]").count() else page.inner_text("body")
    check("karta TikToka: Otwórz źródło zamiast Otwórz w filmie", page.get_by_role("link", name="Otwórz źródło").count() >= 1 and "Otwórz w filmie" not in tk)
    check("karta TikToka: krok Mowa nie zbadana, flaga niesprawdzona", page.locator("[data-testid=proof-path] [data-step=speech][data-state=gap]").count() == 1 and page.locator("[data-testid=proof-path] [data-step=platformFlag][data-state=gap]").count() == 1)
    check("karta TikToka: krok Opis obala podejrzenie oznaczeniem w opisie", page.locator("[data-testid=proof-path] [data-step=description][data-state=refuted]").count() == 1)
    check("karta TikToka: zasięg w odtworzeniach i data szacowana „≈” w jednej linii metadanych", "1 533 odtw." in tk.replace("\xa0", " ") and "≈" in tk, re.sub(r"\s+", " ", tk)[:260])

    # 8. Decyzje na kopii: rodzaj, walidacja, zapis, 409, zamknięcie
    page.goto(f"{BASE}/#review?case=youtube%3AAqXHkxDzSDI", wait_until="networkidle")
    page.wait_for_selector("h2:has-text('Freedom24')")
    panel = page.locator("[role=complementary]")
    before = case("youtube:AqXHkxDzSDI")["revision"]
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
    check("zamknięcie przenosi sprawę z Do sprawdzenia do Zamkniętych", "youtube:OIyPE0z2mng" in closed_ids and "youtube:OIyPE0z2mng" not in review_ids, f"closed={len(closed_ids)} review={len(review_ids)}")
    check("karta odświeżona po zapisie", page.locator("[role=complementary]").count() >= 1)

    # 9. Kalibracja: suwak z podglądem na żywo, FP i FN, macierz 2×2, krzywa, skutek dla kolejki, próg z przywracaniem
    page.goto(f"{BASE}/#calibration", wait_until="networkidle")
    ready(page, "Kalibracja")
    page.wait_for_selector("[data-kpi]")
    page.wait_for_selector("canvas[data-chart=line]")
    body = page.inner_text("body")
    check("kalibracja: zastrzeżenie „oceny agentów” w jednej linii z liczebnością zbioru", re.search(r"Oceny agentów, nie walidacja ekspercka · 26 materiałów · 20 kampanii · zbiór strojenia", body) is not None)
    check("kalibracja: bez wariantu, ścieżki pomiaru i osobnych kafli TP/TN/precyzji", "WYNIK-M1" not in body and "kwalifikacja D" not in body and "Precyzja" not in body and "Fable" not in body)
    check("kalibracja: „4 trafienia, 0 fałszywych alarmów na 26 materiałach” zamiast „Precyzja 100%”", "4 trafienia, 0 fałszywych alarmów na 26 materiałach" in re.sub(r"\s+", " ", body) and "100%" not in body.split("Wynik na zbiorze")[1][:120])
    for label in ("Fałszywe alarmy (FP)", "Przeoczenia (FN)"):
        check(f"kalibracja: duży kafel {label}", page.locator(f"[aria-label^='{label}:']").count() == 1)
    check("kalibracja: macierz 2×2", page.get_by_role("table", name="Macierz pomyłek").count() == 1 and "4 trafnych" in body and "22 poprawnie" in body)
    kpi = lambda name: page.locator(f"[aria-label^='{name}:']").get_attribute("aria-label").split(": ")[1]
    check("kalibracja przy progu 60: FP 0, FN 0", (kpi("Fałszywe alarmy (FP)"), kpi("Przeoczenia (FN)")) == ("0", "0"))
    check("kalibracja: linia „Poprzednie reguły przy tym progu: FP 7, FN 4”", "Poprzednie reguły przy tym progu: FP 7, FN 4" in body)
    check("kalibracja: skutek dla kolejki przy progu obowiązującym", "się nie zmienia" in page.get_by_test_id("queue-effect").inner_text())
    slider = page.get_by_role("slider")
    slider.focus()
    page.keyboard.press("End")
    page.wait_for_selector("text=zniknie")
    check("suwak do 100: FN rośnie (0→3) i skutek dla kolejki „zniknie N”", kpi("Przeoczenia (FN)") == "3" and re.search(r"zniknie \d+ spra", page.get_by_test_id("queue-effect").inner_text()), f"FN={kpi('Przeoczenia (FN)')} {page.get_by_test_id('queue-effect').inner_text()}")
    check("suwak: oznaczenie zmiany względem obowiązującego progu", "względem obowiązującego" in page.inner_text("body"))
    page.keyboard.press("Home")
    page.wait_for_selector("text=Zastosuj 0 pkt")
    page.get_by_role("button", name="Wróć do obowiązującego").click()
    page.wait_for_selector("text=się nie zmienia")
    # kalibracja M2: ten sam suwak, inny zbiór; próg 30 wobec 50 zmienia FP i FN
    page.get_by_role("radio", name="M2 Reklamy firm").click()
    page.wait_for_selector("text=/Oceny agentów, nie walidacja ekspercka · 25 materiałów · 11 firm/")
    m2_60 = (kpi("Fałszywe alarmy (FP)"), kpi("Przeoczenia (FN)"))
    m2_applied = call(f"{BASE}/v1/calibration?module=M2")["storedThreshold"]
    check("kalibracja M2: próg obowiązujący z API (30) i dane zbioru M2 (25 stron, 11 firm)", m2_applied == 30 and "9 trafień" in re.sub(r"\s+", " ", page.inner_text("body")), str(m2_applied))
    slider = page.get_by_role("slider")
    slider.focus()
    for _ in range(4):
        page.keyboard.press("ArrowRight")
    page.wait_for_selector("text=Przy progu 50 pkt")
    page.wait_for_timeout(500)
    m2_50 = (kpi("Fałszywe alarmy (FP)"), kpi("Przeoczenia (FN)"))
    check("kalibracja M2: próg 30 → 50 zmienia FP/FN (FN 3 → 5), skutek dla kolejki „zniknie 3 sprawy”", m2_50 != m2_60 and m2_50[1] == "5" and re.search(r"zniknie 3 sprawy", page.get_by_test_id("queue-effect").inner_text()), f"{m2_60} → {m2_50} {page.get_by_test_id('queue-effect').inner_text()}")
    check("kalibracja M2: bez zapisu progu (tylko podgląd)", page.get_by_role("button", name=re.compile(r"Zastosuj \d+ pkt")).count() == 0)
    page.get_by_role("button", name="Wróć do obowiązującego").click()
    page.wait_for_selector("text=Przy progu 30 pkt")
    page.get_by_role("radio", name="M3 Doradztwo").click()
    page.wait_for_selector("text=/Oceny agentów, nie walidacja ekspercka · 31 materiałów/")
    check("kalibracja M3: przełącznik modułu działa (31 materiałów)", True)
    page.get_by_role("radio", name="M1 Twórcy").click()
    page.wait_for_selector("text=Przy progu 60 pkt")
    page.get_by_text("Więcej: historia ustawień, porównanie reguł, zbiór etykiet").click()
    check("kalibracja: historia ustawień i porównanie reguł pod „Więcej”", page.get_by_role("button", name="Przywróć").count() >= 1 and "Porównanie reguł przy progu" in page.inner_text("body"))
    slider = page.get_by_role("slider")
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
    ctx.close()

    # 11. Telefon: lista, karta jako osobny ekran, pasek Dowód · Decyzja, powrót z filtrem, brak poziomego przewijania
    ctx, page = new(390, 844)
    page.goto(f"{BASE}/#review?from=2026-01-01", wait_until="networkidle")
    page.wait_for_selector("text=Ile trzeba mieć")
    check("telefon: brak poziomego przewijania", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), str(page.evaluate("document.documentElement.scrollWidth")))
    first_y = page.locator("a[id^='row-'], a[href*='case=']").first.bounding_box()["y"]
    check("telefon: pierwsza sprawa powyżej 400 px (dziś ok. 570)", first_y < 400, str(first_y))
    check("telefon: cztery zakładki bez przewijania poziomego", all(page.get_by_role("tab", name=n).is_visible() and page.get_by_role("tab", name=n).bounding_box()["x"] + page.get_by_role("tab", name=n).bounding_box()["width"] <= 392 for n in ("Do sprawdzenia", "Rejestr", "Źródła", "Kalibracja")))
    check("telefon: filtry Stan, Moduł i „Filtry” w jednym rzędzie", page.get_by_role("button", name=re.compile("^Filtry")).count() == 1)
    page.get_by_role("link", name=re.compile("Ile trzeba mieć")).first.click()
    page.wait_for_selector("h2:has-text('Ile trzeba mieć')")
    page.wait_for_selector("[data-testid=proof-path]")
    page.wait_for_timeout(600)
    check("telefon: karta z Wróć do listy i paskiem Dowód · Decyzja", page.get_by_role("button", name="Wróć do listy").count() == 1 and page.get_by_role("button", name="Dowód", exact=True).count() == 1 and page.get_by_role("button", name="Decyzja", exact=True).count() >= 1)
    check("telefon: Droga dowodu jako lista pionowa kroków", page.locator("[data-testid=proof-path] [data-step]").count() >= 6)
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
        page2.wait_for_selector("text=Nowa sprawa", timeout=8000)
        check("alert wysokiego ryzyka w drugiej sesji", "Ile trzeba mieć" in page2.inner_text("body"))
        page2.get_by_role("button", name="Otwórz").first.click()
        page2.wait_for_timeout(800)
        check("alert otwiera sprawę w Do sprawdzenia", "#review" in page2.url and "case=" in page2.url)
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
