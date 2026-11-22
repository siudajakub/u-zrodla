# API i worker

FastAPI udostępnia sprawy, kolejki, decyzje i raporty. Worker wykonuje skany i zapisuje wyniki w SQLite. WebSocket informuje pulpit o zmianach. `INVESTWATCH_STATE` wskazuje katalog stanu. [Architektura](../docs/ARCHITEKTURA.md) · [Kontrakty](../docs/hackathon/contracts.md)

| Plik | Odpowiedzialność | Główne wejścia | Testy (tests/core/...) |
|---|---|---|---|
| `server.py` | trasy HTTP/WS, same-origin, TrustedHost, serwowanie `web/` | `app` | `test_contract_v2_scan`, `_decisions`, `_schema`, `_serve_web`, `test_site_routes` |
| `store.py` | schemat i migracje SQLite, sprawy, kolejki, raport, próg, zdarzenia | `init`, `connection`, `migrate`, `queue_list` | `test_store`, `test_contract_v2_schema`, `_desk_api`, `_desk3` |
| `queue_view.py` | trwałe wiersze i liczniki kolejki odświeżane przy zapisie | `refresh`, `summaries`, `counts` | `test_queue_projection` |
| `jobs.py` | kolejka Huey, dziennik skanów z dzierżawą, tryby skanu, pętla workera | `submit`, `run_inline`, `recover`, `work` | `test_contract_v2_scan`, `test_job_review`, `_qualification` |
| `worker.py` | punkt wejścia procesu workera | `python -m api.worker` | przez `jobs` |
| `enrich.py` | krok mediów: transkrypcja, kadry, bramka mowy | `enrich_media` | `test_contract_v2_speech_gate`, `_media_queue` |
| `replay_pack.py` | paczka mediów replay 21 XI poza Gitem, manifest SHA-256 | `python -m api.replay_pack build/verify` | `test_contract_v2_desk_api` |
| `import_meta.py` | import zapisanych stron Meta/Instagram, kwalifikacja tekstowa | `accept`, `qualify_import` | `test_contract_v2_meta_import` |
| `listen.py` | próbka początku odcinków podcastów w skanie live | `sample_audio` | `test_contract_v2_adapters` |
| `card_view.py` | karta widoku 2 (`?schema=2`) | `card_view` | `test_contract_v2_card_view` |
| `proof_path.py` | `proofPath[]`: kroki weryfikacji sprawy ze stanem | `proof_path` | `test_contract_v2_pitch_fields` |
| `calibration_q2.py` | kalibracja M1 na zbiorze q-v2 | `compare` | `test_contract_v2_social` |
| `calibration_modules.py` | kalibracja M2 i M3 na `fixtures/labeled` | `compare`, `series` | `test_contract_v2_module_calibration` |
| `second_opinion_recorded.py` | zapisany wynik drugiego głosu z 21 XI, bez wywołań modelu | `recorded`, `models_block` | `test_contract_v2_second_opinion_recorded` |
| `shadow_report.py` | CLI: reguły aktywne vs kwalifikacja w cieniu | `python -m api.shadow_report --state DIR` | `test_contract_v2_shadow` |
| `requirements.lock` | zależności venv lokalnego (fastapi, huey, uvicorn) | `pip install -r` | — |

## Trasy

- Przegląd: `GET /v1/health`, `/v1/state` (`?findings=0`), `/v1/overview`, `/v1/trend`.
- `GET /v1/queues/{name}` podaje kolejkę z kursorem, filtrami i licznikami. `GET /v1/cases/{key}`, `.../versions`, `.../versions/{v}` i `.../reach` zwracają kartę, wersje i dane o zasięgu. `PATCH /v1/cases/{key}` zapisuje [decyzję i następny etap](../docs/hackathon/contracts.md#obieg-decyzji-operatora). `POST .../inquiry` zapisuje korespondencję, `POST .../contract` porównanie z umową. Widok 2 wybiera się przez `?schema=2` lub nagłówek `X-InvestWatch-Schema: 2`. Widok 1 jest domyślny (`web/legacy.html`).
- Kalibracja i próg: `GET /v1/calibration` (`module`, `dataset`, `series`); `GET|PUT /v1/threshold`, `.../history`, `POST .../restore`; to samo dla `/v1/qualification`.
- Raport modułu pobiera `GET /v1/report?module=M1|M2|M3&format=json|csv`. Raport decyzji ze wszystkich modułów przyjmuje `module=all` i `queue=control|supplement|closed`. [Pola raportu decyzji](../docs/hackathon/contracts.md#raport-decyzji)
- Skany — `POST /v1/scans` (`mode` przyjmuje `live|replay|recompute|enrich`), `GET /v1/scans/{id}`. Zapis wykrytej przesłanki publikuje zdarzenie `high_risk`.
- Dowody i pliki: `POST /v1/evidence`, `POST /v1/media` (202), `POST /v1/import/meta` (202); `GET /v1/frames/{video}/{name}`, `/uploads/{name}`, `/evidence/m2/{name}`, `/evidence/m2/market/{name}`, statyczne `/evidence/browser`, `/media`.
- Zdarzenia: `WS /v1/events?after=ID` (`ready`, `reset`, potem zdarzenia z tabeli `events`).
- `/`: `web/` przez StaticFiles; `INVESTWATCH_SERVE_WEB=0` wyłącza (Compose, front serwuje nginx).

## SQLite

`STATE/cases.sqlite3` przechowuje skany, sprawy, wersje, decyzje i zdarzenia. Migracja 9 dodaje wiersze kolejki. Podgląd i worker przeliczają indeks przy zmianie jego formatu i odtwarzają etapy z zapisanej historii. Zapis skanu, decyzji lub progu odświeża wiersze w tej samej transakcji. Stare przykłady syntetyczne są dostępne po ID i w kolejce archiwalnej `demo`. Wersję bazy zwraca `/v1/health`. Zadania Huey korzystają z `STATE/queue.sqlite3`.

## Tryby skanu

- `replay` odtwarza zapisane odczyty źródeł i paczkę mediów (`INVESTWATCH_REPLAY_MEDIA`) bez sieci. Pierwszy start z pustą bazą uruchamia skany archiwum. Kolejkę z gotowego archiwum można otworzyć od razu po odtworzeniu.
- `live`: kolektory sieciowe; cyklicznie, gdy `INVESTWATCH_DISCOVERY_INTERVAL` > 0 (w Compose serwis `scheduler`, profil `live`). Skrypty startowe: `INVESTWATCH_MODE=demo|live`.
- `recompute`, `enrich`: ponowna analiza i zaległe media bez zbierania. `upload`: `POST /v1/media`. Import Meta zleca `live` z adapterem `meta_import`.

## Uruchomienie

- Bez Dockera: `sh ops/demo/start-local.sh [--live|--reset|--stop]` (venv `.runtime/venv-local`, `uvicorn api.server:app` na 127.0.0.1:8769 i `python -m api.worker`, stan `.runtime/local/state`). Opis: [ops/demo/README.md](../ops/demo/README.md).
- Compose: `sh ops/demo/start.sh` ([compose.yaml](../compose.yaml): `web` nginx, `api`, `worker`, opcjonalnie `scheduler`, `inference`).
- Testy: `python3 -B -m unittest discover -s tests/core -p 'test_*.py'`.
