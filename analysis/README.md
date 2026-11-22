# Analiza materiałów

`engine.analyze(capture, semantic=...)` zwraca wynik, cytaty i proponowaną kolejkę. Analityk ocenia dowody i zapisuje decyzję.

## Modele na stanowisku

| Model | Zadanie | Uruchomienie |
| --- | --- | --- |
| Multilingual E5 Small | Wskazuje pasujące fragmenty i wspiera klasyfikację typu materiału. | ONNX na CPU. Bootstrap przygotowuje wagi i sprawdza ich skróty. |
| Vosk PL | Zapisuje tekst i czas wypowiedzi w dostępnym nagraniu. | Lokalnie na CPU. Własne wagi można wskazać przez `INVESTWATCH_VOSK_MODEL` i `INVESTWATCH_VOSK_LIBRARY`. |
| Qwen 3.5 4B Q4 | Daje drugi głos w sprawach M1, M2 i M3. | Lokalna Ollama. Domyślny tag to `qwen3.5:4b-q4_K_M`. |

Gdy Ollama jest dostępna, drugi głos dołącza cytat sprawdzony z tekstem źródłowym. Rozbieżność oznacza dowód do weryfikacji. Kolejkę nadal wyznaczają reguły. Gdy lokalny model jest niedostępny, aplikacja pokazuje jego stan i nadal analizuje materiały regułami. [Konfiguracja lokalna](../ops/demo/README.md#lokalny-model-ollama)

OpenRouter służy do jawnych pomiarów z `ops/review/` i `tools/`. Wyniki historyczne można odczytać offline. [Pomiary inferencji](../docs/lanes/2026-11-21-fable-ai-inferencja.md) · [Pomiar drugiego głosu](../docs/lanes/2026-11-21-fable-ai-drugi-glos.md)

## Przepływ analizy

1. Preprocessing: `material_classifier.clean_text`, `dedupe` (HTML, NFKC, URL, znaczniki czasu, powtórzone linie, duplikaty).
2. Embedding: E5 `multilingual-e5-small`, ONNX int8, CPU, 384 wymiary, SHA-256 w `semantic-lock.json`. `semantic.suggest` (woła `api/jobs.py`) wskazuje fragment źródła.
3. Reguły (DECYDUJĄ o trasie): M1 `qualification.qualify` (wariant `qual_d`, domyślny w `api/store.py`) albo `rules_1_2` (`engine.m1` + regułowy `semantic.review_suggestion`); wariant ustawia `api/jobs.py` w `engine.ACTIVE_VARIANT`. Bramki `engine._gate` (mowa) i `_caption_gate`, próg 60 (`DEFAULT_THRESHOLD`) daje `queueEligible`. M2: `m2_card.card` → `m2_rules.evaluate` dla stron rynku, inaczej `checks.marketing` + `m2_evidence.marketing_review_suggestion`. M3: `offers.analyze_entity` → `offers.route`.
4. Typ materiału (OPISUJE): `material_classifier.classify`, regresja logistyczna na E5, 4 klasy, poniżej 0,5 „nieustalone”. Woła go `inference.annotate`, który dodaje `finding.model` z `affectsDecision: false`; włącza `INVESTWATCH_MODEL_ANNOTATE=1`.
5. Drugi głos LLM (OPISUJE): `second_opinion` (M1 ujawnienie, M2 K-03/K-09, M3 oferta) z walidowanym dosłownym cytatem. Rozbieżność ustawia tylko `needsReview`, `affectsRoute: false`. `qualification.priority` też ma `affectsDecision: false`.

| Plik | Odpowiedzialność | Główne wejścia | Testy |
|---|---|---|---|
| `engine.py` | Wejście analizy, M1/M2/M3, warianty, bramki, kalibracja | `analyze`, `calibration`, `module_rules`, `permanent_gap` | `test_engine` |
| `qualification.py` | M1 `qual_d`: relacja reklamowa, przesłanki, siła, pokrycie | `qualify`, `priority` | `test_qualification` |
| `firm_index.py`, `firm-index.json` | Aliasy firm M1 z datowanych rejestrów KNF | CLI `[--check]` | `test_qualification` |
| `m2_rules.py`, `m2_readability.py` | 19 kryteriów M2 na blokach renderu; czytelność ostrzeżeń (kryt. 9) | `evaluate`, `measure` | `test_m2_rules` |
| `m2_card.py` | Karta M2: 19 wierszy, wynik, 3 powody | `card`, `build` | `test_m2_rules`, `collectors/test_m2_market` |
| `checks.py`, `m2_evidence.py` | M2 poza rynkiem: 19 sprawdzeń; pomiary Chromium jako obserwacje | `marketing`, `show_checks`, `marketing_review_suggestion` | `test_engine` |
| `m2_eval.py`, `m2_fixture.py` | Ocena M2 na etykietach agenta (`api/calibration_modules.py`); syntetyczne strony do testów | CLI `[--write]`; `block`, `material` | `test_m2_rules` |
| `offers.py` | M3: 4 osie oferty, dopasowanie do list KNF, trasa | `analyze_entity`; CLI `registers\|analyze\|evaluate` | `test_offers` |
| `semantic.py`, `setup_semantic.py`, `semantic-lock.json`, `semantic-requirements.txt` | E5: fragment źródła; instalacja wag | `suggest`, `review_suggestion`; CLI | `test_semantic` |
| `material_classifier.py`, `material-type-weights.json` | Typ materiału | `classify`; CLI `sample\|train\|evaluate\|classify` | `test_inference` |
| `inference.py` | Klient Ollama, adnotacja modelu | `annotate`; CLI `status\|evaluate\|classify` | `test_inference` |
| `second_opinion.py` | Drugi głos po regułach | `review_m1`, `review_m2_k09`, `review_m3`, `attach` | `test_second_opinion` |
| `openrouter_review.py`, `ollama_review.py` | Porównanie przeglądu dowodów: OpenRouter, lokalna Ollama (pomiar, poza produktem) | CLI; `ops/review/openrouter.sh`, `ops/mac/check.sh` | `test_openrouter_review`, `test_ollama_review` |
| `transcribe.py`, `setup_asr.py`, `asr-lock.json` | ASR Vosk PL, CPU, offline, do 120 s; instalacja z SHA-256 do `.runtime/asr` | `transcribe_file`, `transcribe_excerpt`, `replay_file`; CLI `[--replay]` | `test_engine` |
| `make_sample.py`, `media/*.mp4`, `media/*.asr.json` | Fikcyjne klipy `studio` i `wezwanie` (eSpeak-NG) z zapisanym ASR | CLI `[--cta]` | `test_engine` |
| `__init__.py` | Pakiet | — | — |

Kto woła: `api/jobs.py` (`analyze`, `semantic`, `transcribe_file`; wołany przez `api/worker.py`), `api/store.py` (`qualification`, `semantic`, `setup_semantic`, `module_rules`), `api/server.py` (`calibration`, `second_opinion`), `api/enrich.py`, `api/listen.py`, `api/calibration_modules.py`, `collectors/media.py` (`transcribe_excerpt`), `tools/measure_*.py`, `ops/demo/bootstrap.sh`, `ops/mac/*.sh`.



```sh
python3 -m analysis.setup_asr && python3 -m analysis.transcribe --replay analysis/media/studio.mp4
python3 -m analysis.material_classifier evaluate          # E5, zbiór odłożony
python3 -m analysis.inference status                      # silnik i digest wag
sh ops/mac/measure-llm.sh --pull                          # trafność LLM na Macu
python3 tools/measure_second_opinion.py report            # drugi głos z zapisanych pomiarów
python3 -B -m unittest discover -s analysis -t . -p 'test_*.py'
```
