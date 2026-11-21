# Podział pracy po rewizji UKNF

W sesji Claude obowiązuje [plan Fable z priorytetem YouTube](docs/fable/REALIZACJA.md). Poniżej zachowano stan poprzedniej fali.

## Tablica Fable · fala 1 (rozpoznanie), 21 XI

Baza 491094d, główny checkout, rozłączne pliki, bez commitów. Model i wysiłek to wartości zamówione przy uruchomieniu podagenta. Faktyczny model potwierdza raport agenta.

| ID | Agent · wysiłek | Zakres zapisu | Stan | Zależność | Próba | Dowód | Kolejny ruch |
|---|---|---|---|---|---|---|---|
| A | Opus high | docs/ODBIOR-UKNF.md | w toku | brak | Każde obowiązkowe wymaganie ma właściciela, walidatory przechodzą | docs/ODBIOR-UKNF.md | Odbiór rejestru przez Fable |
| G | Opus high | fixtures/validation/, tools/eval_validation.py | w toku | brak | Zamrożony protokół, niezależna lista Y, testy narzędzia | fixtures/validation/ | Lista Y pozostaje ukryta przed B |
| I | Opus high | docs/lanes/2026-11-21-fable-i-ux.md | w toku | brak | Obserwacja kolejki, dwa warianty, pola do kontraktu | rekord linii | Pola przekazać H |
| B | Opus high | docs/lanes/2026-11-21-fable-b-youtube.md, fixtures/raw/discovery/youtube-probe-2026-11-21/, tools/youtube_probe.py | w toku | dostęp do Data API v3 | Status każdej drogi z próbą live, kandydaci na pierwszy pion | rekord linii | Decyzja o drodze adaptera |
| D | Opus high | docs/lanes/2026-11-21-fable-d-kwalifikacja.md | w toku | brak | Rozstrzygnięcia wierszy próby Q dla M1, kształt pól | rekord linii | Uzgodnić z H |
| H | Sonnet high | docs/lanes/2026-11-21-fable-h-kontrakt.md | w toku | D, I, B | Kontrakt v2 zgodny wstecz, plan testów kontraktowych | rekord linii | Scalić uwagi D, I, B |

### Rejestr kosztów Fable

| Data | Pozycja | Zgoda J | Wydano | Uwagi |
|---|---|---|---|---|
| 21 XI | OpenRouter, eksperyment porównawczy oceny reklam | do 10 USD łącznie (21 XI, potwierdzone ponownie przez J) | 0,0417 USD łącznie: 0,0086 USD za 32 wywołania Qwen3.5-9B i 0,0331 USD za 30 wywołań Qwen3.5-27B. Eksperyment zamknięty. Licznik klucza rośnie także bez naszych wywołań, więc miarą jest koszt z odpowiedzi dostawcy. | Klucz działa od 19:00 UTC. Limit na kluczu to 100 USD, zużycie startowe 18,525 USD, więc budżetu 10 USD pilnuje Fable przez odczyt zużycia przed i po każdej turze. Pierwsza tura D: najwyżej 0,50 USD i 30 wywołań. Produkt i demo pozostają lokalne. |
| 21 XI | YouTube Data API v3 | bezpłatne, klucz po stronie J | 0 | Limit 10 000 jednostek dziennie. |

### Decyzje produktowe J z 21 XI

- System bada całą treść filmu przez opis i transkrypcję. Transkrypcja wystarcza do skierowania.
- Podejrzenie nieoznaczonej współpracy trafia do sprawdzenia, także gdy nie da się go rozstrzygnąć. Wcześniej system szuka oznaczenia w mowie i w kadrach z wybranych momentów.
- Sama opinia twórcy bez relacji z firmą pozostaje poza kolejką.
- Karta skierowania zawiera krótkie wypunktowane uzasadnienie i momenty filmu ze znacznikami czasu.
- Reasoning agentów domyślnie medium. Modele do oceny mają dać się hostować lokalnie.

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
