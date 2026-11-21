# Drugi głos LLM po regułach: M1, M2, M3

Linia `hack/integration`, 2026-11-21. Wykonawca: agent `claude-opus-5-5`. Pytanie badawcze: czy model z otwartymi wagami, użyty jako drugi głos po regułach (nie zamiast nich), mierzalnie poprawia wynik tam, gdzie reguły się mylą, i jaki najmniejszy model wystarcza.

> **Etykiety pochodzą od agentów (Claude), nie od ekspertów.** Zbiory są małe (17, 13, 19 i 29 przypadków). Reguły strojono na tych samych materiałach. Prompt dopracowano na części strojenia. Każdą liczbę traktuj jako sygnał kierunku, nie jako dowód skuteczności.

## Wynik w skrócie

| Moduł | Czy włączać | Model (najmniejszy, który nie psuje) | Dlaczego |
|---|---|---|---|
| **M3** oferta doradztwa | **Tak, jako weto-znacznik** w kolejce „do uzupełnienia” | `qwen3.8:27b-q4_K_M` (18 GB); awaryjnie `ministral-3:3b-instruct-2512-q4_K_M` | Koszt 2×FN+FP spada z 10 do 1, na zbiorze odłożonym z 4 do 0. Model nie zepsuł żadnego trafienia reguł. |
| **M1** ujawnienie współpracy | **Tak, jako znacznik kontrolny**, bez wpływu na trasę | `qwen3.5:9b-q4_K_M` (6,6 GB) | Domyślny `qual_d` nie ma błędów, więc nie ma czego naprawiać. Model potwierdza 17/17 i daje cytat z czasem. Wobec starego `rules_1_2` naprawia 11/11 błędów. |
| **M2 K-03** ryzyko przy korzyści | **Nie** | – | Żaden model nie poprawił wyniku. Najlepsze (Gemma 4 31B, Qwen3.8 27B) zgadzają się z regułami 13/13, a reszta psuje 1–4 przypadki. |
| **M2 K-09** zrozumiałość | **Nie** (najwyżej opis w karcie) | – | Na poziomie strony nic się nie zmienia, bo K-09 waży 5 pkt. Etykieta jest subiektywna: agent nie oznaczył żadnej strony. |

Tryb pokazowy przez API: **`qwen/qwen3.8-27b`**, czyli te same wagi co lokalny `qwen3.8:27b-q4_K_M` (szczegóły w sekcji „Tryb pokazowy”).

## Projekt drugiego głosu

`analysis/second_opinion.py`. Każde pytanie weryfikuje jedną konkretną decyzję reguł i dostaje pełny kontekst tej decyzji. Wynik ma postać `{verdict, quote, locator, confidence, explanation}`, gdzie `explanation` to jedno zdanie. Walidator przyjmuje cytat tylko wtedy, gdy występuje dosłownie we wskazanej linii wejścia. Normalizuje przy tym spacje, cudzysłowy i myślniki i dopuszcza przejście na sąsiednią linię. Cytat spoza wejścia oznacza odrzucenie (`status: rejected`), a nie werdykt. Rozbieżność z regułami ustawia `needsReview: true` i `reviewLabel: "rozbieżność — do przeglądu"`. Pole `affectsRoute` ma zawsze wartość `false`.

