# Lane: Fable I · audyt redukcyjny interfejsu (uproszczenie przed pokazem)

- Owner: J (decyzje produktowe) · orkiestracja: Fable · wykonawca: agent I (UX), model claude-opus-5-5
- Branch: hack/integration (tylko dokumentacja; kod w web/ prowadzi J1)
- Worktree: główny checkout
- State: ACTIVE (audyt gotowy, wdrożenie po stronie J1)
- Updated: 2026-11-21 23:30 UTC
- PR / issue: brak

## Acceptance

Zlecenie J: uprościć cały interfejs. Każdy element, dana i informacja ma odpowiedzieć na pytanie, czy pomaga analitykowi podjąć decyzję w minutę albo czy wymaga go brief (§3.3: filtr daty, źródła, ryzyka i modułu, wykres trendu, zmiana statusu, alert WebSocket, panel kalibracji z progiem i FP/FN, otwarta biblioteka UI, propsy). Wynik: inwentarz z werdyktem, lista pól API, docelowy układ, „droga dowodu”, ponumerowana lista zmian z kryterium na zrzucie oraz makiety tekstowe 1440 i 390 px ([makiety](fable-i-uproszczenie/makiety.md)).

Obserwowalny cel po wdrożeniu: na 390 px pierwsza sprawa jest widoczna bez przewijania. Dziś zaczyna się na wysokości ok. 570 z 844 px (zrzut `390-1-kolejka.png`). Na 1440 px karta M1 mieści na pierwszym ekranie powód, dowód, zakres zbadania i przycisk decyzji.

## Claim

- `docs/lanes/2026-11-21-fable-i-uproszczenie.md`
- `docs/lanes/fable-i-uproszczenie/makiety.md`

## Contracts And Dependencies

- Produces: listę zmian dla J1 (§5), listę poprawek API dla H (§2.3), słownik etykiet (§3.4).
- Consumes: API podglądu `http://127.0.0.1:18801` (schemat 2, odczyt 21 XI ok. 22:15 UTC), kod `web/src/desk/*` (stan roboczy hack/integration z niezacommitowanymi zmianami J1), zrzuty `tests/ui/screens/2026-11-21-r3/` (36 plików, r4 jeszcze nie było), kontrakt H §3.4 i §3.16, brief §3.3 i §6, `docs/hackathon/demo.md`. `docs/PITCH.md` §11 (pojawił się w trakcie, zob. §5a).
- Shared-file coordination: brak. Nie zmieniono żadnego pliku w web/ ani tests/.

## Current State

Metoda: przeczytano kod każdego widoku (co faktycznie renderuje), obejrzano wszystkie zrzuty r3 (1440 i 390), pobrano kolejki z API (review 15, adRegister 200 z 290, offersM2 200 z 209, offersM3 22, incomplete 200 z 228, all 50, demo 3) i 14 kart: dwa filmy YouTube z flagą, dwa filmy z rejestru z oznaczeniem w mowie, film z flagą YouTube, TikTok, post IG z rejestru, reklamę Meta, post IG z importu, dwie strony M2 z przesłanką, rdmwm.pl i dwa podmioty uprawnione M3. Przeglądarki nie uruchamiano.

Zastrzeżenie: zrzuty r3 pokazują starszy stan danych (3 sprawy w kolejce, M2 31) i starszą tabelę rejestru. Werdykty dotyczą kodu z dnia audytu, a zrzuty służą do oceny gęstości i układu.

### 1. Inwentarz

Werdykty: **ZOSTAW**, **POŁĄCZ**, **UKRYJ** (pod „Więcej” albo w zwijanym miejscu), **USUŃ**. Kolumna „Kto” oznacza: A-dec (analityk podejmuje decyzję), A-roz (rozumie kontekst), A-naw (nawigacja), Jury (wymóg briefu lub punkt scenariusza pokazu).

#### 1.1 Szkielet i pasek zakładek (`Desk.jsx`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 1 | Nazwa „InvestWatch” | stała | A-naw | ZOSTAW | Jedyny znak marki. |
| 2 | Kropka i napis „na żywo / łączenie…” | stan WebSocket | Jury (alert WS) | ZOSTAW | Widoczny dowód połączenia na żywo, kosztuje jedną linię. |
| 3 | Przycisk „Dodaj dowód” w górnym pasku | trasa `evidence` | A-roz | POŁĄCZ ze Źródłami | Operacja rzadka. Razem z importem Meta tworzy jedną sekcję „Dodaj materiał” w Źródłach. |
| 4 | Pasek 9 zakładek z licznikami | `queues.*` | A-naw | POŁĄCZ w 4 zakładki | Pięć zakładek to stany i moduły tej samej listy (§3.1). |
| 5 | Baner alertu wysokiego ryzyka z „Otwórz” | zdarzenie `high_risk` | Jury | ZOSTAW | Wymóg briefu. Opis „To nie jest ocena prawna” skrócić do tytułu. |
| 6 | Baner powiadomienia o skanie | lokalny | A-roz | ZOSTAW | Krótki i zamykany. |
| 7 | Baner błędu odświeżenia | lokalny | A-roz | ZOSTAW | Mówi, że dane są nieaktualne. |
| 8 | Baner skanu w toku z paskiem postępu | `scans[0]`, `/v1/scans/{id}` | A-roz, Jury | ZOSTAW | Pojawia się tylko w trakcie skanu. |

#### 1.2 Nagłówek kolejki (`QueueScreen`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 9 | H1 z nazwą zakładki | `TITLES` | A-naw | USUŃ (zostaje dla czytnika ekranu) | Powtarza aktywną zakładkę i zabiera 40 px. |
| 10 | Licznik przy H1 | `counts[queue]` | A-naw | USUŃ | Ten sam licznik jest na zakładce i w filtrze stanu. |
| 11 | Zdanie objaśniające zakładkę | `SENTENCE` | A-roz | UKRYJ (ikona „?” przy filtrze stanu) | Czyta się je raz. Na telefonie zajmuje 3 linie. |
| 12 | Linia skanu („Skan: odtworzenie skanu z 21 XI · częściowy: … · 22 materiałów”) | `scans`, `warnings` | A-roz | POŁĄCZ w linię stanu danych | Jedna krótka linia „Dane: replay 21 XI · 1923 mat.” po prawej stronie paska filtrów. Powód stanu częściowego przenieść do Źródeł. |
| 13 | Sparkline trendu i link „Trend: 4 skany…” | `trend.byScan` | Jury | POŁĄCZ z linią stanu danych | Mała linia obok liczby materiałów. Pełny wykres jest w Źródłach. |
| 14 | „Reguły: kwalifikacja D (opis, mowa i kadry), od 21 XI 21:15” | `qualification` | — | USUŃ | Analityk nie decyduje na tej podstawie. Informacja jest w Kalibracji. |
| 15 | „1288 czeka na transkrypcję: Niepełne dane” | `queues.transcriptPending` | A-naw | POŁĄCZ z licznikiem stanu „Niepełne” | Liczba trafia do podpowiedzi przy stanie „Niepełne”. |
| 16 | Baner „N wierszy ma wynik ze starszych reguł” z „Przelicz” | `needsRecalc` | A-dec | ZOSTAW | Warunkowy. Ostrzega przed decyzją na nieaktualnym wyniku. |

#### 1.3 Filtry (`Filters`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 17 | Pole „Szukaj po kanale lub tytule” | `q` | A-naw | ZOSTAW | Scenariusz pokazu go używa (Konopskyy, Comparic). |
| 18 | „Pobierz raport” (CSV) | `/v1/report` | Jury | ZOSTAW jako mały przycisk „Raport” po prawej | Ostatni krok scenariusza 2-minutowego. |
| 19 | Przycisk „JSON” | `/v1/report?format=json` | — | USUŃ | Ten sam raport dla integratora. Wystarczy CSV, a JSON zostaje w API. |
| 20 | Rząd przełączników „Platforma” (6 pozycji) | `platform` | Jury (źródło) | POŁĄCZ w jeden rząd filtrów jako lista „Źródło” | Na 390 px zajmuje 2 linie. Lista rozwijana zajmuje jedną kontrolkę. |
| 21 | Rząd przełączników „Moduł” z licznikami | `module` + 3 zapytania | Jury (moduł) | ZOSTAW jako główny przełącznik | Po scaleniu zakładek to podstawowy podział listy. |
| 22 | Zwijane „Data, siła” | `from`, `to`, `band` | Jury (data, ryzyko) | POŁĄCZ w jeden rząd filtrów | Wymóg briefu nie powinien być schowany za zwijaniem. „Siła” to lista, a „Data” jeden zakres. |
| 23 | Wybór pola daty („Odczytano / Opublikowano”) | `dateField` | A-roz | UKRYJ w zakresie daty | Domyślnie publikacja, a bez niej odczyt. Przełącznik zostaje w okienku zakresu. |
| 24 | „Rejestr: potwierdzone / do potwierdzenia” | `section` | A-dec | ZOSTAW (w Rejestrze, jako przełącznik) | Rozdziela pewne wpisy od 45 kandydatów bez oznaczenia. |
| 25 | „Wyczyść filtry (n)” | — | A-naw | ZOSTAW | Pojawia się tylko przy aktywnych filtrach. |
| 26 | Stopka „Pokazano N z M” i „Pokaż więcej” | `nextCursor`, `total` | A-naw | ZOSTAW | Stronicowanie po stronie API. |

