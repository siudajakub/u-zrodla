# Odbiór stanowiska na MacBooku M3

Procedura dla J lub agenta uruchomionego na Macu. Przygotowano ją statycznie na devboxie Linux x86_64, bez dostępu do Maca. Skryptu `check.sh` nie wykonano tam w całości (brak `sysctl`, `sw_vers`, `/usr/bin/time -l`, Ollama). Sprawdzono składnię (`sh -n`, `dash -n`) oraz ścieżkę diagnostyczną z atrapą serwera Ollama. Pomiar, sprawdzenie bibliotek `file` i test kontenera dotyczą Maca i nie były uruchamiane. Wynik na Macu rozstrzyga.

## Co działa dziś, a co wymaga poprawki

- **Ocena reklamy przez Ollama (`analysis.ollama_review`) działa na hoście Maca bez Dockera.** Skrypt używa tylko biblioteki standardowej Pythona i łączy się z `127.0.0.1:11434`. Wymaga Pythona 3.12 i modelu `qwen3.5:9b`. Od tej ścieżki zaczyna się odbiór.
- **Quick Start `sh ops/demo/start.sh` ma na Macu gałąź przygotowania w kontenerze linux/arm64** (poprawki B1, B2, B4 wdrożone w `ops/demo/`, obejście B3 po stronie ops). `bootstrap.sh` na Darwin wywołuje `ops/mac/prepare-darwin.sh`, który uruchamia `docker run --platform linux/arm64 python:3.12-bookworm` z `ops/mac/container-prepare.sh` (apt-get ffmpeg, `pip wheel`, `analysis.setup_asr`, E5, `prepare.sh`). Gałąź sprawdzono tylko atrapami na Linuksie, **nie na prawdziwym Macu**.
- Kontenery działają w `linux/arm64` (VM Docker Desktop). Biblioteka Vosk ma więc być ELF aarch64, a nie Mach-O. Dla Vosk 0.3.45 na PyPI nie ma koła macOS, więc natywny `libvosk` na hoście Maca nie istnieje.

## Wymagania wstępne (jednorazowo, z Internetem)

1. macOS na Apple Silicon, terminal natywny arm64 (nie pod Rosetta).
2. Docker Desktop (lub OrbStack), uruchomiony. W Docker Desktop ustaw pamięć VM co najmniej 4 GiB. Model Qwen działa na hoście, nie w VM.
3. Python 3.12 (`brew install python@3.12`; systemowy `python3` z Command Line Tools to zwykle 3.9). Node 22.13+ tylko dla podglądu Astryx. Ollama (aplikacja lub `brew install ollama`).
4. Obraz bazowy: `docker pull --platform linux/arm64 python:3.12-bookworm`.
5. Wagi modelu: `ollama pull qwen3.5:9b`. Przed pobraniem sprawdź pamięć (krok 1). Pobranie zajmuje ok. 6–7 GB.
6. Ustaw krótki kontekst serwera Ollama: `launchctl setenv OLLAMA_CONTEXT_LENGTH 4096` i zrestartuj aplikację Ollama (przy `ollama serve` w terminalu: `OLLAMA_CONTEXT_LENGTH=4096 ollama serve`). Adapter nie ustawia `num_ctx`, więc domyślny kontekst zależy od wersji Ollama i pamięci. Prompt próbki ma ok. 1,9 tys. znaków.

## Krok po kroku

Wszystkie polecenia z katalogu projektu. Raporty trafiają do `.runtime/mac/` (poza Gitem).

**Krok 1. Diagnostyka bez modelu i bez pomiaru**

```sh
sh ops/mac/check.sh
```

Skrypt tylko odczytuje stan i zapisuje raport JSON. Sprawdza m.in. pamięć zunifikowaną (`hw.memsize`), wolne miejsce, architekturę i Rosetta, wersje Docker/Python/Node/FFmpeg, platformę serwera Docker i obrazu bazowego, Ollama (`/api/version`, digest, rozmiar i kwantyzację `qwen3.5:9b` z `/api/tags`), architekturę `libvosk`, `ffmpeg.real` i natywnych rozszerzeń w `.runtime` oraz łączność kontenera z Ollama przez `host.docker.internal`. Werdykt: `ready`, `warnings` lub `blocked` (kod wyjścia 1 przy blokadzie).

