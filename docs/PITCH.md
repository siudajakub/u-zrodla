# Pitch InvestWatch dla jury UKNF

Wersja robocza z 21 XI 2026, ok. 22:30 UTC, do zamrożenia razem z kandydatem. Najpierw ustalamy treść pitchu, potem dopasowujemy do niej pulpit (sekcja 11). Każda liczba ma źródło w repo albo w API bazy pokazu. Liczby z API opisują stan bazy podglądu `127.0.0.1:18801`, odczyt 21 XI o 22:14 UTC. Mogą się zmienić po przeliczeniu, dlatego oznaczamy je **[odczyt]** i przed nagraniem odczytujemy je ponownie z `/v1/overview?schema=2`.

**Narracja.** Pokazujemy narzędzie gotowe do pilotażu w urzędzie. Analityk dostaje krótką listę spraw z dowodem i może się pod nią podpisać przed przełożonym. Technologia służy jako powód, dla którego można temu ufać: warstwy weryfikacji, obalone podejrzenia, kontrola ujemna, praca lokalna i odtwarzalna. Efekt „wow” daje jedna sprawa, którą prowadzimy od odkrycia kanału do sekundy filmu i kadru.

## 0. Jak oceniają i co z tego wynika

Źródło: ustalenia koordynatora ze strony organizatora (hacknation.pl, FAQ i platforma zgłoszeń, odczyt 21 XI wieczorem). Tych ustaleń nie ma w plikach repo.

- **Etap I** zaczyna się 22 XI o 11:00, wraz z końcem kodowania. Jurorzy mają „kilka minut na ocenę każdego zgłoszenia”. Ten etap rozstrzygają **pierwszy slajd PDF i pierwsze 20 sekund filmu**.
- O 14:45 organizator ogłasza finalistów. O 15:15 zaczyna się **etap II, pitching**. Organizator nie podał jego długości, więc mamy gotowe wersje 60 s, 3 min i 5 min.
- **Forma zgłoszenia:** PDF poniżej 10 MB albo link, demo opcjonalne „do 2 minut”, działający przykład i działający link. Brief dopuszcza film do 3 minut ([BRIEF §4](zrodla-uknf/BRIEF.md)). Wersją podstawową jest **film 120 s**.
- **Jury** tworzy pięć osób z UKNF. To urzędnicy nadzoru, więc najmocniejszym argumentem jest „mogę za tym stanąć”, a nie „to robi AI”.

**Pierwszy ekran** (slajd 1 i sekundy 0–20 filmu) musi sam przenieść trzy rzeczy:
1. Tezę: „Z prawie dwóch tysięcy materiałów analityk dostaje piętnaście spraw. Każda ma cytat, sekundę filmu i niewinne wyjaśnienie.”
2. Jedną realną sprawę: kartę ForexMind („Freedom24 Alternatywy…”, `youtube:AqXHkxDzSDI`) z przyciskiem **Otwórz w filmie od 0:15** i dwoma kadrami.
3. Trzy liczby: **1923 → 290 → 15** **[odczyt]**, czyli materiały → rejestr jawnych reklam → sprawy do sprawdzenia (`queues.all`, `queues.adRegister`, `queues.review`).

## 1. Hook i teza

**Hook (jedno zdanie):**
> W 10. minucie i 14. sekundzie filmu Comparic pada zdanie, które oczyszcza twórcę z podejrzenia, a InvestWatch je słyszy, zanim analityk straci na ten film choćby minutę.

**Teza (3 zdania):**
> Bez narzędzia analityk nadzoru ma przed sobą tysiące filmów i stron, w których brokerzy pojawiają się setki razy, i nie wie, która promocja jest uczciwie oznaczona. Z InvestWatch dostaje krótką kolejkę spraw, które przeszły przez opis, flagę platformy, całą mowę, kadry i wykazy KNF, a jawna reklama trafia do osobnego rejestru, nie do alarmu. Każda sprawa ma cytat, sekundę nagrania i niewinne wyjaśnienie, więc analityk może ją obronić przed przełożonym jednym kliknięciem.

Źródła: hook w [rekordzie C](lanes/2026-11-21-fable-c-media.md) („614 s znajdziecie u partnera tego odcinka XTB”) i w karcie `/v1/cases/youtube:CDk20n4u9Kk?schema=2` (`adRegistry.summary`: „Współpraca ujawniona w mowie (10:14)”). Warstwy opisuje sekcja 2.

## 2. Wielowarstwowa weryfikacja: kluczowa decyzja architektoniczna

**Zdanie do powiedzenia:** „U nas żaden model nie może nikogo oskarżyć. Podejrzenie stawia jawna reguła z dosłownym cytatem i znacznikiem czasu. Potem pięć kolejnych warstw próbuje je obalić. Do analityka trafia tylko to, co przetrwa wszystkie.”

| # | Warstwa | Co sprawdza | Czy może obalić podejrzenie | Dowód w repo |
|---|---|---|---|---|
| 1 | Odkrycie i zakres | Wyszukiwanie YouTube Data API v3 po polskich frazach, monitoring bazy 221 polskich kanałów, kanał Atom, język i region | Tak, wyklucza materiał spoza zakresu (177 kanałów niepolskich pominiętych) | [rekord B](lanes/2026-11-21-fable-b-youtube.md), [MONITORING](MONITORING.md) |
| 2 | Opis | Dowód relacji (link śledzący lub skrócony przy marce, kod twórcy) oraz szukanie oznaczenia | **Tworzy** podejrzenie U1. Oznaczenie w opisie je obala i kieruje film do rejestru | [rekord D](lanes/2026-11-21-fable-d-kwalifikacja.md) |
| 3 | Flaga płatnej promocji platformy | Pole z Data API | Tak. W rejestrze jest 49 filmów YouTube i 12 postów IG oznaczonych flagą **[odczyt]** | `/v1/queues/adRegister`, `disclosure.state = platform_flag` |
| 4 | Mowa (bramka mowy) | Pełna transkrypcja z oryginalnych polskich napisów. Bez zbadanej mowy film nie trafia do alarmu, tylko do „Niepełnych danych” | Tak. 9 filmów bez oznaczenia w opisie ma je w mowie i trafiło do rejestru **[odczyt]**. 81 kandydatów czeka na mowę zamiast podnosić alarm **[odczyt]** | `disclosure.state = in_speech`; `route = complete`, `completeReason = transcript_pending` |
| 5 | Kadry z wybranych momentów | Klatki z sekund wskazanych przez dowód, ze storyboardu albo strumienia 360p, bez pobierania filmu | Tak. Freedom24 (195 s) i Comparic (614 s) mają etykietę „REKLAMA” | [rekord C](lanes/2026-11-21-fable-c-media.md) |
| 6 | Wykazy KNF | Dopasowanie firmy do datowanych kopii wykazów (M1: XTB S.A. nr 6884980 i XTB Ltd z notyfikacji, M3: 12 wykazów i lista ostrzeżeń) | Tak. Firma spoza zakresu daje „bez sygnału”, np. pośrednik kredytowy Hipoteka Direct w FBO 348 | [porównanie D](lanes/2026-11-21-fable-d-porownanie.md), [rekord F](lanes/2026-11-21-fable-f-m3.md) |
| 7 | Klasyfikator typu materiału (E5) | Promocja, edukacja, informacja albo opinia, z pewnością 0–1 | Nie. To opis dla analityka (`affectsDecision: false`) | [rekord AI](lanes/2026-11-21-fable-ai-inferencja.md) |
| 8 | Drugi głos modelu językowego | Ponownie czyta kontekst jednej decyzji. Cytat spoza wskazanej linii jest odrzucany | Nie obala. Rozbieżność oznacza sprawę „do przeglądu” i nie zmienia trasy (`affectsRoute: false`). Wyłączony domyślnie | `analysis/second_opinion.py` (`be18904`, `fb17d18`) |
| 9 | Analityk | Decyzja z uzasadnieniem i rewizją, historia, próg z widocznym FP/FN | Tak, ostatnie słowo | [scenariusz](hackathon/demo.md) |

