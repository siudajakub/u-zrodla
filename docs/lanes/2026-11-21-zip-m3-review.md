# Linia m3-review

- Owner: TERRA · GPT-6.1 TERRA, high
- Branch: hack/terra/m3-review
- Worktree: .worktrees/m3-wave
- State: READY
- Updated: 2026-11-21 UTC

## Acceptance

Odkryć pełną ofertę poprzez katalog, wskazać wypowiedź modelem E5 i odróżnić charakter usługi od statusu zezwolenia.

## Claim

- collectors/sites.py, analiza i walidacja M3, sugestia M1, trasy spraw WWW

## Contracts And Dependencies

Producent Capture/Finding i odbiorca API/pulpit uzgodnili [kontrakt](../hackathon/contracts.md). Każdy wynik pokazuje źródło, wersję i zakres obserwacji.

## Current State

Kolektor odnalazł ofertę BOŚ i edukację z dwóch indeksów. Wpis, operator i zakres mają daty oraz źródła. M1 kieruje do przeglądu jawną deklarację z cytatem. Kod przeniesiony do roboczej integracji bez commita.

## Next Step

[Plan funkcji](../PLAN-REALIZACJI.md) i [warunki dalszego odbioru](../ODBIOR-UKNF.md).

## Verification

Na pełnej ofercie E5 wskazał kupno i sprzedaż. Na edukacji sama lista instrumentów nie wystarczyła do końcowej flagi. Ścieżka HTTP dla ID z ukośnikiem obsłużyła wersję i konflikt decyzji. `python3 tests/offline/verify.py --root "$PWD"` na zintegrowanych plikach zakończył trzy przebiegi z 20 sprawami i 20 wynikami E5. Odcisk oraz wyniki zawiera [raport](../../tests/offline/proof-zip-2026-11-21.json).

## Fallback / Cut

Przy niedostępności źródła operator otwiera datowane odtworzenie. Gdy brakuje odpowiedniej modalności lub identyfikacji, wynik wymaga wyjaśnienia.

## Handoff

Przyjęcie robocze na odcisku b572eda8 po poprawkach z [niezależnego przeglądu](../JUDGING.md). Bramka commitowa pozostaje do wykonania po decyzji J.
