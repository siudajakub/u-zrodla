# Lane: analysis-evidence

Historyczny rekord pierwszej integracji. Aktualny zakres i model wykonawcy wskazuje [tablica](../../TEAM_BOARD.md).

- Owner: astra
- Branch: hack/astra/analysis-evidence
- Worktree: /home/codexdev/projects/hacknation/uknf-investwatch/.worktrees/analysis
- State: READY
- Updated: 2026-11-21 16:21 UTC
- PR / issue: brak

## Acceptance

M1 wskazuje polską wypowiedź obecną tylko na ścieżce audio, z czasem i plikiem. M2 zwraca 19 pozycji ze stanem i pochodzeniem. M3 rozróżnia ofertę, edukację i kolizję nazw w KNF. Suwak progu przelicza te same oznaczone przypadki.

## Claim

- `analysis/`
- `fixtures/labeled/`

## Contracts And Dependencies

- Produces: `analysis.engine.demo_captures`, `analyze`, `calibration`, `analysis.transcribe.transcribe_file` i `transcribe_excerpt`.
- Consumes: Capture v1, odczyty DOM i rejestrów z 21 XI 2026, ffmpeg, Vosk CPU oraz pobierane jednorazowo wagi PL.
- Shared-file coordination: API serwuje `/media/` i `/evidence/browser/`, desk korzysta ze znaczników czasu i rozkładu evidence.

## Current State

Gotowe lokalne CLI, instalator z weryfikacją sum, polskie MP4 z syntetycznym głosem, zachowany wynik modelu przypisany do SHA-256 i jawna próbka kalibracji. Dźwięk dodaje 82 punkty w demonstracyjnej karcie Aurora. XTB ma 2 obserwacje pomiarowe i 17 wierszy z jawnym ograniczeniem danych. Przeznaczenie wyników to przesiew do przeglądu przez człowieka. Model Vosk wydobywa mowę; klasyfikacja treści korzysta z wersjonowanych reguł.

## Next Step

Kapitan integruje i sprawdza na działającym UI odtwarzanie od 4,35 s oraz upload nowego pliku. Odrębny przegląd i bramka czystej gałęzi po autoryzowanym commicie.

## Verification

- `python3 -B -m unittest analysis.test_engine` — 14/14 na CPU, w tym inferencja nowego WAV i częściowego MP3, przypadek informacji w obu modalnościach, odrzucenie zmiany hasha i pary kontrolne M2/M3.
- `python3 -B -m analysis.setup_asr` — ponowne użycie zweryfikowanych archiwów i odtworzenie runtime bez sieci.
- `ffprobe -v error -show_entries stream=codec_type,codec_name,duration -of compact analysis/media/studio.mp4` — H.264 13,75 s i AAC 13,84 s.
- `python3 tools/check_agent_docs.py`, `python3 tools/check_plan_evidence.py`, `python3 -B -m unittest discover -s tools -p 'test_*.py'` — dokumenty i manifest poprawne, 23/23 testy narzędzi.
- `sh tools/hack_ready.sh -- python3 -B -m unittest analysis.test_engine` — bramka przed commitem zwróciła 1 zgodnie z wymaganiem czystego kandydata. Kapitan powtarza po zatwierdzeniu.

## Fallback / Cut

Gdy wag brak, kontrolny film ma transkrypcję z poprzedniego rzeczywistego uruchomienia, weryfikowaną skrótem. Nowe pliki wymagają instalacji modelu. Brak sygnału lub niepełna modalność nie potwierdza zgodności materiału.

## Handoff

Konsument otrzymał kontrakty funkcji i mapowanie zasobów. Włączenie w aplikacji oraz sprawdzenie wizualne należy do kapitana i linii analyst-desk. Zestaw 13 przypadków ma 4 obserwacje publiczne i 9 syntetycznych, etykiety autora. Niezależna ewaluacja trafności pozostaje do wykonania.

## Druga próbka i prezentacja

`demo-aurora-kod` zawiera jedną wzmiankę w syntetycznej wypowiedzi „pobierz aplikację aurora i otwórz rachunek”. Surowy Vosk wskazał 0,33–3,60 s. W dostępnej wypowiedzi i opisie brak deklaracji współpracy. Model przepisał rzeczywisty dźwięk, a reguły dały 12→74. Przeciwpróby obejmują neutralną wzmiankę, opis z deklaracją i brak opisu. `python3 -B -m unittest analysis.test_engine` przeszło 15/15.

`presentation/InvestWatch.pdf` ma 4 strony 960×540 pkt, zweryfikowane przez `pdfinfo`, ekstrakcję tekstu i rasteryzację stron. Edycja i generowanie z `presentation/prepare.py`. Liczby odkrycia pochodzą z pierwszego runu monitora i odrębnej rzeczywistej odpowiedzi zachowanej w `fixtures/raw/discovery/2026-11-21.json`.

Niezależny przegląd integracji wykrył mylenie proweniencji identycznego materiału po replay→live i link błędu kalibracji do nieistniejącej sprawy. Potwierdzono poprawki w głównym repozytorium. Kapitan otrzymał także przypadek wielokrotnego uploadu po pierwszym nieudanym rozpoznaniu.