**Dlaczego decydują reguły, a modele weryfikują (wersja ofensywna).** Sprawdziliśmy modele w roli sędziego na tych samych wejściach. Qwen3.5 9B i 27B na 5 materiałach z udokumentowaną nieoznaczoną współpracą **ani razu** nie zwróciły „nieoznaczona współpraca”. 27B poprawnie wskazał dowód relacji w 4 z 5, ale nie wyciągnął wniosku o braku oznaczenia ([porównanie D](lanes/2026-11-21-fable-d-porownanie.md), fale 3 i 4). Wcześniejsze reguły 1.2 dawały na zbiorze strojenia 7 fałszywych alarmów i 4 przeoczenia, a kwalifikacja warstwowa 0 i 0 ([WYNIK-M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md)). Nadzór musi umieć uzasadnić każdą flagę cytatem. Dlatego model może tylko podnieść rękę, a decyzja ma zawsze cytat i wersję reguł. To nie jest „mniej AI”. To AI umieszczone tam, gdzie jest mocne: rozumienie stylu tekstu (E5 30/57 wobec 13/57 słownika) i druga para oczu z kontrolą cytatu.

**Przykład obalenia: Comparic, „ARABIA SZYKUJE SIĘ NA WOJNĘ…”** (`youtube:CDk20n4u9Kk`). W opisie jest link `link-pso.xtb.com` i kod „COMPARIC”, ale nie ma słowa „reklama”. Na samym opisie to klasyczne podejrzenie. Mowa w 10:14 mówi: „znajdziecie u partnera tego odcinka XTB.” W próbie linii C kadr z 614 s ma etykietę „REKLAMA”. Film trafił do rejestru, a nie do alarmu. W bazie pokazu karta ma mowę, ale kadru jeszcze nie (`coverage.gaps`: frames `not_collected`), co opisuje sekcja 11.

**Przykład podejrzenia, które przetrwało wszystkie warstwy: ForexMind, „Freedom24 Alternatywy…”** (`youtube:AqXHkxDzSDI`, siła 95/100). Opis zawiera skrócony link przy XTB i kod „TRADEXTB”. Oznaczenia nie ma w opisie, w całej mowie (0:00–3:24) ani w 2 kadrach (0:15, 3:06). YouTube nie oznacza filmu jako płatnej promocji. Wykaz KNF podaje dwa pasujące podmioty i karta nie wybiera między nimi. Karta podaje też niewinne wyjaśnienie: „link może być zwykłym poleceniem, bez wynagrodzenia dla twórcy” (`reviewDecision.reasons`, `reviewDecision.moments`).

**Drugi głos przez API na stanowisku: stan faktyczny.** Dziś produkt **odmawia** zdalnego backendu (`backend_forbidden` w `analysis/inference.py`), a drugi głos nie jest wpięty w `analysis/engine.py`. Przełącznika „przez API” nie ma, więc nie mówimy o nim jak o funkcji. Jeśli J zdecyduje się go dodać, zdanie brzmi:
> „Na tym laptopie drugi głos czyta model o otwartych wagach przez API, bo jest to jawny przełącznik pokazowy. W urzędzie te same wagi działają lokalnie w Ollamie, bez płatnego API i bez wysyłania danych. Decyzja nigdy od niego nie zależy.”

Rekomendacja (sekcja 12, poz. 1): lepiej uruchomić Ollamę lokalnie na Macu albo pokazać zapisany pomiar niż wprowadzać przełącznik API dzień przed oceną.

**Odpowiedź na „brief mówi: bez płatnych API”:**
> „Produkt nie wywołuje żadnego płatnego API, a kod blokuje to wprost. Model działa lokalnie przez Ollamę na licencji Apache-2.0. Przez API tylko wybieraliśmy, który otwarty model postawić. Cały ten pomiar kosztował ułamek dolara i jest zapisany w rejestrze kosztów.”

Źródła: `analysis/inference.py`, [ARCHITEKTURA](ARCHITEKTURA.md) §Bezpieczeństwo, [TEAM_BOARD](../TEAM_BOARD.md) (rejestr kosztów ok. 0,14 USD). Pomiar drugiego głosu w `fixtures/labeled/ai-second-opinion-summary.json` (niezacommitowany) dokłada swój koszt. Przed pokazem trzeba dopisać go do rejestru.

## 3. Pitch na żywo: 3 minuty

Około 420 słów. Pulpit pod `http://127.0.0.1:8769/theme-preview/` ([scenariusz](hackathon/demo.md)). W nawiasach kwadratowych podajemy ekran i klik.

**0:00–0:20 · problem i hook.** [Ekran startowy z lejkiem 1923 → 290 → 15, sekcja 11 poz. 1]
„Każdego dnia w polskiej sieci powstają setki materiałów o inwestowaniu. Brokerzy pojawiają się w nich ciągle. Nadzór musi odróżnić uczciwie oznaczoną reklamę od ukrytej. W bazie pokazu mamy prawie dwa tysiące materiałów. Analityk dostaje z nich piętnaście spraw. Każdą z nich może obronić przed przełożonym.”

