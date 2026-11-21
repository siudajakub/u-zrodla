# Linia K: pozostałe źródła (TikTok, Facebook, Instagram, Biblioteka Reklam Meta, UA i proxy)

Data: 2026-11-21. Gałąź hack/integration, praca niezacommitowana. Model: Sonnet 5.5. Zakres: `collectors/social.py`, `common.py`, `crosslinks.py`, testy, `fixtures/raw/discovery/social-2026-11-21/`.

## Wyniki prób live (bez logowania, przerwy 3,3 s, razem 19 żądań)

| Cel | Żądań | Kod | Wynik |
|---|---|---|---|
| TikTok embed: comparic.pl, kozaczek_pl, mr_pankracy, brokerchampionofficial, holi.inwestuje, inteligentny.portfel, kacper_snela, etoro_official | 8 | 200 | JSON w skrypcie osadzenia, 8–13 filmów, podpis i `playCount`; bez daty |
| TikTok oEmbed filmu comparic.pl | 1 | 200 | tylko iframe, bez podpisu |
| Facebook profil: comparicpl, etoro | 2 | 302 | przekierowanie na kanoniczny adres (ComparicPL, eToro) |
| Facebook profil kanoniczny: ComparicPL, eToro, brokerchampionofficial | 3 | 200 | metadane karty (np. ComparicPL: 71 277 obserwujących; eToro: 2 435 112), brak wpisów |
| Facebook oEmbed strony bez tokenu | 1 | 200 | fragment osadzenia `fb-page`, bez treści |
| Instagram profil: comparic.pl, brokerchampionofficial, gieldainwestycjetrading | 3 | 302 | `Location: /accounts/login/?next=…` |
| Instagram oEmbed posta (bez tokenu) | 1 | 400 | `OAuthException`, kod 24, podkod 2207045 |

Dwa 302 z facebook.com poprowadziły na kanoniczny adres tej samej strony (to nie ściana logowania), więc wykonano po jednym ponowieniu; brokerchampionofficial odpowiedział 200 od razu. Surowe odpowiedzi: `*.html.gz` i `*.gz`, dziennik żądań w `probe-1-requests.json` i `probe-2-requests.json` (czas, kod, wybrane nagłówki, SHA-256, User-Agent, trasa). Ciasteczka z odpowiedzi nie są zapisywane. Fikstura replay: `replay.json.gz`, odtwarzana z surowych odpowiedzi testem.

## TikTok

Profile pochodzą z opisów YouTube z `youtube-api-2026-11-21/replay.json.gz` (28 profili w odnośnikach). Do odczytu wybrano 8. Polskojęzyczne (filtr podpisów): comparic.pl (10 postów), holi.inwestuje (8), inteligentny.portfel (10), kacper_snela (13), kozaczek_pl (10), mr_pankracy (13): 64 posty. Pominięte jako niepolskie: brokerchampionofficial, etoro_official.

Posty z promocją firmy z rejestru (nazwa i znacznik współpracy), wszystkie @kacper_snela, podpis zaczyna się od „[współpraca z XTB]”:
- https://www.tiktok.com/@kacper_snela/video/7709883447644359969: „[współpraca z XTB] 🥇 Złoto fizyczne czy ETC na złoto? …”
- https://www.tiktok.com/@kacper_snela/video/7709141081027366176: „[współpraca z XTB] ✅ 5 oznak, że radzisz sobie finansowo lepiej …”
- https://www.tiktok.com/@kacper_snela/video/7708027934191193376
- https://www.tiktok.com/@kacper_snela/video/7708026713636146464
- https://www.tiktok.com/@kacper_snela/video/7707284619103718689

Ograniczenia: osadzenie pokazuje tylko ostatnie 8–13 filmów, nie ma dat publikacji (`publishedAt` null, szacunek z id w `publishedAtDerived`), mowy ani napisów, a reklama wyłącznie w obrazie lub mowie jest poza zakresem. Ocena „promocja” to reguła tekstowa (firma z `analysis/firm-index.json` plus znacznik), nie kwalifikacja.

## Facebook i Instagram

Status źródła `access_blocked` z `lastError {code, message, at, nextStep}` i datowaną próbą w `probe`. Ścieżka dostępu: Meta Content Library i Content Library API (Research Tools Manager, instytucja badawcza, publiczne treści FB i IG, bez opłat); alternatywa Graph API z Page Public Content Access po przeglądzie aplikacji. Art. 40 DSA jest podstawą wniosku badawczego, nie dowodem uprawnienia organu. Nie sprawdzono, czy UKNF kwalifikuje się jako instytucja w rozumieniu programu; to decyzja J.

## User-Agent i proxy

Wdrożone w `collectors/common.py` (`Identity`, `open_url`, `safe_get`): pula UA ze zmiennej lub pliku, UA stały per host w sesji, opcjonalne proxy z rotacją i pominięciem niedziałającego, loopback zawsze bezpośrednio, brak cichego łącza bezpośredniego przy martwych proxy, lokalny backoff po 403/429/503 bez zmiany tożsamości. `collectors/audio.py` i `tools/watch_sources.py` nadal mają stały UA (poza zakresem K). yt-dlp bez zmian.

## Crosslinks

`ChannelMetadata` czyta teraz elementy `meta` i `link` niezależnie od położenia względem `</head>`. Test rozstrzygający: `023-profile-etoro.html.gz` daje UCaQbkbbr35GXYsJTjeI-Ahg; identyfikatory ze skryptów i linków `a` nadal są ignorowane.

## Testy

`.runtime/venv/bin/python -B -m unittest discover -s collectors -t . -p 'test_*.py'`: 110 testów OK (nowe: 15 w `test_common.py`, 9 w `test_social.py`, 2 w `test_crosslinks.py`). Żaden nie wychodzi do sieci (proxy i serwery to gniazda 127.0.0.1). Nie uruchomiono pełnej bramki `hack_ready.sh`.

## Do wpięcia przez H (`collectors/discovery.py`)

