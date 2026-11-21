# InvestWatch · arkusz odbioru wersji dla jury

**Stan 21 XI 2026.** „Sonda” potwierdza konkretny odczyt. „Do próby” wymaga wykonania na wersji prezentacyjnej. Właściciele według linii: **K** kapitan/API, **S** kolektory, **A** analiza, **U** interfejs, **J** zgłoszenie i ocena merytoryczna. Odbierający dopisuje wynik, wersję i ścieżkę do dowodu.

| Zakres UKNF | Dziś | Kto | Próba i artefakt wymagany do odbioru |
|---|---|---|---|
| Silnik WWW i social, pobieranie API/parserem, HTML → JSON | Sondy WWW. Dwa działające odczyty YouTube i TikTok | S | Od profilu lub domeny odkryć publikację, zapisać JSON z ID, URL, tekstem i czasem. Powtórzyć odczyt bez duplikatu. Pokazać także awarię źródła. Przy FB/IG podać faktyczny tryb i zakres. |
| Rotacja User-Agent i proxy | Do próby | S | Na kontrolnym serwerze pokazać dwa skonfigurowane nagłówki i dwa uprawnione transporty. Osobno sprawdzić pracę bez puli i prawidłową obsługę 403/429. |
| Kolejka open source i harmonogram | Timer włączony, usługa wywołana ręcznie dwukrotnie. Pierwszy automatyczny termin 21 XI 20:10 CET | K, S | Zarejestrować faktyczne wyzwolenie harmonogramu, przejęcie zadania i ponowienie po restarcie. Jedna logiczna publikacja. |
| SQL na metadane i trwała treść | SQLite z publicznymi opisami 50 publikacji, pliki PNG/DOM | K | Otworzyć zapisaną treść po restarcie, zweryfikować hash, dwie wersje zmienionego materiału i zgodność metadanych. |
| Python AI, preprocessing, inferencja i scoring | Do próby | A | HTML → oczyszczony, znormalizowany tekst → deduplikacja → tokeny i embedding → lokalny model → wynik i kategoria. Zapisać wersję wag, reguł i wynik dla parafrazy oraz negacji. |
| M1, M2, M3 i wspólny agregator | Sondy relacji, stron i rejestrów | A, S | M1: okresowy raport firma–autor–treść–URL, przypadek transgraniczny po polsku. M2: reklama własna uprawnionej firmy, flaga z dowodem. M3: podmiot–oferta–URL, personalizacja i datowany zakres zezwolenia. Otworzyć trzy wyniki ze wspólnej listy. |
| Dashboard, propsy, stabilność, status, alert | Do próby | U, K | W React sprawdzić propsy, cztery filtry (czas/źródło/ryzyko/moduł) i trend. Zmienić status, odświeżyć, w drugim oknie odebrać WebSocket wysokiego ryzyka, rozłączyć i wznowić. Zachować log konsoli i sieci, wyjaśnić błędy i sprawdzić brak sekretów. Biblioteka UI jest opcjonalna. |
| Trafność AI i panel kalibracji | Do próby | A, J, U | Te same ręczne etykiety odłożone całymi kampaniami, dwa progi, TP/FP/FN/TN, precision/recall i konkretne sprawy zmieniające kwalifikację. Porównać reguły z modelem osobno dla M1–M3. |
| Modułowość, Docker/Compose, on-prem, otwarty stos | Dostęp do Docker Engine 29.1.3 na hoście potwierdzony, Compose CLI 2.40.3 | K | Na czystym stanowisku jedną komendą uruchomić frontend, backend i AI oraz SQL. Odtworzyć materiał offline. Spis wersji i licencji zależności/modelu, bez płatnego API na ścieżce produktu. |
| Bezpieczeństwo zależności i sekretów | Do próby | K | Uruchomić npm audit i pip-audit na zablokowanych wersjach, zapisać wyniki, naprawy i ponowny skan. Zweryfikować izolację sekretów w lokalnym .env i brak wartości w Git, obrazach, logach i przeglądarce. |
| Proces z AI, atrakcyjność i formalności | Instrukcje, opisany przegląd bramki | K, J | Wskazać wymaganie, wkład asystenta, niezależną recenzję i test poprawki na wersji demo. Odtworzyć decyzję analityka w 2 min. Otworzyć repo, README (Quick Start, sprzęt, konfiguracja), szczegółowy opis z tytułem i PDF. Film opcjonalny do 3 min. HackTribe: 21 XI 20:00 szkic, 22 XI 11:00 finał, czas polski. |

**M2 · 19 pozycji z załącznika.** A i U pokazują obserwację i jej źródło. J rozstrzyga znaczenie dowodu. Dziś są sondy geometrii. Każda deklarowana automatyzacja wymaga pary kontrolnej na tym samym typie materiału.

| ID | Co może ustalić automat | Kiedy ocenia człowiek |
|---|---|---|
| 1–3 | Nazwa prawna, oznaczenie, sąsiedztwo korzyści i ryzyka | Tożsamość wydawcy, jednoznaczność reklamy, istotność ryzyka dla wskazanego produktu |
| 4–8 | Rozmiar względem dominującego pisma reklamy, kontrast i zasłonięcie, stopka/przypis, interakcja, ucięcie i skala na desktopie/tablecie/telefonie | Tło obrazu, sporny obszar reklamy, czytelność, niewykonany stan strony |
| 9–11 | Wskazanie trudnych zwrotów, języka ostrzeżenia i reklamy, cech, źródła i założeń porównania | Zrozumiałość dla adresata, niepewny język, rzetelność porównania |
| 12a, 12b, 13–16 | Historia: 5 lat, pełne okresy 12-miesięczne, okres i źródło, waluta i koszty, ekspozycja i ostrzeżenie. Prognoza i zastrzeżenie. Podatki i obie części zastrzeżenia | Wyjątki i kontekst, wykresy, dominacja wizualna, adekwatność ostrzeżeń |
| 17–18 | Wskazanie wypowiedzi sugerującej aprobatę organu lub bezpieczeństwo dzięki nadzorowi | Sporne parafrazy, neutralna informacja o nadzorze i ostateczna decyzja |

Przy każdym ID zapisać wynik (spełnione / obserwacja / brak danych / nie dotyczy), tryb (automatyczny / wspomagany / ręczny) i cytat, pomiar lub kadr. Materiał ograniczony do opisu może wymagać ręcznego otwarcia klipu.