**0:20–1:05 · jedna sprawa od odkrycia do sekundy filmu.** [**Co wymaga sprawdzenia** → ForexMind „Freedom24 Alternatywy…” → pasek **Droga dowodu** → **Otwórz w filmie od 0:15**]
„System sam znalazł ten film przez oficjalne API YouTube, wyszukując frazę »Freedom24«. W opisie jest skrócony link przy XTB i kod twórcy. To dowód relacji handlowej. Teraz zaczyna się weryfikacja. Opis nie zawiera oznaczenia reklamy. YouTube nie oznacza filmu jako płatnej promocji. Przeczytaliśmy całą mowę, od zera do trzech minut dwudziestu czterech, z oryginalnych napisów, w dwie sekundy i bez pobierania filmu. Pobraliśmy kadry z momentów dowodu. W piętnastej sekundzie twórca mówi: »znajdziesz linki do specjalnych ofert w opisie«. Wykaz KNF podaje dwa podmioty XTB i system nie zgaduje, którego dotyczy link. Karta podaje też niewinne wyjaśnienie. To przesłanka do kontroli, a nie zarzut.”

**1:05–1:35 · dlaczego możecie temu ufać.** [**Rejestr reklam M1** → szukaj „Comparic” → karta, krok **Mowa 10:14: obaliło**]
„Tu podejrzenie upadło. Comparic ma link i kod XTB bez słowa »reklama«. W dziesiątej minucie twórca mówi jednak: »znajdziecie u partnera tego odcinka XTB«. Film trafił do rejestru, a nie do alarmu. Mowa wyjaśniła tak dziewięć filmów bez oznaczenia w opisie, a flaga platformy kolejne sześćdziesiąt jeden materiałów. Modele językowe sprawdzaliśmy jako sędziów i nie wykryły żadnej ukrytej współpracy. Dlatego u nas decyduje jawna reguła z cytatem, a model jest drugą parą oczu, która może tylko zgłosić rozbieżność.”

**1:35–2:00 · kalibracja i kontrola ujemna.** [**Kalibracja** → suwak 60 → 95 → **Wróć do obowiązującego**]
„Analityk sam ustawia próg. Przy sześćdziesięciu punktach mamy cztery trafienia i zero fałszywych alarmów. Poprzednie reguły dawały siedem. Przy dziewięćdziesięciu pięciu pojawiają się przeoczenia. Żółty pasek mówi uczciwie, że to oceny agentów na zbiorze strojenia, a nie walidacja ekspercka. Każdy próg ma historię i można do niego wrócić.”

**2:00–2:25 · trzy moduły jednym ekranem.** [**Źródła**, potem **Oferty M2** i **Oferty M3**]
„Moduł drugi ocenia dziewiętnaście kryteriów UKNF na stronach jedenastu firm z wykazów, na ekranie komputera i telefonu, i mierzy, czy ostrzeżenie stoi przy obietnicy zysku. Moduł trzeci sprawdza oferty doradcze w dwunastu wykazach KNF i na liście ostrzeżeń. Źródła to YouTube, TikTok i strony WWW. Facebook i Instagram mają datowaną próbkę i import, bo automatyczny odczyt bez tokenu Meta jest zablokowany, a my blokad nie obchodzimy. Raport w każdym module ma firmę, podmiot, treść i adres.”

**2:25–2:45 · jak to powstało.** [slajd procesu]
„Zbudowaliśmy to z zespołem agentów AI według jednego protokołu: kontrakt przed kodem, ślepe etykiety przed regułami i niezależni sędziowie. Etykiety zamrażaliśmy, zanim powstały reguły. Każdy commit z bramką podaje faktycznie uruchomiony test. Dziesięć błędów złapali agenci, zanim trafiły do produktu.”

**2:45–3:00 · co UKNF dostaje jutro.** [karta ForexMind → **Decyzja** → **Pobierz raport**]
„Stanowisko uruchamiane jedną komendą, lokalnie i bez płatnych API. Pięć serwisów w Dockerze, jeden port, sieć bez Internetu. Raport ma kolumny wymagane przez UKNF. Pilotaż zaczyna się od etykiet waszych ekspertów.”

### Plan na 5 minut

Do wersji 3-minutowej dodajemy po kroku 2:00 kolejne kroki z [scenariusza 5 minut](hackathon/demo.md):
1. **M2, ETF XTB:** na telefonie ostrzeżenie stoi 864 px od wzmianki o dywidendach ([rekord E](lanes/2026-11-21-fable-e-m2.md)).
2. **M2, Noble IKE:** cytat korzyści podatkowej bez zastrzeżenia (siła 95 w kolejce **[odczyt]**).
3. **M3, kontrola ujemna DM BOŚ:** oferta ma wszystkie cechy doradztwa, ale wykaz KNF podaje zezwolenie, więc system nie flaguje. Potem **rdmwm.pl**: jedyna skierowana sprawa na 31 materiałów, operator do ustalenia.
4. **Import Meta:** wgranie zapisanej strony Biblioteki Reklam.
5. **Druga karta pulpitu:** decyzja wysyła zdarzenie przez WebSocket.

### Wersja 60 sekund

„W bazie pokazu jest prawie dwa tysiące polskich materiałów o inwestowaniu. Analityk dostaje z nich piętnaście spraw. Ta to film ForexMind. System sam go znalazł przez API YouTube. W opisie jest link i kod XTB, a oznaczenia reklamy nie ma w opisie, w całej mowie, w kadrach ani w danych platformy. Wykaz KNF podaje dwa podmioty XTB. Klikam i film otwiera się w sekundzie dowodu. Tu podejrzenie upadło: Comparic mówi o partnerze odcinka w dziesiątej minucie, więc film trafia do rejestru, a nie do alarmu. Decyduje jawna reguła z cytatem, a model językowy jest drugą parą oczu. Moduł drugi mierzy na ekranie telefonu, czy ostrzeżenie stoi przy zysku. Moduł trzeci sprawdza oferty doradcze w dwunastu wykazach KNF. Wszystko działa lokalnie, jedną komendą i bez płatnych API. Gotowe do pilotażu z etykietami waszych ekspertów.”

## 4. Film 120 s: scenopis i tekst lektora

Około 270 słów lektora. Zdania są krótkie, a liczby zapisane słownie dla syntezy mowy. Nagrywamy z pulpitu na zamrożonym kandydacie w 1440 px. Ujęcie 7 można nagrać w 390 px.

