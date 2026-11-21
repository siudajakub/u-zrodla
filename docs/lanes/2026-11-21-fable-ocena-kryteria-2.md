# Druga niezależna ocena względem kryteriów UKNF · 21 XI 2026, ok. 22:30 UTC (23:30 w Polsce)

Sędzia tylko do odczytu, model `claude-opus-5-5`. Stan: `hack/integration` na 6f62815 plus 26 niezacommitowanych plików (UI rundy 4, README, skrypty `ops/demo`). Działające API to `127.0.0.1:18801`, baza `.runtime/pion-replay`, schemat 8, ostatni skan `5509056b…` z 22:00 UTC. Statusom z `docs/ODBIOR-UKNF.md` nie ufałem, bo opisują HEAD 491094d. Sprawdzałem przez GET na API i w kodzie. Zrzuty pulpitu pochodzą z `tests/ui/screens/2026-11-21-r3/` (21:36 UTC). Pokazują starszą bazę: 3 sprawy, M2 31, M3 2. Rundy r4 w chwili oceny nie było. Testy uruchomione na pustym `INVESTWATCH_STATE`: `tests/core` 354 OK, `collectors` 200 OK, `analysis` 207 OK (3 pominięte), `tools` 46 OK, `check_agent_docs` i `check_plan_evidence` OK.

## Odpowiedź w 10 zdaniach

1. Od poprzedniej oceny (6,25) projekt domknął większość luk w produkcie. Baza pokazu ma teraz trzy moduły, YouTube, TikTok, Facebook, Instagram i WWW w jednym skanie: 1923 materiały z 46 źródeł i 15 spraw do sprawdzenia (4× M1, 10× M2, 1× M3).
2. Dziś szacuję wynik na **5,4 / 6,9 / 7,9** (pesymistyczny, realistyczny, optymistyczny). Wzrost realistycznego wyniku o około 0,6 pkt wynika z kategorii 4 (zgodność ze specyfikacją) i 1 (gotowość).
3. Rozrzut wyniku zależy prawie wyłącznie od stanowiska pokazu. Na macOS nikt niczego nie uruchomił, split Compose na 5 serwisów wszedł przy okazji commita o „drugim głosie” (6f62815, `Gate` testował tylko `analysis.test_second_opinion`), a gotowego stanu (`pack-state.sh`) nie ma w `.runtime/dist/`.
4. Warstwa AI jest w bazie pokazu niewidoczna. `semantic.status` ma wartość `unavailable` (brak numpy, onnxruntime i tokenizers w venv, choć `.runtime/semantic/deps` istnieje), a LLM jest wyłączony. Jury oceniające „trafność klasyfikacji przez moduły AI” zobaczy same reguły.
5. Panel kalibracji liczy wyłącznie M1 na 26 materiałach. FP wynosi 0 przy każdym progu od 20 do 95, a FN rośnie dopiero powyżej 90. Punkt §6 o wpływie progu na FP i FN wypada więc słabo, choć etykiety M2 z realnym kompromisem (próg 30: TP 9, FP 1, FN 3) leżą w repo.
6. Facebook i Instagram pochodzą z próbki usługi ScrapeCreators: 494 materiały, z czego 177 trafia do „Ofert M2” z trasą `insufficient`. Wśród nich jest post XTB o koszykówce i słowacka reklama XTB. Jednocześnie README, HACKATHON.md, PDF i scenariusz mówią „automatyczny odczyt zablokowany, nie obchodzimy”, a API zwraca `accessBlocked: 0`. Tę sprzeczność jury wychwyci.
7. Dokumenty rozjechały się z bazą: README i scenariusz podają 4 sprawy (jest 15), M2 31 lub 3 strony (jest 26 stron i 209 pozycji), M3 2 (jest 22). `ODBIOR-UKNF.md`, podlinkowany w README jako „Co działa”, nadal podaje FB i IG jako „Kolektora nie ma”.
8. M1 ma mowę tylko dla 17 z 1305 filmów YouTube (`transcriptState` full 17, pending 1288), a wszystkie 4 alarmy dotyczą jednego reklamodawcy (XTB). Pytanie o pokrycie jest dziś najsłabszym punktem merytorycznym.
9. Najwięcej punktów do 11:00 dają: zamrożenie i jeden zimny start na zamrożonym kodzie, film i tunel jako zabezpieczenie, spójne liczby i narracja źródeł, E5 włączony w bazie pokazu, kalibracja M2 z widocznym kompromisem FP/FN oraz odszumienie M2. Razem to około +0,5…+0,8 pkt i ochrona przed spadkiem o 1,5 pkt.
10. Realny sufit to około 7,8–8,0. Do 9 nie dojdziecie bez etykiet eksperckich, bez dowodu działania na żywo i bez różnorodności alarmów M1, a tego nie da się zrobić do rana.

## 1. Punktacja dziś

