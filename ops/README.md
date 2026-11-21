# ops/

Uruchomienie i utrzymanie stanowiska. Szczegóły: [ops/demo/README.md](demo/README.md) (Linux, Compose, pulpit) i [ops/mac/README.md](mac/README.md) (macOS Apple Silicon). Usługi Compose: [compose.yaml](../compose.yaml), opis architektury: [docs/ARCHITEKTURA.md](../docs/ARCHITEKTURA.md).

## Start

| Komenda | Co robi |
|---|---|
| `sh ops/demo/start.sh` | Compose, tryb pokazu: replay 21 XI, bez sieci, czeka na kolejkę z 4 filmami. `--live` skan co 4 h, `--reset` czysty stan, `--cold` pełna analiza mimo archiwum |
| `sh ops/demo/start-local.sh` | Wariant bez Dockera: API (uvicorn) i worker jako procesy hosta, stan w `.runtime/local/` |
| `sh ops/demo/bootstrap.sh` | Jednorazowe przygotowanie maszyny (z siecią), potem start jak `start.sh` |
| `sh ops/demo/pack-state.sh [--local]` | Archiwum gotowego stanu (SQLite + obiekty + odcisk kodu) w `.runtime/dist/`; start rozpakowuje je przy pustym stanie |
| `sh ops/demo/pack-media.sh` | Archiwum paczki mediów replay (`.runtime/replay-media/2026-11-21`) + SHA-256, poza Gitem |

## Katalogi

| Katalog | Zawartość | Wejście |
|---|---|---|
| `compose/` | `egress.yaml`: nakładka z wyjściem do sieci tylko dla workera (tryb `--live`, Ollama na hoście) | dokłada `start.sh` |
| `demo/` | Start, przygotowanie (`prepare.sh`, `prepare-preview.sh` buduje pulpit Astryx), czekanie na gotowość (`wait-ready.sh`, `queue_status.py`), paczki (`state_pack.py`), wspólne funkcje (`common.sh`), zależności wariantu lokalnego (`live-requirements.txt`) | `sh ops/demo/start.sh` |
| `inference/` | Jednorazowe pobranie wag Ollamy dla profilu Compose `llm`; `pull.yaml` daje sieć tylko na czas pobrania | `sh ops/inference/pull-model.sh [MODEL]` |
| `mac/` | Przygotowanie w kontenerze linux/arm64 (`prepare-darwin.sh`, `container-prepare.sh`), kontrola architektury bibliotek (`arch-guard.sh`), odbiór stanowiska (`check.sh`), pomiar lokalnego LLM (`measure-llm.sh`) | `sh ops/mac/check.sh` |
| `review/` | `openrouter.sh`: jedno porównanie deweloperskie przez OpenRouter (`analysis.openrouter_review`), klucz z `.env.openrouter`; płatne | `sh ops/review/openrouter.sh ...` |
| `scheduler/` | `scheduler.py`: zleca skan live co `INVESTWATCH_SCHEDULE_INTERVAL` s; skan wykonuje worker | usługa Compose `scheduler`, profil `live` |
| `user-systemd/` | Timer użytkownika co 4 h (00,04,…,20:10 Warszawa) uruchamia `tools/watch_sources.py` i raport dzienny w `.runtime/watch/` | `investwatch-watch.timer` (systemd użytkownika); stan i wstrzymanie: [docs/MONITORING.md](../docs/MONITORING.md) |
| `web/` | `nginx.conf`: statyczny pulpit `web/` + proxy do API (`/v1`, `/uploads`, `/evidence`, `/media`) | usługa Compose `web` |
