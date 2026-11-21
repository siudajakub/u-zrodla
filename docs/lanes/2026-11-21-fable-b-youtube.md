# Lane: B · YouTube (sonda rozpoznawcza)

- Owner: J (decyzje produktowe); wykonawca B (Claude Opus 5.5, wysiłek high), zlecenie od Fable
- Branch: hack/fable/b-youtube (jeszcze nieutworzona); sonda wykonana w checkoucie głównym na hack/integration (HEAD 491094d)
- Worktree: jeszcze nieutworzony
- State: ACTIVE. Fala 2: adapter `collectors/youtube.py` z testami i świeży skan live z kluczem (2088 j.). Czeka na podpięcie przez H (S4) i porównanie z listą Y przez G.
- Updated: 2026-11-21 20:50 UTC
- PR / issue: none yet

## Acceptance

[Próba Y](../fable/ODBIOR.md) i wiersz B [planu](../fable/REALIZACJA.md). Kanał ma zostać wykryty bez podawania wyszukiwarce jego ID. Rekord zapisuje zapytanie, czas, metodę i pozycję oraz statystykę z czasem odczytu. Trzeba pokazać nowego dużego twórcę z rzeczywistą promocją firmy inwestycyjnej, osobno polskojęzyczną promocję firmy transgranicznej, scalenie wyników Atom i API oraz zachowanie przy kolejnej stronie, limicie, usunięciu, prywatności i błędnym języku. Ta fala obejmuje tylko sondę i rekomendację.

## Claim

- `docs/lanes/2026-11-21-fable-b-youtube.md`
- `tools/youtube_probe.py` (sonda bez klucza; tryb `report` dla skanu adaptera)
- `fixtures/raw/discovery/youtube-probe-2026-11-21/` (sonda bez klucza)
- `collectors/youtube.py`, `collectors/test_youtube.py` (fala 2)
- `fixtures/raw/discovery/youtube-api-2026-11-21/` (surowe odpowiedzi API, `replay.json.gz`, `report.json`, `channels-by-subscribers.json`)

## Contracts And Dependencies

- Produces: Capture v1 dla YouTube rozszerzony o `discovery[]`, `reach[]` i `youtube{}` (szczegóły niżej). Konsumentami są H (scalanie, store) i D (kwalifikacja).
- Consumes: aliasy firm z `data/probe-snapshots/knf/` (DM krajowe i notyfikacje transgraniczne), `tools/watch_sources.json` jako listę seedów, `collectors.common`.
- Shared-file coordination: `collectors/discovery.py` (podpięcie adaptera) należy do H. Rozwiązywanie aliasów w `collectors/crosslinks.py` należy do K. Ten rekord zgłasza K błąd opisany w punkcie „Przypadek błędu”.

## Current State

### Dostęp i sekrety (sprawdzono wyłącznie nazwy, bez wartości)

- Repo, zmienne środowiska sesji, `compose.yaml` i `ops/` nie odwołują się do `YOUTUBE_API_KEY`, `GOOGLE_API_KEY` ani innego klucza YouTube. Compose nie ma `env_file`.
- W `hacknation/` nie ma plików `.env`. Są tylko `vendor/*/.env.example` z innych projektów, bez kluczy YouTube.
- Konfiguracja hosta poza repo nie zawiera klucza YouTube dla projektu. Konta i klucze innych projektów pominięto bez użycia (szczegóły hosta usunięto z rekordu przy porządkowaniu repo).
- Narzędzia: brak `yt-dlp` (także w `.runtime/venv` i `.runtime/qa`), `youtube_transcript_api`, `googleapiclient` i whispera w Pythonie hosta. Jest `ffmpeg`. Niczego nie instalowano.

### Wyniki prób live z 2026-11-21, 18:29:53–18:34:46 UTC

Wykonano 61 żądań z przerwą co najmniej 1,5 s na host, bez logowania. Statusy: 54× 200, 3× 404, 1× 403, 1× 400. Żaden zapisany URL nie zawiera klucza. Wszystkie odpowiedzi leżą w `fixtures/raw/discovery/youtube-probe-2026-11-21/requests.jsonl` z numerem, czasem, statusem i sha256 nieskompresowanej treści. Pliki ponad 300 KB są spakowane do `.gz`. W 16 zapisanych stronach kanałów zamieniono osadzony publiczny klucz klienta webowego YouTube (`AIza…`) na `AIza_REDACTED_YOUTUBE_WEB_CLIENT_KEY`, żeby skanery sekretów nie zgłaszały go przy commicie. sha256 tych plików w indeksie dotyczy treści sprzed redakcji.

