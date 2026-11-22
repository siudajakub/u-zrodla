# InvestWatch · pitch i film dla jury UKNF

InvestWatch skraca drogę od publikacji do sprawdzenia. Analityk dostaje sekundę filmu, pomiar ostrzeżenia na stronie lub cytat z oferty wraz z wynikiem sprawdzenia operatora. Wybiera dalsze działanie, edytuje szkic uzasadnienia i zatwierdza zapis. Sprawę i historię otwiera z kolejki, do której ją skierował.

## Film do 120 sekund

Przygotuj pulpit na datowanej bazie i nagraj ujęcia w 1440 px. Widok mobilny nagraj w 390 px. Pierwsze ujęcie pokazuje nazwę InvestWatch i liczniki zakładek **Do sprawdzenia 17** oraz **Rejestr reklam 274**. Łączną liczbę **1 922 materiały** mówi lektor. [Ujęcie kolejki](../tests/ui/screens/2026-11-22-final-workflow/1440-kolejka.png) · [Kliknięcia](hackathon/demo.md)

| Czas | Ujęcie | Tekst lektora |
| --- | --- | --- |
| 0:00–0:14 | 1. Pulpit z licznikami zakładek **Do sprawdzenia 17** i **Rejestr reklam 274**. Wyszukaj „ForexMind” i otwórz kartę. | „W datowanym pokazie InvestWatch jest tysiąc dziewięćset dwadzieścia dwa materiały. Analityk ma siedemnaście spraw do sprawdzenia. Każda prowadzi do dowodu i adresu źródła.” |
| 0:14–0:39 | 2. ForexMind, skrócony link, kod i znacznik 0:15. | „ForexMind podaje link i kod XTB, a po piętnastu sekundach odsyła do specjalnych ofert. W opisie i transkrypcji system nie znalazł oznaczenia współpracy. Kieruje film do sprawdzenia. Analityk widzi cytat, czas i kadry do obejrzenia.” |
| 0:39–0:54 | 3. Rejestr reklam i karta Comparic z momentem 10:14. | „Comparic też podaje link i kod. W dziesiątej minucie i czternastej sekundzie twórca nazywa XTB partnerem odcinka. Ta wypowiedź wyjaśnia podejrzenie. Film trafia do rejestru reklam.” |
| 0:54–1:10 | 4. ETF XTB. Pokaż dowód w widoku telefonu. | „Na stronie ETF pojawia się informacja o dochodzie z dywidend. InvestWatch wskazuje właściwe ostrzeżenie. Na ekranie telefonu trzeba przewinąć stronę, żeby je zobaczyć.” |
| 1:10–1:24 | 5. Oferta rdmwm.pl z cytatem i statusem operatora. | „Strona opisuje dobór portfela na podstawie danych klienta. System wskazuje ten cytat, a karta pokazuje następne zadanie dla analityka. Trzeba ustalić operatora.” |
| 1:24–1:39 | 6. Kalibracja M2, zmiana progu 30 → 50. | „Na próbie dwudziestu pięciu stron zmiana progu zwiększa liczbę przeoczeń z trzech do pięciu. Etykiety nadał agent. Kolejny krok to walidacja ekspercka.” |
| 1:39–2:00 | 7. Wróć do ForexMind. Kliknij **Przekaż do kontroli**, pokaż szkic i dopisz, co należy zweryfikować. Kliknij **Zatwierdź i zapisz decyzję**, po czym **Otwórz w kontroli**. | „Wybieram kontrolę i dopisuję, co zespół ma sprawdzić w filmie. Zatwierdzam decyzję. Sprawa jest teraz w wewnętrznej kolejce kontroli. Uzasadnienie zostaje w historii, a zespół może później zapisać wynik.” |

## Pitch na 3 minuty

Pierwsze 2 minuty poprowadź według [scenariusza](hackathon/demo.md). Pozostałą minutę wykorzystaj na trzy zdania z ekranem źródeł i dwa slajdy.

