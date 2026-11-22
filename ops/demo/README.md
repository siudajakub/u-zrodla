# Lokalne środowisko demo

W katalogu projektu uruchom `sh ops/demo/start.sh` z Docker Compose albo `sh ops/demo/start-local.sh` bez Dockera. Pulpit jest dostępny na [127.0.0.1:8769](http://127.0.0.1:8769/).

Linux x86_64 wymaga Pythona 3.12 z venv i pip, systemowego FFmpeg oraz Node.js 22.13 lub nowszego do budowy pulpitu. Na Apple Silicon wariant Compose przygotowuje zależności Pythona, Vosk, E5 i FFmpeg w kontenerze linux/arm64. Pierwsze przygotowanie korzysta z sieci. Po nim odtwarzanie działa offline. [Apple Silicon](../mac/README.md)

Domyślny start odtwarza skan z 21 listopada 2026 i korzysta z paczki mediów montowanej tylko do odczytu. Przy braku paczki skrypt drukuje instrukcję i kończy pracę kodem 3. `--live` uruchamia osobny harmonogram, domyślnie co cztery godziny. Wariant Compose nie zawiera yt-dlp. Do pozyskiwania mediów YouTube użyj `start-local.sh --live`. [Przełączniki i ścieżki](../../.env.example)

## Lokalny model Ollama

Wariant Compose na Linuksie przygotowuje domyślne wagi przez:

```sh
sh ops/inference/pull-model.sh
sh ops/demo/start.sh
```

Wariant natywny łączy się z miejscową Ollamą. Uruchom aplikację Ollama lub `ollama serve`, a następnie wykonaj:

```sh
ollama pull qwen3.5:4b-q4_K_M
sh ops/demo/start-local.sh
```

Na Apple Silicon Ollama może używać Metal na hoście. Przy Compose wskaż ją przez `OLLAMA_HOST=host.docker.internal:11434`. Inny lokalny model ustawisz przez `INVESTWATCH_LLM_MODEL`. Do działania bez drugiego głosu służy `INVESTWATCH_LLM=0`. Bez dostępnej Ollamy E5, Vosk i reguły nadal działają lokalnie. OpenRouter pozostaje w osobnych skryptach pomiarowych. [Przepływ analizy](../../analysis/README.md)

## Stan i odtwarzanie

Compose uruchamia proces HTTP i oddzielny proces kolejki z tym samym UID/GID co operator. Kod i dane wejściowe są zamontowane do odczytu. SQLite i magazyn obiektów mają osobne zapisywalne katalogi. Domyślnie są to `.runtime/demo/state` i `.runtime/demo/objects`. Stan prywatnego monitora profili znajduje się w .runtime/watch. Na nowej maszynie bez tego monitora kolektor sam pobiera publiczne profile podczas skanu live. Pulpit wiąże port 8769 na interfejsie loopback. Zmienna INVESTWATCH_PORT ustawia inny port. Zatrzymanie dwóch procesów: `docker compose --env-file .runtime/demo/compose.env stop`. Powtórny start zachowuje dane.

Gotową kolejkę można przenieść w parze archiwów stanu i mediów. Umieść oba pliki `.tar.gz` i odpowiadające im pliki `.sha256` w katalogu projektu lub w `.runtime/dist`. Start odtworzy stan, gdy archiwum pasuje do bieżącego kodu. Flaga `--cold` wymusza analizę archiwum źródeł na pustej bazie. Sprawdzenie gotowości czeka na ukończony skan i dopuszcza pustą kolejkę.

FFmpeg działa jako odrębny program systemowy. Skrypt prepare.sh przygotowuje z lokalnej instalacji prywatną kopię binarium, bibliotek i loader do działania w obrazie Python. Katalog .runtime nie jest częścią repozytorium. Licencje FFmpeg i bibliotek zależą od dystrybucji systemowej. Poprawki bibliotek systemowych wymagają ponownego przygotowania. Do przeniesienia demo na inny host służą repozytorium i bootstrap.

## Pulpit Astryx

Pulpit pod `/` i pod `/theme-preview/` korzysta z tej samej lokalnej kompilacji React 19, szablonu Astryx `table-inbox` i fontu Inter z polskimi znakami. Obie ścieżki odczytują tę samą bazę przez lokalne API.

Podgląd wymaga do kompilacji Node.js od 22.13 i npm. Pierwszy bootstrap przygotowuje go razem ze środowiskiem. Na przygotowanej maszynie start używa katalogu pakietów npm pod `.runtime/desk-preview/` w trybie offline. Pinowanie wersji zapewnia `web/package-lock.json`. Kompilacja uruchamia się po zmianie odcisku źródeł lub braku artefaktu. Gotowe pliki są serwowane z `web/theme-preview/`.

Na wcześniej przygotowanej maszynie z pustą pamięcią pakietów jednorazowo wykonaj:

```sh
sh ops/demo/prepare-preview.sh --prepare
```

Później można wymusić lokalne sprawdzenie przez `sh ops/demo/prepare-preview.sh --offline`. Opcja `INVESTWATCH_PREVIEW=off` uruchamia usługi bez kroku kompilacji. Błąd przygotowania podglądu znajdziesz w `.runtime/demo/preview.log`. [Próba Chromium](../../tests/offline/README.md)