#### 1.4 Wiersz kolejki „Co wymaga sprawdzenia” (`CaseList`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 27 | Tytuł materiału (link) | `title` | A-naw | ZOSTAW | Na desktopie wystarczy 1 linia. |
| 28 | Plakietka modułu | `module` → `MODULE_NAME` | A-roz, Jury | ZOSTAW | Nazwy według słownika §3.4. |
| 29 | Linia „platforma · kanał · data” | `platform`, `creatorName`, `publishedAt` | A-roz | ZOSTAW | Dla M2 i M3 zamiast kanału pokazać domenę. |
| 30 | Plakietki pod tytułem (pochodzenie, import, przeliczenie, nowa wersja) | `origin`, `importLabel`, `needsRecalc`, `pendingReReview` | A-dec | POŁĄCZ w jedną plakietkę stanu | Zostają tylko „nowa wersja po decyzji” i „do przeliczenia”. „Import ręczny” wynika z filtra źródła. |
| 31 | Kolumna „Firma” | `firm` | A-dec | ZOSTAW (marka zamiast pełnej nazwy z wykazu) | „XTB Ltd / XTB S.A.” i „DOM MAKLERSKI BANKU OCHRONY ŚRODOWISKA S…” nie mieszczą się w kolumnie (§2.3). |
| 32 | Kolumna „Dlaczego tutaj” | `firstReason` | A-dec | ZOSTAW | 1 linia, do 90 znaków, bez wstępu „Przesłanka do sprawdzenia:”. |
| 33 | Kolumna „Siła” (pasmo i „95 z 100 pkt”) | `reviewScore`, `band` | Jury (ryzyko) | POŁĄCZ w jedną plakietkę „mocna 95” | Dwie linie dla jednej wartości. |
| 34 | Kolumna „Dowód” („opis ↗”, „od 0:15 ↗”) | `firstMoment` | A-dec | USUŃ | Dla 10 z 15 spraw kolejki jest pusta (`firstMoment` null w M2). Dowód otwiera karta. |
| 35 | Wiersz na telefonie: „moduł · platforma · firma / Siła: … / powód” | jak wyżej | A-dec | POŁĄCZ | Kolejność: tytuł, „mocna 95 · XTB · YouTube”, powód. To 3 linie zamiast 4. |