```python
from .social import discover_facebook, discover_instagram, discover_tiktok, build_replay

register(Adapter("tiktok", discover_tiktok, "TikTok · profile z odnośników", after=("youtube",),
                 enabled=_on_unless_listed("tiktok"), run_units_default=8))
register(Adapter("facebook", discover_facebook, "Facebook · wpisy organiczne", enabled=_on_unless_listed("facebook")))
register(Adapter("instagram", discover_instagram, "Instagram · dostęp do wpisów", enabled=_on_unless_listed("instagram")))
```
Adapter `tiktok` używa `ctx.captures` (potrzebny etap YouTube) i `ctx.previous` (kraj i język źródeł); `ctx.fetch` ma sygnaturę `fetch(url, allowed_hosts)`, jak `common.safe_get`. W `collectors/adapter.py` status `access_blocked` mapuje się dziś na zdrowie „ok”: trzeba dodać go do `ERROR_STATUSES` (albo osobny stan), inaczej pulpit nie pokaże blokady. Replay: `build_replay()` lub plik `fixtures/raw/discovery/social-2026-11-21/replay.json.gz` (pola `mode: "replay"` ustawione). Tryb `own_network` dla `tiktok` nie jest potrzebny, bo korzysta z `ctx.fetch`.

## Otwarte

Pozyskanie dostępu Meta (decyzja J), jedno źródło TikTok to profile tylko z odnośników YouTube, brak dat publikacji, `audio.py` bez rotacji UA.

## Etap 2: reklamy FB i IG przez Bibliotekę Reklam Meta

**Próba bez tokenu (2 żądania, 21 XI 2026, `probe-3-requests.json`):**
- `https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=PL&q=XTB` → HTTP 403, 481 B, strona „Ad Library” z wyzwaniem JavaScript (`/__rd_verify…`). Zwykłe żądanie HTTP nie dostaje danych; droga bez tokenu i bez przeglądarki nie istnieje. Nie obchodzimy wyzwania.
- `https://graph.facebook.com/v19.0/ads_archive?...` bez tokenu → HTTP 500, `OAuthException` kod 1 (nie 190). Dane tylko z tokenem.

**Wymagania (dokumentacja Meta; co potwierdzone, a co nie):**
- Potwierdzone w referencji Graph API (`ads_archive`, `ArchivedAd`): parametry `ad_reached_countries`, `ad_type` (`ALL`, `FINANCIAL_PRODUCTS_AND_SERVICES_ADS`, …), `search_terms` (do 100 znaków, bez tłumaczenia, wpisywać po polsku), `search_type`, `search_page_ids` (do 10), `ad_active_status` (`ACTIVE` domyślnie, `ALL`, `INACTIVE`), `ad_delivery_date_min/max`, `languages`, `publisher_platforms`; błędy: 190 zły token, 613 limit, 100 zły parametr, 1009 walidacja. Pola dla wszystkich reklam: `id`, `ad_creation_time`, `ad_creative_bodies`, `…_link_titles/captions/descriptions`, `ad_delivery_start_time/stop_time`, `ad_snapshot_url`, `languages`, `page_id`, `page_name`, `publisher_platforms`, `total_reach_by_location`. Tylko reklamy w UE (UK): `eu_total_reach`, `beneficiary_payers` (tylko UE), `target_ages`, `target_gender`, `target_locations`, `age_country_gender_reach_breakdown`. Wydatki, wyświetlenia, `bylines` dotyczą tylko reklam politycznych i społecznych.
- Niepotwierdzone w oficjalnych stronach (facebook.com/ads/library/api zwróciło 403, transparency.meta.com nie oddało treści): dokładna lista warunków dostępu. Źródła wtórne zgadzają się, że potrzebne jest konto osobiste z potwierdzoną tożsamością (dokument i kraj zamieszkania, SMS) i token użytkownika z aplikacji deweloperskiej; zatwierdzenie zwykle 1–3 dni robocze, do tego czasu zapytania zwracają błąd o wymaganej weryfikacji. Nie potwierdzono limitów liczbowych (dokumentacja podaje tylko kod 613) ani tego, czy wystarcza token aplikacji; zakładamy token użytkownika.
- Zasięg: że API obejmuje wszystkie reklamy komercyjne wyświetlane w UE wynika z opisu pól (`eu_total_reach`, `beneficiary_payers` dla reklam w UE), ale referencja mówi też, że reklamy bez zasięgu w UE zwracane są tylko gdy są polityczne. Zakres zweryfikuje pierwszy odczyt z tokenem.

**Kroki dla właściciela:**
1. Na koncie osobistym Facebooka wejść na facebook.com/ID (Centrum tożsamości), potwierdzić tożsamość (dokument ze zdjęciem, kraj zamieszkania, SMS). Czekać na zatwierdzenie (zwykle 1–3 dni robocze).
2. Wejść na facebook.com/ads/library/api i zaakceptować warunki Ad Library API dla tego konta.
3. Na developers.facebook.com założyć konto deweloperskie (to samo konto) i utworzyć aplikację (typ „Inne”/„Business”, nazwa dowolna).
4. W Graph API Explorer (developers.facebook.com/tools/explorer) wybrać aplikację, „Get User Access Token”, bez dodatkowych uprawnień, kliknąć „Generate Access Token”.
5. Rozszerzyć token do długożyjącego (ok. 60 dni): w Access Token Debugger (developers.facebook.com/tools/debug/accesstoken) „Extend Access Token”, albo wywołać `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=KRÓTKI_TOKEN`.
6. Zapisać token: `mkdir -p ~/.config/investwatch && umask 077 && printf '%s' 'TOKEN' > ~/.config/investwatch/meta.token && chmod 600 ~/.config/investwatch/meta.token`. Plik leży poza repo; adapter ostrzega, gdy tryb jest szerszy niż 600.
7. Test: `curl -s "https://graph.facebook.com/v21.0/ads_archive?ad_type=ALL&ad_reached_countries=%5B%22PL%22%5D&search_terms=XTB&fields=id,page_name&limit=1&access_token=$(cat ~/.config/investwatch/meta.token)"`. Kod 190 oznacza wygasły lub zły token; komunikat o weryfikacji tożsamości oznacza, że krok 1 jeszcze nie został zatwierdzony.
8. Odnowienie: długożyjący token wygasa po ok. 60 dniach; adapter zgłosi wtedy status `error` z kodem `oauth_190` i krokiem naprawczym. Powtórzyć kroki 4-6.
Dostęp dla organu nadzoru jako instytucji (Meta Content Library) to osobna ścieżka dla wpisów organicznych, opisana wyżej.

