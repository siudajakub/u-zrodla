# Niezależna ocena względem kryteriów UKNF · 21 XI 2026, ok. 20:30 UTC

Sędzia tylko do odczytu, model `claude-opus-5-5`. Stan: `hack/integration` na b11e236 plus niezacommitowane zmiany w `api/` i `web/src/desk/`. Działające API to `127.0.0.1:18801` (uvicorn z `.runtime/venv`, nie Compose). Źródła wymagań: `docs/zrodla-uknf/` (BRIEF §1–9, TEMAT-1..3, KRYTERIA-M2). Statusów z `docs/ODBIOR-UKNF.md` nie przyjmowałem na wiarę, bo opisują HEAD 491094d. Wyrywkowo sprawdziłem je w kodzie i w API.

## Odpowiedź w 10 zdaniach

1. Na żywo najmocniej działa M1 na YouTube. Replay 1313 materiałów z Data API i Atom, w tym 17 filmów z napisami i kadrami, daje kolejkę 4 skierowań z momentem dowodu. Do tego rejestr 264 reklam powiązanych z wykazami KNF, także z firmą transgraniczną (Freedom24 → notyfikacja 9439434).
2. M2 ma rzetelny mechanizm Chromium na 3 szerokościach, ale tylko 3 materiały z 2 firm. Na prawdziwych materiałach 13–18 z 19 kryteriów zwraca „brak danych”. K-09 nie ma żadnej oceny.
3. M3 jest najsłabszy. Ma 3 zakodowane domeny, nie odkrywa podmiotów i nie znalazł ani jednego potencjalnie nieuprawnionego doradcy. Na działającym API sugestia E5 dla BOŚ ma stan `unavailable`.
4. Brief wymienia z nazwy Facebook, Instagram i TikTok. FB i IG nie mają kolektora ani udokumentowanej próby dostępu. TikTok (2 profile przez osadzenie) istnieje w kodzie, ale nie występuje w źródłach działającego demo.
5. Wprost wymienione elementy techniczne bez realizacji: rotacja User-Agent i proxy, wykres trendu w nowym pulpicie (jest tylko endpoint `/v1/trend`), aktualny audyt npm/pip dla grafu React 19 i Astryx oraz `.env.example`.
6. Trafności nie zwalidowano. Wynik 4/4 TP i 0 FP dla `qual_d` pochodzi z etykiet dwóch modeli Claude na zbiorze strojenia: 3 kampanie, jeden reklamodawca (XTB), jeden mechanizm (link partnerski). Panel kalibracji pokazuje przy tym inny, stary zbiór 13 przykładów (9 syntetycznych), którego etykiety przeczą decyzji J (FN 4 przy progu 60).
7. Ścieżka pokazu jest ryzykowna. Compose z Quick Start nie montuje paczki `.runtime/replay-media`, więc kolejka M1 w Compose najpewniej będzie pusta (stwierdzone statycznie, nie uruchamiałem). Ścieżki na Macu M3 nikt nie uruchomił. PDF i scenariusz `docs/hackathon/demo.md` opisują produkt sprzed zwrotu na YouTube.
8. Dziś szacuję wynik na **5,0 / 6,3 / 7,3 z 10** (pesymistyczny, realistyczny, optymistyczny).
9. Najwięcej punktów na godzinę dają: próba pokazu na Macu z naprawionym montowaniem paczki, odświeżenie PDF i scenariusza, kalibracja na zbiorze q-v2, TikTok w demo z jawną blokadą FB/IG, wykres trendu, audyt zależności, rotacja UA/proxy i 3–5 prospektywnych ofert M3. Realny zysk to około +1,0 pkt.
10. Rekomendacja źródeł: **(b) YouTube + TikTok** przez istniejący adapter osadzenia oraz FB/IG jako wiersze „blokada dostępu” z datowaną próbą. Nie budujcie szerokiego scrapingu ani X.

## 1. Jak blisko wymagań

### 1a. Kryteria sposobu oceny z briefu §6 (brzmienie oryginału)