#### 1.5 Rejestr reklam (`RegisterTable`, `RegisterList`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 36 | Materiał i kanał | `title`, `creatorName` | A-naw | ZOSTAW | |
| 37 | Kolumna „Firma” („nie ustalono”) | `firm` | A-dec | ZOSTAW | Brak firmy dotyczy 12 z 200 wierszy. |
| 38 | Kolumna „Platforma” | `platform` | A-roz | POŁĄCZ z linią pod tytułem | Ta sama konwencja co w kolejce. |
| 39 | „Typ ujawnienia” (rodzaj i miejsce) | `disclosure.kind/state/where/atSec` | A-dec, Jury | ZOSTAW | Najważniejsza informacja rejestru. Etykieta według słownika („w mowie 11:38”). |
| 40 | Cytat ujawnienia pod typem | `disclosure.text` | A-dec | POŁĄCZ z typem w jednej linii | „w opisie: „[współpraca z XTB]””, ucięte do 60 znaków. |
| 41 | Plakietka „do potwierdzenia” | `adRegistry` | A-dec | ZOSTAW | Przy 45 z 200 wierszy to jedyny sygnał, że wpis nie jest pewny. |
| 42 | „Kiedy”: data, „odczyt” albo „≈ data” z plakietką „data szacowana” | `publishedAt`, `publishedAtDerived` | Jury (data) | POŁĄCZ w jeden tekst | Na przykład „≈ 12 lis”, a uwaga w podpowiedzi. Plakietka zajmuje drugą linię. |
| 43 | Na telefonie trzecia linia `registryInfo.summary` | `adRegistryInfo.summary` | — | USUŃ | Powtarza typ i cytat (np. „Reklama lub współpraca oznaczona w opisie: „#współpraca”” w 13 wierszach). |

#### 1.6 Oferty M2 i M3 (`OffersTable`, `OffersList`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 44 | Tytuł strony lub oferty | `title` | A-naw | ZOSTAW | |
| 45 | Link z domeną | `url` | A-roz | POŁĄCZ z linią pod tytułem (bez linku) | Stronę otwiera przycisk w karcie. Link w tabeli kusi do wyjścia z pulpitu. |
| 46 | Plakietka „import ręczny” | `importLabel` | — | USUŃ z wiersza | Pochodzenie należy do sekcji „Więcej” karty i do filtra źródła. |
| 47 | Plakietka „kontrola: podmiot uprawniony” | wyrażenie regularne na `reason` | A-dec, Jury | ZOSTAW, ale z pola API | Dziś rozpoznawana z tekstu (`licensedControl`). API ma `identity.licensed`, więc powinno je podać w wierszu (§2.3). |
| 48 | Platforma dla wierszy spoza WWW | `platform` | A-roz | POŁĄCZ z 45 | |
| 49 | „Firma” / „Podmiot” | `firm`, `creatorName` | A-dec | ZOSTAW | |
| 50 | „Przesłanka” / „Powód” | `firstReason`, `reason` | A-dec | ZOSTAW | W 183 ze 200 wierszy M2 jest pusta (posty FB/IG), co jest argumentem za §3.1. |
| 51 | „Siła” | `reviewScore`, `band` | Jury | POŁĄCZ (plakietka) | |
| 52 | „Stan” (trasa) | `route` | A-dec | ZOSTAW | Etykiety ze słownika. Dziś „bez przesłanki” w liście i „Bez sygnału” na przycisku decyzji. |
| 53 | Wiersz na telefonie: kanał i siła, bez powodu | `creatorName`, siła | A-dec | POŁĄCZ z szablonem wiersza kolejki | Na telefonie brakuje powodu, czyli jedynej treści decyzyjnej. |

#### 1.7 Niepełne, Zamknięte, Demo i pusty panel

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 54 | Kolumna „Czego brakuje” | `completeReason` → `COMPLETE_REASON` | A-dec | ZOSTAW | Na zrzucie r3 widać jednak 8 razy „Brak wystarczającego zakresu do oceny” (wartość zastępcza), czyli brak powodu w danych. |
| 55 | Kolumna „Decyzja” (zamknięte) | `lastDecision.note` | A-dec | ZOSTAW | |
| 56 | Kolumna „Opis” (demo) | `reason` | A-roz | ZOSTAW | |
| 57 | Pusty stan z przyciskami „Rejestr reklam” i „Niepełne dane” | `counts` | A-naw | ZOSTAW | Tekst skrócić do jednego zdania. |
| 58 | Pusty prawy panel „Wybierz materiał” | — | A-naw | ZOSTAW | |

#### 1.8 Karta M1: nagłówek (`CaseDetail`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 59 | Plakietka „Siła: mocna · 95/100” | `reviewScore` | A-dec, Jury | ZOSTAW | Format według słownika: „mocna 95”. |
| 60 | Plakietka statusu („Nowa”, „W kontroli”) | `status` | Jury (status) | ZOSTAW tylko dla statusu innego niż „Nowa” | Wszystkie 1923 sprawy mają status „Nowa”, więc dziś plakietka niczego nie odróżnia. |
| 61 | Plakietka „odtworzenie skanu z 21 XI” | `origin`, `observedAt` | — | USUŃ | Każda realna sprawa w pokazie to replay. Dla demo i pliku własnego zostaje baner. |
| 62 | Plakietka „import ręczny” | `importLabel` | A-roz | UKRYJ (Więcej › Szczegóły) | Pochodzenie, nie decyzja. |
| 63 | „Do ponownego przeliczenia” | `needsRecalc` | A-dec | ZOSTAW | Warunkowa. |
| 64 | „Nowa wersja po decyzji” | `pendingReReview`, `reviewStale` | A-dec | ZOSTAW | Warunkowa. |
| 65 | „Wróć do listy” | — | A-naw | ZOSTAW | |
| 66 | Tytuł H2 | `title` | A-roz | ZOSTAW | |
| 67 | Podtytuł „kanał · firma” | `creatorName`, `relationship.firmName` | A-roz | POŁĄCZ z linią metadanych | Jedna linia: autor · platforma · data · zasięg · firma (pozycje 87–91). |
| 68 | Przycisk „Otwórz w filmie od 0:15” | `proofOf` | A-dec, Jury | ZOSTAW | Krok scenariusza 0:00–0:25. |
| 69 | Przycisk „Decyzja” (przewija) | — | A-naw | USUŃ na desktopie | Decyzja ma być widoczna bez przewijania (§3.2). Na telefonie zostaje stopka. |

#### 1.9 Karta M1: treść

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 70 | Baner „Materiał syntetyczny / Plik operatora” | `origin` | A-roz | ZOSTAW | Chroni przed pomyleniem demo z rynkiem. |
| 71 | Baner „Wynik ze starszej wersji analizy” | `needsRecalc` | A-dec | ZOSTAW | Warunkowy. |
| 72 | Plakietka trasy w „Dlaczego tutaj” („do sprawdzenia”) | `route` | — | USUŃ, gdy trasa to `refer` | Kolejka i stan już to mówią. Dla innych tras zostaje. |
| 73 | 3 punkty „Dlaczego tutaj” | `reviewDecision.reasons[0..2]` | A-dec | ZOSTAW | Każdy do 120 znaków. Trzeci punkt M1 (wykaz KNF) ma dziś 260 znaków i przenosi się do drogi dowodu (krok „Firma”). |
| 74 | „Pokaż wszystkie (4)” | `reasons[3]` | A-roz | POŁĄCZ z jedną linią „Możliwe wyjaśnienie: …” | Czwarty punkt to `alternative`, powtórzony też w Więcej › Punktacja. Wystarczy raz, widocznie, bo uczciwość karty to argument pokazu. |
| 75 | Kafel „Momenty do sprawdzenia” (tabela Czas, Co, Otwórz) | `moments`, `evidence` | A-dec | POŁĄCZ w kafel „Dowód” | Do 3 wierszy: czas lub „opis”, cytat, link. |
| 76 | Etykieta momentu („Nieoznaczona współpraca z firmą inwestycyjną”, „Dowód relacji handlowej”) | `moments[].label` | — | USUŃ | Powtarza nazwę wymogu. W wierszu najważniejszy jest cytat. |
| 77 | Miniatury kadrów z czasem | `evidence[kind=frame]` | A-dec | ZOSTAW (w „Dowodzie”) | Najmocniejszy obraz karty dla jury. |
| 78 | „Tekst z obrazu nie jest odczytywany automatycznie.” | stała | A-roz | POŁĄCZ z drogą dowodu („Kadry ✓ 3 · bez OCR”) | |
| 79 | Zdanie zakresu `coverage.label` | `coverage.label` | — | USUŃ | Powtarza tabelę pod spodem. |
| 80 | Zdanie o ograniczeniu platformy (TikTok, FB/IG) | stała | A-roz | POŁĄCZ z drogą dowodu | Kroki „Mowa ○ niedostępna (TikTok)” mówią to samo krócej. |
| 81 | Tabela „Co zbadano” (Opis, Mowa, Kadry, Oznaczenie YouTube) | `coverage.modalities` | A-dec | POŁĄCZ w drogę dowodu (§4) | Dziś zielone „zbadano” stoi obok „brak” (flaga YouTube) i czyta się jak wynik pozytywny. |
| 82 | „Luki: …” | `coverage.gaps` | — | USUŃ | Powtarza wiersze z luką. |
| 83 | Baner „Wniosek o braku oznaczenia wstrzymany” | `coverage.blocksConclusion` | A-dec | POŁĄCZ z ostatnim krokiem drogi dowodu | Pełny baner dla jednego zdania. |
| 84 | Kafel „Firma” (Firma, Typ podmiotu, Wykaz KNF) | `adRelationship.firm` | A-dec | POŁĄCZ z nagłówkiem i krokiem „Firma” | „XTB · 2 wpisy KNF” mieści się w kroku. |
| 85 | Zwijane „Wpisy w wykazie KNF” | `firm.candidates` | A-roz | UKRYJ (Więcej › Szczegóły) | |
| 86 | Wariant kafla firmy (Firma, Rola, Podstawa) dla postów | `firmRelation` | A-roz | POŁĄCZ z nagłówkiem | „XTB (reklamodawca)”. |
| 87 | „Kanał: … · znany / nowy w skanie” | `creator` | A-roz | POŁĄCZ z linią metadanych | |
| 88 | „Zasięg filmu” | `reach` | A-roz | POŁĄCZ z linią metadanych | Jedna liczba: „1 330 wyśw.”. |
| 89 | „Zasięg kanału” | `creator.reach` | — | USUŃ | W twórcach z próbki `subscriberCount.state = not_collected`, więc pole wyświetla „Zasięg nieznany”. |
| 90 | „Jak odkryto” | `discovery[0]` | A-roz, Jury (odkrywanie) | UKRYJ (Więcej › Szczegóły) | Droga odkrycia jest też w tabeli twórców w Źródłach. Wartość zastępcza „Droga odkrycia sprzed rozszerzenia kontraktu” trzeba usunąć. |
| 91 | „Opublikowano” z plakietką i notą „data szacowana” | `publishedAt`, `publishedAtDerived` | A-roz | POŁĄCZ z linią metadanych | „≈ 12 lis”, a nota w podpowiedzi. |
| 92 | „Ostatnia: …, data · notatka” | `lastDecision` | A-dec | ZOSTAW | |
| 93 | 4 przyciski rodzaju decyzji | `RESOLUTIONS` | A-dec, Jury (status) | ZOSTAW | Etykieta „Bez sygnału” zmienia się na „Bez przesłanki”. |
| 94 | Podpowiedź pod przyciskami („Wybierz rodzaj decyzji.”) | `RESOLUTIONS[].hint` | — | USUŃ | Przenieść do podpowiedzi przycisków. |
| 95 | Pole „Uzasadnienie decyzji” | — | A-dec | ZOSTAW | |
| 96 | „Zapisz decyzję” | `POST decision` | A-dec | ZOSTAW | |
| 97 | „System nie rozstrzyga o naruszeniu; to Ty decydujesz…” | stała | Jury | POŁĄCZ w jedną stopkę strony | Dziś pojawia się w karcie, w banerze alertu, w punktacji i w kalibracji. |
| 98 | Zwijane „Więcej: historia, punktacja, źródło, surowe dane” | — | A-roz | ZOSTAW (3 zakładki) | |
| 99 | Więcej › Historia | `history` | A-roz | ZOSTAW | |
| 100 | Więcej › Punktacja (składniki i punkty) | `reviewScore.components` | Jury (wyjaśnialność) | ZOSTAW | |
| 101 | Nota o skali punktów | `SCALE_NOTE` | A-roz | ZOSTAW (w Punktacji) | |
| 102 | „Możliwe wyjaśnienie” i „Kontrargument” w Punktacji | `alternative`, `counterEvidence` | A-dec | POŁĄCZ | Wyjaśnienie trafia do „Dlaczego tutaj” (74). Kontrargumenty zostają w Punktacji. |
| 103 | Więcej › Źródło (pochodzenie, odczyt, droga odkrycia, pełny opis) | `origin`, `discovery`, `description` | A-roz | ZOSTAW jako „Szczegóły” | Do tej zakładki trafiają też 62, 85 i 90. |
| 104 | Więcej › Surowe dane (identyfikator, rewizja, wariant, skan, adres) | `id`, `revision`, `activeVariant`, `scanId` | — | USUŃ zakładkę | Identyfikator i adres przenieść do „Szczegółów”. Reszta służy deweloperowi. |
| 105 | Stopka na telefonie „Momenty / Decyzja” | — | A-naw | ZOSTAW | Pierwszy przycisk nazwać „Dowód”. |

#### 1.10 Karta reklamy Meta i postu (`AdTile`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 106 | Treść reklamy (cytat) | `adBody` | A-dec | ZOSTAW jako „Dowód” | |
| 107 | „Reklamodawca” | `author` | A-roz | POŁĄCZ z nagłówkiem | |
| 108 | „Emisja” z datami i stanem | `adDeliveryStartDate/StopDate`, `adStatus` | A-roz, Jury (data) | ZOSTAW (jedna linia w „Dowodzie”) | |
| 109 | „Wezwanie (CTA)” | `callToAction` | A-roz | UKRYJ (Szczegóły) | |
| 110 | „Domena linku” („brak w zapisanym pliku”) | `linkDomain` | — | UKRYJ (Szczegóły) | W próbce zwykle pusta. |
| 111 | „Wersje reklamy” | `versionsCount` | — | UKRYJ (Szczegóły) | |
| 112 | „Zasięg w UE” | `reach` | A-roz | POŁĄCZ z linią metadanych | |
| 113 | Nota importu | `importNote` | — | UKRYJ (Szczegóły) | |

#### 1.11 Karta M2 (`CardM2.jsx`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 114 | Plakietka „8 z 19 wymaga uwagi” | `checks` | A-dec | POŁĄCZ z krokiem „Kryteria” drogi dowodu | |
| 115 | „Wynik reguł 95 z 100 pkt · próg skierowania 30. To przesłanki…” | `m2Card.score/threshold` | — | USUŃ | Siła jest w nagłówku, a zastrzeżenie w stopce. Próg należy do Kalibracji. |
| 116 | Tabela przesłanek (Kryterium, Pomiar i cytat, Zrzut), wszystkie 8 | `checks[state=przesłanka]` | A-dec | POŁĄCZ z „Dlaczego tutaj” i „Dowodem” | Na wierzchu 3 przesłanki, te same co w `reasons`. Pozostałe 5 trafia pod „+5 przesłanek”. |
| 117 | „kryterium 3” na telefonie | `id` | — | USUŃ | Numer katalogu nic nie mówi analitykowi. |
| 118 | Miniatury zrzutów komputer i telefon z powiększeniem | `measurements[].screenshot` | A-dec, Jury | ZOSTAW | Najsilniejszy dowód M2. |
| 119 | Zwijane „Wszystkie 19 kryteriów wg stanu” | `checks` | A-roz | UKRYJ (Więcej › Kryteria) | Pełna lista to zakres badania M2. |
| 120 | Zdanie zakresu `coverage.label` | `coverage.label` | — | USUŃ | Powtarza tabelę widoków. |
| 121 | „Odczytano” | `m2Card.observedAt` | A-roz | POŁĄCZ z linią metadanych | |
| 122 | „Strona” z linkiem | `m2Market.finalUrl` | A-naw | POŁĄCZ z przyciskiem „Otwórz stronę” | |
| 123 | Tabela widoków (Widok, Elementy, Baner cookies) | `m2Market.views` | A-roz | POŁĄCZ z krokiem „Render” | „Render ✓ komputer + telefon · cookies odrzucone”. Kolumnę „Elementy” (318) usunąć. |
| 124 | „Luki: …” | `coverage.gaps` | — | USUŃ | |
| 125 | Kafel „Firma” (nazwa, typ, wykaz, numer, strona firmy) | `m2Card.firm`, `m2Market.firm` | A-dec | POŁĄCZ z nagłówkiem i krokiem „Firma” | Numer wpisu i stronę firmy przenieść do „Szczegółów”. |
| 126 | „Dlaczego tutaj” na karcie M2 | `reasons` | A-dec | POŁĄCZ z 116 | Trzy punkty to te same trzy przesłanki co w tabeli, więc są pokazane dwa razy. |

#### 1.12 Karta M3 (`CardM3.jsx`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 127 | Tabela „Cztery cechy rekomendacji” (Cecha, Stan, Cytat, Kontrargument) | `checks` | A-dec | POŁĄCZ w „Dowód” | 4 wiersze: cecha, stan, cytat w 1 linii, link podstrony. Kontrargument trafia do „Szczegółów”. |
| 128 | Link podstrony przy cesze | `checks[].url` | A-dec | ZOSTAW | |
| 129 | Plakietka uprawnień („brak danych podmiotu na stronie”) | `identity.state` | A-dec, Jury | POŁĄCZ z nagłówkiem i krokiem „Wykazy KNF” | |
| 130 | `identity.label` obok plakietki | `identity.label` | — | USUŃ | Powtarza plakietkę, chyba że wnosi nazwę mocodawcy (agent: „Ipopema Securities S.A.”). Wtedy trafia do kroku. |
| 131 | Baner „Ostrzeżenie publiczne KNF” | `identity.knfWarning` | A-dec | ZOSTAW | Warunkowy i krytyczny. |
| 132 | Baner „Awaria rejestru” | `identity.registerFailures` | A-dec | ZOSTAW | Warunkowy. |
| 133 | Tabela trafień w wykazie (wpis, wykaz, w imieniu) | `identity.matches` | A-dec | POŁĄCZ z krokiem „Wykazy KNF”, a tabelę UKRYJ | Jedno trafienie wystarczy jako tekst. |
| 134 | „Dane podmiotu na stronie” (nazwa, KRS, NIP, REGON) | `identity.operator` | A-dec | POŁĄCZ z krokiem „Podmiot na stronie” | Błąd: UI czyta `operator.name`, a API daje `names`, więc nazwa się nie wyświetla (§2.3). |
| 135 | „Ostrzeżenia KNF” z kropką | `knfWarning.state` | A-dec | POŁĄCZ z drogą dowodu | |
| 136 | Zwijane „Przejrzane wykazy (12…)” | `identity.reviewedRegisters` | A-roz | UKRYJ (Szczegóły) | |
| 137 | „Brak wpisu nie dowodzi braku uprawnień…” | stała | A-dec | POŁĄCZ z podpowiedzią kroku „Wykazy KNF” | |
| 138 | Tabela podstron i czasu odczytu | `offer.pages` | A-roz | POŁĄCZ z krokiem „Tekst ✓ 2 podstrony”, a tabelę UKRYJ | |
| 139 | Kafel „Czego brakuje” z zastrzeżeniem | `reviewDecision.missing` | A-dec | POŁĄCZ z „Dlaczego tutaj” | Dla trasy `complete` lista braków to powód. |
| 140 | Podtytuł „domena · plakietka” | `offer.domain`, `identity.badge` | A-roz | ZOSTAW (linia metadanych) | |

#### 1.13 Źródła (`Sources.jsx`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 141 | H1 i podsumowanie zdrowia źródeł | `sourceHealthSummary` | A-roz, Jury | ZOSTAW | Jedna linia. |
| 142 | Baner skanu w toku | `scans[0]` | A-roz | ZOSTAW | |
| 143 | Karta trendu (dwa wykresy: materiały i skierowania) | `trend` | Jury (wykres trendu) | ZOSTAW | Wymóg briefu. Przenieść na górę strony. |
| 144 | „Jeden dzień danych: słupki pokazują kolejne skany…” | stała | — | USUŃ | Oś X już to pokazuje. |
| 145 | Zwijane „Dane wykresu (tabela)” | `trend` | A-roz | ZOSTAW (zwinięte) | Dostępność. |
| 146 | 7 kafli platform po 4–6 wierszy, „Następny krok” i tabela dróg | `sources`, `sourceHealthDetail`, `paths` | A-roz, Jury | POŁĄCZ w jedną tabelę | Kolumny: Platforma, Stan, Materiały, Konta, Ostatni odczyt, Ograniczenie (2–4 słowa). Szczegóły po rozwinięciu wiersza. Dziś kafle zajmują 2 ekrany na 1440 px. |
| 147 | Wiersze kwot kluczy YouTube | `quota.keys` | A-roz | UKRYJ (w rozwinięciu wiersza YouTube) | |
| 148 | „Następny krok” Meta ze ścieżką `~/.config/investwatch/meta.token (kroki: docs/lanes/…)` | stała w kodzie | — | USUŃ ścieżki | Ścieżka pliku i repozytorium nie powinna trafić przed jury. Wystarczy „Potrzebny token Ad Library API”. |
| 149 | Karta importu Meta | `MetaImport` | A-roz, Jury (krok 6 w 5 min) | POŁĄCZ z „Dodaj dowód” w zwijaną sekcję „Dodaj materiał” | |
| 150 | Wykres „Materiały per platforma” (5 zapytań `limit=1`) | `/v1/queues/all?platform=` | — | USUŃ | Te same liczby są w kolumnie tabeli platform. Trend spełnia wymóg wykresu. |
| 151 | Karta „Skan materiałów” (linia skanu, początek, koniec, statystyka źródeł, „Do sprawdzenia”) | `scans` | A-roz | POŁĄCZ w jedną linię nad przyciskami skanu | „Ostatni skan: replay 21 XI 22:00 · 46 źródeł: 46 działa · 7 skierowań”. |
| 152 | Lista „Zablokowane dostępy” | `accessBlocked` | A-roz, Jury | POŁĄCZ z kolumną „Stan” tabeli platform | |
| 153 | Pasek „Kroki ostatniego skanu” poza skanem | `/v1/scans/{id}` | — | USUŃ | Pasek ma sens tylko w trakcie skanu. |
| 154 | Zwijane „Kroki skanu” | `steps` | A-roz | UKRYJ (zostaje zwinięte) | |
| 155 | Przyciski „Skanuj na żywo”, „Odtwórz skan”, „Przelicz materiały” | `POST /v1/scans` | A-roz, Jury | ZOSTAW | Dziś przyciskiem głównym jest „Przelicz”, a powinien być „Skanuj na żywo”. |
| 156 | Tabela twórców i drogi odkrycia (25 z 477) | `creators` | Jury (odkrywanie, M1) | ZOSTAW | Dodać filtr „nowi w skanie”. Kolumna zasięgu dla FB/IG pokazuje „Zasięg nieznany”, więc pustą wartość zastąpić „—”. |

#### 1.14 Kalibracja (`Calibration.jsx`)

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 157 | H1, przełącznik modułu i zdanie objaśniające | `MODULE_NAME` | Jury | ZOSTAW H1 i przełącznik, USUŃ zdanie | |
| 158 | Żółty baner „Oceny agentów, nie walidacja ekspercka” | `disclaimer` | Jury (uczciwość) | ZOSTAW, skrócony do 1 linii | Scenariusz pokazu go cytuje. Na 390 px zajmuje dziś 6 linii. |
| 159 | Tytuł karty z plakietkami wariantu i „obowiązuje 60 pkt” | `variant`, `threshold` | — | USUŃ plakietki | „obowiązuje 60” jest już znacznikiem na suwaku. |
| 160 | Suwak progu z opisem | `threshold` | Jury (wymóg) | ZOSTAW | Opis skrócić do 1 linii. |
| 161 | 7 kafli KPI (TP, FP, TN, FN, Precyzja, Pełność, Koszt) | `/v1/calibration` | Jury (FP/FN) | POŁĄCZ: FP i FN jako duże kafle z różnicą, TP/TN w macierzy 2×2, Precyzja i Pełność w jednym kaflu, Koszt w jednej linii | Brief wymaga FP wobec FN. Na 390 px 7 kafli zajmuje 2 ekrany. |
| 162 | Zdanie o skutku dla kolejki | `queueEffect` | Jury | ZOSTAW | Pokazuje, że próg zmienia kolejkę. |
| 163 | „Zastosuj”, „Potwierdź”, „Anuluj”, „Wróć do obowiązującego” | `PUT threshold` | A-dec | ZOSTAW | |
| 164 | Nota „Za mało skierowań do oceny precyzji…” | `tp+fp` | Jury | POŁĄCZ z żółtym banerem | |
| 165 | Wykres FP i FN w funkcji progu | `/v1/calibration` × 9 | Jury | ZOSTAW | |
| 166 | Tekst pod wykresem | stała | — | USUŃ | |
| 167 | Tabela porównania wariantów | `variants` | Jury (punkt „poprzednie reguły: FP 7”) | POŁĄCZ w jedną linię pod KPI | „Poprzednie reguły przy tym progu: FP 7, FN 4”. Tabela trafia pod „Więcej”. |
| 168 | Kafel „Aktywny wariant” (od, uwaga, pomiar ze ścieżką repo, zatwierdził) z historią | `qualification` | — | UKRYJ (Więcej › Historia ustawień) | Ścieżka `fixtures/validation/…@463cceb` i „Fable (orkiestrator)” to język zespołu, nie UKNF. |
| 169 | Kafel „Historia progu” z „Przywróć” | `/v1/threshold/history` | A-roz | UKRYJ (Więcej › Historia ustawień) | |
| 170 | Kafel „Zbiór etykiet” | `labelTarget`, `n`, `groups`, `split` | Jury | POŁĄCZ z żółtym banerem | „26 materiałów, 20 kampanii, oceny agentów, zbiór strojenia”. |
| 171 | Tabela przeoczeń i fałszywych alarmów przy progu | `errors` | Jury | ZOSTAW | Konkretne przykłady FP/FN z linkiem. |

#### 1.15 Dodaj dowód i Demo

| # | Element | Dane | Kto | Werdykt | Uzasadnienie |
|---|---|---|---|---|---|
| 172 | Formularz pliku (plik, tytuł, opis, wyślij, „Zobacz Demo…”) | `POST /v1/uploads` | A-roz | POŁĄCZ ze Źródłami › Dodaj materiał | |
| 173 | Trzy kroki instrukcji zapisu strony Meta | stała | A-roz | UKRYJ (zwijane „Jak zapisać stronę”) | |
| 174 | Zakładka „Demo i własne pliki” | `queues/demo` | A-roz | POŁĄCZ z filtrem stanu „Demo” | |

**Rozkład werdyktów (174 elementy):** ZOSTAW 73, POŁĄCZ 58, UKRYJ 16, USUŃ 27 (policzone skryptem z kolumny werdyktu). Poza ZOSTAW jest 101 z 174 elementów, czyli 58%. Elementy z dwoma werdyktami (157 ZOSTAW i USUŃ, 133 POŁĄCZ i UKRYJ) liczono według pierwszego.

### 2. Struktury JSON

#### 2.1 Wypełnienie pól wiersza kolejki (próbka z API, 21 XI ok. 22:15 UTC)

Liczba rekordów z niepustą wartością / liczba rekordów w próbce.

| Pole | review (15) | adRegister (200) | offersM2 (200) | offersM3 (22) | incomplete (200) | Co z tym w UI |
|---|---|---|---|---|---|---|
| `firstReason` | 15 | 44 | 17 | 22 | 89 | Kolumna powodu jest pusta w 78% rejestru i 92% M2. Rejestr pokazuje typ ujawnienia, ale M2 wyświetla „—”. |
| `reason` | 15 | 200 | 17 | 22 | 200 | Dla 183 postów FB/IG w M2 pole jest null, więc wiersz nie ma treści decyzyjnej. |
| `reviewScore` / `band` | 15 / 15 | 96 / 96 | 200 / 200 | 22 / 22 | 89 / 89 | Pustka w M1 to `withheld`, uczciwa. W M2 wiersz ma 20 pkt, a karta `reviewScore: null` (niespójność, §2.3). |
| `score` (stare reguły) | 15 | 200 | 200 | 22 | 200 | UI go nie pokazuje, ale ten sam wiersz niesie `score: 24` i `reviewScore: 100`. Usunąć ze schematu 2. |
| `firstMoment` | 5 | 44 | 0 | 17 | 89 | Kolumna „Dowód” jest pusta w większości. Usuwamy ją (34). |
| `disclosure` | 4 | 200 | 0 | 0 | 184 | Pełne tam, gdzie potrzebne (rejestr). |
| `adRegistryInfo.summary` | 4 | 200 | 0 | 0 | 184 | Powtarza `disclosure.text`. UI nie powinien go pokazywać (43). |
| `firm` | 15 | 188 | 200 | 22 | 200 | Pełne, ale w niespójnym formacie (§2.3). |
| `publishedAt` | 4 | 195 | 183 | 0 | 179 | Brak dla WWW to stan poprawny, wtedy data odczytu. |
| `publishedAtDerived` | 0 | 5 | 0 | 0 | 5 | Tylko TikTok. Plakietka zbędna (42). |
| `completeReason` | 0 | 134 | 0 | 16 | 200 | Pełne w „Niepełnych”. M2 (`insufficient`) go nie ma, stąd zastępcze „Brak wystarczającego zakresu do oceny.” |
| `importLabel` | 0 | 0 | 6 | 0 | 0 | Rzadkie, do sekcji „Szczegóły”. |
| `priority`, `transcriptState` | 4 | 200 | 0 | 0 | 184 | UI nie pokazuje. Dobrze. |
| `origin` | zawsze `replay` | jw. | jw. | jw. | jw. | Karta pokazuje jednak plakietkę „odtworzenie skanu” (61). |
| `revision`, `version`, `queues`, `queueEligible`, `needsRecalc`, `pendingReReview`, `reviewStale`, `creatorId` | pełne | pełne | pełne | pełne | pełne | Techniczne. UI pokazuje tylko flagi warunkowe. Dobrze. |
| `lastDecision` | 0 | 0 | 0 | 0 | 0 | Brak zamkniętych spraw w bazie. |

Przynależność do kolejek: 134 z 200 wierszy rejestru jest jednocześnie w „Niepełnych”, a 2 w „Co wymaga sprawdzenia”. „Niepełne” to w 92% (184 z 200) filmy z rejestru czekające na transkrypcję. Ta sama sprawa występuje więc w 2–3 zakładkach, co przemawia za filtrem stanu zamiast osobnych zakładek.

#### 2.2 Pola, które UI pokazuje, a nie powinien, i odwrotnie

UI pokazuje, a nie powinien:

- `origin` jako plakietkę w karcie, `importLabel` w wierszach i karcie, `m2Card.score` i `threshold` w karcie M2, `coverage.label` nad tabelą zakresu, `coverage.gaps` pod nią, `adRegistryInfo.summary` w rejestrze na telefonie, `creator.reach` („Zasięg nieznany”), `reach.source` w nawiasie („(tiktok_embed)”, „(data_api)”), `m2Market.views[].blocks`, `checks[].id` („kryterium 3”), `identity.label` obok plakietki, `qualification.validationRef` i `validatedBy` (ścieżki repo, „Fable”), `activeVariant`, `revision`, `scanId` w „Surowych danych”.
- Teksty pomiarów M2 w języku narzędzia: „11542.5 px dalej (próg: pół ekranu, 450 px)”, „y=12085.7 px”, „desktop”, „phone”, „FOG-PL 18,5”, „Przekroczone: fog, longShare” (`checks[].evidence`). Do „Dowodu” trafia zdanie analityczne, a liczby pod „Więcej”.

UI nie pokazuje, a powinien:

- `identity.licensed` w wierszu M3. Dziś kontrola ujemna jest rozpoznawana wyrażeniem regularnym na `reason`.
- `identity.operator.names` w karcie M3 (błąd klucza, 134).
- `relationships[]` z drugą firmą w tym samym materiale. Przykład: `youtube:7M0rC6-Rueo` ma relację z Pekao i z XTB, a karta pokazuje tylko XTB. Wystarczy „+1 firma” w kroku „Firma”.
- `reviewDecision.missing[]` dla M1 (`["pełna transkrypcja mowy"]`). Dziś widać tylko w zdaniu `reason`.
- `adRegistry.state` w karcie M1 (potwierdzona / do potwierdzenia). Karta nie mówi, czy materiał jest w rejestrze.

#### 2.3 Niespójności i poprawki

Po stronie UI (J1):

1. Nazwy modułów w czterech wersjach: zakładki „Rejestr reklam M1 / Oferty WWW M2 / Oferty M3”, nagłówki „Oferty WWW (M2) / Oferty doradztwa (M3)”, plakietki „Finfluencer / Reklama firmy / Doradztwo”, `MODULES` „Materiały twórców / Oferty WWW / Doradztwo WWW”, Źródła „WWW firm (M2) / WWW doradców (M3)”, Kalibracja „M2 Reklama firmy”. Do tego zakładka „Oferty WWW M2” to w 92% posty Facebook i Instagram (183 z 200). Jedna nazwa na moduł według słownika §3.4.
2. Trasa `no_signal` to „Bez przesłanki” w liście, a decyzja `no_signal` to „Bez sygnału” na przycisku. `insufficient` to „Za mało danych”, a zakładka nazywa się „Niepełne dane”. Plakietka „do sprawdzenia” jest pisana małą literą, a `ROUTES` wielką.
3. Siła ma pięć nazw: „Siła”, „Siła przesłanki”, „Siła sygnału” (M3), „Wynik reguł” (M2), „Punkty” (błędy kalibracji). Wystarczy jedna: „Siła”.
4. Oznaczenie ma trzy nazwy: „flaga płatnej promocji YouTube” (`DISCLOSURE`), „flaga płatnej promocji” (`DISCLOSURE_ROW`), „flaga platformy” (`DISCLOSURE_WHERE`), a w zakresie „Oznaczenie YouTube: płatna promocja: tak / brak”.
5. Zielona plakietka „zbadano” obok „brak” (flaga YouTube) czyta się jako wynik pozytywny. Stan zbadania i wynik trzeba rozdzielić (§4).
6. Daty w czterech formatach: „21 lis” (`fmtDay`), „21 XI” (`fmtDayRoman`, linia skanu i reguł), „21 lis 2026, 21:37” (`fmtDateTime`) oraz tekst API „21.11.2026 19:05” i „2026-11-21” wewnątrz zdań. W listach zostaje „21 lis”, w szczegółach „21 lis 2026, 21:37”. Bez rzymskich miesięcy.
7. Puste wartości w pięciu wersjach: „—”, „brak”, „nie ustalono”, „Zasięg nieznany”, „brak w zapisanym pliku”. Wystarczą „—” w tabeli i „brak danych” w zdaniu.
8. `ENTITY_ROW.name` → `names` (M3, „Dane podmiotu na stronie”).
9. Wartość zastępcza „Droga odkrycia sprzed rozszerzenia kontraktu” (zrzut `1440-8-niepelne.png`) zamienić na „—”.
10. Ścieżki plików w interfejsie: `~/.config/investwatch/meta.token`, `docs/lanes/2026-11-21-fable-k-social.md`, `fixtures/validation/q-v2/…@463cceb`. Usunąć.

Po stronie API (H):

1. Usunąć z wiersza i karty schematu 2 stare pola `score`, `reviewSuggestion`, `summary`, `signalType`, `possibleUndisclosedPromotion`, `descriptionScore`. Karta `youtube:7M0rC6-Rueo` mówi jednocześnie „Wzmianka o marce”, `no_signal` i 24 pkt (stare) oraz `refer` i 100 pkt (nowe).
2. Posty i reklamy M2 z importu (183 z 200 w `offersM2`): wiersz ma `reviewScore: 20`, `band: weak`, `route: insufficient`, a karta `reviewDecision: null` i `reviewScore: null`. API powinno podać tę samą trasę i siłę w obu miejscach oraz `completeReason` (np. `media_unexamined`).
3. `disclosure.kind` niezgodne z `state`: `platform_flag` + `in_speech` (1), `platform_flag` + `in_description` (2). Dla `youtube:o2GfnmVVkO8` jest `adRelationship.disclosure.kind = partner_mention` i `adRegistry.disclosureKind = platform_flag`, a `basis` to „flaga płatnej promocji YouTube”. Rejestr wyświetla więc „flaga płatnej promocji, w mowie 1:17”. Propozycja: `kind` zawsze opisuje pokazane `state`, a flaga YouTube jako osobne pole logiczne `platformFlag`.
4. `firm` w wierszu w różnych formach: „XTB Ltd / XTB S.A.” (wiersz), „XTB” (karta), „XTB Polska / XTB Online Investing / XTB Online Trading” (nazwy kont M2), „etoro” obok „eToro”, „DOM MAKLERSKI BANKU OCHRONY ŚRODOWISKA S.A.” obok „BOŚ” i „DM BOŚ”. W danych z wykazu jest literówka: „BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.) iuro Maklerskie PEKAO” (urwane „Biuro”). Dodać `firmShort` (marka do wiersza) i `firmLegal` (nazwa z wykazu do kroku „Firma”).
5. `checkCounts` M2 liczy „obserwacja: 8” obok „przesłanka: 8”, choć żadne kryterium nie ma stanu „obserwacja”, więc suma wynosi 27 z 19. Usunąć albo opisać jako alias.
6. `reviewDecision.reasons[3]` (M1) powtarza `alternative`. Podać `alternative` osobno, a `reasons` bez niego.
7. `moments[].label` powtarza nazwę wymogu przy każdym momencie. Przydałaby się etykieta własna momentu („Link w opisie”, „Wezwanie w mowie”, „Kadr”).
8. Tekst M3 bez odstępów między komórkami tabeli: „Obszar usługiCo obejmujeKorzyść dla klienta…” (`rdmwm.pl`, cecha „Instrument”).
9. Tytuł wiersza ucięty na separatorze: wiersz ma „Rachunek IKE -”, a karta „Rachunek IKE - Noble Securities”.
10. Wiersz M3 powinien mieć `licensed` (z `identity.licensed`), a wiersz M1 `registryState` jest już w `adRegistry`. Przyda się też `secondOpinion.agreement` w wierszu, gdy model działa.
11. `/v1/overview` waży 347 KB i przy każdym odświeżeniu niesie 477 twórców, zdublowane `sourceHealth` i `sourceHealthDetail`, puste `findings` i `sourceState` oraz lokalną ścieżkę `semantic.directory` (`/home/codexdev/…`). Twórców przenieść do `/v1/creators?limit=`, a ścieżkę usunąć.
12. M2 `checks[].evidence`: rozdzielić zdanie analityczne od liczb pomiaru (`summary` + `measurements`).
13. Pasmo siły liczone skalą M1 (≥75 mocna, ≥60 średnia) przy progu M2 równym 30: w kolejce „Co wymaga sprawdzenia” 6 z 15 spraw M2 ma plakietkę „słaba” (55, 40, 30 pkt), choć przekroczyły próg skierowania. Kontroler widzi „słabą” sprawę w alarmie. Pasmo powinno być liczone względem progu modułu (np. ≥ próg = średnia, ≥ próg + 30 = mocna) albo UI powinien ukryć pasmo, gdy moduł ma inny próg.