Oczekiwane wartości: `serverArchitecture` aarch64, `baseImage` linux/arm64, `libvosk` elf-aarch64 (także po przygotowaniu stanowiska), `containerToOllama` ok. Wartość `macho-*` lub `elf-x86_64` przy bibliotece w `.runtime` oznacza, że kontener jej nie załaduje.

**Krok 2. Digest wag**

Z raportu skopiuj `ollama.model.digest`, `sizeBytes` i `quantization`. Dopisz je do rekordu linii razem z `ollama.serverVersion`. Te pola identyfikują wagi użyte w ocenie.

**Krok 3. Pomiar z siecią**

```sh
sh ops/mac/check.sh --measure
```

Wykonuje wywołanie `python3 -m analysis.ollama_review fixtures/raw/discovery/2026-11-21.json --capture-id youtube:xtMqKkFO-0M` trzy razy zimne (model wyładowany przez `keep_alive: 0` przed każdym uruchomieniem) i trzy razy ciepłe. Dla każdego przebiegu zapisuje: czas ścienny (`/usr/bin/time -l`), szczytowy RSS procesu Pythona, próbkowany szczyt RSS procesów Ollama, minimalny odsetek wolnej pamięci (`memory_pressure`), `vm.swapusage` przed i po, `size`/`size_vram`/`context_length` z `/api/ps` oraz skrót wyniku i status oceny. `size_vram` równe `size` oznacza 100% na GPU. Liczba powtórzeń: `--runs N`. Inny model: `--model NAZWA` (skrypt podmienia stałą `MODEL` tylko w pamięci, bez zmiany plików).

Interpretacja:
- Szczyt pamięci Ollama dla modelu na Metal jest słabo widoczny w RSS. Wiarygodniejsze są `ollamaPs.size`, `minFreeMemoryPercentSampled` i wzrost `swapUsage`. Wzrost swapu między `swapBefore` a `swapAfter` oznacza, że wariant nie mieści się w pamięci.
- Identyczny `outputSha256` we wszystkich sześciu przebiegach potwierdza powtarzalność przy `temperature: 0`. Różnice zapisz.
- `review.status` `error` z kodem `ollama_timeout` (limit 180 s, `analysis/ollama_review.py:22`) lub `incomplete_response` oznacza niezdatny wariant lub starą wersję Ollama, która ignoruje `reasoning_effort: none`.

**Krok 4. Pomiar bez Internetu (ręcznie)**

1. Wyłącz Wi-Fi (pasek menu) i odłącz Ethernet.
2. Potwierdź: `curl -m 4 -sI https://huggingface.co` kończy się błędem.
3. Uruchom: `sh ops/mac/check.sh --measure --expect-offline --runs 1 --out .runtime/mac/offline.json`.
4. Skrypt odmawia pomiaru (blokada), jeśli sieć nadal działa. Wynik zawiera `internetReachableDuringMeasure: false`.
5. Przywróć sieć. Ollama i Docker działają na pętli zwrotnej i nie wymagają Internetu po pobraniu wag i obrazu.

**Krok 5. Pełne demo w Compose (jedna komenda)**