| §6 | Stan | Dowód | Luka widoczna dla jury |
|---|---|---|---|
| „Skuteczność działania algorytmów scrapujących (poprawność pobierania danych ze źródeł)” | częściowe | `/v1/state`: źródła `youtube` (1300, Data API, wpisy kwoty), `youtube-atom`, `replay-media` (17), 3× M2 Chromium. Próba Y: 3/5 top kanałów (niezaliczone, `WYNIK-Y`). Testy kolektorów 65 OK | Tylko replay. Brak FB/IG, TikToka w demo, WWW poza 5 domenami, pokrycia rynku. Napisy YouTube dają 429 z hosta |
| „Trafność klasyfikacji ryzyka przez moduły AI oraz wpływ zmian parametrów progowych na wyniki w panelu kalibracji” | częściowe, słabe | `/v1/calibration?threshold=20/60/90`: FP 3/1/0, FN 1/4/7 na n=13. `WYNIK-M1`: qual_d 4 TP, 0 FP na 26 materiałach (zbiór strojenia, etykiety agentów) | Panel liczy na starym zbiorze 13 (9 syntetycznych) z etykietami `rules_1_2`, a kolejka działa na `qual_d`. Brak odłożonego testu i eksperta. M2 i M3 bez żadnej miary trafności |
| „Stabilność i płynność działania interfejsu webowego oraz powiadamiań w czasie rzeczywistym” | częściowe | WebSocket `/v1/events`, zdarzenie `high_risk` (`api/store.py:776–918`) → baner w `web/src/desk/store.js:79`, `Desk.jsx:253` | Brak pomiaru dostarczenia do drugiej sesji i po ponownym połączeniu. W wierszach kolejki `creatorName: null`. Skan `recompute` na 18801 wisi w stanie `queued` od 20:15 |
| „Użyte biblioteki i ich bezpieczeństwo” | częściowe | Archiwalny pip-audit (37 wersji) i npm audit dla React 18 (`docs/DEMO-ODBIOR.md:32`). Compose: `read_only`, `cap_drop ALL`, `no-new-privileges` | Aktualnie serwowany graf React 19.3.1 i Astryx 0.7.17 nie był audytowany. Brak `.env.example`. Brak CI |
| „Console.log” | zaliczone w kodzie | `grep console.log web/src web/app.js`: 0 trafień | Konsoli przeglądarki na bieżącym pakiecie nie sprawdzałem (zakaz Chromium) |

### 1b. Moduły

| Moduł · wymóg briefu | Spełnione z dowodem | Częściowe | Brak |
|---|---|---|---|
| **M1** reklama osób trzecich, w tym finfluencerów | Odkrycie bez seedów: 380 kanałów, 209 PL (`collectors/youtube.py`, `fixtures/raw/discovery/youtube-api-2026-11-21/`). Kolejka 4 skierowań z cytatem i lokalizatorem (`/v1/queues/review?schema=2`, np. `youtube:7M0rC6-Rueo`, `reviewScore` 100, `firstMoment` z `charStart` 178) | Wszystkie 4 skierowania to jeden reklamodawca i jeden wzorzec (link-pso/bit.ly XTB). Bramka mowy przy 429 opróżnia kolejkę dla nowych filmów | Promocji wyłącznie w mowie lub obrazie na nowym materiale nie zbadano. Brak OCR |
| M1 polskojęzyczne reklamy firm transgranicznych | Freedom24 → „Notyfikacje zagranicznych firm inwestycyjnych”, kandydat 9439434 (`/v1/cases/youtube:9Fcwo1jlwe4`). Saxo i eToro w rejestrze | Saxo Bank ma `identity_unresolved` | Rejestr podaje tu „brak”, a to już nieaktualne |
| M1 raport: firma, reklamujący, treść, URL, okresowa aktualizacja | URL, cytat, kanał, firma z wykazu (`adRelationship.firm.candidates`), `analysis/firm_index.py` używa 4 wykazów KNF | Harmonogram: `INVESTWATCH_DISCOVERY_INTERVAL` i timer systemd bez dowodu automatycznego wyzwolenia. W kolejce `creatorName: null` | Eksportu raportu (CSV/PDF) dla analityka nie znalazłem |
| **M2** własne materiały firm, oddziały zagraniczne | 3 materiały: XTB ETF, XTB akcje, BDM (`/v1/queues/offersM2`), 18 ujęć z SHA-256 | Stała lista `TARGETS`, brak odkrywania | Brak materiału oddziału firmy zagranicznej |
| M2 ryzyko dostateczne, proporcjonalne, wyraźne; flagowanie | ETF `refer` 60: K-3 obserwacja (dywidendy kontra ostrzeżenie ETF), K-5 ostrzeżenie poza pierwszym kadrem | Ocena samymi regułami. Brak modelu, a brief mówi „AI / modele statystyczne” | Zob. 1d: większość ID bez wyniku na rynku |
| **M3** wyszukiwanie wealth management, consulting, family office | Ścieżka domena → oferta (`collectors/sites.py`) | Tylko 3 zakodowane domeny (bossa.pl ×2, financewell.pl) | Brak wyszukiwania nowych podmiotów |
| M3 wykrywanie faktycznego doradztwa bez zezwolenia; raport podmiot, oferta, URL | BOŚ: obserwacje personalizacja, instrument, czynność oraz wpis KNF (kontrola dodatnia autoryzowanego) | FinanceWell: kolizja nazw, `insufficient` | Brak choćby jednego kandydata nieuprawnionego. Brak „trzymaj”, CFD, pochodnych i uprawnień do emisji (T3-03…10). Na 18801 E5 ma stan `unavailable` |