### 3. Architektura informacji

#### 3.1 Zakładki: z 9 do 4

| Dziś | Docelowo | Jak |
|---|---|---|
| Co wymaga sprawdzenia | **Do sprawdzenia** | Lista z filtrem **Stan** (domyślnie „Do sprawdzenia”) i **Moduł** |
| Oferty WWW M2 | Do sprawdzenia, Moduł M2 | Stan „Wszystkie” daje dzisiejszą listę M2 (`offersM2`) |
| Oferty M3 | Do sprawdzenia, Moduł M3 | Stan „Wszystkie” daje `offersM3` z kontrolą ujemną |
| Niepełne dane | Do sprawdzenia, Stan „Niepełne” | `incomplete` |
| Zamknięte | Do sprawdzenia, Stan „Zamknięte” | `closed` |
| Demo i własne pliki | Do sprawdzenia, Stan „Demo” | `demo` |
| Rejestr reklam M1 | **Rejestr reklam** | Bez zmian w API, przełącznik „potwierdzone / do potwierdzenia” |
| Źródła | **Źródła** | Do zakładki dochodzi sekcja „Dodaj materiał” (dzisiejsze „Dodaj dowód” i import Meta) |
| Kalibracja | **Kalibracja** | Bez zmian w API |

Stan to jeden przełącznik z licznikami, zmapowany wprost na kolejki API: Do sprawdzenia → `review`, Niepełne → `incomplete`, Wszystkie → `offersM2`/`offersM3` przy wybranym module M2/M3, a bez modułu `all`, Zamknięte → `closed`, Demo → `demo`. UI dalej tylko filtruje (kontrakt R9, §3.4), więc API nie wymaga zmian.