- **M1 `m1_disclosure`.** Reguły znalazły relację handlową z firmą X: link lub kod w opisie, cytaty w `dowodRelacji`. Model czyta opis, a potem całą transkrypcję w oknach po 8000 znaków. Segmenty auto-napisów łączy w linie po około 260 znaków ze znacznikiem czasu. W każdym oknie odpowiada na pytanie: „czy autor ujawnia współpracę z X?”. Ujawnienie to pierwszy przyjęty cytat razem z czasem. **Brak ujawnienia stwierdzamy wyłącznie wtedy, gdy każde okno odpowiedziało „brak_ujawnienia”.** Jedno odrzucone, nierozstrzygnięte albo niedostępne okno oznacza brak werdyktu. Prompt `so-2` mówi wprost, że link z kodem twórcy jest dowodem relacji, a nie ujawnieniem.
- **M2 `m2_k03`.** Model dostaje twierdzenie o korzyści wskazane przez reguły. Dostaje też bloki strony w promieniu jednego ekranu (±900 px) z pozycją y i rolą bloku oraz paski przyklejone. Pytanie: czy przy twierdzeniu jest ostrzeżenie o ryzyku tego samego produktu? Ostrzeżenie CFD nie dotyczy akcji ani ETF.
- **M2 `m2_k09`.** Model dostaje treść ostrzeżenia w zdaniach. Pytanie: czy klient detaliczny zrozumie, że może stracić pieniądze? Odpowiedź uzasadnia jednym zdaniem.
- **M3 `m3_offer`.** Model dostaje strony podmiotu w liniach `P0L3` i fragmenty wskazane przez reguły. Długie strony są przycinane: zostaje początek strony i otoczenie dowodów reguł, łącznie do 14 000 znaków. Pytanie: czy podmiot oferuje usługę rekomendacji dotyczących instrumentów finansowych? Do takich usług należą doradztwo, zarządzanie portfelem, sygnały, portfele modelowe i doradztwo majątkowe. Alternatywy to informacja albo edukacja oraz produkt spoza katalogu. Odstępstwo od briefu: etykieta „complete” obejmuje też sygnały bez personalizacji (ppcg, deriv, inwestowaniegpw). Dlatego pytanie dotyczy „oferty rekomendacji”, a nie samej „personalizacji”. Personalizację i wykazy KNF nadal ocenia reguła.

## Pomiar

Narzędzie: `tools/measure_second_opinion.py`. Polecenie `cases` buduje wejścia raz, bez sieci (`.runtime/second-opinion/cases-*.json`, `inputSha` w każdym wyniku). `run` wysyła je do OpenRouter, a `report` liczy metryki. Wszystkie modele dostały identyczne wejścia, temperaturę 0, seed 0, `json_schema` w trybie strict i wyłączone rozumowanie tam, gdzie dostawca to obsługuje. Zabezpieczenia: transport, lokalny cennik i wybór endpointu ze `structured_outputs` pochodzą z `measure_llm_openrouter.py`. Limit ceny wynosi 3 USD/Mtok, limit na model 0,60 USD, a limit serii 2,40 USD w osobnym rejestrze (`.runtime/second-opinion/ledger/`), sumowanym przy każdym żądaniu. HTTP 429 ponawiamy z odczekaniem. Ustawienie `data_collection: deny`. Klucz jest redagowany. Wyniki: `fixtures/labeled/ai-second-opinion-<moduł>-<model>.json`, podsumowanie w `ai-second-opinion-summary.json`.

**Zbiory i podział** (po jednostce niezależnej: kampania, firma, domena; skrót SHA-256):

| Moduł | Przypadki | Pozytywy | Strojenie / odłożone | Błędy reguł |
|---|---|---|---|---|
| M1: 17 filmów q-v2 z pełną transkrypcją, relacja znaleziona przez reguły | 17 | 4 nieoznaczone | 9 / 8 (po 2 pozytywy) | `qual_d` 0; `rules_1_2` 11 (7 FP, 4 FN) |
| M2 K-03: strony, na których reguły znalazły twierdzenie o zysku | 13 | 7 (`"3"` w etykiecie) | 5 / 8 | 3 (FP bdm, cmc-akcje; FN tms-krypto) |
| M2 K-09: strony z ostrzeżeniem | 19 | 0 | 8 / 11 | 9 FP na poziomie kryterium |
| M3: 29 podmiotów z etykietą i tekstem | 29 | 6 (complete/refer) | 14 / 15 (po 3 pozytywy; sól `m3-1` dobrana przed pierwszym uruchomieniem) | 10 FP w kolejce, 0 FN |

**Strojenie promptu.** Wykonano je tylko na części strojenia i tylko modelem Qwen3.5 397B. W wersji `so-1` model uznawał link z kodem za ujawnienie (2 zepsute pozytywy M1). Wersja `so-2` doprecyzowała to w instrukcji M1. Dodatkowo walidator zaczął przyjmować cytat przechodzący na poprzednią linię. Pozostałe prompty są bez zmian. Wszystkie modele zmierzono na `so-2` na całym zbiorze. Dla Qwen3.5 397B część strojenia oceniano trzykrotnie.