### 1c. Wymagania techniczne i formalne (§3–§5)

| Wymóg | Stan | Dowód lub luka |
|---|---|---|
| Kolejka open source, Playwright/httpx, HTML → JSON | spełnione | Huey (`api/jobs.py`), Playwright M2, `collectors/sites.py` |
| Kolektory social z **rotacją UA i proxy** | brak rotacji | Stałe nagłówki `InvestWatch-SourceMonitor/1.0` (`collectors/common.py:48`, `audio.py:44`, `media.py:262`, `tools/watch_sources.py:320`). Brak proxy |
| SQL, magazyn treści, CronJob/orkiestrator | spełnione / częściowe | SQLite (schemat 7), pliki adresowane skrótem. Harmonogram bez zdarzenia automatycznego wyzwolenia |
| Preprocessing, tokeny, embeddingi, silnik inferencji, model open source | częściowe na żywo | E5 ONNX i Vosk istnieją, ale na 18801 `semantic.status: unavailable`. Ollama/Qwen tylko jako adapter porównawczy (`analysis/ollama_review.py`), poza ścieżką produktu |
| Scoring do kategorii, agregator M1–M3 | spełnione | `route` refer/no_signal/complete/insufficient, wspólne Capture/Finding/Case |
| Dashboard React, filtry data/źródło/ryzyko/moduł | spełnione (wg wcześniejszych prób U) | React 19 i Astryx, `web/src/desk/filters.js`. Na bieżącym pakiecie nie sprawdzałem |
| **Wykresy trendów** | brak w nowym pulpicie | `api.trend` zdefiniowane w `web/src/desk/api.js:102`, żaden komponent go nie wywołuje. `Trend` istnieje tylko w starym `web/app.js` |
| Zmiana statusu, WebSocket, panel progu FP/FN | spełnione mechanicznie | `PATCH /v1/cases`, `/v1/events`, `Calibration.jsx`. Problem zbioru opisuje §1a |
| Modułowość: osobny frontend, backend, AI | częściowe | Katalogi rozdzielone. Compose ma 2 usługi: API serwuje frontend, AI siedzi w workerze. Brak Dockerfile, zależności montowane z hosta |
| Compose jedną komendą | częściowe, ryzyko | Brak montowania `.runtime/replay-media` w `compose.yaml` (`api/replay_pack.py:23,29`). Mac nietestowany (`ops/mac/README.md`, linia 3) |
| Tylko darmowe modele, bez płatnych API | spełnione w produkcie | OpenRouter tylko w eksperymencie (0,04 USD). Lepiej nie pokazywać go jury |
| Skan zależności, sekrety w `.env` | częściowe | Audyt nieaktualny. `.env.openrouter` ignorowany przez Git, brak `.env.example` |
| README minimalny | spełnione | 21 wierszy, Quick Start, sprzęt i konfiguracja. Link do OpenRouter w README warto usunąć |
| Tytuł i opis, PDF, repo | częściowe | PDF z 17:11 opisuje stan sprzed YouTube (1 wzmianka o YouTube) |

### 1d. 19 kryteriów M2: test i wynik na 3 prawdziwych materiałach

S oznacza spełnione, O obserwację do przeglądu, BD „brak danych”. Testy syntetyczne: `analysis/test_engine.py::Marketing`, `tests/e2e/m2_control.py`, `collectors/test_m2_archive.py`. Wynik rynkowy z `/v1/cases/{id}` z 20:25 UTC.

