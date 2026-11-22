# Architektura U Źródła

U Źródła działa na pojedynczym stanowisku. Kolektory pozyskują materiały, worker analizuje je lokalnie, a pulpit pokazuje dowody i zapisuje decyzje analityka. SQLite przechowuje metadane i historię. Magazyn plików zachowuje zrzuty, kadry i media. [Uruchomienie](../ops/demo/README.md) · [Compose](../compose.yaml)

## Przepływ danych

```mermaid
flowchart LR
  S[Źródła: YouTube API/Atom, strony firm, profile social, import Meta, replay 21 XI] --> C
  subgraph worker
    C[Kolektory: adaptery discover ctx, collectors/adapter.py + rejestr collectors/discovery.py] --> Q[(Kolejka Huey + dziennik skanów z dzierżawą)]
    Q --> A1[Preprocessing: HTML do tekstu, normalizacja, deduplikacja]
    A1 --> A2[Embedding E5 multilingual-e5-small, ONNX CPU]
    A2 --> A3[Reguły M1 / M2 / M3 z dosłownym cytatem]
    A3 --> A4[Klasyfikator typu materiału: E5 + regresja logistyczna]
    A4 -.gdy dostępna jest Ollama.-> A5[Drugi głos LLM z lokalnej Ollamy]
  end
  SCH[scheduler: CronJob] --> Q
  A5 --> G[Agregator: wspólny Finding/Case z wersjami, api/store.py apply_scan]
  A4 --> G
  G --> DB[(state: SQLite metadane + treść)]
  C --> OBJ[(objects: zrzuty, kadry, media, sha256)]
  DB --> API[api: REST + WebSocket /v1/events]
  OBJ --> API
  API --> WEB[web: nginx, pulpit + reverse proxy] --> U[Analityk: przeglądarka]
```

## Serwisy

| Serwis | Rola | Obraz | Port | Wolumeny | Skalowanie |
|---|---|---|---|---|---|
| `web` | Statyczny pulpit (`web/`) i reverse proxy dla `/v1` (REST, WebSocket), `/uploads`, `/evidence`, `/media` | `nginx:1.27-alpine` (BSD-2) | **jedyny** port na hoście: `127.0.0.1:8769` | `web/` (ro), `ops/web/nginx.conf` (ro) | Bezstanowy, można go powielić za balanserem |
| `api` | FastAPI: sprawy, decyzje, kalibracja progu, raporty, strumień zdarzeń | `python:3.12-bookworm` + zależności z `.runtime` (ro) | brak, tylko sieć `backend` | `state`, `objects`, kod (ro) | Wiele replik do odczytu. Zapisy przechodzą przez jednego pisarza SQLite |
| `worker` | Kolektory i analiza, pobiera zadania z kolejki | jak `api` | brak | `state`, `objects`, `replay-media` (ro), modele (ro) | `--scale worker=N`: zadanie trzyma dzierżawa (`api/jobs.py: claim`, `LEASE`), a po awarii przejmuje je inny worker |
| `scheduler` | Co `INVESTWATCH_DISCOVERY_INTERVAL` s zleca skan live (rola CronJob). Idempotentny identyfikator okna | jak `api`, 256 MB | brak | `state` | Jedna instancja wystarcza. Druga nie dubluje skanu (unikalny `request_id`) |
| `inference` | Ollama, lokalny drugi głos LLM (profil `llm` przy przygotowanych wagach) | `ollama/ollama` (MIT), bez wag w obrazie | brak, tylko `backend` | `.runtime/ollama` (wagi poza Gitem) | Limit `mem_limit` 6 GB, jedno żądanie naraz. Na Macu Ollama działa natywnie (Metal) |

nginx serwuje pulpit i przekazuje ruch do API. Zachowuje nagłówek `Host`, który API sprawdza razem z `Origin`.

**Dane.** `state` (`/data`) zawiera `cases.sqlite3`, czyli metadane, treść materiałów, wersje, decyzje, dziennik skanów i zdarzenia, oraz przejściowy `queue.sqlite3`. `objects` montujemy w podkatalogach `/data/<uploads|m2|media-cache|meta-import|youtube-raw|youtube-cache>`, więc kod nie wymagał zmian. Przesłane nagrania (`uploads/<sha256>.<ext>`) i zasoby archiwum M2 (`<sha256>.png|json`) mają nazwę równą skrótowi SHA-256 treści, więc ta sama treść nie powstaje dwa razy. API serwuje wyłącznie nazwy w tym formacie, a skrót zasobu M2 sprawdza przy odczycie. `replay-media` to paczka 17 filmów z 21 XI, montowana tylko do odczytu i weryfikowana manifestem SHA-256 z repozytorium (`api/replay_pack.py`).

**Skala.** SQLite dopuszcza jednego pisarza naraz, a konkurujące workery korzystają z dzierżaw zadań. Przy większym obciążeniu można przenieść stan do PostgreSQL, kolejkę do Redis i zasoby do magazynu zgodnego z S3. Adresy zasobów nadal mogą opierać się na SHA-256.

