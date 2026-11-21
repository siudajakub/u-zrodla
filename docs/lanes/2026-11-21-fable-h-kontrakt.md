# Lane H: uzgodniony kontrakt v2

- Owner: agent H (integracja), zlecenie Fable
- Branch: hack/integration (HEAD 491094d, bez zmian w kodzie)
- State: PLANNED (uzgodniony kontrakt v2 po wynikach D, I, B i decyzjach Fable i J; żadnej implementacji)
- Updated: 2026-11-21
- Model: claude-sonnet-5-5 (Sonnet 5.5). Poziom namysłu ustawił orkiestrator w sesji (nagłówek: niski), nie „high”.

Dokument: inwentarz stanu (§1), luki (§2), uzgodniony kontrakt v2 z tabelą pól (§3), testy przed implementacją (§4), kolejność wdrożenia w krokach (§5), rozbieżności do rozstrzygnięcia (§6), ryzyka (§7) i ograniczenia (§8). Odwołania `plik:linia` dotyczą HEAD 491094d. Kod jest czytany tylko do odczytu, z dwoma pomiarami z §1.8. Wersja z 18:35 (projekt jednostronny) została zastąpiona; zmiany wylicza §3.0.

## 1. Inwentarz stanu

### 1.1 Schemat SQLite (`api/store.py:13-37`)

Jedna baza `cases.sqlite3` w `INVESTWATCH_STATE` (`store.py:12`), WAL (`store.py:64`), osobne połączenie na transakcję, zapis przez `BEGIN IMMEDIATE` (`store.py:45-59`). Kolejka Huey to osobny plik `queue.sqlite3` (`jobs.py:204`).

| Tabela | Klucz | Zawartość | Uwaga |
|---|---|---|---|
| scans | id (uuid4 hex), request_id UNIQUE | mode (live/replay/upload), status, payload, result (JSON), lease_until, owner, attempts | `store.py:14-18` |
| creators | id | `body` JSON bez kolumn | `store.py:20` |
| sources | id (`id` lub `name`) | `body` JSON | `store.py:21`, klucz `store.py:124` |
| cases | id (= id capture, z ukośnikami), kolumny: body, fingerprint, status (new/reviewing/closed), revision, updated | `body` = `{**capture, **finding, version, mode}` | `store.py:22-25`, `168` |
| versions | (id, version) | signature, observed (czas zapisu, nie czas obserwacji, `store.py:170`), capture JSON, finding JSON | `store.py:26-29` |
| history | seq | case_id, at, action (capture/decision/inquiry/contract), note, details JSON | `store.py:30-33`; brak autora, brak numeru wersji w decyzji (`server.py:127`) |
| events | seq | at, kind (scan/case/finding/high_risk), ref, message | `store.py:34-36` |
| audio_cache | fingerprint | wynik ASR 45 s lub retry_at | `store.py:19`, `listen.py:375-406` |

Nie ma: `PRAGMA user_version`, tabeli migracji, kluczy obcych (włączone `foreign_keys=ON`, ale schemat nie deklaruje FK), indeksów poza PK/UNIQUE, tabeli progów, szeregów czasowych statystyk, tabeli ścieżek odkrycia.

`init()` (`store.py:61-65`) to `executescript(CREATE TABLE IF NOT EXISTS ...)`. Nowe kolumny w istniejącej tabeli wymagają osobnego mechanizmu migracji, którego dziś nie ma.

### 1.2 Obiekty

| Obiekt | Gdzie powstaje | Klucz i pola dziś |
|---|---|---|
| Creator | `catalogs.py:75-80` (Apple), `catalogs.py:243-248` (PeerTube), `social.py:17-21` (seed), `crosslinks.py:78-83` (kandydat YouTube), `sites.py` | `id` z prefiksem platformy (`apple-podcasts:701`, `peertube:host/handle`, `youtube:UC…`, `youtube-candidate:<hash>`); name, platform, url, discoveredVia, opcjonalnie discovery {query, rank, sourceUrl, responseSha256, observedAt}, feedUrl, firstDiscoveredAt, qualification, isSeed. Store dodaje isNew, firstSeen, firstMode, lastMode, lastSeen (`store.py:119-120`) |
| Capture | `collectors/common.py:capture` | id, creatorId, title, url, platform, description (≤24 000 zn.), module M1/M2/M3, observedAt, publishedAt, contentHash, materialType, provenance {sourceUrl, observedAt, responseSha256, scope, truncated, mode, fixture}, extra (brand, segments, mediaUrl, audioUrl, coverage (string!), asrScope…). W trybie live do captura trafia też `mode` (`discovery.py:166-169`) |
| Finding | `analysis/engine.py:347-357` | whitelista pól z captura (`engine.py:350-354`) plus module, score, summary, evidence[{kind,text,start?,end?,url?,confidence?}], rulesVersion (`engine.py:14` = investwatch-rules-pl-1.2), extra z m1/m2/m3 (signalType, descriptionDisclosureStatus/Type/DisclosedBrand, possibleUndisclosedPromotion, modalityComparison, checks, registry…). Dopisuje `jobs.py:232-237`: semantic, reviewSuggestion {state, source, version, reason, evidence} |
| Case | `store.case_dict` (`store.py:179-181`) | body + id, status, revision, updatedAt, history |
| Scan | `store.scan_dict` (`store.py:78-81`) | id=scanId, mode, status (queued/running/done/partial/failed), createdAt, updatedAt, attempts + result (liczniki, warnings, error) |
| Source | `common.source_result` (`common.py:115-132`) | id, name, url, count, status (ok/empty/error/stale/…), observedAt, lastSuccessAt, scope, rawCount, creatorIds. Store dodaje mode, checkedAt, lastSuccessAt (`store.py:129-130`) |
| Event | `store.event` (`store.py:67-68`) | id=seq, at, kind, ref (id sprawy lub skanu), message. Bez ładunku, to sygnał odświeżenia |

### 1.3 Wersjonowanie i rewizje

- **Wersja** (`versions.version`) rośnie tylko, gdy zmieni się sygnatura (`store.py:147-149`): SHA-256 z pól treści (`content_keys`, `store.py:135`: title, url, description, segments, mediaUrl, publishedAt, module, brand, platform, creatorId, sha256, contractDemo; M2 plus m2EvidenceRevision) oraz z wyniku analizy (summary, score, checks, evidence, semantic, modalityComparison, reviewSuggestion). Czasy obserwacji świadomie pominięte (`store.py:134`).
- **Rewizja** (`cases.revision`) jest jednym licznikiem dla czterech różnych zdarzeń: nowa wersja treści (`store.py:171-173`), decyzja analityka (`server.py:126`), korespondencja (`server.py:152`), porównanie umowy (`server.py:179`). Klient trzyma expectedRevision (`server.py:101-103`, 409).
- **Decyzja analityka**: kolumna `status` plus wpis historii action=decision z notatką (`server.py:126-127`). Przy `ON CONFLICT DO UPDATE` kolumna status nie jest nadpisywana (`store.py:171-173`), więc ręczna decyzja przetrwa nową wersję treści (test `test_live_lineage.py:137-161`). Nic nie oznacza, że decyzja dotyczy starszej wersji.
- **Historia progów**: nie istnieje. `/v1/calibration?threshold=` (`server.py:75-82`) liczy symulację na fiksturach (`engine.py:360-396`, `evaluationStatus: illustrative_not_held_out`), wynik jest w `lru_cache`. Do realnej kolejki próg nie jest stosowany. Kolejkę buduje klient z `reviewSuggestion.state` (`web/src/neutral-desk.jsx:202`). Jedyny próg po stronie serwera to stałe 70 dla zdarzenia `high_risk` (`store.py:175`).

### 1.4 Przepływ skanu

1. `POST /v1/scans {mode: live|replay, requestId, sourceId: "all"}` (`server.py:47-50`, `88-93`). `sourceId` przyjmuje wyłącznie `"all"`, mimo że `contracts.md` opisuje wybór źródła. Błąd ValueError (inny tryb dla tego requestId) to 409.
2. `jobs.submit` → `store.create_scan` (`store.py:83-100`): ten sam `request_id` zwraca ten sam skan i `created=False`. Ponowienie nieudanego skanu tylko dla `upload` (`jobs.py:208`, `store.py:89`). Nieudany skan live/replay z tym samym requestId pozostaje failed na stałe.
3. `enqueue` → wywołanie zadania Huey `process(key)` (`jobs.py:213-217`, `267`) tylko wkłada je do `queue.sqlite3`. Błąd kolejki jest logowany, skan zostaje `queued` w dzienniku (odzyskuje `recover`, brak 503 zgodnie z `contracts.md`).
4. Worker (`jobs.py:302-325`): przy starcie `submit("replay","bootstrap-m2-rendered-v1")`, co `INVESTWATCH_DISCOVERY_INTERVAL` (domyślnie 14 400 s) `submit("live", "scheduled-<interwał>-<slot>")`, co 30 s `recover()` (skany queued lub running z wygasłą dzierżawą, `jobs.py:296-300`).
5. `claim` (`jobs.py:219-226`): atomowo status=running, owner, lease 900 s, attempts+1. Bez heartbeatu i bez przedłużania dzierżawy.
6. `build` (`jobs.py:228-265`): `discover(mode, known_ids, known_creators)` → w live `sample_audio` (jeden wycinek 45 s na skan, `listen.py`) → M2 (`staged_captures`, `apply_rendered`) → w replay dokłada `demo_captures()` → dla każdego captura `analyze` + `suggest` + `review_suggestion`. Całość w pamięci; każdy skan analizuje wszystkie captury od nowa (w tym E5), bo sygnatura zależy od wyniku analizy.
7. `apply_scan` (`store.py:106-177`) w jednej transakcji `BEGIN IMMEDIATE`: twórcy, źródła, sprawy. Po stronie właściciela: `active != owner` → wynik odrzucony (`jobs.py:276-278`). Status końcowy done / partial / failed zależnie od źródeł z błędem (`jobs.py:280-284`).
8. Zdarzenia → tabela events → WebSocket `/v1/events?after=ID` odpytuje bazę co 0,6 s (`server.py:215-244`). Bez `after` (lub `-1`) startuje od bieżącego maksimum bez doganiania (`server.py:226-228`). Klient musi sam trzymać ostatni id.

### 1.5 Co store odświeża przy ponownym odczycie tej samej sygnatury

Gałąź `before and fingerprint==signature` (`store.py:158-166`), tylko w trybie live:

- zwykła sprawa: `observedAt` i `provenance` nadpisane w całości (nie scalone), `mode="live"`;
- sprawa M2: tylko `latestM2Observation`;
- replay nie zmienia nic, a replay nigdy nie nadpisuje sprawy live (`store.py:152`) ani twórcy live (`store.py:114`) ani źródła live (`store.py:127`);
- kolumny `revision`, `updated`, `status` nie zmieniają się, co jest właściwe i trzeba to zachować.

Twórca: `{**old, **creator, …}` (`store.py:119`), nowe wartości zawsze wygrywają, brak szeregu czasowego. `discovery.py:_remember` (`discovery.py:51-66`) z kolei zachowuje pierwszą `discovery`/`discoveredVia` twórcy. Źródło: `{**source, mode, checkedAt}`.

### 1.6 Deduplikacja i identyfikatory

- Jedyny klucz deduplikacji to `capture.id`. Przykłady: `youtube:<videoId>` (Atom, `social.py:24-27`), `apple-podcasts:<show>:episode:<digest(guid)[:32]>` (`catalogs.py:185`), `peertube:<videoId>`, `web:bossa.pl/oferta/doradztwo` (fikstura `bossa-discovery-2026-11-21.json`), `upload-<scanId>`.
- W `discover` dedup to `captures.setdefault(id, item)` (`discovery.py:76`), czyli pierwszy wygrywa i drugie ujęcie tego samego materiału znika bez śladu. Z kolei `captures.update(...)` dla bazy watch (`discovery.py:126`) nadpisuje. Zachowanie zależy więc od kolejności wątków.
- Twórca YouTube z Atom ma id `youtube:<UC…>` (`Source.key`, `watch_sources.py:51-53`), a kandydat z oEmbed `youtube-candidate:<hash profilu>` bez trwałego ID kanału (`crosslinks.py:78-83`). Brak tabeli aliasów łączącej kandydata z potwierdzonym kanałem.
- Identyfikatory z ukośnikami: trasy `/v1/cases/{key:path}` (`server.py:105,114,119,131,156`) i test HTTP po `quote(key, safe='')` (`test_site_routes.py:246-258`). Kolejność rejestracji ma znaczenie: `/versions/{n}` jest przed ogólną. Pułapka: id kończące się na `/inquiry`, `/contract` lub `/versions/<n>` byłoby źle rozcięte. Dziś żaden id tak nie wygląda, ale kontrakt v2 nie powinien dokładać kolejnych sufiksów po `{key:path}`.

### 1.7 Testy bazowe (`tests/core/`)

Cztery pliki, 9 testów (`test_store.py` 3, `test_job_review.py` 1, `test_live_lineage.py` 3, `test_site_routes.py` 2). Pokrywają: wersje A→B→A przy replay, tożsamość requestId, ponowienie upload, promocję provenance bez nowej wersji, edycję live zachowującą decyzję, utrwalanie twórców, odczyt/zapis HTTP dla id z ukośnikiem i 409, brak rejestru przy konfliktowym KRS. Nie pokrywają: wielu ścieżek odkrycia, statystyk, równoległego PATCH, restartu workera, reconnectu WebSocket, rekordu sprzed v2.