1. Skopiuj do katalogu projektu paczkę mediów replay: `replay-media-2026-11-21.tar.gz` i `replay-media-2026-11-21.tar.gz.sha256` (z devboxa: `sh ops/demo/pack-media.sh`, pliki lądują w `.runtime/dist/`). Paczka jest poza Gitem. Bez niej `start.sh` kończy z kodem 3 i instrukcją, bo kolejka „Co wymaga sprawdzenia” byłaby pusta.
2. Wymagane: Docker Desktop uruchomiony, Internet tylko przy pierwszym przygotowaniu (pip, Vosk, HuggingFace, apt-get w kontenerze), Node 22.13+ dla podglądu. Python hosta nie jest używany przy przygotowaniu (do weryfikacji paczki wystarczy dowolny `python3`).
3. `sh ops/demo/start.sh`. Skrypt: weryfikuje i rozpakowuje paczkę (SHA-256 z manifestu w repozytorium), przy pierwszym starcie przygotowuje środowisko (`bootstrap.sh`: obraz arm64, koła, Vosk, E5, FFmpeg, `arch-guard.sh`, podgląd Astryx), uruchamia Compose z paczką zamontowaną do odczytu (`/replay-media`), czeka na oba skany bootstrapu (replay M2, replay YouTube, potem kolejki) i drukuje `GOTOWE ... review=4 ids=7M0rC6-Rueo,AqXHkxDzSDI,OIyPE0z2mng,ZJrT-X08Xwc`. Czysty stan: `--reset`. Tryb pokazu ustawia `INVESTWATCH_DISCOVERY_INTERVAL=0`; `--live` włącza harmonogram.
4. `sh ops/mac/check.sh`. Oczekiwane `libvosk`, `pydanticCore`, `onnxruntime`, `ffmpegReal`: `elf-aarch64`, `replayMediaPack: present`, `reviewQueue` z `review=4`.
5. `python3 tests/offline/verify.py --root "$PWD"`, potem scenariusz z [demo.md](../../docs/hackathon/demo.md) na desktopie i telefonie.
6. Błąd `natywne biblioteki maja architekture niezgodna` oznacza zawartość z innej architektury w `.runtime/demo/deps`, `.runtime/semantic/deps` lub `.runtime/asr/vosk`: usuń wskazany katalog i uruchom `sh ops/demo/bootstrap.sh`.
7. Znane ograniczenie: `analysis/ollama_review.py` nadal ma host i model wpisane na stałe (zgłoszone właścicielom). Pomiar oceny z kroku 3 działa na hoście.

**Krok 5a. Serwisy, Ollama na hoście i szybki start**

- `start.sh` uruchamia `web` (nginx, jedyny port `127.0.0.1:8769`), `api` i `worker`. Dwa ostatnie działają w sieci wewnętrznej bez Internetu. `--live` dokłada `scheduler` i wyjście do sieci dla workera. Opis: [docs/ARCHITEKTURA.md](../../docs/ARCHITEKTURA.md). Obraz `nginx:1.27-alpine` (arm64) pobiera `prepare-darwin.sh` razem z `python:3.12-bookworm`. Ręcznie: `docker pull --platform linux/arm64 nginx:1.27-alpine`.
- Drugi głos LLM na Macu: Ollama natywnie na hoście, bo Docker Desktop nie daje kontenerom Metal. Serwisu `inference` (profil `llm`) na Macu nie włączaj.
  ```sh
  OLLAMA_CONTEXT_LENGTH=4096 ollama serve &          # albo aplikacja + launchctl setenv OLLAMA_CONTEXT_LENGTH 4096
  ollama pull ministral-3:8b-instruct-2512-q4_K_M    # model z pomiaru (docs/lanes/2026-11-21-fable-ai-inferencja.md)
  OLLAMA_HOST=host.docker.internal:11434 INVESTWATCH_LLM=1 INVESTWATCH_MODEL_ANNOTATE=1 \
    INVESTWATCH_LLM_MODEL=ministral-3:8b-instruct-2512-q4_K_M sh ops/demo/start.sh
  ```
  Gdy `OLLAMA_HOST` wskazuje `host.docker.internal`, `start.sh` dokłada nakładkę `ops/compose/egress.yaml`, czyli wyjście sieciowe i `host-gateway` tylko dla workera. Bez Ollamy karta pokazuje status `unavailable`, a reszta działa.
- Szybki start pokazu: na devboxie po `GOTOWE` uruchom `sh ops/demo/pack-state.sh`. Skopiuj `.runtime/dist/investwatch-state-2026-11-21.tar.gz` i `.sha256` do katalogu projektu na Macu i uruchom `sh ops/demo/start.sh --reset`. Przy zgodnym odcisku kodu (ta sama zawartość `api/ analysis/ collectors/ fixtures/ data/probe-snapshots/`) stan rozpakowuje się w ok. 30 s zamiast kilku–kilkunastu minut analizy. Przy niezgodnym skrypt ostrzega i liczy od zera. Archiwum działa też z `start-local.sh`.

**Krok 5b. Wariant awaryjny bez Dockera**

