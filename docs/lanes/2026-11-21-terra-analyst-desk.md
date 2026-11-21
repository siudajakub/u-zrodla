# Lane: analyst-desk

- Owner: terra
- Branch: hack/terra/analyst-desk
- Worktree: /home/codexdev/projects/hacknation/uknf-investwatch/.worktrees/desk
- State: READY
- Updated: 2026-11-21 16:21 UTC
- PR / issue: none

## Acceptance

Operator widzi kolejkę, pochodzenie i dowody, przechodzi do fragmentu nagrania, zapisuje decyzję i sprawdza stan źródeł oraz próg. Widok działa na telefonie i bez sieci z lokalną dystrybucją React.

## Claim

- `web/`
- `tests/ui/`
- `docs/lanes/2026-11-21-terra-analyst-desk.md`

## Contracts And Dependencies

- Produces: statyczny pulpit React 18 (lokalne UMD i licencje MIT), bez buildu i CDN.
- Consumes: GET `/v1/state`, GET `/v1/calibration`, POST `/v1/scans`, PATCH `/v1/cases/{id}`, POST `/v1/cases/{id}/contract`, POST `/v1/media`, WebSocket `/v1/events`; media z `/media/` i `/uploads/`.
- Shared-file coordination: ścieżki i payload uzgodnione z kapitanem, bez zmian wspólnych kontraktów.

## Current State

Kolejka z czterema filtrami i wyszukiwaniem, karta dowodów z czasem i przewijaniem nagrania, decyzja z revision/409 i historią, aneks tylko w fikcyjnej sprawie, źródła i błędy skanów, kalibracja oraz upload pliku. Po zdarzeniu i reconnect pobierany jest cały stan. Pusty wynik, błąd i ponowienie mają widoki. Praca agenta Codex/terra; niezależny przegląd i browser smoke należą do integratora.

## Next Step

Kapitan integruje z API oraz danymi analizy i uruchamia próbę w przeglądarce na desktopie i telefonie, w tym upload, seek, konflikt 409 i awarię workera.

## Verification

- `node --check web/app.js`: sukces.
- `node tests/ui/render-smoke.cjs`: sukces; pusta kolejka, ucieczka niebezpiecznego tekstu, znacznik czasu i media.
- Browser / end-to-end: nie uruchomiono w tej linii; kapitan wykonuje po integracji, by nie uruchamiać równoległych ciężkich testów.

## Fallback / Cut

Usunąć `web/` i `tests/ui/`; API pozostaje niezależne. Sam pulpit nie zawiera fikcyjnych danych awaryjnych ani zależności sieciowych.

## Handoff

Przekazano kapitanowi kontrakt i ścieżki. Przed uznaniem zmiany za scalalną wymagane niezależny przegląd oraz `sh tools/hack_ready.sh` na wersji integracyjnej.
