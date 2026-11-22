# InvestWatch · monitoring promocji, ryzyka i ofert doradczych

## Opis do zgłoszenia

InvestWatch pomaga analitykowi UKNF znaleźć w sieci materiały wymagające kontroli. Kolektor wyszukuje polskie kanały YouTube przez oficjalne API, czyta publiczne osadzenia wybranych profili TikTok i zbiera strony z ofertami. System sprawdza opis, oznaczenie platformy i dostępną transkrypcję. Wybrane kadry udostępnia do obejrzenia. Jawna współpraca trafia do rejestru reklam z nazwą firmy, twórcą i adresem publikacji. W karcie podejrzenia analityk widzi cytat, znacznik czasu i zakres sprawdzonych danych. Moduł M2 sprawdza 19 kryteriów UKNF na stronach firm, m.in. czy ostrzeżenie właściwego produktu towarzyszy informacji o zysku. Moduł M3 wskazuje przesłanki spersonalizowanego doradztwa i sprawdza operatora oraz zakres zezwolenia w datowanych wykazach. Po wyborze działania system wstawia edytowalny szkic uzasadnienia. Urzędnik zatwierdza decyzję i kieruje sprawę do kontroli, uzupełnienia albo zakończenia. Zapis trafia do historii, a analityk może pobrać raport CSV. Stanowisko odtwarza datowany pokaz bez płatnych wywołań API. Facebook i Instagram są w nim reprezentowane przez próbkę zewnętrzną. Oficjalny odczyt Meta wymaga tokenu.

## Wyróżnik

- **Cytat może zmienić decyzję.** W filmie Comparic link i kod w opisie wyglądają na nieujawnioną współpracę. Mowa wskazuje partnera odcinka w 10:14, więc publikacja trafia do rejestru.
- **Dowód odpowiada konkretnej sprawie.** Film można otworzyć od właściwej sekundy. Dla strony firmy karta zachowuje zrzut ekranu i pomiar. Dla oferty doradczej rozdziela cytaty o usłudze od ustalenia operatora i jego uprawnień.
- **Analityk widzi pokrycie i pochodzenie.** Raport podaje źródło i ograniczenia odczytu. Panel kalibracji pokazuje liczebność oraz pochodzenie etykiet.

## Stan względem briefu

Datowane odtworzenie obejmuje 1 922 materiały, 274 wpisy w rejestrze reklam i 17 spraw do sprawdzenia, w tym 7 M1, 9 M2 i 1 M3. W siedmiu sprawach M1 występuje pięć par twórca–reklamodawca i dwie marki, XTB oraz eToro. [Liczniki stanowiska](docs/hackathon/demo.md)

| Zakres | Dowód działania | Ograniczenie |
| --- | --- | --- |
| YouTube i TikTok | Odkrywanie i monitoring YouTube przez Data API v3. Stan pokazu ma 1 307 filmów YouTube i 64 posty TikToka. | Pełna transkrypcja jest dostępna dla 23 z 1 307 filmów w tej bazie. Próba Y znalazła 3 z 5 największych kanałów. Z TikToka w pokazie mamy podpisy. |
| Facebook i Instagram | W odtworzeniu jest 494 unikalnych materiałów na tych platformach. Jest import zapisanej strony i adapter Meta Ad Library. | Dane odtworzeniowe korzystają z datowanej próbki zewnętrznej. Bieżący odczyt z oficjalnego API czeka na token. |
| M2 | Próba rynkowa objęła 25 stron 11 firm, w tym trzy oddziały zagraniczne. Jest pomiar ostrzeżeń na komputerze i telefonie. | Etykiety są ocenami agenta. Wiersz 2 jest obserwacją bez wpływu na wynik, a tablet ma dowód w starszej, mniejszej próbie. |
| M3 | 29 domen, 12 datowanych wykazów, w tym jedna rynkowa przesłanka do sprawdzenia na rdmwm.pl. BOŚ stanowi kontrolę firmy z uprawnieniem. | Operator rdmwm.pl pozostaje nieustalony. Odkrywanie rynkowe korzystało z przygotowanych wyników wyszukiwania. |
| Analiza i decyzje | Reguły z cytatem i lokalizatorem, pomocniczy klasyfikator E5, kalibracja wszystkich modułów. Decyzja urzędnika ma edytowalne uzasadnienie, sprawdzenie rewizji, historię i kolejkę dalszej pracy. | Wyniki trafności mają ograniczone próby i etykiety agentów. Model opisuje materiał lub daje drugi głos. Urzędnik zatwierdza zapis. |

[Brief i załączniki](docs/zrodla-uknf/README.md) · [Odbiór](docs/lanes/2026-11-22-odbior-finalny.md) · [Prezentacja PDF](presentation/InvestWatch.pdf) · [Quick Start](README.md) · [Scenariusz](docs/hackathon/demo.md)