| Czas | Ujęcie i ekran | Lektor |
|---|---|---|
| 0:00–0:20 | **1. Pierwszy ekran.** Lejek 1923 → 290 → 15 **[odczyt]**, obok karta ForexMind z dwoma kadrami. Napis: „InvestWatch · gotowe do pilotażu w UKNF” | „Prawie dwa tysiące polskich materiałów o inwestowaniu. Piętnaście spraw dla analityka. Każda ma cytat, sekundę filmu i niewinne wyjaśnienie. To jest InvestWatch. Narzędzie dla analityka nadzoru.” |
| 0:20–0:50 | **2. Droga dowodu.** Karta ForexMind, pasek kroków zapala się kolejno. Klik **Otwórz w filmie od 0:15** | „System sam znalazł ten film przez oficjalne API YouTube. W opisie jest link i kod twórcy przy XTB. To dowód relacji handlowej. Oznaczenia reklamy nie ma w opisie. Platforma nie oznacza płatnej promocji. Przeczytaliśmy całą mowę z oryginalnych napisów. Pobraliśmy kadry z momentów dowodu. Wykaz KNF podaje dwa podmioty XTB. Każdy krok ma znacznik czasu i wersję reguł. Klik, i film otwiera się w piętnastej sekundzie.” |
| 0:50–1:10 | **3. Obalone podejrzenie.** Rejestr reklam → Comparic, krok „Mowa 10:14: obaliło”, licznik obalonych | „Tu podejrzenie upadło. Comparic też ma link i kod bez słowa reklama. Ale w dziesiątej minucie twórca mówi o partnerze odcinka. Film trafia do rejestru, nie do alarmu. Każda warstwa może obalić podejrzenie. Do analityka trafia tylko to, co przetrwa wszystkie. Mowa wyjaśniła tak dziewięć filmów, a flaga platformy sześćdziesiąt jeden materiałów. Żaden model nie może tu nikogo oskarżyć.” |
| 1:10–1:25 | **4. Kalibracja.** Suwak 60 → 95, wykres FP i FN | „Analityk sam ustawia próg i od razu widzi fałszywe alarmy i przeoczenia. Uczciwie oznaczamy, że to oceny agentów, a nie ekspertów. Przy progu sześćdziesiąt: cztery trafienia, zero fałszywych alarmów. Poprzednie reguły dawały siedem.” |
| 1:25–1:40 | **5. Moduły 2 i 3.** Karta M2 na telefonie, potem karta M3 z wykazem KNF | „Moduł drugi sprawdza dziewiętnaście kryteriów UKNF na stronach firm, także na ekranie telefonu. Moduł trzeci szuka doradztwa bez zezwolenia w dwunastu wykazach KNF. Kontrola ujemna: dom maklerski z zezwoleniem nie dostaje flagi.” |
| 1:40–1:52 | **6. Technologia.** Schemat serwisów: web, api, worker, scheduler, inference | „Decyduje jawna reguła z cytatem. Modele o otwartych wagach weryfikują. Całość działa lokalnie, w Dockerze, jedną komendą, bez płatnych API. Modele zmierzyliśmy, zanim je wybraliśmy. Budował to zespół agentów AI z niezależnymi sędziami.” |
| 1:52–2:00 | **7. Zamknięcie.** Decyzja zapisana, przycisk **Pobierz raport**, logo | „Raport w formacie UKNF. Gotowe do pilotażu. Pierwszy krok pilotażu to etykiety waszych ekspertów. InvestWatch, na straży inwestorów.” |

## 5. Slajdy PDF (8–9), szkic treści

PDF zbuduje inny agent po zamrożeniu wersji. Limit to 10 MB.

1. **Tytuł z tezą.** „InvestWatch: piętnaście spraw z dowodem zamiast dwóch tysięcy materiałów.” Punkty: lejek 1923 → 290 → 15 **[odczyt]**; jedna sprawa z cytatem, sekundą i niewinnym wyjaśnieniem; lokalnie, bez płatnych API. Pokazać: zrzut karty ForexMind z kadrami (`1440-2-karta-flagi-momenty.png` albo r4).
2. **Problem.** Promocja brokerów u finfluencerów jest masowa, oznaczenia bywają w opisie, w mowie albo w kadrze, a nadzór musi każdą flagę uzasadnić. Pokazać: trzy sposoby oznaczenia na przykładach (opis Konopskyy, mowa Comparic, kadr Freedom24).
3. **Jedna sprawa od odkrycia do sekundy.** Droga dowodu ForexMind w 6 krokach. Pokazać: pasek kroków i dwa kadry.
4. **Wielowarstwowa weryfikacja.** Tabela 9 warstw z sekcji 2 (skrót). Punkty: 9 filmów wyjaśnionych mową i 61 materiałów wyjaśnionych flagą platformy **[odczyt]**; bramka mowy (81 czeka, zamiast alarmu); model nie oskarża. Pokazać: diagram lejka warstw.
5. **Trzy moduły, pięć źródeł.** M1 (rejestr i kolejka), M2 (19 kryteriów, 25 stron, 11 firm, 1440 i 390 px), M3 (12 wykazów i lista ostrzeżeń, kontrola DM BOŚ). Pokazać: kafle Źródła z datowanym statusem.
6. **Liczby z mianownikami.** Kalibracja 26/20, FP 7 → 0; E5 30/57 wobec 13/57; Y 3 z 5 (niezaliczone). Pokazać: panel kalibracji z żółtym paskiem.
7. **Architektura.** 5 serwisów Compose, jeden port, sieć wewnętrzna, kolejka z dzierżawą, adapter `discover(ctx)`. Pokazać: diagram z [ARCHITEKTURA](ARCHITEKTURA.md).
8. **Proces z agentami AI.** Kontrakt przed kodem, ślepe etykiety, sędziowie; 116 commitów, 84 z bramką; 10 złapanych błędów. Pokazać: tabelę ról z [PROCES-AI](PROCES-AI.md).
9. **Co UKNF dostaje i czego jeszcze nie ma.** Pilot w 3 krokach (etykiety ekspertów, token Meta, zgoda na transkrypcje). Ograniczenia nazwane wprost. Pokazać: listę „gotowe / do pilotażu”.

## 6. Każde kryterium ma swoje zdanie i swój ekran