| ID | Test dodatni / ujemny | ETF · akcje · BDM | Ocena |
|---|---|---|---|
| 1 | tak / tak (`test_name_marking_risk`) | S · S · S | Realny, ale brak przypadku ujemnego na rynku |
| 2 | tak / tak | BD · BD · BD | Mechanizm jest, na rynku nie działa |
| 3 | tak / tak (0% prowizji i CFD jako kontrole) | O · BD · BD | Najlepsze ID: realny dowód i para kontrolna |
| 4 | tak / tak (16→8 px, `adRegion`) | BD · BD · BD | Na rynku brak wspólnej sekcji |
| 5 | kontrola e2e (gradient, przesłonięcie) | O · BD · BD | Realny pomiar ETF |
| 6 | tak / tak (footer kontra body) | S · BD · BD | Brak dodatniego przypadku na rynku |
| 7 | tak / tak (`details`) | S · BD · BD | Link i warstwa niezbadane |
| 8 | kontrola reflow | S · BD · BD | Realny pomiar na 3 szerokościach |
| **9** | **nie / nie** | BD · BD · BD | **Zawsze BD** (`checks.py:86–87`), brak jakiejkolwiek oceny |
| 10 | tak / tak (`verifiedLanguages`) | BD · BD · BD | Na rynku tylko atrybut `lang` |
| 11 | tylko wykrycie (`manual=True`, nigdy S) | BD · BD · BD | Wykrywa, nie ocenia |
| 12a | tylko wykrycie frazy, nie sprawdza lat | BD · BD · BD | Słabe |
| 12b | tak / tak, tylko przy USD/EUR/GBP/„brutto” | BD · BD · BD | Wąskie |
| 13 | tylko wykrycie (`manual=True`) | BD · BD · BD | Dominację ocenia analityk |
| 14 | tak / tak | BD · BD · BD | Mechanizm jest |
| 15 | tak / tak | BD · BD · BD | Przy obecnym ostrzeżeniu daje S i gubi zgłoszenie samej prognozy |
| 16 | tak / tak | BD · BD · BD | Mechanizm jest |
| 17 | tak / tak, tylko KNF | BD · BD · BD | Inne organy pominięte |
| 18 | tak / tak, wąski wzorzec | BD · BD · BD | Parafrazy umykają |

Bilans: 15 ID ma syntetyczny test dodatni i ujemny, 3 tylko wykrywają (11, 12a, 13), a ID 9 zawsze zwraca BD. Na rynku wynik ma 6 ID (1, 3, 5, 6, 7, 8) i tylko w ETF. ID 11–18 nie dostają wyniku na żadnym materiale, bo `fullText` nie jest ustawiony, więc nie zapada nawet „nie dotyczy”.

### 1e. Wiersze rejestru `ODBIOR-UKNF.md`, które rozjechały się z kodem

| Wiersz | Rejestr | Stan faktyczny |
|---|---|---|
| R-§2-M1-02, T1-02, T1-05/07/08 | brak / „kod nie używa” | `firm_index.py` używa banków, oddziałów i notyfikacji. Freedom24 jest powiązany z notyfikacją. Do podniesienia na „częściowe” |
| R-§3.3-06 trend | zaliczone | W nowym pulpicie nie ma wykresu. Do obniżenia na „brak” |
| R-§5-03 Compose | częściowe | Dodatkowo paczka replay-media nie jest montowana, więc pokaz z Quick Start traci 17 filmów |
| R-§3.3-10, R-§6-03 kalibracja | częściowe | Panel liczy na zbiorze innym niż ten, który uzasadnia wariant kolejki |
| R-§2-04 TikTok | częściowe | Nieobecny w `sources` działającego demo |
| R-§3.2-05/06 embeddingi | zaliczone | Na 18801 E5 `unavailable` |

## 2. Ile punktów dziś (skala 0–10 na kategorię, wagi z §8)

