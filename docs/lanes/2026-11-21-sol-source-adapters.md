# Lane: source-adapters

Historyczny rekord pierwszej integracji. Aktualny zakres i model wykonawcy wskazuje [tablica](../../TEAM_BOARD.md).

- Owner: sol
- Branch: hack/sol/source-adapters
- Worktree: .worktrees/sources
- State: READY
- Updated: 2026-11-21 16:21 UTC
- PR / issue: none

## Acceptance

M1 cyklicznie wyszukuje nieznane wcześniej kanały finansowe i pobiera publikacje. Powtórzenie tej samej odpowiedzi zachowuje identyfikatory twórców i publikacji. M2 i M3 pobierają tekst ofert wykrytych w odsyłaczach ze stron startowych. Każde źródło ma datę, wynik i zakres odczytu.

## Claim

- `collectors/`
- `fixtures/raw/discovery/`

## Contracts And Dependencies

- Wywołanie `collectors.discovery.discover(mode, known_ids, known_creators=...)` zwraca `creators`, `captures` i `sources`. Aplikacja przechowuje twórców i przekazuje poprzednie rekordy przy kolejnym skanie.
- `INVESTWATCH_WATCH_DB` wskazuje istniejącą bazę monitoringu. Adapter otwiera ją tylko do odczytu. Bez zmiennej próbuje domyślnej bazy projektu, a gdy jej brakuje, odczytuje publiczne Atom YouTube i widgety TikTok.
- Zawartość audio jest dostępna dla wybranych odcinków RSS przez `collectors.audio.fetch_excerpt(capture, target_path)`. Worker ustala długość odczytanego wycinka i wykonuje lokalne ASR.

## Current State

- Apple Podcasts wyszukuje frazy „inwestowanie”, „obligacje” i „portfel ETF” w katalogu PL. ID audycji, fraza, pozycja i skrót odpowiedzi opisują odkrycie. Język wydawcy jest sprawdzany w RSS. Wydawca i audycja pozostają odrębnymi polami. Do ośmiu udokumentowanych kanałów RSS na przebieg, w kolejności najdawniejszego odczytu. Znane kanały pozostają w puli po zniknięciu z wyników katalogu. [Apple Search API](https://performance-partners.apple.com/search-api)
- Sepia Search sprawdza „ETF” i „kryptowaluty”. Odczyt dotyczy opisów zaindeksowanych przez PeerTube. Dopasowanie tematu i języka daje kandydata do sprawdzenia. Zasięg ogranicza indeks i pierwsza strona wyników. [Sepia Search](https://joinpeertube.org/en_US/browse-content)
- WWW analizuje jeden link na domenę z listy. Wykorzystuje tekst HTML i zapisuje ścieżkę odkrycia. Odczyt pomija część nawigacyjną, stopkę i skrypty. Pomiary obrazu wymagają przechwycenia przeglądarką.
- Wycinek audio ma najwyżej 1,5 MiB od początku pliku MP3. Każdy etap przekierowania jest ograniczony do zweryfikowanych publicznych hostów danego dostawcy. Odpowiedź z pełnym plikiem jest ucinana po tym samym limicie. Pole `transcriptSource` wskazuje opcjonalny link od wydawcy, jeżeli pojawił się w RSS.
- Offline używa pliku `fixtures/raw/discovery/2026-11-21.json` z publicznego odczytu ok. 15:55 UTC. Zawiera 21 profili i audycji, w tym 13 spoza list startowych. Obejmuje 11 wybranych publikacji z krótkimi fragmentami, datami, odnośnikami i skrótami. `recordedCount` wskazuje liczbę pozycji z odczytu, `count` liczbę zachowaną w próbce lub w zwróconych profilach. Pozycje odtworzone mają tryb replay.

## Next Step

Kapitan integruje linię z workerem, zapisem znanych twórców, statusem źródeł i lokalną transkrypcją. Potem uruchamia bramkę na autoryzowanym commicie.

## Verification

- `python3 -B -m unittest collectors.test_discovery -v` — 7 zaliczonych testów. Kontrole obejmują zmianę wyniku bez zmiany zapytania, odczyt audycji po zniknięciu z katalogu, powtórzenie, 403, błędną odpowiedź RSS, pustą odpowiedź i ograniczenie audio.
- `python3 -B -m collectors.discovery replay` — 21 twórców i domen, 13 nowych na pustej bazie, 11 publikacji. Drugi replay z przekazanymi ID daje 0 nowych.
- Dwa wywołania `discover("live", ...)` z lokalną bazą monitoringu trwały razem 4,14 s. Pierwsze odkryło 11 podcastów i 2 kanały PeerTube oraz zwróciło 79 publikacji i stron. Drugie dodało 0 twórców i 8 wcześniej nieodczytanych odcinków z rotacji RSS. Każde wywołanie miało 19 udanych źródeł z wynikami i 2 poprawne puste wyniki. Łącznie odczytano 30 opisów YouTube i 20 podpisów TikTok na przebieg. Linki ofert odkryto na stronach XTB, BDM i FinanceWell.
- Publiczne odcinki Spreaker, Anchor i Buzzsprout zwróciły poprawny plik MP3 o wielkości 1 572 864 bajtów każdy. FFmpeg zdekodował 30,0 s początku pierwszego materiału do 16 kHz mono. Odczyt reszty audycji wymaga kolejnej próbki z adekwatnym zakresem.
- Wymagany świeży przegląd drugiej osoby i `sh tools/hack_ready.sh -- python3 -B -m unittest collectors.test_discovery` po autoryzowanym commicie.

## Fallback / Cut

Przełącz na replay przy braku sieci. Błąd katalogu lub dostępności pojedynczego kanału ma własny status. Pozostałe odczyty kończą się w tym samym skanie. Gdy próbka dźwięku jest niedostępna, karta nadal ma publiczny opis lub podpis i ich proweniencję.

## Handoff

SOL wdrożył i zweryfikował adaptery. Rekord integracji powinien stwierdzić, czy końcowa transkrypcja workera i odtwarzanie w stanowisku analityka przeszły próbę na tym samym wydaniu.
