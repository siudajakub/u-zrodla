# Kontrakty pierwszej integracji

Kontrakty do implementacji zatwierdza kapitan. Przykłady wyznaczają próby akceptacyjne. Stan lokalnego kolektora opisuje [monitoring](../MONITORING.md), definicje wariantów i formatów błędów rozwija [plan](../archiwum/PLAN-REALIZACJI.md).

| Właściciel → odbiorca | Wejście i sukces | Awaria i zachowanie odbiorcy |
|---|---|---|
| core-cases → source-adapters | POST /v1/scans z sourceId, mode i requestId → 202 i scanId. Ten sam requestId zwraca ten sam przebieg | 404 dla nieznanego źródła, 503 dla niedostępnej kolejki. Widok ostatniego sukcesu pozostaje dostępny |
| source-adapters → analysis-evidence | Capture v1 obejmuje platformę, ID publikacji, profil, oryginalny URL, datę obserwacji, opcjonalną datę publikacji, tekst, typ materiału, wersję, hash, tryb live/replay/import oraz odsyłacz do źródła. Powtórka A→A zachowuje wersję, A→B zachowuje obie | Zmiana formatu źródła oznacza błąd parsera. Pusta odpowiedź, brak daty i rzeczywista wartość zero mają osobne znaczenia |
| analysis-evidence → core-cases i analyst-desk | Finding v1 identyfikuje dokument i wersję, moduł, kryterium, sygnał, wynik modelu i jego wersję, wskazanie dowodu, czas oraz pochodzenie. M2 zwraca również sposób pomiaru, viewport i stan strony | Brak odpowiedniej modalności daje „brak danych”. Brak pewnego wpisu w rejestrze powoduje „do wyjaśnienia”. Powtórzenie zdarzenia nie tworzy nowej sprawy |
| core-cases → analyst-desk | PATCH /v1/cases/{id} z expectedRevision, statusem i uzasadnieniem zapisuje kolejną decyzję. Zdarzenie WebSocket ma trwałe ID. Fikcyjny aneks prowadzi do kolejnej wersji porównania | 409 powoduje ponowne pobranie sprawy. Po reconnect klient dociąga pominięte zmiany. Bez odpowiedzi firmy sprawa ma stan „oczekujemy” |
| analysis-evidence → analyst-desk | Calibration v1 zwraca próg, identyfikator zbioru, TP/FP/TN/FN, liczność niezależnych grup i koszt operacyjny. Dwa progi można porównać na jednym zbiorze | Pusty mianownik daje „brak podstaw do obliczenia”. Import demonstracyjny i duplikat opisu nie zwiększają liczby niezależnych przykładów |

Zmianę pola kapitan zapisuje w tablicy z nazwą producenta, konsumentów i testem wstecznej zgodności. Podczas integracji właściciel API utrzymuje schemat i migracje. Przykłady kontrolne obejmują deklarację partnerstwa i neutralną wzmiankę, widoczne i ukryte ostrzeżenie, edukację i indywidualną ofertę usługi.

## Format wersji demonstracyjnej z 21 XI

Kolektor eksportuje `collectors.discovery.discover(mode, known_ids)` zwracające słownik z `creators`, `captures` i `sources` (listy). Tryby replay/live. Klucz twórcy `id` jest trwały i obejmuje platformę. Creator ma id, name, platform, url, discoveredVia. Capture ma id, creatorId, title, url, platform, description, module (M1/M2/M3) i opcjonalne segments [{start,end,text}], mediaUrl, brand i provenance. Źródło ma name, status, count oraz opcjonalne error. Umawiamy też `analysis.engine.demo_captures()` i `analysis.engine.analyze(capture)` → słownik finding z id, title, module, platform, creatorId, url, score (0–100), summary, evidence [{kind,text,start?,end?,url?}], opcjonalnie mediaUrl i checks [{id,label,state,evidence}]. Bez orzeczeń o naruszeniu prawa. Funkcje offline są wywoływane w procesie workera. Ścieżka plików demonstracyjnych analysis/media/ jest serwowana pod /media/.

API same-origin. GET /v1/state → {creators, findings, sources, scans, events, calibration}, finding ma także status, revision, history. POST /v1/scans {mode,requestId} → 202 {scanId,status}, klient ponawia GET /v1/state. PATCH /v1/cases/{id} {status,expectedRevision,note} → {id,status,revision}, konflikt 409. Statusy new, reviewing, closed. POST /v1/cases/{id}/contract {endDate,label} → porównanie z datą publikacji w fikcyjnej sprawie i audyt. GET /v1/calibration?threshold=60 → {threshold,tp,fp,tn,fn,n}. WebSocket /v1/events sygnalizuje odświeżenie. GET /v1/health. API serwuje gotowe pliki z web/ i web/dist/. Rozszerzenie pól kompatybilne wstecz.

## Weryfikacja po rewizji źródeł

Pole score przechowuje priorytet reguł. Sugestia semantyczna podaje wersję modelu, zakres fragmentu i niejednoznaczność. W bieżącej linii reviewSuggestion pozwala pulpitowi wyświetlić skierowanie do przeglądu wraz z uzasadnieniem, fragmentem i pochodzeniem. To rozróżnia sprawę do zbadania od potwierdzonego naruszenia. Brak lokalnego modelu ma własny stan. Identyfikator sprawy WWW może zawierać ukośniki. Odbiór obejmuje odczyt karty, wersji i zapis z expectedRevision na takim identyfikatorze.