| Kryterium (waga) | Pes. | Real. | Opt. | Uzasadnienie | Kontrprzykład jury |
|---|---:|---:|---:|---|---|
| 1. Technologia i gotowość demo (30%) | 5,0 | 7,0 | 8,0 | Na żywo działa: 15 spraw z trzech modułów, karta z cytatem i sekundą filmu, M2 z pomiarem odległości ostrzeżenia w px (Noble: 11 542,5 px wobec progu 450 px), raport CSV i JSON (`/v1/report`), próg z historią, 46 źródeł w stanie `ok`. Testy: 807 OK. Zagrożenia: brak uruchomienia na Macu, świeży i niezacommitowany kod UI oraz ops, brak gotowego stanu (zimny start 5–7 min), E5 `unavailable` | „Proszę uruchomić to tutaj, jedną komendą.” Jeśli Docker Desktop na M3 nie przejdzie `prepare-darwin.sh` (apt, pip wheel, ASR, E5 w kontenerze arm64), pokaz zostaje bez produktu |
| 2. Innowacyjność procesu z AI (20%) | 6,5 | 7,5 | 8,5 | PROCES-AI.md z rolami, bramkami i 10 błędami złapanymi przez agentów, zamrożony protokół, ślepe etykiety, trailery `Lane`/`Gate`, pomiar drugiego głosu na 9 modelach z ledgerem kosztu | „`Gate` to deklaracja, nie CI.” Kontrprzykład z dziś: commit 6f62815 o drugim głosie zawiera split Compose (145 linii), a jego `Gate` testuje tylko `second_opinion` |
| 3. Architektura (20%) | 5,5 | 6,5 | 7,5 | Serwisy `web`, `api`, `worker`, `scheduler`, `inference`, sieć `internal`, rejestr adapterów `discover(ctx)`, kontrakt v2 z wersjami, magazyn adresowany SHA-256. ARCHITEKTURA.md opisuje ścieżkę wzrostu. Minusy: SQLite z jednym pisarzem, `objects` na dysku zamiast S3, zależności montowane z hosta zamiast obrazów | „10 tys. kanałów i 5 analityków jednocześnie?” „Dlaczego nie ma Dockerfile?” |
| 4. Zgodność ze specyfikacją i technologiami (20%) | 4,5 | 6,0 | 7,0 | Domknięte: FB, IG i TikTok w bazie, rotacja UA i proxy (`collectors/common.py:49–170`), trend, audyty npm i pip, `.env.example`, M2 26 stron 11 firm, M3 22 oferty. Braki: silnik inferencji (Ollama, vLLM) poza ścieżką pokazu, E5 niedostępny, kalibracja tylko M1 i płaska, wykres trendu z jednego dnia, a pomiary i próbka FB/IG pochodzą z zewnętrznych płatnych usług wbrew literze §5 | „Brief wymaga Ollama lub vLLM i modelu open source. Gdzie on działa w tym pokazie?” |
| 5. Atrakcyjność (10%) | 6,0 | 7,5 | 8,5 | Rejestr oddzielony od alarmu, kontrdowód z mowy (Comparic, 614 s), link do sekundy, pomiar ekranu M2 na 1440 i 390 px, ostrożne „ustal operatora” w M3 | „Wszystkie alarmy M1 to XTB i ten sam mechanizm linku” |
| **Wynik ważony** | **5,40** | **6,85** | **7,85** | Poprzednio 4,95 / 6,25 / 7,25 | |

### Co faktycznie domknięto od poprzedniej oceny

| Poprzednia luka | Stan | Dowód |
|---|---|---|
| Compose nie montował paczki mediów | domknięte (statycznie) | `compose.yaml:32` montuje `${INVESTWATCH_MEDIA_PACK}` do `/replay-media:ro`. Na Macu nieuruchamiane |
| Kalibracja na starym zbiorze 13 | domknięte, ale słabe | `/v1/calibration`: `dataset q-v2`, n=26, `rules_1_2` FP 7 i FN 4, `qual_d` 0 i 0. Krzywa płaska (patrz §2) |
| TikTok poza demo | domknięte | 8 źródeł `tiktok:*` (6 `ok`, 2 `skipped`), 64 posty, 5 wpisów w rejestrze |
| FB/IG bez danych | domknięte próbką zewnętrzną | `vendor_social` 494, `facebook` 30, `facebook-ads` 113, `instagram` 350, `meta_ads` `needs_key`. Import ręczny `POST /v1/import/meta` |
| Brak wykresu trendu | domknięte | `Sources.jsx:255 TrendTile`, `Desk.jsx:55 TrendGlance`. Dane z jednego dnia (7 skanów) |
| Audyt zależności, `.env.example` | domknięte | `docs/DEMO-ODBIOR.md`: npm audit 0 (181 pakietów), pip-audit 0. `.env.example` istnieje. Prymitywy Radix dodano po audycie, więc audyt trzeba powtórzyć |
| Rotacja UA i proxy | domknięte | `collectors/common.py:49–170` (pula UA na host i sesję, round robin proxy z cooldownem) |
| M3 bez kandydata | domknięte częściowo | `offersM3` 22, `web:rdmwm.pl:m3` `refer` 85, `public-bos-profil` jako kontrola. Odkrywanie przez wyniki wyszukiwania zapisane przez agenta (WebSearch), produkt nie ma własnego wyszukiwania |
| M2: 13–18 z 19 ID z „brak danych” | domknięte | Na 26 stronach WWW „brak danych” pojawia się 1–6 razy na ID, a ID 9 ma 9 przesłanek i 10 spełnień. 12a, 12b, 13 i 14 to „nie dotyczy” na 25 z 26 stron |
| PDF i scenariusz sprzed YouTube | domknięte, ale już nieaktualne | `presentation/InvestWatch.pdf` (21:55) i `docs/hackathon/demo.md` podają 4 sprawy, 22 reklamy, „Meta zablokowany” i Compose „API i worker” |
| `creatorName: null` | domknięte | Wiersze review mają kanał (np. „Inwestycyjna wyprawa”) |
| E5 `unavailable` na 18801 | **otwarte** | `/v1/overview.semantic`: brakuje pakietów numpy, onnxruntime i tokenizers oraz nie ustawiono `INVESTWATCH_SEMANTIC_DIR` |
| Próba na Macu | **otwarte** (decyzja J) | `ops/mac/README.md`, linia 3: „przygotowano statycznie… bez dostępu do Maca” |
| Rejestr ODBIOR-UKNF | **otwarte, gorzej** | Nadal HEAD 491094d (66/60/7/0/4). FB i IG „Kolektora nie ma”. README linkuje go jako „Co działa” |

