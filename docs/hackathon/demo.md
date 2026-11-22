# Pokaz dla jury UKNF

Prezentacja zaczyna się od datowanego stanowiska. Sposób przygotowania opisuje [Quick Start](../../README.md). Po podniesieniu serwera otwórz [pulpit](http://127.0.0.1:8769/). Scenopis do nagrania i tekst lektora są w [pitchu](../PITCH.md).

Stan pokazu z 21 XI 2026 zawiera **1 922 materiały, 274 wpisy w rejestrze reklam i 17 spraw do sprawdzenia**. W kolejce jest 7 materiałów twórców, 9 reklam firm i 1 oferta doradztwa. Pełną mowę odczytano w 23 z 1 307 filmów YouTube, a 1 284 mają status oczekiwania na transkrypcję. Rejestr obejmuje wpisy potwierdzone oraz pozycje do potwierdzenia. Liczniki pochodzą z projekcji kolejek i można je odczytać przez `GET /v1/overview?schema=2`.

## Pokaz w 2 minuty

| Czas | Kliknij | Powiedz |
| --- | --- | --- |
| 0:00–0:30 | Pokaż liczniki **Do sprawdzenia 17** i **Rejestr reklam 274**. Wyszukaj „ForexMind”, otwórz **Freedom24 Alternatywy** i pokaż znacznik **0:15** w sekcji **Dowód**. | Stan pokazu obejmuje 1 922 materiały. W opisie ForexMind są skrócony link przy XTB i kod TRADEXTB. W 0:15 twórca odsyła do specjalnych ofert. System w sprawdzonym opisie i mowie nie znalazł oznaczenia. Film trafia do sprawdzenia, a analityk może obejrzeć kadry. |
| 0:30–0:46 | **Rejestr reklam** → karta Comparic z filmem „ARABIA SZYKUJE SIĘ NA WOJNĘ…”. [Skrót na stanowisku](http://127.0.0.1:8769/#register?case=youtube%3ACDk20n4u9Kk) | Comparic też podaje link i kod. W 10:14 twórca nazywa XTB partnerem odcinka. Ta wypowiedź wyjaśnia sygnał z opisu i film trafia do rejestru reklam. |
| 0:46–1:06 | **Do sprawdzenia** → **Filtry** → **Reklamy firm** → ETF XTB. Pokaż cytat o dywidendach i fragment właściwego ostrzeżenia w dowodzie. | System mierzy, gdzie jest ostrzeżenie o ryzyku ETF względem informacji o potencjalnym dochodzie. Na telefonie ostrzeżenie widać po przewinięciu. Ostrzeżenie dotyczące CFD opisuje inny produkt. |
| 1:06–1:20 | **Do sprawdzenia** → **Filtry** → **Oferty doradztwa** → **rdmwm.pl**. Pokaż cytat i pole operatora. | Strona opisuje dobieranie proporcji między akcjami i obligacjami na podstawie danych klienta. Analityk ma cytat o personalizacji. Żeby sprawdzić zakres ewentualnego zezwolenia, musi najpierw ustalić operatora. |
| 1:20–1:38 | **Kalibracja** → **Reklamy firm**. Zmień podgląd progu z 20 na 30 i 50. | Przy progu 20 na 25 stronach jest jeden fałszywy alarm i trzy przeoczenia. Przy 30 alarm znika. Przy 50 pojawiają się dwa kolejne przeoczenia. Oceny wykonał agent. |
| 1:38–2:00 | Wróć do [ForexMind](http://127.0.0.1:8769/#review?case=youtube%3AAqXHkxDzSDI). W sekcji **Podejmij decyzję** kliknij **Przekaż do kontroli**. Dopisz „Sprawdzić oznaczenie współpracy w pełnym obrazie filmu”, kliknij **Zatwierdź i zapisz decyzję**, a potem **Otwórz w kontroli**. | Szkic korzysta z dowodów tej sprawy. Dopisuję, co ma sprawdzić zespół. Po zatwierdzeniu sprawa trafia do wewnętrznej kolejki kontroli, gdzie można zobaczyć uzasadnienie i później zapisać wynik. |

## Gdzie trafia sprawa

| Działanie urzędnika | Kolejka po zatwierdzeniu | Dalsze działanie |
| --- | --- | --- |
| **Przekaż do kontroli** | **Kontrola** | **Zakończ kontrolę** z wynikiem i jego podstawą albo **Wróć do sprawdzenia** z powodem. |
| **Skieruj do uzupełnienia** | **Do uzupełnienia** | **Dane uzupełnione** z opisem i źródłem albo **Wróć do sprawdzenia** z powodem. Sprawa wróci do **Do sprawdzenia**. |
| **Zakończ bez przesłanki** lub **Zakończ z innym uzasadnieniem** | **Zakończone** | W razie nowej informacji użyj **Wróć do sprawdzenia** i podaj powód. |

Karta najpierw pokazuje dostępne działania. Po wyborze wstawia edytowalny szkic na podstawie sprawy. Ustalenia kontroli, otrzymane dane i uzasadnienie zakończenia wpisuje urzędnik. Po zapisie pulpit przechodzi do kolejnej sprawy lub wraca do listy. Komunikat daje skrót do zapisanej sprawy w nowej kolejce, a zakładka **Historia decyzji** pokazuje poprzednie zapisy. Kolejki organizują dalszą pracę zespołu wewnątrz InvestWatch. [Kontrakt API](contracts.md)

## Dodatkowe ujęcia przy 3–5 minutach

- **M2, porównanie.** Otwórz [kartę ETF XTB](http://127.0.0.1:8769/#review?module=M2&case=dom-xtb-etf). W wersji 390 px pokaż wzmiankę o dywidendach i ostrzeżenie dotyczące ETF poza początkowym kadrem. W widoku akcji XTB można sprawdzić ostrzeżenie dotyczące innego produktu. [Dowód i manifest](../zrodla-uknf/KRYTERIA-M2.md#dowód-w-działającym-m2)
- **M3, kontrola.** Pokaż wpis DM BOŚ z zakresem doradztwa, następnie kolizję nazwy FinanceWell. rdmwm.pl ma cytat o doborze proporcji portfela, a dalsza praca wymaga ustalenia operatora. [Próba M3](../lanes/2026-11-21-fable-f-m3.md) · [Kontrole](../archiwum/M3-WERYFIKACJA-2026-11-21.md)
- **Źródła.** Pokaż tabelę platform i pochodzenie odczytu. Facebook i Instagram są obecne dzięki datowanej próbce zewnętrznej i mechanizmowi importu. Odczyt przez oficjalne API Meta wymaga tokenu. [Monitoring](../MONITORING.md)
- **Raport.** W kolejce **Kontrola**, **Do uzupełnienia** albo **Zakończone** kliknij **Raport**. Możesz objąć eksportem wszystkie moduły lub wybrany moduł. CSV podaje etap, decyzję, uzasadnienie, sprawdzoną wersję i adres źródła. [Kontrakt API](contracts.md)
- **Powiadomienie.** Na kopii roboczej otwórz dwie połączone karty pulpitu. Zapisanie decyzji w pierwszej odświeża sprawę w drugiej. Powiadomienie o wysokim ryzyku pojawia się przy zwykłym skanie, gdy analiza zapisze nowe skierowanie.

## Przed pokazem

- Potwierdź dostęp do zaakceptowanej kopii. Zapisz w konsoli wersję, tryb danych i liczniki z `GET /v1/overview?schema=2`.
- Otwórz kartę, kalibrację i PDF, zanim wystartuje zegar. Sprawdź desktop i telefon. Przećwicz zapis decyzji z dwiema otwartymi kartami na kopii roboczej.
- Kliknięcie publicznego odsyłacza **Otwórz od 0:15** wymaga dostępu do YouTube. W trybie offline pokaż znacznik i cytat w karcie.
- Wariant po tunelu wymaga połączenia z devboxem. Wariant lokalny wymaga paczek, a procedura dla Apple Silicon jest w [ops/mac/README.md](../../ops/mac/README.md).
- Gdy pulpit jest niedostępny, pokaż aktualne ujęcia z [prezentacji PDF](../../presentation/InvestWatch.pdf).

## Pytania jury

| Pytanie | Odpowiedź |
| --- | --- |
| Co działa na żywo? | Decyzja, zmiana progu, eksport i WebSocket działają w bieżącej sesji. Dane pokazowe pochodzą z datowanego odtworzenia i pozyskanych wcześniej materiałów. Tryb live ma osobny harmonogram i zależy od dostępu do źródeł. |
| Czy system sam podejmuje decyzję? | System przygotowuje propozycję uzasadnienia z dowodów w karcie. Urzędnik wybiera działanie, edytuje tekst i zatwierdza zapis. Dla zakończenia lub zapisu ustaleń potrzebna jest własna podstawa. |
| Jak zmierzono trafność? | M1 ma 26 materiałów z 20 kampanii w zbiorze strojenia. Przy 60 reguły kwalifikacji dały 4 TP, 0 FP i 0 FN. Trzy pozytywne kampanie dotyczyły jednego reklamodawcy. Osobna próba ośmiu kontroli ujemnych nie dała podstaw do obliczenia precyzji ani pełności. M2 przy 30 na 25 stronach dał 9 TP, 0 FP, 13 TN i 3 FN. M3 obejmował 31 materiałów i jeden pozytyw. Wyniki pochodzą z etykiet agentów. [Próba diagnostyczna M1](../lanes/2026-11-22-proba-kampanii.md) |
| Gdzie jest AI? | Lokalny E5 wspomaga rozpoznawanie typu materiału. W pomiarze na 57 opisach z odłożonych kanałów miał 30 trafień wobec 13 dla słownika. Drugi głos ma walidator dosłownego cytatu. Kwalifikację wyznaczają udokumentowane reguły, a status wpisuje analityk. |
| Skąd pochodzą napisy? | Wyszukiwanie i metadane pochodzą z oficjalnego YouTube Data API. Próby z publicznymi napisami używały osobnej lokalnej ścieżki. We wdrożeniu potrzebne jest uzgodnione źródło transkrypcji, np. ASR z materiału udostępnionego do analizy. |
| Czy pokaz używa płatnego API? | Odtwarzanie działa bez wywołań do płatnych usług. Wcześniejsze pomiary modelu wykonano w OpenRouter, a próbka Meta pochodzi od zewnętrznego dostawcy. |
| Co po hackathonie? | Sprawdzić nowe kampanie z etykietami ekspertów, rozszerzyć uprawniony odczyt źródeł i zmierzyć skalowanie większej liczby kolektorów. [Audyt](../lanes/2026-11-22-odbior-finalny.md) |