**Zaimplementowano:** `collectors/meta_ads.py` (adapter `discover(ctx)`), 10 testów w `collectors/test_meta_ads.py`. Zapytania: marki z `firm-index.json` (16) i 8 fraz polskich; do 2 stron po 50; budżet żądań z `ctx.budget` (domyślnie 30), pauza 1 s; pamięć podręczna 12 h i kursor w `resume`; brak tokenu → `needs_key` z nextStep; 190 → `error` (`oauth_190`); 613, 4, 17, 32, 80004 → `rate_limited` z `retryAt` +1 h i kursorem. Capture: id `facebook:ad-<id>` lub `instagram:ad-<id>` (platforma wg `publisher_platforms`, Facebook ma pierwszeństwo), twórca `facebook:page-<page_id>`, treść = treść + tytuł + opis + podpis linku, `publishedAt` = start emisji, `reach.metrics.euTotalReach`, `beneficiaryPayers`, `targeting`, `firmRelation {firm, role: advertiser|payer|beneficiary|mentioned, quote}`, `module` M2 dla reklamodawcy z rejestru i M1 w pozostałych przypadkach, `discovery[]` metody `ad_library` (query, rank, page). Pole `url` to publiczny link biblioteki `…/ads/library/?id=<id>`; `ad_snapshot_url` zapisany jest bez tokenu w `adSnapshotUrl`, bo oryginalny adres zawiera token.
Wiersze stanu: `meta_ads` (podsumowanie z listą zapytań), `facebook-ads`, `instagram-ads` (reklamy) i `facebook`, `instagram` (wpisy organiczne: `access_blocked`).
**Nie sprawdzono z prawdziwym tokenem:** kształt odpowiedzi to testy na odpowiedziach zgodnych z referencją, nie z żywym API. Pierwszy odczyt z tokenem może ujawnić różnice (np. `target_locations`, daty w innym formacie).

**Do wpięcia przez H:**
```python
from .meta_ads import discover as discover_meta_ads
register(Adapter("meta_ads", discover_meta_ads, "Meta · Biblioteka Reklam (FB i IG)", enabled=_on_unless_listed("meta_ads"),
                 run_units_env="INVESTWATCH_META_RUN_REQUESTS", run_units_default=30,
                 daily_units_env="INVESTWATCH_META_DAILY_REQUESTS", daily_units_default=300, own_network=True))
```
`own_network=True`, bo adapter używa własnego transportu (`open_url`, odpowiedzi błędów Graph API); `ctx.fetch` nie jest używany. W `adapter.py` `ERROR_STATUSES` powinno zawierać `access_blocked` i `needs_key` (to drugie już jest obsługiwane), a `partial` jest już błędem.

## Import ręczny z Meta (21 XI 2026, wieczór)

Model: Sonnet 5.5. Bez żadnego żądania do facebook.com, instagram.com i graph.facebook.com oraz bez przeglądarki: pracowano na plikach zapisanych wcześniej w `fixtures/raw/discovery/social-2026-11-21/alt/` (opis: `2026-11-21-fable-meta-alternatywy.md`).

**Zaimplementowano:** `collectors/meta_import.py` (parser, CLI `python -m collectors.meta_import <plik lub katalog> --out replay.json[.gz]`, adapter `meta_import`), `collectors/test_meta_import.py` (23 testy), fikstura `replay-meta.json.gz` i `manifest-meta.json` (SHA-256 plików źródłowych). Rozpoznawane pliki: (a) strona wyników Biblioteki Reklam (HTML „Zapisz stronę jako…” albo skopiowany tekst; interfejs polski i angielski), (b) osadzenie profilu IG `/<konto>/embed/`, (c) osadzenie pojedynczego posta IG. Czego plik nie zawiera, to `null` i wpis w `importMissing` („brak danych w zapisanym pliku”), nigdy zgadywanie.

**Kształt capture** jak w `meta_ads`: `facebook:ad-<id>` / `instagram:ad-<id>` (instagram tylko, gdy w pliku są nazwy platform i nie ma facebook), twórca `facebook:page-name-<slug>` (w tekście nie ma identyfikatora strony, więc po późniejszym odczycie API ta sama strona dostanie drugi rekord twórcy), `firmRelation` z `relate()`, moduł M2 gdy reklamodawcą jest firma z rejestru, M1 dla stron trzecich (wzmianka daje `firmRelation.role = "mentioned"`), `materialType`/`provenance.scope = meta_ad_library_text`, `coverage.scope = ad_text` (tylko tekst). Pola reklamy: `adStatus`, `adDeliveryStartDate/StopDate`, `publishedAt` (dzień, `publishedAtPrecision: "day"`), `adBody`, `adTitle`, `adDescription`, `linkDomain`, `callToAction`, `hasVideo`, `versionsCount`, `multipleVersions`, `euTransparencyShown`, `publisherPlatforms` (tylko nazwy z pliku) i `publisherPlatformIcons` (liczba ikon w tekście). Posty IG: `instagram:<kod>`, twórca `instagram:<konto>`, `isPaidPartnership` (`null`, gdy pliku nie ma flagi), `reach.metrics.likeCount`, `firm_signals`, scope `instagram_embed_caption`; konto firmy z rejestru daje M2 (`firmRelation.role = "author"`, `basis = "nazwa konta"`, do potwierdzenia przez analityka).