**Co się pogorszyło lub pojawiło nowego:**
- Szum w M2: 177 z 209 pozycji `offersM2` to posty i reklamy FB/IG z trasą `insufficient` i wynikiem 20. Są tam m.in. `instagram:Dfzb1P6zJmQ` („Polska vs Chorwacja… koszykarskie emocje”) i `facebook:ad-949456423765641` („Viac ako 1 000 000 investorov”, po słowacku).
- Sprzeczna narracja o Meta: dokumenty mówią `access_blocked`, a API pokazuje `sourceHealthSummary.accessBlocked: 0` i FB/IG `ok`.
- Ucięta nazwa w kolejce: „BANK PEKAO S.A. (…) iuro Maklerskie PEKAO”.
- Zależność od zewnętrznych usług w danych pokazu (ScrapeCreators: 74 darmowe kredyty) i w pomiarach (OpenRouter). Do tego nowy tryb „API demo” drugiego głosu (6f62815), który kusi, żeby pokazać płatne API na scenie.
- Mieszanie zakresów w commitach i 26 niezacommitowanych plików 12 h przed oddaniem. Na GitHubie `origin/main` = 491094d, czyli 74 commity za `hack/integration`.

### Co działa na żywo, a co tylko w testach lub dokumentach

| Na żywo (API 18801, GET) | Tylko testy lub fiksury | Tylko dokumenty lub plan |
|---|---|---|
| Kolejki: review 15, adRegister 290, offersM2 209 (26 WWW), offersM3 22, incomplete 228, transcriptPending 1288. Raport M1/M2/M3 JSON i CSV. Próg 60 z historią, wariant `qual_d` z `validationRef`. 19 ID M2 z pomiarami, zrzutami i DOM z SHA-256. Trend z 7 skanów. Sprawy M3 z osiami i cytatem | Drugi głos LLM (`analysis/second_opinion.py`, 9 modeli przez OpenRouter, fiksury nieśledzone przez Git). Ollama (atrapa HTTP). Ścieżka Mac (atrapy). E5 (test, ale nie baza pokazu). Kalibracja M2 i M3 (`fixtures/labeled/m2-agent-eval.json`, `m3-agent-eval-v2.json`) | Split Compose w akcji na Macu, alert `high_risk` w drugiej karcie („do potwierdzenia na próbie”), tryb live co 4 h (wszystkie skany w bazie to replay lub recompute), walidacja ekspercka, film |

## 2. Macierz briefu

### §3.1 Backend i silnik scrapingu

| Punkt briefu | Stan | Dowód | Co jury zobaczy | Ryzyko |
|---|---|---|---|---|
| Kolejka zadań open source | spełniony | Huey na SQLite i dziennik skanów z dzierżawą (`api/jobs.py`). `/v1/overview.recompute` `done`, 1923 sprawy | Status skanu w nagłówku kolejki | niskie |
| Playwright/Selenium/httpx/requests | spełniony | Playwright Chromium dla M2 (`collectors/m2_browser.py`), PoliteFetcher (robots.txt, ≥3 s) dla M3 | Zrzuty M2 1440 i 390 px | niskie |
| Kolektory API lub parsery social z rotacją UA i proxy | częściowo | Rotacja: `collectors/common.py:49–170`. Social: parser osadzeń TikTok, `vendor_social` (tylko replay próbki), `meta_import`, `meta_ads` (`needs_key`). W pokazie wszystko to datowane próbki | Kafle źródeł | „Rotacja i proxy” w ustach regulatora brzmi jak obchodzenie zabezpieczeń. Mówcie: etykietowane UA i tylko uprawnione trasy |
| Ekstrakcja HTML do JSON | spełniony | `collectors/sites.py`, DOM M2 jako `json.gz` z SHA-256, `/v1/report?format=json` | Raport JSON | niskie |
| Baza metadanych (SQL) | spełniony | SQLite, schemat 8 (`/v1/health`) | — | niskie |
| Baza treści (SQL + Object Storage) | częściowo | `objects/` na dysku, nazwy = SHA-256. Bez S3 i MinIO (ścieżka wzrostu w ARCHITEKTURA.md) | `/evidence/m2/market/<sha>.jpg` | niskie–średnie |
| Harmonogram (CronJob lub orkiestrator) | częściowo | Serwis `scheduler` (`ops/scheduler/scheduler.py`, profil `live`, commit 6f62815), `INVESTWATCH_DISCOVERY_INTERVAL` 14400. W bazie nie ma żadnego skanu cyklicznego | W trybie pokazu nic, harmonogram jest wyłączony | „Pokażcie okresową aktualizację” (M1 wymaga jej wprost) |