Dlaczego Rejestr zostaje osobno: to inny obiekt (jawna współpraca, bez decyzji) i drugi krok scenariusza („jawna współpraca trafia do rejestru, a nie do alarmu”). Wymieszany ze stanami traci ten przekaz.

Ryzyka względem briefu i pokazu:

- Brief wymaga filtrowania po module, źródle, ryzyku i dacie. Po zmianie wszystkie cztery filtry stoją w jednym rzędzie nad listą, zamiast być rozłożone na zakładki i zwijany panel. Ryzyko spada.
- Scenariusz `demo.md` i pitch używają dzisiejszych nazw zakładek („Rejestr reklam M1”, „Oferty WWW M2”, „Oferty M3”). Po wdrożeniu trzeba zaktualizować kroki i zrzuty awaryjne r3.
- Stare adresy (`#m2`, `#m3`, `#incomplete`, `#closed`, `#demo`) muszą przekierowywać na `#review?module=…&state=…` w `parseHash`, żeby nie zepsuć linków ani testów UI.
- J1 jest w trakcie rundy 4 (karty M2 i M3). Zmiana zakładek dotyczy `Desk.jsx`, `route.js`, `Lists.jsx` i `filters.js`, a nie kart, więc obie prace dają się rozdzielić.
- Wariant awaryjny przy braku czasu: zostawić zakładki modułów i scalić tylko Niepełne, Zamknięte i Demo w filtr stanu (9 → 6). To zmiana typu S.

