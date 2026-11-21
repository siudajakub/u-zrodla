# Lane: core-cases

- Owner: captain
- Branch: hack/captain/core-cases

## Acceptance

Jedna logiczna sprawa na dokument. Operator może sprawdzić dowód, zapisać decyzję i otrzymać zmianę statusu. Nieaktualna rewizja daje 409.

## Claim

API, worker, stan SQL, testy integracyjne, uruchomienie Compose. Producent kolektora i silnika pozostają niezależni.

## Contracts And Dependencies

Konsument discover, analyze, transcribe_file, transcribe_excerpt i calibration. Producent stanów, rewizji, zdarzeń oraz odczytu plików multimedialnych z obsługą Range.

## Current State

Działają testy repozytorium przypadków. Weryfikacja przez przeglądarkę i w kontenerach należy do integracji.

## Next Step

Uruchomić jeden worker, wprowadzić replay, zeskanować źródła na żywo i ponownie sprawdzić odtwarzanie po restarcie.

## Verification

Dwa testy SQLite potwierdziły stabilność tożsamości żądania i zachowanie kolejnych wersji A→B→A przy powtórce.

## Fallback / Cut

Worker może pracować bez sieci z ustawieniem INVESTWATCH_DISCOVERY_INTERVAL=0, replay zachowuje dowody ze źródeł i lokalnego ASR.

## Handoff

Przy pierwszej próbie sprawdzić prywatny dostęp workera do monitoringu 0600 oraz rzeczywistą możliwość odtwarzania wycinka według znacznika czasu.