### §3.2 Moduły analityczne i AI

| Punkt briefu | Stan | Dowód | Co jury zobaczy | Ryzyko |
|---|---|---|---|---|
| Usuwanie tagów HTML, normalizacja, deduplikacja | spełniony | `analysis/material_classifier.py: clean_text, dedupe`, odcisk treści w wersjonowaniu | Pośrednio (wersje sprawy) | niskie |
| Tokeny i embeddingi | częściowo | E5 `multilingual-e5-small` ONNX w kodzie i w `.runtime/semantic`. Na 18801 `unavailable` | Nic, dopóki E5 nie zostanie włączony | średnie |
| Silnik inferencji (vLLM, llama.cpp, Ollama) | częściowo w kodzie, brak w pokazie | `analysis/inference.py`, serwis `inference` (profil `llm`, domyślnie wyłączony). ONNX Runtime liczy E5, ale nie widać go | Nic | **wysokie**: to wprost wymieniona technologia |
| Model open source (Gemma 4, BERT) | częściowo | E5 (rodzina BERT) z regresją logistyczną: 30/57 na zbiorze odłożonym, `affectsDecision: false` | Nic na 18801 | średnie |
| Klasyfikacja ryzyka przez scoring | spełniony regułami | `route` refer/complete/no_signal/insufficient, `score` i `reviewScore` | Siła 0–100 w kolejce | „Scoring z reguł, nie z warstwy wyjściowej modelu” |
| Agregator wyników M1–M3 | spełniony | Wspólny Case, kolejka review łączy M1, M2 i M3 | Jedna kolejka z filtrem modułu | niskie |

### §3.3 Aplikacja webowa

| Punkt briefu | Stan | Dowód | Co jury zobaczy | Ryzyko |
|---|---|---|---|---|
| Filtry: data, źródło, ryzyko, moduł | spełniony | Filtry Platforma, Moduł, Data i siła (zrzut r3 1440-1, 390-1) | Tak | niskie |
| Wykresy trendów (Chart.js, Recharts) | częściowo | `TrendTile` (Sources.jsx), sparkline w kolejce. Biblioteka wykresów Astryx (`charts.jsx`). Dane z jednego dnia | 4 słupki „odtworzenie 21:13…22:35” | „To nie trend w czasie” |
| Zmiana statusu rekordu | spełniony | `PATCH /v1/cases/{key}` z rewizją | Krok 1:30 scenariusza | niskie |
| WebSocket dla alertów wysokiego ryzyka | częściowo | `/v1/events`, `event(db,"high_risk",…)` (`api/store.py:1014–1057`). Ostatnie 50 zdarzeń to `finding` i `scan`, bez `high_risk`. Scenariusz: „najpewniej wywoła… do potwierdzenia” | Prawdopodobnie tylko baner po decyzji | **wysokie**: §6 sprawdza to wprost |
| Parametr progowy | spełniony | `PUT /v1/threshold`, historia 3 wpisów | Suwak | niskie |
| Próg zmienia FP kontra FN | częściowo | `/v1/calibration?threshold=20/40/60/80/95`: FP 0/0/0/0/0, FN 0/0/0/0/2. Parametr `module=M2` jest ignorowany (zwraca M1) | Suwak, który prawie nic nie zmienia, i wykres z płaską linią FP | **wysokie** |
| Biblioteki UI open source | spełniony | React 19, Astryx | — | niskie |
| Architektura oparta o propsy | spełniony | Komponenty funkcyjne z propsami (`TrendGlance({ trend, go })`) | — | niskie |

### §4 Wymagania formalne

| Punkt | Stan | Dowód | Ryzyko |
|---|---|---|---|
| Szczegółowy opis i tytuł | częściowo | `HACKATHON.md`. Liczby nieaktualne („W bazie pokazu są 3 strony”, „FB/IG `access_blocked`”) | średnie |
| Prezentacja PDF | częściowo | `presentation/InvestWatch.pdf`, 9 stron. Nieaktualne: 4 sprawy, 22 reklamy, „Meta automat. zablokowany”, „Compose: API i worker” | średnie |
| Opis kodu (README) | częściowo | README ma 21 linii. Opisuje 5 serwisów z commita 6f62815, ale własne zmiany ma niezacommitowane. Linkuje nieaktualny ODBIOR i instrukcję OpenRouter | średnie |
| Repozytorium kodu | **ryzyko** | `origin/main` = 491094d. Lokalnie 74 commity więcej i 26 zmienionych plików | **wysokie**: formularz ma tylko link do repo |
| Film do 3 min (opcjonalny) | brak | — | Brak zabezpieczenia pokazu |

### §5 Wymagania techniczne