#### 3.2 Jeden szablon karty dla M1, M2 i M3

```
[← Lista]  mocna 95 · M1 Twórcy · Do sprawdzenia            [Otwórz w filmie od 0:15]
Freedom24 Alternatywy: Którego brokera wybrać? (2026)
ForexMind · YouTube · 31 maj 2026 · 22 wyśw. · Firma: XTB (2 wpisy KNF)
────────────────────────────────────────────────────────────────────────────────
DROGA DOWODU  (pasek, §4)
┌ Dlaczego tutaj ───────────────┐ ┌ Dowód ──────────────────────────────┐
│ • 3 punkty, każdy ≤120 zn.     │ │ 3 wiersze: czas | cytat | ↗          │
│ Możliwe wyjaśnienie: 1 linia   │ │ miniatury kadrów / zrzutów           │
└────────────────────────────────┘ └──────────────────────────────────────┘
┌ Decyzja (zawsze na pierwszym ekranie na 1440) ────────────────────────────┐
│ [Przekaż do kontroli] [Uzupełnij dane] [Bez przesłanki] [Zamknij]          │
│ Uzasadnienie: [______________________________]  [Zapisz decyzję]           │
└────────────────────────────────────────────────────────────────────────────┘
▸ Więcej: Historia · Punktacja · Szczegóły
```

| Część | M1 (film, post) | Reklama Meta, post z importu | M2 (strona firmy) | M3 (oferta doradcza) |
|---|---|---|---|---|
| Linia metadanych | autor · platforma · data · zasięg · firma | reklamodawca · platforma · emisja · zasięg UE | firma (marka) · typ podmiotu · odczyt | domena · podmiot · uprawnienia |
| Dlaczego tutaj | `reasons[0..2]` + `alternative` | `reason` albo „Brak oceny reguł” | 3 przesłanki = `reasons` | `reasons[0..2]` albo `missing[]` |
| Dowód | `moments` (bez kadrów) + kadry | `adBody` (cytat) + emisja | 3 przesłanki: cytat + zrzut komputer/telefon, a pod spodem „+5 przesłanek” | 4 cechy: stan + cytat 1 linia + podstrona |
| Droga dowodu | §4 | §4 | §4 | §4 |
| Więcej › Szczegóły | wpisy KNF, odkrycie, pełny opis, identyfikator, adres | CTA, domena, wersje, nota importu | 19 kryteriów, numer KNF, strona firmy | kontrargumenty, 12 wykazów, podstrony, trafienia |

Na 1440 px w panelu bocznym (ok. 760 px) „Dlaczego” i „Dowód” stoją obok siebie, a „Decyzja” pod nimi na pełną szerokość. Na 390 px kolejność to: nagłówek, droga dowodu (przewijana poziomo albo w 2 liniach), Dlaczego, Dowód, Decyzja, a stopka z przyciskami „Dowód” i „Decyzja” zostaje.

#### 3.3 Zasady tekstu

- Punkt listy: do 120 znaków, jedno zdanie, bez wstępu „Przesłanka do sprawdzenia:”.
- Komórka tabeli: do 60 znaków. Cytat: do 140 znaków z „…”, a pełny tekst po rozwinięciu.
- Jedno zastrzeżenie prawne na stronę, w stopce: „Przesłanki do sprawdzenia, nie ocena prawna. Decyzję podejmuje analityk.”
- Pusta wartość: „—” w tabeli, „brak danych” w zdaniu.
- Liczby: spacja tysięcy („1 330”), czas filmu „m:ss”, daty „21 lis” lub „21 lis 2026, 21:37”.
- Zakazane w interfejsie: „naruszenie”, „zarzut”, „podejrzany”; kody `refer`, `no_signal`, `qual_d`, `m2Card`, `tiktok_embed`, `data_api`, `desktop`, `phone`; jednostki techniczne „px”, „y=”, „FOG”, „sha”; ścieżki plików; „None”, „null”, „undefined”; rzymskie miesiące; nazwy agentów zespołu.

#### 3.4 Słownik etykiet (używać wszędzie tak samo)

| # | Pojęcie | Etykieta | Źródło |
|---|---|---|---|
| 1 | Moduł M1 | M1 Twórcy | `module` |
| 2 | Moduł M2 | M2 Reklamy firm | `module` |
| 3 | Moduł M3 | M3 Doradztwo | `module` |
| 4 | Trasa `refer` | Do sprawdzenia | `route` |
| 5 | Trasy `complete` i `insufficient` | Niepełne (powód obok) | `route`, `completeReason` |
| 6 | Trasa `no_signal` i decyzja `no_signal` | Bez przesłanki | `route`, `resolution` |
| 7 | Status | Nowa · W kontroli · Zamknięta | `status` |
| 8 | Siła | mocna / średnia / słaba + liczba („mocna 95”) | `reviewScore` |
| 9 | Pojedynczy powód | przesłanka | `reasons`, `checks` |
| 10 | Materiał dowodowy | Dowód | `moments`, `checks`, `adBody` |
| 11 | Zakres badania | Droga dowodu | `coverage` |
| 12 | Oznaczenie współpracy | w opisie · w mowie m:ss · w kadrze · flaga YouTube · brak w zbadanym zakresie · nie sprawdzono | `disclosure`, `platformFlags` |
| 13 | Wpis rejestru | Rejestr reklam: potwierdzona · do potwierdzenia | `adRegistry.state` |
| 14 | Firma i wykaz | Firma: XTB · w wykazie KNF · 2 wpisy · brak wpisu | `firm`, `candidates` |
| 15 | Kto opublikował | Autor (kanał, konto, strona) | `creatorName`, `author` |
| 16 | Uprawnienia M3 | uprawniony · agent firmy · inny zakres · brak wpisu · brak danych podmiotu · kolizja nazw | `identity.state` |
| 17 | Platforma | Źródło: YouTube · TikTok · Instagram · Facebook · WWW | `platform` |
| 18 | Daty | Opublikowano · Odczytano · „≈” dla szacunku | `publishedAt`, `observedAt`, `publishedAtDerived` |
| 19 | Decyzje | Przekaż do kontroli · Uzupełnij dane · Bez przesłanki · Zamknij | `RESOLUTIONS` |
| 20 | Pochodzenie syntetyczne | Demo | `origin` |

#### 3.5 Nagłówek strony w jednej linii

Desktop: `InvestWatch ● na żywo │ Do sprawdzenia 15 · Rejestr reklam 290 · Źródła · Kalibracja │ replay 21 XI · 1 923 mat. ▁▃█▂ │ Raport`. Pod spodem jeden rząd filtrów: `Stan [Do sprawdzenia 15 ▾] Moduł [Wszystkie │ M1 4 │ M2 10 │ M3 1] Źródło [▾] Siła [▾] Data [▾] [Szukaj…]`.