### Wyniki na całości (n jak wyżej; w nawiasie zbiór odłożony)

Kolumny „Naprawione” i „Zepsute” liczą tylko odpowiedzi przyjęte przez walidator. „Odrzucone” podaje odpowiedzi odrzucone na przypadek, a dla M1 dodatkowo wywołania na okna. Koszt 2×FN+FP liczymy w trzech wariantach: same reguły / weto (model może tylko zdjąć pozytyw reguł) / eskalacja (model może tylko dodać materiał do przeglądu).

**M1 względem domyślnego `qual_d`** (reguły: 0 błędów, koszt 0) **i starego `rules_1_2`** (11 błędów, koszt 15):

| Model (licencja) | Zepsute wobec qual_d | Odrzucone: przypadki / wywołania | Naprawione wobec rules_1_2 (odłożone) | rules_1_2: weto / eskalacja | Koszt USD |
|---|---|---|---|---|---|
| DeepSeek V4 Pro (MIT) | 0 | 3 / 3 z 39 | 10 (4) | 9 / 7 | 0,115 |
| Qwen3.5 397B-A17B (Apache-2.0) | 0 | 2 / 3 z 36 | 10 (5) | 8 / 9 | 0,042 |
| Qwen3.8 27B (Apache-2.0) | 0 | 1 / 1 z 37 | 11 (5) | 8 / 7 | 0,008 |
| Gemma 4 31B (Apache-2.0) | 0 | 0 / 0 z 35 | 11 (5) | 8 / 7 | 0,009 |
| Gemma 4 26B-A4B (Apache-2.0) | 0 | 0 / 0 z 31 | 11 (5) | 8 / 7 | 0,004 |
| Mistral Small 3.2 24B (Apache-2.0) | 2 | 2 / 2 z 39 | 11 (5) | 8 / 9 | 0,008 |
| Ministral 3 14B (Apache-2.0) | 1 | 4 / 6 z 31 | 7 (3) | 9 / 13 | 0,013 |
| **Qwen3.5 9B (Apache-2.0)** | **0** | 0 / 1 z 35 | **11 (5)** | 8 / 7 | 0,009 |
| Ministral 3 8B (Apache-2.0) | 1 | 1 / 3 z 31 | 10 (4) | 8 / 9 | 0,010 |
| Ministral 3 3B (Apache-2.0) | 3 | 3 / 10 z 42 | 7 (2) | 10 / 12 | 0,010 |

Przy `rules_1_2` weto zdejmuje 7/7 FP (koszt 15 → 8). Eskalacja dodaje 4/4 FN (koszt 15 → 7). Gdyby model zastąpił decyzję o ujawnieniu, koszt spadłby do 0. Tę samą rozdzielność daje dziś `qual_d`. Wszystkie 4 pozytywy to linki programu partnerskiego XTB.

**M2 K-03** (reguły: 3 błędy kryterium; koszt strony 2×FN+FP = 2 na tych 13 stronach):

| Model | Naprawione | Zepsute | Odrzucone | Zgodność z regułami | Strona: reguły / weto / eskalacja | Koszt USD |
|---|---|---|---|---|---|---|
| DeepSeek V4 Pro | 1 | 3 | 0/13 | 9/13 | 2 / 2 / 2 | 0,031 |
| Qwen3.5 397B | 0 | 2 | 1/13 | 10/12 | 2 / 4 / 3 | 0,015 |
| Qwen3.8 27B | 0 | 0 | 0/13 | 13/13 | 2 / 2 / 2 | 0,003 |
| Gemma 4 31B | 0 | 0 | 0/13 | 13/13 | 2 / 2 / 2 | 0,003 |
| Gemma 4 26B-A4B | 0 | 0 | 1/13 | 12/12 | 2 / 2 / 2 | 0,002 |
| Mistral Small 3.2 | 0 | 3 | 2/13 | 8/11 | 2 / 6 / 3 | 0,002 |
| Ministral 14B | 0 | 2 | 1/13 | 10/12 | 2 / 4 / 3 | 0,004 |
| Qwen3.5 9B | 0 | 1 | 0/13 | 12/13 | 2 / 2 / 0 | 0,003 |
| Ministral 8B | 1 | 3 | 2/13 | 7/11 | 2 / 7 / 3 | 0,003 |
| Ministral 3B | 1 | 4 | 1/12 | 7/12 | 2 / 8 / 2 | 0,002 |

