# Lane: D · kwalifikacja M1 (projekt kontraktu)

- Owner: J (decyzje produktowe); wykonawca D (Opus, wysiłek high) na zlecenie Fable
- Branch: hack/fable/d-kwalifikacja
- Worktree: jeszcze nieutworzony; projekt powstał w checkoucie głównym na hack/integration (HEAD 491094d)
- State: ACTIVE
- Updated: 2026-11-21 (fala 2: moduł czysty, bez wpięcia)
- PR / issue: none yet

## Acceptance

[Próba Q](../fable/ODBIOR.md) i wiersz D [planu](../fable/REALIZACJA.md): dwie rzeczywiste deklaracje „Partnerem odcinka jest XTB” (youtube:xtMqKkFO-0M, youtube:04mmNbAlHFo) trafiają do rejestru reklam i nie trafiają do kolejki „Co wymaga sprawdzenia”. Działają stany niepełnego materiału, edukacji i dobrze udokumentowanej przesłanki. Kontrprzykład: jawna współpraca z odrębnym, udokumentowanym twierdzeniem o zysku bez ostrzeżenia daje skierowanie z cytatem, kryterium i linkiem do sekundy.

## Claim

- `docs/lanes/2026-11-21-fable-d-kwalifikacja.md` (ta fala, wyłącznie dokument)
- `analysis/qualification.py` (następna fala, nowy moduł)
- `analysis/test_qualification.py` (następna fala)
- `analysis/semantic.py` (następna fala, tylko gałąź M1 w `review_suggestion`)
- `analysis/test_engine.py`, `analysis/test_semantic.py` (następna fala, aktualizacja asercji M1)

## Contracts And Dependencies

- Produces: pola kwalifikacji M1 dołączane do Finding: `adRelationship`, `adRegistry`, `reviewDecision`, `reviewScore`, `premises[]`, `evidence[]` (rozszerzone), `coverage`, `priority`, `rulesVersion`, `requalification`.
- Consumes: Capture od B (YouTube: pełny opis, statystyki z datą, linki, język, czas trwania) i C (segmenty mowy/napisów/OCR z czasem, metodą i pokryciem); datowane kopie wykazów KNF w `data/probe-snapshots/knf/`.
- Shared-file coordination: `analysis/engine.py`, `api/`, schemat i fingerprint w `api/store.py` należą do H. D nie edytuje tych plików; H wpina `qualify()` po uzgodnieniu poniższego kontraktu. Etykiety w `fixtures/labeled/calibration.json` należą do G.

## Projekt kontraktu kwalifikacji M1

### 0. Stan obecny i dlaczego wymaga zmiany

Odczyt wykonany w tej sesji (`python3 -B`, bez modelu E5, `review_suggestion(..., {"status": "unavailable"}, finding)`), HEAD 491094d:

| Rekord | score | signalType | summary | reviewSuggestion | rulesVersion |
|---|---|---|---|---|---|
| youtube:xtMqKkFO-0M | 94 | declaration | „Deklaracja współpracy lub partnerstwa. Ustal warunki współpracy z firmą.” | review (źródło rules) | investwatch-rules-pl-1.2 |
| youtube:04mmNbAlHFo | 94 | declaration | jw. | review (źródło rules) | investwatch-rules-pl-1.2 |

Skutki w produkcie: `review_suggestion` w [analysis/semantic.py](../../analysis/semantic.py) (gałąź M1, `signalType in {"declaration", "brand_cta"}` → `review`) kieruje każdą jawną deklarację do przeglądu. Pulpit (`web/src/neutral-desk.jsx`) pokazuje je jako „Reguły wskazały materiał”, filtr „wysokie ryzyko” liczy `score >= 60`, a `api/store.py` emituje zdarzenie `high_risk` przy `score >= 70`. W `fixtures/labeled/calibration.json` wpis `yt-partner` (ten sam tekst i URL) ma `expected: true`, więc przy progu 60 liczy się jako TP.

Ocena: według kontraktu próby Q to błąd. Silnik zlewa oś (i) „jest reklama” z osią (ii) „jest przesłanka do kontroli”. Wynik 94 mierzy pewność relacji reklamowej, a pulpit czyta go jako siłę alarmu. Jawna deklaracja jest pożądanym zachowaniem twórcy, a nie sygnałem uchybienia. Pod starym modelem, w którym M1 był wyłącznie rejestrem relacji, wynik był spójny. Pod jednostką etykiety G („materiał zawiera udokumentowaną przesłankę wymagającą kontroli”) etykieta `yt-partner` powinna brzmieć `false`.

Dodatkowe fakty o tych rekordach, istotne dla pokrycia:
- `description` zawiera 26 znaków. `contentHash` (d245bd33…) to skrót tego wycinka, a `provenance.originalTextSha256` (f88d4e26…) skrót innego, pełnego tekstu. Rekord ma `sampled: true` i `truncated: true`. Fikstura przechowuje więc wycinek, nie pełny opis. Pełnego opisu, mowy, napisów ani obrazu nie ma w repo.
- Źródłem jest Atom (`materialType: youtube_atom_title_description`). Atom nie podaje statystyk zasięgu ani flagi płatnej promocji.
- Marka „XTB” pasuje do dwóch wpisów: XTB S.A. (ID 6884980, „Firmy inwestycyjne - Domy maklerskie”, `knf_domy_maklerskie.json`) oraz XTB Ltd (ID 9439233, „Notyfikacje zagranicznych firm inwestycyjnych na terytorium RP”, `knf_notyfikacje_zagr_FI.json`). Bez linku lub domeny nie wiadomo, który podmiot jest stroną współpracy.
- Oba materiały mają tego samego twórcę i sponsora. Dla G to jedna kampania z dwoma materiałami.

Inne obserwacje z przeglądu kodu:
- `SIGNALS` ocenia zachętę przy marce (74) wyżej niż kod lub link polecający (66). Kod polecający jest silniejszym dowodem relacji handlowej niż samo „otwórz rachunek”, bo zachęta pojawia się też w poradnikach.
- Wpis kalibracyjny `wynagrodzenie` („Przelew od domu maklerskiego dostaję za każdy nowy rachunek…”) dostaje 12 i wychodzi jako FN. Deklaracja wynagrodzenia nie jest rozpoznawana jako dowód relacji.
- W przejrzanych fiksturach M1 (`fixtures/raw/discovery/2026-11-21.json`, `fixtures/labeled/*`) nie znalazłem rzeczywistego materiału z twierdzeniem o zysku w kontekście jawnej współpracy. Rzeczywisty przypadek „skieruj” musi dostarczyć B/C.

