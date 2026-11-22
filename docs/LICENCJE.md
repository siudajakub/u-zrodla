# Licencje zależności, modeli i usług

Repozytorium nie ma pliku LICENSE, NOTICE ani COPYING (sprawdzone `ls`). Wybór licencji projektu należy do właściciela. Dane z metadanych lokalnych (stan 21 XI 2026, bez sieci). Reguła projektu: kod produktu używa zależności i modeli na licencjach permisywnych.

## Python

Źródło licencji: `*.dist-info/METADATA` w `.runtime/venv`. Pakiety bez instalacji w venv mają "nieustalona offline".

| Nazwa | Wersja | Licencja | Źródło (plik lock) |
|---|---|---|---|
| annotated-doc | 0.0.7 | MIT | api/requirements.lock |
| annotated-types | 0.8.0 | MIT | api/requirements.lock |
| anyio | 4.16.0 | MIT | api/requirements.lock |
| click | 8.5.1 | BSD-3-Clause | api/requirements.lock |
| fastapi | 0.165.0 | MIT | api/requirements.lock |
| h11 | 0.16.0 | MIT | api/requirements.lock |
| huey | 3.5.4 | nieustalona offline (METADATA bez pola licencji) | api/requirements.lock |
| idna | 3.20 | BSD-3-Clause | api/requirements.lock |
| opentelemetry-api | 1.45.2 | Apache-2.0 | api/requirements.lock |
| pydantic | 2.14.4 | MIT | api/requirements.lock |
| pydantic_core | 2.50.5 | MIT | api/requirements.lock |
| starlette | 1.10.0 | BSD-3-Clause | api/requirements.lock |
| typing-inspection | 0.4.5 | MIT | api/requirements.lock |
| typing_extensions | 4.16.0 | PSF-2.0 | api/requirements.lock |
| uvicorn | 0.54.0 | BSD-3-Clause | api/requirements.lock |
| websockets | 17.4 | BSD-3-Clause | api/requirements.lock |
| numpy | 2.2.6 | nieustalona offline | analysis/semantic-requirements.txt |
| onnxruntime | 1.22.1 | nieustalona offline | analysis/semantic-requirements.txt |
| tokenizers | 0.21.4 | nieustalona offline | analysis/semantic-requirements.txt |
| yt-dlp | 2026.10.26 | Unlicense (domena publiczna) | ops/demo/live-requirements.txt |
| youtube-transcript-api | 1.2.5 | MIT | ops/demo/live-requirements.txt |
| vosk | 0.3.45 | Apache-2.0 wg analysis/README.md (brak w venv) | analysis/asr-lock.json |

Uwaga: METADATA pakietu `huey` nie ma pola licencji; do potwierdzenia przed redystrybucją.

## JavaScript (`web/package-lock.json`, 183 pakiety)

Produkcyjne (licencja z lock/`node_modules/*/package.json`):

| Nazwa | Wersja | Licencja |
|---|---|---|
| @astryxdesign/core | 0.7.17 | MIT |
| @astryxdesign/theme-neutral | 0.7.17 | MIT |
| @formatjs/fast-memoize | 3.1.7 | MIT |
| @formatjs/icu-messageformat-parser | 3.5.18 | MIT |
| @formatjs/icu-skeleton-parser | 2.1.11 | MIT |
| @kurkle/color | 0.3.4 | MIT |
| @stylexjs/stylex | 0.19.2 | MIT |
| chart.js | 4.6.1 | MIT |
| intl-messageformat | 11.2.15 | BSD-3-Clause |
| lucide-react | 1.77.0 | ISC |
| react | 19.3.1 | MIT |
| react-dom | 19.3.1 | MIT |
| scheduler | 0.28.0 | MIT |
| styleq | 0.2.1 | MIT |

Narzędziowe (`dev`, 170 pakietów, m.in. `@astryxdesign/cli` 0.7.17, `esbuild` 0.28.2, oba MIT):

| Licencja | Liczba |
|---|---|
| MIT | 136 |
| BSD-2-Clause | 13 |
| ISC | 11 |
| Apache-2.0 | 2 |
| BSD-3-Clause | 2 |
| MIT-0, 0BSD, CC0-1.0 (`mdn-data`) | po 1 |
| BlueOak-1.0.0 (`graceful-fs`) | 1 |
| CC-BY-4.0 (`caniuse-lite`, dane, wymaga atrybucji) | 1 |

## Pliki wbudowane (`web/vendor/`)

| Plik | Licencja |
|---|---|
| react.production.min.js | MIT (nagłówek `@license React`, plik REACT-LICENSE) |
| react-dom.production.min.js | MIT (nagłówek, plik REACT-DOM-LICENSE; zawiera fragment Modernizr 3.0.0pre, MIT) |

Wbudowany React (`web/vendor/*.production.min.js`, UMD z linii 18; wersja 18.3.1 wg docs/archiwum/DEMO-ODBIOR.md) obsługuje tylko stary pulpit `web/legacy.html`. Bieżący pulpit buduje React 19.3.1 z `web/package.json`. Obie wersje: MIT.