Gdy Compose na Macu zawiedzie: `sh ops/demo/start-local.sh`. Wymaga Pythona 3.12 (`brew install python@3.12`). Tworzy `.runtime/venv-local`, instaluje `api/requirements.lock` (sieć tylko przy pierwszym razie), uruchamia `uvicorn` i `api.worker` jako procesy hosta na tym samym porcie (`INVESTWATCH_PORT`, domyślnie 8769), czyta tę samą paczkę mediów i drukuje to samo `GOTOWE ... review=4`. Stan: `.runtime/local/state`, logi: `.runtime/local/*.log`. Zatrzymanie: `sh ops/demo/start-local.sh --stop`. Nie uruchamiaj obu wariantów na tym samym porcie. Różnice: brak Vosk i FFmpeg (upload nagrania nie działa), E5 działa po `pip install` pakietów z `analysis/semantic-requirements.txt` (skrypt próbuje to zrobić). W trybie `--live` instaluje też `yt-dlp` i `youtube-transcript-api` (`ops/demo/live-requirements.txt`).

**Krok 6. Co odesłać**

Po `GOTOWE` linię z `start.sh` (czas do kolejki) oraz pliki `.runtime/mac/check-*.json` (online), `.runtime/mac/offline.json` oraz wynik `ollama list` i `ollama --version`. Raporty nie zawierają nazwy użytkownika, hosta, adresów IP ani ścieżek domowych; przejrzyj je mimo to przed wysłaniem. Pole `hardwareModel` to identyfikator sprzętu (np. `Mac15,x`), nie dane osobowe.

## Kryteria przejścia

- Werdykt `ready` lub `warnings` bez blokad pamięci i architektury.
- Zimny przebieg kończy się `review.status` innym niż `error` w limicie 180 s, a swap nie rośnie.
- Szczyt: `ollamaPs.size` plus ok. 4 GiB na system i Docker mieści się w `unifiedMemoryGiB`, `size_vram` równe `size`.
- Pomiar bez Internetu daje te same statusy co z Internetem.

## Ścieżka awaryjna: brak pamięci lub zbyt wolno

Jeśli swap rośnie, `size_vram` jest mniejsze niż `size`, albo zimny przebieg przekracza limit:

1. Zamknij przeglądarkę i inne aplikacje, powtórz pomiar. Obniż kontekst (`OLLAMA_CONTEXT_LENGTH=2048`).
2. Wybierz mniejszą kwantyzację tego samego modelu albo mniejszy model z listy tagów na `ollama.com/library/qwen3.5/tags` (nazwy tagów sprawdź tam, nie zgaduj). Pobierz i zmierz: `sh ops/mac/check.sh --measure --model NAZWA:TAG`.
3. Wynik zmiany jest tylko pomiarem zasobów. **Nie wolno podmienić modelu w demo bez osobnego pomiaru trafności** na zamrożonych kampaniach z etykietami (próba Q z `ODBIOR.md`, TP/FP/FN/TN, koszt 2×FN+FP; linia G). Kwantyzacja i rozmiar zmieniają oceny, więc jedna ocena reklamy niczego nie dowodzi. Zapisz digest i kwantyzację nowego wariantu.
4. Zmiana modelu w kodzie wymaga edycji stałej `MODEL` w `analysis/ollama_review.py:20` (właściciel pliku). Do czasu poprawki z przełącznikiem środowiskowym pomiar zasobów obsługuje `--model`, ale demo użyje stałej.
5. Jeśli żaden wariant się nie mieści: pozostaje odtwarzalny fallback na regułach i zapisanych ocenach (bez modelu na żywo). Zapisz to jawnie w rekordzie linii.

## Typowe problemy

- `containerToOllama: unreachable`: w Docker Desktop `host.docker.internal` działa z loopbackiem hosta. Przy OrbStack lub innym silniku ustaw `OLLAMA_HOST=0.0.0.0:11434` dla serwera Ollama (tylko w zaufanej sieci). Dotyczy dopiero przyszłej integracji workera. Sama ocena działa na hoście.
- `Ollama nie udostępnia modelu`: `ollama list` musi zawierać dokładnie `qwen3.5:9b`.
- Pierwsze wywołanie `python3` na Macu bez Command Line Tools otwiera okno instalatora. Zainstaluj Pythona 3.12 z Homebrew i uruchom skrypt ponownie.
