# InvestWatch

Prototyp dla UKNF wyszukuje publikacje i oferty inwestycyjne, wskazuje fragmenty wymagające sprawdzenia i przechowuje dowód z decyzją analityka. M1 dotyczy reklam osób trzecich, M2 reklamy własnej firmy, M3 potencjalnego nieuprawnionego doradztwa.

## Quick Start

```sh
sh ops/demo/start.sh
```

Jedna komenda przygotowuje stanowisko (pierwszy raz z siecią), uruchamia serwisy Compose, odtwarza datowany skan z 21 XI 2026 i czeka na kolejkę **Co wymaga sprawdzenia** z czterema filmami (7M0rC6-Rueo, AqXHkxDzSDI, OIyPE0z2mng, ZJrT-X08Xwc). Potem pulpit jest pod [127.0.0.1:8769/theme-preview/](http://127.0.0.1:8769/theme-preview/). Pierwsze odtworzenie liczy ok. 1,9 tys. materiałów z sześciu skanów bootstrapu (na obciążonym devboxie 12 min). Szybki start: archiwum gotowego stanu z `sh ops/demo/pack-state.sh` (`.runtime/dist/investwatch-state-2026-11-21.tar.gz` i `.sha256`) położone w katalogu projektu jest rozpakowywane przy pustym stanie, jeśli odcisk kodu się zgadza (start w ok. 30 s; inaczej ostrzeżenie i pełna analiza). Czysty stan: `--reset`, pełna analiza mimo archiwum: `--cold`.

- **Wymagania:** Linux x86_64 lub macOS Apple Silicon (M1 i nowsze, 16 GiB RAM zalecane, 8 GiB minimum), Docker Compose (Docker Desktop z pamięcią VM co najmniej 4 GiB), Node 22.13+ dla pulpitu, ok. 10 GiB wolnego miejsca. Bez płatnego API.
- **Paczka mediów replay** (transkrypcje i kadry 17 filmów, poza Gitem): bez niej kolejka jest pusta, a `start.sh` odmawia startu z instrukcją. Na komputerze z paczką: `sh ops/demo/pack-media.sh` tworzy `.runtime/dist/replay-media-2026-11-21.tar.gz` i `.sha256`. Skopiuj oba pliki do katalogu projektu na docelowym komputerze. `start.sh` sam je zweryfikuje (`python -m api.replay_pack verify`) i rozpakuje.
- **Tryb pokazu (domyślny):** replay, bez sieci po przygotowaniu, harmonogram live wyłączony. **Tryb live:** `sh ops/demo/start.sh --live` (skan co 4 h; klucz YouTube w `.env` jako `YOUTUBE_API_KEY`, wzór w [.env.example](.env.example)). Pobieranie mediów z YouTube (yt-dlp) działa tylko lokalnie, patrz niżej.
- **Serwisy** ([architektura](docs/ARCHITEKTURA.md)): `web` (nginx, pulpit i reverse proxy, jedyny port 127.0.0.1:8769), `api` (FastAPI, REST + WebSocket), `worker` (kolektory i analiza, kolejka), `scheduler` (skan cykliczny, tylko `--live`), `inference` (Ollama, profil `llm`, opcjonalny). `api`, `worker` i `inference` pracują w sieci wewnętrznej. Dane: `.runtime/demo/state` (SQLite) i `.runtime/demo/objects` (pliki adresowane SHA-256).
- **Bez Dockera (wariant awaryjny):** `sh ops/demo/start-local.sh` uruchamia ten sam stan i tę samą paczkę jako procesy hosta (Python 3.12, `--stop` zatrzymuje). Procedura odbioru na Macu: [ops/mac/README.md](ops/mac/README.md).

[Zakres UKNF i pięć plików źródłowych](docs/zrodla-uknf/README.md) · [Co działa i z jakimi ograniczeniami](docs/ODBIOR-UKNF.md) · [Scenariusz pokazu](docs/hackathon/demo.md) · [Prezentacja PDF](presentation/InvestWatch.pdf)

Test porównawczy oceny pojedynczej reklamy przez OpenRouter i lokalnie na Apple Silicon opisuje [instrukcja OpenRouter / Mac M3](docs/fable/OPENROUTER-M3.md).

Mapa repozytorium: [docs/README.md](docs/README.md)
