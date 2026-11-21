# Rekordy linii

Jeden rekord na linię: zakres plików, stan, weryfikacja, przekazanie. Rekordy są dowodem procesu z 21 XI 2026 i nie są aktualizowane wstecz. Kolumna „Stan w rekordzie” podaje ostatni zapis autora; o tym, co jest w kodzie, rozstrzyga `hack/integration` i [macierz odbioru](../ODBIOR-UKNF.md). Wzór nowego rekordu: [TEMPLATE.md](TEMPLATE.md).

## Runda 2 · Claude Code (Fable, agenci Opus i Sonnet)

| Linia | Zakres plików | Stan w rekordzie | Najważniejszy wynik | Rekord |
|---|---|---|---|---|
| B · YouTube | `collectors/youtube.py`, `tools/youtube_probe.py`, `fixtures/raw/discovery/youtube-*` | ACTIVE, kod scalony | Adapter Data API v3 + Atom i skan live; próba pokrycia 3 z 5 największych kanałów listy Y (niezaliczona) | [b-youtube](2026-11-21-fable-b-youtube.md) |
| C · multimedia | `collectors/media.py`, `fixtures/raw/media/` | kod scalony | Napisy, kadry i ASR; mowa i kadr obaliły podejrzenie Comparic (614 s) | [c-media](2026-11-21-fable-c-media.md) |
| D · kwalifikacja M1 | `analysis/qualification.py`, `analysis/firm_index.py` | ACTIVE, kod scalony | Reguły `qual_d`: FP 0, FN 0 na 26 materiałach strojenia (etykiety agentów) wobec FP 7, FN 4 reguł 1.2 | [d-kwalifikacja](2026-11-21-fable-d-kwalifikacja.md) |
| D · porównanie z LLM | `fixtures/raw/review-compare/` | zakończone | Qwen 9B i 27B nie poprawiły reguł D; koszt 0,0417 USD | [d-porownanie](2026-11-21-fable-d-porownanie.md) |
| E · M2 | `analysis/m2_*`, `collectors/m2_*`, `data/probe-snapshots/m2/` | READY, kod scalony | 19 kryteriów na 25 stronach 11 firm, 1440 i 390 px | [e-m2](2026-11-21-fable-e-m2.md) |
| F · M3 | `analysis/offers.py`, `collectors/sites.py` | READY, kod scalony | 4 osie Tematu 3 i 12 wykazów KNF; jedna skierowana oferta na 31 materiałów | [f-m3](2026-11-21-fable-f-m3.md) |
| H · kontrakt v2 | `api/`, `tests/core/` | kontrakt uzgodniony, implementacja w kolejnych commitach | Kontrakt v2 zgodny wstecz, testy kontraktowe przed kodem | [h-kontrakt](2026-11-21-fable-h-kontrakt.md) |
| ARCH · Compose | `compose.yaml`, `ops/`, `docs/ARCHITEKTURA.md` | łatka do `api/` zastosowana przez H | Serwisy web, api, worker, scheduler, inference; jedyny port 127.0.0.1:8769 | [ARCHITEKTURA](../ARCHITEKTURA.md), [łatka](2026-11-21-fable-arch-api.diff) |
| I · UX | dokumentacja (kod w `web/` prowadzi J1) | ACTIVE | Obserwacja kolejki i karty, dwa warianty układu, audyt redukcyjny | [i-ux](2026-11-21-fable-i-ux.md), [i-uproszczenie](2026-11-21-fable-i-uproszczenie.md) |
| K · social | `collectors/social.py`, `collectors/vendor_social.py`, `collectors/meta_*` | kod scalony | TikTok z odsyłaczy YouTube; FB/IG `access_blocked`, próbka ScrapeCreators (74 ze 100 darmowych kredytów) | [k-social](2026-11-21-fable-k-social.md) |
| Meta · badania | tylko dokumentacja | zakończone | Drogi oficjalne, MCP i biblioteki dla FB/IG z oceną ryzyka | [alternatywy](2026-11-21-fable-meta-alternatywy.md), [GitHub](2026-11-21-fable-meta-github-research.md), [MCP](2026-11-21-fable-meta-mcp-research.md) |
| Transkrypcje · badanie | tylko dokumentacja | zakończone | Porównanie dróg pozyskania polskich transkrypcji YouTube | [transkrypcje](2026-11-21-fable-transkrypcje-research.md) |
| AI · inferencja | `analysis/inference.py`, `analysis/material_classifier.py` | kod scalony, LLM domyślnie wyłączony | E5 + regresja 30/57 na odłożonym zbiorze; LLM bez istotnej przewagi przy n = 57 | [ai-inferencja](2026-11-21-fable-ai-inferencja.md), [łatka](2026-11-21-fable-ai-inferencja-patch.diff) |
| AI · drugi głos | `analysis/second_opinion.py`, `tools/measure_second_opinion.py` | kod scalony, domyślnie wyłączony | W M3 jako weto koszt 2×FN+FP spada z 10 do 1; w M1 i M2 bez poprawy | [ai-drugi-glos](2026-11-21-fable-ai-drugi-glos.md) |
| N · demo i proces | `docs/PROCES-AI.md`, `docs/hackathon/demo.md`, `presentation/` | ACTIVE | Opis procesu z 10 przypadkami błędów i scenariusz pokazu | [n-demo](2026-11-21-fable-n-demo.md) |
| PITCH | `docs/PITCH.md` | READY do decyzji J | Treść pitchu, filmu 120 s i slajdów | [pitch](2026-11-21-fable-pitch.md) |
| Sędziowie | tylko odczyt | zakończone | Dwie niezależne oceny wobec §8 briefu (20:30 i 22:30 UTC) | [ocena 1](2026-11-21-fable-ocena-kryteria.md), [ocena 2](2026-11-21-fable-ocena-kryteria-2.md) |

Makiety UX: [fable-i-ux-makiety.md](fable-i-ux-makiety.md), [fable-i-uproszczenie/makiety.md](fable-i-uproszczenie/makiety.md).

## Runda 1 · Codex (ASTRA, SOL, TERRA)

| Linia | Rekord |
|---|---|
| analysis-evidence (ASR, próbka Aurora) · core-cases (sprawy, decyzje) · source-adapters (podcasty, PeerTube) · analyst-desk (pierwszy pulpit) | [astra](2026-11-21-astra-analysis-evidence.md), [captain](2026-11-21-captain-core-cases.md), [sol](2026-11-21-sol-source-adapters.md), [terra](2026-11-21-terra-analyst-desk.md) |
| m2-capture · m3-review (po rewizji ZIP UKNF) | [zip-m2](2026-11-21-zip-m2-capture.md), [zip-m3](2026-11-21-zip-m3-review.md) |

## Zasady

- Jeden właściciel i jeden rekord na gałąź; rozłączne ścieżki. Stany: `PLANNED`, `ACTIVE`, `BLOCKED`, `READY`, `INTEGRATED`, `CUT`.
- `python3 tools/hack_join.py --list` pokazuje wolne zadania z [tablicy](../../TEAM_BOARD.md), `python3 tools/hack_status.py` zbiera stan worktree i gałęzi `hack/*`. Wspólne interfejsy: [kontrakty](../hackathon/contracts.md).