| Punkt | Stan | Dowód | Ryzyko |
|---|---|---|---|
| Modułowa architektura lekkich serwisów | spełniony w kodzie | `compose.yaml`: `web`, `api`, `worker`, `scheduler` (live), `inference` (llm) | Nieprzetestowane na Macu |
| Docker Compose, start jedną komendą | częściowo | `sh ops/demo/start.sh`. Jeden czysty start w Compose (397 s) na Linux przed splitem (commit 7d25695). Brak gotowego stanu w `.runtime/dist/` | **wysokie** |
| Open source, on-premise, bez płatnych API | częściowo | Ścieżka produktu nie woła płatnych API. Pomiary szły przez OpenRouter (wydatki w centach), próbka FB/IG przez ScrapeCreators, transkrypcje przez yt-dlp (poza warunkami YouTube, co przyznaje scenariusz) | średnie: „całkowicie eliminując” jest dosłowne |
| Skan zależności i sekrety w `.env` | spełniony z zastrzeżeniem | `docs/DEMO-ODBIOR.md`: 0 wykryć. `.env.example`. Audyt trzeba powtórzyć po Radix. ODBIOR nadal podaje „częściowe” | niskie |
| README minimalny, bez AI slop | częściowo | README zwięzły, ale w repo jest 3600 linii rekordów linii `fable-*` i rejestr 137 wierszy | średnie |

### §6 Co jury sprawdza

| Punkt | Stan | Co jury zobaczy | Ryzyko |
|---|---|---|---|
| Skuteczność scrapingu | częściowo | 46 źródeł `ok`, 1923 materiały, ale wszystko z datowanego replaya. Mowa tylko w 17 z 1305 filmów. Próba Y niezaliczona (3 z 5) | średnie |
| Trafność AI i wpływ progu | słabo | 26 materiałów strojenia z etykietami dwóch modeli Claude (kappa 1,0). Płaska krzywa. M2 i M3 tylko w PDF | **wysokie** |
| Stabilność UI i powiadomienia w czasie rzeczywistym | nieznane lub częściowo | Zrzuty r3 1440 i 390 bez błędów. Runda r4 w toku. Brak testu reconnect i deterministycznego alertu | wysokie |
| Biblioteki i bezpieczeństwo | spełniony | Audyty 0, kontenery `read_only`, `cap_drop ALL`, sieć `internal` | niskie |
| Console.log | spełniony w kodzie | 0 w `web/src` (jedynie `web/dev-server.mjs`, po stronie serwera). Konsoli przeglądarki nie sprawdzałem | niskie |

### Moduły §2 i źródła

| Moduł | Stan na 18801 | Luka |
|---|---|---|
| M1 finfluencerzy i firmy transgraniczne | 4 sprawy review (XTB), rejestr 290 (YouTube, TikTok, FB, IG), Freedom24, Saxo i eToro w danych. Raport: firma, podmiot reklamujący, treść, URL, data | Jeden reklamodawca w alarmach. Mowa w 17 filmach. Brak cyklu live w bazie |
| M2 materiały własne, także oddziały zagraniczne | 26 stron WWW 11 firm (w tym CMC Germany GmbH, Finax o.c.p., Lynx), 10 `refer`. 19 ID z pomiarem | ID 2 flaguje 18 z 26 stron. 177 pozycji FB/IG `insufficient` zaśmieca listę |
| M3 shadow advisory | 22 oferty z 29 domen, 1 `refer` (rdmwm.pl, „ustal operatora”), kontrola BOŚ | Brak trafienia na liście ostrzeżeń KNF. Reguły v2 strojone na tym samym zbiorze |

| Źródło | Live | Datowana próbka w pokazie | Import ręczny | Blokada |
|---|---|---|---|---|
| WWW (M2, M3) | kod gotowy (Chromium, PoliteFetcher), w pokazie nie | 26 stron M2, 29 domen M3 | `POST /v1/evidence` | — |
| Facebook | nie | 30 postów i 113 reklam (ScrapeCreators, 21 XI) | `POST /v1/import/meta` | Ad Library API: `needs_key` (weryfikacja tożsamości J, której nie będzie) |
| Instagram | nie | 350 postów i 1 reklama (ScrapeCreators) | jw. | Odczyt organiczny wymaga Meta Content Library |
| TikTok | adapter osadzeń działa bez logowania, w pokazie nie | 64 posty z 6 profili (sam podpis, data szacowana) | — | Research API niedostępne |
| YouTube (dodatek spoza briefu) | `--live` z kluczem co 4 h | 1300 (Data API) + 45 (Atom) + 17 z mową i kadrami | upload nagrania | Napisy przez yt-dlp poza warunkami platformy |

## 3. Decyzje pod punktację

Wpływ podaję w punktach wyniku ważonego 0–10. Koszt przy ~10 h do oddania.