- **Źródła.** „YouTube zbieramy oficjalnym API, z TikToka czytamy publiczne osadzenia, a strony firm mierzymy w Chromium. Facebook i Instagram pokazujemy z datowanej próbki zewnętrznej. Import działa dziś, a oficjalny odczyt Meta wymaga tokenu.”
- **Technologia.** „Web, API i worker działają lokalnie. Harmonogram ma osobną usługę dla trybu live, a lokalna Ollama jest opcjonalna. Kolejka wznawia zadania po awarii, a przy zapisie decyzji API sprawdza rewizję. Pokaz korzysta z zapisu i nie wywołuje płatnego API.”
- **Proces.** „Agenci pracowali według kontraktów i oddzielnych zakresów. Niezależni sędziowie próbowali podważyć wnioski. Tak znaleźliśmy między innymi fałszywe alarmy na jawnych współpracach i za słabe pokrycie odkrywania kanałów.” [Proces w repo](PROCES-AI.md)

## Pitch w 60 sekund

„ForexMind i Comparic podają link i kod XTB. ForexMind odsyła do ofert, a w odczytanym opisie i mowie brakuje oznaczenia współpracy. Ten film trafia do sprawdzenia. Comparic nazywa XTB partnerem odcinka, więc film trafia do rejestru reklam. Na stronach firm InvestWatch mierzy położenie właściwego ostrzeżenia przy informacji o potencjalnym zysku. W ofertach doradztwa wskazuje cytat o personalizacji, a analityk może sprawdzić, czy ustalono operatora i zakres uprawnień. Z jednej karty urzędnik przechodzi od dowodu do decyzji. Wybiera działanie, poprawia szkic i zatwierdza zapis. Zespół przejmuje sprawę w odpowiedniej kolejce i ma dostęp do uzasadnienia oraz sprawdzonej wersji.”

## Punkty do rozmowy z jury

| Kryterium | Dowód na pokazie |
| --- | --- |
| Technologia i gotowość | Przejście od cytatu i wersji materiału do przyjęcia uzasadnienia, zmiany kolejki i dalszego działania. Przy dłuższej prezentacji pokaż aktualizację w drugiej karcie. |
| Proces z asystentami AI | Kontrakt przed implementacją, bramki, ślepe etykiety tam, gdzie się udały, i jawny zapis odstępstw. |
| Architektura | Wspólny adapter zbierania, kolejka Huey z dzierżawą, API i pulpit rozdzielone. SQLite i magazyn na dysku obsługują pojedyncze stanowisko. |
| Zgodność | Brief wymaga zmiany statusu i powiadomień. Pokaz obejmuje obie funkcje, a także trzy moduły, znacznik dowodu i kalibrację M2. |
| Atrakcyjność | ForexMind i Comparic. Podobne opisy prowadzą do dwóch kolejek, bo w 10:14 Comparic wskazuje partnera odcinka. |

Przekazanie do kontroli zmienia kolejkę wewnątrz InvestWatch. Pokaz tego obiegu dostarcza dowód gotowości pulpitu i działania zmiany statusu według briefu. Trafność wykrywania dalej oceniamy na zbiorach z opisanymi etykietami i liczebnością. [Kolejki i pytania jury](hackathon/demo.md#gdzie-trafia-sprawa) · [Brief UKNF](zrodla-uknf/BRIEF.md#strona-2)

Przy pytaniach o trafność podaj mianowniki. M1 to 26 materiałów z 20 kampanii w próbie strojenia, w tym trzy pozytywne kampanie jednego reklamodawcy. W osobnej próbie diagnostycznej było osiem kontroli ujemnych i zero skierowań, więc precyzja i pełność są nieobliczalne. M2 to 25 stron z 11 firm. M3 to 31 materiałów i jeden rzeczywisty przypadek skierowany. Przy pytaniach o AI powiedz, że E5 wspomaga rozpoznanie rodzaju materiału, drugi głos jest pomocniczy, a reguły kierują sprawy do człowieka. [Wynik M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md) · [Próba diagnostyczna M1](lanes/2026-11-22-proba-kampanii.md) · [Próba M2](lanes/2026-11-21-fable-e-m2.md) · [Próba M3](lanes/2026-11-21-fable-f-m3.md) · [Pomiar AI](lanes/2026-11-21-fable-ai-inferencja.md) · [PDF](../presentation/InvestWatch.pdf)
