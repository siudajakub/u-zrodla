# Lane: PITCH · treść pitchu, filmu 120 s i slajdów

- Owner: J
- Branch: hack/integration
- Worktree: główny checkout
- State: READY (treść do decyzji J, potem dopasowanie UI i PDF)
- Updated: 2026-11-21 22:40 UTC
- PR / issue: none yet

## Acceptance

Brief §4, §6 i §8 ([BRIEF](../zrodla-uknf/BRIEF.md)) oraz ustalenia koordynatora ze strony organizatora: ocena dwuetapowa, film do 2 minut, PDF poniżej 10 MB. Wynik obserwowalny: [PITCH.md](../PITCH.md) zawiera hook i tezę, pitch 3 min, plan 5 min, wersję 60 s, scenopis filmu 120 s, szkic 9 slajdów, mapę pięciu kryteriów, mocne strony z dowodem, tabelę technologii, liczby do powiedzenia i do pominięcia, 10 trudnych pytań, wymagania dla UI i ocenę podejścia. Każda liczba ma odsyłacz albo pole API. Kontrprzykład: liczba bez pokrycia trafia do tabeli „czego nie mówimy”.

## Claim

- `docs/PITCH.md`
- `docs/lanes/2026-11-21-fable-pitch.md`

## Contracts And Dependencies

- Produces: wejście dla agentów UI (PITCH §11) i dla agenta PDF (PITCH §5). Brak kontraktu kodu.
- Consumes: API podglądu `127.0.0.1:18801` (tylko GET, odczyt 22:14 UTC): `/v1/overview?schema=2`, `/v1/queues/review`, `/v1/queues/adRegister`, `/v1/cases/youtube:AqXHkxDzSDI`, `/v1/cases/youtube:CDk20n4u9Kk`. Rekordy linii B, C, D, E, F, K, AI, N, PROCES-AI, MONITORING, WYNIK-M1, WYNIK-Y, zrzuty r3, `analysis/second_opinion.py`, `analysis/inference.py`.
- Shared-file coordination: odsyłacz do `docs/ARCHITEKTURA.md` działa na dysku, ale w Gicie zadziała dopiero po commicie linii ARCH. Plik jest dziś nieśledzony.

## Current State

Model: claude-opus-5-5 (podagent PITCH zlecony przez Fable). Ustalenia:
- Drugi głos LLM (`be18904`, `fb17d18`) nie jest wpięty w `analysis/engine.py`. Produkt odmawia backendu OpenRouter (`backend_forbidden`), więc przełącznika „drugi głos przez API” nie ma. Zdanie przygotowano warunkowo, a rekomendacją jest Ollama lokalnie albo zapisany pomiar.
- W bazie podglądu `semantic.status = unavailable` i `analysisVersion.model = null`. E5 nie jest dziś widoczny w kartach.
- Nagłówek pulpitu pokazuje „na żywo” przy danych z odtworzenia (zrzuty r3).
- Karta Comparic w bazie pokazu ma obalenie mową (10:14), ale nie ma kadru 614 s (`coverage.gaps`: frames `not_collected`).
- Odrzucone jako niepotwierdzone: „ok. 150 commitów” (jest 116 do `fb17d18`), „precyzja 100%”, trafność drugiego głosu (niezacommitowane `fixtures/labeled/ai-second-opinion-*.json`), 792 testy (tylko w handoffie poza Gitem), czasy na macOS, pokrycie rynku.

## Next Step

J zatwierdza tezę i narrację. Agenci UI realizują PITCH §11 (pozycje M), a po zamrożeniu kandydata ktoś odczytuje ponownie liczby **[odczyt]** i nagrywa film według PITCH §4.

## Verification

- Skrypt odsyłaczy (linki `[..](..)`, ścieżki w backtickach, hashe commitów) na `docs/PITCH.md`: 0 braków.
- `python3 tools/check_agent_docs.py`: „Hackathon context validation passed.”
- Liczba słów: pitch 3 min 417, film 266 słów lektora, wersja 60 s ok. 130.
- Liczby z API odczytano GET-em o 22:14 UTC. Scenariusza nie przechodziłem w przeglądarce. Testów produktu nie uruchamiałem.

## Fallback / Cut

Dokument nie zmienia kodu. Wycofanie: `git revert` commita tej linii. Poprzedni scenariusz zostaje w [demo.md](../hackathon/demo.md).

## Handoff

Do przeglądu przez świeżego agenta: zgodność liczb z plikami i API oraz to, czy odpowiedzi na pytania o YouTube ToS, płatne API i drugi głos nie obiecują więcej, niż jest w kodzie. Kontrprzykład do sprawdzenia: liczby 9 i 61 z `disclosure.state` po kolejnym przeliczeniu bazy pokazu.
