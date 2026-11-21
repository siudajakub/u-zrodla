# Podział pracy InvestWatch

Kapitan przypisuje jednego właściciela do jednej linii. Tablica opisuje następny etap budowy. Stan wykonania zbierają rekordy sesji i rzeczywiste testy. Przy starcie odczytaj dostępne linie poleceniem `python3 tools/hack_join.py --list`.

## Available Work

| Slug | Outcome / acceptance | Claim | Contract / dependency | Priority | State |
| --- | --- | --- | --- | --- | --- |
| core-cases | Skan ma trwałe ID, decyzja i alert przeżywają restart, równoległa edycja zwraca 409 | api/, compose.yaml, migrations/ | Scan, Finding, Case | P0 | AVAILABLE |
| source-adapters | Jeden kontrakt łączy monitor z kolejką, importem materiałów firm i odkrywaniem stron ofert PL. Powtórzenie nie dubluje sprawy | collectors/, fixtures/raw/ | Scan, Capture | P0 | AVAILABLE |
| analysis-evidence | M1, 19 wierszy M2 i M3 zwracają cytaty lub jawne braki danych. Lokalny model porównany z regułami | analysis/, fixtures/labeled/ | Capture, Finding | P0 | AVAILABLE |
| analyst-desk | Operator przechodzi od kolejki do dowodu, umowy i zmiany progu. Odświeżenie zachowuje decyzję | web/, tests/ui/ | Finding, Case, Calibration | P0 | AVAILABLE |

## Active Lanes

Przy przygotowaniu zestawu projekt nie miał początkowego commitu. Operator zakłada pierwsze worktree po ustaleniu bazy Git z J. Polecenie `python3 tools/hack_status.py` pokazuje istniejące linie. Bieżące prace dokumentacyjne i monitoring są opisane w historii sesji.

## Merge Train

Kapitan integruje najpierw API i kontrakt, potem po jednym konsumencie. Każda linia przedstawia wynik próby pozytywnej i błędnej, odtworzonej przez innego agenta. Kryteria odbioru są w [planie](docs/PLAN-REALIZACJI.md).

## Broadcasts

Wykaz ESMA pobrany w sondzie zawiera 26 wpisów CSP. Zakres zezwolenia na doradztwo i prawo świadczenia tej usługi w Polsce wymagają odrębnego potwierdzenia. Tę uwagę stosują linie source-adapters i analysis-evidence.
