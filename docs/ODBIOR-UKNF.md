# Rejestr wymagań i macierz odbioru InvestWatch

> **Rejestr OTWARTY.** Statusy opisują dowody w repozytorium 21 XI 2026 (HEAD 491094d). Rejestr zamyka się dopiero na końcowym kandydacie. Wtedy A sprawdza każdy wiersz na tej samej wersji, którą zobaczy jury ([próba R](fable/ODBIOR.md)). Do tego czasu „zaliczone” oznacza dowód dla stanu odniesienia, nie dla przyszłego kandydata.

Wymagania pochodzą z [pięciu plików konkursu](zrodla-uknf/README.md), ZIP SHA-256 `ad609dbb…5018043` (sprawdzone 21 XI). Wątpliwe fragmenty porównano z oryginałem PDF i DOCX, m.in. brak YouTube i X w briefie oraz brzmienie 12a/12b. Priorytety mentora i J oraz decyzje zespołu są w sekcjach 7–8, osobno od wymagań ZIP.

**Stan odniesienia.** Dowody poprzedniego demo pochodzą z bazy eaa9c10 i odcisku kodu `b572eda8…` ([raport](../tests/offline/proof-zip-2026-11-21.json)). Dzisiejszy `python3 tests/offline/verify.py --root "$PWD" --fingerprint-only` zwraca `89a8e544…`. Bieżące drzewo nie jest więc tą wersją. Każdy wiersz „zaliczone” wymaga powtórzenia próby. Pełna poprzednia macierz jest w [sekcji 10](#10-stan-odniesienia-poprzednia-macierz).

## Jak czytać

- **ID.** `R-§n-…` to brief PDF, gdzie §2-M1/M2/M3 oznacza moduł. `T1-`, `T2-` i `T3-` to załączniki tematów. `K-` to 19 kryteriów M2 z osobnymi K-12a i K-12b.
- **Zakres.** M1, M2, M3 albo wspólne.
- **Charakter.** Wiersz jest *obowiązkowy*, jeśli brief go wymaga. *Definicja* to definicja zakresu z DOCX. *Przykład technologii* oznacza, że wymóg dotyczy funkcji, a nazwa narzędzia jest przykładem. *Opcjonalne* to „może” lub „możliwość”. *Zasób organizatora* to coś, co dostarcza UKNF. *Kryterium jury* to punkt oceny z §6 lub §8.
- **Wykonawca.** Litera z [tabeli przydziałów](fable/REALIZACJA.md): B YouTube, C multimedia, D M1 i kwalifikacja, E M2, F M3, G dane i walidacja, H integracja i API, I UX, J1 UI, K pozostałe źródła, L operacje, M QA, N demo, O/P sędziowie. J oznacza decyzję lub czynność samego J.
- **Status.** Dopuszczalne wartości to zaliczone / częściowe / brak / blokada dostępu / poza obowiązkowym zakresem. Opierają się wyłącznie na plikach w repo. Wiersz jest „częściowy”, jeśli mechanizm istnieje, a brakuje dowodu rynkowego lub pełnego zakresu.
- **Test.** Testy Y, Q, U i R1–R5 są opisane w [próbach odbiorowych](fable/ODBIOR.md). Komendy podano dosłownie.

## Podsumowanie

| Status | Liczba |
|---|---:|
| zaliczone | 41 |
| częściowe | 75 |
| brak | 17 |
| blokada dostępu | 0 |
| poza obowiązkowym zakresem | 4 |
| **razem** | **137** |

W tym 92 wiersze briefu, 26 wierszy załączników tematów i 19 kryteriów M2. Wszystkie 17 wierszy „brak” jest obowiązkowych lub ma charakter definicji. Wymienia je [sekcja 6](#6-obowiązkowe-wiersze-bez-dowodu). Żaden wiersz nie ma dziś statusu „blokada dostępu”, bo w repo nie zapisano jeszcze odmowy dostępu do FB, IG ani YouTube Data API. Status zmieni się po raporcie K lub B.

## 1. Brief §1–2: cel, silnik i moduły

| ID | Wymaganie | Źródło i cytat | Zakres | Charakter | Wyk. | Status | Test | Materiał |
|---|---|---|---|---|---|---|---|---|
| R-§1-01 | Automatyczna identyfikacja, agregacja i analiza promocji i ofert instrumentów i usług finansowych na polskim rynku | [Brief s.1 §1](zrodla-uknf/BRIEF.md#strona-1): „automatyczną identyfikację, agregację i analizę materiałów promocyjnych oraz ofert” | wspólne | obowiązkowe | H | częściowe | Y, R2 | `tests/offline/proof-zip-2026-11-21.json` (20 spraw replay). Samodzielne odkrywanie obejmuje Apple Podcasts, PeerTube i odsyłacze. YouTube to tylko 2 kanały startowe |
| R-§1-02 | Uniwersalny silnik scrapingu i trzy wyspecjalizowane moduły analityczne | s.1 §1: „uniwersalnym silniku web scrapingu oraz trzech wyspecjalizowanych modułach” | wspólne | obowiązkowe | H | zaliczone | R2 | `collectors/`, `analysis/engine.py`, `api/jobs.py` |
| R-§2-01 | Centralny silnik pobiera dane z Internetu (WWW) | s.1 §2: „centralnego silnika zbierającego dane (z Internetu” | wspólne | obowiązkowe | H, K | zaliczone | `python3 tools/check_plan_evidence.py`, R2 | `collectors/sites.py`, `fixtures/validation/bossa-discovery-2026-11-21.json`, `data/probe-snapshots/2026-11-21-discovery-check.json` |
| R-§2-02 | Pozyskiwanie danych z Facebooka | s.1 §2: „m.in. Facebook, Instagram, TikTok” | wspólne | obowiązkowe | K | brak | R2, raport niedostępności K | Kolektora nie ma. [Monitoring](MONITORING.md) wymienia Meta Ad Library tylko jako źródło do sprawdzenia |
| R-§2-03 | Pozyskiwanie danych z Instagrama | jw. | wspólne | obowiązkowe | K | brak | R2, raport niedostępności K | Kolektora nie ma |
| R-§2-04 | Pozyskiwanie danych z TikToka | jw. | wspólne | obowiązkowe | K | częściowe | R2, świeży odczyt K | `collectors/social.py`, `data/probe-snapshots/social/2026-11-21-source-check.json`: 2 profile po 10 podpisów, bez dat i bez odkrywania |
| R-§2-05 | Inne media społecznościowe z otwartej listy, w tym YouTube i podcasty | s.1 §2: „m.in.” | wspólne | obowiązkowe (lista otwarta) | B, K | częściowe | Y | YouTube Atom dla 2 kanałów z `tools/watch_sources.json`, Apple Podcasts i PeerTube w `collectors/catalogs.py`. Brak wyszukiwania YouTube |
| R-§2-M1-01 | Wyszukiwanie reklam firm inwestycyjnych zarejestrowanych w PL oraz ich instrumentów i usług, publikowanych przez osoby trzecie, zwłaszcza finfluencerów | s.1 M1: „zamieszczane przez podmioty trzecie lub osoby prywatne (w szczególności finfluencerów)” | M1 | obowiązkowe | B, D | częściowe | Y, Q | „Partnerem odcinka jest XTB” w 2 publikacjach monitorowanego kanału (`data/probe-snapshots/2026-11-21-discovery-check.json`). Nowy twórca z PeerTube nie miał reklamy ([próba](M3-WERYFIKACJA-2026-11-21.md)) |
| R-§2-M1-02 | Polskojęzyczne reklamy zagranicznych firm działających w PL transgranicznie | s.1 M1: „także polskojęzyczne reklamy zagranicznych firm inwestycyjnych działających w Polsce transgranicznie” | M1 | obowiązkowe | D, B | brak | Y (firma transgraniczna) | Brak przykładu. Kandydaci są tylko w `data/probe-snapshots/knf/knf_notyfikacje_zagr_FI.json` |
| R-§2-M1-03 | Raport: dane firmy inwestycyjnej | s.1 M1 Rezultat: „dane firmy inwestycyjnej” | M1 | obowiązkowe | D, H | częściowe | Y, U | Marka pochodzi z cytatu. Dowody nie pokazują powiązania reklamy M1 z wpisem rejestru KNF |
| R-§2-M1-04 | Raport: dane podmiotu reklamującego | „dane podmiotu reklamującego” | M1 | obowiązkowe | D, H | częściowe | Y, U | ID kanału, handle i autor ze źródła (`tools/watch_sources.json`, `fixtures/raw/discovery/2026-11-21.json`) |
| R-§2-M1-05 | Raport: treść reklamy | „treść reklamy” | M1 | obowiązkowe | D, C | częściowe | Y, Q | Dosłowny cytat z opisu. Mowa jest analizowana tylko w klipach syntetycznych (`analysis/media/`). Promocja wyłącznie w mowie lub obrazie na rynku nie była badana |
| R-§2-M1-06 | Raport: dokładna lokalizacja (URL) | „jej dokładną lokalizację (URL)” | M1 | obowiązkowe | D, H | zaliczone | `python3 tools/check_plan_evidence.py` | 2 URL publikacji w `data/probe-snapshots/2026-11-21-discovery-check.json` |
| R-§2-M1-07 | Raport lub baza tworzone automatycznie | „Automatyczny raport/baza” | M1 | obowiązkowe | H | częściowe | Y, R2 | `tools/watch_sources.py report` (raporty w `.runtime/watch/`, poza Gitem) i kolejka API. Zakres rynkowy to 4 profile |
| R-§2-M1-08 | Mechanizm okresowej aktualizacji | „wraz z mechanizmem okresowej aktualizacji” | M1 | obowiązkowe | L, H | częściowe | R2 (potwierdzenie harmonogramu) | `ops/user-systemd/`, `INVESTWATCH_DISCOVERY_INTERVAL`. Były dwa ręczne wyzwolenia, ale dziennik nie zawiera automatycznego ([Monitoring](MONITORING.md)) |
| R-§2-M2-01 | Wyszukiwanie materiałów marketingowych publikowanych bezpośrednio przez firmy inwestycyjne zarejestrowane w PL | s.1 M2: „publikowanych bezpośrednio przez zarejestrowane w Polsce firmy inwestycyjne” | M2 | obowiązkowe | E | częściowe | R1 | 3 oferty z 2 domen (XTB, BDM), stała lista `TARGETS` w `collectors/m2_archive.py`. Brak automatycznego odkrywania nowych firm |
| R-§2-M2-02 | W tym polskie oddziały firm zagranicznych | „(w tym polskie oddziały firm zagranicznych)” | M2 | obowiązkowe | E | brak | R1 (oddział zagraniczny) | `data/probe-snapshots/knf/knf_oddzialy_zagr_FI.json` służy tylko jako źródło |
| R-§2-M2-03 | AI lub statystyka ocenia, czy informacja o ryzyku jest dostateczna | s.1 M2 Analiza: „w sposób dostateczny” | M2 | obowiązkowe | E | częściowe | Q, R1 | Reguły w `analysis/checks.py`. W M2 nie ma oceny lokalnym modelem |
| R-§2-M2-04 | Ryzyko proporcjonalne do informacji o zyskach | „proporcjonalny do informacji o zyskach” | M2 | obowiązkowe | E | częściowe | Q, R1 | ETF: dywidendy kontra ostrzeżenie ETF, K-3 jako obserwacja (`data/probe-snapshots/m2/manifests/xtb-etf.json`) |
| R-§2-M2-05 | Ryzyko podane wyraźnie | „oraz wyraźny” | M2 | obowiązkowe | E | częściowe | R1 | Geometria, kontrast i przesłonięcie: `collectors/m2_browser.js`, `tests/e2e/m2_control.py` |
| R-§2-M2-06 | Ocena według listy wymogów z załącznika | „(zgodnie z listą wymogów w załączniku)” | M2 | obowiązkowe | E | częściowe | R1 | Wszystkie 19 ID w [sekcji 5](#5-kryteria-m2-19-id) |
| R-§2-M2-07 | Automatyczne flagowanie materiałów niespełniających kryteriów | s.1 M2 Rezultat: „automatycznie flagujące materiały” | M2 | obowiązkowe | E, H | częściowe | Q, U | ETF trafia do przeglądu według reguł ([raport demo](DEMO-ODBIOR.md)) |
| R-§2-M3-01 | Wyszukiwanie ofert wealth management, investment consulting, family office i innych doradców spoza autoryzowanych firm | s.1 M3: „wealth management, investment consulting, family offices oraz innych podmiotów doradczych” | M3 | obowiązkowe | F | częściowe | R1 (podmiot spoza pary kontrolnej) | Ścieżka domena → oferta działa dla bossa.pl i financewell.pl (`collectors/sites.py`). Nie ma wyszukiwania nowych podmiotów |
| R-§2-M3-02 | Wykrywanie treści wskazujących na faktyczne doradztwo inwestycyjne w PL bez zezwolenia | s.1 M3 Analiza: „faktyczne świadczenie w Polsce usługi doradztwa inwestycyjnego” | M3 | obowiązkowe | F, D | częściowe | Q, R1 | E5: „My podpowiadamy co kupić i sprzedać, Ty decydujesz.” oraz kontrola edukacji. Oba przypadki dotyczą autoryzowanego BOŚ ([próba M3](M3-WERYFIKACJA-2026-11-21.md)) |
| R-§2-M3-03 | Ustalenie braku wymaganego zezwolenia na dzień oferty | „bez wymaganych zezwoleń” | M3 | obowiązkowe | F | częściowe | Q, R1 | Wpis KNF 8353437 z kodem 5 (`fixtures/validation/knf-extract-2026-11-21.json`). FinanceWell pozostaje nierozstrzygnięty |
| R-§2-M3-04 | Raport: dane podmiotu | s.1 M3 Rezultat: „dane podmiotu” | M3 | obowiązkowe | F | częściowe | R1 | KRS i NIP ze stopki BOŚ (`fixtures/validation/bossa-discovery-2026-11-21.json`) |
| R-§2-M3-05 | Raport: treść oferty | „treść oferty” | M3 | obowiązkowe | F | częściowe | R1 | Pełny tekst oferty kontrolnej BOŚ, 5956 znaków |
| R-§2-M3-06 | Raport: URL potencjalnego naruszenia | „lokalizację (URL) potencjalnego naruszenia” | M3 | obowiązkowe | F | częściowe | R1 | URL jest zapisany. Na razie dotyczy kontroli, a nie potencjalnego naruszenia |

## 2. Brief §3: oczekiwany rezultat (MVP)

| ID | Wymaganie | Źródło i cytat | Zakres | Charakter | Wyk. | Status | Test | Materiał |
|---|---|---|---|---|---|---|---|---|
| R-§3.1-01 | Backend w .NET, Pythonie lub Node.js | [Brief s.2 §3.1](zrodla-uknf/BRIEF.md#strona-2): „Backend & Scraping Engine (.NET/Python/Node.js)” | wspólne | obowiązkowe (wybór z listy) | H | zaliczone | R3 | `api/server.py` (Python, FastAPI) |
| R-§3.1-02 | Kolejka zadań na narzędziu open source | „kolejki zadań w oparciu o dowolne narzędzie open source” | wspólne | obowiązkowe | L, H | zaliczone | R2 (przerwanie workera, dzierżawa) | Huey w `api/jobs.py`. Wznowienie po wygaśnięciu dzierżawy w `tests/offline/proof-zip-2026-11-21.json` |
| R-§3.1-03 | Biblioteki pobierania typu Playwright, Selenium, httpx, requests | „bibliotek typu Playwright, Selenium, httpx, requests itp.” | wspólne | przykład technologii | E, K | zaliczone | R2 | Playwright w `collectors/m2_browser.py`, urllib w `collectors/common.py` |
| R-§3.1-04 | Kolektory API lub parsery treści social media | „kolektorów API lub parserów treści dla Social Mediów” | M1 | obowiązkowe | B, K | częściowe | R2, Y | `collectors/social.py`: YouTube Atom i osadzenie TikTok. Brak Data API, FB i IG |
| R-§3.1-05 | Rotacja User-Agent w nagłówkach | „przy zachowaniu rotacji User-Agent w nagłówkach” | wspólne | obowiązkowe | L, K/B | brak | R2 | Stały nagłówek `InvestWatch-SourceMonitor/1.0` w `collectors/common.py` i `collectors/audio.py` |
| R-§3.1-06 | Rotacja proxy | „i proxy” | wspólne | obowiązkowe | L | brak | R2 (dwie uprawnione trasy) | W kodzie nie ma konfiguracji proxy |
| R-§3.1-07 | Ekstrakcja danych z HTML do formatu wyjściowego | „Ekstrakcja danych z HTML do formatu wyjściowego np. JSON” | wspólne | obowiązkowe (JSON to przykład) | H, K | zaliczone | R2 | `collectors/sites.py`, `fixtures/validation/bossa-discovery-2026-11-21.json` |
| R-§3.1-08 | Baza metadanych SQL | „Baza metadanych (SQL)” | wspólne | obowiązkowe | L, H | zaliczone | R2 | SQLite w `api/store.py` |
| R-§3.1-09 | Baza treści: SQL i magazyn obiektów | „Baza treści (SQL + np. Object Storage)” | wspólne | obowiązkowe (Object Storage to przykład) | L, H | zaliczone | R2 (kopia z załącznikami) | SQLite i pliki adresowane skrótem w `data/probe-snapshots/m2/assets/`. Nie zmierzono odtworzenia kopii z załącznikami |
| R-§3.1-10 | Harmonogram: CronJob lub orkiestrator | „CronJob jako mechanizm uruchamiania scrapperów lub system orchestratora” | wspólne | obowiązkowe (CronJob to przykład) | L | częściowe | R2 (potwierdzenie uruchomienia) | `ops/user-systemd/investwatch-watch.timer` i interwał workera. Brak zdarzenia automatycznego wyzwolenia |
| R-§3.2-01 | Moduły analityczne w Pythonie | s.2 §3.2: „Moduły Analityczne / AI (Python)” | wspólne | obowiązkowe | D, E, F | zaliczone | R3 | `analysis/` |
| R-§3.2-02 | Usuwanie tagów HTML | „Usuwanie tagów HTML” | wspólne | obowiązkowe | H | zaliczone | R2 | `collectors/sites.py` (HTMLParser), pełny tekst bez znaczników w `fixtures/validation/bossa-discovery-2026-11-21.json` |
| R-§3.2-03 | Normalizacja tekstu | „normalizacja tekstu” | wspólne | obowiązkowe | H, D | zaliczone | R2 | Scalanie białych znaków w `collectors/sites.py` i `collectors/common.py`, casefold przy dopasowaniu |
| R-§3.2-04 | Usuwanie duplikatów | „usuwanie duplikatów” | wspólne | obowiązkowe | H | zaliczone | R2, Y (duplikat Atom/API) | Drugi odczyt: 50 z 50 bez zmian ([Monitoring](MONITORING.md)). Replay → live bez dublowania (`tests/core/test_live_lineage.py`) |
| R-§3.2-05 | Reprezentacja tokenowa | „w postaci tokenów” | wspólne | obowiązkowe | D, F | zaliczone | R2 | E5, 128 tokenów na fragment (`analysis/semantic.py`, `analysis/semantic-lock.json`) |
| R-§3.2-06 | Embeddingi | „i embeddingów” | wspólne | obowiązkowe | D, F | zaliczone | R2 | jw. |
| R-§3.2-07 | Silnik inferencji | „Dowolny silnik inferencji: vllm, lama.cpp lub ollama” | wspólne | obowiązkowe (wymienione to przykłady) | L, D | zaliczone | R2, R3 | Lokalnie ONNX (E5) i Vosk. Nie ma vLLM, llama.cpp ani Ollama (zob. W3) |
| R-§3.2-08 | Otwarty model albo klasyfikator | „Model open source np. Gemma4 lub klasyfikator np. BERT” | wspólne | przykład technologii | D, F | zaliczone | R3 | multilingual-e5-small (MIT) i Vosk PL (Apache 2.0) ([licencje](DEMO-ODBIOR.md)) |
| R-§3.2-09 | Klasyfikacja ryzyka funkcją scoringową przypisującą kategorię z warstwy wyjściowej | „Klasyfikacja ryzyka poprzez funkcje scoringowe” | wspólne | obowiązkowe | D, E, F, G | częściowe | Q, R2 | Punkty reguł i `reviewSuggestion.state` w `analysis/engine.py` i `analysis/semantic.py`. Brak skalibrowanej kategorii |
| R-§3.2-10 | Agregator łączący wyniki M1, M2 i M3 we wspólne obiekty | „Agregator wyników, łączący wyniki,1,2,3 w ujednolicone obiekty” | wspólne | obowiązkowe | H | zaliczone | R2 | Capture, Finding i Case ([kontrakty](hackathon/contracts.md)), `api/store.py` |
| R-§3.3-01 | Dashboard w React, Vue lub Angular | s.2 §3.3: „Aplikacja Webowa (Dashboard) (React/Vue/Angular)” | wspólne | obowiązkowe | J1 | zaliczone | U | `web/app.js` (React 18), `web/src/` (React 19 i Astryx) |
| R-§3.3-02 | Filtr po dacie | „z filtrowaniem po dacie, źródle, poziomie ryzyka i module” | wspólne | obowiązkowe | J1 | zaliczone | U | [Raport UI](DEMO-ODBIOR.md) |
| R-§3.3-03 | Filtr po źródle | jw. | wspólne | obowiązkowe | J1 | zaliczone | U | jw. |
| R-§3.3-04 | Filtr po poziomie ryzyka | jw. | wspólne | obowiązkowe | J1 | zaliczone | U | jw. |
| R-§3.3-05 | Filtr po module analitycznym | jw. | wspólne | obowiązkowe | J1 | zaliczone | U | jw. |
| R-§3.3-06 | Wykres trendu, np. liczby incydentów w czasie | „Wykresy trendów … Chart.js lub Recharts” | wspólne | obowiązkowe (biblioteka to przykład) | J1 | zaliczone | U | Komponent `Trend` w `web/app.js` z własnymi słupkami. W nowym głównym widoku zachowanie wykresu wymaga sprawdzenia |
| R-§3.3-07 | Zmiana statusu rekordu | „Funkcjonalność zmiany statusu rekordu” | wspólne | obowiązkowe | H, J1 | zaliczone | U | `api/server.py`: new, reviewing i closed z rewizją i 409 |
| R-§3.3-08 | WebSocket powiadamia o wysokim ryzyku w czasie rzeczywistym | „WebSocketów np. Socket.io dla powiadomień o wykryciu wysokiego ryzyka” | wspólne | obowiązkowe (Socket.io to przykład) | H, J1 | częściowe | U (druga sesja), R2 (reconnect) | `/v1/events` w `api/server.py`. Nie zmierzono dostarczenia alertu do drugiej sesji ani po reconnect |
| R-§3.3-09 | Panel kalibracji z progiem | „Implementacja parametru progowego (threshold)” | wspólne | obowiązkowe | J1, G | zaliczone | U | `web/app.js`, `/v1/calibration` |
| R-§3.3-10 | Zmiana progu zmienia liczbę FP i FN | „Zmiana wartości treshold bezpośrednio wpływa na liczbę wyników False Positive vs False Negative” | wspólne | obowiązkowe | G, J1 | częściowe | Q, U | 13 grup z etykietami autora: przy progu 30 FP 1 i FN 2, przy 80 FP 0 i FN 5. Nie zmierzono skutku na rzeczywistej kolejce |
| R-§3.3-11 | Otwarte biblioteki UI | „Możliwość korzystania z bibliotek do UI open source” | wspólne | opcjonalne | J1 | poza obowiązkowym zakresem | U | Astryx 0.7.17 (MIT) w `web/package.json` |
| R-§3.3-12 | Architektura oparta na propsach | „Architektura oparta o propsy” | wspólne | obowiązkowe | J1 | zaliczone | U, `node tests/ui/render-smoke.cjs` | `web/app.js`, np. `El(Trend, { findings })`, `web/src/neutral-desk.jsx` |

## 3. Brief §4–8: zgłoszenie, wymagania techniczne, ocena i zasoby

| ID | Wymaganie | Źródło i cytat | Zakres | Charakter | Wyk. | Status | Test | Materiał |
|---|---|---|---|---|---|---|---|---|
| R-§4-01 | Szczegółowy opis i tytuł projektu | [Brief s.3 §4](zrodla-uknf/BRIEF.md#strona-3): „szczegółowy opis i tytuł projektu” | wspólne | obowiązkowe | N (zgłoszenie J) | częściowe | R5 | `HACKATHON.md`, `README.md`. Treść w systemie konkursu potwierdza J |
| R-§4-02 | Prezentacja PDF | „prezentację w formacie PDF” | wspólne | obowiązkowe | N | zaliczone | R5 | `presentation/InvestWatch.pdf`, stan poprzedniego demo |
| R-§4-03 | Opis kodu lub README | „opis kodu/readme” | wspólne | obowiązkowe | N | zaliczone | R3, R5 | `README.md`, `analysis/README.md`, `ops/demo/README.md` |
| R-§4-04 | Repozytorium kodu | „repozytorium kodu” | wspólne | obowiązkowe | N, J | zaliczone | R5 | 491094d na origin/main. Wysyłkę potwierdza J |
| R-§4-05 | Film do 3 minut | „Dodatkowo może zawierać: krótki film” | wspólne | opcjonalne | N | poza obowiązkowym zakresem | R5 | Brak |
| R-§5-01 | Modułowa architektura lekkich serwisów: osobny frontend, backend i AI | s.3 §5: „separacja Frontendu, Backend-u i silnika AI” | wspólne | obowiązkowe | H, L | częściowe | R2, R4 | Osobne katalogi `web/`, `api/`, `analysis/`, `collectors/`. `compose.yaml` ma 2 usługi: API serwuje frontend, a AI działa w workerze |
| R-§5-02 | Przejrzysty podział zamiast ciężkiego monorepo | „unikając ciężkich struktur monorepo” | wspólne | obowiązkowe | L | zaliczone | R4 | Jedno repo podzielone katalogami, bez narzędzi monorepo |
| R-§5-03 | Docker Compose uruchamia cały stos on-premise jedną komendą, powtarzalnie dla kilku osób | „uruchomienie całego stosu on-premise jedną komendą” | wspólne | obowiązkowe | L | częściowe | R3 (trzy czyste starty) | `sh ops/demo/start.sh`, trzy starty offline po 20 spraw. Pierwszy start wymaga na hoście Pythona 3.12, FFmpeg i bootstrapu ([ops](../ops/demo/README.md)) |
| R-§5-04 | Wyłącznie darmowe modele AI | „wyłącznie darmowych modeli AI” | wspólne | obowiązkowe | L | zaliczone | R3 | E5 (MIT), Vosk (Apache 2.0). Prawa do konwersji ONNX są nierozstrzygnięte |
| R-§5-05 | Otwarte bazy danych i biblioteki | „otwartych baz danych i bibliotek” | wspólne | obowiązkowe | L | zaliczone | R3 | SQLite, Huey, FastAPI, React, Astryx (MIT) |
| R-§5-06 | Bez zewnętrznych płatnych API | „całkowicie eliminując zewnętrzne, płatne API” | wspólne | obowiązkowe | L | zaliczone | R3 (start offline) | Kod nie korzysta z płatnych API (zob. W5) |
| R-§5-07 | Obowiązkowe skanowanie zależności npm i pip | „obowiązkowe skanowanie zależności (npm, pip) narzędziami typu Snyk” | wspólne | obowiązkowe (Snyk to przykład) | L | częściowe | R3 | Archiwalnie pip-audit (37 wersji) i npm audit dla React 18.3.1. Graf Astryx i React 19 z `web/package-lock.json` nie był audytowany |
| R-§5-08 | Usunięcie wykrytych podatności | „w celu eliminacji podatności … npm audit / npm fix” | wspólne | obowiązkowe | L | częściowe | R3 | 0 znanych podatności w zakresie archiwalnym. Stan nowego grafu nieznany |
| R-§5-09 | Ścisła izolacja sekretów w .env | „ścisła izolacja sekretów w plikach .env” | wspólne | obowiązkowe | L | częściowe | R3, przegląd repo | `.gitignore` wyklucza `.env*`. Brak `.env.example` i opisu sekretów |
| R-§5-10 | README zawiera Quick Start | „jasna instrukcja uruchomienia (Quick Start)” | wspólne | obowiązkowe | N | zaliczone | R3 | `README.md` |
| R-§5-11 | README zawiera wymagania sprzętowe | „lista wymagań sprzętowych” | wspólne | obowiązkowe | N | zaliczone | R3 | `README.md` (4 vCPU, 8 GiB) |
| R-§5-12 | README opisuje konfigurację serwisów | „opis konfiguracji serwisów” | wspólne | obowiązkowe | N | zaliczone | R3 | `README.md`, `ops/demo/README.md` |
| R-§5-13 | README bez zbędnych treści | „bez zbędnych treści. Bez AI Slop.” | wspólne | obowiązkowe | N | zaliczone | R4 | `README.md` ma 19 wierszy. Ocenę na kandydacie wydają O/P |
| R-§6-01 | Skuteczność scrapingu i poprawność pobierania | [Brief s.4 §6](zrodla-uknf/BRIEF.md#strona-4): „poprawność pobierania danych ze źródeł” | wspólne | kryterium jury | M, B, K | częściowe | Y, R2, `python3 tools/check_plan_evidence.py` | Sondy z SHA-256 i dwa identyczne odczyty. Pokrycia rynku nie oszacowano |
| R-§6-02 | Trafność klasyfikacji ryzyka przez AI | „Trafność klasyfikacji ryzyka przez moduły AI” | wspólne | kryterium jury | G | częściowe | Q (bramka produktowa) | `fixtures/labeled/calibration.json`: 13 pozycji z etykietami autora. Brak niezależnej próby |
| R-§6-03 | Wpływ progu na wyniki w panelu kalibracji | „wpływ zmian parametrów progowych na wyniki” | wspólne | kryterium jury | G, J1 | częściowe | U, Q | Jak R-§3.3-10 |
| R-§6-04 | Stabilność i płynność interfejsu | „Stabilność i płynność działania interfejsu webowego” | wspólne | kryterium jury | J1, M | częściowe | U (390 i 1440 px) | Chromium bez błędów JS na b572eda8. Znany problem dotyku w starym pulpicie ([raport](DEMO-ODBIOR.md)) |
| R-§6-05 | Powiadomienia w czasie rzeczywistym | „oraz powiadamiań w czasie rzeczywistym” | wspólne | kryterium jury | H, J1 | częściowe | U, R2 | Jak R-§3.3-08 |
| R-§6-06 | Użyte biblioteki i ich bezpieczeństwo | „Użyte biblioteki i ich bezpieczeństwo” | wspólne | kryterium jury | L | częściowe | R3 | Jak R-§5-07 |
| R-§6-07 | Console.log | „Console.log” | wspólne | kryterium jury | M | zaliczone | R3 (konsola przeglądarki), `grep -rn console.log web/app.js web/src` | 0 wystąpień w `web/app.js` i `web/src/` 21 XI, brak błędów JS na b572eda8 (zob. W6) |
| R-§6-08 | Ocena na prezentacji: działające demo | „podczas prezentacji/ demo projektu” | wspólne | kryterium jury | N, M | częściowe | R3, R5 | [Scenariusz](hackathon/demo.md), awaryjny replay. Brak próby na kandydacie |
| R-§7-01 | Próbki danych od organizatora (pendrive przy stoisku) | s.4 §7: „próbki danych zostaną dostarczone … pobrania danych na pendrive przy stoisku” | wspólne | zasób organizatora | J (odbiór), G (użycie) | poza obowiązkowym zakresem | brak | Próbek nie ma w ZIP ani w repo ([pakiet](zrodla-uknf/README.md)). Nieodebrane (zob. W7) |
| R-§8-01 | Technologia i gotowość demo, 30% | s.4 §8 kryterium 1 | wspólne | kryterium jury | N, M | częściowe | R4 | Wewnętrznie SOL 25/30, TERRA 21/30 na b572eda8 ([oceny](JUDGING.md)) |
| R-§8-02 | Standaryzowany proces wytwarzania z asystentami AI, 20% | kryterium 2 | wspólne | kryterium jury | Fable, N | częściowe | R4 | `AGENTS.md`, `docs/lanes/`, `TEAM_BOARD.md`. Oceny 18/20 i 16/20 |
| R-§8-03 | Architektura: kompozycja, skalowalność, rozbudowa, 20% | kryterium 3 | wspólne | kryterium jury | H, L | częściowe | R4 | Oceny 16/20 i 14/20. SQLite i Huey na jednym hoście, skalowania nie zmierzono |
| R-§8-04 | Zgodność ze specyfikacją i preferowanymi technologiami, 20% | kryterium 4 | wspólne | kryterium jury | A | częściowe | R4 i ten rejestr | Oceny 14/20 i 12/20 |
| R-§8-05 | Atrakcyjność i unikalność, 10% | kryterium 5 | wspólne | kryterium jury | N, I | częściowe | R4 | Oceny 8/10 i 7/10 |

Część „Korzyści” (s.3) oraz §9–10 (s.5) to kontekst bez wymagań. Zawierają wdrożenie pilotażowe, nagrodę i kontakt z mentorami, więc nie mają osobnych wierszy.

## 4. Załączniki: Temat 1, Temat 2 i Temat 3

| ID | Wymaganie | Źródło i cytat | Zakres | Charakter | Wyk. | Status | Test | Materiał |
|---|---|---|---|---|---|---|---|---|
| T1-01 | Firma inwestycyjna: dom maklerski, bank z działalnością maklerską, zagraniczna firma inwestycyjna w PL, osoba prawna z państwa trzeciego | [Temat 1](zrodla-uknf/TEMAT-1.md): „firmie inwestycyjnej - rozumie się przez to dom maklerski, bank prowadzący działalność maklerską…” | M1 | definicja | D | częściowe | Q, Y | Powiązanie z wykazem domów maklerskich w `analysis/engine.py`. Banki i podmioty zagraniczne nie są łączone |
| T1-02 | Zagraniczna firma inwestycyjna: siedziba lub centrala w innym państwie członkowskim, zezwolenie organu | „zagranicznej firmie inwestycyjnej - rozumie się przez to osobę prawną…” | M1 | definicja | D | brak | Y (firma transgraniczna) | Kod jej nie rozpoznaje |
| T1-03 | Zagraniczna instytucja kredytowa (art. 4 ust. 1 pkt 1 rozp. 575/2013) | „zagranicznej instytucji kredytowej - rozumie się przez to instytucję kredytową…” | M1 | definicja | D | brak | Y | Kod jej nie rozpoznaje |
| T1-04 | Źródło: Rejestr Firm Inwestycyjnych, czyli wykaz firm i agentów | „Rejestr Firm Inwestycyjnych” i URL KNF | M1 | obowiązkowe (wskazane źródło) | D, F | częściowe | R1 | `data/probe-snapshots/knf/knf_rejestr_FI.json`, `knf_agenci_prawne.json` (21 XI). Agentów użyto w FinanceWell |
| T1-05 | Źródło: banki prowadzące działalność maklerską | „Banki prowadzące działalność maklerską” i URL | M1 | obowiązkowe (wskazane źródło) | D | częściowe | Y | `data/probe-snapshots/knf/knf_banki_maklerskie.json` jako kopia, kod jej nie używa |
| T1-06 | Źródło: domy maklerskie | „Domy maklerskie” i URL | M1 | obowiązkowe (wskazane źródło) | D | zaliczone | `python3 tools/check_plan_evidence.py` | `data/probe-snapshots/knf/knf_domy_maklerskie.json`, test rejestru w `analysis/test_engine.py` |
| T1-07 | Źródło: oddziały zagranicznych firm inwestycyjnych | „Oddziały zagranicznych firm inwestycyjnych” i URL | M1 | obowiązkowe (wskazane źródło) | D | częściowe | Y | `data/probe-snapshots/knf/knf_oddzialy_zagr_FI.json` jako kopia, kod jej nie używa |
| T1-08 | Źródło: zagraniczne firmy bez oddziału | „Zagraniczne firmy inwestycyjne bez otwierania oddziału” i URL | M1 | obowiązkowe (wskazane źródło) | D | częściowe | Y | `knf_notyfikacje_zagr_FI.json` (712 notyfikacji) i `esma_mif_passport_to_PL.json` jako kopie, kod ich nie używa |
| T2-01 | Definicja firmy inwestycyjnej dla wydawcy materiału M2 | [Temat 2](zrodla-uknf/TEMAT-2.md): ta sama definicja co T1-01 | M2 | definicja | E | częściowe | R1 | XTB 6884980 i BDM 6884964 w `collectors/m2_archive.py`, sprawdzone przez `check_plan_evidence.py` |
| T2-02 | Zagraniczna firma inwestycyjna jako wydawca, według briefu tylko polski oddział | jak T1-02 | M2 | definicja | E | brak | R1 (oddział zagraniczny) | Brak materiału |
| T2-03 | Zagraniczna instytucja kredytowa jako wydawca | jak T1-03 | M2 | definicja | E | brak | R1 | Brak |
| T2-04 | Źródło: rejestr firm i agentów | jak T1-04 | M2 | obowiązkowe (wskazane źródło) | E | częściowe | R1 | `knf_rejestr_FI.json` |
| T2-05 | Źródło: banki z działalnością maklerską | jak T1-05 | M2 | obowiązkowe (wskazane źródło) | E | częściowe | R1 | `knf_banki_maklerskie.json`, kod jej nie używa |
| T2-06 | Źródło: domy maklerskie | jak T1-06 | M2 | obowiązkowe (wskazane źródło) | E | zaliczone | `python3 tools/check_plan_evidence.py` | `knf_domy_maklerskie.json` (XTB, BDM) |
| T2-07 | Źródło: oddziały zagranicznych firm | jak T1-07 | M2 | obowiązkowe (wskazane źródło) | E | częściowe | R1 | `knf_oddzialy_zagr_FI.json`, brak materiału oddziału |
| T2-08 | Źródło: zagraniczne firmy bez oddziału | jak T1-08 | M2 | wskazane źródło poza zakresem M2 z briefu | E | poza obowiązkowym zakresem | brak | Interpretacja z [Tematu 2](zrodla-uknf/TEMAT-2.md) (zob. W4) |
| T3-01 | Doradztwo: rekomendacja oparta na potrzebach i sytuacji klienta | [Temat 3](zrodla-uknf/TEMAT-3.md), art. 76: „przygotowanej w oparciu o potrzeby i sytuację klienta rekomendacji” | M3 | definicja | F, D | częściowe | Q, R1 | Klasa E5 `personalized_advice` w `analysis/semantic.py`. Przykład: „profil klienta” u BOŚ |
| T3-02 | Rekomendacja nabycia lub zbycia instrumentu | „dotyczącej nabycia lub zbycia jednego instrumentu finansowego” | M3 | definicja | F | częściowe | R1 | „co kupić i sprzedać” u BOŚ ([próba M3](M3-WERYFIKACJA-2026-11-21.md)) |
| T3-03 | Inna czynność o równoważnych skutkach | „albo dokonania innej czynności wywołującej równoważne skutki” | M3 | definicja | F | brak | R1 | Brak wzorca i przykładu |
| T3-04 | Rekomendacja powstrzymania się, czyli „trzymaj” | „rekomendacji dotyczącej powstrzymania się od wykonania takiej czynności”, „nabywania, zbywania albo trzymania” | M3 | definicja | F | brak | R1 („kup, sprzedaj lub trzymaj”) | `analysis/semantic.py` i `analysis/engine.py` nie mają wzorca „trzymaj” |
| T3-05 | Forma i inicjatywa: pisemna, ustna lub elektroniczna, z inicjatywy firmy albo na wniosek klienta | „z inicjatywy firmy inwestycyjnej albo na wniosek klienta … pisemnej, ustnej lub w innej formie” | M3 | definicja | F | brak | R1 | Nie jest modelowana |
| T3-06 | Instrument: papiery wartościowe (art. 3: akcje, prawa poboru, obligacje, certyfikaty, kwity, prawa pochodne) | „Ilekroć jest mowa o papierach wartościowych” | M3 | definicja | F | częściowe | Q, R1 | Wzorzec instrumentu w `analysis/engine.py`, test `test_m3_instrument_cue_uses_words_and_negation` |
| T3-07 | Instrument: tytuły uczestnictwa w instytucjach wspólnego inwestowania i instrumenty rynku pieniężnego (art. 2 pkt 2 lit. a–b) | „tytuły uczestnictwa…, instrumenty rynku pieniężnego” | M3 | definicja | F | częściowe | R1 | Wzorzec obejmuje „fundusz”, ale nie instrumenty rynku pieniężnego |
| T3-08 | Instrument: pochodne z lit. c–g oraz i, z warunkami rozliczenia, obrotu i wyjątkami | art. 2 pkt 2 lit. c–g, i | M3 | definicja | F | brak | R1 | Brak wzorca i przykładu |
| T3-09 | Instrument: kontrakty na różnicę (lit. h) | „h) kontrakty na różnicę” | M3 | definicja | F | brak | R1 | W M3 brak wzorca CFD. CFD występuje tylko w kontroli M2 |
| T3-10 | Instrument: uprawnienia do emisji (lit. j) | „j) uprawnienia do emisji” | M3 | definicja | F | brak | R1 | Brak |

## 5. Kryteria M2 (19 ID)

Źródło: [kryteria M2](zrodla-uknf/KRYTERIA-M2.md), w nawiasie wiersz DOCX. Wszystkie wiersze mają zakres M2, charakter obowiązkowy i wykonawcę E. Test zbiorczy to R1, a dla każdego ID test dodatni, ujemny i brak danych lub brak zastosowania (wynik E). Wspólny materiał to `analysis/checks.py`, `analysis/m2_evidence.py`, `analysis/test_engine.py`, `tests/e2e/m2_control.py` i `data/probe-snapshots/m2/manifests/`.

Stan na rzeczywistych ujęciach otrzymasz poleceniem `staged_captures('replay', …)` i `analysis.checks.marketing`, uruchomionym 21 XI. ETF: 1 S, 3 O, 5 O, 6 S, 7 S, 8 S, pozostałe brak danych. XTB akcje i BDM: 1 S, pozostałe brak danych. S oznacza spełnione, O obserwację.

| ID | Wymaganie | Cytat | Status | Mechanizm, test syntetyczny i dowód rynkowy |
|---|---|---|---|---|
| K-01 | Oficjalna nazwa firmy inwestycyjnej w materiale (2) | „podaje oficjalną nazwę firmy inwestycyjnej” | częściowe | `present("1")`. Spełnione na 3 rzeczywistych materiałach, brak testu ujemnego na rynku |
| K-02 | Jednoznaczne oznaczenie materiału jako reklamy (3) | „jednoznacznie oznaczono jako taki” | częściowe | Wzorzec etykiety. Na rynku wszędzie brak danych |
| K-03 | Twierdzenie o potencjalnym zysku i bezpośrednio przy nim informacja o istotnym ryzyku (4) | „Wykryj twierdzenia o potencjalnych zyskach” | częściowe | Para dywidendy kontra ostrzeżenie ETF jako obserwacja. Próby ujemne: 0% prowizji i CFD ([raport](DEMO-ODBIOR.md)) |
| K-04 | Rozmiar czcionki ryzyka kontra przeważający rozmiar materiału (5) | „Porównaj rozmiar czcionki” | częściowe | Dominanta ważona znakami, kontrola 16→8 px w `tests/e2e/m2_control.py`. Na rynku brak danych |
| K-05 | Umiejscowienie, kontrast, przesłonięcie i czytelność ryzyka (6) | „Oceń umiejscowienie … kontrast, przesłonięcie” | częściowe | ETF: obserwacja, ostrzeżenie poza pierwszym kadrem telefonu. Kontrola gradientu i przesłonięcia |
| K-06 | Ryzyko ukryte w przypisie, sekcji „Legal” lub miejscu o niskiej widoczności (7) | „ukrytą m.in. w przypisach, w sekcji „Legal”” | częściowe | ETF spełnione, czyli rola body. Brak przypadku dodatniego na rynku |
| K-07 | Ryzyko dostępne bez rozwijania, kliknięcia lub zmiany warstwy (8) | „musi rozwinąć element, kliknąć link” | częściowe | ETF spełnione. Kontrola rozwinięcia `details`. Link i warstwa niezbadane |
| K-08 | Responsywność na komputerze, tablecie i telefonie (9) | „Zasymuluj widok na komputerze, tablecie i telefonie” | częściowe | ETF spełnione na 1440, 768 i 390 px. Kontrola reflow |
| K-09 | Zrozumiałość ostrzeżenia dla przeciętnego odbiorcy grupy docelowej (10) | „zrozumiały dla przeciętnego odbiorcy” | brak | Kod zawsze zwraca brak danych z notatką do ręcznego przeglądu. Brak oceny automatycznej i modelowej |
| K-10 | Język ostrzeżenia zgodny z językiem przekazu (11) | „Porównaj język informacji o ryzyku” | częściowe | Reguła na `verifiedLanguages` i test. Na rynku brak danych |
| K-11 | Porównania: źródło i założenia, wskazanie ustalonych naruszeń (12) | „Wykryj porównania, sprawdź źródło” | częściowe | Wzorzec z testem, ocena ręczna. Na rynku brak danych |
| K-12a | Wyniki historyczne: ostatnie 5 lat, pełne okresy 12-miesięczne, okres referencyjny i źródło (13) | „obejmuje ostatnie pięć lat … okres referencyjny i źródło” | częściowe | Test `test_historical_and_conditional_rules`. Wykrywa frazę „5 lat”, ale nie sprawdza, które lata pokazano |
| K-12b | Wyniki historyczne: ostrzeżenie o kursach walut oraz wpływ prowizji, opłat i obciążeń (14) | „ostrzeżenie o wpływie zmian kursów walutowych oraz wpływ prowizji, opłat” | częściowe | Uruchamia się tylko przy USD, EUR, GBP lub „brutto”. Opłaty bez słowa „brutto” są pomijane. Na rynku nie dotyczy lub brak danych |
| K-13 | Wyniki historyczne nie są najbardziej eksponowane (15) | „Reguła wymaga, by nim nie były” | częściowe | Wykrywa kontekst, dominację ocenia ręcznie analityk |
| K-14 | Zastrzeżenie, że wyniki historyczne nie są wiarygodnym wskaźnikiem (16) | „nie są wiarygodnym wskaźnikiem przyszłych wyników” | częściowe | Reguła sąsiedztwa i test. Na rynku brak danych |
| K-15 | Wykrycie i zgłoszenie prognozy oraz osobno ostrzeżenie (17) | „Rozpoznaj prognozę … zaznacz jej wykrycie” | częściowe | Wzorzec prognozy i test. Samo wykrycie jest tylko w cytacie dowodu, bez osobnego stanu |
| K-16 | Podatki: zależność od indywidualnej sytuacji i możliwość zmian (18) | „zależności od indywidualnej sytuacji klienta i możliwości zmian” | częściowe | Obie części z testem. Na rynku brak danych |
| K-17 | Brak sugestii aprobaty KNF lub innego organu (19) | „Wykryj odwołanie do KNF lub innego właściwego organu” | częściowe | Wąski wzorzec ograniczony do KNF, test `test_neutral_supervision`. Inne organy pominięte |
| K-18 | Brak wywodzenia bezpieczeństwa z nadzoru (20) | „zapewnienie o pełnym bezpieczeństwie oparte na spełnianiu rygorystycznych wymogów KNF” | częściowe | Wzorzec i test. Parafrazy bez słowa „dzięki” lub „bo” umykają |

## 6. Obowiązkowe wiersze bez dowodu

| ID | Czego brakuje |
|---|---|
| R-§2-02 | Brak kolektora i próbki z Facebooka |
| R-§2-03 | Brak kolektora i próbki z Instagrama |
| R-§2-M1-02 | Brak polskojęzycznej reklamy zagranicznej firmy działającej transgranicznie |
| R-§2-M2-02 | Brak materiału polskiego oddziału firmy zagranicznej |
| R-§3.1-05 | Stały User-Agent, brak rotacji |
| R-§3.1-06 | Brak obsługi proxy |
| T1-02, T1-03 | Kod nie rozpoznaje zagranicznej firmy inwestycyjnej ani zagranicznej instytucji kredytowej w M1 |
| T2-02, T2-03 | Jak wyżej dla wydawcy M2 |
| T3-03, T3-04, T3-05 | M3 nie wykrywa czynności równoważnych, rekomendacji „trzymaj” ani formy i inicjatywy rekomendacji |
| T3-08, T3-09, T3-10 | M3 nie rozpoznaje pochodnych, CFD ani uprawnień do emisji |
| K-09 | Brak jakiejkolwiek oceny zrozumiałości ostrzeżenia |

Najsłabsze z wierszy częściowych są nadal bez przypadku rynkowego: potencjalnego naruszenia M3 (R-§2-M3-01…06), reklamy u nowego twórcy (R-§2-M1-01), automatycznego wyzwolenia harmonogramu (R-§3.1-10) i niezależnej trafności (R-§6-02).

## 7. Priorytet mentora i J (poza ZIP)

Te ustalenia porządkują pracę, ale nie zmieniają ani nie zastępują wymagań ZIP.

| ID | Ustalenie | Źródło w repo | Relacja do ZIP |
|---|---|---|---|
| P-01 | YouTube jest pierwszym źródłem i pierwszym pionem: duży polskojęzyczny twórca spoza listy startowej, reklama i domyślna kolejka | [Prompt](../START_PROMPT.md), [plan Fable](fable/REALIZACJA.md) (B, K, kolejność) | Brief nie wymienia YouTube. Mieści się w „m.in.” (R-§2-05). FB, IG i TikTok (R-§2-02…04) pozostają obowiązkowe |
| P-02 | X jest rozszerzeniem proponowanym przez mentora | [Plan Fable](fable/REALIZACJA.md), wiersz K | Poza ZIP, nie wchodzi do bramki obowiązkowej |
| P-03 | Koszt błędu 2 × FN + FP pochodzi od J | [Próba M3](M3-WERYFIKACJA-2026-11-21.md), [kontrakty](hackathon/contracts.md) | Brief żąda wpływu progu na FP i FN (R-§3.3-10) bez wag |
| P-04 | Z konsultacji mentorskiej: potwierdzenie współpracy, odpowiedź firmy i porównanie z umową lub aneksem jako dalszy krok M1, na fikcyjnych danych | [Konsultacja](PLAN-PO-KONSULTACJI.md) | Ilustracja, nie wymóg. Wymagany wynik M1 to R-§2-M1-03…08 |
| P-05 | J podejmuje decyzje produktowe i zatwierdza koszty, commit, publikację i wysyłkę | `AGENTS.md` | Dotyczy R-§4-01, R-§4-04 i R-§7-01 |

## 8. Decyzje zespołu (poza ZIP)

| ID | Decyzja | Źródło |
|---|---|---|
| D-01 | Pokaz trwa dwie minuty. Widoki M2 to 1440×900, 768×1024 i 390×844, a próby UI 1440 i 390 px | [Plan realizacji](PLAN-REALIZACJI.md), [kryteria M2](zrodla-uknf/KRYTERIA-M2.md) |
| D-02 | Stos: Vosk, E5, SQLite, Huey, Astryx. Brief podaje tylko przykłady | [Plan realizacji](PLAN-REALIZACJI.md) |
| D-03 | Progi pomocnicze 4,5:1 i 12 px oraz ważenie widocznymi znakami. To metody zespołu, nie wymogi UKNF | [Kryteria M2](zrodla-uknf/KRYTERIA-M2.md) |
| D-04 | Cel Y: co najmniej 4 z 5 największych kwalifikujących się kanałów w niezależnej próbie. regionCode=PL tylko zawęża wyszukiwanie | [Próby](fable/ODBIOR.md) |
| D-05 | Bramka Q: precyzja kolejki co najmniej 90% przy co najmniej 20 skierowaniach z różnych kampanii, z 95% przedziałem. Jednostka etykiety to udokumentowana przesłanka do kontroli | [Próby](fable/ODBIOR.md) |
| D-06 | Jawny sponsor bez osobnego uchybienia trafia do rejestru reklam, nie do kolejki. Materiał syntetyczny lub ręczny jest poza domyślną kolejką | [Próby](fable/ODBIOR.md), [prompt](../START_PROMPT.md) |
| D-07 | Preferowana droga YouTube to Data API v3 (search → videos/channels → uploads). Atom monitoruje znane ID | [Plan Fable](fable/REALIZACJA.md) |
| D-08 | Score jest oddzielony od podobieństwa E5 i zasięgu. Słowo „prawdopodobieństwo” wolno użyć dopiero po kalibracji | [Plan Fable](fable/REALIZACJA.md), [próby](fable/ODBIOR.md) |
| D-09 | Zakres M2 obejmuje polskie oddziały, ale nie zagraniczne firmy bez oddziału (T2-08) | [Temat 2](zrodla-uknf/TEMAT-2.md) |
| D-10 | Fable orkiestruje, a wykonanie i odbiór prowadzą agenci Opus i Sonnet. Sędziowie O/P oceniają niezależnie | [Plan Fable](fable/REALIZACJA.md) |

## 9. Wątpliwości interpretacyjne do decyzji J

| ID | Wątpliwość | Wiersze |
|---|---|---|
| W1 | Brief wymienia FB i IG z nazwy, a dziś nie ma dowodu. Dostęp do Meta wymaga aplikacji i uprawnień. Czy przy odmowie przyjmujemy status „blokada dostępu” z raportem K, czy wymagamy choćby publicznej próbki, np. z Ad Library przez oznaczony import? | R-§2-02, R-§2-03 |
| W2 | Rotacja UA i proxy jest wpisana jako wymóg. Jako ścieżkę bez kosztu proponuję konfigurowalną rotację tylko na uprawnionych trasach, bez płatnej puli proxy. Czy to wystarczy? | R-§3.1-05, R-§3.1-06 |
| W3 | Brief mówi „dowolny silnik”, ale kryterium §8.4 premiuje „preferowane technologie”. Czy dodać lokalny LLM (Ollama lub llama.cpp z otwartym modelem) do oceny treści M2/M3, np. K-09, czy zostajemy przy ONNX E5 i Vosk? | R-§3.2-07, R-§3.2-08, R-§8-04, K-09 |
| W4 | Temat 2 podaje wykaz firm bez oddziału, a brief M2 wymienia tylko oddziały. Zespół przyjął węższy zakres | T2-08, D-09 |
| W5 | YouTube Data API v3 jest bezpłatne z limitem, ale zewnętrzne. Czytam zakaz z briefu jako dotyczący płatnych API. Klucz trafiłby do .env | R-§5-06, R-§5-09 |
| W6 | „Console.log” w §6 jest niejednoznaczne: czysta konsola przeglądarki czy brak `console.log` w kodzie? Rejestr sprawdza oba | R-§6-07 |
| W7 | Próbki organizatora są dostępne tylko przy stoisku. Czy J je odbierze i czy G ma je dołączyć do walidacji? | R-§7-01 |
| W8 | „Jedna komenda” działa, ale wymaga przygotowania hosta (Python, FFmpeg). Czy wymagamy obrazu w pełni samowystarczalnego? | R-§5-03 |

**Wiersze bez jednoznacznego właściciela.** R-§3.1-05 i R-§3.1-06: L sprawdza konfigurację, ale kod leży w kolektorach B, K i H. R-§3.3-08 i R-§6-05 dzielą H (zdarzenie serwera) i J1 (alert w UI). R-§8-02 dzielą Fable i N (opis procesu w PDF). R-§7-01 wymaga fizycznego odbioru przez J. Fable powinien przypisać jednego właściciela każdemu z nich.

## 10. Stan odniesienia: poprzednia macierz

Poniżej pełna treść poprzedniej macierzy bez zmian. Dotyczy roboczej integracji na bazie eaa9c10 i odcisku b572eda8 i jest punktem odniesienia dla kolumny „Materiał”.

Wymagania pochodzą z [pięciu plików konkursu](zrodla-uknf/README.md). Stan odnosi się do roboczej integracji na bazie eaa9c10 z 21 listopada 2026. Lokalny podgląd po czystym zasianiu bazy zwrócił 20 spraw z zakończonego replay. Poprzednia instancja z pięcioma skanami i 93 sprawami służyła do pomiaru wyjściowego. Są to dwa różne zbiory i żaden licznik nie określa liczby naruszeń.

| Wymóg w PDF | Zaimplementowane i sprawdzone | Ograniczenie lub następna próba |
|---|---|---|
| §1–2, §3.1. Crawler WWW i social, API/parser, HTML → dane | Monitor profili YouTube/TikTok i odkrywanie z Apple Podcasts, RSS, PeerTube oraz odsyłaczy. Publiczne domeny firm dostarczają tekst do JSON, M2 zapisuje także renderowaną reklamę. [Monitoring](MONITORING.md) | FB/IG bez potwierdzonego kolektora live. Dotychczasowe konta i limity źródeł nie dają oszacowania pokrycia rynku. Brak odbioru rotacji UA i proxy z dwiema faktycznie uprawnionymi trasami. |
| §2 M1. Raport o reklamie osoby trzeciej i okresowe aktualizacje | Na monitorowanym kanale w dwóch publikacjach znaleziono rzeczywistą deklarację „Partnerem odcinka jest XTB”. Osobny replay odkrywa nowego twórcę i utrwala neutralny materiał bez duplikatu przy powtórce. Klip syntetyczny z polskim ASR pozwala przejść do czasu promocji. [Próby M1](M3-WERYFIKACJA-2026-11-21.md) | Nowo odkryty autor i rzeczywista reklama to osobne przykłady. Pozostają do sprawdzenia realna promocja obecna tylko w mowie oraz udokumentowana polskojęzyczna reklama firmy transgranicznej. |
| §2 M2. Własny materiał zarejestrowanej firmy, proporcjonalność, dostateczność i wyrazistość ryzyka | Trzy publiczne oferty z dwóch domen rejestrowych. Chromium zachował 18 ujęć na trzech szerokościach. W ETF porównujemy tekst o dochodzie z dywidend z właściwym ostrzeżeniem. Ramki na telefonie dzieli 921 pikseli CSS. Wskaźnik reguł kieruje sprawę do przeglądu. Obraz i odpowiadający mu wyciąg DOM mają indywidualne skróty. [Manifest ETF](../data/probe-snapshots/m2/manifests/xtb-etf.json) | To obserwacja położenia konkretnej pary w przechwyconym stanie. Na mobilnych kadrach widać baner cookies. Detektor okna zgody obejmuje dialogi. Kwalifikacja prawna i istotność ryzyka dla odbiorcy wymagają oceny. Materiał oddziału zagranicznego i reklama bez DOM czekają na osobny odbiór. |
| Załącznik ryzyka M2, wszystkie 19 ID | W trzech kartach replay są łącznie 2 obserwacje, 6 pozycji „spełnione” i 49 „brak danych”. Dla ETF: 2, 4 i 13. Dla akcji XTB i rachunku BDM zbadany materiał potwierdza po jednej pozycji. Kontrola syntetyczna obejmuje m.in. 16→8 px, rozwinięcie, przesłonięcie i gradient. [19 reguł i podstawy źródłowe](zrodla-uknf/KRYTERIA-M2.md) | Domyślny Compose odtwarza przygotowane pomiary. Świeże renderowanie wymaga środowiska z Chromium i Playwright. Samo pobranie HTML nie aktualizuje geometrii. Próg kontrastu i widoczności jest pomocniczy. |
| §2 M3. Potencjalne nieuprawnione doradztwo w Polsce | Kolektor przeszedł z bossa.pl przez katalog do oferty. E5 wskazał wypowiedź o kupnie i sprzedaży. KRS/NIP operatora i zakres 5 w datowanym wykazie KNF pozwalają pokazać uprawnionego dostawcę jako kontrolę. W odrębnym materiale edukacyjnym model wybrał listę instrumentów, a końcowa decyzja wstrzymała flagę. FinanceWell pozostaje kolizją dwóch nazw. [Pełna ścieżka, źródła i granice](M3-WERYFIKACJA-2026-11-21.md) | Brak potwierdzonego przypadku nieuprawnionej usługi. Następna próba to pełna publiczna oferta spoza autoryzowanego domu maklerskiego i niezależna weryfikacja podmiotu, czynności oraz zakresu. Brak wpisu ma własny stan. |
| §3.1. Kolejka, harmonogram, SQL i treść | Huey, dzierżawa zadania i osobny worker. SQLite przechowuje wersje, decyzje i zdarzenia. Obrazy, DOM i media mają trwałe odnośniki. Osobny timer monitoruje cztery profile. [Próba awarii](../tests/offline/README.md) | Dla timera użytkownika sprawdzono aktywność i następny termin. Automatyczne wywołanie wymaga zdarzenia dziennika. Kopia z odtworzeniem wszystkich załączników, retencja oraz kolejka 1/2 procesów pod obciążeniem pozostają do pomiaru. |
| §3.2. Python, czyszczenie, normalizacja, deduplikacja, tokeny, embeddingi, inferencja i wspólny wynik | Lokalne Vosk i E5, reguły priorytetu oraz wspólne obiekty Capture/Finding. W M3 wskazanie modelu ma cytat i przyczynę. W M2 kwalifikujący pomiar jest jawnie oznaczony jako wynik reguł. [Analiza](../analysis/README.md) | Model może wskazać edukację jako podobną do oferty. Jedna zgodna para lub parafraza nie waliduje skuteczności na rynku. Ograniczenia wejścia i brak wag są sygnalizowane. |
| §3.3. Dashboard, filtry, trendy, status, WebSocket i kalibracja | React z lokalnymi komponentami, filtry daty, źródła, ryzyka i modułu, trend, rewidowane decyzje, odczyt wersji, zdarzenia i panel progów. Weryfikujemy działanie na telefonie i komputerze, również dla ID zawierającego ukośnik. [Raport UI](DEMO-ODBIOR.md) | Należy odróżnić obsługę zdarzeń od pomiaru opóźnienia alertu przy obciążeniu. Znany problem starego pulpitu przy dotyku po głębokim przewinięciu opisuje raport prób. |
| §3.3 i §6. Trafność i wpływ progu na FP/FN | Zbiór ilustracyjny 4 publicznych i 9 syntetycznych przykładów. Przy progu 30: FP 1, FN 2 i koszt 5. Przy 80: FP 0, FN 5 i koszt 10. Wagi kosztu 2:1 pochodzą od J. | To wynik reguł względem oczekiwanego skierowania do przeglądu. Brak eksperckiej próby nowych kampanii dla trzech modułów. Odmienna wersja materiału lub definicja celu zmienia interpretację wyniku. |
| §4–5. Dostarczenie, architektura, Compose/on-prem, otwarty stos, bezpieczeństwo i minimalny README | Lokalny [Quick Start](../README.md), kod, opis produktu i [prezentacja PDF](../presentation/InvestWatch.pdf). API i worker to dwie usługi Compose. Praca na przygotowanym hoście korzysta z lokalnych wag. [Warunki środowiska i zakres audytu](DEMO-ODBIOR.md) | Archiwalne audyty pip i React 18 nie obejmują całego nowego grafu Astryx, obrazów ani bibliotek natywnych. Oddzielnego ustalenia wymagają prawa do konwersji wag. Wysyłkę i stan konkursowego zgłoszenia potwierdza J. |
| §6 i §8. Prezentacja oraz sposób pracy z AI | Osobne worktree, wykonawcy i poziomy reasoning. Błąd 404 dla prawdziwego ID, mylna sugestia E5 w edukacji i mylenie opłat z potencjalnym zyskiem doprowadziły do zmian podlegających powtórnym próbom. [Tablica](../TEAM_BOARD.md) · [Scenariusz](hackathon/demo.md) | Punktacja panelu agentów ma odniesienie do konkretnej wersji. Wynik oficjalny zależy od jury. |

Końcowa regresja kodu, kolektorów i API objęła 58 testów, a warstwa narzędziowa 23 testy. Trzy starty Compose offline zwróciły po 20 spraw, 20 wersji i 20 wyników E5 w 6,27 s, 6,61 s i 7,00 s. Trzeci worker wznowił przerwane zadanie po zasymulowanym wygaśnięciu dzierżawy. W bazie pozostało 20 różnych spraw. [Raport maszynowy](../tests/offline/proof-zip-2026-11-21.json) · [Oceny i granice przeglądu](JUDGING.md)