| # | Decyzja | Werdykt | Wpływ | Koszt | Uzasadnienie |
|---|---|---|---|---|---|
| a | Reguły decydują, modele weryfikują i dają drugi głos | **ZOSTAW**, ale pokaż model | +0,2…+0,3, jeśli E5 będzie widoczny | S | Dla regulatora cytat i lokalizator to właściwa architektura. Problem nie leży w decyzji, tylko w tym, że w pokazie nie ma żadnego modelu. Włączcie E5 (pakiety są w `.runtime/semantic/deps`) i potwierdźcie `semantic.status: available` w ścieżce, którą zobaczy jury. Jeden slajd z pomiarem drugiego głosu: Gemma 4 31B zgadza się z regułami w 17 z 17 przypadków i naprawia 11 z 11 błędów reguł 1.2 (`fixtures/labeled/ai-second-opinion-summary.json`) |
| b | Datowany replay zamiast skanu na żywo | **ZOSTAW** | 0 (zmiana: −0,5 ryzyka) | — | 429, kwota i sieć na sali to realne zagrożenia. Powiedzcie to w pierwszych 20 s i pokażcie `--live` jako polecenie oraz 4 słupki skanów. Przycisk „Skanuj na żywo” powinien być nieaktywny z wyjaśnieniem |
| c | YouTube jako główne źródło spoza briefu | **ZOSTAW, ZMIEŃ narrację** | +0,1 | S | YouTube daje najlepszy dowód (mowa, kadry). Zaczynajcie jednak od źródeł z briefu: „FB, IG, TikTok i WWW są w bazie, YouTube to miejsce, gdzie polski finfluencer mówi”. W PDF i na kaflach źródeł kolejność: WWW, FB, IG, TikTok, YouTube |
| d | FB/IG z próbki usługi zewnętrznej, import ręczny i adapter oficjalnego API | **ZOSTAW dane, ZMIEŃ etykietę i filtr** | +0,15 (usunięcie daje −0,2 w kat. 4) | S–M | Usunięcie oznacza powrót do „brak” w punkcie, który brief wymienia z nazwy. Trzeba jednak (1) wszędzie pisać jednym zdaniem „jednorazowa próbka z 21 XI przez usługę zewnętrzną (darmowe kredyty), nie część produktu, produkt to import i oficjalne API”, (2) usunąć sprzeczne „access_blocked / nie obchodzimy” albo przenieść je wyłącznie na „automatyczny odczyt przez nasz host”, (3) ukryć w domyślnym widoku M2 pozycje `insufficient` z FB/IG oraz odfiltrować treści nie po polsku i niefinansowe |
| e | LLM przez API na stanowisku pokazu jako jawny przełącznik | **USUŃ ze sceny**, zostaw slajd z pomiarem | uniknięte −0,2…−0,4 w kat. 4 | S | Brief mówi „całkowicie eliminując zewnętrzne, płatne API”. Włączenie OpenRouter przy jury UKNF to samobój, nawet „jawny”. Tryb z 6f62815 zostaw w kodzie wyłączony i nie wspominaj go w README. Lokalną Ollamę pokaż tylko wtedy, gdy przejdzie na Macu, a ta ścieżka nie jest sprawdzona |
| f | SQLite i pliki zamiast Postgres i Object Storage | **ZOSTAW** | 0 (zmiana: −) | L | Ścieżka wzrostu w ARCHITEKTURA.md wystarcza. Migracja w nocy to czyste ryzyko |
| g | Liczba zakładek i złożoność pulpitu | **ZMIEŃ minimalnie** | +0,05…+0,1 | S | 9 zakładek, z czego „Zamknięte” i „Demo i własne pliki” nie służą scenariuszowi. Nie przebudowujcie układu. Wystarczy kolejność zakładek zgodna ze scenariuszem i usunięcie z nagłówka kolejki liczby „1288 czeka na transkrypcję” (przenieść do „Źródeł”) |
| h | Zastrzeżenia w UI („oceny agentów, nie walidacja ekspercka”) | **ZOSTAW, skróć** | ±0,05 | S | Regulator ceni uczciwość, ale duży żółty baner wygląda jak przeprosiny. Wystarczy jedna linia w kalibracji i jedna w PDF. Uzasadnienie w karcie sprawy wystarczy |
| i | M3 z zapisanymi wynikami wyszukiwania zamiast własnej wyszukiwarki | **ZOSTAW** | 0 | — | Własna wyszukiwarka wymaga płatnego API albo scrapingu Google. Pokażcie zapytania i kolejność wyników jako adapter wymienny |
| j | Kryterium 2 M2 flaguje 18 z 26 stron | **ZMIEŃ** (ID 2 jako obserwacja, bez wpływu na trasę), jeśli H zdąży z testem przed zamrożeniem. Inaczej ZOSTAW i powiedz to | +0,05…+0,1 | S | Flaga na 70% stron firm z wykazu wygląda na szum i podważa pozostałe przesłanki. Prawnik UKNF może zgodzić się z ID 2, ale uzna je za drugorzędne wobec ID 3 i 5 |
| k | „Niepełne dane” z setkami pozycji czekających na transkrypcję | **ZMIEŃ prezentację** | +0,1 | S | Widać to w nagłówku i w zakładce (228). To ujawnia, że mowę zbadano w 17 z 1305 filmów. Lepiej powiedzieć sami: „bramka mowy: bez mowy nie alarmujemy, 1288 czeka”. Dociągania transkrypcji z `s4-live` do bazy pokazu nie róbcie po zamrożeniu: `refer-po-mowie.json` jest pusty, więc nowych alarmów to nie da, a ryzyko jest duże |
| l | Brak próby na sprzęcie pokazu | **ZMIEŃ**: nie próba, tylko 3 zabezpieczenia | ochrona przed −1,5 | M | (1) Film 3 min nagrany z bazy kandydata, plik w repo i link w README (spełnia też opcjonalny wymóg §4). (2) Tunel SSH z Maca do devboxa (`ssh -N -L 8769:127.0.0.1:<port> devbox`) sprawdzony rano przez 2 min, z hotspotem z telefonu jako siecią zapasową. (3) Gotowy stan (`pack-state.sh`) i paczka mediów na Macu i na pendrivie. Decyzję, czy pokazujecie lokalnie, podejmijcie 60 min przed pokazem |
| m | Kalibracja tylko M1 | **ZMIEŃ** | +0,2…+0,3 | M | Dodać M2 (etykiety z `m2-agent-eval.json`, 25 stron, przy progu 30 TP 9, FP 1, FN 3). Suwak pokaże wtedy prawdziwy kompromis FP/FN, a o to jury pyta wprost w §6 |
| n | Narracja i liczby w README, HACKATHON, scenariuszu, PDF i ODBIOR | **ZMIEŃ** | +0,15 | S–M | Jedna tabela liczb z zamrożonej bazy w README i PDF. ODBIOR-UKNF.md oznaczyć na górze jako „stan odniesienia 491094d” albo nie linkować go z README |
| o | Alert `high_risk` bez deterministycznego wyzwalacza | **ZMIEŃ** | +0,1 | S–M | Przygotowany plik do „Dodaj dowód” (link i kod bez oznaczenia) → `refer` → baner w drugiej karcie. Sprawdzić dwa razy |

