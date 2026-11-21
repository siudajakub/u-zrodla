# Mapa dokumentacji

## Jury: kolejność czytania (ok. 15 min)

1. [Brief UKNF](zrodla-uknf/BRIEF.md): wymagania i kryteria oceny; [pięć plików konkursu](zrodla-uknf/README.md), oryginały w [brief/](brief/).
2. [HACKATHON.md](../HACKATHON.md): opis zgłoszenia, wyróżnik, stan względem briefu.
3. [ARCHITEKTURA.md](ARCHITEKTURA.md): serwisy, przepływ danych, bezpieczeństwo, punkty rozszerzeń.
4. [PROCES-AI.md](PROCES-AI.md): role agentów, bramki, przypadki, w których agent złapał błąd.
5. [ODBIOR-UKNF.md](ODBIOR-UKNF.md): każde wymaganie briefu ze statusem i dowodem.

Uruchomienie: [README](../README.md). Pokaz: [scenariusz](hackathon/demo.md), [PITCH.md](PITCH.md), [prezentacja PDF](../presentation/InvestWatch.pdf).

## Kod: gdzie co jest

| Katalog | Zawartość | Mapa |
|---|---|---|
| `collectors/` | Odkrywanie i zapis materiałów (YouTube, social, strony M2/M3, Meta) | [README](../collectors/README.md) |
| `analysis/` | Reguły M1/M2/M3, E5, klasyfikator, drugi głos | [README](../analysis/README.md) |
| `api/` | FastAPI, SQLite, kolejka i worker skanów | [README](../api/README.md) |
| `web/` | Pulpit analityka (React, Astryx) | [README](../web/README.md) |
| `ops/` | Start, Compose, paczki stanu i mediów, Mac | [README](../ops/README.md) |
| `tests/` | Testy kontraktowe, UI, e2e, próba offline | [README](../tests/README.md) |
| `tools/` | Walidatory, narzędzia linii, pomiary | [README](../tools/README.md) |
| `fixtures/`, `data/probe-snapshots/` | Dane surowe, etykiety, zamrożony zbiór walidacyjny, datowane sondy | [README](../fixtures/README.md) |

## Rozwój: dla kolejnego agenta

| Potrzeba | Dokument |
|---|---|
| Reguły pracy (Codex i Claude Code) | [AGENTS.md](../AGENTS.md); `CLAUDE.md` jest generowany z niego |
| Kontrakt API i schemat v2 | [rekord H](lanes/2026-11-21-fable-h-kontrakt.md), [kontrakty integracji](hackathon/contracts.md) |
| Kto robił co i z jakim wynikiem | [rekordy linii](lanes/README.md), [tablica](../TEAM_BOARD.md) |
| Plan i próby rundy 2 | [prompt startowy](fable/START_PROMPT.md), [plan](fable/REALIZACJA.md), [próby odbiorowe](fable/ODBIOR.md), [OpenRouter i Mac M3](fable/OPENROUTER-M3.md) |
| Protokół integracji i gałęzi | [integration.md](hackathon/integration.md), [playbook.md](hackathon/playbook.md) |
| Źródła danych, limity, dostęp | [MONITORING.md](MONITORING.md) |
| Licencje zależności i modeli | [LICENCJE.md](LICENCJE.md) |
| Stan poprzednich rund | [archiwum](archiwum/README.md) |