Pomiar bazowy (`.runtime/venv/bin/python -B -m unittest discover -s tests/core -p 'test_*.py'`): **Ran 9 tests in 0.906s, OK.** Systemowy `python3` nie ma fastapi, więc potrzebny jest venv projektu. Uwaga: import `api.jobs` w testach tworzy `queue.sqlite3` w domyślnym `.runtime/demo` (`jobs.py:203-204`), czyli test ma skutek uboczny poza katalogiem tymczasowym. Katalog jest ignorowany przez Git.

### 1.8 Pomiary dodatkowe (skrypt jednorazowy, tymczasowa baza, nic w repo)

Wywołania `store.apply_scan` na sztucznym capture `youtube:AAAAAAAAAAA`:

| Próba | Wynik | Wniosek |
|---|---|---|
| ten sam materiał z Atom (`reach.views=10`) i potem z API (`reach.views=999`, inna `provenance`) | changedFindings 0; w sprawie `reach.views=10`, `provenance` z API | statystyka z drugiego odczytu przepada, a ścieżka Atom jest nadpisana zamiast scalona |
| `publishedAt` jako `…+00:00` i potem `…Z` (ten sam instant) | nowa wersja (2) | niewystarczająca normalizacja czasu: Atom i API różnią się zapisem |
| opis pełny → skrócony „d...” → pełny (jak `search.list` vs `videos.list`) | wersje 3 i 4 | dwa źródła o różnej kompletności tworzą migotanie wersji |

## 2. Luki względem planu

| # | Wymaganie (REALIZACJA, „Wspólny kontrakt”) | Stan dziś | Skutek |
|---|---|---|---|
| L1 | discovery: metoda, zapytanie, pozycja, czas, wiele ścieżek na materiał | Capture nie ma pola discovery; ma jedną `provenance` (nadpisywaną `store.py:163`) i `setdefault` w `discovery.py:76`. Twórca ma jedną `discovery` bez metody i strony | Atom + API dają jedną ścieżkę zamiast dwóch; nie da się pokazać „skąd system to wziął” |
| L2 | reach: datowana statystyka oddzielona od zmiany treści | Brak. Capture z `reach` zapisze je tylko przy nowej wersji, w gałęzi „ta sama sygnatura” przepada (§1.8) | Licznik stoi w miejscu albo wymusza fałszywą wersję |
| L3 | oddzielenie licznika od nowej wersji | Sygnatura jest dobrą bazą (bez statystyk, bez czasów), ale łączy treść, dowody i wynik analizy w jedną sumę; brak powodu wersji | Nie wiadomo, czy wersja to nowy opis, nowy dowód z ASR czy nowa reguła |
| L4 | adRelationship | Rozproszone: brand, signalType, descriptionDisclosure*, possibleUndisclosedPromotion (`engine.py:203-224`) | Brak jednego obiektu (firma, twórca, dowód) |
| L5 | reviewDecision (skieruj, uzupełnij, bez sygnału) | `reviewSuggestion.state` ∈ review/uncertain/no_signal/unavailable (`semantic.py:242-277`) bez kryterium, twierdzenia, kontekstu i wyjaśnienia | D dostarcza treść, H miejsce i kolejki |
| L6 | reviewScore + wersja reguł/modelu, skala i znaczenie | `score` 0–100 + `rulesVersion` (`engine.py:355-356`); brak „nie da się wyliczyć”; podobieństwo E5 w `semantic` oddzielnie, ale `score` nie ma pola znaczenia | Niewystarczające dane muszą mieć wartość null z powodem, nie „0” |
| L7 | evidence z modalnością i czasem | `kind` (audio/description/screenshot/identity/registry), start/end, url; brak modality, wersji sprawy, współrzędnych klatki, odsyłacza do sekundy dla platformy (jest `mediaUrl#t=` tylko dla lokalnego pliku, `engine.py:185`) | UI nie może wiarygodnie odsyłać do sekundy w YouTube |
| L8 | counterEvidence | Zaprzeczenia i ostrzeżenia o oszustwie blokują sygnał (`engine.py:34-52,112-121`), ale nie są zwracane jako dowód | Kontrola ujemna niewidoczna dla analityka |
| L9 | coverage | Tekst w `coverage` tylko przy ASR (`listen.py:372`, string) oraz `descriptionDisclosureStatus` | Konflikt nazwy z obiektem v2; brak modalności i luk |
| L10 | stan „do ponownego przeliczenia” | Brak. Zmiana RULESET (`engine.py:14`) zmienia wynik i sygnaturę → nowa wersja każdej sprawy + zdarzenia `high_risk` (`store.py:175`) | Bump reguł zalewa kolejkę i nie odróżnia się od zmiany treści |
| L11 | zachowanie ręcznych decyzji | Działa dla `status` (§1.3), ale bez `decidedVersion` nie widać decyzji na starej wersji | Brak „wersja oczekuje na powtórny przegląd” (Q) |
| L12 | historia i przywracanie progu | Brak tabeli, brak progu w kolejce | Q wymaga progu zastosowanego do realnej kolejki |
| L13 | kolejki Q | Tylko filtr po stronie klienta; `/v1/state` zwraca wszystkie sprawy z historią (N+1 zapytań, `store.py:188`) | Przy setkach filmów YouTube stan się nie skaluje |
| L14 | wznowienie po limicie, kolejna strona | Brak kursora i stanu źródła; skan to jedno wywołanie w pamięci; dzierżawa 900 s bez heartbeatu (`jobs.py:225`) | Długi skan YouTube może zostać powtórzony przez drugiego właściwego właściciela i spalić limit |
| L15 | migracje | Brak wersji schematu (`store.py:61-65`) | Nowe kolumny wymagają kontrolowanej migracji, API i worker startują równolegle (Compose) |
| L16 | niezgodność dokumentu z kodem | `contracts.md` obiecuje sourceId i 503 dla kolejki; kod: tylko `all`, błąd kolejki jest połykany (`jobs.py:213-217`) | Trzeba zdecydować, co jest kontraktem |
| L17 | WebSocket | Brak sygnału reset przy `after` większym od maksimum (np. nowa baza), zdarzenia bez typowanego ładunku | Klient po odtworzeniu bazy cicho nic nie dostanie |
| L18 | aliasy twórców | `youtube-candidate:<hash>` i `youtube:UC…` to dwa różne wpisy tego samego kanału | Podwójne liczenie twórców, fałszywy „nowy twórca” |
| L19 | kolejność i miejsce wywołania kwalifikacji | `analyze()` jest wołane z `jobs.evaluate` (`jobs.py:233`) i z `calibration()` (`engine.py:373`), a `suggest`/`review_suggestion` tylko z `jobs.evaluate` (`jobs.py:234-236`) | Jeśli decyzja powstanie tylko w `jobs`, panel progu i kalibracja jej nie zobaczą |
| L20 | pochodzenie | Trzy pola: `mode` (live/replay/upload), `synthetic`, `contractDemo`, plus `platform:"upload"` | Brak jednego pola; synthetic w trybie replay jest nieodróżnialny od zwykłego replay bez znajomości fikstury |
| L21 | `isNew` twórcy | Przeliczane przy każdym skanie (`store.py:116,119`): po pierwszym zapisie wraca na false. I zmierzył 13 twórców z wyszukiwania z `isNew:false` | UI nie umie powiedzieć „nowy twórca”; potrzebny `firstSeenScanId` |
| L22 | dostępność materiału i język | Brak stanów usunięty/prywatny/nie-PL (próba Y) | Materiał znika z Atom bez śladu w sprawie |
| L23 | wariant kwalifikacji | Jedna reguła (`RULESET`), brak przełącznika i historii; model semantyczny dodany po `analyze` | Nie da się porównać reguł 1.2, kwalifikacji D i D + model na tych samych danych ani cofnąć wyboru |

## 3. Uzgodniony kontrakt v2

Ten rozdział zastępuje projekt jednostronny z 18:35. Źródła uzgodnienia: [D](2026-11-21-fable-d-kwalifikacja.md) (§7–8), [I](2026-11-21-fable-i-ux.md) (pola dla UI), [B](2026-11-21-fable-b-youtube.md), [OPENROUTER-M3](../fable/OPENROUTER-M3.md), rozstrzygnięcia Fable (R1–R9) i decyzje J (J1–J4).

### 3.0 Co się zmieniło względem projektu

| Obszar | Projekt 18:35 | Uzgodniony v2 |
|---|---|---|
| Kody decyzji | `reviewDecision.state` refer/complete/no_signal/insufficient | Te same cztery kody, pole nazywa się `reviewDecision.route` (nazwa z I, bo `reviewScore.value` też ma `value`). Polskie etykiety tylko w UI |
| Firma | `company.registryId` pojedynczy | `adRelationship.firm.candidates[]` + `identityStatus` (nazwa pola z D) |
| Rejestr reklam | stany declared/label_only/cta/referral wchodziły do rejestru | Tylko `declared` i `documented`. `probable` (sama zachęta, link, kod, etykieta bez firmy) to `adRegistry.state="candidate"`, w UI „do potwierdzenia” |
| Zasięg | pole obserwacyjne | Dodatkowo: wpływa wyłącznie na `priority`, nigdy na `reviewDecision`, `reviewScore` ani `queues[]` |
| Miejsce wywołania `qualify` | `jobs.evaluate` | `analysis.engine.analyze` dla M1 (jedno miejsce, widzą je kolejka, kalibracja i `jobs`) |
| `high_risk` | próg aktywnego wpisu | Przejście na `refer` kwalifikujące się do kolejki. Reguła aktywna dopiero po wyborze wariantu (§3.5); do tego czasu bez zmian (`score >= 70`) |
| Powtórny przegląd | `pendingReReview` | Dwie flagi: `pendingReReview` (nowa treść po decyzji) i `reviewStale` (zmiana trasy po decyzji). Enum statusu bez zmian |
| Pochodzenie | `mode` + `synthetic` + `contractDemo` | Jedno pole `origin`: live / replay / synthetic / upload |
| Zakładki | kolejki z mojego projektu | Te same nazwy + `all` i `demo`; przynależność wylicza API, UI tylko filtruje (R9) |
| Próg | jeden zestaw wpisów | Wpisy per wariant kwalifikacji (skale punktów różnią się między regułami 1.2 a kwalifikacją D) |
| Zasięg w API | `reach` skalarny | `reach.metrics{viewCount,likeCount,commentCount}` z `state` per metryka; szereg w `reach_samples`. Twórca: `creator.reach.metrics.subscriberCount` |
| Ścieżka odkrycia | pole `rank` | `position` (nazwa z B), `observedAt` (nie `at`), `scanId` nadaje H |
| Pokrycie | `coverage.modalities` obiekt z `speech`/`ocr` | Obiekt (mapa) z modalnościami `title`, `description`, `transcript`, `frames`, `platformFlags`; `blocksConclusion` (nazwa z I) |
| Dowody | `deepLink` | `sourceUrlAtTime` (nazwa z I); `modality` ∈ description/title/transcript/frame/page/registry/identity, a metoda w `method` |
| Wersja | `reason` content/evidence/analysis/rules | `reason` content/evidence/analysis, szczegóły (`rulesFrom/To`, `variantFrom/To`, `routeFrom/To`) w `details` |
| Wariant kwalifikacji | brak | Przełącznik z historią (§3.5) |
| Odtwarzalność modelu | brak | Cache wyników modelu (`model_cache`), wariant z modelem wyłącznie po walidacji, fallback na reguły |
| Nieoznaczona współpraca (decyzja J) | `probable` + U1 `conditional` → `complete` | Link śledzący lub kod twórcy bez oznaczenia w zbadanym zakresie to przesłanka U1 `documented` → `refer`, także przy nierozstrzygniętej tożsamości firmy. Oznaczenie znalezione w mowie lub kadrze obala przesłankę (`no_signal`, wpis w rejestrze reklam) |
| Opinia bez relacji (decyzja J) | `out_of_scope_m1` | Bez zmiany znaczenia: `no_signal`, poza `review`, widoczna w `all` |
| Uzasadnienie skierowania (decyzja J) | `reason` (jedno zdanie) | Obowiązkowe dla `refer`: `reasons[]` (3–5 zdań: co znaleziono, gdzie, czego nie znaleziono) i `moments[]` `{start,end,label,deepLink,evidenceId}`; `reason` zostaje jako skrót |
| Kadry (decyzja J) | `frames.state` evidence_only | Krok opcjonalny tylko dla materiałów z podejrzeniem; wynik jako `evidence` `kind:"frame"` z czasem; `coverage` rozróżnia `selected_moments` od `full` |

### 3.1 Zasady obowiązujące (rozstrzygnięcia Fable i decyzje J)

