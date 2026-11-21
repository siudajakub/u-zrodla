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