### 1. Model kwalifikacji: cztery niezależne osie

Każda oś ma własne pole i własne testy. Żadna oś nie jest liczona z innej osi, poza jawnie opisanymi warunkami zakresu (oś ii korzysta z wyniku osi i jako warunku zastosowania, nie jako punktów).

| Oś | Pytanie | Pole | Wpływ na decyzję |
|---|---|---|---|
| (i) Relacja reklamowa | Czy materiał jest reklamą lub współpracą firmy z wykazu i kto ją publikuje? | `adRelationship`, `adRegistry` | Decyduje o wpisie do rejestru reklam. Sama nie kieruje do kontroli. Jest warunkiem zastosowania części przesłanek (ii). |
| (ii) Przesłanka do kontroli | Czy w materiale jest konkretne twierdzenie lub okoliczność, którą należy sprawdzić? | `premises[]` | Jedyne źródło decyzji `skieruj`. |
| (iii) Siła dowodu | Jak dobrze udokumentowano relację i przesłanki? | `evidence[]`, `coverage`, punkty w `premises[].strength` | Moduluje `reviewScore`. Brak pokrycia blokuje wniosek o braku przesłanek. |
| (iv) Wpływ na odbiorców | Ilu odbiorców mógł dotknąć materiał? | `reach`, `priority` | Wyłącznie kolejność pobrania materiału i kolejność w kolejce. Nigdy `reviewScore`, `reviewDecision` ani status przesłanki. |

#### Oś (i) `adRelationship`