Qwen3.5 9B w eskalacji osiąga koszt 0 na poziomie strony, ale to efekt jednego przypadku (tms-krypto) przy zepsutym kryterium gdzie indziej. Nie traktujemy tego jako wyniku.

**M2 K-09** (0 pozytywów w etykietach, reguły 9 FP): najlepsze weto mają Gemma 4 26B-A4B (naprawione 6, zepsute 2) i Qwen3.5 9B (6/3). Duże modele wypadają gorzej: Qwen3.5 397B 4/6, DeepSeek 2/4. Koszt na poziomie strony wynosi 6 dla każdego modelu i każdej polityki. Zgodność modeli między sobą jest niska, co potwierdza wcześniejszą ocenę: etykieta „zrozumiałe” jest subiektywna, a pomiar nie pozwala wybrać modelu.

**M3** (reguły: 10 FP, 0 FN, koszt 10; zbiór odłożony: koszt 4). „Naprawione” i „zepsute” nie obejmują 5 podmiotów, o których rozstrzyga wykaz KNF (`authorized_advice`, `investment_firm_agent`). Etykieta wynika tam z wykazu, a nie z treści. Eskalacja ich nie dotyczy.

| Model | Trafne | Naprawione | Zepsute | Odrzucone | Weto: koszt (odłożone) | Eskalacja | Koszt USD |
|---|---|---|---|---|---|---|---|
| DeepSeek V4 Pro | 20/21 | 8 | 0 | 3/29 | 2 (1) | 10 | 0,152 |
| Qwen3.5 397B | 19/20 | 7 | 0 | 3/29 | 3 (1) | 10 | 0,053 |
| **Qwen3.8 27B** | **22/22** | **9** | **0** | 2/29 | **1 (0)** | 10 | 0,009 |
| Gemma 4 31B | 19/22 | 7 | 2 | 1/29 | 3 (3) | 12 | 0,012 |
| Gemma 4 26B-A4B | 13/22 | 4 | 4 | 3/29 | 6 (3) | 14 | 0,006 |
| Mistral Small 3.2 | 18/22 | 7 | 2 | 2/29 | 3 (1) | 12 | 0,010 |
| Ministral 14B | 16/18 | 6 | 1 | 6/29 | 4 (1) | 11 | 0,024 |
| Qwen3.5 9B | 19/22 | 8 | 3 | 2/29 | 8 (2): zdejmuje 3 prawdziwe pozytywy | 10 | 0,012 |
| Ministral 8B | 18/20 | 7 | 1 | 5/29 | 3 (1) | 11 | 0,017 |
| Ministral 3B | 19/21 | 9 | 1 | 4/29 | 1 (1) | 11 | 0,011 |

Reguły M3 nie mają FN, więc eskalacja nie ma czego naprawiać i tylko dokłada FP. Weto działa: Qwen3.8 27B zdejmuje 9 z 10 FP i nie zdejmuje żadnego pozytywu. Ministral 3B osiąga ten sam koszt, ale odrzuca 14% odpowiedzi (wtedy weto nie działa, a koszt nie rośnie). Przy obu modelach zostaje FP na spolkawsingapurze.pl albo kursnagielde.pl. To artykuły, które model raz czyta jako ofertę.

**Koszt pomiaru:** 0,740 USD wg `usage.cost` (rejestr serii) przy limicie tury 2,50 USD. Czasy z API (mediana na przypadek 0,7–23 s, M1 to kilkadziesiąt okien) to opóźnienie dostawców, a nie czas lokalny.

**Czego nie zmierzono:** Mistral Large 3 (675B, Apache-2.0): endpoint Mistral zwracał HTTP 429, zmierzono 2 przypadki. gpt-oss-120b (Apache-2.0): HTTP 400 u dwóch dostawców, prawdopodobnie przez wymuszone wyłączenie rozumowania. Llama pominięta z powodu licencji. Wyniki pochodzą z wag BF16 lub FP8 u dostawców (Qwen3.8 27B: Chutes fp8), a nie z Q4 w Ollama. Dostawcy nie są w pełni deterministyczni nawet przy temperaturze 0: Qwen3.5 397B dał inne abstencje M3 w dwóch przebiegach na tych samych wejściach.

