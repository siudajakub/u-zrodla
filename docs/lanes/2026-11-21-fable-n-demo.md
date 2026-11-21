# Lane: N · demo, proces AI i prezentacja

- Owner: J
- Branch: hack/integration
- Worktree: główny checkout
- State: ACTIVE
- Updated: 2026-11-21 22:00 UTC
- PR / issue: none yet

## Acceptance

Brief §4, §6 i §8. Kryterium 2 wymaga opisu ustandaryzowanego procesu z asystentami AI. Pakiet formalny obejmuje tytuł, opis i PDF. Jury pyta, gdzie są FB/IG, na czym opiera się trafność i gdzie jest przypadek M3. Wynik obserwowalny: scenariusz pokazu oparty na bazie pokazu, PDF opisujący produkt po zwrocie na YouTube i każda liczba z odsyłaczem do pliku w repo.

## Claim

- `docs/PROCES-AI.md`
- `docs/hackathon/demo.md`
- `HACKATHON.md`
- `presentation/prepare.py`, `presentation/InvestWatch.pdf`
- `docs/lanes/2026-11-21-fable-n-demo.md`

## Contracts And Dependencies

- Produces: brak kontraktu kodu.
- Consumes: API podglądu `127.0.0.1:18801` (tylko GET), rekordy linii, `fixtures/validation/`, `fixtures/labeled/`, zrzuty `tests/ui/screens/2026-11-21-r3/`.
- Shared-file coordination: README.md i docs/ARCHITEKTURA.md należą do innej linii. Slajd architektury i odpowiedź o SQLite odsyłają do docs/ARCHITEKTURA.md, który w chwili zapisu istniał tylko w drzewie roboczym. Odsyłacz zadziała w repo dopiero po commicie tej linii.

## Current State

Model: claude-opus-5-5 (podagent N zlecony przez Fable). Zrobione:
- PROCES-AI.md: role, standardy, bramki, dobór modelu, 10 przypadków błędów z dowodem i sekcja „co nie zadziałało”.
- Scenariusz 2 i 5 minut z kliknięciami i zdaniami, lista kontrolna, wariant awaryjny, 8 trudnych pytań.
- HACKATHON.md: tytuł, opis (163 słowa), wyróżnik, tabela stanu.
- `prepare.py` nie korzysta już z `analysis/` ani z ffmpeg. Generuje 9 slajdów z 3 zrzutami pulpitu. PDF zbudowano.

Kroki scenariusza oznaczone **[po wpięciu]**: para XTB akcje i ETF w M2, Noble IKE, rdmwm.pl. W bazie 18801 o 21:50 UTC M2 miał 3 strony, a M3 dwie sprawy (BOŚ i FinanceWell).

Nie potwierdzono w repo i dlatego pominięto: „92 fałszywe wersje” przy normalizacji czasu. Repo zawiera mechanizm i test, ale nie tę liczbę.

## Next Step

Po wpięciu M2 i M3 do bazy pokazu przejść scenariusz na żywo i zdjąć znaczniki „[po wpięciu]”.

## Verification

- `python3 tools/check_agent_docs.py`: „Hackathon context validation passed.”
- `python3 tools/check_plan_evidence.py`: przechodzi, SHA-256 pakietu 53e5bc3d…
- Skrypt sprawdzający odsyłacze `[..](..)` w czterech dokumentach linii, ścieżki w backtickach, zrzuty w `prepare.py` i 15 hashy commitów: 0 braków.
- `python3 presentation/prepare.py`: 9 stron, 960×540 pt. Strony obejrzane po renderze `pdftoppm`.
- Scenariusza nie przeszedłem w przeglądarce. Odczyty pochodzą z GET na 18801 i ze zrzutów r3.

## Fallback / Cut

Poprzednia wersja PDF i scenariusza jest w historii Git (`git show HEAD~:presentation/prepare.py`). Wycofanie: `git revert` commitów tej linii.

## Handoff

Do przeglądu przez świeżego agenta: zgodność liczb z plikami źródłowymi oraz uczciwość odpowiedzi na trudne pytania (YouTube ToS, trafność). Kontrprzykład do sprawdzenia: czy import pliku `metaadlib-browser-body.txt` dubluje 22 reklamy z próbki.