Stany: `zadeklarowana` (jawna deklaracja z nazwą firmy), `udokumentowana` (dowód handlowy: kod/link polecający do domeny firmy, deklaracja wynagrodzenia, flaga płatnej promocji platformy), `prawdopodobna` (zachęta przy marce bez dowodu handlowego, etykieta #reklama bez nazwy firmy), `brak` (neutralna wzmianka, krytyka, zaprzeczenie, ostrzeżenie przed oszustwem).

Pola: firma (wzmianka, kandydaci z wykazów, status tożsamości, transgraniczność), reklamujący (twórca, trwałe ID kanału), dowody (`evidenceRefs`), jawność oznaczenia (`disclosure.state`: `jawna_w_opisie` / `jawna_w_mowie` / `jawna_w_obrazie` / `jawna_flaga_platformy` / `nie_znaleziono_w_zakresie` / `nie_sprawdzono`, z listą modalności sprawdzonych i niesprawdzonych), język materiału z metodą.

Tożsamość firmy: dopasowanie aliasu do wpisów z `knf_domy_maklerskie`, `knf_banki_maklerskie`, `knf_oddzialy_zagr_FI`, `knf_notyfikacje_zagr_FI`, `esma_mif_passport_to_PL`. Wynik `identityStatus`: `ustalona` (domena linku lub pełna nazwa prawna wskazuje jeden wpis), `kandydaci` (kilka wpisów), `brak_wpisu_w_przejrzanych_wykazach`, `nieustalona`. Wpis w wykazie notyfikacji oznacza `crossBorder: true`. Brak wpisu w jednym wykazie nie dowodzi braku uprawnień ([Temat 1](../zrodla-uknf/TEMAT-1.md)).

#### Oś (ii) przesłanki właściwe dla wypowiedzi osoby trzeciej

Zasada nadrzędna: reguły z [tabeli M2](../zrodla-uknf/KRYTERIA-M2.md) opisują materiały marketingowe firmy inwestycyjnej. Na wypowiedź finfluencera przechodzą tylko wtedy, gdy materiał można traktować jako komunikat firmy rozpowszechniany przez osobę trzecią. Operacyjnie: `adRelationship.status ∈ {zadeklarowana, udokumentowana}` i twierdzenie dotyczy produktu lub usługi tej firmy. Bez relacji to samo zdanie jest opinią twórcy, oznaczane `poza_zakresem_M1` i nie flagowane. Przy relacji `prawdopodobna` przesłanka ma status `warunkowa` i może dać najwyżej `uzupełnij`.

| ID typu | Przesłanka | Podstawa źródłowa | Zakres zastosowania | Typowy kontrargument |
|---|---|---|---|---|
| `U1 nieujawniona_wspolpraca` | Dowód relacji handlowej bez oznaczenia reklamy w zbadanym zakresie | [Brief](../zrodla-uknf/BRIEF.md) §2 M1 (reklamy podmiotów trzecich) i §3 „Korzyści” (weryfikacja zasad współpracy firmy z podmiotami reklamującymi). Pośrednio KRYTERIA ID 2 (art. 24 ust. 3 MiFID II), które pakiet wiąże z materiałem firmy | Relacja `udokumentowana` lub `prawdopodobna`. Status `udokumentowana` przesłanki wymaga sprawdzenia oznaczenia w pełnym opisie, mowie i obrazie | Oznaczenie w modalności, której nie analizowano (flaga YouTube, kadr, przypięty komentarz); polecenie organiczne bez wynagrodzenia; link afiliacyjny do produktu spoza wykazu |
| `U2 oznaczenie_niejednoznaczne` | Oznaczenie istnieje, ale bez nazwy firmy albo w miejscu o niskiej widoczności | KRYTERIA ID 2 („jednoznacznie oznaczono”) w transferze jak wyżej | Tylko przy relacji `zadeklarowana/udokumentowana`. Sama nie daje `skieruj` (limit punktów poniżej progu), najwyżej `uzupełnij` | Ocena widoczności i wystarczalności oznaczenia to ocena prawna; wycinek nie pokazuje układu strony |
| `U3 podmiot_spoza_wykazu` | Polskojęzyczna promocja podmiotu, którego nie dopasowano do żadnego przejrzanego wykazu, albo dopasowano do ostrzeżeń KNF | Brief §2 M1 (firmy zarejestrowane w Polsce i zagraniczne działające transgranicznie); Temat 1 (definicje, wskazane wykazy). Lista ostrzeżeń KNF (`knf_warnings_parsed.json`) to źródło zespołu spoza pakietu | Relacja co najmniej `prawdopodobna`, materiał po polsku, nazwa lub domena firmy w dowodzie | Brak wpisu w jednym wykazie nie dowodzi braku uprawnień; kolizja nazw; podmiot spoza reżimu firm inwestycyjnych (np. kryptoaktywa) |
| `U4 zysk_bez_ryzyka` | Twierdzenie o potencjalnym zysku z produktu reklamowanej firmy bez bezpośrednio towarzyszącej informacji o istotnym ryzyku | KRYTERIA ID 3 (art. 44 ust. 2 lit. b rozp. 2017/565) w transferze warunkowym | Relacja `zadeklarowana/udokumentowana`; ten sam produkt (zasada „to samo ryzyko i produkt” z Q/M2); ostrzeżenie szukane w opisie, mowie w oknie czasowym wokół twierdzenia i w kadrach | Osobisty wynik lub opinia, nie obietnica firmy; ostrzeżenie w innej modalności; twierdzenie o rynku, a nie o produkcie; zakres okna sąsiedztwa to metoda zespołu |
| `U5 obietnica_lub_prognoza` | Pewny/gwarantowany zysk, konkretna przyszła stopa zwrotu lub wynik historyczny podany bez zastrzeżenia | KRYTERIA ID 15 (art. 44 ust. 6), ID 14 (art. 44 ust. 4 lit. d), ID 12a/12b (art. 44 ust. 4) w transferze warunkowym | Jak U4. ID 15 każe zgłosić samo wystąpienie prognozy; przy osobie trzeciej zgłaszamy ją tylko w kontekście relacji | Ironia, cytat cudzej obietnicy, scenariusz hipotetyczny; ogólne „brak gwarancji” jest szersze od wymaganego zastrzeżenia |
| `U6 aprobata_nadzoru` | Sugestia, że KNF lub inny organ zatwierdza produkt albo gwarantuje bezpieczeństwo | KRYTERIA ID 17, 18 (art. 44 ust. 8) w transferze warunkowym | Jak U4 | Neutralna informacja „firma jest nadzorowana przez KNF” nie jest sugestią aprobaty (to już test w `analysis/test_engine.py`, `test_neutral_supervision`) |
| `U7 sygnał_M3` | Oferta indywidualnego doboru instrumentów przez twórcę | Brief §2 M3 | To nie jest przesłanka M1 i nie daje punktów M1. Tworzy odsyłacz do kolejki M3 | Edukacja, zaprzeczenie doradztwu (istniejące wzorce `NO_ADVICE`) |

Każda przesłanka ma status: `kandydat` (znaleziony fragment, bez oceny zakresu), `warunkowa` (zastosowanie zależy od brakującego faktu lub modalności), `udokumentowana` (zakres spełniony, dosłowny cytat z lokalizatorem, kontrdowody przeszukane w dostępnym pokryciu bez wyniku), `obalona` (znaleziono kontrdowód; zostaje w audycie), `poza_zakresem_M1`.

#### Oś (iii) siła dowodu

Składniki: modalność (opis autora, napisy autora, napisy automatyczne, ASR z ufnością, OCR kadru, metadane platformy), dosłowność cytatu (dopasowanie do tekstu źródła i jego skrótu), lokalizator (URL wersji, sekunda lub zakres znaków), pokrycie materiału (`coverage`), niezależne potwierdzenie w drugiej modalności, czas obserwacji i wersja.

#### Oś (iv) wpływ na odbiorców

`reach` przechowuje statystyki z platformy wraz z datą i źródłem (`subscribers`, `views`, `observedAt`, `source`, `hidden`). Z niego wynika wyłącznie `priority.acquisition` (kolejność pobrania mowy/obrazu u C) i `priority.review` (kolejność w kolejce przy równym statusie). Funkcja kwalifikacji nie czyta `reach`. Test kontrolny: ten sam materiał z różnymi `reach` daje identyczne `reviewDecision`, `reviewScore` i `premises`.

### 2. Decyzja, rejestr i punkty siły sygnału

`reviewDecision.value ∈ {skieruj, uzupełnij, bez_sygnału}`. `adRegistry` jest osobnym polem i może współistnieć z każdą decyzją.

Reguła decyzji (wersja projektowa `investwatch-m1-qual-0.1`):

1. `skieruj`: co najmniej jedna przesłanka `udokumentowana` i `reviewScore.value >= próg` (domyślnie 60, ustawiany w panelu kalibracji).
2. `uzupełnij`: którakolwiek przesłanka `warunkowa`; albo przesłanka `udokumentowana` poniżej progu; albo relacja `zadeklarowana/udokumentowana/prawdopodobna` przy braku głównej modalności treści (dla wideo: mowa lub pełne napisy); albo `identityStatus` nieustalony tam, gdzie od niego zależy przesłanka U3. Decyzja podaje listę brakujących danych.
3. `bez_sygnału`: w pozostałych przypadkach. Etykieta w UI: „nie stwierdzono w zbadanym zakresie” z wypisanym zakresem.

`adRegistry.included = true` dla relacji `zadeklarowana` lub `udokumentowana`. Relacja `prawdopodobna` daje `adRegistry.candidate = true` (sekcja „do potwierdzenia”). Wpis rejestru: firma z kandydatami z wykazu, reklamujący, treść (cytat), URL, czas obserwacji, klucz kampanii (twórca + firma) i historia odczytów.

`reviewScore` to punkty siły sygnału 0–100, nie prawdopodobieństwo. Pola: `state ∈ {wyliczony, brak_podstaw}`, `value` (liczba lub null), `scale`, `threshold`, `rulesVersion`, `components[]`, `reason` przy `brak_podstaw`. Jest oddzielony od `semantic.cosineSimilarity` (E5) i od `reach`.

Asymetria pokrycia: obecność przesłanki można policzyć na częściowym materiale, ale „0 punktów, brak przesłanek” wolno podać tylko przy pokryciu głównej modalności. Inaczej `state: brak_podstaw` z powodem, np. „zbadano 26-znakowy wycinek opisu; mowa i obraz niedostępne”.

Punkty startowe (do strojenia przez G na zbiorze strojenia; nie są skalibrowane):

| Składnik | Punkty |
|---|---|
| Baza typu: U5 50, U6 50, U4 40, U1 35, U3 30, U2 15 | jak obok |
| Dosłowny cytat z lokalizatorem (sekunda lub zakres znaków w wersji) | +15 |
| Modalność: opis lub napisy autora +10; ASR z ufnością ≥ 0,8 lub OCR +5; ASR < 0,8 0 | jak obok |
| Potwierdzenie w drugiej niezależnej modalności | +10 |
| Kontrdowody przeszukane w pełnym pokryciu bez wyniku | +10 |
| Status `warunkowa` | limit 45 (poniżej progu) |
| U2 samodzielnie | limit 40 |
| Kolejna niezależna przesłanka | +10 do maksimum, łącznie ≤ 100 |

`reviewScore.value` = maksimum punktów przesłanek plus premia za kolejne. E5 może jedynie zgłosić fragment-kandydat do sprawdzenia regułami. Podobieństwo E5 pozostaje w `semantic` i nie dodaje punktów.

### 3. Rozstrzygnięcia dla wierszy próby Q dotyczących M1

| Materiał testowy | adRelationship | premises | coverage | reviewDecision | adRegistry | reviewScore | Uzasadnienie |
|---|---|---|---|---|---|---|---|
| youtube:xtMqKkFO-0M, youtube:04mmNbAlHFo (stan dziś) | `zadeklarowana`, firma `kandydaci` (6884980, 9439233), oznaczenie `jawna_w_opisie` | brak | `minimalne`: wycinek opisu 26 znaków, brak mowy, obrazu, flagi platformy | `uzupełnij` (brak: pełny opis, mowa, obraz) | tak, jedna kampania, dwa materiały | `brak_podstaw` | Jawna współpraca to wpis do rejestru. Brak przesłanek nie jest stwierdzony, bo nie zbadano treści filmu. Poza kolejką kontroli |
| Ten sam materiał po pobraniu mowy przez C, bez twierdzeń o zysku | `zadeklarowana`, `jawna_w_opisie` (+ `jawna_w_mowie`, jeśli padnie) | brak | `pełne` dla mowy | `bez_sygnału` | tak | `wyliczony`, 0 | Prawidłowa promocja bez osobnego uchybienia |
| Edukacja, nazwa brokera w neutralnym kontekście | `brak` | brak (twierdzenia twórcy → `poza_zakresem_M1`) | dowolne | `bez_sygnału` | nie | `wyliczony` 0 lub `brak_podstaw` przy minimalnym pokryciu | Materiał znajdziesz przez wyszukiwanie i wzmiankę o marce. Brak automatycznej flagi |
| Wyraźnie ujawniona prawidłowa promocja, brak osobnego uchybienia | `zadeklarowana` | brak | `pełne` | `bez_sygnału` | tak | `wyliczony`, 0 | Rejestr współprac, poza kolejką |
| Jawna współpraca + odrębne udokumentowane twierdzenie o zysku bez ostrzeżenia | `zadeklarowana` | U4 `udokumentowana`: cytat, ID 3, `evidenceRef` z linkiem `…&t=Ns` | `pełne` (mowa, opis, kadry) | `skieruj` | tak | `wyliczony`, ≥ 60 (np. 40+15+5+10 = 70) | Flaga z cytatem, kryterium i linkiem do sekundy. Rejestr i skierowanie współistnieją |
| Identyczny materiał na dużym i małym kanale | identyczne | identyczne | identyczne | identyczna | identyczny | identyczny | Różni się tylko `priority.acquisition/review` |
| Opis bez ostrzeżenia, brak dostępu do mowy i obrazu | np. `zadeklarowana` | U4 `warunkowa` (ostrzeżenie może być w mowie lub kadrze) | `częściowe`, luki: mowa, obraz | `uzupełnij` | tak (gdy relacja jawna) | `wyliczony`, ≤ 45 | Widać zakres i lukę. Wniosek o braku ostrzeżenia w całym filmie wstrzymany |
| Materiał syntetyczny albo ręcznie przesłany | wyliczane normalnie | wyliczane normalnie | jak w materiale | wyliczana normalnie, `queueEligible: false` | wyliczany, oznaczony `origin` | jak w materiale | `origin ∈ {syntetyczny, operator}` widoczne. Poza domyślną kolejką i poza rzeczywistym rejestrem w domyślnym demo |
| Firma transgraniczna promowana po polsku (np. eToro (Europe) Ltd, ID 9651212 w notyfikacjach) | `zadeklarowana`, `crossBorder: true`, język `pl` z metodą | brak lub U1–U6 jak wyżej | dowolne | jak w pozostałych wierszach | tak | jak w pozostałych wierszach | W zakresie M1 z briefu. Brak dopasowania do żadnego wykazu → U3 `warunkowa`, `uzupełnij`, nie `skieruj` |

Uwaga do syntetycznych przykładów demo: `demo-aurora-kod` (zachęta przy marce w mowie, brak oznaczenia w opisie) przy nowej regule ma relację `prawdopodobna` i U1 `warunkowa`, więc `uzupełnij`, nie `skieruj`. Zachęta nie dowodzi relacji handlowej, a obrazu nie zbadano. Dodatkowo materiał jest syntetyczny, więc wypada z domyślnej kolejki.

### 4. Kształt danych

Przykład A: rzeczywisty rekord youtube:xtMqKkFO-0M (fikstura `fixtures/raw/discovery/2026-11-21.json`). Wartości zasięgu są puste, bo Atom ich nie podaje.

```json
{
  "id": "youtube:xtMqKkFO-0M",
  "module": "M1",
  "origin": "rynek",
  "rulesVersion": "investwatch-m1-qual-0.1",
  "adRelationship": {
    "status": "zadeklarowana",
    "basis": "deklaracja_nazwana",
    "signalScore": 94,
    "advertiser": {"creatorId": "youtube:UCnmJzS-tFT7DlxIMFxYGcHw", "handle": "DETERMINACJA-OFFICIAL"},
    "firm": {
      "mention": "XTB",
      "identityStatus": "kandydaci",
      "candidates": [
        {"registryId": 6884980, "name": "XTB S.A.", "category": "Firmy inwestycyjne - Domy maklerskie",
         "sourceFile": "data/probe-snapshots/knf/knf_domy_maklerskie.json", "checkedAt": "2026-11-21"},
        {"registryId": 9439233, "name": "XTB Ltd", "category": "Notyfikacje zagranicznych firm inwestycyjnych na terytorium RP",
         "sourceFile": "data/probe-snapshots/knf/knf_notyfikacje_zagr_FI.json", "checkedAt": "2026-11-21"}
      ],
      "crossBorder": "nieustalone",
      "reason": "Marka pasuje do dwóch podmiotów; w zbadanym wycinku brak linku lub domeny wskazującej operatora."
    },
    "disclosure": {"state": "jawna_w_opisie", "evidenceRef": "ev-1",
                   "checked": ["description_fragment"], "notChecked": ["speech", "frames", "platform_paid_promotion_flag"]},
    "language": {"value": "pl", "method": "tekst tytułu i opisu", "note": "krótki tekst"},
    "evidenceRefs": ["ev-1"]
  },
  "adRegistry": {"included": true, "campaignKey": "youtube:UCnmJzS-tFT7DlxIMFxYGcHw|XTB",
                 "firstObservedAt": "2026-11-21T15:40:13.808887+00:00"},
  "premises": [],
  "reviewDecision": {
    "value": "uzupełnij",
    "reason": "Jawna współpraca z marką XTB. Treści filmu nie zbadano, więc nie można stwierdzić ani wykluczyć przesłanek.",
    "missing": ["pełny opis", "mowa lub napisy", "kadry", "flaga płatnej promocji"],
    "queue": "niepełne_dane",
    "queueEligible": true
  },
  "reviewScore": {
    "state": "brak_podstaw", "value": null,
    "scale": "punkty siły sygnału 0–100; nie prawdopodobieństwo",
    "threshold": 60, "rulesVersion": "investwatch-m1-qual-0.1", "components": [],
    "reason": "Zbadano 26-znakowy wycinek opisu (sampled). Mowa i obraz niedostępne."
  },
  "evidence": [
    {"id": "ev-1", "kind": "description", "modality": "description", "text": "Partnerem odcinka jest XTB",
     "match": "verbatim", "url": "https://www.youtube.com/watch?v=xtMqKkFO-0M",
     "textSha256": "d245bd33bc2209dda4e312e8c2e9508fbc42b3eb36386d6b33a61663ba15d108",
     "sourceUrl": "https://www.youtube.com/feeds/videos.xml?channel_id=UCnmJzS-tFT7DlxIMFxYGcHw",
     "responseSha256": "6540a1ac08c6940a8508831da9f0c5b00e197f7e01bcdac7ba3ca507815e2764",
     "sourceVersion": 1, "observedAt": "2026-11-21T15:40:13.808887+00:00"}
  ],
  "coverage": {
    "status": "minimalne",
    "modalities": {
      "title": {"state": "przeanalizowano"},
      "description": {"state": "fragment", "chars": 26,
                      "originalTextSha256": "f88d4e266c32f2d0861b1ac693dcf1987117ccaa50fa887f74a042f202662716",
                      "note": "Zachowano wycinek; pełny tekst ma inny skrót."},
      "captions": {"state": "niedostępne", "reason": "Atom nie zawiera napisów"},
      "speech": {"state": "niedostępne", "reason": "audio nie pobrano"},
      "frames": {"state": "niedostępne", "reason": "obrazu nie pobrano"},
      "platformFlags": {"state": "niedostępne", "reason": "Atom nie podaje oznaczenia płatnej promocji"}
    },
    "gaps": ["Nie można stwierdzić braku twierdzeń o zysku ani obecności ostrzeżeń w filmie."]
  },
  "reach": {"subscribers": null, "views": null, "observedAt": null, "source": "brak w Atom"},
  "priority": {"acquisition": "nieustalony", "review": "nieustalony", "basis": "reach", "affectsScore": false},
  "score": null,
  "summary": "Rejestr reklam: jawna współpraca z XTB. Do uzupełnienia: treść filmu nie została zbadana.",
  "reviewSuggestion": {"source": "rules-m1-qual", "version": "investwatch-m1-qual-0.1", "state": "uncertain",
                       "reason": "Jawna współpraca; brak treści filmu do oceny przesłanek."}
}
```

Przykład B: youtube:04mmNbAlHFo daje identyczny wynik poza `id`, `url`, `publishedAt`. Wspólny `campaignKey` sprawia, że rejestr pokazuje jedną kampanię z dwoma materiałami.

Przykład C: kształt skierowania. To ilustracja wymyślona na potrzeby kontraktu (`origin: syntetyczny`), nie rzeczywisty materiał.

```json
{
  "origin": "syntetyczny",
  "adRelationship": {"status": "zadeklarowana", "disclosure": {"state": "jawna_w_mowie", "evidenceRef": "ev-2"}},
  "premises": [{
    "id": "pr-1", "type": "U4 zysk_bez_ryzyka",
    "claim": "Twierdzenie o potencjalnym zysku z ETF w reklamowanej firmie bez towarzyszącej informacji o ryzyku.",
    "quote": "Na ETF-ach w tej aplikacji spokojnie zrobicie dwadzieścia procent rocznie",
    "evidenceRef": "ev-3",
    "basis": {"source": "KRYTERIA-M2 ID 3", "provision": "art. 44 ust. 2 lit. b rozporządzenia (UE) 2017/565",
              "basisScope": "pakiet UKNF, materiały firmy", "transfer": "warunkowy: relacja zadeklarowana i ten sam produkt"},
    "scope": {"requires": ["relacja zadeklarowana lub udokumentowana", "produkt: ETF tej firmy",
                           "ostrzeżenie szukane w opisie, w mowie ±60 s i w kadrach (okno to metoda zespołu)"],
              "satisfied": true},
    "counterEvidence": {"searched": ["mowa 0–100%", "pełny opis", "kadry co 2 s"], "found": [],
                        "possibleExplanations": ["ostrzeżenie w przypiętym komentarzu (poza zakresem)",
                                                 "wypowiedź może opisywać osobisty wynik"]},
    "status": "udokumentowana",
    "strength": {"points": 70, "components": [["baza U4", 40], ["cytat z sekundą", 15], ["ASR ≥ 0,8", 5], ["kontrdowody przeszukane", 10]]},
    "legalStatus": "przesłanka_do_kontroli"
  }],
  "evidence": [{"id": "ev-3", "kind": "audio", "modality": "speech_asr", "text": "Na ETF-ach w tej aplikacji spokojnie zrobicie dwadzieścia procent rocznie",
                "start": 312.4, "end": 316.9, "confidence": 0.86, "method": "vosk-pl", "url": "https://www.youtube.com/watch?v=EXAMPLE&t=312s",
                "mediaVersion": "sha256:…"}],
  "reviewDecision": {"value": "skieruj", "queueEligible": false},
  "reviewScore": {"state": "wyliczony", "value": 70, "threshold": 60}
}
```

#### Zgodność wsteczna z obecnym Finding

| Pole Finding v1 | Po zmianie |
|---|---|
| `score` (0–100) | Dla M1 przyjmuje `reviewScore.value` (null przy `brak_podstaw`). Dawny wynik relacji przechodzi do `adRelationship.signalScore`. M2/M3 bez zmian |
| `summary` | Krótko: rejestr, decyzja i powód. Bez słów „naruszenie”, „niezgodność” |
| `evidence[]` | Zachowuje `{kind, text, start?, end?, url?}`; dochodzą `id`, `modality`, `match`, `textSha256`, `observedAt`, `sourceVersion`, `confidence`, `method` |
| `checks[]` | Dla M1 opcjonalnie lista przesłanek w kształcie `{id, label, state, evidence}` dla pulpitu, który już czyta `checks` |
| `reviewSuggestion` | Pochodna `reviewDecision`: `skieruj → review`, `uzupełnij → uncertain`, `bez_sygnału → no_signal`, `source: rules-m1-qual`. Pulpit filtruje dziś po tym polu |
| `signalType`, `descriptionDisclosure*`, `possibleUndisclosedPromotion`, `modalityComparison` | Zostają przez jedną wersję jako pola diagnostyczne. Decyzji z nich nie wywodzimy |

Starsze rekordy: rekord M1 bez `reviewDecision` albo z `rulesVersion` innym niż bieżący dostaje `requalification: {state: "do_przeliczenia", reason, fromRulesVersion}`. Pulpit nie umieszcza go w kolejce kontroli do czasu przeliczenia. Worker przelicza z zapisanego Capture (tabela `versions` przechowuje capture). Ręczne decyzje analityka (`status`, `revision`, `history`, notatka) nie są nadpisywane. Jeśli przeliczenie zmieni decyzję sprawy, którą analityk już rozpatrzył, system dopisuje wpis historii „zmiana kwalifikacji X → Y (reguły A → B)” i ustawia `reviewStale: true`.

### 5. Plan modułu i testów

`analysis/qualification.py` (czyste funkcje, bez sieci, bez modelu):

- `registry_index()` buduje indeks aliasów z datowanych kopii wykazów KNF i paszportów ESMA. Alias → lista wpisów, z odrzuceniem nazw przekreślonych (`<strike>`) jako nazw historycznych oznaczanych osobno.
- `resolve_firm(capture, mentions)` zwraca kandydatów, status tożsamości i transgraniczność; domena linku z opisu rozstrzyga kandydata.
- `ad_relationship(capture, firm)` korzysta z istniejących wzorców `PARTNER`, `DISCLOSURE_LABEL`, `REFERRAL`, `CTA`, `DENIAL`, `FRAUD_*` z `engine.py` (import, bez kopiowania), dodaje deklarację wynagrodzenia i flagę platformy.
- `coverage(capture)` wylicza stan każdej modalności z pól Capture (`provenance.sampled/truncated`, `contentHash` wobec `originalTextSha256`, `segments` z metodą, `frames`, `mediaStatus`).
- `extract_premises(capture)` wyszukuje kandydatów U1–U7 w każdej modalności z lokalizatorem.
- `apply_scope(premise, relation, firm, coverage)` ustala status przesłanki i kontrdowody.
- `score(premises, coverage)` oraz `decide(...)` zwracają `reviewScore`, `reviewDecision`, `adRegistry`.
- `qualify(capture) -> dict` łączy wszystko i zwraca pola z sekcji 4. `priority(reach, relation)` to osobna funkcja wywoływana przez H, aby `qualify` nie widziała zasięgu.
- W `analysis/semantic.py` gałąź M1 `review_suggestion` będzie mapować `reviewDecision` zamiast `signalType`.

Przypadki testowe (`analysis/test_qualification.py`):

| # | Wejście | Oczekiwany wynik |
|---|---|---|
| 1 | Rzeczywisty youtube:xtMqKkFO-0M z fikstury | relacja `zadeklarowana`, kandydaci {6884980, 9439233}, `adRegistry.included`, `uzupełnij`, `brak_podstaw`, `premises == []` |
| 2 | Rzeczywisty youtube:04mmNbAlHFo | jak 1, ten sam `campaignKey` |
| 3 | Rekord 1 + segmenty mowy bez twierdzeń, `speech: pełne` | `bez_sygnału`, `wyliczony 0`, rejestr tak |
| 4 | Rekord 1 + segment „zrobicie 20% rocznie” bez ostrzeżenia, pokrycie pełne | U4 `udokumentowana`, `skieruj`, `evidence` z `start`, link `&t=` |
| 5 | Jak 4, ostrzeżenie o ryzyku w mowie 20 s później | U4 `obalona`, `bez_sygnału`, kontrdowód w `counterEvidence.found` |
| 6 | Jak 4, mowa dostępna, kadry niedostępne | U4 `warunkowa` albo `udokumentowana` z luką w kadrach; zapis decyzji do uzgodnienia z J (pytanie J2) |
| 7 | „Na przykładzie XTB pokazuję, czym jest zlecenie limit” | relacja `brak`, `bez_sygnału`, rejestr nie |
| 8 | „Zarobiłem 30% na akcjach w XTB” bez relacji | U4 `poza_zakresem_M1`, `bez_sygnału` |
| 9 | Opis z jawną współpracą i „pewny zysk”, bez mowy i obrazu | U5 `warunkowa`, `uzupełnij`, luka widoczna, punkty ≤ 45 |
| 10 | Test 4 z `reach` duży i mały | identyczne `qualify()`; różne `priority` |
| 11 | Dowolny przypadek z `synthetic: true` lub `platform: upload` | `origin` ≠ rynek, `queueEligible: false` |
| 12 | Jawna współpraca z eToro po polsku | kandydat 9651212, `crossBorder: true`, rejestr tak |
| 13 | Jawna współpraca z marką spoza wykazów | U3 `warunkowa`, `uzupełnij`, powód „brak wpisu w przejrzanych wykazach” |
| 14 | Kod polecający z linkiem do domeny firmy, brak oznaczenia, pełne pokrycie | relacja `udokumentowana`, U1 `udokumentowana`, `skieruj` |
| 15 | „Otwórz rachunek w XTB” bez innych dowodów, tylko opis | relacja `prawdopodobna`, U1 `warunkowa`, `uzupełnij`, rejestr kandydat |
| 16 | „Przelew od domu maklerskiego dostaję za każdy nowy rachunek” | relacja `udokumentowana` (obecny FN `wynagrodzenie`) |
| 17 | „Firma jest nadzorowana przez KNF” w sponsorowanym materiale | brak U6 |
| 18 | Zaprzeczenie, krytyka, ostrzeżenie przed oszustwem (istniejące przypadki z `test_engine`) | relacja `brak`, rejestr nie |
| 19 | Pusty tekst i brak segmentów | `brak_podstaw`, powód „brak treści” |
| 20 | Stary Finding bez `reviewDecision` | `requalification.state == "do_przeliczenia"`, status analityka zachowany (test po stronie H/M) |

Zmiany istniejących asercji: `test_public_partner_declaration_has_verbatim_evidence` (oczekuje `score == 94`) oraz `test_m1_review_uses_rule_evidence_not_model_label` (oczekuje `review` dla „Partnerem odcinka jest XTB.”). Obie zmienią się na rejestr i `uncertain`/`no_signal` zależnie od pokrycia. `tests/core/test_job_review.py` (zakres M) oczekuje dziś `review` dla tej deklaracji.

Wejścia wymagane od B (YouTube):
- pełny opis z `fullText: true` albo jawnym `truncated` i skrótem pełnego tekstu;
- linki z opisu z domeną (do rozstrzygnięcia operatora firmy);
- `reach` z datą: subskrybenci kanału, wyświetlenia filmu, znacznik ukrytych statystyk;
- czas trwania, język z metodą, kategoria Shorts;
- flaga płatnej promocji, jeśli Data API v3 ją udostępnia (B ma to sprawdzić; nie wiem, czy pole jest dostępne dla naszego klucza);
- trwałe ID kanału i filmu oraz wersja treści.

Wejścia wymagane od C (multimedia):
- `segments[{start, end, text, confidence, modality: speech_asr|captions_author|captions_auto, method, language}]`;
- `frames[{t, text, method: ocr, bbox?, frameSha256}]`;
- `mediaCoverage{speech: {state, windows, durationSec}, frames: {state, intervalSec}}` oraz powód niedostępności;
- wersja mediów (skrót) wiążąca segmenty z wersją filmu;
- gotowy link do sekundy w oryginale (`https://www.youtube.com/watch?v=ID&t=Ns`) niezależnie od lokalnego odtwarzacza.

### 6. Granice wiedzy prawnej i komunikacja

Rozstrzygnięcia, do których nie mamy kompetencji ani źródła w pakiecie:
- Czy i kiedy obowiązki z art. 24 ust. 3 MiFID II i art. 44 rozporządzenia 2017/565 obejmują treść publikowaną przez finfluencera. To zależy od warunków współpracy (zlecenie, wynagrodzenie, akceptacja treści), których nie widzimy. Dlatego U2, U4–U6 mają transfer warunkowy.
- Czy oznaczenie „Partnerem odcinka jest XTB” w opisie jest wystarczające co do miejsca, momentu i formy. To kwestia oceny prawnej i ewentualnie przepisów konsumenckich spoza pakietu. System podaje stan `jawna_w_opisie` i listę niesprawdzonych modalności.
- Zakres usług objętych notyfikacją transgraniczną. Wykaz podaje kategorię, a nie każdą usługę. System pokazuje kategorię i datę kopii.
- Obowiązki dotyczące rekomendacji inwestycyjnych (MAR), standardowych ostrzeżeń dla CFD i reżimu kryptoaktywów. Pakiet UKNF ich nie zawiera. System nie tworzy przesłanek z tych podstaw i oznacza je jako poza zakresem.
- Okno sąsiedztwa „bezpośrednio towarzyszy” dla mowy i wideo. Wartość ±60 s to metoda zespołu, którą G ma zamrozić i pokazać obok wyniku.

Komunikacja w produkcie:
- Każda przesłanka ma `legalStatus: "przesłanka_do_kontroli"` i podstawę z pakietu oraz osobną informację, że zastosowanie wobec osoby trzeciej zależy od ustalenia relacji.
- Wzór treści: „Przesłanka do kontroli: [twierdzenie]. Podstawa w pakiecie UKNF: [ID, przepis]. Możliwe wyjaśnienie: [kontrargument]. To nie jest stwierdzenie naruszenia.”
- Słowa „naruszenie”, „niezgodne”, „nielegalne” nie występują w `summary`, `reason` ani etykietach decyzji.
- `bez_sygnału` brzmi zawsze „nie stwierdzono w zbadanym zakresie: [modalności]”.

### 7. Otwarte pytania

Do H:
1. Czy `qualify()` wywołujesz w `engine.analyze` (wtedy kalibracja używa nowych pól) czy w `jobs.evaluate`? Rekomenduję `engine.analyze` dla M1.
2. Fingerprint w `api/store.py` obejmuje `score` i `reviewSuggestion`. Zmiana reguł utworzy nową wersję każdej sprawy M1. Czy dodasz `rulesVersion` do sygnatury i rozdzielisz wersję treści od wersji kwalifikacji, żeby przeliczenie nie wyglądało jak zmiana materiału?
3. Zdarzenie `high_risk` przy `score >= 70`: proponuję wyzwalać je przejściem `reviewDecision` na `skieruj`, a nie progiem `score`.
4. `score: null` przy `brak_podstaw`: czy kalibracja i filtr ryzyka obsłużą to jako „wstrzymane” (osobny licznik), zamiast rzutować na 0?
5. Rejestr reklam: osobny endpoint czy filtr na `/v1/state` (`adRegistry.included`)? Potrzebny klucz kampanii i historia odczytów.
6. `origin` jako pole Capture (`rynek`/`syntetyczny`/`operator`) zamiast obecnych `synthetic: true` i `platform: upload`. Czy przyjmujesz?
7. `reviewStale: true` zamiast nowego statusu sprawy, żeby nie zmieniać enumu new/reviewing/closed. Czy wystarcza pulpitowi?
8. Kto jest właścicielem indeksu aliasów firm (plik danych obok `data/probe-snapshots/knf/`)?

Do J:
1. Czy jawna współpraca z niezbadaną treścią filmu ma trafiać do `uzupełnij` (moja rekomendacja: tak, bo „brak sygnału” bez obejrzenia treści byłby twierdzeniem bez podstaw), czy do `bez_sygnału` z widoczną luką?
2. Czy do `skieruj` wystarcza mowa przy niedostępnych kadrach? Rekomendacja: tak, jeśli przeszukano pełną mowę i opis, a brak kadrów jest pokazany jako luka.
3. Czy akceptujesz zasadę, że kryteria z M2 (U4–U6) stosujemy do osoby trzeciej tylko przy zadeklarowanej lub udokumentowanej relacji?

### 8. Zestawienie z projektem H (`docs/lanes/2026-11-21-fable-h-kontrakt.md`, stan z 18:35 UTC)

Projekt H powstał równolegle. Zgodne: `reviewSuggestion` wyprowadzane z decyzji, E5 tylko w `semantic`, zasięg tylko w `reach`, `value=null` z powodem przy braku podstaw, `coverage` jako obiekt z lukami i wstrzymanym wnioskiem, czysta funkcja `qualify`. Do rozstrzygnięcia przy uzgodnieniu:

| Temat | H | D | Propozycja |
|---|---|---|---|
| Kody decyzji | `refer`, `complete`, `no_signal`, `insufficient` | `skieruj`, `uzupełnij`, `bez_sygnału` + `reviewScore.state=brak_podstaw` | Przyjąć kody H w danych, polskie etykiety w UI. `insufficient` = brak jakiejkolwiek treści lub błąd `qualify`; materiał z relacją i bez treści filmu to `complete` |
| Wpis do rejestru | `adRelationship.state ∈ declared, label_only, cta, referral` | `included` tylko dla relacji zadeklarowanej lub udokumentowanej; `cta` i etykieta bez nazwy firmy jako kandydat | Wersja D. Zachęta przy marce występuje też w poradnikach, a rejestr ma zestawiać reklamy |
| Firma | `company.registryId` pojedynczy | `firm.candidates[]` z `identityStatus` | Lista kandydatów, bo „XTB” pasuje do 6884980 i 9439233 |
| Miejsce wywołania | `jobs.evaluate` po `analyze` i `suggest` | `engine.analyze` | Kalibracja (`engine.calibration`) wywołuje tylko `analyze`. Przy wywołaniu w `jobs` panel progu nie zobaczy nowej decyzji |
| Legacy `score` przy null | 0 z `scoreBasis: "insufficient"` | null | Przyjąć wariant H dla zgodności, pod warunkiem że kalibracja liczy takie rekordy jako wstrzymane, a nie TN/FN |

Odpowiedzi na pytania H: (1) rejestr reklam to `adRelationship`/`adRegistry`, nie stan decyzji; (2) `value` jest liczbą dla `refer` i dla `complete` z przesłanką; dla `no_signal` 0 tylko przy pokryciu głównej modalności, w przeciwnym razie null; (3) C wylicza stan modalności z faktycznie wykonanych okien, D wylicza `conclusionHeld` i luki istotne dla przesłanek; (4) zmiana reguł nie otwiera zamkniętych spraw, tylko ustawia `reviewStale`; przejście na `refer` dodatkowo dodaje sprawę do kolejki powtórnego przeglądu.

## Current State

Fala 2 (moduł, bez wpięcia w silnik i kolejkę): `analysis/qualification.py` (`qualify`, `coverage`, `priority`, reguły `investwatch-m1-qual-1.0`), generator indeksu firm `analysis/firm_index.py` i dane `analysis/firm-index.json` (16 marek z ID z kopii wykazów KNF z 2026-11-21 i 3 reklamodawców spoza M1), testy `analysis/test_qualification.py`. Pola według uzgodnionego kontraktu H §3.3. Decyzje J wdrożone na stałe: U1 zawsze `refer`, oznaczenie w mowie lub kadrze obala U1, opinia bez relacji poza kolejką, `refer` wymaga `reasons[]` i `moments[]`. Wyniki na realnych materiałach (także stan opis+mowa+kadry z próbek agenta C): `fixtures/raw/review-compare/qualification-results.json`. Relacja z samym linkiem lub kodem ma status `probable` (rejestr: `candidate`) zgodnie z R3 kontraktu H; U1 nadal daje `refer` (J5). Poniżej stan z fali 1.

Wykonano: rozpoznanie i projekt kontraktu (ten dokument). Kod bez zmian. Odczyt obecnego zachowania silnika na dwóch rekordach XTB wykonano lokalnie w tej sesji (wynik w sekcji 0). Przykład C jest ilustracją, nie danymi. Punkty w sekcji 2 to wartości startowe bez kalibracji. Agent D: Opus (claude-opus-5-5), wysiłek zgodnie ze zleceniem.

Znany przypadek błędu: obecny silnik kieruje jawną deklarację do przeglądu (`score 94`, `reviewSuggestion: review`). Powtórzenie: `analyze()` i `review_suggestion(cap, {"status": "unavailable"}, finding)` na `youtube:xtMqKkFO-0M` z `fixtures/raw/discovery/2026-11-21.json`.

## Next Step

Uzgodnić z H pytania 1–8 i z J pytania 1–3, potem w osobnym worktree napisać `analysis/qualification.py` z testami 1–19 i przełączyć gałąź M1 w `analysis/semantic.py`.

## Verification

- `python3 -B` z `analysis.engine.analyze` i `analysis.semantic.review_suggestion` na dwóch rekordach XTB: oba `score 94`, `signalType declaration`, `reviewSuggestion review/rules`.
- `analysis.engine.calibration(60)` dla M1: `yt-partner 94 tp`, `kod 66 tp`, `wynagrodzenie 12 fn`, `krytyka 24 tn`, `odmowa 12 tn`, `cytat 66 fp`.
- Fala 1: testy nie uruchamiane (bez zmian w kodzie).
- Fala 2: `.runtime/venv/bin/python -B -m unittest analysis.test_qualification` → 27 testów OK; `-m unittest discover -s analysis -t . -p 'test_*.py'` → 73 testy OK, 2 pominięte (`TestLocalModel`, brak `INVESTWATCH_SEMANTIC_DIR`); `python -m analysis.firm_index --check` → aktualny.

## Fallback / Cut

Jeśli moduł nie zdąży: minimalna poprawka w `review_suggestion` (gałąź M1) mapuje `declaration` bez innych sygnałów na `no_signal` z oznaczeniem rejestru, a pulpit ukrywa M1 z samą deklaracją w kolejce kontroli. Wycofanie modułu: H nie wywołuje `qualify()`, pola są opcjonalne, Finding v1 działa jak dziś.

## Handoff

- Zmienione: wyłącznie ten plik.
- Weryfikacja: odczyt silnika opisany w Verification; brak testów kodu.
- Otwarte: kontrakt z H, decyzje J (sekcja 7), dane od B i C, ponowne oznaczenie `yt-partner` przez G.
- Następny krok: jak w Next Step.