| Kryterium (waga, [BRIEF §8](zrodla-uknf/BRIEF.md)) | Zdanie | Ekran |
|---|---|---|
| Technologia i gotowość demo (30%) | „Jedna sprawa od wyszukania w API do kadru z 15. sekundy, odtwarzalna offline z datowanego zapisu.” | Karta ForexMind z paskiem **Droga dowodu** |
| Proces z asystentami AI (20%) | „Agenci budowali według protokołu z kontraktem, ślepymi etykietami i sędziami. Dziesięć błędów złapali agenci.” | Slajd 8 albo tabela z [PROCES-AI](PROCES-AI.md) |
| Architektura (20%) | „Pięć lekkich serwisów, jeden adapter na źródło, kolejka z dzierżawą. Nowe źródło to jedna funkcja.” | Slajd 7 i kafle **Źródła** |
| Zgodność ze specyfikacją (20%) | „Trzy moduły, raport z kolumnami UKNF, próg z FP/FN, WebSocket, Docker Compose, Ollama, Chart.js, React.” | Kolejka z filtrami M1/M2/M3, **Kalibracja**, **Pobierz raport** |
| Atrakcyjność (10%) | „Podejrzenie obalone mową w 10:14. System, który sam szuka dowodu niewinności.” | Karta Comparic z krokiem „obaliło” |

## 7. Nasze najmocniejsze strony

| # | Mocne zdanie | Dowód | Kryterium |
|---|---|---|---|
| 1 | **Podejrzenie musi przetrwać pięć niezależnych prób obalenia, zanim zobaczy je człowiek.** | 9 filmów bez oznaczenia w opisie wyjaśnionych mową, 61 materiałów wyjaśnionych flagą platformy, 81 wstrzymanych przez bramkę mowy **[odczyt]** (`/v1/queues/adRegister`). Reguły 1.2: FP 7 → 0 ([WYNIK-M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md)) | Technologia, atrakcyjność |
| 2 | **Słyszymy cały film w 2 sekundy, bez pobierania wideo.** | Oryginalne polskie napisy w 1,95–2,18 s na film i 0 B audio. Lokalne ASR Vosk zostaje jako wariant awaryjny ([rekord C](lanes/2026-11-21-fable-c-media.md)) | Technologia |
| 3 | **Kadry tylko z sekund, które wskazał dowód.** | Storyboard: 0,2 s na arkusz 9 kadrów, 2–7 kB na kadr. Strumień 360p: 131–206 kB na kadr. Żadna droga nie pobiera całego filmu ([rekord C](lanes/2026-11-21-fable-c-media.md)) | Technologia |
| 4 | **Szukamy oszczędnie: dzienną kwotę YouTube wydajemy na nowe kanały, a znane monitorujemy niemal za darmo.** | Frazy tematyczne dały 152 polskie kanały na 800 jednostek, frazy firmowe 51. Ponowny odczyt 1300 filmów kosztował 27 z 10 000 jednostek dziennej puli. W bazie jest 221 polskich kanałów ([MONITORING](MONITORING.md), [rekord B](lanes/2026-11-21-fable-b-youtube.md)) | Technologia, architektura |
| 5 | **Rejestr reklam jest osobnym produktem, zgodnie z wymogiem M1, a nie efektem ubocznym alarmu.** | 290 pozycji z firmą, twórcą, treścią i URL **[odczyt]**. Jawna współpraca nie podnosi alarmu ([BRIEF §2 M1](zrodla-uknf/BRIEF.md), [HACKATHON](../HACKATHON.md)) | Zgodność |
| 6 | **M2 mierzy geometrię ostrzeżenia na ekranie telefonu, a nie tylko jego obecność.** | 19 kryteriów, 25 stron 11 firm (w tym 3 oddziały zagraniczne), 50 widoków 1440 i 390 px. ETF XTB: na telefonie 864 px od ostrzeżenia ([rekord E](lanes/2026-11-21-fable-e-m2.md)) | Zgodność, technologia |
| 7 | **M3 woli jedną udokumentowaną sprawę niż listę zarzutów.** | 31 materiałów z 29 domen, 12 wykazów KNF, lista ostrzeżeń (682 wpisy), 1 sprawa skierowana (rdmwm.pl), kontrola ujemna DM BOŚ ([rekord F](lanes/2026-11-21-fable-f-m3.md)) | Zgodność |
| 8 | **Każde źródło to jedna funkcja w jednym kontrakcie.** | `discover(ctx)` i `register(Adapter(…))` w `collectors/discovery.py`. YouTube, TikTok, Meta (API, import, próbka), strony M2 i oferty M3 mają wspólny stan źródła, kwotę i dzierżawę ([ARCHITEKTURA](ARCHITEKTURA.md)) | Architektura |
| 9 | **Analityk widzi skutek progu, zanim go zmieni.** | Suwak z TP/FP/FN, kosztem 2×FN+FP, porównaniem wariantów i historią progu. Próg 60: 4/0/0 wobec FP 7 i FN 4 dla reguł 1.2 (`/v1/overview`, pole `calibration`) | Zgodność (§6 briefu) |
| 10 | **Wszystko jest odtwarzalne, lokalne i weryfikowalne.** | Datowany zapis 21 XI z SHA-256, 5 serwisów Compose z jednym portem 127.0.0.1, kontenery tylko do odczytu, audyty npm i pip bez wykryć, produkt bez płatnych API ([ARCHITEKTURA](ARCHITEKTURA.md)) | Architektura, zgodność |
| 11 | **Agenci AI budowali według protokołu, który łapał ich własne błędy.** | 116 commitów do `fb17d18`, 84 z trailerem `Gate:` (`git log`). 10 udokumentowanych błędów złapanych przez agenta albo walidator. Etykiety zamrożone przed regułami ([PROCES-AI](PROCES-AI.md)) | Proces AI |

## 8. Technologia po ludzku

