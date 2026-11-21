# Linia m2-capture

- Owner: SOL · GPT-6.2 SOL, high
- Branch: hack/sol/m2-capture
- Worktree: .worktrees/m2-wave
- State: READY
- Updated: 2026-11-21 UTC

## Acceptance

Otworzyć twierdzenie o potencjalnym zysku i właściwe ostrzeżenie ETF na źródłowym ekranie komputera i telefonu. Odrzucić CFD i samo 0% prowizji.

## Claim

- collectors/m2_*, analysis/m2_evidence.py, kryteria i zapisy renderów M2

## Contracts And Dependencies

Producent Capture/Finding i odbiorca API/pulpit uzgodnili [kontrakt](../hackathon/contracts.md). Każdy wynik pokazuje źródło, wersję i zakres obserwacji.

## Current State

Kryterium 3 ma pełną parę i właściwą wersję obrazu oraz DOM. Kryterium 9 używa wyłącznie potwierdzonego ostrzeżenia tego produktu. Kod przeniesiony do roboczej integracji bez commita.

## Next Step

[Plan funkcji](../PLAN-REALIZACJI.md) i [warunki dalszego odbioru](../ODBIOR-UKNF.md).

## Verification

Trzy materiały z dwóch firm, 18 stanów Chromium. Test przeciwnej kreacji wykazał 16/8 px, zasłonięcie, rozwinięcie i brak pomiaru dla gradientu. `python3 tests/offline/verify.py --root "$PWD"` na zintegrowanych plikach zakończył trzy przebiegi z 20 sprawami i 20 wynikami E5. Odcisk oraz wyniki zawiera [raport](../../tests/offline/proof-zip-2026-11-21.json).

## Fallback / Cut

Przy niedostępności źródła operator otwiera datowane odtworzenie. Gdy brakuje odpowiedniej modalności lub identyfikacji, wynik wymaga wyjaśnienia.

## Handoff

Przyjęcie robocze na odcisku b572eda8 po poprawkach z [niezależnego przeglądu](../JUDGING.md). Bramka commitowa pozostaje do wykonania po decyzji J.