**Ścieżka i pochodzenie:** `discovery[] = {method: "manual_import", adapter: "meta_import", sourceFile, savedAt, importedAt, responseSha256, import: true}`; `provenance` dostaje `sourceFile`, `sourceFileSha256`, `savedAt`, `importedAt`, `import: true`, `importKind`, `parser`. `savedAt` to czas modyfikacji pliku (w fiksturze stałe wartości z dnia zapisu). `origin`: w replay `mode: "replay"` ustawia adapter; w live import niesie `mode: "live"` z runnera i `importLabel: "import ręczny"`, bo prawdziwe dane analityka mają trafić do kolejki M2 (platforma `upload` i `mode: "upload"` wyłączają rekord z kolejek rzeczywistych według `derive_origin`, więc nie użyto ich). Do decyzji H, jeśli import ma mieć własne `origin`.

### Wynik na istniejących plikach (`alt/`)

| Plik | Rozpoznano jako | Wynik |
|---|---|---|
| `metaadlib-browser-body.txt` | Biblioteka Reklam (PL), ok. 14 000 wyników na stronie | 22 reklamy, wszystkie M2 (reklamodawca „XTB Online Investing” i „XTB Online Trading”) |
| `ig-profile-embed.html` | osadzenie profilu `xtb_polska` (44 764 obserwujących) | 6 postów, M2, flaga płatnego partnerstwa `false` we wszystkich |
| `ig-profile-embed-etoro.html` | osadzenie profilu `etoro` (konto „Eugenio Toro”, 0 postów) | 0, status `empty` |
| `ig-profile-embed-trading212_pl.html` | pusty szkielet (`contextJSON: null`) | 0, status `empty`, „brak danych w zapisanym pliku” |
| `ig-embed-captioned.html` | pojedynczy post (konto google, wpis przykładowy badacza) | 1 post, M1, bez daty i flagi (w teście, poza fiksturą) |
| `fb-page-plugin.html`, `firm-xtb.html` | nierozpoznane | `unrecognized`, nic nie wczytano |

Fikstura `replay-meta.json.gz`: 28 captures (22 reklamy + 6 postów), 3 twórców. W tekście Biblioteki platformy są ikonami bez nazw (3 do 5 ikon na kartę), więc `publisherPlatforms` jest puste, ID reklam ma przedrostek `facebook:` (jak w `meta_ads` bez nazwy platformy), a `instagram-ads` pokazuje 0 z adnotacją. Nazwy platform zostaną odczytane, gdy zapisany HTML ma `alt`, `aria-label` lub `title` z nazwą (obsłużone, przetestowane na spreparowanym HTML, nie na prawdziwej stronie).

Przykłady:
1. Reklama 1421543096020676, reklamodawca „XTB Online Investing”, 18 wrz 2025 – 1 wrz 2026 (nieaktywna), 3 ikony platform bez nazw, 12 reklam z tym materiałem, domena xtb.pl, CTA „Sign Up”. Treść: „Nie tylko zarabiaj pieniądze. Zacznij inwestować w akcje i ETF-y z 0% prowizji”.
2. Reklama 846978505145299, „XTB Online Investing”, aktywna od 8 paź 2026 (bez daty końca), xtb.com, CTA „Learn More”. Treść: „Pieniądze są tylko narzędziem. Ty decydujesz, czy będą pracować dla Ciebie.”
3. Post `instagram:DfrQqayEanl` (xtb_polska), 20 XI 2026 14:00 UTC, 22 polubienia, `is_paid_partnership: false`. Podpis: „Czy Super El Niño może wywołać kolejne wzrosty cen surowców rolnych?”

### Cytaty z próbki (bez oceny)

Reklamy z twierdzeniem o korzyściach lub zysku (ostrzeżenie o ryzyku w zapisanym tekście: brak we wszystkich 22; Biblioteka pokazuje tekst reklamy, nie obraz ani stopkę wideo):
- 1421543096020676, 1859210128043429 (18 wrz 2025 i 1 lis 2025): „Nie tylko zarabiaj pieniądze. Zacznij inwestować w akcje i ETF-y z 0% prowizji”; nagłówek „Inwestuj w akcje i ETF-y bez prowizji”.
- 1150549887287116 (3 lis 2025 – 2 lut 2026): „W XTB nawet gdy czekasz na okazję inwestycyjną, Twoje pieniądze mogą pracować i zarabiać odsetki. 🇵🇱 4.1% 🇺🇸 3.9% 🇪🇺 2.3%”; nagłówek „Zyskaj na swoich wolnych środkach”.
- 844397757965187, 1502625730954011 (29 paź 2025 – 21 maj 2026): „Pieniądze. Ciężko na nie pracujesz, ale czy one pracują dla Ciebie❓ … A więc nie tylko zarabiaj pieniądze, ale kontroluj je i pozwól im pracować”.
- 1885061166227236, 1313279843868269, 686329227418607: „Odkryj tysiące sposobów, by Twoje pieniądze pracowały w XTB”.
- 3997163377260894, 691976580310888, 541892802207347, 1424173491814994: „W XTB Twoje pieniądze pracują na wiele sposobów”.
- 846978505145299, 1069448859458332, 1437269528586761, 1050466267828086 (od 1 paź 2026): „Pieniądze są tylko narzędziem. Ty decydujesz, czy będą pracować dla Ciebie.”
- 3966215633674503 (11 sie – 14 paź 2026): „… Zyskaj dostęp do materiałów edukacyjnych i korzystaj ze wsparcia 24/5.”

Posty IG z flagą płatnego partnerstwa: 0 z 6 (`is_paid_partnership: false` w każdym). Wpis z ostrzeżeniem o ryzyku w podpisie: tylko `DfrQqayEanl`: „*79% rachunków inwestorów detalicznych odnotowuje straty pieniężne w wyniku handlu kontraktami CFD u niniejszego dostawcy. Zastanów się, czy możesz pozwolić sobie na wysokie ryzyko utraty twoich pieniędzy.” Wpis `Dfy_1kbTqY8` (17 XI): „Pozwól swoim pieniądzom pracować z XTB i bądź z tego dumny!”, bez ostrzeżenia w podpisie. Kwalifikacja należy do analityka.