| ID | Zasada | Skutek w kontrakcie |
|---|---|---|
| R1 | Kody decyzji: `refer`, `complete`, `no_signal`, `insufficient` | `reviewDecision.route`. `insufficient` = brak jakiejkolwiek treści do oceny lub błąd `qualify` |
| R2 | Firma jako lista kandydatów z rejestru | `firm.candidates[]`; brak pojedynczego `registryId` w relacji |
| R3 | Do rejestru reklam tylko relacja zadeklarowana lub udokumentowana | `adRegistry.state="included"` ⇔ `adRelationship.status ∈ {declared, documented}`. `probable` → `candidate` |
| R4 | `reach` wpływa tylko na `priority` | `qualify` nie dostaje `reach`. `priority(reach, relation)` to osobna funkcja (D), wołana przez H po `qualify`. Test T26 |
| R5 | `qualify` w jednym miejscu | `analysis.engine.analyze(capture, *, semantic=None, variant=None)`, na końcu gałęzi M1. `jobs.evaluate` liczy `suggest` przed `analyze` i przekazuje wynik; `calibration()` woła to samo `analyze` z tym samym `variant` |
| R6 | `high_risk` po przejściu na `refer`, nie po progu score | Reguła przejścia jest property wariantu. Dla `rules_1_2` zostaje stara (`score >= 70`) |
| R7 | `reviewStale` / `pendingReReview` zamiast nowego statusu | `status` nadal new/reviewing/closed |
| R8 | `origin` jednym polem | live / replay / synthetic / upload |
| R9 | Zakładki wylicza API | `queues[]` w każdym rekordzie, `GET /v1/queues/{name}`, liczniki w `/v1/state` |
| J1 | System bada całą treść filmu przez opis i transkrypcję | `coverage.scope="description+transcript"`; wniosek `no_signal` wymaga obu w pełnym zakresie |
| J2 | Transkrypcja wystarcza do `refer` | `refer` dopuszczalny, gdy `frames.state` ≠ `full`; brak obrazu nie jest luką blokującą |
| J3 | Kadr tylko z momentu wskazanego przez transkrypcję, jako dowód | `frames[]` powstają tylko dla momentów z `reviewDecision.moments[]` mających `start`; `coverage.modalities.frames.state` ∈ `selected_moments` / `full` / `not_collected` |
| J4 | `complete` to stan przejściowy lub awaryjny | `reviewDecision.completeReason` ∈ `transcript_pending`, `transcript_unavailable`, `identity_unresolved`, `other_gap` |
| J5 | Podejrzenie nieoznaczonej współpracy → `refer`, także przy nierozstrzygniętym | Link śledzący lub kod twórcy w opisie lub transkrypcji bez oznaczenia w zbadanym zakresie → U1 `documented`, `route=refer`; `identityStatus` nie blokuje. Brak transkrypcji nie blokuje `refer` z opisu, blokuje tylko `no_signal`; `reasons[]` mówi wtedy, że mowy nie zbadano. Oznaczenie znalezione w mowie lub kadrze → przesłanka `refuted`, `route=no_signal`, `adRegistry=included` |
| J6 | Opinia bez relacji z firmą → poza kolejką | `adRelationship.status="none"`, `route=no_signal`, tylko `all` |
| J7 | Każde `refer` niesie `reasons[]` i `moments[]` | Pola obowiązkowe dla `refer`; `qualify` zwraca `insufficient` zamiast `refer` bez nich. UI pokazuje je w wierszu i karcie |
| J8 | Kadry: opcjonalne wzbogacenie tylko dla podejrzeń | Osobny krok po `qualify` (C); wynik dopisuje `evidence kind="frame"` z czasem i wymusza ponowne `qualify` (wersja `changeKind:"evidence"`) |

Zasada kolejności (decyzja Fable, pkt 3): **domyślna kolejka i zdarzenia `high_risk` nie zmieniają się, dopóki G nie zmierzy FP/FN na odłożonych kampaniach i Fable nie zatwierdzi wariantu.** Kod wdrażam w trybie cienia (§3.5): pola v2 są liczone i zapisywane od razu, ale `queues.review` i `high_risk` korzystają z aktywnego wariantu, a ten startuje jako `rules_1_2`. OpenRouter pozostaje eksperymentem poza workerem.

### 3.2 Trzy warstwy danych (bez zmian)

| Warstwa | Gdzie | Tworzy wersję? |
|---|---|---|
| Treść i analiza | `versions` + `cases.body` | tak |
| Obserwacje (ścieżki odkrycia, szereg `reach`, dostępność, ostatni skan) | tabele boczne `discoveries`, `reach_samples`, `creator_samples`, `case_meta` (dostępność, pierwszy i ostatni skan); bez kolumn w tabelach v1 | nie |
| Decyzje człowieka | `cases.status`, `history` (z `version`, `route`, `analysisSig` w szczegółach) | nie (rewizja) |

### 3.3 Ostateczna tabela pól

Skróty: producent B = `collectors/youtube.py`, C = media (`analysis/media_enrich.py`, `collectors/audio.py`), D = `analysis/qualification.py`, H = `api/*`, `collectors/discovery.py`, `analysis/engine.py`; konsument J1 = UI (web/), G = walidacja i kalibracja, M = QA. „Brak” = zachowanie, gdy pole nie istnieje w rekordzie lub źródło go nie dało. Zasada ogólna: brak klucza ≠ `null` (ustalone jako nieznane) ≠ `[]` (zbadano, nic nie znaleziono) ≠ `0`.

**Capture (wejście z adapterów)**

| Pole | Typ | Producent | Konsument | Zachowanie przy braku |
|---|---|---|---|---|
| `id` | string; kanonicznie `youtube:<videoId>` (jak Atom) | B, K, F | H, wszyscy | Wpis odrzucony przez walidator adaptera jako błąd parsera źródła, reszta wyniku zostaje |
| `creatorId` | string `youtube:<UC…>` | B | H, J1, G | Odrzucenie wpisu jak wyżej; kandydat bez ID ma `creator.status="candidate"` i alias później |
| `discovery[]` | `{method, adapter, queryKind, query\|null, position\|null, page\|null, sourceId, sourceUrl (bez klucza), observedAt, responseSha256, reason\|null, import:boolean}`; `method` ∈ data_api_search, data_api_playlist, atom, oembed, crosslink, ranking_import, apple_search, peertube_search, watch_sqlite, fixture, upload | B (jeden wpis na obserwację), H (scalanie, `scanId`, `firstSeenAt`, `lastSeenAt`, `seenCount`) | J1 (Źródła, szczegół), G (pokrycie wg ścieżki; `import:true` poza benchmarkiem Y), M | Rekord sprzed v2: brak klucza (nie zmyślamy ścieżki z `provenance`); UI używa `creator.discoveries`/`discoveredVia`. Adapter bez wpisu: odrzucony |
| `reach` | `{asOf, source, primary:"viewCount", metrics:{viewCount\|likeCount\|commentCount:{value:number\|null, state:"observed"\|"hidden"\|"unavailable"\|"not_collected", observedAt, source}}}` | B (z `statistics`; Atom daje `views` i `starRating`) | J1 (wiersz), D przez `priority()` | `{metrics:{}}` ze stanem `not_collected`, w UI „Zasięg nieznany”, nigdy 0. `state:"hidden"` → „statystyka ukryta przez autora” |
| `contentCompleteness` | `"full"\|"partial"` | B (opis z `search.list` = partial; `videos.list`/Atom = full), K | H (reguła wersji) | Domyślnie `partial`, gdy `provenance.truncated` lub `sampled`; inaczej `full`. Obserwacja niższej kompletności nie tworzy wersji |
| `youtube` | `{channelId, videoId, publishedAt, durationSec, isShort, defaultAudioLanguage, detectedLanguage, privacyStatus, paidPromotionFlag:true\|false\|null}` | B | D (flaga płatnej promocji, język), J1 | `null`; `paidPromotionFlag:null` = „nie sprawdzono”, wtedy `coverage.modalities.platformFlags.state="unavailable"` |
| `language` | `{declared\|null, detected\|null, method}`; `outOfScope:"language"\|null` | B (+ detektor tekstu) | D, J1 | `outOfScope:null`. Materiał `outOfScope` zostaje, trafia tylko do `all` |
| `availability` | `{state:"available"\|"unavailable"\|"private"\|"removed"\|"unknown", observedAt, reason}` | B | J1, M | `unknown`. Zmiana stanu nie tworzy wersji; ostatnia wersja zostaje |
| `priority.acquisition` | `{rank:number\|null, reason:string\|null}` (B: `scanPriority`) | B | H (kolejność pobrania), C | `null`, kolejność wg `observedAt` |
| `segments[]` (transkrypcja) | `{start,end,text,confidence?, method:"author_captions"\|"auto_captions"\|"asr", language, windowId}`; dotychczasowe `{start,end,text,confidence}` pozostają ważne | C | D, J1 (cytat, link do sekundy) | Brak klucza: `coverage.transcript` ze stanem `pending` lub `unavailable` |
| `frames[]` | `{t, text, method:"ocr", bbox?, frameSha256, evidenceFor:[evidenceId]}` — tylko dla materiałów z `route=refer` i momentów z `moments[]` | C (krok opcjonalny) | D, J1 | Brak: `frames.state="not_collected"`; to nie blokuje `refer` |
| `mediaCoverage` | `{transcript:{state, source:"author_captions"\|"auto_captions"\|"asr"\|"analyst"\|"none", windows:[{start,end}], durationSec\|null, reason\|null}, frames:{state:"selected_moments"\|"full"\|"not_collected", moments:[t], intervalSec\|null}}` | C | D (liczy `coverage`) | `transcript.state="unavailable"`, `reason:"nie pobrano"` |
| `mediaVersion` | string (sha256 pliku lub wersji napisów) | C | H (wiąże segmenty z wersją), D | Segmenty bez wersji: `evidence.sourceVersion` = wersja sprawy |

**Finding (wynik analizy; M1 z D, M2/M3 bez zmian i bez v2-pól oceny)**

| Pole | Typ | Producent | Konsument | Zachowanie przy braku |
|---|---|---|---|---|
| `origin` | `"live"\|"replay"\|"synthetic"\|"upload"` | H (`derive_origin`: synthetic lub contractDemo → synthetic; upload → upload; inaczej `mode`) | J1 (etykieta w wierszu), G (wyłączenie z prób), M | Wyliczane przy odczycie ze starych pól. Synthetic i upload poza kolejkami rzeczywistymi |
| `analysisVersion` | `{rules, model\|null, schema:number, variant}` | H (+ `rulesVersion` z D) | J1, G | `schema:1` → `needsRecalc:true` |
| `adRelationship` | `{status:"declared"\|"documented"\|"probable"\|"none"\|"unknown", basis, signalScore, advertiser:{creatorId, handle}, firm:{mention, identityStatus:"established"\|"candidates"\|"no_registry_entry"\|"unresolved", candidates:[{registryId, name, category, sourceFile, checkedAt}], crossBorder:true\|false\|"unresolved", reason}, disclosure:{state:"in_description"\|"in_speech"\|"in_frame"\|"platform_flag"\|"not_found_in_scope"\|"not_checked", where, text, evidenceId, checked:[], notChecked:[]}, language:{value, method}, evidenceRefs:[]}` | D | J1 (rejestr, szczegół), G, M | `status:"unknown"`, „Relacja reklamowa: nieustalona”. `not_found_in_scope` zawsze z zakresem w UI |
| `adRegistry` | `{state:"included"\|"candidate"\|"none", campaignKey (twórca+firma), firstObservedAt}` | D | J1, G | `none` |
| `premises[]` | `{id, type:"U1".."U7", claim, quote, evidenceRef, basis:{source, provision, basisScope, transfer}, scope:{requires:[], satisfied}, counterEvidence:{searched:[], found:[], possibleExplanations:[]}, status:"candidate"\|"conditional"\|"documented"\|"refuted"\|"out_of_scope_m1", strength:{points, components:[]}, legalStatus:"review_premise"}` | D | J1 (szczegół), G | `[]` = zbadano, brak; brak klucza = nie liczono |
| `reviewDecision` | `{route:"refer"\|"complete"\|"no_signal"\|"insufficient", reason (≤160 zn., jedno zdanie, bez nakazu), reasons:[string] (3–5 zdań: co znaleziono, gdzie, czego nie znaleziono; obowiązkowe dla refer), moments:[{start:number\|null, end:number\|null, label, deepLink, evidenceId}] (≥1, obowiązkowe dla refer; start/end null dla opisu), completeReason, requirement:{module,id,label,scope}\|null, claim:{text,evidenceId}\|null, alternative\|null, missing:[], decidedBy:"rules"\|"model"\|"rules+model", version, queueEligible:boolean}` | D; dla wariantu `rules_1_2` H mapuje `reviewSuggestion` (review→refer, uncertain→complete, no_signal→no_signal, unavailable→insufficient) | J1, G, M | Brak i `needsRecalc` → wiersz w `incomplete` z tokenem „Do ponownego przeliczenia”. `refer` bez `requirement`, `claim`, `reasons[]` lub `moments[]` nie powstaje: `qualify` zwraca `insufficient` z powodem (blokada trasy). UI pokazuje `reason` i pierwszy moment w wierszu, `reasons[]` i `moments[]` w karcie |
| `reviewScore` | `{state:"computed"\|"withheld", value:number\|null, scale:"0-100", band:"strong"\|"moderate"\|"weak"\|null, meaning, notComputableReason, rulesVersion, modelVersion\|null, components:[]}` | D | J1 („—” przy null), G | `value:null` + `notComputableReason`. Nigdy nie zawiera E5 ani `reach` |
| `counterEvidence[]` | jak `evidence[]` + `effect` | D | J1 | Brak klucza = „nie zbadano”; `[]` = „nie znaleziono w zbadanym zakresie” |
| `evidence[]` | dotychczasowe `{kind,text,start?,end?,url?,confidence?}` + `{id, role:"claim"\|"disclosure"\|"context", modality:"description"\|"title"\|"transcript"\|"frame"\|"page"\|"registry"\|"identity", method, match:"verbatim"\|"approximate", textSha256, mediaSha256?, url, sourceUrlAtTime, bbox?, windowId?, sourceVersion, observedAt, available:boolean, unavailableReason?}` | D (opis, rejestr), C (transkrypcja, kadry), E (M2) | J1 (przejście do dowodu), G, M | Bez `id` UI numeruje lokalnie, ale bez przejścia. Bez `url` element nie jest dostępnym dowodem. Dla YouTube bez `sourceUrlAtTime` UI dokleja `&t=` (I) |
| `coverage` | `{scope:"description+transcript", state:"full"\|"partial"\|"minimal"\|"none", modalities:{title:{state}, description:{state:"full"\|"fragment"\|"empty"\|"unavailable", chars, originalTextSha256?}, transcript:{state:"full"\|"partial"\|"pending"\|"unavailable", source, windows, durationSec, reason}, frames:{state:"selected_moments"\|"full"\|"not_collected", moments:[t], reason}, platformFlags:{state:"observed"\|"unavailable", paidPromotion:true\|false\|null}}, gaps:[{modality, code, reason}], blocksConclusion:boolean, label}` | D liczy `state`, `gaps`, `blocksConclusion`; C dostarcza stan transkrypcji (`mediaCoverage`) | J1, G (wstrzymane), M | Brak → „Zakres analizy nieznany”, każdy wniosek o braku wyświetlany jako „w zbadanym opisie”. Dotychczasowy string `coverage` → `coverage.label` |
| `priority` | `{acquisition:{rank,reason}, review:{rank:number\|null}, basis:"reach", affectsDecision:false}` | B (acquisition), D (`priority()` → review), H scala | J1 (kolejność), C | `null`; sortowanie wg wyniku i `publishedAt` |
| `variants` | `{rules_1_2\|qual_d\|qual_d_model:{route, reviewScore, decidedBy, variantUsed, fallback\|null}}` (zwarty wynik każdego policzonego wariantu) | H (`engine.analyze`) | G (porównanie na tych samych danych), M | Tylko aktywny wariant w `reviewDecision` |
| `requalification` + `needsRecalc` | `{state:"current"\|"pending", reasonCode, fromRules, toRules, fromVariant}`; `needsRecalc:boolean` (state==pending) | H (porównanie `analysisVersion` z `analysisCurrent`) | J1 („Do ponownego przeliczenia”), M | Brak pola i brak `reviewDecision` → `needsRecalc:true` |
| `score`, `summary`, `reviewSuggestion` (legacy) | jak dziś | H wypełnia z aktywnego wariantu: `score = reviewScore.value`, a przy `withheld` 0 + `scoreBasis:"withheld"`; `reviewSuggestion` pochodna `route` | J1 (stare widoki), kalibracja | Pola zostają; `summary` nie jest pokazywane jako powód |