| Co robimy | Jak | Dlaczego to trudne albo wartościowe |
|---|---|---|
| Sami znajdujemy polskie kanały i nowe filmy | Oficjalne API YouTube, polskie frazy, baza kanałów sprawdzana tanio, księga kwoty na każdy klucz (YouTube Data API v3, Atom) | Darmowa kwota to 10 000 jednostek na dobę, a jedno wyszukiwanie kosztuje 100. Bez oszczędnej bazy pula kończy się po kilkudziesięciu zapytaniach |
| Czytamy, co twórca powiedział i pokazał | Oryginalne polskie napisy, klatki z wybranych sekund (yt-dlp bez pobierania wideo, ffmpeg, storyboard; Vosk jako awaryjne ASR) | Oznaczenie reklamy często pada tylko w mowie albo w kadrze. Bez tego co drugi alarm byłby fałszywy |
| Każdą flagę uzasadniamy cytatem | Jawne, wersjonowane reguły z dosłownym cytatem, pozycją w tekście i znacznikiem czasu (Python, `investwatch-m1-qual-1.0`) | Urząd musi obronić każdą flagę. Reguła ma wersję, więc wiadomo, dlaczego sprawa trafiła do kolejki w danym dniu |
| Sprawdzamy, czy firma jest w wykazach KNF | Datowane kopie wykazów i listy ostrzeżeń, dopasowanie z kandydatami zamiast zgadywania (JSON, SHA-256) | Nazwy się powtarzają (XTB S.A. i XTB Ltd, kolizja FinanceWell). System pokazuje kandydatów i nie przesądza |
| Mierzymy strony firm jak człowiek z linijką | Zrzut i pomiar położenia każdego bloku tekstu na komputerze i telefonie (Playwright, Chromium) | „Wyraźne i proporcjonalne” ostrzeżenie to pytanie o odległość na ekranie, a nie o samo słowo |
| AI jako druga para oczu | Klasyfikator typu materiału na embeddingach (E5 multilingual, ONNX na CPU) i drugi głos modelu o otwartych wagach z walidatorem cytatu (Ollama, Ministral 3 albo Qwen3.5, Apache-2.0) | Model nie oskarża. Gdy się nie zgadza, sprawa idzie do człowieka, a zmyślony cytat jest odrzucany |
| Praca w tle i odporność | Kolejka zadań z dzierżawą i przejęciem po awarii, harmonogram co 4 h (Huey, SQLite, scheduler w roli CronJob) | Awaria jednego procesu nie gubi skanu, a drugi harmonogram nie dubluje pracy |
| Pulpit i alarmy na żywo | API i strumień zdarzeń, pulpit z wykresem trendu i suwakiem progu (FastAPI, WebSocket, React 19, Astryx, Chart.js) | Druga karta widzi decyzję kolegi od razu, a każda decyzja ma rewizję |
| Jedno polecenie, lokalnie | Pięć serwisów w kontenerach, jeden port, sieć wewnętrzna bez Internetu (Docker Compose, nginx) | Stanowisko w urzędzie nie wysyła danych na zewnątrz i startuje tak samo na każdym komputerze |

## 9. Liczby

### Liczby do pokazania

| Liczba | Znaczenie | Źródło | Zastrzeżenie |
|---|---|---|---|
| 1923 → 290 → 15 | Materiały w bazie pokazu → rejestr reklam → do sprawdzenia (4 M1, 10 M2, 1 M3) | `/v1/overview?schema=2`, `queues` **[odczyt]** | Stan bazy podglądu. Zmienia się po przeliczeniu |
| 9 i 61 | Wpisy rejestru, w których oznaczenie znalazła dopiero mowa (9) albo flaga platformy (61: 49 YouTube + 12 IG) | `/v1/queues/adRegister`, `disclosure.state` **[odczyt]** | Liczę wpisy rejestru ze stanem `in_speech` i `platform_flag`. Nie każdy z 61 miał w opisie dowód relacji, więc nie nazywamy ich wszystkich „podejrzeniami” |
| 81 | Kandydaci wstrzymani przez bramkę mowy zamiast alarmu | jw., `completeReason = transcript_pending` **[odczyt]** | 1288 materiałów czeka na transkrypcję |
| 477 | Twórcy i podmioty: YouTube 381, IG 31, FB 19, TikTok 6, WWW 40 | `/v1/overview`, `creatorCounts` **[odczyt]** | FB i IG pochodzą z datowanej próbki i importu |
| 221 | Polskie kanały w bazie monitoringu (177 niepolskich pominiętych) | [rekord B](lanes/2026-11-21-fable-b-youtube.md) | Pokrycie listy Y niezaliczone (3 z 5) |
| 152 vs 51 | Polskie kanały na 800 jednostek: frazy tematyczne wobec firmowych | [MONITORING](MONITORING.md) | Pierwszy przebieg. Kolejne dają mniej nowych kanałów (nasycenie) |
| 27 z 10 000 | Jednostki kwoty na ponowny odczyt 1300 filmów | [rekord B](lanes/2026-11-21-fable-b-youtube.md) | Dzięki cache i oknu dziennemu |
| ok. 2 s, 0 B audio | Pełna transkrypcja jednego filmu | [rekord C](lanes/2026-11-21-fable-c-media.md) | Pomiar na 4 filmach. Auto-napisy przekręcają nazwy własne |
| 26 / 20 · FP 7 → 0, FN 4 → 0 | Kalibracja M1: materiały i kampanie, reguły 1.2 wobec kwalifikacji warstwowej przy progu 60 | [WYNIK-M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md) | Zbiór strojenia, etykiety dwóch modeli Claude, 3 pozytywne kampanie jednego reklamodawcy |
| 0 z 5 | Ile razy Qwen 9B i 27B wskazały nieoznaczoną współpracę tam, gdzie była | [porównanie D](lanes/2026-11-21-fable-d-porownanie.md) | 5 materiałów, jeden prompt i jedna taksonomia |
| 30/57 vs 13/57 | Typ materiału: E5 wobec słownika na zbiorze odłożonym | [rekord AI](lanes/2026-11-21-fable-ai-inferencja.md) | Jeden oznaczający, przedział ±0,13 |
| 19 · 25 · 11 | Kryteria M2, strony, firmy (3 oddziały zagraniczne) | [rekord E](lanes/2026-11-21-fable-e-m2.md) | Etykiety agenta |
| 12 · 31 · 1 | Wykazy KNF w M3, materiały, sprawa skierowana | [rekord F](lanes/2026-11-21-fable-f-m3.md) | Reguły v2 strojone na tym samym zbiorze |
| 64 | Posty TikTok z 6 polskich profili znalezionych z opisów YouTube | [MONITORING](MONITORING.md) | Sam podpis, bez mowy |
| 116 / 84 | Commity do `fb17d18` i commity z trailerem `Gate:` | `git rev-list --count fb17d18`, `git log --format=%B fb17d18 \| grep -c '^Gate:'` | Brak CI. Trailer jest deklaracją agenta |
| 10 | Błędy złapane przez agenta albo walidator | [PROCES-AI](PROCES-AI.md) | Opisane z dowodem |
| ok. 0,14 USD | Koszt pomiarów modeli przez API w rejestrze | [TEAM_BOARD](../TEAM_BOARD.md) | Pomiar drugiego głosu jeszcze poza rejestrem |

### Liczby, których NIE mówimy