### Instrukcja dla analityka: strona Biblioteki Reklam Meta do systemu

1. We własnej przeglądarce (zwykłe okno, bez automatyzacji) otwórz https://www.facebook.com/ads/library/ . Kraj: Polska, „Wszystkie reklamy”, wpisz nazwę firmy (np. XTB) w polu wyszukiwania i zatwierdź. Jeśli pojawi się baner cookies, zamknij go zwykłym przyciskiem.
2. Przewiń kilka ekranów w dół, aż na liście będzie tyle reklam, ile chcesz zachować (każda karta ma „Identyfikator biblioteki”). Nie klikaj „Zaloguj się”.
3. Zapisz: wariant A, Ctrl+S, „Strona internetowa, tylko HTML” albo „kompletna”; wariant B (pewniejszy): Ctrl+A, Ctrl+C, wklej do Notatnika i zapisz jako `xtb-2026-11-21.txt` (UTF-8). Nazwa pliku powinna mieć firmę i datę. Wariant B zachowuje ten sam tekst co pliki w `alt/`.
4. Wgraj plik: skopiuj go do katalogu importu (`INVESTWATCH_META_IMPORT_DIR`, domyślnie `.runtime/demo/meta-import/`) i uruchom skan źródła `meta_import` (w pulpicie: skan z listą adapterów `["meta_import"]`, albo z terminala `python -m collectors.meta_import <plik> --out /tmp/x.json`, żeby sprawdzić, ile reklam rozpoznano). Z terminala komenda wypisuje dla każdego pliku rodzaj i liczbę wpisów.
5. Reklamy firmy z rejestru pojawią się w kolejce M2 z etykietą „import ręczny” i ścieżką „import ręczny: <plik>, zapisano <data>”. Plik niewgrywalny (np. strona logowania) daje status `unrecognized` w wierszu źródła z komunikatem, bez błędu skanu.
6. Profil Instagrama: otwórz w przeglądarce `https://www.instagram.com/<konto>/embed/`, zapisz stronę (Ctrl+S, HTML) i wgraj tak samo. Widoczne jest 6 ostatnich postów. Rozpoznawane są też `/p/<kod>/embed/captioned/`.

Dziś w API nie ma endpointu na pliki HTML: `POST /v1/media` przyjmuje tylko audio i wideo (rozszerzenia mp4, wav, mp3 i podobne), a `POST /v1/evidence` dodaje transkrypcję do istniejącej sprawy. Przycisk „Dodaj dowód” w pulpicie nie przyjmie więc strony Meta bez zmiany w `api/`.

### Do wpięcia przez H / integrację (nie edytowano `api/` ani `discovery.py`)

```python
# collectors/discovery.py, obok meta_ads
from .meta_import import discover as discover_meta_import, SAMPLE_REPLAY as META_IMPORT_SAMPLE
register(Adapter("meta_import", discover_meta_import, "Meta · import ręczny (FB i IG)", modes=("live", "replay"),
                 enabled=_on_unless_listed("meta_import")))
```
Adapter nie używa sieci (`own_network=False`). W trybie replay zwraca `replay-meta.json.gz`, w live czyta katalog importu. Wiersze źródeł: `facebook-ads`, `instagram-ads` i `instagram` (id wspólne z `meta_ads` i adapterem `instagram`): przy równoległym działaniu `meta_ads` bez tokenu (`needs_key`) i `meta_import` runner musi zdecydować, który wiersz wygrywa; zalecenie: dla tych trzech id wygrywa wiersz o statusie `ok`, a `meta_ads` zostaje widoczny jako `meta_ads`. Wiersz `facebook` zostaje `access_blocked` z `nextStep` „Ad Library API po uzyskaniu tokenu (adapter meta_ads gotowy) / Meta Content Library”.

Opcjonalny endpoint wgrywania (fragment dla `api/server.py`, wzór: `POST /v1/media`):
```python
@app.post("/v1/import/meta", status_code=202)
async def import_meta(request: Request, filename: str = Query("meta.txt", max_length=200)):
    ext = Path(filename).suffix.lower()
    if ext not in {".html", ".htm", ".txt"}:
        raise HTTPException(415, "Wybierz zapisaną stronę (.html lub .txt).")
    body = await request.body()
    if not body or len(body) > 25 * 1024 * 1024:
        raise HTTPException(422, "Plik jest pusty albo większy niż 25 MiB.")
    folder = store.STATE / "meta-import"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = sha256(body).hexdigest()[:16] + "-" + re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:80]
    (folder / name).write_bytes(body)
    return jobs.submit("live", "meta-import-" + sha256(body).hexdigest(), {"adapters": ["meta_import"]})
```
(sprawdzić, czy `jobs.submit("live", …)` z `adapters` obsługuje adapter spoza domyślnej listy; nazwa pliku w `provenance.sourceFile` to wtedy `<skrót>-<nazwa>`.)

### Testy

`.runtime/venv/bin/python -B -m unittest discover -s collectors -t . -p 'test_*.py'`: 156 testów OK (23 nowe w `test_meta_import.py`; poprzednio 133). Pokrycie: pełna próbka z `alt/`, wersja angielska, reklama tylko na IG, brak dat, ta sama strona jako HTML ze skryptami i z rozdzielonymi etykietami, ikona z nazwą platformy, duplikat karty, flaga płatnego partnerstwa `true` i brak flagi, profil bez postów, pusty szkielet, pojedynczy post, plik nierozpoznany lub nieistniejący, adapter live (katalog) i replay, zgodność fikstury z parserem i skrótów w manifeście, CLI (json i gz). `tests/core/test_contract_v2_social.py`: 48 OK. Fikstura `replay.json.gz` odbudowana (zmienił się tylko `nextStep` wierszy `facebook` i `instagram`).

### Ograniczenia

