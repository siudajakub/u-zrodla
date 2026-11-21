# Lokalne środowisko demo

Na macOS (Apple Silicon) wystarczy Docker Desktop i Node 22.13+ dla podglądu: `sh ops/demo/start.sh` przygotowuje koła, Vosk, E5 i FFmpeg w kontenerze linux/arm64 (apt-get ffmpeg w kontenerze, sieć wymagana tylko przy pierwszym przygotowaniu), a kontrola `ops/mac/arch-guard.sh` odrzuca biblioteki Mach-O lub innej architektury w `.runtime`. Procedura odbioru: [ops/mac/README.md](../mac/README.md). Na Linux x86_64 z Pythonem 3.12, venv/pip, systemowym FFmpeg i Docker Compose uruchom z katalogu projektu `sh ops/demo/start.sh`. Pierwszy start wywołuje bootstrap i przygotowuje publiczne pakiety, modele oraz obraz bazowy. Po przygotowaniu usługi wstają bez pobierania czegokolwiek. `start.sh` domyślnie działa w trybie pokazu: harmonogram live jest wyłączony (INVESTWATCH_DISCOVERY_INTERVAL=0), a kolejkę zasila datowany replay z paczką mediów (`.runtime/replay-media/2026-11-21`, montowana do odczytu jako `/replay-media`). `--live` włącza poszukiwania co cztery godziny. Bez paczki start kończy się instrukcją (kod 3). Archiwum paczki: `sh ops/demo/pack-media.sh`; wariant bez Dockera: `sh ops/demo/start-local.sh`; zmienne: [.env.example](../../.env.example). Obraz Compose nie zawiera yt-dlp, więc pobieranie mediów z YouTube w trybie live działa tylko lokalnie (`start-local.sh --live`).

Compose uruchamia proces HTTP i oddzielny proces kolejki z tym samym UID/GID co operator. Kod i dane wejściowe są zamontowane do odczytu. Jedynym zapisywalnym katalogiem danych produktu jest .runtime/demo/state. Stan prywatnego monitora profili znajduje się w .runtime/watch. Na nowej maszynie bez tego monitora kolektor sam pobiera publiczne profile podczas skanu live. Pulpit wiąże port 8769 na interfejsie loopback. Zmienna INVESTWATCH_PORT ustawia inny port. Zatrzymanie dwóch procesów: `docker compose --env-file .runtime/demo/compose.env stop`. Powtórny start zachowuje dane.

FFmpeg działa jako odrębny program systemowy. Skrypt prepare.sh przygotowuje z lokalnej instalacji prywatną kopię binarium, bibliotek i loader do działania w obrazie Python. Katalog .runtime nie jest częścią repozytorium. Licencje FFmpeg i bibliotek zależą od dystrybucji systemowej. Poprawki bibliotek systemowych wymagają ponownego przygotowania. Do przeniesienia demo na inny host służą repozytorium i bootstrap.

## Pulpit Astryx

Ścieżka `/theme-preview/` udostępnia jasny pulpit Astryx Neutral z katalogowym szablonem `table-inbox`. Pulpit pod `/` korzysta z lokalnie dołączonego React 18. Oba widoki odczytują tę samą bazę przez lokalne API. Podgląd ma własną kompilację React 19 i lokalne fonty Figtree.

Podgląd wymaga do kompilacji Node.js od 22.13 i npm. Pierwszy bootstrap przygotowuje go razem ze środowiskiem. Na przygotowanej maszynie start używa katalogu pakietów npm pod `.runtime/desk-preview/` w trybie offline. Pinowanie wersji zapewnia `web/package-lock.json`. Kompilacja uruchamia się po zmianie odcisku źródeł lub braku artefaktu. Gotowe pliki są serwowane z `web/theme-preview/`.

Na wcześniej przygotowanej maszynie z pustą pamięcią pakietów jednorazowo wykonaj:

```sh
sh ops/demo/prepare-preview.sh --prepare
```

Później można wymusić lokalne sprawdzenie przez `sh ops/demo/prepare-preview.sh --offline`. Opcja `INVESTWATCH_PREVIEW=off` uruchamia usługi bez kroku kompilacji. Błąd przygotowania podglądu znajdziesz w `.runtime/demo/preview.log`. [Próba Chromium](../../tests/offline/README.md)
