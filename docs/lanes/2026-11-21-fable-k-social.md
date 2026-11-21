# Linia K: pozostałe źródła (TikTok, Facebook, Instagram, UA i proxy)

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
register(Adapter("facebook", discover_facebook, "Facebook · dostęp do wpisów", enabled=_on_unless_listed("facebook")))
register(Adapter("instagram", discover_instagram, "Instagram · dostęp do wpisów", enabled=_on_unless_listed("instagram")))
```
Adapter `tiktok` używa `ctx.captures` (potrzebny etap YouTube) i `ctx.previous` (kraj i język źródeł); `ctx.fetch` ma sygnaturę `fetch(url, allowed_hosts)`, jak `common.safe_get`. W `collectors/adapter.py` status `access_blocked` mapuje się dziś na zdrowie „ok”: trzeba dodać go do `ERROR_STATUSES` (albo osobny stan), inaczej pulpit nie pokaże blokady. Replay: `build_replay()` lub plik `fixtures/raw/discovery/social-2026-11-21/replay.json.gz` (pola `mode: "replay"` ustawione). Tryb `own_network` dla `tiktok` nie jest potrzebny, bo korzysta z `ctx.fetch`.

## Otwarte

Pozyskanie dostępu Meta (decyzja J), jedno źródło TikTok to profile tylko z odnośników YouTube, brak dat publikacji, `audio.py` bez rotacji UA.
