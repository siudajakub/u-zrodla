# Podział pracy InvestWatch

Kapitan przypisuje jednego właściciela do jednej linii. Tablica opisuje następny etap budowy. Stan wykonania zbierają rekordy sesji i rzeczywiste testy. Przy starcie odczytaj dostępne linie poleceniem `python3 tools/hack_join.py --list`.

## Available Work

| Slug | Outcome / acceptance | Claim | Contract / dependency | Priority | State |
| --- | --- | --- | --- | --- | --- |
| core-cases | Skan ma trwałe ID, decyzja i alert przeżywają restart, równoległa edycja zwraca 409 | api/, compose.yaml, migrations/ | Scan, Finding, Case | P0 | PAUSED |
| source-adapters | Jeden kontrakt łączy monitor z kolejką, importem materiałów firm i odkrywaniem stron ofert PL. Powtórzenie nie dubluje sprawy | collectors/, fixtures/raw/ | Scan, Capture | P0 | PAUSED |
| analysis-evidence | M1, 19 wierszy M2 i M3 zwracają cytaty lub jawne braki danych. Lokalny model porównany z regułami | analysis/, fixtures/labeled/ | Capture, Finding | P0 | PAUSED |
| analyst-desk | Operator przechodzi od kolejki do dowodu, umowy i zmiany progu. Odświeżenie zachowuje decyzję | web/, tests/ui/ | Finding, Case, Calibration | P0 | PAUSED |

## Active Lanes

Cztery linie dostarczyły zakres demo, a lokalne commity zostały scalone. Rekordy i wyniki są w docs/lanes oraz w [odbiorze](docs/DEMO-ODBIOR.md). Stan PAUSED blokuje ponowne przydzielenie zamkniętej pracy. Dalszy zakres kapitan tworzy osobno.

| Linia | Właściciel | Gałąź | Stan |
|---|---|---|---|
| core-cases | kapitan | hack/captain/core-cases | INTEGRATED |
| source-adapters | SOL | hack/sol/source-adapters | INTEGRATED |
| analysis-evidence | ASTRA | hack/astra/analysis-evidence | INTEGRATED |
| analyst-desk | TERA | hack/terra/analyst-desk | INTEGRATED |

## Merge Train

Kapitan integruje najpierw API i kontrakt, potem po jednym konsumencie. Każda linia przedstawia wynik próby pozytywnej i błędnej, odtworzonej przez innego agenta. Kryteria odbioru są w [planie](docs/PLAN-REALIZACJI.md).

## Broadcasts

Wykaz ESMA pobrany w sondzie zawiera 26 wpisów CSP. Zakres zezwolenia na doradztwo i prawo świadczenia tej usługi w Polsce wymagają odrębnego potwierdzenia. Tę uwagę stosują linie source-adapters i analysis-evidence.
