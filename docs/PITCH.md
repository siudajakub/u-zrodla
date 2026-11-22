# InvestWatch · pitch i film dla jury UKNF

InvestWatch kieruje do analityka sprawy z dowodem. W filmie może to być konkretna sekunda, na stronie reklamy pozycja ostrzeżenia, a w ofercie doradczej cytat i wpis w wykazie. Analityk wybiera działanie, sprawdza propozycję uzasadnienia i zatwierdza decyzję. Potem może otworzyć tę samą sprawę w kolejce docelowej.

## Film do 120 sekund

Przygotuj pulpit na datowanej bazie i nagraj ujęcia w 1440 px. Widok mobilny nagraj w 390 px. Pierwsze ujęcie pokazuje nazwę InvestWatch i liczniki zakładek **Do sprawdzenia 17** oraz **Rejestr reklam 274**. Łączną liczbę **1 922 materiały** mówi lektor. [Ujęcie kolejki](../tests/ui/screens/2026-11-22-final-workflow/1440-kolejka.png) · [Kliknięcia](hackathon/demo.md)

| Czas | Ujęcie | Tekst lektora |
| --- | --- | --- |
| 0:00–0:14 | 1. Pulpit z licznikami zakładek **Do sprawdzenia 17** i **Rejestr reklam 274**. Wyszukaj „ForexMind” i otwórz kartę. | „W datowanym pokazie InvestWatch jest tysiąc dziewięćset dwadzieścia dwa materiały. Analityk ma siedemnaście spraw do sprawdzenia. Każda prowadzi do dowodu i adresu źródła.” |
| 0:14–0:39 | 2. ForexMind, skrócony link, kod i znacznik 0:15. | „Ten film znaleźliśmy przez oficjalne API YouTube. Przy XTB są link i kod twórcy. System sprawdza opis, flagę platformy i transkrypcję. Kadry są do obejrzenia. W piętnastej sekundzie twórca odsyła do specjalnych ofert. Klik otwiera ten fragment.” |
| 0:39–0:54 | 3. Rejestr reklam i karta Comparic z momentem 10:14. | „W filmie Comparic też jest kod. Jednak w dziesiątej minucie twórca mówi, że XTB jest partnerem odcinka. Ten fragment wyjaśnia podejrzenie i przenosi materiał do rejestru reklam.” |
| 0:54–1:10 | 4. ETF XTB. Pokaż dowód w widoku telefonu. | „Na stronie ETF widać informację o dochodzie z dywidend. System mierzy, gdzie jest ostrzeżenie o ryzyku ETF. Ostrzeżenie o kontraktach CFD opisuje inny produkt.” |
| 1:10–1:24 | 5. Oferta rdmwm.pl z cytatem i statusem operatora. | „W ofercie doradczej strona opisuje dobór proporcji między akcjami i obligacjami na podstawie danych klienta. Operator pozostaje do ustalenia.” |
| 1:24–1:39 | 6. Kalibracja M2, zmiana progu 30 → 50. | „Na próbie dwudziestu pięciu stron zmiana progu zwiększa liczbę przeoczeń z trzech do pięciu. Etykiety nadał agent. Kolejny krok to walidacja ekspercka.” |
| 1:39–2:00 | 7. Wróć do ForexMind. Kliknij **Przekaż do kontroli**, pokaż szkic i dopisz, co należy zweryfikować. Kliknij **Zatwierdź i zapisz decyzję**, po czym **Otwórz w kontroli**. | „Analityk wybiera dalszy krok. InvestWatch przygotowuje edytowalny szkic z dowodów. Po zatwierdzeniu sprawa trafia do kontroli, a uzasadnienie zostaje w historii. Z tej kolejki zespół zapisze wynik albo wróci do sprawdzenia.” |

## Pitch na 3 minuty

Pierwsze 2 minuty poprowadź według [scenariusza](hackathon/demo.md). Pozostałą minutę wykorzystaj na trzy zdania z ekranem źródeł i dwa slajdy.