- Parser Biblioteki Reklam opiera się na układzie tekstu z 21 XI 2026 (polski i angielski); zapis HTML z przeglądarki nie był na prawdziwej stronie testowany (dowód: wariant syntetyczny z `div` i `span`). Wariant tekstowy jest pewniejszy.
- Karty bez domeny i bez wideo nie rozdzielają treści, tytułu i opisu (`importLayoutNote`); całość jest w treści.
- Platformy, identyfikator strony reklamodawcy, zasięg w UE, płatnik i targetowanie nie występują w tekście karty: `null` / `not_collected`.
- Dane z jednego widoku (22 z ok. 14 000 wyników). To próbka, nie pokrycie kampanii.
- Import ręczny z przeglądarki analityka mieści się w jego własnym użyciu publicznej strony, ale warunki Meta kierują odczyt maszynowy do API; decyzja o pokazaniu tych danych jury należy do J.

## Próbka FB, IG i reklam przez usługę zewnętrzną (ScrapeCreators), 21 XI 2026, wieczór

Model: Sonnet 5.5. Zakres: `collectors/vendor_social.py`, `collectors/test_vendor_social.py`, `fixtures/raw/discovery/social-2026-11-21/vendor/`. Dane zebrała **usługa ScrapeCreators**, nie nasz host: wołano wyłącznie `api.scrapecreators.com` (klucz w nagłówku `x-api-key`, z pliku `~/.config/investwatch/scrapecreators.token`, tryb 600, poza repo). Żadnego żądania do facebook.com, instagram.com i graph.facebook.com. Apify nie użyto.

**Ryzyko regulaminowe (wprost).** Automatyczny odczyt publicznych treści Meta wykonuje dostawca. Meta uznaje automatyczne zbieranie danych za sprzeczne z warunkami platformy; ryzyko leży po stronie dostawcy (blokada usługi) i decyzji o jej użyciu. Wyrok z sprawy Meta v. Bright Data (N.D. Cal. 2024) dotyczył odczytu bez logowania, jest rozstrzygnięciem sądu pierwszej instancji w USA i nie wiąże w Polsce. To jednorazowa, datowana próbka do pokazu. Produkt nie zależy od tej usługi: adapter `vendor-social-replay` czyta tylko zapisaną próbkę i nie ma ścieżki do klucza ani do sieci (test `test_adapter_reads_only_the_sample_and_never_the_network`). Odczyt cykliczny w produkcie to import ręczny lub oficjalne API po uzyskaniu dostępu.

### Przebieg i kredyty

100 darmowych kredytów, 1 kredyt = 1 zapytanie; **zero zakupów**. Zużyto 74, **zostało 26** (rezerwa 15 nienaruszona; plan do 85 nie został wykorzystany do końca). Licznik: `requests.json` (każde żądanie: czas, punkt końcowy, parametry, kod, kredyty naliczone i pozostałe, SHA-256 odpowiedzi, plik; nagłówek `x-api-key: REDACTED`). Saldo czytane z pola `credits_remaining` każdej odpowiedzi (osobnego wywołania salda nie robiono, jego strona dokumentacji nie dała kształtu odpowiedzi). Odstęp między wywołaniami 2,2 s.

| Operacja (punkt końcowy) | Zapytań | Kredytów | Uwagi |
|---|---|---|---|
| `GET /v1/instagram/profile` (profil + 12 ostatnich postów, obserwujący) | 31 | 31 | próba kształtu: `xtb_polska` (1 kredyt, curl); 5 kont firm, 26 twórców |
| `GET /v1/facebook/adLibrary/search/companies` | 8 | 8 | ustalenie strony, `page_alias` i `ig_username` firmy; trafiono XTB, Trading 212, eToro, Lightyear, Saxo; mBank, DM BOŚ i Freedom24 bez właściwej strony |
| `GET /v1/facebook/adLibrary/company/ads` (`country=PL`, `status=ALL`) | 13 | 5 (+1 ponowione) | 30 reklam na stronę; XTB, eToro, Saxo; Trading 212, Lightyear i trzy zapytania po nazwie zwróciły 0 reklam w PL (zapytania z 0 wynikami nie kosztowały); kursor XTB strona 2: HTTP 500 „Facebook is blocking us” (2 próby, bez kosztu) |
| `GET /v1/facebook/profile/posts` | 16 | 15 | 3 wpisy na stronę; parametr `pageId` zwracał 0 wpisów (5 prób, bez kosztu), działa `url` strony |
| `GET /v1/facebook/adLibrary/search/ads` | 7 | 7 | reklamy stron trzecich: XTB, Trading 212, eToro, Freedom24, „kod promocyjny XTB”, „kod polecający broker”, Lightyear |
| `GET /v1/facebook/adLibrary/ad` (szczegóły: zasięg w UE, płatnik, targetowanie) | 7 | 7 | 5 reklam firm i 2 reklamy stron trzecich |

Pierwsza odpowiedź reklam XTB została ponowiona (1 kredyt), bo filtr zapisu usunął wtedy pole `cards` z treścią reklam dynamicznych (`DCO`, w `snapshot.body.text` stoi szablon `{{product.brand}}`). Filtr poprawiono; odpowiedź zastąpioną usunięto z repo, w `requests.json` zostało `superseded`. Zapytanie „Lightyear” w wyszukiwaniu reklam zwróciło reklamy o filmie Toy Story (Buzz Lightyear): oznaczone `discard`, odpowiedź zachowana w `raw/`, poza replayem. Z wyszukiwania słów kluczowych zostają tylko reklamy, które nazywają firmę z rejestru (`firmRelation`).

### Co zawiera próbka (replay `replay-vendor.json.gz`, 494 materiały)