**Sprawa (Case)**

| Pole | Typ | Producent | Konsument | Zachowanie przy braku |
|---|---|---|---|---|
| `version`, `revision`, `status` | jak dziś (status new/reviewing/closed) | H | J1, M | bez zmian |
| `versions[]` | `{version, observedAt, changeKind:"content"\|"evidence"\|"analysis", details:{rulesFrom,rulesTo,variantFrom,variantTo,routeFrom,routeTo,scoreFrom,scoreTo}}` | H | J1 (historia) | Wersje historyczne: `changeKind:"content"`, bez `details` |
| `history[].changeKind` | `"content"\|"evidence"\|"analysis"\|"provenance"\|"decision"\|"inquiry"\|"contract"` | H | J1 | Dotychczasowy opis „Zachowano wersję materiału” |
| `lastDecision` | `{status, at, note, version, revision, route, analysisSig}` | H | J1, M | Wyprowadzane z `history` (ostatni wpis `decision`); `version` i `route` = `null` dla decyzji sprzed v2 |
| `pendingReReview` | boolean: `status=closed` i bieżąca wersja > `lastDecision.version` i `changeKind ∈ {content, evidence}` | H | J1 („Nowa wersja po decyzji”), G | `false` bez `lastDecision.version` |
| `reviewStale` | boolean: istnieje decyzja analityka i późniejsze przeliczenie zmieniło `route` względem `lastDecision.route`; kasowane kolejną decyzją | H (+ wpis historii „zmiana kwalifikacji X → Y (reguły A → B)”) | J1, G | `false` |
| `queues[]` | podzbiór: `review`, `adRegister`, `offersM2`, `offersM3`, `incomplete`, `closed`, `all`, `demo` | H (czysta funkcja `queues_of(finding, threshold, variant)`) | J1 (filtruje), M | Zawsze obecne; UI nie klasyfikuje |
| `firstScanId`, `lastScanId` | string | H | J1 („z jakiego skanu”) | Pominięte w wierszu |
| `needsRecalcReason` | string, np. „Wynik z reguł 1.1; bieżące 1.3” | H | J1 | „starsza wersja analizy” |

**Creator i Source**

| Pole | Typ | Producent | Konsument | Zachowanie przy braku |
|---|---|---|---|---|
| `creator.discoveries[]` | jak `discovery[]` (legacy `creator.discovery` jako obiekt zostaje) | B, K, H | J1 (Źródła) | `discoveredVia` + „droga odkrycia sprzed rozszerzenia” |
| `creator.status`, `persistentId` | `"seed"\|"confirmed"\|"candidate"`, `string\|null` | B, K, H (alias `creator_aliases`) | J1, G | „ID niepotwierdzone” |
| `creator.reach` | jak `reach`, z `subscriberCount` i `hiddenSubscriberCount`→`state:"hidden"` | B | J1, G (ranking niszy) | „Zasięg nieznany” |
| `creator.firstSeenScanId`, `firstMode` | string | H | J1 | `isNew` (przejściowe, `store.py:116`) bez zmian |
| `source.target`, `kind`, `scope` | string; `"search"\|"feed"\|"profile"\|"crosslink"\|"asr"\|"page"`; `{query,window,pages,maxSeconds}` | B, K, H (`source_result`) | J1 | Dotychczasowy `name` i `scope` jako tekst |
| `source.lastError` | `{code, message, at, nextStep, retryAt?}` | adaptery | J1, M | `error` tekstem |
| `source.quota` | `{used, limit, resetAt}\|null` | H (`quota_ledger`) z budżetu B | J1 | Brak wiersza limitu |
| `source.status` | dotychczasowe + `limit`, `needs_key`, `unavailable` | adaptery | J1 | jak dziś |

**Stan, skan i kalibracja**

| Pole | Typ | Producent | Konsument | Zachowanie przy braku |
|---|---|---|---|---|
| `schema` | `{version, migratedAt}` | H | M | Stary serwer: brak |
| `analysisCurrent` | `{rules, model\|null, schema, variant}` | H | J1 | UI polega na `needsRecalc` z rekordu |
| `queues` | liczniki `{review, adRegister, offersM2, offersM3, incomplete, closed, all, demo}` | H | J1 (licznik zakładki, bez filtrów użytkownika) | Nie pokazuj „0” przed odpowiedzią |
| `threshold` | `{id, variant, value, setAt}` | H | J1, G | Domyślny wpis (60 dla wariantu reguł) |
| `qualification` | `{id, variant, setAt, validatedBy\|null}` | H | J1 (Kalibracja), G, M | Wariant `rules_1_2` |
| `scans[].sources`, `referred`, `progress` | `{ok,empty,partial,failed,total}`, number (nowe `refer` kwalifikujące się do kolejki z tego skanu), `{done,total}\|null` | H | J1 | „brak danych” / bez postępu |
| `calibration` (rozszerzone) | dotychczasowe + `variant`, `labelTarget`, `labelers[]`, `split`, `frozenAt`, `groups`, `precisionCI{low,high,method}`, `perModule`, `unresolved`, `withheld`, `notComputableReason` | G (metadane zbioru w fiksturze), H (przekazanie przez `engine.calibration`) | J1, G, Fable | Bez zbioru: „cel etykiet nieopisany”, wyniki wyszarzone |

### 3.4 Kolejki (wylicza API; UI tylko filtruje)

Wspólny filtr: `origin ∈ {live, replay}` (poza `all` i `demo`), `outOfScope = null` i `availability.state ≠ removed` (z wyjątkiem `all`). `route` i `queueEligible` pochodzą z aktywnego wariantu.

| Nazwa API | Warunek | Sortowanie |
|---|---|---|
| `review` | module=M1, `route=refer` (po bramce mowy, §3.11), `queueEligible`, `status≠closed`, ≥1 dowód `available:true`, `needsRecalc=false`; dodatkowo sprawy zamknięte z `pendingReReview` lub `reviewStale` (oznaczone) | `reviewScore.value` malejąco, potem `priority.review.rank`, potem `publishedAt` malejąco |
| `adRegister` | `adRegistry.state ∈ {included, candidate}`; `?section=confirmed\|candidate` | `publishedAt` malejąco |
| `offersM2`, `offersM3` | module=M2 / M3 | liczba obserwacji / trasa, potem wynik |
| `incomplete` | `needsRecalc` albo (`route ∈ {complete, insufficient}` i materiał z sygnałem lub trasa wstrzymana bramką mowy, §3.11). Samo `coverage.blocksConclusion` nie wystarcza; film bez sygnału to `no_signal` z pokryciem „mowy nie zbadano”, tylko w `all` | najpierw `needsRecalc`, potem `observedAt` |
| `closed` | `status=closed` (z oznaczeniem `pendingReReview`/`reviewStale`) | `lastDecision.at` |
| `all` | wszystko, także `no_signal`, `outOfScope`, `removed` | `observedAt` |
| `demo` | `origin ∈ {synthetic, upload}` | `observedAt` |

`queueEligible` = `route=refer` oraz `reviewScore.value >= aktywny próg` (próg według rekomendacji N2). Sama jawna współpraca, zasięg, wysokie podobieństwo i brak napisu w niepełnym materiale nie dają `refer`.

### 3.5 Wariant kwalifikacji, próg i bramka

Warianty (id w danych): `rules_1_2` (dzisiejsze reguły, domyślny), `qual_d` (kwalifikacja D), `qual_d_model` (D + lokalny model). `engine.analyze` liczy zawsze `rules_1_2` i `qual_d` (tanie, bez sieci) i zapisuje oba w `variants`. Model liczy się tylko, gdy aktywny jest `qual_d_model` albo gdy G uruchamia pomiar narzędziem poza workerem.

| Element | Zachowanie |
|---|---|
| Co wynika z wariantu | `reviewDecision`, `reviewScore`, legacy `score`/`reviewSuggestion`, `queueEligible`, reguła `high_risk`. Pola relacji, rejestru, pokrycia, dowodów, `priority` pochodzą zawsze z D (nie zmieniają kolejki) |
| Tryb cienia (stan po kroku S5) | Aktywny `rules_1_2`: kolejka `review` i zdarzenia `high_risk` zachowują się jak dziś. T21 chroni to testem (zrzut kolejki i zdarzeń na fiksturach przed i po) |
| Wybór wariantu | `PUT /v1/qualification {variant, expectedId, note, validationRef}`. Dla wariantu innego niż `rules_1_2` wymagany `validationRef` (identyfikator raportu G z TP/FP/TN/FN i odłożoną próbą) oraz `approvedBy` (Fable/J); bez nich 422. Dla `qual_d_model` serwer sprawdza dostępność modelu (digest z locka) i odrzuca bez niego |
| Historia | Tabela `qualification_settings` (id, variant, previous_id, restored_from, note, validation_ref, approved_by, at, rules_version, model_id, model_digest, prompt_version), tylko dopisywana. `GET /v1/qualification/history`, `POST /v1/qualification/restore {id, expectedId}` tworzy nowy wpis |
| Skutek zmiany | Zdarzenie `qualification`, automatyczny skan `recompute` (idempotentny: requestId `recompute-<hash wariantu, reguł, modelu>`). Sprawy dostają wersję `changeKind:"analysis"` tylko, gdy zmieni się `analysis_sig`. Status i decyzje nietknięte; `reviewStale=true` tylko tam, gdzie trasa zmieniła się po decyzji analityka |
| Próg | Tabela `thresholds` per wariant (kolumna `variant`), wpisy dopisywane, `restore` kopiuje do nowego wpisu. Zmiana progu nie przepisuje spraw i nie wystrzeliwuje zdarzeń historycznych |
| `high_risk` | `rules_1_2`: jak dziś (`score >= 70`, `store.py:175`). `qual_d*`: raz, przy przejściu sprawy na `refer` z `queueEligible=true` w aktywnym wariancie (nowa sprawa lub zmiana z innej trasy); nie przy powtórnym skanie, `recompute` bez zmiany trasy ani zmianie progu |
| Model lokalny | Wynik modelu w `model_cache` (klucz: sha256 treści, wersja promptu, id i digest modelu, parametry) — powtórzenie daje ten sam wynik bez wywołania. Zapis: dostawca (`ollama`), model, digest, parametry, wersja promptu, czas, tokeny. Worker nigdy nie czyta `OPENROUTER_API_KEY` ani nie importuje `analysis.openrouter_review` (T23) |
| Fallback | Model niedostępny, timeout, odpowiedź bez dowodu lub z cytatem spoza źródła → `variantUsed:"qual_d"` z `fallback:{from:"qual_d_model", reason}`, wynik identyczny jak dla czystych reguł. Brak kontekstu → `reviewScore.state:"withheld"` |
| Kalibracja | `GET /v1/calibration?threshold=&variant=` (domyślnie aktywny). Cache musi być kluczowany wariantem i digestem modelu (dziś tylko progiem, `server.py:79`). Wyniki z modelem liczy narzędzie G poza workerem i zapisuje jako artefakt (zbiór, wariant, digest, czas); API serwuje zapisany wynik |

### 3.6 Trasy

Istniejące bez zmian. Nowa zasada o id: żadnych nowych sufiksów po `{key:path}` poza `/versions` i `/reach`; wszystko inne przyjmuje id w ciele lub zapytaniu.