- **Źródła.** „YouTube zbieramy oficjalnym API, z TikToka czytamy publiczne osadzenia, a strony firm mierzymy w Chromium. Facebook i Instagram pokazujemy z datowanej próbki zewnętrznej. Import działa dziś, a oficjalny odczyt Meta wymaga tokenu.”
- **Technologia.** „Web, API i worker działają lokalnie. Harmonogram ma osobną usługę dla trybu live, a lokalna Ollama jest opcjonalna. Kolejka wznawia zadania po awarii, a przy zapisie decyzji API sprawdza rewizję. Pokaz korzysta z zapisu i nie wywołuje płatnego API.”
- **Proces.** „Agenci pracowali według kontraktów i oddzielnych zakresów. Niezależni sędziowie próbowali podważyć wnioski. Tak znaleźliśmy między innymi fałszywe alarmy na jawnych współpracach i za słabe pokrycie odkrywania kanałów.” [Proces w repo](PROCES-AI.md)

## Pitch w 60 sekund

„Pokażę sprawę od filmu do decyzji. W opisie są link i kod XTB. W piętnastej sekundzie twórca odsyła do ofert. W innym filmie podobne podejrzenie wyjaśnia mowa, bo twórca nazywa XTB partnerem odcinka. Drugi moduł mierzy położenie ostrzeżenia przy informacji o zysku. Trzeci wskazuje cytat o spersonalizowanej ofercie i dane operatora. Analityk wybiera dalsze działanie, poprawia szkic i zatwierdza decyzję. Sprawa trafia do odpowiedniej kolejki z uzasadnieniem i historią.”

## Punkty do rozmowy z jury

| Kryterium | Dowód na pokazie |
| --- | --- |
| Technologia i gotowość | Przejście od cytatu i wersji materiału do przyjęcia uzasadnienia, zmiany kolejki i dalszego działania. Przy dłuższej prezentacji pokaż aktualizację w drugiej karcie. |
| Proces z asystentami AI | Kontrakt przed implementacją, bramki, ślepe etykiety tam, gdzie się udały, i jawny zapis odstępstw. |
| Architektura | Wspólny adapter zbierania, kolejka Huey z dzierżawą, API i pulpit rozdzielone. SQLite i magazyn na dysku obsługują pojedyncze stanowisko. |
| Zgodność | Brief wymaga zmiany statusu i powiadomień. Pokaz obejmuje obie funkcje, a także trzy moduły, znacznik dowodu i kalibrację M2. |
| Atrakcyjność | Przykład Comparic. Film o podobnym opisie zmienia trasę dzięki wypowiedzi w 10:14. |

Przekazanie do kontroli zmienia kolejkę wewnątrz InvestWatch. Pokaz tego obiegu dostarcza dowód gotowości pulpitu i działania zmiany statusu według briefu. Trafność wykrywania dalej oceniamy na zbiorach z opisanymi etykietami i liczebnością. [Kolejki i pytania jury](hackathon/demo.md#gdzie-trafia-sprawa) · [Brief UKNF](zrodla-uknf/BRIEF.md#strona-2)

Przy pytaniach o trafność podaj mianowniki. M1 to próba strojenia 26 materiałów, 20 kampanii i trzy pozytywne kampanie jednego reklamodawcy. M2 to 25 stron z 11 firm. M3 to 31 materiałów i jeden rzeczywisty przypadek skierowany. Przy pytaniach o AI powiedz, że E5 rozpoznaje rodzaj materiału, drugi głos jest pomocniczy, a reguły kierują sprawy do człowieka. [Wynik M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md) · [Próba M2](lanes/2026-11-21-fable-e-m2.md) · [Próba M3](lanes/2026-11-21-fable-f-m3.md) · [Pomiar AI](lanes/2026-11-21-fable-ai-inferencja.md) · [PDF](../presentation/InvestWatch.pdf)