## Rekomendacja i wymagania sprzętowe

- **Serwer UKNF:** jeden model dla M1 i M3, czyli `qwen3.8:27b-q4_K_M` (Apache-2.0). Pobranie 18 GB, około 22 GB RAM/VRAM przy `num_ctx` 8192 (szacunek). Wystarczy jedna karta 24 GB (L4/A10/RTX 4090) albo CPU z 32 GB RAM (wolno). Duże modele (Qwen3.5 397B, DeepSeek V4 Pro) nie dały lepszego wyniku niż 27B, więc nie ma powodu stawiać ich lokalnie (Q4 to około 230 GB i około 900 GB).
- **MacBook M3:** przy 32 GB lub więcej ten sam `qwen3.8:27b-q4_K_M`. Przy 16 GB `qwen3.5:9b-q4_K_M` (6,6 GB) dla M1, który ma 17/17 przy 0 zepsutych. Dla M3 przy 16 GB nie bierz Qwen3.5 9B: zdejmuje prawdziwe pozytywy. Weź `ministral-3:8b-instruct-2512-q4_K_M` (6,0 GB; weto 3, odrzucenia 17%) albo `ministral-3:3b-instruct-2512-q4_K_M` (3,0 GB; weto 1, odrzucenia 14%).
- **M2:** nie włączać drugiego głosu ani dla K-03, ani dla K-09. Na K-03 nic nie poprawia. K-09 można najwyżej pokazać jako opis w karcie, bez wpływu na punkty.
- **Polityka:** wynik zawsze jako `secondOpinion` z `needsReview`. W M3 rozbieżność „model: informacja lub edukacja” przy trasie `complete` to znacznik dla analityka (np. sortowanie kolejki na koniec), a nie zmiana trasy. W M1 rozbieżność z `qual_d` oznacza „do przeglądu”.
- Przed włączeniem domyślnym potrzebny jest pomiar Q4 lokalnie (`ollama pull qwen3.8:27b-q4_K_M`, to samo `cases` na Ollama). Sprawdzenia wymaga też obsługa `format` ze schematem w Ollama dla tej architektury.

## Tryb pokazowy (decyzja J z 21 XI)

`INVESTWATCH_LLM_DEMO_API=1` oraz `INVESTWATCH_LLM_DEMO_MODEL` (domyślnie `qwen/qwen3.8-27b`) włączają w procesie produktu zaplecze OpenAI-compatible dla modeli z listy `MODEL_CARDS`. Na liście są wyłącznie modele z otwartymi wagami i zapisaną licencją. Bez flagi zachowanie się nie zmienia. Każdy wynik zawiera `modelId`, `weightsLicense`, `localQ4Gb`, `localMemoryGb`, `localModel` i `runtime: "api-demo" | "local"` oraz etykietę po ludzku, np. „model Qwen3.8 27B · Apache-2.0 · uruchomiony przez API (pokaz); lokalnie: ollama pull qwen3.8:27b-q4_K_M”. Dobowy limit kosztu `INVESTWATCH_LLM_DEMO_DAILY_USD` (domyślnie 1,0) liczy księga `.runtime/second-opinion/demo-ledger.json`. Po jego przekroczeniu tryb wyłącza się do końca doby (`demo_budget_exceeded`). Wyniki trafiają do pamięci podręcznej po skrócie wejścia, a pole `affectsRoute` ma wartość `false`.

**Otwarte: kto trzyma klucz.** Próbę dodania do `second_opinion.py` odczytu klucza OpenRouter (zmienna albo `.env.openrouter`) i wysyłki z procesu produktu **zablokował system uprawnień sesji** (klasyfikator: wyciek danych wrażliwych). Nie obchodziłem tego. Moduł przyjmuje więc transport przez `register_demo_transport(chat, meta)` i sam nie ma klucza. Brakuje małego launchera po stronie stanowiska pokazowego. Launcher czyta klucz, buduje ciało żądania (dostawca ze `structured_outputs`, `data_collection: deny`, `max_price`) przez `openrouter_review._post` i wywołuje `register_demo_transport` przy starcie API. Decyzję, czy i gdzie ma powstać, podejmuje J lub orkiestrator. Wzorzec jest w `tools/measure_second_opinion.py` (`SeriesMeter`).