| Trasa | Opis |
|---|---|
| `GET /v1/state` | te same klucze + `schema`, `analysisCurrent`, `queues`, `threshold`, `qualification`; `?compact=1` pomija `history` i `evidence` |
| `GET /v1/queues/{name}` | filtry `limit, cursor, module, creator, since, until, minScore, q, section`; wynik `{items:[PodsumowanieSprawy], total, nextCursor, counts, threshold, asOf, lastScan}` |
| `GET /v1/cases/{id}`, `/versions`, `/versions/{n}`, `/reach` | rozszerzone o pola z §3.3; lista wersji z `changeKind` i `details` |
| `PATCH /v1/cases/{id}` | jak dziś + opcjonalne `reviewedVersion`; serwer zapisuje `version`, `route`, `analysisSig` w historii. 409 niesie `current:{revision,status,version}` |
| `POST /v1/evidence` | `{caseId, kind:"transcript", text\|segments, source:"analyst", note, expectedRevision}` — transkrypcja dostarczona przez analityka lub za zgodą (`origin` sprawy się nie zmienia; wersja `changeKind:"evidence"`, `coverage.transcript.source:"analyst"`) |
| `GET/PUT /v1/threshold`, `GET /v1/threshold/history`, `POST /v1/threshold/restore` | per wariant; 409 przy innym `expectedId` |
| `GET/PUT /v1/qualification`, `GET /v1/qualification/history`, `POST /v1/qualification/restore` | §3.5 |
| `POST /v1/scans` | `mode` rozszerzone o `recompute`; opcjonalne `adapters:[…]`; sourceId zostaje |
| `GET /v1/scans/{id}` | z krokami, postępem i budżetem |
| `GET /v1/calibration` | `?variant=` |
| `WS /v1/events` | bez zmian + `threshold`, `qualification`, `reset` (gdy `after` > maksimum) |

### 3.7 Migracja

**Zasada: tabel v1 nie zmieniamy (żadnego `ALTER TABLE` na `cases`, `versions`, `creators`, `sources`).** Powód: kod z 491094d zapisuje do nich pozycyjnie, bez listy kolumn: `INSERT INTO cases VALUES(?,?,?,'new',1,?)` (`store.py:171`), `INSERT INTO versions VALUES(?,?,?,?,?,?)` (`store.py:169`), `INSERT INTO creators VALUES(?,?)`, `INSERT INTO sources VALUES(?,?)`. Dodatkowa kolumna zepsułaby każdy z tych zapisów i uniemożliwiła wycofanie kodu („table cases has 8 columns but 6 values were supplied”). Wcześniejsza wersja tego dokumentu obiecywała `ALTER TABLE cases ADD COLUMN …`; to było błędne i zostało zastąpione modelem tabel bocznych.

- `PRAGMA user_version` i tabela `schema_meta` (jeden wiersz na krok). Numer wersji schematu to numer ostatniego kroku (po S2: 3); `schema.version` w `/v1/state` podaje ten numer. Migracje to lista kroków idempotentnych, wykonywana w `BEGIN IMMEDIATE`; równoległy start czeka na blokadę, a `init()` ponawia próbę przy „database is locked” (`PRAGMA journal_mode=WAL` i pierwszy `CREATE TABLE` ignorują timeout, co powodowało także błąd w kodzie 491094d).
- Krok 2 (S1): `schema_meta`. Krok 3 (S2): `version_meta(id, version, reason, content_sig, evidence_sig, analysis_sig, details)`, `discoveries(case_id, key, first_seen, last_seen, seen_count, body)`, `reach_samples(case_id, observed, source, body)`.
- Kroki późniejsze: `case_meta(case_id, availability, first_scan, last_scan, decided_version, analysis_schema)` (S6), `creator_samples`, `creator_aliases`, `thresholds(variant, …)`, `qualification_settings`, `model_cache`. Krok 4 (S3): `scan_steps`, `source_state`, `quota_ledger`. Każda tabela jest tworzona w kroku, który jej używa.
- Odczyt starych rekordów bez backfillu (`compat_view`): `origin`, `analysisVersion` (schemat 1, `derived:"legacy"`), `needsRecalc=true`, `requalification:{state:"pending", reasonCode:"schema_1"}`. Starym rekordom nie dopisujemy ocen v2 (`reviewDecision`, `discovery`, `reach` pozostają nieobecne); `reviewDecision` z mapowania `reviewSuggestion` pojawi się dopiero w S5, już z wymaganymi `reasons[]` i `moments[]`. Rodzaj dawnych wersji (`changeKind`) jest wyliczany z zapisanych `capture` i `finding`.
- Odcisk wersji: nowy zapis używa odcisku po normalizacji (czas UTC, kanoniczny link YouTube, tekst NFC i LF). Sprawa zapisana wcześniej rozpoznaje niezmienione ujęcie także po odcisku liczonym starym wzorem (`legacy`), więc wdrożenie nie tworzy fali wersji (test `test_s2_recognises_what_v1_stored_for_real_fixtures`). Zmiana formatu między źródłami (np. `Z` zamiast `+00:00`) jest już zerem zmian.
- Domyślne wpisy: `thresholds` (reguły: 60), `qualification_settings` (`rules_1_2`). Rollback kodu na 491094d nie wymaga zmian bazy: nowe tabele są ignorowane, a tabele v1 mają dotychczasowy kształt (test `test_t11_rollback_to_v1_code_keeps_working`).

### 3.8 Adaptery, tryby skanu, miejsce wywołania `qualify`

Interfejs adaptera (B, K, F), rejestr w `collectors/discovery.py` i scalanie `merge_captures` jak w projekcie z 18:35 (`discover(ctx)`, `ctx.state`, `ctx.budget`, `ctx.heartbeat()`, wynik `{creators, captures, sources, status, resume}`). Uzgodnienia z B: id kanoniczne bez wyjątków; budżet `INVESTWATCH_YT_DAILY_UNITS` zapisywany w `quota_ledger` (reset o północy czasu pacyficznego); `quotaExceeded` → status źródła `limit`, `retryAt`, kursor (zapytanie, `pageToken`) w `source_state`; Atom działa dalej; brak klucza → status `needs_key` bez wyjątku; klucz wyłącznie w środowisku workera, URL-e z `key=REDACTED`; `ranking_import` i `fixture` oznaczone `import:true`/`method`. Remis w rankingu i Shorts to koszyk rankingu B, nie reguła H.

Przepływ skanu po zmianie (oba tryby): `discover` (adaptery) → `merge_captures` → `enrich` (C, własny cache i budżet, pomijany w replay, jeśli fikstura niesie `segments`) → w `jobs.evaluate`: `suggest(cap)` (E5, tylko dla M2/M3 i `qual_d_model`) → `analyze(cap, semantic=…, variant=aktywny)` — **jedyne miejsce wywołania `qualify`** (koniec gałęzi M1 w `engine.analyze`, `engine.py:347-357`), a potem `priority(reach, relation)` osobno → `apply_scan` (zapis po kroku). `calibration()` woła to samo `analyze`. Replay czyta fiksturę o tym samym kształcie i nadal nie nadpisuje live. Wyjątek w `qualify` nie przerywa skanu: `route:"insufficient"` z `notComputableReason`.

### 3.9 Cień kwalifikacji D (S5) i krok mediów (S8): stan wdrożenia

- **Jedno miejsce wywołania.** `analysis.engine.analyze(capture, *, semantic=None, variant=None)` woła `qualification.qualify` na końcu gałęzi M1 (wyjątek daje `route:"insufficient"` z `notComputableReason`, skan trwa). `jobs.evaluate` bez zmian (test `test_job_review` podmienia `analyze` jednym argumentem); `qualify` nie używa `semantic`, więc kolejność z R5 nie zmienia wyniku. `priority(reach, relation)` woła `analyze` po `qualify`.
- **Tabela boczna `qualification_results(case_id, version, body)`** (migracja 5): przy zapisie `apply_scan` zdejmuje z findingu pola v2 (`reviewDecision`, `reviewScore`, `adRelationship`, `relationships`, `adRegistry`, `premises`, `counterEvidence`, `coverage`, `variants`, `analysisVersion`, `priority` i dowody z `role`). `cases.body`, `versions` i sygnatura zostają w kształcie v1 (T21 bez zmiany zrzutu, brak fali wersji). Odczyt (`case_dict`) dokłada pola v2 dla bieżącej wersji; przy ponownym odczycie tej samej sygnatury wiersz jest odświeżany.
- **Nazwy w cieniu.** Dowody D (z `id`) i obiekt `coverage` kolidują ze starymi polami (`evidence` bez `id`, `coverage` jako tekst z ASR, czytany w `web/src/proof.jsx`), więc API podaje je jako `evidenceV2` i `coverageV2`. Zamiana na `evidence` i `coverage` następuje przy aktywacji wariantu (S7). `analyze()` zwraca dowody v1 i v2 w jednej liście `evidence` (v2 mają `role`).
- **Warianty.** `variants.rules_1_2` mapuje `reviewSuggestion` (review→refer, uncertain→complete, no_signal→no_signal, unavailable→insufficient), `variants.qual_d` niesie trasę D. Aktywny wariant to nadal `rules_1_2` (`analysisVersion.variant`), `analysisVersion.shadowVariant="qual_d"`. `queueEligible` w `reviewDecision` = `refer` i wynik ≥ 60 (N2). Wiersze kalibracji dostają `route` (reguły 1.2 przy progu) i `variants`.
- **Rozszerzenia D przyjęte do kontraktu** (obecne w `analysis/qualification.py`): `relationships[]` (kolejne relacje poza główną z `status`, `basis`, `firm`, `adRegistry`), `firm.inScope` i `firm.outOfScopeReason`, `evidence[].locator` (`field`, `charStart`, `charEnd`, `occurrences`), `evidence[].match` (`verbatim`/`approximate`) i `observation`, `evidence[].caveat` (auto-napisy), `moments[].locator`, `reviewDecision.completeReason` (kod pojedynczy; D nie zwraca listy `completeReasons`: do ustalenia z D, jeśli lista ma być w kontrakcie), `adRelationship.status="probable"` dla samego linku lub kodu (rejestr `candidate`, a U1 `documented` daje `refer`).
- **Krok `enrich` (S8)** w `api/enrich.py`, wołany z `jobs.build` przed analizą: dla M1 z `youtube:*` bez segmentów woła `collectors.media.enrich` (opis i napisy zawsze; cache `INVESTWATCH_MEDIA_CACHE`, domyślnie `STATE/media-cache`; limit `INVESTWATCH_MEDIA_PER_SCAN` filmów z siecią na skan, domyślnie 25; `INVESTWATCH_MEDIA_SECONDS` na film, domyślnie 120). Kadry (`INVESTWATCH_MEDIA_FRAMES`, domyślnie 3) tylko live i tylko dla podejrzanego (U1 `documented`/`conditional`/`candidate` lub `refer`) w momentach z `reviewDecision.moments[].start` i z `find_markers` (znacznik promocji przy nazwie brokera), odstęp ≥ 5 s. Replay czyta wyłącznie cache przez klienta bez sieci, a brak transkrypcji to luka `mediaCoverage`. Błąd mediów to luka, nie błąd skanu. Transkrypcja zmienia `segments`, więc powstaje wersja `changeKind:"evidence"`.
- **Nie wdrożone:** `POST /v1/evidence` (T29) czeka na S7, bo wymaga `coverage` jako obiektu w odpowiedzi sprawy (dziś `coverageV2`). `shadow_report`: `python -m api.shadow_report --state <katalog> [--json] [--case ID]`, tylko do odczytu.

### 3.10 S4, S6, S7: stan wdrożenia (domyślny wariant nadal `rules_1_2`)

- **S4.** `youtube` działa w każdym skanie live (`INVESTWATCH_ADAPTERS`, gdy ustawione, wylicza adaptery opcjonalne). Domyślny budżet 1200 jednostek na przebieg i 8000 na dobę (`INVESTWATCH_YT_RUN_UNITS`, `INVESTWATCH_YT_DAILY_UNITS`), `raw_dir` i `cache_dir` pod `STATE/youtube-raw` i `STATE/youtube-cache`. Adapter z własnym transportem nie działa, gdy wywołujący podał własny `fetch` (testy). Źródło na limicie lub bez klucza kończy skan jako `partial` z powodem w `warnings`. `youtube-replay` (fikstura B) jest adapterem tylko na żądanie (`payload.adapters`), żeby `discover("replay")` i zrzut T21 się nie zmieniły; worker zleca go jako `bootstrap-youtube-replay-v1`. Kolejność mediów: najpierw dowód relacji w opisie, potem zasięg; limit domyślnie 25 na skan.
- **S6.** `queues[]`, `route`, `queueEligible`, `lastDecision`, `pendingReReview`, `reviewStale` w rekordzie; `GET /v1/queues/{name}` (filtry `module`, `creator`, `platform`, `since`, `until`, `minScore`, `q`, `section`, `limit`, `cursor`), liczniki, `threshold`, `qualification` i `schema.views` w `/v1/state`; `?compact=1`. Decyzja zapisuje `version`, `route`, `analysisSig`; `reviewedVersion` i stara rewizja dają 409 z `current`. Kolejka liczy trasę i próg aktywnego wariantu.
- **S7.** `GET/PUT /v1/qualification` (+ `history`, `restore`; wariant inny niż `rules_1_2` wymaga `validationRef` i `approvedBy`, `qual_d_model` jest odrzucany, bo model nie ma miejsca uruchomienia), `GET/PUT /v1/threshold` (+ `history`, `restore`; wpisy per wariant, `expectedId` → 409), skan `recompute` (po każdej zmianie wariantu; analizuje zapisane materiały M1 od nowa, nie rusza statusu ani decyzji, nie odtwarza obserwacji), `high_risk` dla `qual_d*` raz przy przejściu na kwalifikujące się `refer`, `POST /v1/evidence`, `WS reset`. Pola legacy `score` i `reviewSuggestion` nadal pochodzą z reguł 1.2 także po przełączeniu.
- **Zgodność ze starym pulpitem:** parametr `?schema=` (domyślnie 1). Widok 1 zostawia `evidence` i `coverage` w starym kształcie i dodaje `evidenceV2`, `coverageV2`; widok 2 podaje `evidence` (z `role`) i `coverage` jako obiekt, a dawny tekst `coverage` trafia do `coverage.legacyText`. `store.case_dict` i `store.state` domyślnie zwracają widok 2.