| Liczba | Dlaczego nie |
|---|---|
| „ok. 150 commitów” | W repo jest 116 (do `fb17d18`) |
| „Precyzja 100%” z panelu kalibracji | n = 4 skierowania, przedział 51–100%, zbiór strojenia. Mówimy „4 trafienia, 0 fałszywych alarmów na 26 materiałach” |
| Trafność drugiego głosu (`ai-second-opinion-*.json`) | Pliki niezacommitowane, brak rekordu linii, pomiar w toku |
| Trafność M2 „9 z 12” i M3 „0 FP” jako wynik | Reguły poprawiano na tym samym zbiorze, więc to nie test odłożony |
| Pokrycie polskiego rynku finfluencerów | Nieustalone ([MONITORING](MONITORING.md)). Próba Y niezaliczona |
| Czasy na Macu, zimny start | Nie mierzono na macOS. Zimny start na devboxie trwa 5–7 min (handoff orkiestratora, poza Gitem) |
| Czas E5 na materiał (0,3 s albo 3,0 s) | Pomiar na obciążonym hoście |
| Gemma 3 12B 36/57 | Licencja niepermisywna, model wykluczony z produktu |
| „92 fałszywe wersje” | Brak w repo ([rekord N](lanes/2026-11-21-fable-n-demo.md)) |
| 66/137 wierszy macierzy „zaliczone”, ocena sędziego 6,25 | Stan sprzed domknięcia luk, rejestr otwarty |
| 792 testy (354 + 200 + 192 + 46) | Źródłem jest tylko handoff poza Gitem. Mówimy dopiero po powtórzeniu na kandydacie i zapisie w rekordzie |
| 269 / 241 / 31 / 2 z [demo.md](hackathon/demo.md) | Nieaktualne kolejki z 21:50 UTC |
| Koszt całej budowy z agentami | Nie liczyliśmy go. Mówimy tylko o koszcie pomiaru modeli |

## 10. Trudne pytania jury

| Pytanie | Odpowiedź |
|---|---|
| Gdzie Facebook i Instagram? | Bez tokenu Meta strony kończą się wyzwaniem 403 albo ścianą logowania, a urząd nie może budować na obchodzeniu blokad. Pokazujemy datowaną próbkę, import zapisanej strony i gotowy adapter Ad Library API, który ruszy z tokenem instytucji ([rekord K](lanes/2026-11-21-fable-k-social.md)). |
| Brief mówi: bez płatnych API | Produkt nie woła żadnego płatnego API, a kod odmawia zdalnego backendu (`backend_forbidden`). Przez API tylko wybieraliśmy, który otwarty model postawić lokalnie w Ollamie. Kosztowało to ułamek dolara i jest w rejestrze. |
| Gdzie tu AI, skoro decydują reguły? | Zmierzyliśmy modele jako sędziów: na 5 ukrytych współpracach nie wskazały ani jednej. Dlatego AI jest tam, gdzie wygrywa (E5 rozpoznaje typ materiału 30/57 wobec 13/57 słownika, drugi głos kontroluje decyzję z walidacją cytatu), a oskarżenie zawsze ma jawny cytat. |
| Trafność opiera się na etykietach agentów? | Tak i mówimy to na ekranie. Etykiety zamrożono przed regułami, dwóch oceniających oceniało na ślepo, wszystkie mianowniki są podane. Pierwszym krokiem pilotażu są etykiety ekspertów UKNF na nowych kampaniach. |
| M3 ma jedną sprawę? | Tak, z 31 materiałów jedną. Kontrola ujemna DM BOŚ pokazuje, że system nie flaguje podmiotu z zezwoleniem. Wolimy jedną przesłankę do obrony niż listę zarzutów, a operatora strony system każe ustalić. |
| Czy wolno pobierać napisy z YouTube? | Odkrywanie i metadane idą przez oficjalne API z księgą kwoty. Publiczne napisy pobieramy lokalnie i powoli, co wykracza poza warunki YouTube. Mówimy to wprost. We wdrożeniu potrzebna jest zgoda platformy albo ASR z uprawnionego źródła ([kontrakt H](lanes/2026-11-21-fable-h-kontrakt.md)). |
| Jak to się skaluje? | Dziś działa jedno stanowisko na SQLite. Workery skalujemy przez `--scale worker=N` dzięki dzierżawie zadań. Droga wzrostu to Postgres, magazyn S3 i zewnętrzna kolejka, bez zmiany adapterów ([ARCHITEKTURA](ARCHITEKTURA.md)). |
| Co jest live, a co zapisem? | Pokaz to datowany zapis z 21 XI ze skrótami SHA-256, więc jury zobaczy dokładnie to, co sprawdziliśmy. Tryb `--live` skanuje co 4 h. Na scenie nie skanujemy, żeby nie ryzykować limitu 429. |
| Dlaczego YouTube, skoro brief go nie wymienia? | Brief mówi „m.in. Facebook, Instagram, TikTok”, a finfluencerzy publikują najwięcej na YouTube i tam działa oficjalne API. Z opisów YouTube odkrywamy też ich profile TikTok i Facebook (64 posty TikTok). |
| Co trzeba do pilotażu w UKNF? | Trzy rzeczy: etykiety ekspertów na nowych kampaniach, token Meta Ad Library albo Content Library dla instytucji oraz decyzja o źródle transkrypcji. Stanowisko startuje jedną komendą na sprzęcie urzędu. |

## 11. Czego potrzebuje pitch od interfejsu

Wejście dla agentów UI. Każda pozycja podaje widok, zawartość, dane i to, czego nie pokazywać. **M** znaczy musi, **W** warto, **P** pomiń.