## Wpięcie (fragment dla właściciela `analysis/engine.py`)

```python
# analysis/engine.py, po zbudowaniu findingu przez reguły modułu (domyślnie nic nie robi)
from analysis import second_opinion as so

def _second_opinion(finding, capture, module_view):
    if not so.enabled():
        return finding
    try:
        if finding["module"] == "M1":
            rel = (finding.get("adRelationship") or {})
            if rel.get("status") in ("declared", "documented", "probable"):
                quotes = [e["text"] for e in finding.get("evidence") or []
                          if e.get("modality") == "description" and e.get("role") != "disclosure"][:3]
                rules = "brak_ujawnienia" if (finding.get("reviewDecision") or {}).get("route") == "refer" else "ujawnione"
                second = so.review_m1(capture, (rel.get("firm") or {}).get("mention"), quotes, rules)
                return so.attach(finding, second)
        elif finding["module"] == "M3" and finding.get("route") in ("complete", "refer"):
            evidence = [e for axis in ("action", "personalisation") for e in (finding["axes"][axis].get("evidence") or [])]
            second = so.review_m3(module_view["pages"], evidence, "oferta_rekomendacji")
            return so.attach(finding, second)
    except Exception as error:  # drugi głos nigdy nie zatrzymuje skanu
        return so.attach(finding, {**so.disabled("error"), "status": "unavailable", "reason": type(error).__name__})
    return finding
```

Kontrakt pola `secondOpinion`: `task`, `status` (`disabled|ready|abstained|rejected|unavailable|busy|empty`), `verdict`, `quote`, `locator` (M1: `field`, `lineId`, `seconds`, `time`; M3: `url`, `line`; M2: `viewport`, `block`), `confidence`, `explanation`, `rulesVerdict`, `agreement`, `needsReview`, `reviewLabel`, `modelId`, `weightsLicense`, `runtime`, `displayLabel`, `localModel`, `localQ4Gb`, `localMemoryGb`, `promptVersion`, `digest`, `latencyMs`, `affectsRoute: false`. Karta pokazuje werdykt i cytat tylko przy `ready`. Statusy `rejected`, `busy` i `unavailable` oznaczają brak drugiego głosu, nigdy brak sygnału. Zmienne: `INVESTWATCH_SECOND_OPINION=1`, `INVESTWATCH_SECOND_OPINION_MODEL` (domyślnie `qwen3.8:27b-q4_K_M`), `INVESTWATCH_SECOND_OPINION_CTX` (8192), `INVESTWATCH_SECOND_OPINION_TIMEOUT` (180 s), `OLLAMA_HOST`.

## Weryfikacja

- `.runtime/venv/bin/python -B -m unittest analysis.test_second_opinion analysis.test_inference`: 40 testów, OK, 1 pominięty (pominięcie w `test_inference`). Na `test_second_opinion` przypada 19 testów offline na atrapie Ollamy i atrapie transportu pokazowego.
- Powtórzenie pomiaru: `.runtime/venv/bin/python -B tools/measure_second_opinion.py cases`, potem `run --model qwen/qwen3.8-27b --module all --split all --public-source` (około 0,02 USD), a na końcu `report`.

## Ograniczenia

- Mianowniki: M1 ma 4 pozytywy z jednego reklamodawcy i jednego mechanizmu (link-pso XTB). M2 K-03 ma 13 stron, K-09 nie ma pozytywów. M3 ma 6 pozytywów, z czego 3 w zbiorze odłożonym. Przedziały ufności są bardzo szerokie.
- Etykiety pochodzą od agentów (Claude, M1 dwóch oceniających, M2 i M3 jeden). Werdykt modelu, który „naprawia” błąd reguł, zgadza się z agentem, a nie z ekspertem.
- Prompt strojono na części strojenia tych samych zbiorów. Reguły strojono na tych samych stronach i filmach.
- Pomiar wykonano przez API na wagach BF16/FP8, bez Q4 i bez pomiaru czasu lokalnie. Dostawcy nie są w pełni deterministyczni.
