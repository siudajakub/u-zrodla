# Zbiór Q v1 · zamrożone kampanie i oceny agentów

Zamrożono 21 listopada 2026 o 18:43 UTC według [protokołu 1.0](../PROTOKOL.md), przed strojeniem reguł D, promptu Qwen i progu. Skróty plików są w [FREEZE.json](../FREEZE.json). Zbiór zawiera wyłącznie rzeczywiste, publiczne materiały dostępne w repozytorium. Materiały syntetyczne zostają w regresji ([inwentarz](../INWENTARZ.md)).

**To zbiór strojenia, nie odłożony test.** Zespół widział wszystkie 17 materiałów przy budowie reguł. Zamknięty test liczy dziś 0 kampanii. Etykiety to **oceny agentów**, nie wzorzec ekspercki.

| Plik | Zawartość |
|---|---|
| `materialy.json` | Treść 17 materiałów w dostępnym zakresie, pokrycie i neutralny kontekst rejestrowy, bez predykcji. To wejście ślepego odczytu |
| `kampanie.json` | 15 jednostek niezależnych: 6 kampanii reklamowych (5 firm inwestycyjnych i 1 wydarzenie spoza zakresu) oraz 9 publikacji bez reklamy firmy |
| `oceny-agentow.jsonl` | Oceny surowe A i B z cytatem, uzasadnieniem i kontrargumentem |
| `etykiety-agentow.jsonl` | Etykiety końcowe (`referenceKind: agent`, `split: tuning`) |
| `predykcje-reguly-1.2.jsonl` | Rekord przebiegu i wyniki obecnych reguł na ścieżce replay produktu |
| `wynik-reguly-1.2.json` | Pełny raport `tools/eval_validation.py` |
| `predykcje-szablon-reguly-qwen.jsonl` | Pusty szablon rekordu przebiegu dla wariantu reguły + Qwen3.5-9B. Bez predykcji, bo modelu nie uruchomiono |

## Oceniający

- **A:** agent G, `claude-opus-5-5`. Ocena nie jest ślepa (`blindToPrediction: false`), bo wcześniej widział wyniki reguł w rekordzie linii D. Zapisał swoje decyzje przed odczytem ocen B.
- **B:** osobny subagent, `claude-sonnet-5-5`. Ocena ślepa. Otrzymał wyłącznie przetasowane pakiety z `materialy.json` bez wyników, kolejki i ścieżki odkrycia. Zadeklarował, że nie otwierał innych plików.
- Zgodność: 17/17, kappa 1,000. Zgodność dwóch modeli nie zastępuje eksperta i może wynikać ze wspólnych założeń.

Etykieta `yt-partner` (youtube:xtMqKkFO-0M) w historycznym `fixtures/labeled/calibration.json` brzmi `expected: true`. Tutaj oba filmy DETERMINACJA × XTB mają klasę `rejestr` (przesłanka = false) i tworzą jedną kampanię. Historycznego pliku nie zmieniano.

## Obecne reguły na zbiorze strojenia

Wariant: `investwatch-rules-pl-1.2` (M1, M3) i `investwatch-m2-rendered-1` (M2), commit 491094d, ścieżka `discover('replay')` + archiwum M2 + `demo_captures`, bez modelu E5. Mianowniki: 17 materiałów, w tym 1 `nieustalone` (FinanceWell), co daje 16 w macierzy. Zbiór obejmuje 14 jednostek niezależnych w macierzy, 2 pozytywy (obie kampanie XTB, M2:3) oraz 5 prawidłowych reklam w 3 kampaniach.

| Próg | TP | FP | TN | FN | Precyzja [95% Wilson] | Pełność [95% Wilson] | Koszt 2×FN+FP | Kampanie skierowane | Prawidłowe reklamy w kolejce |
|---|---|---|---|---|---|---|---|---|---|
| 30 | 1 | 4 | 10 | 1 | 0,200 [0,036; 0,625] | 0,500 [0,095; 0,905] | 6 | 3 | 4/5 |
| 60 | 1 | 2 | 12 | 1 | 0,333 [0,061; 0,792] | 0,500 [0,095; 0,905] | 4 | 2 | 2/5 |
| 80 | 0 | 2 | 12 | 2 | 0,000 [0; 0,658] | 0,000 [0; 0,658] | 6 | 1 | 2/5 |

Per moduł przy progu 60: M1 n=10, TP 0, FP 2, FN 0. Pełność nie ma podstaw do obliczenia, bo brak pozytywów. M2 n=3, TP 1, FP 0, FN 1. M3 n=2 w macierzy i 1 `nieustalone`, bez skierowań. Wstrzymanych: 0. Poziom kampanii przy progu 60: TP 1, FP 1, TN 11, FN 1.

Fałszywe alarmy:

- Progi 30/60/80: youtube:xtMqKkFO-0M i youtube:04mmNbAlHFo (wynik 94), cytat „Partnerem odcinka jest XTB”. Jawna współpraca bez odrębnej przesłanki to jedna kampania z dwoma materiałami.
- Tylko próg 30: web:bossa.pl/oferta/doradztwo i public-bos-profil (wynik 58), cytat „Klienci usługi otrzymują wyselekcjonowaną listę papierów wartościowych składających się na portfel rekomendowany odpowiedni dla profilu inwestycyjnego Klienta.” Oferta doradztwa podmiotu z kodem zakresu 5 w datowanym wykazie KNF.

Przeoczenia:

- Progi 30/60/80: web:www.xtb.com/pl/akcje (wynik 20), cytat „Rozszerz swoje źródła dochodu o dywidendy wypłacane przez spółki w które zainwestowałeś.” W wyciągu jedyna informacja o ryzyku dotyczy CFD. Pomiar M2 nie potwierdził twierdzenia o zysku w zweryfikowanych fragmentach, choć dla ETF potwierdził identyczne zdanie.
- Próg 80: dom-xtb-etf (wynik 60).

## Czego brakuje do bramki

Bramka wymaga precyzji ≥ 90% przy ≥ 20 skierowaniach z różnych kampanii w odłożonym teście z wzorcem eksperckim. Dziś test liczy 0 kampanii. Pozytywnych kampanii w całych danych są 2, obie od jednego reklamodawcy i obie tylko w ocenach agentów. Potrzeba co najmniej 20 nowych skierowanych kampanii zaobserwowanych po `T_cut`, z czego co najmniej 18 trafnych, oraz dwóch niezależnych ekspertów i losowej próby co najmniej 50 nieskierowanych materiałów na moduł. Przy realnej pełności poniżej 1 trzeba zebrać więcej niż 18 pozytywnych kampanii. Tych wyników nie wolno traktować jako walidacji. Pokazują tylko, że obecna kolejka kieruje jawną współpracę i pomija twierdzenie o dochodzie z akcji.

## Powtórzenie

```sh
python3 tools/eval_validation.py --labels fixtures/validation/q-v1/etykiety-agentow.jsonl \
  --predictions fixtures/validation/q-v1/predykcje-reguly-1.2.jsonl --thresholds 30,60,80 \
  --gate-threshold 60 --split tuning --ratings fixtures/validation/q-v1/oceny-agentow.jsonl
```

Porównanie z wariantem modelowym albo z inną kwantyzacją: dodaj `--compare plik.jsonl`. Plik musi zawierać rekord przebiegu z polami z §11 protokołu.
