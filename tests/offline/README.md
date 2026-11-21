# Trzy starty bez dostępu do Internetu

**Próba po integracji materiałów ZIP**. 21 XI 2026 na przygotowanym hoście trzy puste projekty Compose z siecią wewnętrzną dostarczyły po 20 spraw i 20 wersji w 6,27 s, 6,61 s i 7,00 s. Wszystkie miały lokalny wynik E5. W pierwszej próbie przesłany klip zwrócił cytat 0,33–3,60 s. W trzeciej nowy worker dokończył zadanie po przerwaniu i zasymulowanym wygaśnięciu dzierżawy. [Wyniki tej wersji](proof-zip-2026-11-21.json)

Na hoście z Dockerem, gotowym obrazem i zależnościami demonstratora uruchom:

```sh
python3 tests/offline/verify.py --root "$PWD"
```

Każda próba tworzy osobny projekt Compose, kontenery API i workera oraz puste katalogi pod `.runtime/proof`. Wewnętrzna sieć bez wyjścia na Internet, wyłączony harmonogram live i wyłącznie lokalne wagi są częścią testu. Limit CPU wynosi 1 na usługę. Skrypt sprawdza rozwiązane montowania przed startem i faktyczną sieć po starcie. Odczyt HTTP pochodzi z loopbacku w kontenerze API, ponieważ wewnętrzny bridge może wyłączyć forwarding portu na hoście. Kontenery i sieć testowa są zamykane również po niepowodzeniu.

**Stan po przebudowie pionu YouTube (21 XI 2026, wieczór).** Próba oczekuje teraz pełnego startu pokazu: co najmniej dwóch skanów bootstrapu (replay M2, `bootstrap-youtube-replay-v1`, a od późniejszej zmiany kodu także `bootstrap-social-replay-v1`) zakończonych, paczki mediów zamontowanej do odczytu w `/replay-media` (17 filmów, źródło `replay-media` ze statusem `ok`) i kolejki **Co wymaga sprawdzenia** z dokładnie czterema filmami (7M0rC6-Rueo, AqXHkxDzSDI, OIyPE0z2mng, ZJrT-X08Xwc) w wariancie `qual_d`. Zamiast starych „20 spraw” raport zapisuje liczniki kolejek (`queues`: review, adRegister, offersM2, offersM3, incomplete, all, demo, transcriptPending). Wersje liczone są jako brak luk numeracji; nadmiarowe wersje (`extraVersions`) to dowód z transkrypcji. Pierwszy zimny start liczy ok. 1,4 tys. materiałów, więc trwa ok. 5 min przy limicie 1 CPU. Paczkę wskazuje `INVESTWATCH_REPLAY_MEDIA` (domyślnie `.runtime/replay-media/2026-11-21`). Przebieg z 21 XI na devboxie (obciążony host): 296,8 s, 290,2 s i 296,3 s do czterech filmów w kolejce, 1386, 1386 i 1414 spraw (kod zmieniał się w trakcie przez innych agentów), lokalny wynik E5 przy każdej sprawie M2/M3, upload MP4 z cytatem 0,33–3,60 s, odtworzenie po SIGKILL workera w trzeciej próbie, szczyt pamięci workera 647–832 MiB, brak OOM. Końcowy odcisk kodu różnił się od początkowego, więc raport nie jest dowodem na zamrożonej wersji; powtórz próbę po zamrożeniu kodu (`.runtime/proof/cold-*/report.json`).

W historycznym pomiarze z 21 XI 2026 wszystkie trzy starty dostarczyły **17 spraw, 17 wersji i 17 wyników lokalnego modelu semantycznego**. Czas od wywołania Compose do gotowej kolejki HTTP wyniósł kolejno **4,37 s**, **3,69 s** i **4,92 s**. W pierwszej próbie dodatkowy upload MP4 został rozpoznany przez lokalny Vosk. Cytat z jedną nazwą marki miał zakres 0,33–3,60 s. Najwyższy odczyt `memory.peak` workera wyniósł 949,9 MiB przy limicie 1200 MiB. Dla API było to 64,7 MiB. Docker nie wskazał zakończenia przez OOM.

W trzeciej próbie skrypt czeka na atomowe przejęcie zadania, wysyła SIGKILL do własnego workera, przyspiesza wygaśnięcie wyłącznie tej dzierżawy na bazie testowej i wznawia kontener. Drugi właściciel ukończył ten sam identyfikator zadania. Baza miała jeden zakończony skan, dwie próby przetworzenia i 17 różnych identyfikatorów spraw. Szczyt pamięci trzeciego przebiegu dotyczy wznowionego kontenera.

Wyniki maszynowe zawiera [raport](proof-2026-11-21.json). Raport wskazuje lokalny commit użyty do pomiaru; zawiera on poprawkę wspólnej rejestracji zadań w API i workerze Huey. Pole `codeSha256` obejmuje rzeczywiste pliki montowanych modułów i Compose, również nowe pliki spoza indeksu. Skrót zgadzał się przed i po trzech próbach. Aby porównać zawartość przyszłej rewizji:

```sh
python3 tests/offline/verify.py --root "$PWD" --fingerprint-only
```

## Odbiór pulpitu w Chromium

Na oddzielnej, uruchomionej bazie z datowanym replay powtórz tę samą ścieżkę w dwóch widokach. Uruchom kolejno testy z Pythona z Playwright i lokalnym Chromium.

```sh
sh ops/demo/prepare-preview.sh --offline
python tests/e2e/neutral_desk.py http://127.0.0.1:18773 baseline --out .runtime/browser/review
python tests/e2e/neutral_desk.py http://127.0.0.1:18773 neutral --out .runtime/browser/review
```

Adres 18773 oznacza osobną instancję testową. Test zapisuje decyzje i wykonuje odczyt z API. Przechodzi kolejkę, nagranie, decyzję, dowód M2, kartę źródeł i próg przy 1440 × 1000 oraz 390 × 844. Sesja Playwright blokuje żądania do innych originów. Przy podglądzie wymusza zapis z nieaktualną rewizją, zachowanie szkicu i ponowienie decyzji. Dodaj `--require-live`, gdy baza zawiera archiwa renderowanych stron XTB i BDM oraz ofertę DM BOŚ. Tryb tworzy zrzuty dowodu kryterium 3 ETF i karty M3. Test sprawdzi także zapis dla identyfikatora sprawy ze znakiem ukośnika. Flaga `--chromium` wskazuje istniejący plik binarny, gdy środowisko używa systemowej kopii. [Przygotowanie stanowiska](../../ops/demo/README.md)
