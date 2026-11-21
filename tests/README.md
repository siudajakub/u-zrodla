# tests/

Testy jednostkowe modułów leżą obok kodu (`collectors/test_*.py`, `analysis/test_*.py`, `tools/test_*.py`). Ten katalog zawiera testy kontraktu API, przeglądarkowe i próbę bez Internetu.

## Suity uruchamiane bez przeglądarki i Dockera

Wyniki z 21 XI 2026, HEAD `hack/integration`:

| Suita | Komenda | Wynik |
|---|---|---|
| `collectors/` | `.runtime/venv/bin/python -B -m unittest discover -s collectors -t . -p 'test_*.py'` | 200 OK |
| `analysis/` | `.runtime/venv/bin/python -B -m unittest discover -s analysis -t . -p 'test_*.py'` | 211 OK, 3 pominięte |
| `tests/core/` (kontrakt API v2, magazyn, trasy) | `INVESTWATCH_STATE=$(mktemp -d) .runtime/venv/bin/python -B -m unittest discover -s tests/core -p 'test_*.py'` | 386 OK |
| `tools/` | `python3 -B -m unittest discover -s tools -p 'test_*.py'` | 46 OK |

`tests/core` wymaga venv z `.runtime/venv` (przygotowuje `ops/demo/bootstrap.sh`) i pustego katalogu stanu w `INVESTWATCH_STATE`. `golden_shadow_v1.json` to zapisany wzorzec wyniku v1 dla `test_contract_v2_qualification.py`, `v2_helpers.py` to wspólne pomocniki.

## tests/ui (pulpit Astryx)

Nie uruchamiano w tym przeglądzie.

| Plik | Co sprawdza | Wymaga |
|---|---|---|
| `render-smoke.cjs` | Drzewo React z `web/app.js` (pusta kolejka, tekst z `<script>` jako tekst, media) i render SSR pulpitu z `desk-ssr-entry.jsx` na `web/sample/export.json`; 60 linii z `assert` w kodzie | `node tests/ui/render-smoke.cjs`, Node, `web/node_modules` (esbuild); bez Chromium |
| `desk-flow.py` | Ścieżki pulpitu w Chromium na API schematu 2: kolejki, karta, decyzja, próg, rejestr reklam, import Meta; ok. 168 wywołań `check()` w kodzie | Playwright + Chromium, własne API na kopii bazy (`--base`), opcjonalnie `node web/dev-server.mjs` (`--dev`) |
| `capture-screens.py` | Zrzuty 1440 i 390 px do `screens/<data>/`, błędy konsoli | Playwright + Chromium, działające API (`--base`) |

`screens/` przechowuje zrzuty z rund 21 XI (`2026-11-21`, `-r2`, `-r3`, `-r4`).

## tests/e2e (starszy pulpit)

Nie uruchamiano w tym przeglądzie. Wszystkie trzy wymagają Playwright i Chromium.

| Plik | Co sprawdza | Stan |
|---|---|---|
| `analyst_flow.py` | Decyzja i upload klipu na `/`; 19 asercji | Selektory starego `web/app.js` (`.timecode`, „Decyzja i historia”). `/` ładuje teraz pulpit Astryx, stary jest pod `/legacy.html`. Brak odwołań w repo |
| `neutral_desk.py` | Ta sama ścieżka 1440 i 390 px na `/` i `/theme-preview/`; 16 asercji | Etykiety „Sygnał do sprawdzenia”, „Wszystkie sprawy” nie występują w `web/src`. Opis w [tests/offline/README.md](offline/README.md) |
| `m2_control.py` | Widoczność ostrzeżenia, kontrast i reflow na fikcyjnej reklamie przez `collectors.m2_browser.measure`; 13 asercji | Bez API; wskazany w [docs/ODBIOR-UKNF.md](../docs/ODBIOR-UKNF.md) |

## tests/offline (trzy zimne starty bez Internetu)

Nie uruchamiano w tym przeglądzie. `python3 tests/offline/verify.py --root "$PWD"` tworzy trzy projekty Compose w sieci wewnętrznej, sprawdza kolejkę z 4 filmami i odtworzenie po SIGKILL workera. Wymaga Dockera, zbudowanego obrazu i paczki mediów replay. `--fingerprint-only` liczy tylko odcisk kodu. `compose.llm-stub.yaml` + `llm_stub.py` podstawiają atrapę Ollamy. Wyniki: `proof-2026-11-21.json`, `proof-zip-2026-11-21.json`. Opis: [tests/offline/README.md](offline/README.md).