- **Instagram:** 31 kont (5 firm z rejestru: xtb_polska, trading212, etoro_official, golightyear, saxobank; 26 twórców znalezionych w odnośnikach opisów YouTube), 350 postów (60 z kont firm, 290 twórców), od 15 IV 2021 do 21 XI 2026. Flaga `is_paid_partnership`: `true` w 13 postach (12 konto Oskara Bednarskiego, 1 konto Trading 212 ze współautorem `the.independent`), `false` w 337.
- **Facebook:** 10 stron (4 firmy: XTB Online Investing, eToro, Lightyear, Saxo Bank; 6 twórców/mediów z opisów YouTube), 30 wpisów po 3 na stronę. Trading 212 pod aliasem `Trading212` i część stron nie dały wpisów w odpowiedzi.
- **Reklamy w PL (Biblioteka Reklam):** 114 reklam, 7 reklamodawców: eToro 40, Saxo Bank 40, XTB Online Investing 30, XTB Online Trading 1 (razem 111, moduł M2, 102 nieaktywne i 9 aktywnych) oraz 3 reklamy stron trzecich z firmą z rejestru (M1). Szczegóły z zasięgiem w UE, płatnikiem i targetowaniem dla 7 reklam. Brak reklam w PL dla Trading 212 i Lightyear (0 wyników).
- **Firmy z materiałem w próbce:** XTB, eToro, Saxo, Trading 212, Lightyear (konta firm), plus wzmianki w postach twórców o BOŚ (bossa), mBank, PKO BP, Alior, Freedom24. Moduł: **M2 = 183** (konta i strony firm, reklamy firm), **M1 = 311**.
- Zakres: tylko tekst (podpisy, treść reklam), liczby (polubienia, komentarze, odtworzenia, reakcje, udostępnienia; z datą odczytu) i flaga platformy. Obrazu, wideo, mowy i napisów w grafice nie zbadano. Z odpowiedzi usunięto komentarze użytkowników, listy obserwujących, podpisane adresy mediów i zdjęć profilowych; oznaczone konta sprowadzono do publicznej nazwy konta. Surowe odpowiedzi (796 KB razem z replayem) są w repo.

### Wskazania w próbce (cytaty, bez oceny prawnej)

Twórcy z promocją firmy z rejestru, **z oznaczeniem** (flaga platformy była `false` przy wszystkich z tekstowym znacznikiem):
- @kacper.snela (5 postów XI 2026, podpis zaczyna się od „[współpraca z XTB]”), np. https://www.instagram.com/p/Df7QRf4jI99/ („[współpraca z XTB] 🥇 Złoto fizyczne czy ETC na złoto? …”), `isPaidPartnership: false`.
- Giełda Inwestycje Trading, Facebook, 31 X do 10 XI 2026: „#współpracareklamowa #Freedom24”, „#wspolpraca #freedom24” (flaga na FB: `null`).
- @piotr.zajac.finsite https://www.instagram.com/p/DOLoE5fjEbI/ (4 IX 2025): „#sponsorowane”, „Partnerem” (bossa).

Kandydaci M1 **bez** flagi i **bez** oznaczenia w tekście (to kandydaci do przeglądu, nie kwalifikacja; w próbce takich materiałów jest mało, tylko pierwszy ma link firmy):
1. Marcin Tuszkiewicz, Facebook, 21 XI 2026, https://www.facebook.com/reel/987873170602563/: „Porozmawiam z nimi podczas debaty na XTB Investing Masterclass, 27–28 listopada … 👉 Rejestracja na XTB Investing Masterclass …: https://link-pso.xtb.com/pso/4CLMt”. Link w domenie firmy, brak oznaczenia.
2. Justyna Kik, https://www.instagram.com/p/DfZuVJXiFDi/ (6 XI 2026): „Teraz gdybym miała wybrać jedną promkę, postawiłabym na Alior i te łatwe 3500 zł” … „300 zł za polecenie mu konta” … „Napisz w komentarzu JDG, a wyślę Ci linki”. Firmy z rejestru: mBank, Alior; brak flagi, brak oznaczenia, brak linku w podpisie.
3. Paweł, https://www.instagram.com/p/DRCmQ9AiNjt/ (14 XI 2025): „Najwyższa dywidenda w tym roku. Ile zysku przyniosła inwestycja 120 000 PLN w XTB?”; brak oznaczenia i linku (słaby sygnał).
4. Giełda Inwestycje Trading, https://www.instagram.com/p/DcOkHz9DKif/ (19 VIII 2026): „Oto krótki tutorial jak zaimportować swój portfel z XTB”, `#markawlasna` (promocja własnej aplikacji Stoxly; firma tylko wymieniona; to samo konto oznacza „#współpracareklamowa” przy Freedom24 na Facebooku).
5. holi.inwestuje, https://www.instagram.com/p/DZDCsF-gY54/ (1 VI 2026): omówienie kursu XTB, z ostrzeżeniem „Inwestowanie wiąże się z ryzykiem utraty kapitału” (kontrola ujemna: wzmianka o firmie bez promocji).

Kandydaci M2: twierdzenie o korzyści w treści reklam i postów firm (ostrzeżenie może być w grafice; badany jest tylko tekst):
1. XTB Online Investing, reklama 1421543096020676 (18 IX 2025 do 1 IX 2026, nieaktywna), https://www.facebook.com/ads/library/?id=1421543096020676: „Nie tylko zarabiaj pieniądze. Zacznij inwestować w akcje i ETF-y z 0% prowizji”; zasięg w UE 5 279 218, targetowanie Polska 18–65, płatnik XTB Online Trading. Bez ostrzeżenia w tekście.
2. XTB, reklama 1150549887287116 (3 XI 2025 do 2 II 2026), https://www.facebook.com/ads/library/?id=1150549887287116: „… Twoje pieniądze mogą pracować i zarabiać odsetki. 🇵🇱 4.1% 🇺🇸 3.9% 🇪🇺 2.3% … Zyskaj na swoich wolnych środkach”. Bez ostrzeżenia w tekście.
3. XTB, reklama aktywna 846978505145299 (od 8 X 2026), https://www.facebook.com/ads/library/?id=846978505145299: „Pieniądze są tylko narzędziem. Ty decydujesz, czy będą pracować dla Ciebie.”; zasięg w UE 1 660 449. Bez ostrzeżenia w tekście.
4. XTB Polska, Instagram, https://www.instagram.com/p/Dfo_zBYzzMi/ (12 XI 2026): przykład „efektywnych 10% rocznie … wartość wynosi około 346 673 zł” i kod „TECHPILOT” przy rejestracji w XTB; w tekście zastrzeżenie „Rzeczywisty wynik może być inny, także ujemny” (jest, ale nie jako ostrzeżenie o ryzyku utraty środków).
5. Z ostrzeżeniem w tekście (kontrola): Saxo Bank, reklama aktywna 1269830924657531 (od 10 IV 2026), https://www.facebook.com/ads/library/?id=1269830924657531: „Oszczędzaj do 70% na opłatach … Handel instrumentami finansowymi jest ryzykowny. Zawsze najpierw upewnij się, że rozumiesz to ryzyko.” W próbce wszystkie 40 reklam Saxo mają ostrzeżenie w tekście (28 z twierdzeniem o korzyści); XTB Online Investing: 16 z 30 reklam ma twierdzenie o korzyści bez ostrzeżenia w tekście, 14 nie ma ani twierdzenia, ani ostrzeżenia; eToro: 38 z 40 bez twierdzenia i bez ostrzeżenia, 1 z twierdzeniem bez ostrzeżenia, 1 z ostrzeżeniem (reguły tekstowe, heurystyka).