## 4. Lista „do 11:00” (czas polski)

| # | Działanie | Zysk | Nakład | Właściciel | Warunek odbioru |
|---|---|---|---|---|---|
| 1 | Do 02:00: dokończyć i zacommitować UI rundy 4 oraz zmiany `ops/demo` i README. Commity per zakres z prawdziwym `Gate` | warunek wszystkiego | M | integracja H, UI J1 | `git status` czysty (poza `.runtime`, `.claude/worktrees`). `tests/core`, `collectors`, `analysis`, `tools` OK |
| 2 | Do 04:00: zamrożenie kandydata, potem jeden zimny start `sh ops/demo/start.sh --reset` w Compose na devboxie (5 serwisów) i `pack-state.sh`. Od tej chwili żadnych zmian w regułach i bazie | +0,3…+0,6 (ochrona kat. 1) | M | operacje | Kolejka review = liczba w README. `semantic.status: available`. Archiwum stanu i `.sha256` w `.runtime/dist/`. Zapisany SHA commita |
| 3 | Przed zamrożeniem: E5 włączony w ścieżce Compose i `start-local` | +0,15…+0,25 | S | H / operacje | `/v1/overview.semantic.status` = `available`, w karcie widać typ materiału z pewnością |
| 4 | Przed zamrożeniem: kalibracja M2 w API i panelu (przełącznik modułu) | +0,2…+0,3 | M | H + J1 | `/v1/calibration?module=M2` zwraca zbiór M2. Przy progach 30 i 60 FP i FN się różnią. Wykres pokazuje obie linie w ruchu |
| 5 | Przed zamrożeniem: odszumienie i drobne błędy: M2 bez `insufficient` FB/IG w domyślnym widoku, bez treści nie po polsku i niefinansowych. ID 2 bez wpływu na trasę (jeśli test zdąży). Naprawa uciętej nazwy Pekao. Nagłówek „na żywo” → „połączono · odtworzenie 21 XI”. „1288 czeka…” przeniesione do „Źródeł” | +0,1…+0,15 | S–M | H, J1 | Lista M2 zaczyna się od stron WWW z `refer`. Koszykówki i słowackiej reklamy brak w domyślnym widoku |
| 6 | Przed zamrożeniem: deterministyczny alert `high_risk` (plik do „Dodaj dowód”) wpisany w scenariusz | +0,1 | S–M | H | Dwa przebiegi: baner w drugiej karcie w ciągu 5 s |
| 7 | 04:00–06:00: film 2,5–3 min z zamrożonej bazy (ścieżka 2-minutowa plus alert), plik w repo (`presentation/`), link w README. Zrzuty r4 1440 i 390 | ochrona −1,5, §4 opcja | M | operacje / J | Film odtwarza się z GitHuba. Długość ≤ 3:00 |
| 8 | 06:00–08:00: spójne liczby i narracja źródeł w README, HACKATHON.md, `demo.md` i jednym ostatnim PDF. ODBIOR oznaczony jako historyczny. Usunąć link OpenRouter z README | +0,15 | S–M | dokumenty N | Każda liczba w PDF równa się `/v1/overview` zamrożonej bazy. Słowo „zablokowany” odnosi się tylko do odczytu przez nasz host |
| 9 | Do 09:30: push na `main` (merge zamrożonego kandydata), świeży klon i sprawdzenie linków (PDF, film, README), skan sekretów (`git grep -i "key\|token"` na zmianach), bez `.claude/worktrees` | warunek oddania | S | właściciel J | Link z formularza otwiera README z PDF i filmem. `origin/main` = SHA kandydata |
| 10 | 08:30–10:00: 10 min na Macu: tunel do devboxa i, jeśli czas pozwoli, `start-local.sh` z gotowym stanem. Decyzja „lokalnie czy tunel” | ochrona kat. 1 | S | właściciel J | Pulpit otwiera kolejkę z 15 sprawami na Macu (tunel lub lokalnie) |

