# Podział pracy po rewizji UKNF

ASTRA ustala cel i kryteria odbioru, uzgadnia wspólne kontrakty, scala sprawdzony stan roboczy i przekazuje J wyniki. Każdy wykonawca rozwija i testuje swój zakres w osobnym worktree. J podejmuje decyzje produktowe i zatwierdza zgłoszenie. [Cele i kolejność prac](docs/PLAN-REALIZACJI.md)

| Linia i wykonawca | Model i reasoning | Odpowiedzialność | Kontrprzykład na tym samym materiale |
|---|---|---|---|
| M2 · SOL · m2-wave | GPT-6.2 SOL, high | Przechwycenie reklamy, 19 ID, dowody wersji, tabela źródłowa | Korzyść niższych opłat nie jest automatycznie twierdzeniem o zysku. Ostrzeżenie CFD może należeć do innego produktu. |
| M3, odkrywanie i AI · TERRA · m3-wave | GPT-6.1 TERRA, high | Od pełnej oferty do sugestii E5 i datowanego wpisu, kontrola edukacyjna, tematy 1–3, przegląd M1 | Model może uznać listę instrumentów za spersonalizowaną rekomendację. Pojedyncza zgodna nazwa nie potwierdza tożsamości. |
| Pulpit i demo · SOL · desk | GPT-6.2 SOL, high | Układ Astryx, filtry i dowód z decyzją, ocena mobilna, odtworzenie PDF briefu | Syntetyczny przykład z prostym ID nie wykrywa błędu otwierania realnej sprawy WWW z ukośnikiem w ID. |
| Integracja · ASTRA | Model sesji orkiestratora | Wymagania, przeniesienie zmian bez utraty zastanych edycji, priorytety i bramki | Ocena poprzedniej wersji lub planu nie jest pomiarem aktualnego demo. |

Do powtórzenia testów wystarcza reasoning medium. Odrębni sędziowie SOL i TERRA oceniają dowody na tej samej wersji z reasoning high. Każdy przekazuje własny rozkład punktów przed poznaniem wyniku drugiego.

## Available Work

| Slug | Outcome / acceptance | Claim | Contract / dependency | Priority | State |
| --- | --- | --- | --- | --- | --- |
| m2-capture | Zrzut i DOM właściwej wersji dla kryterium ryzyka | collectors/m2*, analysis/m2*, data/probe-snapshots/m2/ | Capture, Finding | P0 | PAUSED |
| m3-review | Wykrycie, źródło fragmentu, ustalenie podmiotu i zakresu, jawna niepewność | analysis/semantic.py, collectors/sites.py | Capture, Finding, reviewSuggestion | P0 | PAUSED |
| analyst-desk | Dowód i decyzja w zwykłej ścieżce na telefonie i desktopie | web/, tests/e2e/neutral_desk.py | Finding, Case | P0 | PAUSED |

PAUSED w tabeli rekrutacyjnej chroni zajęte linie przed ponownym przydziałem przez hack_join. Stan odbioru podaje [macierz](docs/ODBIOR-UKNF.md). Cztery historyczne linie dostarczyły bazę eaa9c10 i mają [osobne rekordy](docs/lanes/README.md).

## Odbiór roboczy

Zakresy M2, M3 i pulpitu przeniesiono do roboczej integracji. SOL i TERRA zakończyli dwie niezależne oceny. Trzy czyste starty offline przeszły na odcisku b572eda8. Formalna bramka gałęzi zakłada zatwierdzony commit. [Linia M2](docs/lanes/2026-11-21-zip-m2-capture.md) · [Linia M3](docs/lanes/2026-11-21-zip-m3-review.md) · [Pulpit i dowody](docs/DEMO-ODBIOR.md) · [Panel](docs/JUDGING.md)