| # | Prio. | Widok i zmiana | Co ma być widać | Skąd dane | Czego NIE pokazywać | Kryterium |
|---|---|---|---|---|---|---|
| 1 | M | **Ekran startowy „Przegląd”** (pierwszy ekran filmu i slajdu 1) | Lejek trzech liczb: „Zebrane materiały”, „Rejestr reklam”, „Do sprawdzenia”, pod nim po jednym kliknięciu do najlepszej sprawy | `queues.all`, `queues.adRegister`, `queues.review` z `/v1/overview?schema=2` | Skanów częściowych, komunikatów technicznych, liczby 46 wierszy źródeł | Technologia, atrakcyjność |
| 2 | M | **Pasek „Droga dowodu”** w karcie M1 (`CaseDetail`) | 6–8 kroków ze stanem: Odkrycie (`discovery[0].method`, `query`, `position`) → Opis (`descriptionDisclosureStatus`, `reviewDecision.claim`) → Flaga platformy (`youtube.paidPromotionFlag`) → Mowa (`mediaCoverage.transcript.state`, zakres) → Kadry (`mediaCoverage.frames.moments`) → Wykaz KNF (`adRelationship.firm.candidates[].name`, `registryId`) → Typ materiału (`model`, gdy jest) → Decyzja (`lastDecision`). Stan kroku: „zbadano, brak oznaczenia”, „**obaliło**” (krok ze stanem w `adRelationship.disclosure.state`), „nie zbadano” | `/v1/cases/{id}?schema=2` | Kroku drugiego głosu ze stanem „wyłączony” jako zielonego. Wolno go pokazać tylko jako szary „wyłączony” albo wcale | Technologia, atrakcyjność |
| 3 | M | **Nagłówek: tryb** | „Odtworzenie skanu z 21 XI” zamiast zielonego „na żywo” w trybie replay | `scans[0].mode`, `origin` | Napisu „na żywo” przy danych z zapisu, bo jury to wychwyci | Gotowość demo, zaufanie |
| 4 | M | **Licznik „Wyjaśnione automatycznie”** w rejestrze reklam i na ekranie startowym | „9 przez mowę · 61 przez flagę platformy · 81 czeka na mowę” z filtrem do listy | Liczba wpisów `/v1/queues/adRegister` po `disclosure.state` (`in_speech`, `in_frame`, `platform_flag`) i `completeReason = transcript_pending`. Najlepiej jako pole w `/v1/overview` (zmiana H) | Słowa „uniewinnione” | Technologia, atrakcyjność |
| 5 | M | **Karta Comparic z kadrem 614 s** | Krok „Mowa 10:14: obaliło” z cytatem i kadr „REKLAMA” | Kadr z cache linii C dołączony do paczki pokazu. Dziś `coverage.gaps` pokazuje `frames not_collected` | Twierdzenia o kadrze, dopóki karta go nie ma | Atrakcyjność |
| 6 | M | **Typ materiału E5 w karcie** albo usunięcie E5 z pitchu | „Typ: opinia · pewność 0,74 · opis, nie wpływa na decyzję” | Pole `model` (`INVESTWATCH_MODEL_ANNOTATE=1`, `analysis/engine.py`). W podglądzie `semantic.status = unavailable` i `analysisVersion.model = null` | Etykiety typu przy pewności < 0,5 (pokazać „nieustalone”) | Zgodność §3.2 |
| 7 | W | **Kalibracja** | Zamiast dużego kafla „Precyzja 100%”: „4 trafienia, 0 fałszywych alarmów na 26 materiałach (20 kampanii)”, przedział w podpisie | `calibration.variants` | Samego „100%” bez n i przedziału | Zgodność, zaufanie |
| 8 | W | **Nazwy zakładek** | „Do sprawdzenia”, „Rejestr reklam”, „Strony firm (M2)”, „Oferty doradcze (M3)”, „Czeka na dane”, „Źródła”, „Kalibracja” | etykiety w `web/src/desk/labels.js` | — | Atrakcyjność |
| 9 | W | **Ukryć na czas pokazu** | — | — | Zakładek „Zamknięte” i „Demo i własne pliki” oraz linii „częściowy: Brak zapisanego odczytu Chromium…” w nagłówku kolejki | Gotowość demo |
| 10 | W | **Karta M2 na telefonie** | Zrzut 390 px z zaznaczoną odległością „864 px od ostrzeżenia” | `m2Card.rows`, `reviewDecision.moments` | Pełnej tabeli 19 wierszy na pierwszym ekranie (lepiej rozwinąć) | Zgodność |
| 11 | W | **Kafle Źródła** | Platforma, metoda (API, monitoring, import, próbka), data i stan | `sources[]`, `sourceHealthDetail` | Kafla „Instagram ads 0” bez wyjaśnienia | Architektura |
| 12 | P | Osobny ekran architektury w pulpicie | — | — | Architektura idzie na slajd, nie do pulpitu | — |
| 13 | P | Drugi głos LLM w karcie | Dopiero po decyzji z sekcji 12, poz. 1 | — | Trafności z niezacommitowanego pomiaru | — |

## 12. Ocena podejścia: co zmienić przed pokazem

| # | Zmiana | Zysk | Koszt | Ryzyko |
|---|---|---|---|---|
| 1 | **Drugi głos: lokalnie albo jako zapisany pomiar, bez przełącznika API.** Jeśli na Macu działa Ollama, wpiąć `second_opinion` dla 4 spraw M1 jako „zgadza się / rozbieżność” z cytatem. Jeśli nie, pokazać zapisany wynik pomiaru na slajdzie | Kryteria 1 i 4 (§3.2: silnik inferencji widoczny w działaniu). Odpowiada J na „za mało AI” | 2–4 h (wpięcie w `engine` u H, pobranie wag na Macu). Domyślny `qwen3.5:27b` ma ok. 17 GB, więc na Macu trzeba użyć Ministral 3 3B albo 8B | Przełącznik API przeczy §5 i kodowi (`backend_forbidden`). Model może się nie zgodzić z regułami na scenie, ale to akurat dobry materiał |
| 2 | **Pasek „Droga dowodu” i licznik obaleń (sekcja 11, poz. 2 i 4)** | Największy zysk na pierwszym ekranie: teza „wielowarstwowa weryfikacja” staje się widoczna | 3–5 h UI plus jedno pole w API | Niski. Dane już są w `/v1/cases` |
| 3 | **Uruchomić E5 w bazie pokazu albo zdjąć go z pitchu.** Dziś `semantic.status = unavailable` | Kryterium 4 (embeddingi, klasyfikator z warstwą wyjściową) | 1 h: pakiety, `INVESTWATCH_SEMANTIC_DIR`, `INVESTWATCH_MODEL_ANNOTATE=1`, przeliczenie | Przeliczenie 1923 materiałów trwa długo. Adnotować tylko kolejkę i rejestr |
| 4 | **Schować zakładki o niskiej wartości** („Zamknięte”, „Demo i własne pliki”) i napis „na żywo” w replayu | Krótsza ścieżka w 120 s, brak pytań o niespójność | 30 min | Żadne, jeśli import Meta zostanie pod „Dodaj dowód” |
| 5 | **Powtórzyć pełne testy i scenariusz na zamrożonym kandydacie** i zapisać wynik w rekordzie (testy, kolejki, czas startu na Macu) | Kryterium 1 (gotowość) i prawo do liczb z sekcji 9 | 1–2 h | Bez tego liczby **[odczyt]** i „792 testy” nie mają pokrycia w wersji, którą zobaczy jury |

Czego nie robić: nie dodawać nowych źródeł ani modułów i nie zmieniać reguł kwalifikacji przed oceną. Każda zmiana reguł unieważnia kalibrację z [WYNIK-M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md).