**NIE RÓB:**
- Skanu na żywo przy jury, nowych źródeł (X, LinkedIn) ani dalszych kredytów ScrapeCreators.
- Włączania trybu API drugiego głosu na stanowisku i jakiegokolwiek wywołania OpenRouter w pokazie.
- Dociągania transkrypcji z `s4-live` ani recompute bazy pokazu po zamrożeniu.
- Dalszego strojenia reguł M1, M2 lub M3 na tych samych zbiorach. Każda zmiana pogłębia zarzut przeuczenia.
- Migracji na Postgres, MinIO lub k8s ani dodawania Dockerfile w nocy.
- Przebudowy nawigacji pulpitu ani nowych zakładek.
- Nowych rekordów linii i dokumentów poza aktualizacją liczb. Kilku wersji PDF: jedna, na końcu.
- Ollamy jako decydenta w kolejce i pobierania modeli na Maca rano (6–7 GB przez sieć sali).
- Commitowania `.claude/worktrees/`, `.runtime/`, kluczy ani surowych odpowiedzi z danymi osób prywatnych.

## 5. Ryzyka pokazu i pytania jury

| Ryzyko | Jak zneutralizować w scenariuszu |
|---|---|
| 1. Stos nie wstaje na MacBooku M3 (Docker Desktop arm64, przygotowanie w kontenerze, zimny start 5–7 min) | Tunel do devboxa jako ścieżka A albo B, ustalona 60 min wcześniej. Gotowy stan zamiast zimnego startu. Film i zrzuty r4 jako ostatnia linia. Nie debugować przy jury |
| 2. Zarzut „płatne API i obchodzenie regulaminów” (OpenRouter, ScrapeCreators, yt-dlp) przed regulatorem | Jedno zdanie na otwarcie części o źródłach: „Produkt działa bez płatnych API. Dla FB/IG pokazujemy jednorazową próbkę z usługi zewnętrznej i import, a produkcyjnie oficjalne API po akredytacji UKNF”. Bez przełącznika API na scenie |
| 3. Kalibracja, która nic nie pokazuje, i alarmy M1 wyłącznie z XTB | Kalibracja M2 z ruchomą krzywą. W M1 pokazać kontrdowód (Comparic) i porównanie z regułami 1.2 (FP 7 → 0). Różnorodność pokazać przez M2: 10 spraw z 8 firm |

| Pytanie jury (pewne) | Czy dziś jest dobra odpowiedź |
|---|---|
| „Gdzie Facebook, Instagram i TikTok i jak je zbieracie?” | Średnia. Dane są, ale dokumenty mówią co innego niż API. Po działaniu 8 odpowiedź będzie dobra |
| „Gdzie jest AI i jak trafne są te klasyfikacje?” | Słaba. Model nie działa w bazie, etykiety pochodzą od agentów, krzywa jest płaska. Po działaniach 3 i 4 średnia |
| „To działa na żywo czy to nagranie?” | Dobra, jeśli powiecie to pierwsi i pokażecie polecenie `--live`. Słaba, jeśli nagłówek będzie mówił „na żywo” |
| „Ile z 1300 filmów naprawdę przeanalizowaliście?” | Słaba: opis we wszystkich, mowa w 17. Bramka mowy jest dobrym argumentem, ale tylko powiedziana z wyprzedzeniem |
| „Czy to zgodne z regulaminami platform i RODO?” | Średnia. Scenariusz uczciwie przyznaje, że yt-dlp wykracza poza warunki YouTube, a ScrapeCreators jest sprzeczny z warunkami Meta. Brakuje zdania o danych osobowych w próbkach w publicznym repo |

## 6. Werdykt

Realnie około 6,9/10, a przy bezbłędnym pokazie na stanowisku i z kalibracją M2 oraz widocznym E5 około 7,8–8,0. Do tego brakuje sprawdzonego uruchomienia u jury, spójnej i uczciwej narracji źródeł oraz modelu, który faktycznie działa w pokazie. Wynik 9 wymagałby walidacji eksperckiej i działania na żywo, czego nie da się zrobić do 11:00.

## Ograniczenia tej oceny

- Nie uruchamiałem Chromium, Compose, modeli ani skanów. UI oceniałem po kodzie, API i zrzutach r3, które opisują starszą bazę. Rundy r4 nie widziałem.
- Baza 18801 to instancja z venv (bez E5). W Compose stan E5 może być inny, czego nie sprawdzałem.
- Stanu na macOS i czasu startu nie mierzyłem. Ocena ryzyka Maca jest statyczna (`ops/mac/README.md`, `prepare-darwin.sh`).
- Punktacja jury to szacunek eksperta, a nie pomiar. Wagi pochodzą z §8.
- Prawnej oceny ID 2 M2, warunków Meta i YouTube ani RODO nie przeprowadzałem. Wskazuję tylko ryzyko pytania.