## Modele i zasoby natywne

| Zasób | Wersja / suma | Licencja (źródło w repo) | Źródło |
|---|---|---|---|
| multilingual-e5-small, konwersja ONNX (`model_quantized.onnx`, `tokenizer.json`) | rewizja 761b726d..., sha256 w analysis/semantic-lock.json | MIT dla modelu bazowego (`analysis/semantic-lock.json`); karta konwersji nie podaje osobnej licencji, prawa do artefaktu nierozstrzygnięte (docs/archiwum/DEMO-ODBIOR.md, docs/ODBIOR-UKNF.md) | huggingface.co/Xenova/multilingual-e5-small, baza: intfloat/multilingual-e5-small |
| Vosk (biblioteka) | 0.3.45, sha256 w analysis/asr-lock.json (aarch64, x86_64) | Apache-2.0 (analysis/README.md) | files.pythonhosted.org (URL w lock) |
| vosk-model-small-pl | 0.22, sha256 c4cd1649... | Apache-2.0 (analysis/README.md) | alphacephei.com/vosk/models/vosk-model-small-pl-0.22.zip |
| FFmpeg (system, w `.runtime/demo/ffmpeg`, montowany w compose) | wg dystrybucji | GPL-2.0-or-later (docs/archiwum/DEMO-ODBIOR.md), uruchamiany jako osobny proces, nie dołączany do repo | ffmpeg.org/legal.html |
| qwen3.5:4b-q4_K_M (Ollama, domyślny `INVESTWATCH_LLM_MODEL`) | brak digestu w repo | Apache-2.0 (analysis/README.md) | ollama.com/library/qwen3.5 |
| qwen3.5:9b / qwen/qwen3.5-9b (pomiar) | brak digestu | Apache-2.0 (docs/fable/OPENROUTER-M3.md) | huggingface.co/Qwen/Qwen3.5-9B |
| ministral-3:8b-instruct-2512-q4_K_M, ministral-3:3b-instruct-2512-q4_K_M (historyczne pomiary i eksperymenty) | brak digestu | nie podana w repo, do potwierdzenia | ollama.com |
| gemma4:e2b (tylko test jednostkowy), Gemma 3 12B (pomiar) | brak digestu | Gemma 3: "nie permisywna" (analysis/README.md); Gemma 4 nie podana, do potwierdzenia | ollama.com |

## Obrazy kontenerów (`compose.yaml`)

| Obraz | Licencja | Uwaga |
|---|---|---|
| python:3.12-bookworm | do potwierdzenia (PSF-2.0 dla Pythona, Debian: mieszane, w tym GPL/LGPL) | docs/ARCHITEKTURA.md nie podaje |
| nginx:1.27-alpine | do potwierdzenia (nginx: BSD-2-Clause, Alpine: mieszane) | docs/ARCHITEKTURA.md nie podaje |
| ollama/ollama:0.40.17 | MIT (docs/ARCHITEKTURA.md) | wagi poza obrazem |

## Usługi i dane zewnętrzne (pomiar i zbieranie)

| Usługa | Użycie | Zależność produktu | Warunki |
|---|---|---|---|
| OpenRouter | porównania deweloperskie (`ops/review/`, `tools/measure_*.py`) | brak, inferencja działa przez lokalną Ollamę | do potwierdzenia przez właściciela |
| YouTube Data API v3 | odkrywanie i monitoring kanałów, kwota 10 000 j./dobę | tak, w trybie live (offline działa na zapisach) | do potwierdzenia przez właściciela |
| ScrapeCreators | jednorazowa próbka Instagram/Facebook/reklamy z darmowego pakietu (docs/MONITORING.md) | nie, skan czyta tylko zapisane odpowiedzi | do potwierdzenia przez właściciela; docs/MONITORING.md: Meta uznaje automatyczny odczyt za sprzeczny z warunkami, ryzyko po stronie dostawcy |
| Meta Ad Library | adapter `meta_ads` gotowy, bez tokenu; import ręczny | nie | do potwierdzenia przez właściciela |

## Do decyzji i do potwierdzenia

- Licencja projektu (brak pliku LICENSE).
- Nieustalone offline: huey, numpy, onnxruntime, tokenizers (zainstalować w venv albo sprawdzić na PyPI).
- Nie permisywne lub wymagające uwagi: FFmpeg GPL-2.0-or-later (osobny proces, nie w repo), Gemma 3 12B (warunki własne Google, tylko pomiar), konwersja ONNX E5 bez własnej licencji, caniuse-lite CC-BY-4.0 (dane narzędziowe, nie w produkcie), obrazy bazowe z komponentami GPL/LGPL (Debian).
- Licencje Ministral 3 i Gemma 4 niepodane w repo.
- Warunki YouTube, OpenRouter, ScrapeCreators i Meta: potwierdzenie właściciela.