**Start (devbox Linux x86_64, obciążony, 21 XI).** Czysty start `sh ops/demo/start.sh --reset --cold` do `GOTOWE` przez `web` zajmuje 701–721 s: 6 skanów bootstrapu, 1932 sprawy, jeden worker. Start z archiwum stanu (`ops/demo/pack-state.sh`, 9 MB) trwa 33 s, w tym `GOTOWE` po 23 s od `up`. Przy niezgodnym odcisku kodu skrypt ostrzega i robi normalny bootstrap. Odcisk to SHA-256 śledzonych plików `api/ analysis/ collectors/ fixtures/ data/probe-snapshots/` bez testów i `.md`.

## Punkty rozszerzeń

| Co dodać | Jak |
|---|---|
| Nowe źródło | Jeden adapter z funkcją `discover(ctx)` zwracającą materiały i stan źródła (`collectors/adapter.py: Adapter, AdapterContext`). Do tego jedna linia `register(Adapter("id", fn, "Etykieta", modes=...))` w `collectors/discovery.py`. Kwoty, dzierżawa, ponowienia i stan źródła są wspólne |
| Moduł analityczny | Funkcja oceniająca materiał w `analysis/` wywołana z `analysis/engine.py: analyze()`. Wynik trafia do wspólnego Finding, a wersję modułu zapisuje pole `analysisVersion` |
| Nowy model | E5: `analysis/semantic-lock.json` i `analysis.setup_semantic`. Klasyfikator: `python -m analysis.material_classifier train`. LLM: `INVESTWATCH_LLM_MODEL` plus `sh ops/inference/pull-model.sh MODEL` albo `ollama pull` na hoście |
| Nowy serwis | Usługa w `compose.yaml` w sieci `backend`. Wychodzi na zewnątrz tylko przez `web` |

## Bezpieczeństwo

- Na hoście nasłuchuje tylko `web` (127.0.0.1). `api`, `worker`, `scheduler` i `inference` są w sieci `internal: true`, bez drogi do Internetu. Wyjście dostaje wyłącznie `worker`, i to tylko w trybie `--live` albo przy Ollamie na hoście (nakładka `ops/compose/egress.yaml`).
- Każdy kontener: system plików tylko do odczytu, `tmpfs` na `/tmp`, użytkownik bez roota (UID hosta), `cap_drop: ALL`, `no-new-privileges`, limity CPU i pamięci, `pull_policy: never` oraz healthcheck. Kod i modele są montowane tylko do odczytu, zapis jest możliwy tylko w `state` i `objects`.
- Sekrety (np. `YOUTUBE_API_KEY`) trzymamy wyłącznie w `.env` albo w pliku poza repozytorium (`.env.example` to sam wzór). Worker uruchamia inferencję lokalnie przez Ollamę. Eksperymenty porównawcze z OpenRouter mają osobne polecenia i klucz poza konfiguracją aplikacji.
- Zależności są przypięte (`api/requirements.lock`, `web/package-lock.json`) i instalowane offline z lokalnego wheelhouse. Stan audytu: [ODBIOR-UKNF.md](ODBIOR-UKNF.md), R-§5-07/08.

## Mapowanie na brief

| Wymaganie (BRIEF) | Gdzie |
|---|---|
| §3.1 kolejka zadań open source | Huey na SQLite oraz dziennik skanów z dzierżawą: `api/jobs.py` |
| §3.1 crawler, kolektory API i parsery, rotacja User-Agent i proxy, wyjście JSON | `collectors/*.py`, transport: `collectors/common.py`, przeglądarka M2: `collectors/m2_browser.py` |
| §3.1 baza metadanych SQL, baza treści SQL + Object Storage | `state/cases.sqlite3` (`api/store.py`), `objects/` adresowane SHA-256 |
| §3.1 harmonogram (CronJob/orchestrator) | serwis `scheduler` (`ops/scheduler/scheduler.py`), profil `live` |
| §3.2 preprocessing, tokeny i embeddingi | `analysis/material_classifier.py: clean_text, dedupe`, `analysis/semantic.py` (E5, ONNX) |
| §3.2 silnik inferencji i model open source, scoring | reguły i punkty M1/M2/M3: `analysis/engine.py`, klasyfikator: `analysis/material_classifier.py`, Ollama: `analysis/inference.py` + serwis `inference` |
| §3.2 agregator wyników w ujednolicone obiekty | `api/store.py: apply_scan`, wspólny Finding/Case z wersjami |
| §3.3 pulpit, filtry, trend, status, WebSocket, próg | `web/src/desk/*`, `/v1/trend`, `PATCH /v1/cases/…`, `/v1/events`, `/v1/threshold` (`api/server.py`) |
| §5 modułowe lekkie serwisy | `web`, `api`, `worker`, `scheduler`, `inference` w `compose.yaml` |
| §5 konteneryzacja, start jedną komendą | `sh ops/demo/start.sh`. Gotowy stan: `ops/demo/pack-state.sh` |
| §5 open source, on-premise, bez płatnych API | nginx, Python, FastAPI, Huey, SQLite, ONNX Runtime, Vosk, Ollama |
| §5 łańcuch dostaw, sekrety w .env | lockfile'y, offline wheelhouse, `.env.example`, sieć wewnętrzna |
