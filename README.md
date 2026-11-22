# InvestWatch

Prototyp dla UKNF wyszukuje publikacje i oferty inwestycyjne, wskazuje fragmenty wymagające sprawdzenia i przechowuje dowód z decyzją analityka. M1 dotyczy reklam osób trzecich, M2 reklamy własnej firmy, M3 potencjalnego nieuprawnionego doradztwa.

## Quick Start

```sh
sh ops/demo/start.sh
```

Po przygotowaniu środowiska komenda uruchamia Compose, odtwarza datowany stan pokazu i czeka na kolejkę **Do sprawdzenia**. Pulpit jest pod [127.0.0.1:8769](http://127.0.0.1:8769/). Pierwsze przygotowanie wymaga sieci. Z wcześniejszego pomiaru na Linux x86_64 start trwał około 12 min od zera lub 33 s z pasującym archiwum. Odbiór lokalny na Macu jest osobną próbą. [Architektura i pomiar](docs/ARCHITEKTURA.md) · [Procedura na Macu](ops/mac/README.md)

Datowany stan pokazu zawiera 1 922 materiały, 274 wpisy w rejestrze reklam i 17 spraw do sprawdzenia. [Scenariusz i liczby](docs/hackathon/demo.md)

- **Wymagania:** Linux x86_64 lub macOS Apple Silicon (M1 i nowsze, 16 GiB RAM zalecane, 8 GiB minimum), Docker Compose (Docker Desktop z pamięcią VM co najmniej 4 GiB), Node 22.13+ dla pulpitu, ok. 10 GiB wolnego miejsca. Bez płatnego API.
- **Dane pokazu.** Skopiuj `replay-media-2026-11-21.tar.gz` i jego `.sha256` do katalogu projektu przed startem. Z przygotowanego stanowiska eksportuje je `sh ops/demo/pack-media.sh`. Dla szybkiego startu skopiuj także `investwatch-state-2026-11-21.tar.gz` i jego `.sha256`, tworzone przez `sh ops/demo/pack-state.sh`. Start użyje archiwum przy pustym stanie i zgodnym odcisku kodu. Opcja `--reset` czyści lokalny stan. `--cold` wymusza pełną analizę. [Instrukcja operatora](ops/demo/README.md)
- **Tryb pokazu (domyślny):** replay, bez sieci po przygotowaniu, harmonogram live wyłączony. **Tryb live:** `sh ops/demo/start.sh --live` (skan co 4 h; klucz YouTube w `.env` jako `YOUTUBE_API_KEY`, wzór w [.env.example](.env.example)). Pobieranie mediów z YouTube (yt-dlp) działa tylko lokalnie, patrz niżej.
- **Serwisy** ([architektura](docs/ARCHITEKTURA.md)): `web` (nginx, pulpit i reverse proxy, jedyny port 127.0.0.1:8769), `api` (FastAPI, REST + WebSocket), `worker` (kolektory i analiza, kolejka), `scheduler` (skan cykliczny, tylko `--live`), `inference` (Ollama, profil `llm`, opcjonalny). `api`, `worker` i `inference` pracują w sieci wewnętrznej. Dane: `.runtime/demo/state` (SQLite) i `.runtime/demo/objects` (pliki adresowane SHA-256).
- **Bez Dockera (wariant awaryjny):** `sh ops/demo/start-local.sh` uruchamia ten sam stan i tę samą paczkę jako procesy hosta (Python 3.12, `--stop` zatrzymuje). Procedura odbioru na Macu: [ops/mac/README.md](ops/mac/README.md).

[Zakres UKNF i pięć plików źródłowych](docs/zrodla-uknf/README.md) · [Audyt odbioru](docs/lanes/2026-11-22-odbior-finalny.md) · [Scenariusz pokazu](docs/hackathon/demo.md) · [Prezentacja PDF](presentation/InvestWatch.pdf)

Test porównawczy oceny pojedynczej reklamy przez OpenRouter i lokalnie na Apple Silicon opisuje [instrukcja OpenRouter / Mac M3](docs/fable/OPENROUTER-M3.md).

Mapa repozytorium: [docs/README.md](docs/README.md)
