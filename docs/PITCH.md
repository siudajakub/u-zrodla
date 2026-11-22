# U Źródła · scenariusz filmu dla jury UKNF

## Gotowy film · 1:56

[Obejrzyj film](../presentation/film/U-Zrodla-116s-zespol-AI.mp4) · [Tekst lektora](../presentation/film/lektor-zespol-AI-116s.txt)

## Ujęcia wersji dla jury · 1:56

| Czas | Co pokazuje ekran |
| --- | --- |
| 0:00–0:10 | Dwa materiały kierują widza do ofert XTB. Comparic w rejestrze i ForexMind do kontroli. |
| 0:10–0:23 | Pięć źródeł danych, cykliczne wyszukiwanie nowych publikacji i licznik 13 690 unikalnych materiałów. |
| 0:23–0:36 | Wypowiedź Comparic o partnerze odcinka i odsyłacz do 10:14. |
| 0:36–0:50 | Kod afiliacyjny ForexMind i kadr z 0:15 do wzrokowej weryfikacji oznaczenia współpracy. |
| 0:50–1:05 | Zachęta do uzyskiwania dywidend, zapisany ekran telefonu i słowo wskazane przez OCR. |
| 1:05–1:16 | Oferta doboru proporcji akcji i obligacji oraz weryfikacja operatora serwisu. |
| 1:16–1:19 | Próba 100 filmów YouTube. Pokaż zwięzłe porównanie czwórpolowe z osią „Flaga płatnej promocji” i osią „Wpis w rejestrze”. Przy fladze „tak” było 10 wpisów i 5 poza rejestrem, przy „nie” 2 wpisy i 83 poza rejestrem. |
| 1:19–1:27 | Pokaż cytat „Partnerem odcinka jest XTB” z wynikiem „Stara reguła · 94 pkt · fałszywy alarm”. Następnie pokaż pomiar drugiego agenta dla obu wersji reguł. Na ekranie oznacz „Zbiór strojenia · 26 materiałów z 20 kampanii · etykiety agentów” oraz liczbę fałszywych alarmów 7 → 0 i przeoczeń 4 → 0 w tym zbiorze. [Diagnoza reguł](lanes/2026-11-21-fable-d-porownanie.md) · [Pomiar](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md) |
| 1:27–1:40 | Kalibracja. Na próbie 25 stron podniesienie progu z 30 do 50 zwiększa liczbę przeoczeń z 3 do 5. |
| 1:40–1:56 | Zapis decyzji i przekazanie ForexMind do kolejki kontroli. Przy ostatnim zdaniu pokaż „13 690 materiałów”, po czym zatrzymaj na źródle, uzasadnieniu i znaczniku 0:15. [Stan zbioru i przebieg pokazu](hackathon/demo.md) |

## Obrona według kryteriów UKNF

| Kryterium | Podstawa odpowiedzi, jeśli juror zapyta |
| --- | --- |
| **Technologia i gotowość demo · 30%** | Film pokazuje zapis uzasadnienia przy sprawdzonej wersji materiału i otwarcie tej samej sprawy w Kontroli. Test dwóch połączonych kart potwierdził odświeżenie drugiej po zapisie. Alert wysokiego ryzyka pojawia się, gdy skan zapisze nowe skierowanie. [Obieg decyzji i alerty](hackathon/demo.md#gdzie-trafia-sprawa) |
| **Innowacyjność procesu wytwarzania z AI · 20%** | Agent w linii kwalifikacji wykazał, że starsza reguła z wynikiem 94 punktów kierowała jawną deklarację partnerstwa XTB do przeglądu. Agent z linii pomiaru porównał obie reguły na 26 materiałach z 20 kampanii ze zbioru strojenia. [Proces pracy z asystentami AI](PROCES-AI.md#agent-złapał-błąd-agenta-albo-człowieka) · [Pomiar](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md) |
| **Architektura i rozbudowa · 20%** | Compose rozdziela role pulpitu, API, workera i harmonogramu. Zadania trafiają do Huey, a dziennik skanu z dzierżawą pozwala innemu workerowi przejąć pracę po awarii. Adaptery przekazują dane we wspólnym formacie. SQLite obsługuje jednego równoczesnego pisarza. [Architektura](ARCHITEKTURA.md) |
| **Zgodność z zadaniem · 20%** | M1 łączy firmę, twórcę, cytat i adres. M2 mierzy położenie ostrzeżenia i pozwala sprawdzić skutki zmiany progu na oznaczonej próbie. W M3 przypadek `rdmwm.pl` zawiera cytat o indywidualnym doborze proporcji portfela. Tożsamość operatora i uprawnienia wymagają ustalenia przez analityka. [Brief UKNF](zrodla-uknf/BRIEF.md#8-kryteria-oceny) · [Próba M3](lanes/2026-11-21-fable-f-m3.md) |
| **Atrakcyjność · 10%** | Jedno zdanie Comparic w **10:14** zmienia ścieżkę sprawy. Finał pokazuje, jak kolejny analityk podejmuje sprawę od wskazanej sekundy. |

## Pytania o dowody

| Pytanie | Odpowiedź |
| --- | --- |
| **Skąd wiemy, że program faktycznie szuka?** | Datowana próba YouTube użyła **17 zapytań** przez `search.list` bez nazw kanałów. Znalazła **209 polskojęzycznych kanałów**, w tym **33 z 68** kwalifikujących się kanałów z zamrożonej listy referencyjnej po wyłączeniu znanego wcześniej Comparic. W pierwszej piątce wynik wyniósł **3/5** przy celu **4/5**. [Pełny wynik próby Y](../fixtures/validation/y-reference/WYNIK-Y-2026-11-21.md) |
| **Co w źródłach jest dostępne na żywo?** | Oficjalne API YouTube służy do wyszukiwania i odczytu opisów. TikTok dostarcza podpisy z publicznych osadzeń. W pokazie odtwarzamy datowaną próbkę zewnętrzną Meta, a oficjalny odczyt cykliczny wymaga uprawnień. Zapis decyzji i zmiana wyniku symulacji działają w otwartej sesji pulpitu. [Monitoring i zakres dostępu](MONITORING.md) |
| **Co mówią liczby o trafności?** | Wynik porównania reguł M1 dotyczy zbioru strojenia. W osobnej próbie 8 filmów różnych twórców obie oceny zgadzają się w sprawie 3 jawnych współprac i 5 kontroli ujemnych. Mianowniki precyzji i pełności są zerowe. Kalibracja M2 obejmuje 25 stron 11 firm ocenionych przez agenta w zbiorze strojenia. Przy progach 30 i 50 jest odpowiednio 3 i 5 przeoczeń. [Próba M1](lanes/2026-11-22-proba-kampanii.md) · [Próba M2](lanes/2026-11-21-fable-e-m2.md) |
| **Gdzie pomaga AI?** | Lokalny E5 wspomaga rozpoznawanie rodzaju materiału. Lokalny Qwen w Ollamie dostarcza drugą opinię z cytatem do sprawdzenia. OCR odczytuje tekst oraz jego położenie w zachowanym obrazie. Za automatyczne skierowanie odpowiadają reguły, a decyzję w sprawie uzasadnia i zatwierdza analityk. [Pomiar inferencji](lanes/2026-11-21-fable-ai-inferencja.md) · [Pełny scenariusz stanowiska](hackathon/demo.md) |
