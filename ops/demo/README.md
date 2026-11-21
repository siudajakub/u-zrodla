# Lokalne demo Compose

Dwa procesy korzystają z istniejącego obrazu `python:3.12-bookworm` oraz katalogu repozytorium. Nie ma budowania obrazu ani pobierania pakietów w trakcie startu. Przed uruchomieniem integrator kopiuje `ops/demo/compose.yaml` do `compose.yaml` w katalogu głównym repozytorium.

Wymagania: Linux x86_64, Docker Compose z lokalnym obrazem `python:3.12-bookworm`, Python 3.12 z pip, hostowy `ffmpeg`, komplet kół z `api/requirements.lock` w `.runtime/build/wheels` i lokalny model ASR w `.runtime/asr`. Koła i model trzeba przygotować osobno. Konieczny jest zamontowany oddzielny wolumen `/home/codexdev/projects`; skrypt sprawdza także rezerwy miejsca. Przygotowanie kopiuje zależności FFmpeg hosta (w wykonanej próbie ok. 239 MiB) oraz instaluje koła lokalnie (ok. 22 MiB). `WHEELHOUSE` i `PREPARE_PYTHON` pozwalają wskazać alternatywne lokalne ścieżki.

```sh
sh ops/demo/prepare.sh
sh ops/demo/start.sh
```

Po przygotowaniu każde następne uruchomienie to tylko `sh ops/demo/start.sh`. Interfejs: <http://127.0.0.1:8769>. `docker compose --env-file .runtime/demo/compose.env logs -f` pokazuje logi; `docker compose --env-file .runtime/demo/compose.env down` zatrzymuje usługi bez usunięcia danych. Konfiguracja wiąże port tylko z loopbackiem. W trybie domyślnym automatyczny monitoring sieciowy jest wyłączony (`INVESTWATCH_DISCOVERY_INTERVAL=0`); replay działa offline, a ręczny skan live wymaga sieci.

Kod i model są montowane tylko do odczytu; baza spraw oraz kolejki są w `.runtime/demo/state`, na wolumenie projektu. Kontenery działają z UID i GID użytkownika, który uruchomił przygotowanie. Istniejąca `.runtime/watch/watch.sqlite3` pozostaje w repozytorium, z uprawnieniami `0600`, i jest dostępna tylko do odczytu dla tego samego UID. Nie jest kopiowana ani modyfikowana. Dla innego użytkownika należy osobno rozwiązać dostęp do tego pliku; nie należy poszerzać uprawnień. Zmiana UID, obrazu, systemowego FFmpeg albo lockfile wymaga ponownego przygotowania i sprawdzenia.

FFmpeg jest osobnym narzędziem systemowym gospodarza, nie częścią kodu produktu. `prepare.sh` lokalnie kopiuje jego binarium, dynamiczne biblioteki i loader z hosta, a wrapper uruchamia je wewnątrz kontenera. Katalog `.runtime` jest lokalnym artefaktem, nie należy go commitować ani redystrybuować jako składnika produktu; licencje i konfiguracja systemowego FFmpeg i jego bibliotek zależą od instalacji gospodarza. W szczególności niniejszy sposób uruchomienia nie zmienia ich licencji ani nie stanowi deklaracji zgodności do redystrybucji.

Próba 21 XI: w jednym kontenerze `python:3.12-bookworm`, bez sieci, z systemem plików tylko do odczytu i UID/GID `1002:1003`, import `fastapi`, `pydantic_core`, `huey`, `uvicorn` i `websockets` zakończył się poprawnie; FFmpeg poprawnie zdekodował jedną sekundę `studio.mp4` do PCM. `docker compose config` poprawnie rozwinął ścieżki, UID i port. Pełny start API + workera oraz test odczytu bazy `0600` pozostają próbą integracyjną kapitana.