### 3.11 Bramka mowy i zaległość mediów (decyzja J, 21 XI wieczór)

Decyzja: film trafia do „Co wymaga sprawdzenia” (`review`) dopiero po tym, jak system zbadał opis i mowę (a przy podejrzeniu także kadry) i nie znalazł oznaczenia współpracy, albo gdy transkrypcji nie da się uzyskać. Dotyczy wyłącznie filmów YouTube M1 (`engine.is_video`); podcasty, strony i inne materiały zachowują dotychczasowe trasy.

- **Faza transkrypcji** (`engine.transcript_phase`): `full`, `partial`, `pending` (jeszcze niepobrana; brak `mediaCoverage`, błąd przejściowy: `rate_limited`, `login_required`, `timeout`, `error`, limit skanu, brak cache w replay) albo `unavailable` (trwale: brak napisów po polsku, `private`, `unavailable`, `age_restricted`, `members_only`, a także trzecia nieudana próba). `qualify` dostaje `mediaCoverage.transcript.state="pending"`, więc `coverage` mówi „mowa: niezbadana (w kolejce)”.
- **Bramka** (`engine._gate`, po `qualify`): `refer` przy fazie `pending` lub `partial` staje się `complete` z `completeReason="transcript_pending"` (`other_gap` przy fazie częściowej), `reason` „Podejrzenie z opisu; mowy jeszcze nie zbadano”, `queueEligible=false`, `gatedFrom="refer"`; uzasadnienie i momenty zostają do wglądu. `refer` przy fazie `full` ma `speechBasis="examined"`; przy `unavailable` zostaje `refer` z `speechBasis="unavailable"` i jawnym zdaniem w `reasons[]` („Transkrypcji nie da się uzyskać (powód); oceniono wyłącznie opis, mowy nie zbadano.”). To samo wstrzymanie dotyczy wariantu `rules_1_2` (`variants.rules_1_2.gated`), bo kolejka czyta trasę aktywnego wariantu.
- **`high_risk`**: wstrzymane `refer` nie wyzwala zdarzenia (`rules_1_2`: `score>=70` i brak `gated`; `qual_d*`: trasa przestaje być `refer`). Zdarzenie odpala przy zwolnieniu bramki: nowa wersja `evidence` z transkrypcją albo przejście z `pending` na `unavailable` bez nowej wersji (jednorazowo).
- **`incomplete`**: materiał z sygnałem (dowód relacji, firma z rejestru w opisie lub tytule, `identity_unresolved`, awaria kwalifikacji) i konkretną luką, albo trasa wstrzymana bramką, albo `needsRecalc`. Film bez sygnału w opisie to `no_signal` z pokryciem „mowy nie zbadano”, poza `incomplete`, widoczny w `all`.
- **Kadry**: tylko dla filmu, który po zbadaniu mowy (albo przy niedostępnej transkrypcji) nadal jest `refer`, 2–3 kadry: wezwanie „link w opisie”, wzmianka firmy, momenty z `moments[]`; bez momentu w mowie początek, środek i koniec. Brak OCR: kadr jest dowodem `kind="frame"`, `role="context"`, `modality="frame"` z czasem i `sourceUrlAtTime`, dopisanym też do `moments[]`; `coverage.modalities.frames.reason` = „kadry pobrane, tekst z obrazu nieodczytany automatycznie”.
- **Zaległość mediów**: tabela boczna `media_state(case_id, state, body, updated)` (migracja 7; `state` ∈ `done`, `unavailable`, `failed`; `body` niesie `segments`, `mediaCoverage`, `frames`, `mediaVersion`, `framesAttempted`, `attempts`). Zapisuje ją `apply_scan` przy każdym skanie z wynikiem mediów, a `merge_known` dokłada ją do ponownie odczytanego filmu (powtórny skan nie traci transkrypcji i nie tworzy wersji). Cel transkrypcji: wszystkie filmy z dowodem relacji lub wzmianką firmy z rejestru w opisie lub tytule (najpierw dowód relacji, potem zasięg i `priority.acquisition`); film bez sygnału nie jest celem. Budżet kroku: `INVESTWATCH_MEDIA_PER_SCAN` (filmy z siecią; 25 w skanie, 150 w `enrich`) i `INVESTWATCH_MEDIA_SCAN_SECONDS` (czas kroku; 600 s w skanie, 1800 s w `enrich`), `INVESTWATCH_MEDIA_SECONDS` na film (120 s). Niedokończone czekają w zaległości do kolejnego skanu. Blokada YouTube (`rate_limited`, `login_required`) zatrzymuje krok i zostawia resztę jako `pending` (`summary.blocked`).
- **Skan `mode=enrich`** (`POST /v1/scans {mode:"enrich"}` lub `store.create_scan("enrich", id)`): bierze zapisane filmy M1, nie woła adapterów odkrywania i nie rusza księgi kwoty YouTube Data API; kroki `enrich`, `analyze`, `apply`; zapisuje tylko zmienione sprawy (wersja `evidence` przy nowej transkrypcji). Wyniki idą przez `apply_recompute`, więc status i decyzje analityka nie są ruszane.

### 3.12 Replay pionu i prośby pulpitu (21 XI, wieczór)

- **Paczka mediów replay** (`api/replay_pack.py`, poza Gitem): `python -m api.replay_pack build --from .runtime/media-cache --ids ID1,ID2,... [--out .runtime/replay-media/2026-11-21] [--manifest-out fixtures/raw/media/2026-11-21/replay-pack.manifest.json]`, `verify [--pack DIR] [--manifest FILE]`. Układ jak cache mediów (`<id>/meta.json`, `transcript.json`, `frames/*.jpg` bez arkuszy `sheet_*`) plus `MANIFEST.json` z SHA-256 każdego pliku; w repozytorium tylko narzędzie i kopia manifestu. Ścieżka: `INVESTWATCH_REPLAY_MEDIA` albo `.runtime/replay-media/2026-11-21`. `enrich` w trybie replay czyta paczkę przez klienta bez sieci (transkrypcje i kadry w momentach z kwalifikacji), a brak lub uszkodzenie paczki (`state` ∈ `present`/`missing`/`corrupt`) to źródło `replay-media` ze statusem `empty` i opisem luki (skan zostaje `done`), film bez transkrypcji ma `pending` z powodem „brak paczki mediów” lub „film poza paczką”.
- **Zdarzenie replay.** `youtube-replay` dokłada `fixtures/raw/discovery/youtube-api-2026-11-21/replay-media-extra.json`: 5 filmów paczki, których nie zwróciło datowane wyszukiwanie (CDk20n4u9Kk, YQH4FEP9exI, xtMqKkFO-0M z zapisanego captura próby live, -HpCSKp9bqk i 9Fcwo1jlwe4 z `meta.json`, data publikacji z dokładnością do dnia) plus jeden twórca. Pochodzenie: `provenance.fixture="replay-media-extra.json"`, `provenance.extraOrigin`, `discovery[].method="fixture"`, `import:true`.
- **Pulpit (schema 2; `?schema=2` albo nagłówek `X-InvestWatch-Schema: 2`, domyślnie 1, stary pulpit `web/legacy.html` bez zmian):** `GET /v1/frames/{videoId}/{name}` (tylko odczyt, tylko JPEG wymieniony w sprawie, z sumą SHA-256 zgodną z zapisem, z folderów paczki lub cache stanu; reszta 404) i `evidence[].thumbnailUrl`; `PATCH` z `resolution` ∈ `refer_to_control`/`complete_data` (status `reviewing`), `no_signal`/`close` (status `closed`), bez `status` wynika z rodzaju, wpis historii i `lastDecision.resolution`; `scans[].sources {ok,empty,partial,failed,total}`, `referred` (nowe `refer` kwalifikujące się do kolejki aktywnego wariantu, tylko live/replay), `progress {done,total}`; `GET /v1/scans/{id}` kroki `{id,name,status,...}`; `sources[]` z `lastError`, `quota`, `target`, `kind`, `retryAt`; `sourceHealth` zostaje mapą tekstów (T18), a `sourceHealthDetail` niesie obiekty `{status,sourceStatus,lastError,quota,...}` i `sourceHealthSummary {status,total,problems}`; `creators[].discoveries[]` (dla starych rekordów wyprowadzone z `discovery`, `derived:"legacy"`) i `reach`; `GET /v1/trend?days=` oraz `trend` w stanie: `byScan` i `byDay` (`scans`, `captures`, `referred`, `newMaterials`). Podsumowanie kolejki podaje wynik i powód aktywnego wariantu.

### 3.13 Domyślny wariant qual_d, tożsamość firm zagranicznych, kalibracja q-v2 (21 XI, noc)

- **Domyślny wariant.** Nowa, pusta baza startuje z `qual_d` jako wpisem historii nr 1 (`validationRef` `fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md@463cceb`, `validatedBy` Fable, próg 60, nota „oceny agentów, nie walidacja ekspercka”). Istniejąca baza (z `cases`) nie zmienia wariantu samoczynnie. Powrót: `PUT /v1/qualification {variant:"rules_1_2"}` albo `restore`. Testy dziedziczą z `StateCase` bazę przypiętą do `rules_1_2` (`BASELINE`), T21 sprawdza to jawnie; `DefaultVariant` testuje nowy domyślny stan.
- **Przeliczenie bez workera.** `recompute_for` wykonuje skan w żądaniu, gdy baza ma co najwyżej `INVESTWATCH_INLINE_RECOMPUTE_MAX` spraw (60; 1307 spraw trwa ok. 15 s, więc większa zostaje w kolejce). `/v1/state.recompute` podaje `state` (`none`, `queued`, `waiting_for_worker` po 10 s w kolejce, `running`, `done`, `failed`), `scanId`, `ageSec` i zdanie dla człowieka.
- **Tożsamość firm.** `firm-index.json` niesie `entityType` (`domestic_investment_firm`, `domestic_bank`, `foreign_investment_firm`; `foreign_credit_institution` jest w modelu, ale żaden wiersz kopii nie jest tak typowany, bo kopie go nie wyróżniają), `homeCountry`, `passporting` (`branch` z wykazu oddziałów, `cross_border` z notyfikacji) i listę przejrzanych wykazów z datą kopii. `firm` w `adRelationship` ma `entityType`, `entityTypes`, `homeCountry`, `passporting`, `entitySentence`, `registersChecked`; przy różnych kandydatach `unresolved`. Saxo Bank nie występuje w żadnej z czterech kopii, więc zostaje „nie ustalono w przejrzanych wykazach”. Jawnie oznaczona współpraca z firmą spoza kopii nie tworzy już przesłanki U3 (trasa `complete`/`identity_unresolved`); trafia do rejestru reklam z `adRegistry.identityStatus` i `identityNote`. U3 zostaje dla relacji nieoznaczonej (link, kod, wynagrodzenie).
- **Teksty.** Cytat przycinany do końca zdania albo słowa, bez wiszącej jednej lub dwóch liter; zdanie o możliwym niewinnym wyjaśnieniu wymienia tylko niezbadany zakres (`_explanations`).
- **Kalibracja.** `GET /v1/calibration` domyślnie `dataset=q-v2` (M1, `fixtures/validation/q-v2`, bez kopiowania danych; liczy `tools/eval_validation.py` dla dowolnego progu): `variants.{rules_1_2,qual_d}` z TP/FP/TN/FN, kosztem 2×FN+FP, kampaniami i błędami, `labelTarget`, `labelers`, `disclaimer`, `frozenAt`, `queueEffect` (ile spraw prawdziwej kolejki `review` zmieni się przy podanym progu). Bez `threshold` obowiązuje próg zapisany dla wariantu (`/v1/threshold`), czyli ten, który filtruje kolejkę. `dataset=illustrative` zwraca stary zbiór. `/v1/state.calibration` to to samo porównanie.
- **Inne.** `creatorName` w wierszach kolejek uzupełniany z tabeli twórców. `/v1/state.semantic` mówi, dlaczego model E5 jest niedostępny (brak `INVESTWATCH_SEMANTIC_DIR`, wag albo pakietów) i że M3 działa wtedy tylko regułami.

### 3.14 Źródła social, access_blocked, kwota per klucz, raport modułów, lekki stan (21 XI, noc)