Reklamy stron trzecich z firmą jako marką (M1): Instagram `trading212pies` https://www.facebook.com/ads/library/?id=3672200766256534 (17 II 2026): „(282.11 - 171.33) ÷ 171.33 × 100% = +65% profit in just 16.5 months 🔥 … #trading212promocode #trading212freeshares”; zasięg w UE 20 775, płatnik „Trading 212 Pies”; bez ostrzeżenia w tekście. Facebook `tatiana.yurchik` ?id=1426347765576294 (24 XI 2025, po rosyjsku, wymienia „Freedom Finance, Degiro, Trading 212”, zasięg w UE 17 479) i `Forum Boost` ?id=949389864484336.

### Statusy źródeł dla integracji (`paths[]`)

Adapter zwraca wiersze `instagram`, `facebook`, `facebook-ads`, `instagram-ads` z `path: "vendor_sample"`, `sampleDate: "2026-11-21"`, `count`, `message` = „próbka datowana z 21 XI zebrana przez usługę zewnętrzną (N kont, M postów / K reklam); odczyt cykliczny w produkcie: import ręczny lub oficjalne API po uzyskaniu dostępu” i `nextStep`, oraz wiersz zbiorczy `vendor_social` (kredyty zużyte i pozostałe). `instagram-ads` ma liczbę 1 (reklama tylko na IG; reszta idzie na Facebooka i Instagram jednocześnie, a ID dostaje przedrostek `facebook:`, jak w `meta_ads`). Propozycja dla H w `collectors/adapter.py` (poza moim zakresem zapisu):

```python
PATH_OF["vendor-social-replay"] = "vendor_sample"
PATH_LABEL["vendor_sample"] = "próbka z usługi zewnętrznej"
_NEXT_STEP["vendor_sample"] = "Import ręczny (POST /v1/import/meta) lub oficjalne API po uzyskaniu dostępu."
# w path_summary: dla entry["path"] == "vendor_sample" i statusu ok:
#   text = f"próbka z usługi zewnętrznej ({count} {'postów' if posts else 'reklam'}, {dzień} XI)"
```

### Do wpięcia przez H (`collectors/discovery.py`)

```python
if importlib.util.find_spec("collectors.vendor_social") is not None:
    from .vendor_social import discover as discover_vendor_social
    register(Adapter("vendor-social-replay", discover_vendor_social, "Instagram i Facebook · próbka z usługi zewnętrznej (21 XI)",
                     modes=("replay",), enabled=_on_unless_listed("vendor-social-replay"), own_network=False))
```
Tylko `replay` i tylko na żądanie (jak `meta-import-replay`), żeby domyślny replay jej nie mieszał; worker może zlecić `adapters=["vendor-social-replay"]`. Opcja `vendor_social_sample` wskazuje inny plik próbki. Narzędzie zbierające to osobna komenda i nie jest zarejestrowane jako adapter: `python -m collectors.vendor_social collect --plan plan.json --max-credits N [--reserve 15] [--out-dir …]`; odbudowa replayu i manifestu bez sieci: `python -m collectors.vendor_social build`. Bez klucza `collect` kończy się kodem 3 (`needs_key`) bez żądania.

### Testy

`.runtime/venv/bin/python -B -m unittest discover -s collectors -t . -p 'test_*.py'`: 200 testów OK (w tym 25 nowych w `test_vendor_social.py`; żaden nie otwiera sieci): parser postów IG (profil i `v2/user/posts`, brak pól, ukryte polubienia), wpisów FB, reklam (reklama dynamiczna, szczegóły, strona trzecia), mapowanie błędów 401/402/429/404/400/500, licznik kredytów i rezerwa, wznowienie, klucz tylko w nagłówku, brak klucza (`needs_key`, kod 3, bez żądania), odmowa hostów spoza `api.scrapecreators.com`, replay zgodny z surowymi (także przy różnym `PYTHONHASHSEED`), skróty z manifestu, adapter bez sieci i bez klucza, brak komentarzy i klucza w plikach.

### Czego nie zrobiono

Nie wołano punktów komentarzy, obserwujących, grup ani transkrypcji. XTB ma w Bibliotece 2044 reklamy w PL, próbka ma 31 (dwie pierwsze strony po 30 posortowane według wyświetleń; drugiej strony nie dało się pobrać, HTTP 500). Posty tylko z jednej strony profilu IG (12 ostatnich) i 3 ostatnie wpisy strony FB, więc nie jest to pełna historia ani miara trafności. Tekst reklam bez grafiki: brak ostrzeżenia w tekście nie dowodzi braku ostrzeżenia w kreacji. Własność kont twórców z opisów YouTube nie została potwierdzona (konto wskazane w opisie, `crosslinkDiscovery`). Reklamy w UE bez zasięgu w UE zwracają `euTotalReach: null` do czasu pobrania szczegółów (7 z 114 mają szczegóły).
