# Kontrakty pierwszej integracji

Kontrakty do implementacji zatwierdza kapitan. Przykłady wyznaczają próby akceptacyjne. Stan lokalnego kolektora opisuje [monitoring](../MONITORING.md), definicje wariantów i formatów błędów rozwija [plan](../PLAN-REALIZACJI.md).

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