| Kategoria (waga) | Pes. | Real. | Opt. | Uzasadnienie | Kontrprzykład jury |
|---|---:|---:|---:|---|---|
| 1. Technologia i gotowość demo (30%) | 5,0 | 6,5 | 7,5 | Na żywo: replay 1313 materiałów, kolejka z momentem dowodu, M2 z 3 widokami, WebSocket, decyzje z rewizją. Testy przechodzą: 93 analysis, 222 core, 65 collectors. Pokazu nie przećwiczono na Macu. Compose nie montuje paczki mediów, PDF i scenariusz są nieaktualne, E5 ma stan `unavailable` | „Uruchomcie to jedną komendą u nas.” Kolejka w Compose wyjdzie pusta albo padnie zależność arm64 |
| 2. Innowacyjność procesu z AI (20%) | 6,0 | 7,5 | 8,5 | Linie, kontrakty, niezależni oceniający z kappa, zamrożony protokół, kontrprzykłady, porównanie z Qwen i log sesji. Brak CI i automatycznej bramki w repo | „To 137 wierszy rejestru i setki stron, a gdzie standard (CI, PR review)?” Obszerność może wyglądać na „AI slop” |
| 3. Architektura (20%) | 5,0 | 6,0 | 7,0 | Czytelny podział collectors/analysis/api/web, kontrakt v2 z wersjami i migracją, adaptery wymienne, warianty kwalifikacji z historią. SQLite i Huey na jednym hoście, frontend serwowany przez API, brak Dockerfile | „Jak to skalować na 10 tys. kanałów i 5 analityków?” „Dlaczego AI nie jest osobną usługą?” |
| 4. Zgodność ze specyfikacją i technologiami (20%) | 3,5 | 4,5 | 5,5 | Brak FB/IG z nazwy, TikTok poza demo, brak rotacji UA/proxy, brak wykresu trendu, M3 bez kandydata, M2 w większości BD. Ollama/vLLM poza produktem, audyt nieaktualny | „Brief wymienia Facebook, Instagram i TikTok. Pokażcie choć jeden rekord.” |
| 5. Atrakcyjność (10%) | 5,5 | 7,0 | 8,0 | Wyróżnik: rozdział rejestru reklam od alarmu, bramka mowy, link do sekundy, kontrdowód, pomiar ekranu M2 | „Cztery alarmy, wszystkie XTB, zero w M2 rynkowym poza ETF, zero w M3. Co tu zaskakuje?” |
| **Wynik ważony** | **4,95** | **6,25** | **7,25** | Wewnętrzny panel z b572eda8 dał 7,0–8,1. Obniżam, bo tamta wersja to nie bieżący pokaz, a nowe elementy nie mają próby na sprzęcie pokazu | |

### Co działa na żywo, a co tylko w testach lub dokumentach

| Na żywo (API 18801, sprawdzone GET) | Tylko testy lub fiksury | Tylko dokumenty lub plan |
|---|---|---|
| Kolejki review 4, adRegister 264, offersM2 3, offersM3 2, incomplete 208. Próg 60 z historią. Wariant `qual_d` z `validationRef`. 19 ID dla ETF. Zdarzenia i trend z API | M2 ID 2, 4, 9–18 (syntetyczne). Kontrola Ollama (atrapa serwera). Ścieżka Mac (atrapy). Qwen v2 (OpenRouter, płatne) | Walidacja ekspercka, odłożony test M1, FB/IG, rotacja UA/proxy, Mac M3, aktualny audyt, film |

## 3. Co poprawić: priorytet według „punkty na godzinę agenta”

Zysk podaję w punktach wyniku ważonego 0–10. Pozycja 1 chroni głównie przed spadkiem.