- **Adaptery K.** Zarejestrowane: `tiktok` (drugi etap, po `youtube`, czyta `ctx.captures`), `facebook`, `instagram` (wpisy organiczne, status `access_blocked`), `meta_ads` (Biblioteka Reklam Meta, własny transport, budżet `INVESTWATCH_META_RUN_REQUESTS`/`INVESTWATCH_META_DAILY_REQUESTS`, 30 i 300) i `social-replay` (tylko replay, tylko na żądanie). Każdy da się wyłączyć listą `INVESTWATCH_ADAPTERS`. Worker zleca `bootstrap-social-replay-v1` (`payload.adapters=["social-replay"]`) obok `bootstrap-youtube-replay-v1`.
- **`access_blocked`** to osobny stan zdrowia źródła (obok `ok`, `error`, `needs_key`, `quota_exhausted`): znany, udokumentowany stan, a nie awaria. Skan z takim źródłem nie jest `partial`; `scans[].sources` ma `accessBlocked` (tylko gdy >0), a wynik skanu `accessBlocked:[{id,name,code,message,nextStep,attemptedAt}]`. `sourceHealthDetail[id]` niesie `lastError {code,message,at,nextStep}`, `lastAttemptAt`, `probe`, `accessPath`; `sourceHealthSummary` ma `accessBlocked` (liczba) i `accessBlockedSources`, a `problems` i `status` ich nie liczą. `meta_ads`, `facebook-ads`, `instagram-ads` bez tokenu (`needs_key`) są widoczne z `nextStep`, ale nie czynią skanu `partial` ani zdrowia `degraded` (`store.TOKEN_OPTIONAL`).
- **Kwalifikacja podpisów.** Podpis TikToka jest opisem; mowa `unavailable` trafia do `coverage`. Jawny znacznik „[współpraca z XTB]” jest oznaczeniem reklamy: `engine._caption_vocabulary` dopisuje ten wzorzec do `NAMED_DECLARATION` modułu D i nie pozwala pominąć zdania zaczynającego się od znacznika, gdy kończy się znakiem zapytania. Cytat zostaje dosłowny. To obejście w zakresie H; docelowo wzorzec powinien trafić do `analysis/qualification.py` (lane D), wtedy funkcja nic nie zmienia. Wynik na replayu K: 5 postów @kacper_snela w `adRegister`, 0 w `review`. Posty „[współpraca z OKX]” nie trafiają do rejestru, bo OKX nie ma wpisu w kopiach wykazów.
- **M2 z reklam Meta.** Reklama firmy z rejestru (`module=M2`, id `facebook:ad-…`) przechodzi przez analizę tekstową M2; `coverage.label` mówi „Zbadano: tylko tekst reklamy, bez renderu”. Reklama twórcy (M1) idzie przez `qualify`. Zasięg to `euTotalReach`, nie `viewCount`.
- **Baza kanałów YouTube.** Adapter dostaje `state_dir` = `STATE/youtube-state` (plik `channels.json`, odporny na restart); `cursor` (ok. 140 kB) nie jest już zapisywany w `source_state` ani w wyjściu kroku i nie jest oddawany w `/v1/state.sourceState` (stare bazy nadal go mają i adapter z niego odtwarza bazę). Opcje z środowiska: `INVESTWATCH_YT_MONITOR_SHARE`, `_MONITOR_CHANNELS`, `_MONITOR_MIN_HOURS`, `_KEY_DAILY_UNITS`. `known_creators` to wyłącznie `youtube:UC…`.
- **Kwota per klucz.** Migracja 8: tabela `quota_keys(source_id, day, key_id, used, units_limit, exhausted_at, updated)`, dodana bez zmian w tabelach v1. Wiersz na klucz z `result.quota.keys` (`keyId` musi mieć dokładnie 8 znaków szesnastkowych, inne są odrzucane, wartość klucza nigdy nie trafia do bazy ani do odpowiedzi). Limit klucza to `min(limit zgłoszony, INVESTWATCH_YT_DAILY_UNITS)`, limit źródła to suma limitów kluczy, a zużycie w przebiegu dodaje `usedThisRun`. `quotaExceeded` jednego klucza oznacza jego dobę jako wyczerpaną, a drugi działa. Nowy dzień zaczyna od liczby kluczy z dnia poprzedniego. `source.quota.keys[]` i `sourceHealthDetail[].quota.keys[]`: `{keyId, used, limit, exhaustedAt}`.
- **Filtry.** `GET /v1/queues/{name}` filtruje po `platform` (tiktok, facebook, instagram, youtube, web, …), `module`, `since`/`until` z `dateField=observedAt|publishedAt` (TikTok bez daty platformy używa `publishedAtDerived`), `minScore`, `band` (`strong` od max(80, próg), `moderate` od progu, `weak` poniżej), `route`, `q` (tytuł, nazwa kanału, autor, id twórcy). Podsumowanie sprawy dostało `band`, `completeReason`, `firstReason` (pierwszy punkt `reasons[]`), `adRegistryInfo {state, summary, identityStatus}`, `disclosure {kind, state, where, atSec, text}`, `transcriptState`; `creatorName` wraca do `author`, gdy twórcy nie ma w tabeli. `counts` ma `transcriptPending` (materiał live/replay z mową do pobrania).
- **Raport.** `GET /v1/report?module=M1|M2|M3&format=json|csv` (+ `queue`, `platform`, `since`, `until`, `dateField`, `minScore`, `band`, `route`, `q`, `limit` ≤ 5000, `cursor`). Domyślny zakres: M1 kolejki `review` i `adRegister`, M2 `offersM2`, M3 `offersM3`; `queue=all` bierze wszystko z modułu. Kolumny M1: firma, typPodmiotu, podmiotReklamujacy, tresc, url, platforma, dataPublikacji, podstawaDatyPublikacji, dataOdczytu, trasa, silaSygnalu, relacjaReklamowa, rejestrReklam, statusDecyzji, id (M2: operator, M3: autor zamiast podmiotu reklamującego i bez relacji i rejestru). CSV: UTF-8 z BOM, CRLF, komórki zaczynające się od `= + - @`, tabulatora lub CR dostają apostrof, znaki sterujące stają się spacją; stronicowanie nagłówkami `X-Total-Count` i `X-Next-Cursor`.
- **Lekki stan.** `GET /v1/overview` (to samo co `GET /v1/state?findings=0`): bez spraw (`findings:[]`, `findingsOmitted:true`), twórcy w skrócie plus `creatorCounts {total, byPlatform}`, liczniki kolejek z pamięci podręcznej (klucz: liczność i ostatnia zmiana spraw, kwalifikacji i mediów, ustawienia, wersja analizy), źródła, skany, `sourceHealth*`, trend, próg, kwalifikacja, `recompute`. Na kopii bazy z 1313 sprawami: ok. 0,6 s przy pierwszym odczycie, 0,03 s z pamięci, 295 kB (stan `compact=1` to 12 MB).
- **Inne.** `history[].details` jest zawsze obiektem w widoku 2 (widok 1 zostaje tekstem, T18). Kalibracja ilustracyjna jest buforowana po skrócie plików `fixtures/labeled`, a narzędzie `tools/eval_validation.py` jest ładowane po skrócie pliku. Zawieszone przeliczenie: `recompute` w `queued` albo `running` z wygasłą dzierżawą daje `waiting_for_worker` z `waitingSince`, `stalled` i zdaniem z datą; `GET /v1/state` kończy je w żądaniu, gdy baza ma najwyżej `INVESTWATCH_INLINE_RECOMPUTE_MAX` spraw, a większą zostawia czekającą z datą.

## 4. Plan testów kontraktowych (tests/core/, wspólnie z M przed implementacją)

T1–T18 bez zmian względem projektu (powtórzenie skanu, duplikat Atom/API, zmiana statystyk, edycja opisu, fałszywe wersje, równoległa decyzja, decyzja a nowa wersja, restart, reconnect, id z ukośnikami, stary rekord, migracja równoległa, recompute, kolejki, próg, adapter, tryby, zgodność odpowiedzi). T14 i T15 rozszerzone o wyliczanie `queueEligible`, per-wariantowy próg i `queues[]` jak w §3.4. Nowe:

| # | Test | Oczekiwane zachowanie |
|---|---|---|
| T19 | pochodzenie | `derive_origin`: synthetic → synthetic nawet w replay; contractDemo → synthetic; upload → upload; reszta = `mode`. Stary rekord bez `origin` dostaje wartość przy odczycie |
| T20 | jedno miejsce wywołania | dla jednego capture M1 `analyze()` zwraca pola v2, a `calibration()` i `jobs.build` dają ten sam `route` i `reviewScore` (porównanie z zapisanym rekordem) |
| T21 | cień nie zmienia kolejki | po wdrożeniu pól v2 przy aktywnym `rules_1_2` zrzut kolejki `review` i lista zdarzeń `high_risk` na fiksturach są identyczne jak na HEAD 491094d |
| T22 | przełącznik wariantu | `PUT` bez `validationRef`/`approvedBy` → 422; dla `qual_d_model` bez modelu → 422; z poprawnymi → wpis w historii, skan `recompute`, wersje `changeKind:"analysis"`, status i decyzje zachowane, `reviewStale` tylko po zmianie trasy po decyzji; `restore` tworzy nowy wpis |
| T23 | odtwarzalny fallback | model niedostępny → `variantUsed:"qual_d"` z `fallback`, wynik identyczny jak `qual_d`; drugi przebieg z `model_cache` bez wywołania modelu; z ustawionym `OPENROUTER_API_KEY` worker go nie czyta i nie importuje adaptera OpenRouter |
| T24 | `high_risk` po przejściu | `qual_d`: jedno zdarzenie przy przejściu na kwalifikujące się `refer`; zero przy powtórnym skanie, `recompute` bez zmiany trasy i zmianie progu. `rules_1_2`: stara reguła bez zmian |
| T25 | zakres transkrypcji | `refer` przy opisie i pełnej transkrypcji bez kadrów (J2); `no_signal` niedozwolone bez pełnej transkrypcji → `complete/transcript_unavailable` lub `transcript_pending`; kadr powstaje tylko dla momentu z `moments[]` mającego `start` (J3, J8); `coverage.frames.state` rozróżnia `selected_moments` i `full` |
| T26 | niezależność od zasięgu | ten sam capture z różnym `reach` → identyczne `reviewDecision`, `reviewScore`, `queues[]`, różne `priority` |
| T27 | dwie flagi | zmiana treści po decyzji → `pendingReReview`, nie `reviewStale`; zmiana trasy po decyzji bez nowej treści → `reviewStale`, nie `pendingReReview`; kolejna decyzja kasuje obie |
| T28 | rejestr reklam | `declared`/`documented` → `included`; sama zachęta, link, kod lub etykieta bez firmy → `candidate`; neutralna wzmianka → `none`; firma jako lista kandydatów (XTB: 6884980 i 9439233) |
| T29 | transkrypcja analityka | `POST /v1/evidence` → wersja `changeKind:"evidence"`, `origin` bez zmian, `coverage.transcript.source:"analyst"`, 409 przy starej rewizji |
| T31 | nieoznaczona współpraca (J5) | link śledzący + kod twórcy w opisie bez oznaczenia, `identityStatus` nierozstrzygnięty → `refer` z U1 `documented`, `adRegistry=candidate`; przy niedostępnej transkrypcji nadal `refer`, ale `reasons[]` wskazuje niezbadaną mowę; oznaczenie dodane w segmencie mowy lub kadrze → U1 `refuted`, `no_signal`, `adRegistry=included` |
| T32 | opinia bez relacji (J6) | „Zarobiłem 30% na akcjach w XTB” bez relacji → `no_signal`, tylko `all`, nigdy `review` |
| T33 | uzasadnienie skierowania (J7) | każde `refer` ma 3–5 pozycji `reasons[]` i ≥1 `moments[]` z `deepLink` i `evidenceId` wskazującym istniejący dowód; `refer` bez nich nie powstaje (`insufficient`) |
| T30 | dostępność i język | film usunięty/prywatny → `availability` bez nowej wersji i ostatnia wersja zostaje; `outOfScope:"language"` tylko w `all` |

Pomiar po wdrożeniu: `tests/core` ≈ 42 testy (9 obecnych + T1–T33 z podziałem na pliki), na izolowanej bazie.

## 5. Kolejność wdrożenia (kroki odbierane osobno)

Każdy krok daje działający stan, test i kryterium odbioru; kolejny startuje po odbiorze poprzedniego. Pliki w obrębie H (jedyny właściciel), o ile nie zaznaczono. Krok S0 jest wspólny z M.