M2 wiąże measurements w odpowiednim checks z rzeczywistym ekranem i wyciągiem DOM danego przechwycenia. Wnioski o urządzeniu dotyczą wykonanego stanu, a nie samej szerokości podanej w żądaniu. Koszt pokazywany przy suwaku to 2 × FN + FP. Układ próby, progi i pochodzenie etykiet muszą być widoczne przy interpretacji. [Wymagania źródłowe](../zrodla-uknf/README.md) · [Odbiór](../ODBIOR-UKNF.md)

## Obieg decyzji operatora

`PATCH /v1/cases/{id}` zapisuje rozstrzygnięcie lokalnie i zwraca aktualną sprawę. Przekazanie do kontroli oznacza zmianę kolejki w InvestWatch. Karta, jej wiersz na liście i odpowiedź po zapisie mają `workflowStage`. Pomiar źródła i decyzja operatora mają osobne pola (`route` i `lastDecision`).

| `resolution` | Dozwolony `workflowStage` przed decyzją | Etap i kolejka po decyzji |
|---|---|---|
| `refer_to_control` | `review`, `supplement` | `control` — przekazane do kontroli |
| `complete_data` | `review`, `control` | `supplement` — do uzupełnienia przez operatora |
| `no_signal`, `close` | `review`, `control`, `supplement` | `closed` — zakończone |
| `control_result` | `control` | `closed` — zakończone z wynikiem kontroli w `note` |
| `data_received` | `supplement` | `review` — dane odnotowane w `note`, wraca do oceny |
| `reopen` | `control`, `supplement`, `closed` | `review` — powód ponownego otwarcia w `note` |

```json
{
  "resolution": "control_result",
  "expectedRevision": 7,
  "reviewedVersion": 2,
  "note": "Potwierdzono datę i treść oznaczenia na opublikowanej wersji.",
  "requestId": "75d45a6c-8af8-4cef-8dc2-3506999fc576"
}
```

- `note` jest obowiązkowe, zawiera do 2000 znaków i musi mieć treść po obcięciu białych znaków. `expectedRevision` jest obowiązkowe. Podaj `reviewedVersion`, jeśli użytkownik ogląda konkretną wersję źródła. `requestId` jest opcjonalne, ma do 160 znaków z alfabetu ASCII `[A-Za-z0-9_.:-]`. Ponowienie tego samego żądania z tym samym identyfikatorem zwraca aktualną kartę bez nowej rewizji, wpisu w historii ani zdarzenia.
- Konflikt rewizji, wersji lub dozwolonego etapu oraz użycie tego samego `requestId` dla innej decyzji dają `409` z `detail` i `current` (`revision`, `status`, `version`, `workflowStage`). Po konflikcie odśwież kartę i zachowaj treść szkicu. `422` oznacza nieprawidłowe żądanie, np. puste uzasadnienie, nieznaną akcję lub `status` sprzeczny z `resolution`.
- Zapis dopisuje `history` z `action: "decision"`, wersją materiału, uwagą oraz `fromStage` i `workflowStage`. Publikuje zdarzenie `case`. Po nim odśwież kartę, listy i liczniki. Starsi klienci nadal mogą zapisać `status` bez `resolution`. Statusy `reviewing` i `new` pozostają dostępne. Etap `control` albo `supplement` dla wcześniejszej decyzji wynika z jej `resolution` i pasującego statusu `reviewing`.
- `GET /v1/queues/control`, `.../supplement` i `.../closed` działają z tymi samymi filtrami co `.../review`. `incomplete` nadal wskazuje automatycznie wykryte braki przed decyzją. `adRegister` zależy od materiału reklamowego i może zawierać sprawę na dowolnym etapie. `offersM2`, `offersM3` i `all` zachowują dostęp do ewidencji.
- Nowa treść lub dowód po decyzji ustawia `pendingReReview` i zachowuje decyzję oraz etap. Zmiana automatycznej trasy ustawia `reviewStale`. Sprawa zakończona może pojawić się jako sygnał do ponownego rozpatrzenia w `review`, jeśli znów spełnia kryteria kolejki. Przed kolejnym rozstrzygnięciem wymaga `reopen`. Ponowne otwarcie i udokumentowanie otrzymanych danych włączają sprawę do `review` również poniżej progu.

### Raport decyzji

`GET /v1/report?module=all&queue=control&format=csv` eksportuje pasujące sprawy M1, M2 i M3. Parametr `queue` przyjmuje `control`, `supplement` albo `closed`. Format `json` zwraca te same kolumny i wiersze z paginacją. Mieszany CSV domyślnie obejmuje wszystkie pasujące wiersze. Jawny `limit` ogranicza rozmiar strony, a `X-Next-Cursor` wskazuje początek kolejnej.

Raport mieszany podaje `modul`, `id`, tytuł, podmiot, `url` źródła i dane kwalifikacji. W każdej z trzech kolejek eksport uwzględnia `etap`, `rodzajDecyzji`, `dataDecyzji`, `uzasadnienieDecyzji` i `sprawdzonaWersja`. Wersja pochodzi z ostatniej decyzji, również gdy obok niej dostępny jest nowszy materiał. Starsze wiersze bez historii mają puste pola decyzji. Raport jednego modułu w tych kolejkach dopisuje dane decyzji do istniejących kolumn. Dotychczasowe domyślne raporty M1, M2 i M3 zachowują wcześniejszy format. CSV jest kodowany w UTF-8 z BOM i zabezpiecza komórki rozpoczynające się jak formuła arkusza.