| Droga | Tryb | Status | Dowód i liczniki | Warunki i ryzyko |
|---|---|---|---|---|
| (a) Data API v3 search.list → videos.list/channels.list → playlistItems | live, bez klucza | **wymaga klucza** | Żądanie [001] zwróciło 403 `PERMISSION_DENIED` (`youtube.googleapis.com`). Ścieżka z kluczem jest gotowa w `youtube_probe.py api`, ale jej nie uruchomiono | Droga podstawowa zgodna z warunkami. Kwota wynosi 10 000 j./dzień, search.list kosztuje 100 j. Dane nieautoryzowane trzeba odświeżać lub usuwać w ciągu 30 dni (Developer Policies) |
| (b) Atom `feeds/videos.xml?channel_id=` | live | **działa** | 10 odczytów 8 kanałów (2 ponowne). 7 kanałów miało po 15 pozycji, `@KanalSportowy` 0. Wśród 105 pozycji jest 28 Shorts z linkiem `/shorts/`. Każda pozycja ma `media:statistics views` i `starRating count`. Drugi odczyt po ok. 80 s pokazał zmianę wyświetleń w 21 z 30 filmów przy 15/15 identycznych opisach i `updated` w obu kanałach | Mechanizm jest udokumentowany (WebSub). `robots.txt` YouTube zawiera jednak `Disallow: /feeds/videos.xml` dla ogólnych crawlerów. Używamy go jako czytnika subskrypcji znanych ID, a nie do pełzania. Nie daje subskrybentów ani języka, a okno to 15 pozycji |
| (c) oEmbed `/oembed` | live | **działa** | 6× 200 dla trzech kandydatów i jednego tropu z RSS (ten sam film trzy razy w pierwszym przebiegu). Zwraca `author_name` i `author_url` w formie `@handle`, bez ID kanału. Nieistniejące ID `aaaaaaaaaaa` daje 400 | Oficjalny i lekki. Potwierdza trop i autora, ale nie daje trwałego ID ani opisu |
| (d1) Apple Podcasts Search API | live | **działa, mało trafień YouTube** | 9 zapytań, wszystkie 200. 3 frazy promocyjne zwróciły 0 wyników (42 B). Kanały RSS polskich podcastów nie zawierały linków do YouTube. Linki prowadziły głównie do firmowych kanałów eToro i XTB CZ | Zgodne z warunkami. Daje odkrywanie przez katalog, a nie wyszukiwanie YouTube |
| (d2) RSS podcastów → linki | live | **działa** | 12 kanałów RSS dało 5 linków do profili i 188 do filmów, prawie wyłącznie firmowych (eToro DE/IT/global). 2 kanały RSS obcięto przy limicie 4 MB | Zgodne z warunkami. Uzyskaliśmy markowe kanały firm, a nie twórców |
| (d3) PeerTube | nie testowano w tej sondzie | n/d | Obecny `discovery.py` już go używa. YouTube nie ma tam twórców | — |
| (e1) strona kanału `/@handle` → ID | live | **działa po poprawce** | 11 handle'i z publicznych rankingów: 8 rozwiązanych, 3× 404. Nie przyjmujemy handle'a bez weryfikacji. `@KanalSportowy` prowadzi do kanału o tej samej nazwie z pustym Atom i ok. 193 subskrybentami, czyli prawdopodobnie nie oficjalnego | To skrobanie HTML, a warunki YouTube zakazują automatycznego dostępu poza robots.txt. Robots nie blokuje `/@`. Repo już tak robi w `crosslinks.channel_id`. Po uzyskaniu klucza zastąpić `channels.list?forHandle=` (1 j.) |
| (e2) Wikidata SPARQL (P2397) | live | **działa, bezużyteczne w niszy** | Zapytanie o osoby z Polski z finansowym opisem dało 1 wynik. Szersze zapytanie ręczne zwróciło głównie polityków i ekonomistów | Otwarte API zgodne z warunkami. Pokrycie finfluencerów jest znikome |
| (e3) wyszukiwarka WWW agenta | ręcznie | **trop pomocniczy** | 9 zapytań nie zwróciło żadnego URL z youtube.com. Przydały się rankingi twórców: [comparic InvestTube 2026](https://comparic.pl/ranking-investtube-2026-ci-tworcy-maja-najwiekszy-wplyw-na-decyzje-inwestorow/), [freenance 2026](https://freenance.io/rankingi/najlepsze-kanaly-youtube-o-finansach-polska/) oraz [SII](https://www.sii.org.pl/14541/aktualnosci/felietony/18-kanalow-o-finansach-na-youtube-ktore-warto-sledzic.html) | Nie może zasilić produktu. Rankingi są publiczne, więc G może je użyć do listy referencyjnej. Ta ścieżka **nie liczy się do benchmarku Y** |
| (e4) `/results`, `/youtubei/`, `/api/timedtext`, yt-dlp, Invidious/Piped | nie uruchamiano celowo | **odmowa z warunków** | `robots.txt` zawiera `Disallow: /results`, `/youtubei/` i `/api/`. yt-dlp nie jest zainstalowany | Technicznie to działa, bo z tego korzysta yt-dlp `ytsearch`. Narusza jednak warunki YouTube (zakaz automatycznego dostępu i pobierania). Najwyżej awaryjny replay ręcznie zebranego materiału, oznaczony jako import, nigdy jako droga podstawowa |

### Napisy i audio do analizy lokalnej

- `captions.list` (50 j., wystarczy klucz) zwraca listę ścieżek z językiem i rodzajem (`asr` lub `standard`). Tak sprawdzimy, czy napisy istnieją.
- `captions.download` (200 j.) wymaga OAuth `youtube.force-ssl` i prawa edycji filmu. Dla cudzych filmów to niedostępne.
- `/api/timedtext` i pobieranie audio filmu są poza warunkami serwisu. Nie testowano ich.
- Uprawnione wejścia dla C: własny lub udostępniony za zgodą plik, transkrypt dostarczony przez analityka oraz bliźniaczy odcinek podcastu RSS (`audio.py` już to obsługuje).
- Dla DNA Rynków i Kanału Zero wyszukiwanie Apple nie znalazło bliźniaczego podcastu (żądania [060]–[061]).
- UI zawsze pokazuje link `watch?v=ID&t=Ns`.

### Sonda odkrycia (bez ID kanałów w wyszukiwarce)

| Przebieg | Zapytania | Wyniki (wiersze) | Unikalne kanały | Unikalne filmy | Plik |
|---|---|---|---|---|---|
| katalogi: Apple → RSS → profil → Atom, Wikidata | 9: 3 marki (XTB, eToro, Trading 212), 3 promocyjne, 3 tematyczne | 1 | 1 | 0 | `results-keyless.jsonl` (rozwiązanie aliasów nie zadziałało, patrz błąd) |
| rankingi publiczne → handle → strona → Atom | 11 handle'i | 116 | 8 | 105 | `results-rankings.jsonl` |
| potwierdzenie: oEmbed i ponowny Atom | 4 URL | 34 | 2 | 31 | `results-confirm.jsonl` |
| razem | 24 | 151 | 9 | 106 | 0 trafień w seedach (DETERMINACJA, Comparic Rynki) |

Każdy wiersz zawiera: `route`, `via`, `queryKind`, `query`, `observedAt`, `position`, `channelId`, `videoId`, `url`, `author`, `title`, `published`, `shorts`, `stats{views, ratingCount, statsObservedAt}`, `signals{promo, brands}` i `seeded`. Liczby subskrybentów poniżej pochodzą z tekstu strony kanału. To nieoficjalne odczyty, do zastąpienia `channels.list`.

### Kandydaci na pierwszy pion

1. **Nowy twórca z niszy inwestycyjnej (rekomendacja):** Piotr Cymcyk – Merytorycznie o Finansach (`UCgw_3Epv7swquSZyMDjYHTg`, `@DNARynkow`, ok. 122 tys. subskrybentów wg strony). Kanał trafił do sondy przez ranking SII → handle → stronę → Atom. Nie ma go w seedach. W 15 ostatnich filmach opisy zawierają linki afiliacyjne XTB (7), Freedom24 (4) i Saxo Bank (2).
   - Film: https://www.youtube.com/watch?v=-HpCSKp9bqk („Nadchodzi bessa na rynku nieruchomości?…”, 221 247 → 221 266 wyświetleń w Atom o 18:32:34 i 18:33:52 UTC).
   - Cytat z opisu: „Zacznij razem z aplikacją XTB — https://link-pso.xtb.com/pso/kdg44 / Rejestrując się na XTB z kodem DNARYNKOW otrzymasz specjalny kurs zarządzania finansami od podstaw. #YSBP | Inwestowanie jest ryzykowne.”
2. **Największy zasięg:** Kanał Zero (`UClhEl4bMD8_escGCCTmRAYg`, ok. 2,42 mln subskrybentów wg strony). To kanał publicystyczny, a nie inwestycyjny, więc jego przynależność do populacji Y rozstrzyga J lub G.
   - Film: https://www.youtube.com/watch?v=T_Nnok-eNUY (21 974 → 24 580 wyświetleń).
   - Cytat: „Zdobądź ją podczas bezpłatnej konferencji online XTB Investing Masterclass już 27-28 listopada. Zapisz się 👉 http://link.pl.xtb.com/kanal-zero / Rejestrując się w XTB z kodem ZERO, otrzymasz specjalny kurs…”
3. **Promocja firmy transgranicznej po polsku:** Freedom24 na tym samym kanale Cymcyka. Freedom Finance Europe Ltd (Cypr) występuje w lokalnym wykazie notyfikacji KNF `knf_notyfikacje_zagr_FI.json`.
   - Film: https://www.youtube.com/watch?v=9Fcwo1jlwe4 (89 107 wyświetleń).
   - Cytat: „Inwestuj globalnie i odbierz do 20 darmowych akcji na start: https://c.freedom24.com/?a=t9fkwo&i=fvk7z5&ref1=1511 … Firma znajduje się pod nadzorem CySec.”
   - Opis nie zawiera słów „reklama” ani „płatna współpraca”. Mowy, obrazu i flagi „płatnej promocji” nie sprawdzono, więc nie wolno wnioskować o braku oznaczenia w całym filmie.
   - Wariant z jawnym oznaczeniem: https://www.youtube.com/watch?v=_aqCM37gK1U, cytat „Partnerem publikacji jest Saxo Bank, z którym serwis prowadzi płatną współpracę marketingową. #PłatnaWspółpraca”. Saxo Bank A/S nie występuje w lokalnych kopiach rejestrów KNF/ESMA, więc status trzeba zweryfikować.

Ograniczenie: kandydatów znaleziono przez publiczne rankingi i handle, a nie przez wyszukiwanie YouTube. Warunek Y („wykryty przez wyszukiwarkę na zapytaniach”) zostanie spełniony dopiero po ponownym przebiegu `api` z kluczem. Kandydat musi wtedy wypłynąć z search.list bez podawania jego ID.

### Przypadek błędu: wyniki sondy katalogowej, do zgłoszenia K

`collectors/crosslinks.py: ChannelMetadata` czyta identyfikator kanału tylko z `<head>`. Na stronach pobranych 21 XI 2026 YouTube umieszcza `<link rel="canonical">`, `og:url` i `itemprop="identifier"` dopiero po `</head>` (dla `@etoro` `</head>` jest na pozycji 842 917, a canonical na 894 288). Efekt: wszystkie 8 rozwiązań aliasów w pierwszym przebiegu zwróciło brak ID, więc ten przebieg nie odczytał żadnego Atom. Sonda zawiera lokalny resolver, który przyjmuje tylko te trzy znaczniki i wymaga jednej wartości. Test rozstrzygający dla K: plik `023-profile-etoro.html.gz` → `UCaQbkbbr35GXYsJTjeI-Ahg`.

Drugi błąd, wykryty i poprawiony w sondzie: Atom podaje `yt:channelId` bez prefiksu `UC`. Pliki wyników zostały znormalizowane bez ponownych żądań.

## Fala 2: adapter i skan live (2026-11-21, 19:03–19:06 UTC, klucz z `~/.config/investwatch/youtube.key`)

### Adapter `collectors/youtube.py`

- `discover(ctx)` zwraca `{creators, captures, sources, status, resume, retryAt, quota}`.
- **Interfejs `Context` v1 (stabilny od 2026-11-21 19:20 UTC; zmiana tylko z wpisem w tym rekordzie):**
  - `mode`: live | replay;
  - `state`: treść `source_state`, w tym `resume={queryIndex, query, pageToken, page}`;
  - `budget`: twardy limit jednostek przebiegu. Domyślnie `INVESTWATCH_YT_RUN_UNITS` albo **0**, czyli bez budżetu żadnego wywołania API;
  - `fetch(url) → (status, body)`: `None` oznacza `http_fetch`, wyszukiwany przy wywołaniu;
  - `clock() → ISO UTC`;
  - `key`, `key_source`: `None` oznacza wywołanie modułowego `load_key()` przy każdym skanie, więc `patch.object(youtube, "load_key")` działa;
  - `heartbeat()`: wołany przed każdym żądaniem API, runner H podmienia go na przedłużenie dzierżawy;
  - `raw_dir`, `cache_dir`: ścieżki od workera (np. pod `store.STATE`), `None` = bez zapisu;
  - `cache_ttl` oraz ustawienia skanu (`queries`, `window_days`, `published_after`, `max_results`, `playlist_channels`, `atom_channels`, `pause`, `known_creators`) nadpisywalne przez `ctx.options["youtube"]`.
- **Kody błędów:** wyczerpany budżet przebiegu to `status=rate_limited`, `sources[0].lastError.code="budget"`, status źródła `partial` lub `empty`, bez `retryAt`. Limit z API to `lastError.code="quotaExceeded"` (lub `dailyLimitExceeded`, `rateLimitExceeded`), status źródła `limit`, `retryAt` = północ czasu pacyficznego.
- **Zgodność z H (sprawdzona):** `collectors/discovery.py:_youtube` buduje `youtube.Context(mode, state, known_creators, budget, **ctx.options["youtube"])` i podstawia `heartbeat`. Rejestr włącza adapter tylko przy `INVESTWATCH_ADAPTERS=youtube`, z `daily_units_env=INVESTWATCH_YT_DAILY_UNITS`, `run_units_env=INVESTWATCH_YT_RUN_UNITS` i `quota_tz=America/Los_Angeles`. `validate_adapter_result` przyjmuje fiksturę replay: 1300 z 1300 zachowanych, 0 błędów. `tests/core/test_contract_v2_*.py`: 85 testów OK (20 oczekiwanych porażek H).
- Przepływ: search.list (`type=video`, `regionCode=PL`, `relevanceLanguage=pl`, `maxResults=50`, okno `publishedAfter` z dokładnością do dnia, `pageToken`) dla 17 zapytań w trzech rodzinach → videos.list (`snippet,statistics,contentDetails,status,paidProductPlacementDetails`; przy 400 ponowienie bez flagi) → channels.list → playlistItems dla 8 kanałów z najwyższą pozycją skanowania → videos.list dla nowych filmów z playlist → Atom dla 3 pierwszych kanałów.
- Rekord zgodny z kontraktem v2: `id=youtube:<videoId>`, `creatorId=youtube:<UC…>`, `discovery[]` (`method` ∈ data_api_search, data_api_playlist, atom; `queryKind`, `query`, `position`, `page`, `sourceUrl` z `key=REDACTED`, `responseSha256`, `reason`, `quotaUnits`, `import:false`), `reach.metrics` ze stanem observed/hidden/unavailable/not_collected, `contentCompleteness` (full z videos.list i Atom, partial z samego search.list), `youtube{durationSec, isShort, defaultAudioLanguage, detectedLanguage, languageMethod, languageStatus, privacyStatus, paidPromotionFlag}`, `availability`, `priority.acquisition{rank, reason}`. Twórca: `status=confirmed`, `persistentId`, `discoveries[]`, `reach.subscriberCount` (ukryte → `hidden`), `scanPriority{rank, reason}`.
- Atom dla tego samego filmu dopisuje drugi wpis `discovery` (z `atomViews` i hashem treści), a nie drugi materiał. Rekord z API zostaje głównym. Scalanie między skanami robi `merge_capture` H.
- Język: zadeklarowany polski wygrywa. Silny polski tekst wygrywa z inną deklaracją (twórcy zostawiają `en-US` lub `zxx`, np. Marcin Iwuć), poza tym deklaracja, a na końcu tekst. `regionCode` niczego nie rozstrzyga. Materiał nie-PL zostaje z `languageStatus=out_of_scope`.
- Shorts: `isShort=true` przy ≤ 60 s albo linku `/shorts/` w Atom, `null` przy 61–180 s. Shorts mają osobny koszyk w kolejności skanowania. Remis rozstrzyga nowszy film, potem `videoId`.
- Film zwrócony przez search.list, którego nie ma w videos.list: `availability=unavailable`, `contentCompleteness=partial`, zasięg `not_collected`. `privacyStatus=private` daje `availability=private`.
- Kwota: twardy budżet przebiegu. Rezerwa na wzbogacenie jest liczona przed każdym search.list. Księga `quota.entries` liczy również nieudane żądania. Po prawdziwym `quotaExceeded` przebieg nie wysyła już żadnego żądania do API: `status=rate_limited`, źródło `limit`, `retryAt` = północ czasu pacyficznego, `resume={queryIndex, query, pageToken, page}`. Atom działa dalej.
- Cache odpowiedzi na dysku (TTL: search 6 h, channels 1 h, playlist 30 min, videos 10 min, nadpisywane przez `cache_ttl`). Trafienie w cache nie zużywa jednostek ani nie blokuje budżetu.
- Brak klucza: `needs_key` bez wyjątku i bez żądań. Klucz pochodzi tylko z `YOUTUBE_API_KEY`, `YOUTUBE_API_KEY_FILE` lub `~/.config/investwatch/youtube.key`; plik klucza w repo jest odrzucany. W żadnym zapisanym pliku i wyniku nie ma klucza: sprawdziłem `grep -F -f` na kluczu, który zwrócił 0 plików.
- `description_signals(text)` to pomoc dla D i raportu, a nie kwalifikacja. Zwraca firmy z rejestru (krajowe i transgraniczne), `firmEvidence` (link śledzący do domeny firmy, skracacz lub kod wielkimi literami w odległości do 200 znaków od nazwy firmy) oraz frazy ujawnienia. Ignoruje linie kontaktowe w rodzaju „Współpraca: biuro@…”.

### Zużycie kwoty: 2088 jednostek B (dziennie łącznie z H ok. 4990)

| Przebieg | search | videos | channels | playlistItems | Razem |
|---|---|---|---|---|---|
| 1. skan (19:03:44–19:04:21) | 1900 (19 stron) | 27 | 8 | 8 | 1943 |
| nieudany ponowny odczyt (błąd, patrz niżej) | 100 | 9 | 1 | 8 | 118 |
| 2. ponowny odczyt (search z cache, świeże videos) | 0 | 27 | 0 | 0 | 27 |
| **razem** | **2000** | **63** | **9** | **16** | **2088** |

### Liczniki skanu

- 19 stron search.list: 17 zapytań plus druga strona dla „XTB” i „inwestowanie”.
- 1300 filmów: 910 ze ścieżką wyszukiwania, 400 ze ścieżką playlisty, 45 z dodatkowym wpisem Atom, 53 z więcej niż jedną metodą odkrycia.
- 380 kanałów, wszystkie z jawną liczbą subskrybentów (0 ukrytych w tej próbie). 209 kanałów polskojęzycznych, czyli z przewagą filmów `in_scope`.
- 805 filmów po polsku, 495 poza zakresem językowym. 361 Shorts. 276 filmów z flagą płatnej promocji `paidPromotionFlag=true`. 0 filmów niedostępnych.
- Ponowny odczyt po 98 s: 1300/1300 z tym samym hashem treści, 289 ze zmienioną liczbą wyświetleń. Zmiana samych statystyk nie zmienia wersji.

### Porównanie rodzin zapytań na tym samym budżecie

| Rodzina | Jednostki search | Filmy | Kanały | Polskojęzyczne | PL ≥ 100 tys. subskrybentów | PL z promocją firmy inwestycyjnej w opisie |
|---|---|---|---|---|---|---|
| markowe (XTB×2 strony, eToro, Trading 212, Freedom24, Interactive Brokers, Saxo Bank, mBank eMakler) | 800 | 391 | 186 | 51 | 11 | 29 |
| tematyczne (inwestowanie×2, giełda, ETF, akcje dywidendowe, obligacje skarbowe, IKE IKZE, jak zacząć inwestować) | 800 | 388 | 170 | 152 | 20 | 37 |
| promocyjne (partnerem odcinka, kod promocyjny konto maklerskie, link w opisie darmowe akcje) | 300 | 146 | 71 | 52 | 27 | 19 |

- Zapytania markowe zwracają głównie zagraniczne materiały o brokerach (`relevanceLanguage` tylko zawęża).
- Zapytania tematyczne dają 3× więcej polskojęzycznych kanałów na tym samym budżecie.
- Frazy promocyjne najtaniej trafiają w duże kanały ogólne (Kanał Zero, Konopskyy, Patecki) spoza niszy inwestycyjnej.
- „Promocja w opisie” to heurystyka `firmEvidence` lub nazwa firmy z frazą ujawnienia, a nie etykieta.

### Kanały po subskrybentach (wejście dla G, bez porównania z listą Y)

Pełna lista 380 kanałów z ID, drogą odkrycia, czasem, liczbą subskrybentów z datą i oznaczeniem języka jest w `fixtures/raw/discovery/youtube-api-2026-11-21/channels-by-subscribers.json`. Z seedów obecny jest tylko Comparic Rynki. Poniżej 30 największych kanałów polskojęzycznych (subskrybenci z channels.list, 19:04:21 UTC):

| # | Kanał | ID | Subskrybenci | Pierwsza droga odkrycia | Czas | Filmy z promocją / znalezione |
|---|---|---|---|---|---|---|
| 1 | Kanał Zero | `UClhEl4bMD8_escGCCTmRAYg` | 2 420 000 | promo: „link w opisie darmowe akcje” #13 | 19:03:58 | 12/51 |
| 2 | Konopskyy | `UCR7uLtPuXsDpN8N6ocFQyeg` | 2 130 000 | promo: „link w opisie darmowe akcje” #33 | 19:03:58 | 50/50 |
| 3 | Patecki | `UCYsZvmJGPzTMSBXES06-2lg` | 1 980 000 | promo: „partnerem odcinka” #20 | 19:03:56 | 0/50 |
| 4 | Globalista TV | `UC2MQ1TRVmCnslmwlgqayVrw` | 928 000 | topic: „inwestowanie” #26 | 19:03:51 | 4/4 |
| 5 | HISTORIA REALNA | `UCw6m0T0_F5DLfPzJHumplDw` | 778 000 | promo: „partnerem odcinka” #3 | 19:03:56 | 5/5 |
| 6 | Robert Makłowicz | `UCCT_JGIn9I9FS6OTzzqWEew` | 702 000 | promo: „partnerem odcinka” #29 | 19:03:56 | 0/1 |
| 7 | Przemek Górczyk Podcast | `UCrKY6A2xsHXgw3MK9mkan5w` | 666 000 | topic: „inwestowanie” #69 (s. 2) | 19:03:52 | 0/3 |
| 8 | Do Roboty | `UCF5Ug3YNz41qauWNMacdLgw` | 646 000 | promo: „partnerem odcinka” #41 | 19:03:56 | 0/1 |
| 9 | CANAL+ SPORT | `UCTVB8m2FcbwBsi6DHsGSuVw` | 646 000 | brand: „XTB” #35 | 19:03:45 | 1/1 |
| 10 | KSW | `UCv_fwQqff6zEFDxfJh_03fg` | 626 000 | brand: „XTB” #1 | 19:03:45 | 0/2 |
| 11 | Bądź Na Bieżąco | `UCTAAUHQl0sN6w0RpAUzs-Bg` | 562 000 | brand: „Freedom24” #1 | 19:03:48 | 2/2 |
| 12 | naTemat | `UCH5UB8PulkZ75fOHgcSGt2g` | 536 000 | brand: „XTB” #29 | 19:03:45 | 1/3 |
| 13 | Maciej Wieczorek - Expert w Bentleyu | `UCNvSk-U6X9mOJHr7wz_xCWw` | 534 000 | topic: „inwestowanie” #15 | 19:03:51 | 1/1 |
| 14 | Biznes Misja | `UCxhAfhXu0ECIbt_2AN-NdHw` | 506 000 | topic: „inwestowanie” #8 | 19:03:51 | 0/2 |
| 15 | Marcin Iwuć | `UCe8VykA_qDCBmg_08eIA8iQ` | 446 000 | brand: „Saxo Bank” #2 | 19:03:49 | 7/14 |
| 16 | Mieczaki AJ | `UCblCfbJ9YCBU11ngfsZKlWg` | 372 000 | promo: „link w opisie darmowe akcje” #30 | 19:03:58 | 0/1 |
| 17 | This Is IT - Maciej Kawecki | `UCk1qY09hkqTworXLBKd5M-w` | 347 000 | promo: „partnerem odcinka” #11 | 19:03:56 | 0/1 |
| 18 | DzikPlus | `UCMI9Cw5EiT9I1IjetPEXl8Q` | 338 000 | promo: „link w opisie darmowe akcje” #46 | 19:03:58 | 0/1 |
| 19 | Kuba Midel | `UC6SinQiw2eDU6k9tEXpZv9g` | 325 000 | brand: „Freedom24” #7 | 19:03:48 | 3/5 |
| 20 | Onet Rano | `UCjkNubkfecaFLZbHnnsz6pw` | 310 000 | topic: „jak zacząć inwestować” #15 | 19:03:56 | 0/1 |
| 21 | Koniec Świata - Arleta Bojke | `UCGTkoYHU9n1Ec2Z4s5kdgVg` | 309 000 | promo: „link w opisie darmowe akcje” #25 | 19:03:58 | 1/1 |
| 22 | x-kom | `UCmsxFRm1zRgueucG2Pc9Kzg` | 303 000 | promo: „partnerem odcinka” #8 | 19:03:56 | 0/2 |
| 23 | OdwróconaLekcja | `UCKGrbEJp8wgNrR4Q3OeO4bw` | 289 000 | promo: „partnerem odcinka” #35 | 19:03:56 | 0/1 |
| 24 | Kanał Otwarty | `UCuAOJnMr905iKjURUsffDgA` | 229 000 | promo: „partnerem odcinka” #9 | 19:03:56 | 0/12 |
| 25 | Gosia Ohme | `UCEPr3huxC4mEPN8NtIKVmxA` | 215 000 | topic: „ETF” #16 | 19:03:53 | 1/3 |
| 26 | Pankracy | `UC7MTGFfIn1Hht3ZMQxnZBhA` | 212 000 | topic: „inwestowanie” #2 | 19:03:51 | 0/7 |
| 27 | Zawód Inwestor | `UCG4T6bLDq2TdAdRAp2GDOCw` | 208 000 | brand: „XTB” #4 | 19:03:45 | 10/10 |
| 28 | Think About, Piotr Opulski | `UCmodyDWBnEMvu7uLASNQNvg` | 195 000 | promo: „partnerem odcinka” #31 | 19:03:56 | 0/1 |
| 29 | Szczytomaniak | `UChFr0plZ7_23KlTMFEKlMlA` | 181 000 | promo: „partnerem odcinka” #28 | 19:03:56 | 0/1 |
| 30 | Tomasz Trela – Twój człowiek na Wall Street | `UCMh0w6OpVi085p81jK5TnzQ` | 177 000 | topic: „giełda” #30 | 19:03:52 | 0/2 |

Lista zawiera kanały ogólne (kulinarne, podróżnicze, sportowe), które pojawiły się dla fraz promocyjnych. Czy należą do populacji „związanej z inwestowaniem”, rozstrzyga G według swojego kryterium. API znalazło prawdziwy kanał Pankracy (`UC7MTG…`, 212 tys.); sonda bez klucza trafiła na zbieżny handle o innym ID, co potwierdza ryzyko odgadywania handle'i.

### Kandydaci na pierwszy pion (z API, bez seedów)

- **Duży twórca z rzeczywistą promocją firmy inwestycyjnej:** Konopskyy (`UCR7uLtPuXsDpN8N6ocFQyeg`, 2,13 mln).
  - Film: https://www.youtube.com/watch?v=p_ui_fqLdV0 (2 393 368 wyświetleń o 19:05:58 UTC; flaga płatnej promocji `false`).
  - Cytat: „⚫️[reklama] Zarejestruj się w XTB z kodem KONOP i zgarnij darmowy kurs inwestowania od podstaw | Inwestowanie jest ryzykowne…”
  - Alternatywa: Kanał Zero (2,42 mln), https://www.youtube.com/watch?v=AACSYgzS47o (255 654 wyświetleń; flaga `true`), cytat „📚 Wiedza to dobry pierwszy krok w inwestowaniu! Zdobądź ją podczas bezpłatnej [konferencji XTB]…” i kod ZERO.
  - W niszy inwestycyjnej: Zawód Inwestor (208 tys.), https://www.youtube.com/watch?v=B8TYcM5WKp0, cytat „Konto które polecam (XTB): https://geolink.xtb.com/xVRDC Kod przy rejestracji: INWESTOR”.
- **Polskojęzyczna promocja firmy transgranicznej:** Bądź Na Bieżąco (`UCTAAUHQl0sN6w0RpAUzs-Bg`, 562 tys.).
  - Film: https://www.youtube.com/watch?v=i3QxMqyRlks (75 787 wyświetleń; flaga `true`; w opisie „materiał sponsorowany”).
  - Cytat: „…odbierz do 20 darmowych akcji na start: https://freedom24.club/BadzNaBiezaco … Freedom, jest częścią Freedom Holding Corp.”
  - Freedom Finance Europe Ltd (Cypr) jest w wykazie notyfikacji KNF.
  - Kanał odkryły dwa zapytania promocyjne (#43 i #6) oraz zapytanie markowe „Freedom24” (#1).

### Kandydaci na uzasadnioną flagę: link lub kod firmy bez oznaczenia w opisie i bez flagi platformy

Kryterium: `firmEvidence` niepuste, brak frazy ujawnienia w opisie (linie kontaktowe pominięte), `paidPromotionFlag=false`, materiał po polsku. Takich filmów jest 16, ale skupiają się na kilku kanałach. Po ograniczeniu do 2 na kanał, z preferencją małych i średnich kanałów oraz firm transgranicznych, zostaje 6. Opis nie obejmuje mowy ani obrazu, więc to kandydaci do transkrypcji i kadrów przez C, a nie ustalenia.

| videoId | Kanał | Subskrybenci | Wyświetlenia | Flaga API | Firma | Cytat z opisu |
|---|---|---|---|---|---|---|
| `O5YmmKadQQw` | Krypto Królestwo | 990 | 64 | false | eToro (Europe) Ltd (transgraniczna) | „Link do rejestracji: https://tinyurl.com/WladcaEtoro eToro to wieloaktywowa platforma inwestycyjna…” |
| `AqXHkxDzSDI` | ForexMind | 416 | 22 | false | XTB S.A.; w oknie także Freedom24 | „🥇XTB: https://bit.ly/44BfO3V (Użyj kodu "TRADEXTB", aby uzyskać materiały edukacyjne) 🥈XM: https://bit.ly/4l0vliM” |
| `yIbtMnfP25Q` | Dywidendowy Inwestor | 8 350 | 5 100 | false | XTB S.A. | „✅Konto maklerskie, które polecam (XTB): https://link-pso.xtb.com/pso/WtGV9 … rejestrując się w XTB z kodem "DYWIDENDOWY"…” |
| `7M0rC6-Rueo` | Inwestycyjna wyprawa | 1 290 | 1 330 | false | XTB S.A.; Bank Pekao (konto, link afiliacyjny tmlead) | „✅Konto maklerskie (XTB) (z kodem " WYPRAWA "): https://link-pso.xtb.com/pso/7SA9k” |
| `OIyPE0z2mng` | Wojtek Smart | 3 550 | 1 223 | false | XTB S.A. (Short) | „🔹 XTB Tu zakładam konto inwestycyjne 👉 https://link-pso.xtb.com/pso/u0V2g Możesz inwestować nawet do 100 000 € bez prowizji…” |
| `ZJrT-X08Xwc` | Wojtek Smart | 3 550 | 1 219 | false | XTB S.A. (Short) | jak wyżej |

Wynik dodatkowy: 34 filmy z linkiem lub kodem firmy nie mają frazy ujawnienia w opisie, ale mają flagę platformy `paidPromotionFlag=true`, np. wszystkie filmy Cymcyka z Freedom24 i XTB. Wniosek z sondy z fali 1 („brak oznaczenia w opisie”) był więc niepełny: oznaczenie istnieje na poziomie platformy. D powinien traktować tę flagę jako ujawnienie (`coverage.modalities.platformFlags`).

### Incydent kwoty w testach H (przyczyna po stronie adaptera, naprawione)

Według Fable dwa przebiegi testów H zużyły ok. 2900 j. przez prawdziwe wywołania live tego adaptera. Przyczyny w adapterze:
- domyślny `key_source=load_key` był wiązany przy definicji klasy, więc `patch.object(youtube, "load_key")` nie działał;
- domyślny budżet wynosił 1500 j., gdy runner nie podał limitu.

Naprawa:
- klucz jest wyszukiwany przy wywołaniu;
- domyślny budżet wynosi 0;
- `fetch=None` oznacza `http_fetch` wyszukiwany przy wywołaniu;
- `collectors/test_youtube.py` ma w `setUp` każdej klasy twardą osłonę `collectors.youtube.urlopen` (AssertionError) i `load_key → None`;
- testy pokrywają osłonę, honorowanie podmienionego `load_key` i zerowy koszt przy domyślnym budżecie.

Dzienne zużycie: B 2088 + H ok. 2900 ≈ 4990 z 10 000. Bez kolejnego skanu live. Limit 8000 i rezerwa ≥ 2000 na odbiór pionu zostają zachowane.

### Przypadek błędu (fala 2)

Pierwsza próba ponownego odczytu przez cache spaliła 118 jednostek. `publishedAfter` zawierało sekundy bieżącego czasu, więc klucz cache search.list był inny w każdym przebiegu. Dodatkowo kontrola budżetu przed search.list nie uwzględniała trafień w cache. Przebieg wydał 100 j. na nowe zapytanie „XTB”, zatrzymał się na budżecie 200 z kursorem `XTB, page 2` i wzbogacił 50 wyników. Poprawka: okno z dokładnością do dnia, opcja `--published-after`, kontrola budżetu tylko dla żądań spoza cache. Po poprawce drugi odczyt kosztował 27 j.

## Fala 3: baza kanałów, budżet w dwóch fazach, wiele kluczy (2026-11-21, 20:30–20:50 UTC)

Wdrożone zasady 2–6, 8 i 9 z [MONITORING.md](../MONITORING.md) w `collectors/youtube.py`; zakres zapisu: `collectors/`, `fixtures/raw/discovery/youtube-api-2026-11-21b/`, `.runtime/kanaly-live/`.

### Zmiana Contextu (tylko pola addytywne z wartościami domyślnymi; v1 bez zmian)

`keys`, `key_daily_units` (10000), `state_dir`, `known_channels`, `monitor_share` (0,4), `monitor_channels` (200), `monitor_min_hours` (6), `sparse_after` (2), `sparse_every` (4), `min_yield` (0 = wyłączone), `yield_streak` (3). Wynik dostał klucze `cursor` (baza kanałów), `report` i `quota.keys`. Interfejs wywołania przez H (`_youtube` w `collectors/discovery.py`) działa bez zmian: baza kanałów wraca w `cursor`, który `store.record_adapter` zapisuje w `source_state` i oddaje w `ctx.state["cursor"]`.

### Domyślny zestaw zapytań (kolejność = malejąca wydajność, firmy na końcu)

Tematyczne: „inwestowanie” (2 strony), „giełda”, „ETF”, „akcje dywidendowe”, „obligacje skarbowe”, „IKE IKZE”, „jak zacząć inwestować” (dotychczasowe, pomiar 21 XI: 152 polskie kanały na 800 j.). Nowe, każda z uzasadnieniem:
- „pasywny dochód inwestowanie”: język finfluencerów i Shorts („dochód pasywny”, „z dywidend”), mało obecny w ogólnych frazach;
- „portfel inwestycyjny”: typowy tytuł filmów z pokazywaniem własnego portfela, często z linkiem do domu maklerskiego;
- „konto maklerskie”: fraza wprost z ścieżki rejestracji, trafia w filmy porównujące i polecające brokerów;
- „jak kupić akcje”: poradnik dla początkujących, zwykle z poleceniem konkretnego konta;
- „ETF na IKE”: łączy produkt i opakowanie podatkowe, wąska polska nisza z promocją kont IKE;
- „dywidendy”: krótka fraza używana w tytułach Shorts, szerszy zasięg niż „akcje dywidendowe”;
- „trading”: potoczne polskie słowo wprost, trafia w kanały daytradingowe i Shorts o zyskach;
- „kontrakty CFD”: produkt typowy dla promowanych brokerów z ostrzeżeniem o ryzyku w opisie.
Promocyjne bez zmian (4), krypto i analiza techniczna (5) po nich. Firmy tylko w polskim brzmieniu z kontekstem: „XTB opinie”, „konto maklerskie XTB”, „Freedom24 opinie”, „Saxo Bank opinie”, „mBank eMakler”. Usunięte: „eToro”, „Trading 212”, „Interactive Brokers”, „XTB” w gołej postaci.

### Zachowanie

- **Baza kanałów** (`state_dir/channels.json` albo `cursor`): etykieta języka po pierwszym odczycie (decyduje treść filmów; jedna obca próbka nie wystarcza do pominięcia, chyba że kanał deklaruje inny język), lista pominięć kanałów niepolskich (ich filmy z wyszukiwania są odrzucane przed `videos.list`), znacznik sygnału promocji firmy (link lub kod przy nazwie firmy w opisie), `lastRead`, `newest`.
- **Przebieg:** (1) monitoring znanych polskich kanałów: `playlistItems` 1 j./50 filmów, w kolejności z sygnałem promocji, potem reszta, w obrębie grupy najdawniej czytane najpierw, do `monitor_share` budżetu; kanał czytany krócej niż 6 h temu pomijany; nowe filmy to te nowsze niż zapisane `newest` i z okna 180 dni; (2) odkrywanie: strony wyszukiwania, po każdym zapytaniu tani odczyt jego filmów i nowych kanałów (stąd dokładna liczba nowych polskich kanałów na zapytanie); (3) listy przesłanych najlepszych nowych kanałów i Atom bez kwoty.
- **Rzadszy cykl:** zapytanie bez nowego polskiego kanału w dwóch kolejnych przebiegach z wydatkiem schodzi na co 4. przebieg (`queries[...].nextRun` w bazie). Powtórka z cache nie liczy się jako przebieg.
- **Przerwanie przy niskiej wydajności:** `min_yield` i `yield_streak`; kursor wznawia od następnego zapytania.
- **Cache:** okno dat do dnia, `search` ważny 24 h, `videos` 10 min, `channels` 1 h, `playlistItems` 30 min.
- **Wiele kluczy:** `INVESTWATCH_YT_KEY_FILES` (ścieżki po dwukropku, poza repo), domyślnie `~/.config/investwatch/youtube.key`. Kolejny klucz dopiero po `quotaExceeded` bieżącego, przerwane żądanie jest powtarzane. Wiersz księgi na klucz: skrót SHA-256 tekstu klucza obcięty do 8 znaków, `used` za dobę pacyficzną, `exhaustedAt`; zapis w `cursor.keyLedger`, `quota.keys` i `requests.jsonl` (pole `keyId`). Wartość klucza nigdzie się nie zapisuje.
- Sygnał promocji i etykieta to heurystyki opisu, nie kwalifikacja (decyduje D).

### Przebieg live (jedyny w tej fali; jedynie adapter, własna baza, bez mediów i bez skanu aplikacji)

Komenda: `python3 -m collectors.youtube --budget 2500 --raw-dir fixtures/raw/discovery/youtube-api-2026-11-21b --cache-dir .runtime/kanaly-live/cache --state-dir .runtime/kanaly-live --known-channels fixtures/raw/discovery/youtube-api-2026-11-21/channels-by-subscribers.json --seed-used 6120 --min-yield 2 --atom-channels 25 --monitor-channels 209`. Wejście: 380 kanałów (209 polskich, 171 niepolskich na liście pominięć od razu).

| Wynik | Wartość |
|---|---|
| zużyte jednostki | 1205 z limitu 2500 (monitoring 378, odkrywanie 811, listy przesłanych nowych kanałów i reszta 16); klucz `e97cae75`: 6120 (zgłoszone przez właściciela) + 1205 = 7325 z 10000, bez `quotaExceeded` |
| monitoring | 209 kanałów, w tym 51 z sygnałem promocji; 8415 nowych filmów z okna 180 dni; 0 błędów |
| odkrywanie | 7 zapytań tematycznych, 800 j. wyszukiwania; przerwane po „jak zacząć inwestować”: 3 kolejne zapytania poniżej 2 nowych polskich kanałów na 100 j.; kursor `queryIndex=7` („pasywny dochód inwestowanie”) |
| nowe polskie kanały na 100 j. | rodzina tematyczna 1,5 (12 na 800 j.): „inwestowanie” 4,0; „akcje dywidendowe” 3,0; „IKE IKZE” 1,0; „giełda”, „ETF”, „obligacje skarbowe”, „jak zacząć inwestować” 0. Rodziny promocyjna i firmowa nie doszły do głosu w tym przebiegu |
| baza kanałów | 221 polskich (209 wejściowych + 12 nowych), 177 pominiętych niepolskich (171 + 6), 59 z sygnałem promocji firmy |
| filmy | 8915 (3469 Shorts); czeka na transkrypcję 1340: 792 z dowodem relacji w opisie (link lub kod przy nazwie firmy), 548 z samą nazwą firmy (132 Shorts) |
| kandydaci | 66 filmów (11 Shorts): link lub kod firmy w opisie, bez oznaczenia w opisie, `paidPromotionFlag=false`, uporządkowane wg subskrybentów i wyświetleń: `candidates.json` |

Pliki: `fixtures/raw/discovery/youtube-api-2026-11-21b/` (surowe odpowiedzi z `key=REDACTED`, duże `videos` w `.gz`, `requests.jsonl`, `report.json`, `candidates.json`, `channels-db.json`), stan `.runtime/kanaly-live/` (`channels.json`, cache, `result.json`). Grep po całych katalogach i po rozpakowanych `.gz` nie znalazł wartości klucza.

### Zmiany po stronie integracji (H), nieujęte tu

1. Księga H (`quota_ledger`) ma jeden wiersz na źródło i dobę, a `record_adapter` po `quotaExceeded` ustawia `used=limit`. Przy dwóch kluczach to zablokuje drugi klucz: trzeba wiersza na `(source_id, keyId)` z `result["quota"]["keys"]`, a limit dobowy źródła liczyć jako suma limitów kluczy (dziś `INVESTWATCH_YT_DAILY_UNITS`=8000).
2. `store.source_state` musi nadal oddawać `cursor` w `ctx.state` (baza kanałów kilkaset wpisów, ok. 150 kB JSON na 400 kanałów); alternatywa: przekazać `options["youtube"]["state_dir"]` z rejestru.
3. Monitoring domyślnie bierze 40% budżetu przebiegu (H: 1200 j. z `run_units_default`) i czyta każdy znany polski kanał co najmniej co 6 h; przy 209 kanałach pierwszy przebieg kosztuje ok. 380 j., kolejne mniej. Jeśli H ma osobny budżet na monitoring, wystarczy `options["youtube"]["monitor_share"]`.
4. Skan z H przekazuje `known_creators` wszystkich platform; adapter bierze tylko `platform=youtube` z identyfikatorem `youtube:UC…`.

## Rekomendowana architektura `collectors/youtube.py` (z fali 1, wdrożona w fali 2)

- **Wejście:** `discover_youtube(mode, known, *, budget, fetch, clock, state)`. Tryby: `live` i `replay` (datowany katalog fiksturowy).
- **Kolejka odkrycia (API):** po każdej rotacji 3 rodzaje zapytań: marki i aliasy z rejestrów KNF (krajowe i transgraniczne), frazy promocyjne oraz neutralne tematy. Parametry: `type=video`, `relevanceLanguage=pl`, `regionCode=PL` (tylko zawężenie), `maxResults=50`, `publishedAfter` w oknie kroczącym. Wynik → `videos.list` (`snippet,statistics,contentDetails,status,paidProductPlacementDetails`, paczki po 50) → `channels.list` (`snippet,statistics,contentDetails`). Dla nowych kanałów w kolejności skanowania → `playlistItems.list` na playliście uploadów z `pageToken`.
- **Monitor (Atom):** darmowy, dla kanałów już przyjętych. Wykrywa nowe ID i zmianę opisu, a statystyki odświeża tanim `videos.list` (1 j./50 filmów).
- **Rekord Capture** (rozszerzenie Capture v1, wstecznie zgodne):
  - `id = youtube:<videoId>`, `creatorId = youtube:<channelId>`, `url` (oryginalny watch lub shorts), `author` i `channelTitle`;
  - `discovery[]: {method: data_api_search|atom|oembed|crosslink|ranking_import, query, queryKind, position, page, observedAt, sourceUrlRedacted, responseSha256}`;
  - `reach[]: {statistic: viewCount|likeCount|subscriberCount, value|null, hidden: bool, observedAt, source: data_api|atom}`;
  - `youtube{channelId, videoId, publishedAt, durationSec, isShort, defaultAudioLanguage, detectedLanguage, privacyStatus, paidPromotionFlag|null}`;
  - `scanPriority{rank, reason}`, np. „kanał 122 tys. subskrybentów, temat inwestycyjny, film 221 tys. wyświetleń w oknie 7 dni”.
- **Scalanie:** klucz materiału to `youtube:<videoId>`. Atom i API dopisują wpisy do `discovery[]`, więc powstaje jeden materiał z wieloma ścieżkami pochodzenia. Wersja treści zmienia się tylko przy zmianie hash(tytuł+opis). Zmiana samych statystyk dopisuje `reach[]` bez nowej wersji (sonda pokazała 21 zmian wyświetleń przy 0 zmianach opisu).
- **Budżet:** `INVESTWATCH_YT_DAILY_UNITS` (domyślnie 8000 z 10 000, zapas na ręczne próby). Licznik kosztów per metoda trwale w store, reset o północy czasu pacyficznego. Przy `quotaExceeded` (403): status źródła `limit`, `retryAt` = następny reset, kursor (zapytanie, `pageToken`) zapisany do wznowienia. Atom działa dalej.
- **Cache:** odpowiedzi API z kluczem ETag/sha i TTL 6 h dla search, statystyki co skan. Dane nieautoryzowane są odświeżane lub usuwane do 30 dni (Developer Policies).
- **Przypadki brzegowe:**
  - ukryte subskrypcje (`hiddenSubscriberCount`) dają `value=null, hidden=true`, a ranking używa wtedy wyświetleń w oknie;
  - Shorts: `/shorts/` w Atom albo `duration ≤ 180 s`, osobny koszyk rankingu;
  - remis: wyższe wyświetlenia w oknie, potem nowszy, potem `videoId`;
  - film usunięty lub prywatny: brak w `videos.list`, oEmbed 401/404 albo zniknięcie z Atom daje status `unavailable` z czasem, a ostatnia wersja zostaje;
  - błędny język: `defaultAudioLanguage` plus lokalny detektor na tytule i opisie; materiał nie-PL zostaje, ale z `outOfScope: language`;
  - pusta odpowiedź, prawdziwe zero i brak pola mają osobne stany.

## Next Step

1. H w S4 rejestruje `collectors.youtube.discover` w `collectors/discovery.py`. Wynik adaptera ma już kształt kontraktu; `status=rate_limited` + `resume` zapisuje do `source_state` (T16).
2. G porównuje `channels-by-subscribers.json` z niezależną listą Y. B tego porównania nie wykonuje.
3. Fable zleca C transkrypcję i kadry dla 6 kandydatów na flagę. B nie pobierał mediów.
4. Do uzgodnienia z D: flaga platformy jako ujawnienie oraz mapowanie `firmEvidence` na `adRelationship`.

Dzienna kwota po fali 2: ok. 5000 j. wolnych z 10 000; obowiązuje limit 8000 łącznie i rezerwa ≥ 2000. Rozliczenie dobowe zeruje się 2026-11-22 08:00 UTC. Pełny powtórny skan kosztuje ok. 1950 j. Odczyt samych statystyk z cache wyszukiwań kosztuje ok. 27 j.:

```sh
.runtime/venv/bin/python -B -m collectors.youtube --budget 60 --published-after 2026-05-25T19:03:44Z \
  --refresh videos --cache-dir <cache> --raw-dir <katalog> --out <wynik.json>
.runtime/venv/bin/python -B tools/youtube_probe.py report <wynik.json> --previous <poprzedni.json>
```

## Verification

- `python3 -m py_compile tools/youtube_probe.py`: ok.
- `python3 -B tools/youtube_probe.py keyless`: 34 żądania. 403 bez klucza zgodnie z oczekiwaniem. Ujawnił błąd resolvera.
- `python3 -B tools/youtube_probe.py keyless --skip-catalogs --tag rankings --handle …` (11 handle'i): 116 wierszy, 9 kanałów, 105 filmów, 3× 404.
- `… --tag confirm --video …` (3 kandydatów i 1 fałszywe ID): oEmbed 3× 200 i 1× 400. Ponowny Atom: 21/30 zmian wyświetleń, 15/15 identycznych opisów w każdym kanale.
- Fala 2: `.runtime/venv/bin/python -B -m unittest collectors.test_youtube`: 25 testów OK, z twardą osłoną sieci, w tym replay na `replay.json.gz`. Pokryte przypadki:
  - kolejna strona i ciągłość pozycji;
  - jeden materiał z kilkoma ścieżkami wyszukiwania;
  - duplikat Atom/API jako druga ścieżka;
  - playlista uploadów;
  - film usunięty lub prywatny;
  - błędny język, w tym `en-US` i `zxx` przy polskim tekście;
  - ukryte polubienia i subskrypcje;
  - Shorts z czasu trwania i linku Atom;
  - kolejność kanałów z powodem;
  - flaga płatnej promocji true/false/null;
  - zmiana samych statystyk (ten sam hash) i edycja opisu (nowy hash, to samo id);
  - 403 `quotaExceeded`: kursor, `retryAt`, opłacone nieudane żądanie, brak dalszych żądań, wznowienie od `PAGE2`;
  - twardy budżet;
  - brak klucza: `needs_key`, zero żądań;
  - trafienie w cache bez kosztu;
  - brak klucza w wyniku i w plikach surowych, odrzucenie pliku klucza w repo;
  - sygnały opisu: link firmy, kod, linia kontaktowa, własny link utm.
- Fala 2: `.runtime/venv/bin/python -B -m unittest discover -t . -s collectors -p 'test_*.py'`: 65 testów OK. `tests/core/test_contract_v2_*.py`: 85 OK, w tym 20 oczekiwanych porażek H.
- Fala 2, skan live: `python -B -m collectors.youtube --budget 2300 …`: `status=ok`, 1300 filmów, 380 kanałów, 1943 j. Drugi odczyt `--budget 60 --refresh videos`: 27 j., 1300/1300 bez zmiany treści, 289 zmian wyświetleń. `grep -F -f` na pliku klucza w surowych plikach i wynikach znalazł 0 plików.
- Nieuruchomione w tej fali: podpięcie do `discover()` i store (należy do H), testy `tests/core` po stronie H, porównanie z listą Y (należy do G), wznowienie po prawdziwym `quotaExceeded` na żywo (sprawdzone tylko offline).

## Fallback / Cut

Bez klucza: obecny monitor Atom dla znanych ID, oEmbed i crosslinki jako tropy oraz kanały z sondy jako oznaczony import (`discovery.method=ranking_import`) z datą i źródłem rankingu, poza benchmarkiem Y. Datowany replay z tego katalogu zapewnia ciągłość pokazu. Adapter ma się wyłączać jedną flagą bez wpływu na resztę `discover()`.

## Handoff

Sonda i fala 2: B (Claude Opus 5.5, high). Niezależnego przeglądu jeszcze nie było. Do przeglądu w fali 2: `collectors/youtube.py` (księga kwoty, wznowienie, brak klucza w wyniku) oraz heurystyka `description_signals` na kandydatach do flagi. Do sprawdzenia przez drugiego agenta: kandydaci (cytaty są w surowych plikach Atom `049-*.xml.gz` i `053-*.xml.gz`), brak sekretów w `requests.jsonl` oraz zgodność rekomendacji z kontraktem H. Katalogu `fixtures/validation/y-reference/` nie czytano.