| Krok | Zakres | Pliki | Test | Odbiór |
|---|---|---|---|---|
| S0 | Testy kontraktowe z `expectedFailure` | `tests/core/test_contract_v2_*.py` (M + H) | T1–T33 jako szkielety | Lista testów czerwonych z oczekiwanym powodem; 9 obecnych zielonych |
| S1 (odebrane) | Migracja, widok zgodności, `origin`, `analysisCurrent`, `needsRecalc` | `api/store.py` (migracje, `compat_view`, `derive_origin`), `api/server.py` (`/v1/state`, `/v1/health`) | T11, T12, T18, T19 | Baza z HEAD 491094d otwiera się, odczyt starych spraw ma pola domyślne, drugi start bez zmian |
| S2 | Normalizacja, `contentCompleteness`, powód wersji, scalanie ścieżek, szereg `reach` (tabele boczne `version_meta`, `discoveries`, `reach_samples`) | `api/store.py`, `api/jobs.py` (`scan_id`), `api/server.py` (`/versions`, `/reach`), `collectors/discovery.py` (`merge_capture`, `merge_captures`), testy `tests/core/test_contract_v2_*.py` | T1, T2, T3, T4, T5, T17 (zielone bez `expectedFailure`), T10 (trasy) | Atom + API → jedna sprawa, dwie ścieżki; zmiana samych statystyk nie tworzy wersji; pomiary z §1.8 dają 0 fałszywych wersji |
| S3 | Rejestr adapterów, walidator, kroki skanu, heartbeat, `source_state`, `quota_ledger` | `collectors/discovery.py`, `collectors/adapter.py` (nowy), `api/jobs.py`, `api/store.py` | T8, T16 | Istniejące źródła działają przez rejestr bez zmiany wyników; przerwany skan wznawia od niezakończonych kroków |
| S4 | **YouTube pierwszy**: rejestracja `collectors/youtube.py` (pisze B), Atom owinięty, replay z fikstur sondy | `collectors/discovery.py` (wpis w rejestrze), `api/jobs.py`; plik adaptera B | T2 end-to-end, T30, próba Y na izolowanej bazie | Świeży skan przez normalną kolejkę; bez klucza status `needs_key` i działa replay; z kluczem search→videos→channels→playlistItems i ponowny odczyt (wymaga klucza od J) |
| S5 | **Cień kwalifikacji D**: `qualify` w `engine.analyze`, `variants`, `priority`, legacy mapowanie, kalibracja z `variant` | `analysis/engine.py`, `api/jobs.py` (`evaluate`), `api/store.py` (`analysis_sig`, `variants`), `api/server.py` (`/v1/calibration`); D dostarcza `analysis/qualification.py` | T14 (część pól), T20, T21, T26, T28, T31, T32, T33 | Pola v2 w rekordach, kolejka `review` i `high_risk` identyczne jak dziś (T21). **Tu zatrzymanie: G mierzy FP/FN na odłożonych kampaniach, Fable zatwierdza wariant** |
| S6 | Kolejki po stronie API, `pendingReReview`, `reviewStale`, pola decyzji | `api/store.py` (`queues_of`, decyzje), `api/server.py` (`/v1/queues`, PATCH), `GET /v1/cases/{id}/versions` | T6, T7, T14, T27 | Liczniki i listy zakładek z API; J1 może podłączyć UI; domyślna zawartość `review` nadal wg aktywnego `rules_1_2` |
| S7 | Przełącznik wariantu, próg per wariant z historią, `recompute`, reguła `high_risk` per wariant | `api/store.py`, `api/server.py`, `api/jobs.py` (`mode=recompute`, `model_cache`) | T13, T15, T22, T23, T24 | **Dopiero po bramce z S5.** Zmiana i cofnięcie wariantu i progu z historią, decyzje analityka nietknięte |
| S8 | Transkrypcja i dowody: wpięcie C, `coverage`, opcjonalne kadry tylko dla `refer` (ponowne `qualify` po dopisaniu kadru), `POST /v1/evidence` | `api/jobs.py` (`enrich`), `api/server.py` (`/v1/evidence`), `api/store.py` | T25, T29, T31, T33 | `refer` i `complete/transcript_unavailable` na realnych przypadkach; link do sekundy; kadr z czasem tylko dla skierowanych |
| S9 | M2/M3/K i pełna droga z B po każdej zmianie API | `collectors/discovery.py`, `api/*` | pełne `tests/core`, `tests/e2e`, próba Y i U | Pełny obieg z interfejsu na izolowanej bazie; powtórzenie, edycja źródła, równoległa decyzja, restart, reconnect, id z ukośnikami |

Stan: S0-S3, S5 i S8 odebrane; S4, S6 i S7 wdrożone lokalnie (§3.10), do odbioru. Poprzednio: S5 (cień kwalifikacji D) i S8 (krok mediów) wdrożone lokalnie w trybie cienia (bez commitu), do odbioru; S4 czeka na stabilny interfejs `Context` agenta B (decyzja Fable: źródło ze statusem `limit` lub `needs_key` kończy skan jako `partial` z widocznym powodem, wdrożenie w S4). S3 nie zależy od klucza YouTube ani od pomiarów G.

S3 w kodzie: `collectors/adapter.py` (kontrakt, walidator, `execute`, `MemoryRunner`), rejestr `ADAPTERS` w `collectors/discovery.py` (apple-podcasts, peertube, social, sites, crosslinks jako etap drugi, replay; `youtube` zarejestrowany, ale wyłączony do czasu wpisu `INVESTWATCH_ADAPTERS=youtube`, bo skan z kluczem zużywa dzienną kwotę; S4 włącza go domyślnie), `api/jobs.py` (`ScanRunner`, dzierżawa `INVESTWATCH_LEASE_SECONDS`, domyślnie 300 s, przedłużana przy każdym żądaniu adaptera, kroku i przeanalizowanym materiale; `LeaseLost` zatrzymuje skan bez zapisu), `api/store.py` (migracja 4: `scan_steps`, `source_state`, `quota_ledger`; `/v1/state` dostaje `sourceState` i `sourceHealth`, wiersze `sources` zostają w kształcie v1 przez T18), `GET /v1/scans/{id}` (kroki `{step,status,attempts,summary}`, `progress`, `budget`). Wznowienie: kroki `discover:<adapter>` zapisują wynik i po przerwaniu nie są powtarzane; `enrich`, `analyze` liczą się od nowa; wynik skanu zapisuje się jedną transakcją razem ze statusem `apply` (jedno zdarzenie „Skan zakończony”). Kwota dzienna: `Adapter.daily_units_env` (dla YouTube `INVESTWATCH_YT_DAILY_UNITS`, doba kończy się o północy czasu pacyficznego), budżet przebiegu = min(`INVESTWATCH_YT_RUN_UNITS`, pozostała kwota); wyczerpane źródło lub `retryAt` w przyszłości nie wywołuje adaptera i daje status `limit` z kursorem w `source_state`.

Nakład (praca agenta, bez przeglądu zewnętrznego): S0 2 h, S1 3–4 h, S2 4–5 h, S3 4–5 h, S4 2–3 h po stronie H (adapter B osobno), S5 4–5 h, S6 3–4 h, S7 4–5 h, S8 3–4 h, S9 3 h. Razem ≈ 32–40 h; ścieżka do odbioru Y (S0–S4) ≈ 15–19 h.

## 6. Rozbieżności, których nie rozstrzygam sam

| # | Rozbieżność | Rekomendacja |
|---|---|---|
| N1 | Transkrypcja a dostęp (B): `captions.download` wymaga prawa edycji filmu, `/api/timedtext` i pobieranie audio filmu są poza warunkami YouTube. Dla cudzych filmów rynkowych transkrypcja będzie zwykle niedostępna. Po decyzji J5 `refer` z samego opisu jest możliwy (link śledzący lub kod bez oznaczenia, np. 3 materiały Comparic z wynikiem 24 wg I), ale: (a) `no_signal` i przesłanki z mowy (U4–U6) będą stale blokowane, więc `complete/transcript_unavailable` przestaje być stanem przejściowym (J4); (b) `refer` z opisu bez zbadanej mowy ma realne ryzyko FP, bo oznaczenie może paść w mowie, której nie sprawdzono; (c) dwie deklaracje XTB (opis 26 znaków, `partial`) pozostają `complete` do czasu pełnego opisu | Przyjąć: `incomplete/transcript_unavailable` jako stan stały z widocznym licznikiem; `refer` z opisu pokazywać z jawnym „mowy nie zbadano” w `reasons[]` (J5). Uprawnione źródła transkrypcji: bliźniaczy podcast RSS, plik za zgodą, transkrypt analityka (`POST /v1/evidence`). Wpływ (b) na precyzję mierzy G na odłożonych kampaniach przed bramką z S5. J potwierdza |
| N2 | Gdzie działa próg: D liczy `refer` tylko przy `value >= próg` (poniżej → `complete`), co czyni trasę zależną od progu i miesza „brak danych” z „słaby sygnał” (sprzeczne z J4 i J5). Dodatkowo U1 z samego opisu ma wg punktów startowych D 35 + 15 + 10 = 60, czyli dokładnie próg domyślny, więc „refer” z J5 jest na granicy kolejki | `qualify` bez progu: `refer` ⇔ przesłanka udokumentowana (zgodnie z J5). Próg stosuje API (`queueEligible`), `high_risk` odpala dla `queueEligible`. D dobiera punkty tak, by udokumentowane U1 z cytatem przekraczało domyślny próg z zapasem, a G strojenie weryfikuje. Słaby sygnał poniżej progu trafia do `all` z etykietą „poniżej progu”. Wymaga zgody D (zmiana reguł 1–2 w jego §2) i Fable |
| N3 | Lokalny model w workerze: Ollama działa na hoście (Mac M3, L), a worker to kontener Linux x86 bez Ollama i bez dostępu do hosta; OpenRouter jest poza workerem. Wariant `qual_d_model` może nie mieć gdzie działać w demo na jednej maszynie | Zarejestrować wariant w przełączniku dopiero po potwierdzeniu przez L łączności kontener→Ollama i digestu wag; do tego czasu `qual_d_model` niedostępny (PUT zwraca 422), a pomiary G idą narzędziem offline. Fallback na `qual_d` działa bez niego |
| N4 | Czy materiał `replay` (datowana kopia rzeczywistych danych z 21 XI) wchodzi do rzeczywistych kolejek i rejestru: Q wyklucza „syntetyczny albo ręcznie przesłany”, nie replay; I liczy 87 live i 6 replay | `replay` kwalifikuje się do kolejek z widoczną etykietą pochodzenia i datą; `synthetic`/`upload` tylko w `demo`. Decyzja J, bo zmienia liczniki pokazu |
| N5 | Kolejność w `review`: I zapisał, że zasięg nie wpływa na kolejność; D i R4 dopuszczają `priority.review` przy równym statusie | Wynik malejąco, potem `priority.review.rank` jako rozstrzygnięcie remisu, potem data. Zasięg nigdy nie zmienia przynależności. I dostosowuje opis |

Rozstrzygnięte samodzielnie (do wiadomości): nazwa `route`, struktura `coverage` jako mapa, `discovery[]` (sprawa) kontra `discoveries[]` (twórca, bo legacy `creator.discovery` to obiekt), `score` przy `withheld` = 0 z `scoreBasis` i osobny licznik w kalibracji, właściciel indeksu aliasów firm = D (plik danych generowany jego narzędziem, H czyta tylko przez `qualify`), `sourceUrlAtTime` jako nazwa odsyłacza do sekundy.

## 7. Ryzyka

1. **Migracja przy równoległym starcie API i workera** (T12).
2. **Fałszywe wersje po wdrożeniu normalizacji**: istniejące sprawy mogą jednorazowo dostać wersję `analysis` lub `content`; zapisać w logu i zaakceptować.
3. **Tryb cienia rozjedzie się z docelowym zachowaniem**: tabele kolejek i `high_risk` mają dwie reguły do czasu bramki; T21 i T24 pilnują obu.
4. **Dzierżawa 900 s przy skanie z paginacją i limitem** (heartbeat i kroki w S3).
5. **Skala `/v1/state`** (`?compact=1`, `/v1/queues`, indeksy).
6. **Dwa źródła prawdy o kolejce**: do czasu S6 klient filtruje po `reviewSuggestion`; J1 przechodzi na `queues[]` w jednym kroku.
7. **Kalibracja a zbiór G**: `yt-partner` ma dziś `expected:true`; po zmianie jednostki etykiety wyniki bazowe się zmienią. Zbiór należy do G i nie zmieniam go.
8. **Klucz YouTube**: brak klucza blokuje próbę Y live (nie blokuje S0–S3 ani replay). Sekret tylko w środowisku workera.
9. **Wariant z modelem bez miejsca uruchomienia** (N3).
10. **Wydajność `analyze`**: dwa warianty reguł na każdy capture przy każdym skanie; model tylko dla aktywnego wariantu. Pomiar w S5.

## 8. Ograniczenia tej wersji

- Zero zmian w kodzie i bazie; edytowany jest wyłącznie ten plik. Nie uruchamiano Compose, Chromium ani modeli.
- Test bazowy `tests/core` z poprzedniej wersji (9 testów OK) nie był powtarzany po tej edycji, bo kod się nie zmienił.
- Dokumenty D, I, B i OPENROUTER-M3 czytano w stanie z 21 XI wieczorem; `fable-d-porownanie.md` nie był czytany.
- `Qwen` i Ollama nie były uruchamiane; opis wariantu z modelem opiera się wyłącznie na dokumentach.
- Nakłady i wydajność to oceny bez pomiaru pod obciążeniem.

## Uzupełnienie 21 XI (kolejka mediów i adnotacja modelem)

- Model agenta: claude-sonnet-5-5 (Sonnet 5.5).
- `api/enrich.py`: 429 o zakresie `video` zostawia film jako pending z `mediaAttempts` i krok idzie dalej (`summary.videoLimited`); przerwanie tylko przy `login_required` lub `rate_limited` z zakresem `host` (także w kroku kadrów). Kolejność: najmniej prób najpierw, w obrębie tego dotychczasowy ranking. Po `MAX_TRIES`=3 nieudanych próbach film jest trwale niedostępny z powodem „nieudane 3 próby”. `api/store.py::media_outcome` liczy pending z `mediaAttempts` jako `failed`. `no_captions` pozostaje trwały i nie wraca do kolejki. `mediaCoverage.transcript.source=transcript_api` przechodzi bez zmian. Testy: `tests/core/test_contract_v2_media_queue.py` (4).
- `analysis/engine.py`: przy `INVESTWATCH_MODEL_ANNOTATE=1|on|true` `analyze()` dopisuje `finding.model` (`affectsDecision=false`) i `analysisVersion.model` tylko dla materiałów kolejek review (refer i kwalifikujący się), adRegister (included/candidate), M2 i M3. Wyjątek lub brak wag daje `model.status=unavailable` z powodem „model niedostępny”, nigdy błąd skanu. Bez flagi wynik jest identyczny. Pole `model` nie wchodzi w sygnaturę treści i trafia do widoku 2 sprawy. Testy: `tests/core/test_contract_v2_model_annotation.py` (5). Łatka `fable-ai-inferencja-patch.diff` wdrożona ręcznie (inne gating i obsługa wyjątku).
- Ograniczenia: adnotacja kolejki jest przybliżeniem `queues_of` na poziomie findingu (nie widzi statusu `closed`, `needsRecalc`, dostępności dowodów). Nie uruchamiano pętli enrich na `.runtime/s4-live` ani realnych wag/usługi LLM.