| # | Pozycja | Kategoria i wymóg | Zysk | Nakład | Ryzyko | Zależność |
|---|---|---|---:|---|---|---|
| 1 | Próba generalna na Macu M3: zamontować `.runtime/replay-media` w `compose.yaml` (lub `INVESTWATCH_REPLAY_MEDIA`), uruchomić `ops/mac/check.sh`, potem 2 zimne starty offline i przejście scenariusza. Wariant awaryjny: uvicorn z venv z tą samą bazą. Potwierdzić E5 `available` | 1 (30%), R-§5-03, §6 | +0,3…+0,6 (uniknięty spadek do −1,5) | M | arm64 Vosk i E5, pamięć VM | J z Makiem; skopiować paczkę i bazę replay |
| 2 | Nowy scenariusz `demo.md` i PDF dla obecnego produktu: 1 alarm M1 kontra 1 poprawna reklama, ETF M2, BOŚ M3 jako kontrola, źródła ze statusami, kalibracja, uczciwe granice | 1, 5, §4 | +0,3 | S–M | niskie | po pozycjach 3–5 |
| 3 | Kalibracja na zbiorze q-v2 (26 materiałów, 20 kampanii, `qual_d`) zamiast starych 13. Pokazać porównanie `rules_1_2` i `qual_d` oraz zastosowanie progu do rzeczywistej kolejki z przywróceniem | 1, 4, §6 „trafność i próg” | +0,25 | S | Krzywa `qual_d` jest płaska między 60 a 80. Trzeba to powiedzieć wprost | dane q-v2 w repo |
| 4 | Źródła social: TikTok z `watch.sqlite3` do replay demo i do „Źródeł”. FB i IG jako wiersze „blokada dostępu” z datowaną próbą (HTTP, ściana logowania, wymagany interfejs) i kolejnym krokiem | 4 (20%), R-§2-02…04 | +0,2…+0,3 | S–M | Bez logowania i obchodzenia zabezpieczeń | `collectors/social.py`, `api/jobs.py` (H) |
| 5 | Wykres trendu w pulpicie z `/v1/trend` (komponent Astryx lub Recharts) | 4, R-§3.3-06 | +0,15 | S | niskie | J1 |
| 6 | Aktualny `npm audit` (lock React 19/Astryx) i `pip-audit`, raporty w repo, `.env.example` | 4, §6 „biblioteki”, R-§5-07…09 | +0,1…+0,15 | S | Wysyła listę pakietów do publicznych rejestrów | zgoda J |
| 7 | Konfigurowalna pula UA i opcjonalne proxy w `collectors/common.py` z testem. Opisać jako zgodność ze specyfikacją na uprawnionych trasach, nie jako obchodzenie limitów | 4, R-§3.1-05/06 | +0,1 | S | wizerunkowe, gdy źle opisane | brak |
| 8 | M3: 3–5 prospektywnie znalezionych publicznych ofert „doradca inwestycyjny / wealth management / family office” spoza wykazu KNF, przepuszczonych przez obecną ścieżkę i rejestr, ze statusem „uprawnienia do ustalenia”, bez zarzutu | 4, R-§2-M3-01…06 | +0,2 | M | Prawne przy złym słownictwie. Wynik może być pusty | sieć na hoście, F/H |

Suma realistyczna to około +1,0 pkt, czyli z 6,25 do około 7,2. Kolejność: 1 → 3 → 4 → 5 → 6 → 7 → 8 → 2. PDF na końcu, bo opisuje wynik pozostałych.

**Nie warto przed pokazem:**
- Kolektor X: poza briefem, a API jest płatne.
- Scraping FB/IG za logowaniem: regulamin, ryzyko prawne przed regulatorem.
- Dalsze strojenie próby Y (frazy krypto): nie zmienia oceny jury i zużywa kwotę.
- Kolejne przebiegi Qwen przez OpenRouter: płatne API stoi w sprzeczności z §5. Qwen 9B nie wniósł nic ponad reguły D.
- Migracja na Postgres lub k8s.
- Nowe syntetyczne testy M2 zamiast jednego prawdziwego materiału.
- Dopisywanie dokumentacji (ryzyko „AI slop”).
- Skan YouTube na żywo w trakcie pokazu (429 i kwota).
- Ollama jako decydent w kolejce. Najwyżej pokazać ją jako drugą opinię na Macu, jeśli pozycja 1 przejdzie bez problemów.

## 4. Nowe źródła czy tylko YouTube

Co brief mówi dosłownie (§2): „centralnego silnika zbierającego dane (z Internetu oraz mediów społecznościowych, m.in. Facebook, Instagram, TikTok)”. §3.1 dodaje „kolektorów API lub parserów treści dla Social Mediów, przy zachowaniu rotacji User-Agent w nagłówkach i proxy”. Obowiązkowe są więc strony WWW i social media. Z nazwy padają **tylko FB, IG i TikTok**, a „m.in.” otwiera listę. YouTube i X nie występują w briefie (zgodnie z `ODBIOR-UKNF.md` P-01 i P-02).

