# Niezależna ocena działającego demo

**SOL 81/100, TERRA 70/100.** Oba modele pracowały niezależnie na odizolowanym API działającej wersji z odciskiem produktu `b572eda8b83ab0a69e174ee46df0d885c301581fe769c1fdd679537d3190fbb8`. Oficjalna skala UKNF wynosi 0–10. Poniższa tabela pokazuje wewnętrzne punkty po zastosowaniu wag. [Kryteria, strona 4](zrodla-uknf/BRIEF.md)

| Kryterium | Maks. | SOL | TERRA |
|---|---:|---:|---:|
| Technologia i gotowość demo | 30 | 25 | 21 |
| Innowacyjność procesu z asystentami AI | 20 | 18 | 16 |
| Architektura | 20 | 16 | 14 |
| Zgodność z tematyką i specyfikacją | 20 | 14 | 12 |
| Atrakcyjność | 10 | 8 | 7 |

SOL (GPT-6.2 SOL, high) odczytał 20 spraw z gotowym E5, potwierdził integralność 18 par obraz–DOM, zmianę w źródłach BOŚ, flagę M1 z cytatem i stan kryterium 9 po poprawce. Wziął pod uwagę [raport trzech czystych startów](../tests/offline/proof-zip-2026-11-21.json) oraz ujawnione i poprawione regresje.

TERRA (GPT-6.1 TERRA, high) sprawdziła punkty API, źródła M1 i M3, zakres 5 i dwa kryteria M2. Niższą ocenę uzasadniła małą próbą, ograniczeniem zakresu źródeł oraz brakiem rzeczywistego potwierdzenia nieuprawnionej usługi. Oba modele obejrzały zrzuty tego samego pakietu JS. Sędziowie nie wykonywali samodzielnie interaktywnego scenariusza Chromium ani trzech uruchomień Compose. Wyniki wykonawców są w [raporcie demo](DEMO-ODBIOR.md).

Przegląd doprowadził do czterech konkretnych korekt: kryterium 9 przestało cytować cudzy produkt, źródła BOŚ zachowują stary pusty i nowy udany odczyt, jawne deklaracje M1 trafiają do filtra przeglądu, a suwak objaśnia cel historycznych etykiet. Nadal brakuje walidacji eksperckiej na niezależnych, nowych kampaniach. Punktów za nią nie doliczamy.

## Wcześniejsze wyniki

Wewnętrzny panel wersji bazowej eaa9c10 przyznał 77/100 (SOL) i 77/100 (TERRA). W kolejności technologia, proces AI, architektura, zgodność i atrakcyjność wyniki wyniosły odpowiednio 24/18/15/12/8 i 24/17/15/13/8. Sędziowie sprawdzali działające API i zapisane próby demo. Wyniki odnoszą się do tej wersji.

UKNF ocenia prezentowaną wersję w skali 0–10 z wagami 30/20/20/20/10 procent. Wewnętrzne sumy na 100 stanowią wygodną prezentację ważonej skali. Dawne wyniki 91,3 i wcześniejsze rundy dotyczą **planów**. Odbiór po zmianie produktu wymaga nowej próby. [Brief, sekcja 8](zrodla-uknf/BRIEF.md) · [Macierz odbioru](ODBIOR-UKNF.md)

Historyczne oceny planów oraz ich uzasadnienia zachowano w [archiwum](archiwum/kontekst-przed-rewizja-uknf.tar.gz), w docs/JUDGING.md.
