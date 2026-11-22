# Dane, replay i zbiory walidacyjne

Odtwarzanie korzysta z zapisanych odpowiedzi źródeł. Materiały z etykietami służą do pomiaru reguł i modeli. Pełne transkrypcje i kadry z 21 listopada są w osobnej paczce `.runtime/replay-media/2026-11-21` przygotowywanej przez `sh ops/demo/pack-media.sh`.

Stan pokazowy z 21 listopada obejmuje **1 922 materiały**, a rozszerzenie z 22 listopada **13 690**. Te liczby pochodzą z dwóch osobnych stanów pulpitu. Tabela poniżej opisuje poszczególne pliki wejściowe, które mogą obejmować tylko część stanu. [Zakres i pochodzenie](../docs/MONITORING.md)

## raw/ · surowe odpowiedzi źródeł

| Ścieżka | Źródło | Kto czyta |
|---|---|---|
| `raw/discovery/2026-11-21.json` | Datowany wybór wyników publicznych ze skróconymi cytatami, zapis 15:55 UTC | `collectors/discovery.py`, `analysis/test_qualification.py` |
| `raw/discovery/youtube-api-2026-11-21/` | YouTube Data API v3: zapytania `search`, `videos`, `playlistItems`; `replay.json.gz` (1300 materiałów, 380 kanałów) to replay pokazu, `requests.jsonl` log żądań | `collectors/youtube.py`, `api/jobs.py`, `analysis/material_classifier.py` |
| `raw/discovery/youtube-api-2026-11-21b/` | YouTube Data API v3, drugi przebieg 20:34 UTC: monitoring 209 znanych kanałów przed odkrywaniem (1205 z 2500 jednostek) | brak odczytu w kodzie; opis w [rekordzie linii B](../docs/lanes/2026-11-21-fable-b-youtube.md) |
| `raw/discovery/youtube-probe-2026-11-21/` | `tools/youtube_probe.py`: Apple Podcasts, RSS, Wikidata, oEmbed (bez klucza) i YouTube Data API | `collectors/test_crosslinks.py` |
| `raw/discovery/social-2026-11-21/` | Publiczne osadzenia TikTok, profile Facebook/Instagram, oEmbed bez tokenu, Meta Ad Library (strona i API bez tokenu, odpowiedzi odmowne) | `collectors/social.py`, `api/jobs.py` |
| `raw/discovery/social-2026-11-21/alt/`, `manifest-meta.json`, `replay-meta.json.gz` | Meta Ad Library i osadzenia Instagram zapisane w przeglądarce, wczytane ręcznym importem (`meta-import-1`, 22:10 UTC, 28 materiałów) | `collectors/meta_import.py` |
| `raw/discovery/social-2026-11-21/vendor/` | ScrapeCreators (`api.scrapecreators.com`), 21:28 UTC, 74 kredyty, 3 nieudane żądania; sumy SHA-256 w `manifest-vendor.json` | `collectors/vendor_social.py` |
| `raw/discovery/m3-2026-11-21/` | Wyniki wyszukiwarki WebSearch agenta (produkt nie ma klucza wyszukiwarki), odczyt stron podmiotów (`requests.jsonl` z robots.txt), wyciągi rejestrów KNF | `collectors/discovery.py`, `analysis/test_offers.py`, `api/calibration_modules.py` |
| `raw/media/2026-11-21/` | Analiza mediów 17 filmów (napisy yt-dlp, kadry); `replay-pack.manifest.json` opisuje paczkę poza Gitem | `api/replay_pack.py`, `tests/core/test_contract_v2_qualification.py` |
| `raw/review-compare/` | Przebiegi Qwen 3.5 9B/27B przez OpenRouter, wejścia, wyniki reguł, liczby tokenów | `analysis/test_qualification.py`, `tests/core/test_review_adapters_offline.py` |

## labeled/ · etykiety i wyniki pomiarów

| Plik | Zawartość | Kto czyta |
|---|---|---|
| `showcase.json`, `calibration.json` | 6 materiałów pokazowych; 13 przypadków kalibracji (9 syntetycznych, 4 publiczne) | `analysis/engine.py` |
| `ai-material-type.json` | Etykiety „typ materiału” na replay YouTube; jeden oznaczający agent (claude-opus-5-5) | `analysis/material_classifier.py`, `tools/measure_llm_openrouter.py` |
| `ai-material-type-result-e5.json` | Pomiar lokalnego E5 na zbiorze odłożonym (devbox CPU) | `api/second_opinion_recorded.py` |
| `ai-material-type-result-<model>[-mt-llm-1].json` | Pomiar 6 modeli otwartych wag przez OpenRouter (`tools/measure_llm_openrouter.py`) | brak odczytu w kodzie; wynik dokumentacyjny |
| `ai-second-opinion-{m1,m2k03,m2k09,m3}-<model>.json`, `-summary.json` | Drugi głos LLM, 10 modeli przez OpenRouter (`tools/measure_second_opinion.py`) | `api/second_opinion_recorded.py` |
| `m2-agent-labels.jsonl`, `m2-agent-eval.json`, `m3-agent-labels.jsonl`, `m3-agent-eval-v{1,2}.json` | Etykiety agenta (claude-opus-5-5) zapisane przed regułami i ich ocena | `api/calibration_modules.py`, `analysis/m2_eval.py` |

## validation/ · zamrożone

Zamrożono 21 XI 2026 18:46 UTC (commit `491094d`). Nie edytować: zmiana tworzy nową wersję protokołu. [Protokół](validation/PROTOKOL.md), [skróty plików](validation/FREEZE.json), [inwentarz](validation/INWENTARZ.md). `q-v1/` zbiór strojenia, `q-v2/` warianty M1, `y-reference/` niezależna lista kanałów (zakaz użycia w odkrywaniu).

## data/probe-snapshots

Datowane sondy z 21 XI (KNF, strony M2 w przeglądarce, źródła social); sumy w `2026-11-21-evidence.sha256` sprawdza `python3 tools/check_plan_evidence.py`.
