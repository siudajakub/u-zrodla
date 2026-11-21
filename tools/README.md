# tools/

Skrypty pomocnicze poza produktem. Wszystkie testy z tego katalogu: `python3 -B -m unittest discover -s tools -p 'test_*.py'` (21 XI 2026: 46 testów OK). Kolumna „Kto woła” podaje miejsca znalezione przez `git grep`; same wzmianki w rekordach linii (`docs/lanes/`) pominięto.

## Walidatory dokumentów i dowodów

| Plik | Do czego | Kto woła | Test |
|---|---|---|---|
| `check_agent_docs.py` | Sprawdza zestaw plików kontekstu, budżet `AGENTS.md`, tabelę `TEAM_BOARD.md`; `--sync` odtwarza `CLAUDE.md` z `AGENTS.md` | [AGENTS.md](../AGENTS.md), `hack_ready.sh` | `test_agent_context.py` |
| `check_plan_evidence.py` | Weryfikuje sumy SHA-256 i komplet plików w [data/probe-snapshots](../data/probe-snapshots) | [AGENTS.md](../AGENTS.md), [docs/ODBIOR-UKNF.md](../docs/ODBIOR-UKNF.md) | `test_plan_evidence.py` |
| `eval_validation.py` | Liczy trafność kolejki według zamrożonego [protokołu](../fixtures/validation/PROTOKOL.md) (etykiety JSONL + predykcje) | `api/calibration_q2.py`, [fixtures/validation](../fixtures/validation) | `test_eval_validation.py` |

## Linie hackathonu

| Plik | Do czego | Kto woła | Test |
|---|---|---|---|
| `hack_context.sh` | Kontekst na start sesji: status linii i ostatnie wpisy logu | hooki w [.claude/settings.json](../.claude/settings.json) (`--claude`, `--claude --remind`), [AGENTS.md](../AGENTS.md) | `test_agent_context.py` |
| `hack_status.py` | Zbiera stan linii z worktree i gałęzi `hack/*` | [AGENTS.md](../AGENTS.md), `hack_context.sh` | `test_agent_context.py` |
| `hack_start.sh` | Tworzy linię: gałąź, worktree obok, rekord w `docs/lanes/` | [integracja](../docs/hackathon/integration.md), `hack_join.py` | brak |
| `hack_join.py` | Wybór pracy z `TEAM_BOARD.md` i start linii z wypełnionym rekordem | [integracja](../docs/hackathon/integration.md), [docs/lanes/README.md](../docs/lanes/README.md) | brak |
| `hack_ready.sh` | Bramka gotowości linii przed scaleniem | [AGENTS.md](../AGENTS.md), [integracja](../docs/hackathon/integration.md) | brak |

## Log sesji

| Plik | Do czego | Kto woła | Test |
|---|---|---|---|
| `session_log.py` | Dopisuje i czyta wpisy JSONL w `session-logs/` (`append`, `latest`, `id`) | [AGENTS.md](../AGENTS.md), `hack_context.sh` | `test_agent_context.py` |

## Pomiary

| Plik | Do czego | Kto woła | Test |
|---|---|---|---|
| `measure_llm_openrouter.py` | Pomiar modelu „typ materiału” przez OpenRouter (płatny, limity kosztu w kodzie) | ręcznie; [analysis/README.md](../analysis/README.md) | `analysis/test_inference.py` |
| `measure_second_opinion.py` | Pomiar drugiego głosu LLM na M1, M2, M3 przez OpenRouter; wyniki w `fixtures/labeled/ai-second-opinion-*` | ręcznie; [analysis/README.md](../analysis/README.md) | brak |
| `youtube_probe.py` | Rozpoznanie tras odkrywania YouTube (API i bez klucza); wynik w `fixtures/raw/discovery/youtube-probe-2026-11-21` | ręcznie; `TEAM_BOARD.md` | brak (fixture czyta `collectors/test_crosslinks.py`) |

## Monitoring

| Plik | Do czego | Kto woła | Test |
|---|---|---|---|
| `watch_sources.py` | Odpytuje kanały Atom YouTube i osadzenia TikTok, raport dzienny | `ops/user-systemd/run-watch.sh` (timer co 4 h), [docs/MONITORING.md](../docs/MONITORING.md) | `test_watch_sources.py` |
| `watch_sources.json` | Lista monitorowanych profili | `watch_sources.py` | `test_watch_sources.py` |