| Strategia | Co powie jury UKNF | Wykonalność do pokazu | Wpływ punktowy (kat. 4, na wynik) |
|---|---|---|---|
| (a) Głęboko YouTube (filmy i Shorts), reszta minimalnie | „Dobra analiza jednego kanału, ale nie tego, o który prosiliśmy z nazwy” | Już jest. Shorts obsłużone (`isShort`, `collectors/youtube.py:441`), choć kadry Shorts mają 101×180 | 0 (zostaje 4,5/10) |
| **(b) YouTube + TikTok, FB/IG jako jawna blokada** | „Pokazali drugą platformę z listy i uczciwie zbadali granice dostępu” | TikTok: publiczne osadzenie profilu i oEmbed bez logowania, adapter i 2 profile już są (`collectors/social.py`, `data/probe-snapshots/social/`). Ograniczenia: 10 ostatnich postów, bez dat, tylko podpis. Odkrywanie przez odsyłacze z opisów YouTube (`collectors/crosslinks.py`). FB/IG: publiczne profile i oEmbed wymagają logowania lub tokenu aplikacji Meta. Ad Library API wymaga konta deweloperskiego i weryfikacji (do potwierdzenia datowaną próbą) | +0,5…+1,0 w kat. 4, czyli +0,1…+0,2 |
| (c) Szeroko po wszystkich | „Dużo kafelków, nic nie działa do końca” | Nieuczciwie wykonalne: FB/IG wymagałyby obejścia logowania, X płatnego API. Ryzyko awarii pokazu | Ujemny przez kat. 1 |

**Rekomendacja: (b).** TikTok jest jedyną platformą z listy briefu, którą da się dziś pokazać legalnie i bez logowania, a adapter już istnieje. Wystarczy go włączyć do replay i do „Źródeł”. Niepokryte źródła pokazujcie jako status „blokada dostępu” z datą, metodą próby, odpowiedzią (kod HTTP lub ściana logowania), wymaganym interfejsem (Meta Content Library lub Ad Library API po akredytacji instytucji) i kolejnym krokiem. Nie pokazujcie ich jako pustego „brak”. Dla regulatora uczciwa granica jest argumentem: UKNF może sam wystąpić o dostęp instytucjonalny, a system ma gotowe miejsce na adapter.

## 5. Trzy najsłabsze punkty i odpowiedź w jednym zdaniu

| Pytanie jury | Odpowiedź |
|---|---|
| „Gdzie Facebook i Instagram?” | „Oba wymagają logowania lub tokenu Meta, którego hackathon nie daje. Pokazujemy datowaną próbę i status blokady, a adapter podłączymy po uzyskaniu przez UKNF dostępu instytucjonalnego.” |
| „Jak trafny jest model i skąd ta liczba?” | „Na 26 materiałach z 20 kampanii nowy wariant ma 0 fałszywych alarmów wobec 7 dla reguł bazowych. To jednak zbiór strojenia z etykietami agentów, więc deklarujemy przesiew do przeglądu, nie skuteczność, a walidację ekspercką proponujemy jako pierwszy krok pilota.” |
| „Pokażcie nieuprawnionego doradcę (M3)” | „Pokazujemy pełną ścieżkę na autoryzowanym BOŚ jako kontroli dodatniej i na materiale edukacyjnym jako kontroli ujemnej, a wskazanie konkretnego podmiotu jako nieuprawnionego wymaga ustalenia rejestru i zakresu, czego system nie przesądza.” Odpowiedź będzie słaba, dopóki nie powstanie pozycja 8 |

## Ograniczenia tej oceny

- Nie uruchamiałem Chromium, Compose, modeli ani skanów. UI oceniłem po kodzie i API, a stabilności i konsoli przeglądarki nie widziałem.
- Problem z montowaniem replay-media w Compose stwierdziłem statycznie (`compose.yaml` i `api/replay_pack.py`), bez uruchomienia.
- API 18801 to instancja z venv. Może nie mieć E5 i workera, a w Compose 8769 bywa inaczej.
- Punktacja jury to szacunek eksperta, nie pomiar. Wagi i skala pochodzą z §8.
- Dostępność FB/IG/TikTok oceniam z kodu, sond w repo i wiedzy ogólnej, bez nowych żądań sieciowych. Warunki Meta wymagają datowanej próby.
- Polecenia uruchomione: unittest `analysis` (93 OK, 2 pominięte), `tests/core` (222 OK), `collectors` (65 OK) na pustym `INVESTWATCH_STATE` oraz `tools/check_plan_evidence.py` (OK).