Telefon: `InvestWatch ●` i zakładki (4 mieszczą się bez przewijania przy rozmiarze `sm`), filtry w jednym przycisku „Filtry (n)” z arkuszem, a stan danych tylko w Źródłach.

### 4. Droga dowodu

Jeden pasek kroków pod nagłówkiem karty zastępuje kafle „Co zbadano” (M1, M2, M3), „Firma” (M1, M2), część „Twórca i zasięg”, „Uprawnienia” (M3), baner „Wniosek wstrzymany” i dopiski o kadrach i platformie. Krok ma ikonę stanu zbadania (✓ zbadano, ○ nie zbadano, … czeka) oraz wynik w 2–4 słowach. Kolor dostaje wynik, nie ikona: pomarańczowy, gdy wspiera przesłankę, szary, gdy jest neutralny, zielony, gdy jej przeczy. Kliknięcie kroku przewija do dowodu albo otwiera „Szczegóły”. Ostatni krok to wynik.

| Krok | Pole API | Reguła wyświetlania |
|---|---|---|
| Opis | `coverage.modalities.description.state`, `premises[].relationEvidence[].kind`, `adRelationship.basis` | ✓ gdy `full`. Wynik: „link i kod XTB” (relacja), „„[współpraca z XTB]”” (oznaczenie) albo „bez śladu” |
| Flaga YouTube | `coverage.modalities.platformFlags.paidPromotion` | true → „płatna promocja” (zielony), false → „brak” (pomarańczowy przy relacji), null → ○ „nie sprawdzono” |
| Mowa | `coverage.modalities.transcript.state/windows`, `adRelationship.disclosure` | ✓ „0:00–14:46, brak oznaczenia”, ✓ „oznaczenie 10:14” (`state=in_speech`, `atSec`), … „czeka na transkrypcję”, ○ „niedostępna (TikTok)” |
| Kadry | `coverage.modalities.frames.moments.length` | ✓ „3 kadry, bez OCR” albo ○ „nie pobrano” |
| Firma | `adRelationship.firm.mention/identityStatus/candidates`, `relationships.length` | „XTB · 2 wpisy KNF”, „Freedom24 · w wykazie”, „+1 firma” |
| Model (opcjonalnie) | `model.secondOpinion.agreement`, gdy jest | „Model: zgodny / niezgodny”. Krok ukryty, gdy brak pola (dziś w bazie pokazu brak) |
| Wynik | `reviewDecision.route`, `reviewScore`, `adRegistry.state`, `coverage.blocksConclusion` | „Do sprawdzenia · mocna 100”, „Rejestr · potwierdzona”, „Niepełne · wniosek wstrzymany” |

Przykłady na danych z API:

- **M1, film z flagą** (`youtube:7M0rC6-Rueo`): `Opis ✓ link i kod XTB → Flaga YouTube ✓ brak → Mowa ✓ 0:00–14:46, brak oznaczenia → Kadry ✓ 3, bez OCR → Firma XTB · 2 wpisy KNF · +1 firma → Do sprawdzenia · mocna 100`.
- **M1, rejestr, podejrzenie obalone w mowie** (`youtube:CDk20n4u9Kk`, Comparic): `Opis ✓ link i kod XTB → Mowa ✓ oznaczenie 10:14 „znajdziecie u partnera tego odcinka XTB” → Flaga YouTube ✓ … → Firma XTB → Rejestr · potwierdzona (bez przesłanki)`. Krok „Mowa” jest zielony, bo przeczy przesłance z opisu. Ten jeden wiersz pokazuje jury, po co system słucha mowy.
- **M1, TikTok** (`tiktok:7707284619103718689`): `Opis ✓ „[współpraca z XTB]” → Mowa ○ niedostępna (TikTok) → Kadry ○ → Flaga ○ nie sprawdzono → Firma XTB · 2 wpisy → Rejestr + Niepełne · wniosek wstrzymany`.
- **Reklama Meta** (`facebook:ad-949456423765641`): `Tekst reklamy ✓ → Obraz i wideo ○ nie badano → Emisja 9 gru 2024 – 11 maj 2026 → Firma XTB (reklamodawca) → Brak oceny reguł`. Ostatni krok uczciwie pokaże brak oceny, dopóki API nie poda trasy (§2.3 punkt 2).
- **M2, strona** (`web:noblesecurities.pl/…/rachunek-ike`): `Render ✓ komputer + telefon, cookies odrzucone → Kryteria 8 przesłanek · 5 spełnione · 6 nie dotyczy → Zrzuty ✓ 2 → Firma NOBLE Securities · dom maklerski · w wykazie → Do sprawdzenia · mocna 95`. Pola: `coverage.modalities.desktop/phone`, `m2Market.views.*.consent`, `checks[].state`, `shotsOf`, `m2Card.firm`.
- **M3, rdmwm.pl** (`web:rdmwm.pl:m3`): `Tekst ✓ 2 podstrony → Cechy 4 z 4 → Podmiot na stronie ✗ brak nazwy, NIP, KRS → Wykazy KNF ✓ 12, brak wpisu → Ostrzeżenia KNF brak → Do sprawdzenia · mocna 85`. Pola: `coverage.modalities.pageText.pages`, `checks[].state`, `identity.operator`, `identity.state/reviewedRegisters/checkedAt`, `knfWarning.state`.
- **M3, kontrola ujemna** (`web:phinance.pl:m3`): `Tekst ✓ 2 podstrony → Cechy 3 z 4 (czynność częściowo) → Podmiot ✓ Phinance S.A., KRS, NIP → Wykazy KNF ✓ agent firmy (Ipopema Securities) → Bez przesłanki · kontrola`.

### 5. Lista zmian dla J1

Kolejność wdrażania. Pierwsze 10 daje największe uproszczenie. „Musi” oznacza: przed pokazem.

| # | Plik / komponent | Zmiana | Kryterium akceptacji na zrzucie | Szac. | Prior. |
|---|---|---|---|---|---|
| 1 | `Desk.jsx` `QueueScreen` (nagłówek) | Usunąć H1, licznik, zdanie, linię reguł i linię skanu. Zostaje jedna linia stanu danych ze sparkline po prawej stronie rzędu filtrów | 390 px: pierwszy wiersz listy powyżej 400 px (dziś ok. 570). 1440 px: nagłówek kolejki ma 1 linię | S | Musi |
| 2 | `Lists.jsx` `Filters` | Jeden rząd: Moduł (przełącznik), Źródło, Siła, Data (listy), Szukaj, „Raport”. Usunąć „JSON” i zwijane „Data, siła”. Na telefonie przycisk „Filtry (n)” | 1440 px: filtry w 1 linii. 390 px: filtry w 1 linii, a pod nimi lista | M | Musi |
| 3 | `route.js` `TABS`, `Desk.jsx`, `filters.js` | Zakładki: Do sprawdzenia, Rejestr reklam, Źródła, Kalibracja. Filtr „Stan” mapuje się na kolejki (§3.1). Przekierowania starych adresów | Pasek ma 4 zakładki, a na 390 px wszystkie mieszczą się bez przewijania. `#m3` otwiera listę M3 w stanie „Wszystkie” | M | Musi (wariant awaryjny 9 → 6: S) |
| 4 | `CaseDetail.jsx` + nowy `EvidencePath` w `cardparts.jsx` | Droga dowodu (§4) zamiast `ScopeTile`, `FirmTile`, `M2ScopeTile`, `M2FirmTile`, `PermissionsTile`, `M3ScopeTile` i banera „wstrzymany” | Karta M1 ForexMind na 1440: pasek 6 kroków pod nagłówkiem, bez kafli „Co zbadano” i „Firma” | M | Musi |
| 5 | `CaseDetail.jsx` nagłówek | Jedna linia metadanych (autor · platforma · data · zasięg · firma). Usunąć plakietki pochodzenia, importu i statusu „Nowa”, przycisk „Decyzja” na desktopie oraz `CreatorTile` | Nagłówek: plakietka siły, tytuł, linia metadanych, przycisk główny. Bez kafla „Twórca i zasięg” | S | Musi |
| 6 | `cardparts.jsx` `WhyTile` | 3 punkty i linia „Możliwe wyjaśnienie”. Usunąć „Pokaż wszystkie” i plakietkę trasy przy `refer`. M2: punkty z przesłankami. M3 `complete`: lista `missing` | Kafel „Dlaczego tutaj” ma najwyżej 4 linie tekstu i nie ma rozwijania | S | Musi |
| 7 | `CaseDetail.jsx` `MomentsTile` → „Dowód” | Do 3 wierszy (czas, cytat, ↗) bez etykiety wymogu, kadry pod spodem. M2: 3 przesłanki z cytatem i zrzutami, reszta pod „+N”. M3: 4 cechy w 1 linii | Karta M2 Noble: 3 wiersze ze zrzutami zamiast 8. Karta M1: 3 wiersze i 2–3 miniatury | M | Musi |
| 8 | `CaseDetail.jsx` układ | Na 1440: Dlaczego i Dowód obok siebie, Decyzja pod nimi. Podpowiedź decyzji i zastrzeżenie przenieść do stopki strony | 1440 px: przycisk „Zapisz decyzję” na pierwszym ekranie karty M1 i M2, bez przewijania | S | Musi |
| 9 | `labels.js` | Słownik §3.4: moduły, „Bez przesłanki” (także na przycisku decyzji), jedna nazwa siły, jedna nazwa flagi, formaty dat bez rzymskich, puste „—” | Na wszystkich zrzutach r4 nie ma „Bez sygnału”, „Oferty WWW”, „21 XI” w treści ani „Reklama firmy” | S | Musi |
| 10 | `Lists.jsx` `CaseList`, `OffersTable`, `RegisterTable` | Wiersz: tytuł (1 linia), plakietka modułu, linia autor/domena · źródło · data. Firma (marka), Powód (1 linia), Siła (plakietka „mocna 95”). Usunąć kolumny „Dowód” i „Platforma”, plakietki importu oraz dwulinijkową siłę | Kolejka 1440: 4 kolumny, wiersz o wysokości 2 linii. Rejestr: typ i cytat w 1 linii | M | Musi |
| 11 | `CaseDetail.jsx` `MoreTabs` | 3 zakładki: Historia, Punktacja, Szczegóły (wpisy KNF, odkrycie, pełny opis, CTA, domena, wersje, 19 kryteriów, wykazy, kontrargumenty, identyfikator). Usunąć „Surowe dane” | „Więcej” ma 3 zakładki | S | Musi |
| 12 | `Calibration.jsx` | Baner w 1 linii z danymi zbioru, FP i FN jako duże kafle, macierz 2×2, linia „Poprzednie reguły: FP 7, FN 4”. „Aktywny wariant”, „Historia progu” i tabelę wariantów pod „Więcej” | 1440 px: suwak, FP/FN, zdanie o skutku i wykres na pierwszym ekranie. 390 px: FP i FN widoczne bez przewijania pod suwakiem | M | Musi |
| 13 | `Sources.jsx` | Trend na górze, jedna tabela platform z rozwijanym wierszem, jedna linia skanu nad przyciskami. Usunąć wykres „per platforma”, pasek kroków poza skanem i ścieżki plików. Głównym przyciskiem zostaje „Skanuj na żywo” | 1440 px: trend i tabela 7 platform na pierwszym ekranie | M | Musi |
| 14 | `Sources.jsx` + `EvidenceForm.jsx` + `MetaImport.jsx` | Zwijana sekcja „Dodaj materiał” z dwoma kartami (nagranie, zapisana strona). Usunąć przycisk z górnego paska | Górny pasek: nazwa, kropka „na żywo”. Krok 6 scenariusza 5-min działa ze Źródeł | S | Warto |
| 15 | `CardM3.jsx` | `ENTITY_ROW` `name` → `names`. Plakietka kontroli z `identity.licensed` | Karta phinance: „Phinance S.A.” w kroku „Podmiot” | S | Musi |
| 16 | `Lists.jsx` `OffersList`, `RegisterList` | Telefon: ten sam szablon 3 linii co kolejka, z powodem. Usunąć `registryInfo.summary` | 390 px M2: każdy wiersz ma powód | S | Warto |
| 17 | `Desk.jsx` baner alertu | Tytuł „Nowa sprawa: <tytuł> · mocna 95” i przycisk „Otwórz”, bez opisu | Baner w 1 linii | S | Warto |
| 18 | `Lists.jsx` stan „Niepełne” | Kolumna „Czego brakuje” z `completeReason` albo `missing[0]`. Liczba czekających na transkrypcję w podpowiedzi stanu | Brak powtórzeń „Brak wystarczającego zakresu do oceny” w M1 | S | Warto |
| 19 | `docs/hackathon/demo.md` (autor N/PITCH, nie J1) | Nazwy zakładek i ścieżki kliknięć po zmianie 3. Nowe zrzuty awaryjne r4 | Scenariusz 2-min przechodzi z nowymi nazwami | S | Musi, jeśli wdrożono 3 |
| 20 | `Sources.jsx` tabela twórców | Filtr „nowi w skanie” i pusty zasięg jako „—” | — | S | Później |
| 21 | `CaseDetail.jsx` droga dowodu, krok „Model” | Krok z `model.secondOpinion`, gdy API go poda | — | S | Później |
| 22 | `charts.jsx` / Źródła | Trend jako jeden wykres z dwiema seriami i osobnymi osiami opisanymi liczbami nad słupkami (opcjonalnie) | — | S | Później |
| 23 | Strona: stopka | Jedno zastrzeżenie prawne (§3.3) w stopce zamiast czterech miejsc | — | S | Warto |

