# InvestWatch: wykrywanie nieoznaczonej promocji, ryzyka w reklamie i nieuprawnionego doradztwa

## Opis do zgłoszenia

InvestWatch pomaga analitykowi UKNF znaleźć w sieci materiały, które wymagają kontroli, i pokazuje, dlaczego. System sam odkrywa polskojęzyczne kanały YouTube i profile TikTok, odczytuje opis, mowę i kadry filmu, a następnie oddziela jawną współpracę od nieoznaczonej. Jawna reklama trafia do rejestru reklam z firmą powiązaną z wykazami KNF. Do przeglądu trafia tylko film z dowodem relacji handlowej, w którym nie znaleziono oznaczenia w opisie, mowie ani kadrach. Każda flaga ma cytat, link do sekundy nagrania, niewinne wyjaśnienie i zakres tego, czego nie zbadano. Dla stron firm (M2) system ocenia 19 kryteriów UKNF na zrzutach z komputera i telefonu. Dla ofert doradczych (M3) sprawdza personalizację, instrument i czynność, a potem zakres zezwolenia w wykazach KNF. Analityk zmienia próg na zbiorze etykiet i od razu widzi zmianę liczby fałszywych alarmów i przeoczeń. Decyzje mają historię, a raport eksportuje się do CSV. Stanowisko działa lokalnie, na regułach i otwartym modelu E5, bez płatnych API. Pokaz korzysta z datowanego replayu, a tryb live skanuje co 4 godziny.

## Wyróżnik

1. **Rejestr oddzielony od alarmu.** Jawna współpraca nie generuje alarmu. Kolejka zawiera tylko przesłanki, czyli nieoznaczoną współpracę, a podejrzenie obala mowa lub kadr (przykład Comparic w [scenariuszu](docs/hackathon/demo.md)).
2. **Dowód, który da się sprawdzić jednym kliknięciem.** Każda flaga ma cytat z lokalizatorem, sekundę filmu albo zrzut strony z odciskiem wersji oraz jawny zakres braków.
3. **Uczciwe granice.** Źródła mają datowany status dostępu. Facebook i Instagram oznaczono `access_blocked`, bez obchodzenia blokad. Trafność podajemy z mianownikami i z zastrzeżeniem, że to oceny agentów. Proces opisuje [PROCES-AI](docs/PROCES-AI.md).

## Stan względem briefu

| Moduł / źródło | Co działa | Ograniczenie |
|---|---|---|
| M1 YouTube | Odkrywanie przez Data API v3, baza 221 polskich kanałów, mowa i kadry. W replayu 4 flagi z momentem dowodu i 269 pozycji rejestru | Próba pokrycia kanałów niezaliczona (3 z 5 największych). Wszystkie 4 flagi dotyczą jednego reklamodawcy. Transkrypcje z publicznych napisów (yt-dlp) wykraczają poza warunki YouTube |
| M1 TikTok | 64 posty z 6 polskich profili znalezionych z odsyłaczy w opisach YouTube, w tym jawne współprace | Sam podpis, bez mowy i kadrów. Data szacowana |
| M1/M2 Facebook, Instagram | Datowana próbka Biblioteki Reklam (22 reklamy) i 6 postów IG. Import zapisanej strony w pulpicie. Adapter Ad Library API gotowy | Automatyczny odczyt zablokowany bez tokenu Meta. Następny krok to Ad Library API albo Meta Content Library |
| M2 strony firm | 19 kryteriów na 25 stronach 11 firm z wykazów KNF, w tym 3 oddziałów zagranicznych, na 1440 i 390 px | W bazie pokazu są 3 strony, karty pozostałych czekają na wpięcie. Etykiety agenta, nie eksperta |
| M3 oferty doradcze | Odkrywanie z wyników wyszukiwania, 4 osie Tematu 3, 12 wykazów KNF. Kontrola uprawnionego (DM BOŚ) | Jedna skierowana sprawa (rdmwm.pl) na 31 materiałów, operator nieustalony. Reguły v2 strojone na tym samym zbiorze |
| Kalibracja i decyzje | Suwak progu z FP, FN i kosztem 2×FN+FP, porównanie wariantów, historia progu, decyzje z rewizją, WebSocket, eksport CSV | Zbiór M1 to 26 materiałów strojenia z etykietami agentów |
| Uruchomienie | `sh ops/demo/start.sh` (Compose) albo `start-local.sh` bez Dockera. Tryb offline po przygotowaniu | Zimny start trwa kilka minut. Nieuruchamiane na macOS |

Źródła liczb: [rekord YouTube](docs/lanes/2026-11-21-fable-b-youtube.md), [social](docs/lanes/2026-11-21-fable-k-social.md), [M2](docs/lanes/2026-11-21-fable-e-m2.md), [M3](docs/lanes/2026-11-21-fable-f-m3.md), [WYNIK-M1](fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md), [WYNIK-Y](fixtures/validation/y-reference/WYNIK-Y-2026-11-21.md). Wymagania: [brief i załączniki](docs/zrodla-uknf/README.md) · [macierz odbioru](docs/ODBIOR-UKNF.md) · [kolejność prac](docs/PLAN-REALIZACJI.md). Pakiet zgłoszenia to tytuł, opis, [PDF](presentation/InvestWatch.pdf), [README](README.md) i repozytorium. Film do 3 minut jest opcjonalny. Status zgłoszenia potwierdza J.