5 rzeczy, których nie ruszać:

1. Suwak progu z natychmiastowym podglądem, zdaniem o skutku dla kolejki i wykresem FP/FN. To wymóg briefu i krok pokazu 0:50.
2. Alert `high_risk` przez WebSocket i kropka „na żywo”, wymóg briefu. Skrócić wolno tylko tekst.
3. Przycisk „Otwórz w filmie od m:ss” i miniatury kadrów oraz zrzutów z powiększeniem. To najmocniejszy dowód na pokazie i w decyzji.
4. Cztery rodzaje decyzji z wymaganym uzasadnieniem i obsługą konfliktu 409 (zmiana statusu z briefu, rewizja).
5. Filtry w adresie (`#…?module=…`), stronicowanie po stronie API, uczciwe puste stany i żółty baner „oceny agentów”. Te elementy działają i chronią przed fałszywym wrażeniem.

### 5a. Zgodność z `docs/PITCH.md` §11 (plik pojawił się po napisaniu §1–5)

| PITCH §11 | Stanowisko audytu | Zmiana w liście §5 |
|---|---|---|
| 1 Ekran startowy „Przegląd” z lejkiem 3 liczb | Zgoda co do lejka, ale bez nowej zakładki. Lejek „1 923 zebrane → 290 rejestr → 15 do sprawdzenia” trafia do linii stanu danych w nagłówku (§3.5) i jest klikalny | Poz. 1: linia stanu = lejek |
| 2 Pasek „Droga dowodu” z krokiem Odkrycie | Zgoda (§4). Dodać krok „Odkrycie” na początku (`discovery[0]`: „Wyszukiwanie YouTube „jak zacząć inwestować”, poz. 37”) i stan „obaliło” dla mowy w rejestrze | Poz. 4 |
| 3 Nie pokazywać „na żywo” przy danych z replay | Zgoda. Kropka zostaje jako stan WebSocket, ale z napisem „połączono”. Tryb danych („replay 21 XI”) stoi osobno w linii stanu. Element 2 inwentarza zmienia się na POŁĄCZ | Poz. 1 i 17 |
| 4 Licznik „wyjaśnione automatycznie” w rejestrze | Zgoda. To 3 klikalne liczniki nad tabelą rejestru zamiast przełącznika sekcji: „w mowie 8 · flaga YouTube 50 · czeka na mowę 120” (z `disclosure.state` i `completeReason`, najlepiej z pola API) | Nowa poz. 24 |
| 7 Kalibracja bez samego „100%” | Zgoda, zgodne z poz. 12: precyzja zawsze z n i przedziałem | Poz. 12 |
| 8 Nazwy 7 zakładek | Rozbieżność: audyt proponuje 4 zakładki. Nazwy PITCH obowiązują tylko w wariancie awaryjnym 9 → 6 („Strony firm (M2)”, „Oferty doradcze (M3)”, „Czeka na dane” jako stan). Decyzja należy do J | Poz. 3 |
| 9 Ukryć Zamknięte, Demo i linię „częściowy…” | Zgoda, realizują to poz. 1 i 3 | — |
| 10 Karta M2 na telefonie z odległością od ostrzeżenia | Zgoda. Zdanie przesłanki 3 podaje odległość, a pełna tabela 19 kryteriów jest pod „Więcej” | Poz. 7 |
| 6 i 13 Typ materiału E5 i drugi głos | Krok „Model” w drodze dowodu tylko przy obecnym polu, szary „wyłączony” albo wcale | Poz. 21 |

Dodatkowa pozycja listy zmian:

| # | Plik / komponent | Zmiana | Kryterium akceptacji na zrzucie | Szac. | Prior. |
|---|---|---|---|---|---|
| 24 | `Lists.jsx` `RegisterTable` + `Desk.jsx` | Nad tabelą rejestru 3 klikalne liczniki („w mowie · flaga YouTube · czeka na mowę”), które filtrują listę. „Do potwierdzenia” jako czwarty licznik zamiast przełącznika sekcji | Rejestr 1440: liczniki w 1 linii nad tabelą, kliknięcie zawęża listę | S (UI z licznikami z API) / M (bez pola API) | Musi (pitch) |

### 6. Makiety

ASCII na realnych danych (M1 ForexMind `youtube:AqXHkxDzSDI`, M2 Noble IKE), 1440 i 390 px: [makiety](fable-i-uproszczenie/makiety.md).

## Next Step

J akceptuje układ 4 zakładek albo wariant awaryjny 9 → 6. Potem J1 wdraża pozycje 1–10 z §5 po zakończeniu rundy 4 kart, a H dostaje §2.3 „Po stronie API” punkty 1–4.

## Verification

- Odczyt API: `curl -H 'X-InvestWatch-Schema: 2' http://127.0.0.1:18801/v1/{overview,calibration,trend,threshold,qualification}`, kolejki `?limit=50` (API zwróciło do 200 rekordów; w ponownej próbie `limit` działał) i 14 kart `/v1/cases/{id}`. Wypełnienie pól policzone skryptem na pobranych plikach.
- Kod: przeczytane `Desk.jsx`, `Lists.jsx`, `CaseDetail.jsx`, `cardparts.jsx`, `CardM2.jsx`, `CardM3.jsx`, `parts.jsx`, `labels.js`, `model.js`, `route.js`, `filters.js`, `Sources.jsx`, `Calibration.jsx`, a pobieżnie `charts.jsx`, `EvidenceForm.jsx` i `MetaImport.jsx`.
- Zrzuty: obejrzane `1440-1`, `-2-momenty`, `-3`, `-4`, `-6`, `-7`, `-8`, `-9`, `-9b`, `-10`, `-12`, `-13` oraz `390-1`, `-2`, `-7`. Pozostałe zrzuty r3 to warianty tych samych widoków (stan momentów, TikTok w rejestrze, zamknięte) i nie zostały otwarte.
- Nie uruchomiono: przeglądarki, testów UI ani walidacji wdrożenia, bo to audyt bez kodu.

## Fallback / Cut

Dokument nie zmienia kodu. Jeśli J odrzuci scalenie zakładek, pozycje 1, 2 i 4–13 z §5 zostają ważne bez pozycji 3.

## Handoff

- Co zmieniono: nowy rekord audytu i plik makiet. Nic w web/, tests/, api/.
- Weryfikacja: dane z API i kodu z 21 XI ok. 22:15–23:30 UTC. Brak przebiegu przeglądarki.
- Otwarte: decyzja J o zakładkach, przejęcie §2.3 przez H, aktualizacja `demo.md` po zmianie nazw.
- Czego nie dało się ocenić bez przeglądarki: rzeczywista wysokość karty po rundzie 4, zachowanie przewijania panelu bocznego, czytelność paska kroków na 390 px (zawijanie lub przewijanie poziome), czas odpowiedzi filtra stanu przy przełączaniu kolejek i wygląd baneru alertu przy kilku zdarzeniach naraz.
