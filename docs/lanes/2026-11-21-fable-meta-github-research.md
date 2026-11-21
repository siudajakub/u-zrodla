# Meta FB i IG: nieoficjalne biblioteki, scrapery i zbiory (przegląd źródeł, 21 XI 2026)

Model: Sonnet 5.5. Zakres: wyłącznie przegląd źródeł (WebSearch, strony GitHub, PyPI, Apify, dokumentacje, artykuły). Niczego nie zainstalowano ani nie uruchomiono, nie wysłano żadnego żądania do facebook.com, instagram.com ani graph.facebook.com, nie zmieniono kodu. Nie powtarzam ustaleń z `2026-11-21-fable-k-social.md` i `2026-11-21-fable-meta-alternatywy.md` (Ad Library API z tokenem, publiczna Biblioteka Reklam w przeglądarce, osadzenia profili IG, oEmbed, Apify i Bright Data ogólnie); odwołuję się do nich tylko tam, gdzie nowy wynik je zmienia.

Zastrzeżenie o jakości danych: liczby gwiazdek, daty i opisy pochodzą ze stron GitHub/PyPI/Apify (odczyt przez narzędzie streszczające) i z zestawień wtórnych (Scrapfly, Thunderbit, xpoz.ai, blogi). Gdzie strona GitHub nie pokazała daty ostatniego commita, piszę „brak daty”. Zestawienia wtórne bywają pisane przez sprzedawców usług, więc traktuj je jako wskazówki, nie dowody. Nic nie zostało potwierdzone próbą na żywo.

## Najważniejsze ustalenia (nowe względem wcześniejszych raportów)

1. **Jest darmowa, lokalna biblioteka do Biblioteki Reklam bez tokenu: `meta-ads-collector` (repo `promisingcoder/MetaAdsCollector`), wersja 1.7.2 z 10 XI 2026, MIT.** To jedyna znaleziona aktywna pozycja open source, która robi to, co wcześniej planowano Playwrightem, w gotowym pakiecie z CLI, JSON/JSONL/CSV i opcją `--enrich` (zasięg w UE, płatnik i beneficjent). Nie dowodzi to, że działa dla PL ani z naszego IP: README samo ostrzega o blokadach, weryfikacji i pustych wynikach, a w repo brak zgłoszeń (0 otwartych, zamkniętych nie widać), więc brak też świadectw użytkowników.
2. **Instaloader w listopadzie 2026 jest niestabilny także anonimowo.** Zgłoszenie #2806 z 21 XI 2026 (v4.16 + PR 2795): pobranie posta lub profilu bez sesji kończy się „Fetching Post metadata failed” (jedno zgłoszenie, bez potwierdzeń). Wątek #2786 („Is Instaloader still working reliably in 2026?”): wyniki mieszane, 429 na publicznych profilach w 4.13.2 i 4.15.4, ale jeden użytkownik pisze, że 4.16 znów pobiera bez logowania; logowanie i `--load-cookies` zgłaszane jako zepsute (#2792, 400 `feedback_required`).
3. **Facebook: żaden darmowy projekt open source nie jest żywy.** `kevinzg/facebook-scraper` i fork `moda20` nieaktywne od czerwca 2024, w issues „mbasic is gone”. Jedyna działająca droga bez konta to płatne actory Apify (jeden z nich, `mambalabs/facebook-posts-scraper`, deklaruje test 6 XI 2026 na 3 stronach po 30 postów bez logowania).
4. **Gotowych zbiorów polskich reklam lub postów finansowych bez dotykania Meta nie znalazłem** (ani na Hugging Face, Kaggle, Zenodo, ani w repozytoriach badaczy). Badacze (np. AI Forensics) budują własne zbiory z Biblioteki Reklam. DSA Transparency Database ma tylko decyzje moderacyjne, nie treści promocji.
5. **Wyrok Meta v. Bright Data (N.D. Cal., 23 I 2024)** orzekł, że warunki Meta nie zakazują zbierania publicznych danych bez zalogowania; Meta później wycofała roszczenie z umowy (według MediaPost, daty nie sprawdzono). To argument za scrapingiem bez konta, ale to jedno orzeczenie sądu pierwszej instancji w USA, nie wiąże w Polsce i nie zmienia faktu, że Meta uznaje takie zbieranie za naruszenie (patrz „Ryzyko regulaminowe”).

## Tabela projektów (23 pozycje, pogrupowane)

Skróty: **anon** = działa bez konta (deklaracja lub dowód); **sesja** = wymaga ciasteczek lub loginu konta Instagram/Facebook; **API-płatne** = wymaga konta u dostawcy pośredniczącego, nie na Meta. „Serwer” = czy ma szansę działać z adresu serwerowego (datacenter).

### A. Instagram, możliwy dostęp bez konta Meta

| # | Projekt | Licencja, żywotność | Co pobiera | Logowanie | Punkt końcowy | Problemy 2026 | Serwer | Wpięcie w Pythona |
|---|---|---|---|---|---|---|---|---|
| 1 | [instaloader/instaloader](https://github.com/instaloader/instaloader) | MIT; 14,0 tys. gwiazdek; v4.15.3 (26 VII 2026), w zgłoszeniach już 4.15.4/4.16; commit z 26 VII 2026 wg zestawienia | posty profilu publicznego, podpis, data, polubienia, komentarze, reelsy, geotagi, hashtagi; bez wyszukiwania słów kluczowych | **anon** dla publicznych profili; sesja dla prywatnych, stories, części funkcji | web GraphQL / `web_profile_info` (z zgłoszenia #2726 „429 on web_profile_info”) | 429 po kilku żądaniach z jednego IP (#2750, #2786, #2726); #2806 anonimowo „Fetching Post metadata failed” (21 XI 2026); 302 przy szybkich żądaniach; login i cookies zepsute (#2792) | słabo: wg zestawienia Scrapfly IP datacenter są blokowane | łatwe: `pip install instaloader`, `Profile.from_username()`, `profile.get_posts()` |
| 2 | [mpython77/instaharvest_v2](https://github.com/mpython77/instaharvest_v2) | MIT; 5 gwiazdek, 95 commitów, brak daty; praktycznie bez społeczności | profil, posty, reelsy, komentarze, hashtagi, lokalizacje przez `Instagram.anonymous()` (23 metody, opcjonalne proxy) | **anon** (deklaracja README) | agregacja wielu punktów, nienazwanych; paginacja publicznego GraphQL może dawać HTTP 400 (README) | liczby testów i „162 narzędzi agentowych” to deklaracje autora; hashtagi: 30 unikalnych na profil na 7 dni | nieznane | łatwe, ale niski poziom zaufania do projektu |
| 3 | [subzeroid/instagrapi](https://github.com/subzeroid/instagrapi) | MIT; 7,2 tys. gwiazdek; wydania 2.18.x (2.18.17 na liście wydań, 2.18.18 z 26 VIII 2026 wg xpoz.ai); commit z 10 VIII 2026 wg zestawienia | profil, posty, reelsy, stories, komentarze, DM, statystyki | **sesja** dla prywatnego API (`_v1`); metody `_gql` publiczne „opportunistic”, mogą zwracać 401/403/404/429; wydanie usunęło martwe `?__a=1`, a hashtagi i lokalizacje przeniesiono do uwierzytelnionych przepływów | mobile private API (konto) lub web GraphQL (anon) | wyzwania (`challenge_required`), zaufanie konta, proxy, stan urządzenia; maintainerzy: „fragile in production” | gorzej z kontem; konta są banowane | łatwe, ale bez konta wpięcie ma sens tylko dla metod `_gql` |
| 4 | Scrapfly `instagram-scraper` ([scrapfly-scrapers](https://github.com/scrapfly/scrapfly-scrapers/tree/main/instagram-scraper)) | NPOSL-3.0 (licencja niepermisywna, sprawdzić przed użyciem w produkcie); commit 4 VIII 2026 | profil, posty (publiczne punkty), doc_id GraphQL | **anon** przez płatny Scrapfly API (anty-bot po ich stronie) | web GraphQL `doc_id` (rotują) | licencja i płatność; własne repo sprzedawcy | tak (przez ich proxy) | łatwe; koszt nieustalony |
| 5 | [apify/instagram-scraper](https://apify.com/apify/instagram-scraper) (hosted) | płatny actor; 497 tys. użytkowników, 100% udanych uruchomień (deklaracja strony) | posty, reelsy, komentarze, oznaczenia, profil, hashtagi, miejsca | **anon** („logged-out version”), API-płatne (konto Apify) | publiczny widok; szczegóły nieujawnione | plan darmowy: ok. 15 komentarzy na post, ok. 21 oznaczeń; prywatnych profili nie czyta; numeryczne ID niewspierane | tak (działa po stronie Apify) | `pip install apify-client`, wywołanie actora i odczyt datasetu |
| 6 | ScrapeCreators ([scrapecreators.com](https://scrapecreators.com/blog/scrape-instagram-data)) i HikerAPI ([hikerapi.com](https://hikerapi.com)) | płatne API; ScrapeCreators 100 darmowych kredytów bez karty; HikerAPI 100 darmowych żądań (rejestracja, Telegram, wg Capterra), 0,02 do 0,0006 USD za żądanie (ze strony promującej) | profil i posty IG (ScrapeCreators: `/v1/instagram/profile`; HikerAPI: ponad 105 punktów, w tym posty, reelsy, stories) | **anon** po naszej stronie (konto u dostawcy, klucz API) | prywatne łącza dostawcy | nie sprawdzano warunków ani zasięgu danych (nie widziałem odpowiedzi) | tak | proste żądania HTTP z kluczem |

### B. Instagram, wymagają sesji konta (poza zakresem „bez konta właściciela”)

| # | Projekt | Licencja, żywotność | Co pobiera | Logowanie | Uwagi |
|---|---|---|---|---|---|
| 7 | [megadose/toutatis](https://github.com/megadose/toutatis) | GPL-3.0; 4,5 tys. gwiazdek; 331 otwartych zgłoszeń; brak daty | dane konta (imię, ID, bio, obfuskowany e-mail i telefon, liczby), nie treść postów | **sesja**: `toutatis -u konto -s sessionid` | rozpoznanie OSINT, nie monitoring treści |
| 8 | [Datalux/Osintgram](https://github.com/Datalux/Osintgram) | GPL-3.0; 15,7 tys. gwiazdek; brak daty (zestawienie podaje 25 VIII 2025 lub 5 XII 2024, nie ustalono, który projekt) | wiele zapytań OSINT o konto | **sesja** dla bogatszych zapytań; README: nie używaj głównego konta | edukacyjne, bez gwarancji |
| 9 | [dilame/instagram-private-api](https://github.com/dilame/instagram-private-api) (Node) | MIT; ostatni commit 7 III 2024, 408 otwartych zgłoszeń | prywatne API IG | **sesja** | pozostaje w tyle za zmianami Instagrama |
| 10 | RSS-Bridge `InstagramBridge` ([dok.](https://rss-bridge.github.io/rss-bridge/Bridge_Specific/Instagram.html)) | wydawca RSS-Bridge; bridge wymaga ciasteczek `sessionid` i `ds_user_id` w `config.ini.php` | kanał RSS konta | **sesja** (dokumentacja radzi osobne konto) | limity szybkości (429); dokumentacja wskazuje `PicukiBridge` i `PicnobBridge` jako drogę bez konta (ich stan nieweryfikowany) |
| 11 | RSSHub (trasy Instagram, `/picnob/user/:id`) | [DIYgod/RSSHub](https://github.com/DIYgod/RSSHub) | RSS z kont | trasa `instagram/user`: starsze zgłoszenie (2022) mówi o 403 `login_required`, więc prawdopodobnie ciasteczko; nie potwierdziłem w dokumentacji (strona tras zwróciła 404). Trasa `picnob` bez wzmianki o ciasteczku | demo `rsshub.app` ma limity per IP, dokumentacja radzi samodzielny hosting |

### C. Instagram, projekty uśpione lub martwe

| # | Projekt | Status |
|---|---|---|
| 12 | `drawrowfly/instagram-scraper` (npm `instatouch`) | MIT; ostatni commit 10 XI 2022; anon ograniczone i uśpione; punkty rotowały od 2022 |
| 13 | [chris-greening/instascrape](https://github.com/chris-greening/instascrape) (PyPI `insta-scrape`) | MIT; ostatnie wydanie 5 II 2021; repo: „no longer actively maintained”; nie działa na obecnej stronie |
| 14 | `igramscraper` (realsirjoe) | adres repo zwrócił 404; nie sprawdziłem, czy istnieje pod inną nazwą; brak dowodu żywotności, nie używać |
| 15 | `snscrape` ([JustAnotherArchivist/snscrape](https://github.com/JustAnotherArchivist/snscrape)) | ostatni commit XI 2023, ostatnie wydanie 0.7.0.20230622; moduły Instagram i Facebook niepotwierdzone, zgłoszenie IG z IV 2024 bez odpowiedzi; uznać za martwy |
| 16 | Bibliogram, Proxigram, Imginn, Picuki, Dumpor, Picnob, kittygram | Bibliogram zakończony (2022). [Proxigram](https://codeberg.org/ThePenguinDev/Proxigram) (Codeberg): ostatnia aktualizacja 3 XII 2024, scrapuje inne przeglądarki IG, instancje często padają (wątek Privacy Guides II 2026). Imginn: działał II 2026 według forum, reklamy. kittygram: „działa dość dobrze” (III 2026, jedno źródło). Picuki, Dumpor, Picnob: **status 2026 nie ustalony** (wyszukiwanie zwróciło szum). Są to usługi trzecie, nie API; ich wykorzystanie to kolejna warstwa regulaminowa |

### D. Facebook (wpisy stron)

| # | Projekt | Licencja, żywotność | Co pobiera | Logowanie | Uwagi |
|---|---|---|---|---|---|
| 17 | [kevinzg/facebook-scraper](https://github.com/kevinzg/facebook-scraper) i fork [moda20](https://github.com/moda20/facebook-scraper) | licencja nie ustalona; 3157 i 110 gwiazdek; ostatni push 22 VI 2024 i 14 VI 2024; 438 i 29 otwartych zgłoszeń | strony i grupy publiczne: tekst, czas, polubienia, komentarze, obrazy | opcjonalny login lub ciasteczka | „mbasic is gone” w zgłoszeniach; Thunderbit: „częściowo zepsute”; **uznać za martwy** (mbasic nie działa) |
| 18 | [shaikhsajid1111/facebook_page_scraper](https://github.com/shaikhsajid1111/facebook_page_scraper) | MIT; 281 gwiazdek; 78 otwartych zgłoszeń; brak daty | posty stron przez Selenium (przeglądarka) | bez klucza; logowanie opcjonalne, README ostrzega przed zawieszeniem konta | nie wiadomo, czy przechodzi ścianę logowania w 2026; **niepotwierdzone, niski priorytet** |
| 19 | [minimaxir/facebook-page-post-scraper](https://github.com/minimaxir/facebook-page-post-scraper) | 2128 gwiazdek; commit 23 V 2019 | Graph API z App ID i sekretem | token aplikacji | porzucony, wymaga zatwierdzenia przez Meta |
| 20 | Apify: [apify/facebook-posts-scraper](https://apify.com/apify/facebook-posts-scraper) oraz [mambalabs/facebook-posts-scraper](https://apify.com/mambalabs/facebook-posts-scraper) | płatne; oficjalny: od 2 USD (README: 5 USD, z filtrem daty +2 USD, Starter 4 USD) za 1000 postów, 145 tys. użytkowników, plan darmowy do 1000 postów; mambalabs: ok. 6,4 do 7,5 USD za 1000 wierszy, plan darmowy ogranicza do ok. 200 wierszy | strony publiczne: tekst, adres, czas UTC, reakcje, liczba komentarzy, udostępnienia, media, wideo transkrypt (oficjalny, opcja) | **anon** (mambalabs: „no login and no cookies”); API-płatne | mambalabs: test 6 XI 2026, 3 strony po 30 postów bez ściany logowania; rotujący identyfikator paginacji powoduje „partial” do aktualizacji actora; część stron odmówiona |

### E. Biblioteka Reklam Meta (bez tokenu)

| # | Projekt | Licencja, żywotność | Co pobiera | Logowanie | Punkt końcowy i problemy |
|---|---|---|---|---|---|
| 21 | [promisingcoder/MetaAdsCollector](https://github.com/promisingcoder/MetaAdsCollector) (PyPI `meta-ads-collector` 1.7.2) | MIT; 114 gwiazdek, 32 forków, 36 commitów; wydanie 10 XI 2026; Python 3.9+ (MCP 3.10+) | reklamy z Biblioteki: id, strona, treść, daty, platformy; `--enrich`: zasięg UE/UK, płatnik, beneficjent; wyjście CSV, JSON, JSONL; CLI, biblioteka Pythona i MCP | **anon**, klucz Meta niepotrzebny; opcjonalne proxy | „wewnętrzne punkty końcowe Meta” (nienazwane; według opisu w wyszukiwarce używa `curl_cffi` do odcisku TLS przeglądarki); README: możliwe blokady, weryfikacja, limity, pusty wynik nie dowodzi braku reklam; nie sprawdzono, czy radzi sobie z naszym wyzwaniem 403 JS (wcześniej odkrytym) |
| 22 | Apify: [apify/facebook-ads-scraper](https://apify.com/apify/facebook-ads-scraper) | płatne; 5,80 USD za 1000 reklam (plan darmowy), od 3,40 USD (Business); filtr kraju przez adres URL Biblioteki | reklamy FB, IG, Threads, Messenger, Audience Network; strona i reklamodawca; zasięg UE tylko dla reklam kierowanych na UE (często null) | **anon**, API-płatne | wyniki pojawiają się dopiero po zakończeniu uruchomienia; pola zasięgu „gdy dostępne” |
| 23 | Apify: [constructive_calm/facebook-ad-library-pro](https://apify.com/constructive_calm/facebook-ad-library-pro/examples/facebook-ads-poland.md) (gotowe zadanie „Polska”) | płatne, cena nieustalona na stronie przykładu | polskie reklamy FB i IG po słowie kluczowym (przykład: „kredyt”): id, strona, aktywna, daty, platforma, treść, CTA, link, obrazy, wideo | **anon**, API-płatne; proxy rezydencyjne (Apify) | to jedyny znaleziony gotowy preset PL; jakość nie sprawdzona |

Inne pozycje z przeglądu (bez własnego wiersza): [ChrisFeldmeier/fb_ad_scraper](https://github.com/ChrisFeldmeier/fb_ad_scraper) (20 gwiazdek, 15 commitów, brak daty i licencji, sesja przez `requests`, w README cel EU), [SandiRidwan/meta-ad-collector](https://github.com/SandiRidwan/meta-ad-collector) (1 gwiazdka, MIT, wymaga tokenu Apify; zapasowo Playwright z przechwytem GraphQL), [WhoTargetsMe/Ad_Library_API](https://github.com/WhoTargetsMe/Ad_Library_API) (wymaga tokenu Ad Library, więc nie pasuje), SocialAPIsHub/facebook-ads-library-api (opis „klient API Ads Library”, brak weryfikacji, czy ma token). Metoda „przechwyt GraphQL przeglądarką” (`/api/graphql/`, węzły `ad_library_main.search_results_connection`) jest opisana w kilku artykułach sprzedawców; wymaga przeglądarki i, wg nich, rezydencyjnego IP z właściwego kraju.

### F. Threads, narzędzia pomocnicze, archiwa

| Projekt | Status |
|---|---|
| [Danie1/threads-api](https://github.com/Danie1/threads-api) (Python) | MIT; 156 gwiazdek; **zarchiwizowane przez właściciela 1 X 2023**; odczyt publiczny bez logowania, reszta z loginem; uznać za martwe |
| [data-scrape/threads-scraper](https://github.com/data-scrape/threads-scraper) | zadeklarowana licencja MIT; strona zalana linkami sponsorów, funkcje niepotwierdzone; nie polegać |
| Apify actory Threads (`logiover/threads-scraper`, `axlymxp/threads-scraper` i ok. 15 innych) | deklarują „no login”; jedna z dokumentacji: ok. 25 postów na profil bez logowania, potem ściana; Threads nie jest priorytetem dla polskich firm inwestycyjnych (wcześniejszy raport) |
| [qeeqbox/social-analyzer](https://github.com/qeeqbox/social-analyzer) | AGPL-3.0 (copyleft, kłopot w produkcie); 24,6 tys. gwiazdek; wyszukuje konto o danej nazwie na ok. 1000 serwisach; **nie pobiera treści postów**; przydatny tylko do odkrywania profili |
| ArchiveBox, Wayback, archive.today | nie dają treści: wersje IG w Wayback przekierowują na login (ponad 83% w badaniu 2024), Archive-It: ostatnie zrzuty IG to pusty ekran, FB blokuje robota, pojedyncze posty bywają odtwarzalne; archive.today wpisane na czarną listę Wikipedii (II 2026). ArchiveBox to prywatne archiwum własnych linków, bez rozwiązania ściany logowania. Zgodne z wcześniejszym: `archived_snapshots: {}` |
| crawl4ai, Firecrawl, Crawlee | **nie znalazłem żadnego przykładu dla Instagrama ani Facebooka** z tymi narzędziami; Crawlee pojawia się tylko wewnątrz actorów Apify (jeden oznaczony jako przestarzały). Zestawienia 2026 piszą wprost, że proste skrypty BeautifulSoup lub zwykły klient HTTP już nie działają |

## Zbiory danych i archiwa (bez dotykania Meta)

| Źródło | Co zawiera | Przydatność dla próbki PL finansowej |
|---|---|---|
| **DSA Transparency Database** (`transparency.dsa.ec.europa.eu/data-download`) | dzienne spakowane CSV „statements of reasons”: osobno Facebook i Instagram; wersje pełna i lekka; parkiet tylko dla pełnego pliku zbiorczego; najnowszy dzień na liście 20 XI 2026 (42,4 mln wpisów); 20 XI 2026 to także dzień, na który strona pokazała rekordy | **niska**: to decyzje moderacyjne platform, nie treść promocji; strona nie potwierdza pól z treścią posta; pliki dzienne rzędu gigabajtów; Research API wymaga tokenu od DSA Helpdesk i obejmuje ok. 6 miesięcy; licencja danych „Data licence” niewczytana. Pomocne tylko, jeśli UKNF chce sprawdzić, które treści były usuwane lub zgłaszane (np. oszustwa inwestycyjne) |
| Meta Ad Library Report i Ad Targeting dataset | raport do pobrania dla krajów z autoryzacją reklam politycznych; zbiór kierowania tylko dla reklam politycznych i społecznych; przyjmowanie wniosków wstrzymane od 19 XII 2025 | **brak**: nie obejmują reklam finansowych |
| Hugging Face, Kaggle, Zenodo | wyszukiwanie nie zwróciło żadnego zbioru reklam Meta dla PL | **brak** (nie dowód nieistnienia) |
| Repozytoria badaczy | AI Forensics i podobni budują własne zbiory z Biblioteki Reklam, nie publikują gotowych eksportów PL, które znalazłem | **brak** |
| Archiwa CrowdTangle | CrowdTangle zamknięto w 2024 r. (z mojej wiedzy, nie z tego przeglądu); nie znalazłem publicznych archiwów polskich treści finansowych | **brak** |
| Meta Content Library (oficjalnie) | wpisy publiczne FB i IG; przegląd CASD ok. 2–3 tygodnie, potem przetwarzanie Meta ok. 2–3 tygodnie; kwalifikują się instytucje non-profit z celem badawczym; **brak informacji, jak traktowani są organy publiczne** (kontakt: metaresearchapplications@meta.com) | docelowo; nie na dziś |

## Ryzyko regulaminowe (wprost)

- **Żadne z narzędzi nieoficjalnych z tabel A–E nie jest dopuszczone przez Meta.** Warunki Meta zabraniają zbierania danych z produktów „automatycznymi środkami” bez uprzedniej zgody (cytat z doniesień prasowych; brzmienia „Automated Data Collection Terms” nie odczytałem, patrz ograniczenia). Meta egzekwowała to wobec badaczy (konta zespołu NYU Ad Observatory wyłączone w 2021), wskazując im drogę oficjalną.
- **Argument obronny, nie zgoda:** wyrok Meta v. Bright Data (23 I 2024) uznał, że zbieranie publicznych danych bez zalogowania nie narusza umowy z Meta; Meta wycofała tę część sprawy; część komentatorów oczekiwała apelacji. Dotyczy zbierania **bez logowania**; scraper z sesją konta (instagrapi, Toutatis, Osintgram, RSS-Bridge IG, facebook-scraper z ciasteczkami) jest wyraźnie poza tym argumentem i narażony na ban konta. W Polsce i UE wyrok USA nie jest wiążący; osobno obowiązuje RODO (publiczne dane mogą być danymi osobowymi).
- **Narzędzia na API pośredników (Apify, ScrapeCreators, HikerAPI, Scrapfly):** to nadal zbieranie automatyczne, ale ryzyko techniczne i konta trafia do dostawcy; nie czyni zbierania „oficjalnym”.
- **Oficjalnie dopuszczone:** Ad Library API (po potwierdzeniu tożsamości), Meta Content Library, oEmbed i osadzenia tylko do wyświetlania (analityka zabroniona), Threads API, Instagram Graph API na koncie, do którego mamy uprawnienia. Z naszej listy ani jedna pozycja nieoficjalna.

## TOP 3 dla Instagrama (bez konta właściciela, dziś, z treścią, datą i autorem)

Baza odniesienia, już sprawdzona wcześniej: osadzenie profilu `/<konto>/embed/` (6 postów z podpisem i datą). Poniższe drogi mają dać więcej niż 6 postów i historię.

### IG-1. Apify `apify/instagram-scraper` (płatne/próbne, najpewniejsze dziś)
- Wymaga konta Apify (plan darmowy: 5 USD kredytu miesięcznie, bez karty, wg kilku źródeł), nie konta Meta. Cena: od 1,50 USD za 1000 wyników (plan darmowy 2,70 USD). 5 USD wystarcza na rząd 1800 postów (obliczenie przeze mnie z ceny 2,70 USD, bez narzutu startowego).
- Kroki (nie wykonywałem): `pip install apify-client`; w Pythonie `ApifyClient(token).actor("apify/instagram-scraper").call(run_input={"directUrls": ["https://www.instagram.com/xtb_polska/"], "resultsType": "posts", "resultsLimit": 30})`, potem `client.dataset(run["defaultDatasetId"]).iterate_items()`. Nazwy pól wejścia i wyjścia pochodzą z mojej wiedzy o actorze, nie z przeczytanej strony; sprawdzić w zakładce Input przed uruchomieniem.
- Kształt danych (wg opisu strony i znanych wyników actora, niepotwierdzony): rekord posta z podpisem, czasem publikacji, nazwą autora, adresem, liczbą polubień i komentarzy, typem medium.
- Ryzyko regulaminowe: wysokie (automatyczny odczyt), przeniesione na dostawcę. Techniczne: nie dotyczy naszego IP; limity planu darmowego (ok. 15 komentarzy na post); prywatnych profili brak.

### IG-2. Instaloader anonimowo, z domowego (nie serwerowego) IP
- Darmowe, MIT, najbardziej utrzymywane. Brak potwierdzenia, że dziś działa: zgłoszenie #2806 (21 XI) mówi, że nie działa bez sesji w v4.16; wątek #2786 jest niejednoznaczny; zalecane obejścia z wątku: wersja 4.15.1/4.15.2, wolne żądania, zmiana sieci.
- Kroki: wirtualne środowisko poza repo, `pip install instaloader==4.15.2`, potem w Pythonie `L = instaloader.Instaloader(download_pictures=False, download_videos=False, save_metadata=False, max_connection_attempts=1)`; `profile = instaloader.Profile.from_username(L.context, "xtb_polska")`; `for post in profile.get_posts(): print(post.date_utc, post.owner_username, post.shortcode, post.caption)`; limit kilkanaście postów i odstęp ≥5 s. Atrybuty `Post` pochodzą z dokumentacji Instaloader znanej mi z pamięci, nie z tej sesji.
- Kształt: podpis, data UTC, autor, shortcode (z niego URL), polubienia.
- Ryzyko regulaminowe: wysokie (web GraphQL Instagrama, bez zgody). Techniczne: 429 po kilku żądaniach, redirect 302 i blokada IP; nie logować się kontem (ban).

### IG-3. Hostowane API z darmowym progiem: ScrapeCreators (100 kredytów) lub HikerAPI (100 żądań)
- Wymaga rejestracji u dostawcy, nie na Meta. ScrapeCreators: klucz API, `GET /v1/instagram/profile` (potwierdzone na stronie, że punkt istnieje); punkt z postami nieweryfikowany. HikerAPI: według zestawień ponad 105 punktów, w tym posty, reelsy, stories; warunki i dokładne punkty niezweryfikowane (wymaga rejestracji, wg Capterra także weryfikacji przez Telegram).
- Kształt: JSON z profilem i postami (pola do sprawdzenia w dokumentacji dostawcy).
- Ryzyko regulaminowe: jak IG-1. Techniczne: małe (po stronie dostawcy); nie sprawdzałem, czy dostawca zwraca podpis i datę dla polskich kont.

## TOP 3 dla Facebooka i reklam

### FB-1 (reklamy). `meta-ads-collector` lokalnie (darmowe, najszybsza ścieżka przy powodzeniu)
- Kroki (nie wykonywałem): `python -m venv /tmp/mac && /tmp/mac/bin/pip install meta-ads-collector`; test małej próbki: `python -m meta_ads_collector -q "XTB" -c PL -n 20 -o xtb.jsonl`; potem `--enrich` dla zasięgu UE; limity: kilka zapytań, bez pętli.
- Kształt: rekordy reklam (`ad.id`, strona, treść i dane Meta w `ad.api_fields`); `--enrich` dodaje zasięg UE, płatnika, beneficjenta; CSV, JSON, JSONL.
- Ryzyko regulaminowe: średnie do wysokie (wewnętrzne punkty końcowe; brak zgody Meta; argument Bright Data za logged-off). Techniczne: wyzwanie 403 JS, blokada IP serwerowego, rotacja identyfikatorów; **nie wiadomo, czy projekt przechodzi wyzwanie, które nasz zwykły HTTP dostawał jako 403**. Zalecam próbę z domowego IP; wynik zapisać jako `method: meta_ads_collector`, `mode: replay`.

### FB-2 (reklamy). Apify `apify/facebook-ads-scraper` lub gotowe zadanie `constructive_calm/facebook-ad-library-pro` (PL, „kredyt”)
- Kroki: `ApifyClient(token).actor("apify/facebook-ads-scraper").call(run_input={"startUrls":[{"url":"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=PL&q=XTB"}],"resultsLimit":50})` (nazwy pól z pamięci, sprawdzić). Cena 5,80 USD za 1000 reklam na planie darmowym, więc ok. 50 reklam to ok. 0,29 USD.
- Kształt: id archiwum, strona, aktywność, daty, platforma, treść, CTA, link, media; zasięg UE tylko gdy dostępny (często null).
- Ryzyko: jak IG-1; techniczne: wynik dopiero po zakończeniu uruchomienia. Daje to samo co droga 1 z wcześniejszego raportu, bez pisania skryptu.

### FB-3 (wpisy organiczne). Apify `apify/facebook-posts-scraper` lub `mambalabs/facebook-posts-scraper`
- Kroki: `ApifyClient(token).actor("apify/facebook-posts-scraper").call(run_input={"startUrls":[{"url":"https://www.facebook.com/ComparicPL"}],"resultsLimit":30})` (pola z pamięci; mambalabs używa `max_posts_per_page`, `since_date`). Cena: oficjalny 5 USD za 1000 (README) lub od 2 USD (nagłówek), mambalabs 6,4–7,5 USD; plan darmowy oficjalnego do 1000 postów.
- Kształt: tekst, adres, czas (UTC), reakcje, liczba komentarzy, udostępnienia, media, `page_name`; bez tekstu komentarzy.
- Ryzyko regulaminowe: jak wyżej. Techniczne: mambalabs ostrzega, że po zmianie identyfikatora paginacji zwraca tylko pierwszy post („partial”); część stron odmawiana; test 6 XI 2026 to deklaracja twórcy. To jedyna droga bez konta do wpisów FB, jaką znalazłem, i jedyna płatna.

## Drogi w pełni zgodne (skromniejsze)

1. **Ad Library API z tokenem** po potwierdzeniu tożsamości na facebook.com/ID (1–3 dni robocze wg źródeł wtórnych): reklamy komercyjne dostarczone w UE, strukturalnie. Adapter gotowy w `collectors/meta_ads.py`. Zmiana względem wcześniejszego raportu: żadna; potwierdza ją tylko to, że narzędzia nieoficjalne istnieją, bo API ma wąski zakres (jedno źródło twierdzi, że komercyjne reklamy nie są zwracane, wcześniejszy raport cytuje referencję, według której są; rozstrzygnie pierwszy odczyt z tokenem).
2. **Meta Content Library** (organiczne FB i IG): kilka tygodni, brak informacji o statusie organu nadzoru.
3. **Dane od samych firm i twórców:** eksport z Meta Business Suite lub zrzuty przekazane przez firmę, ręcznie wklejone URL-e i tekst z oznaczeniem pochodzenia. Wymaga współpracy podmiotu; nie badałem formatu eksportu.
4. **oEmbed i osadzenia tylko do wyświetlania oryginału w UI**, bez analityki (zakaz w dokumentacji).
5. **DSA Transparency Database:** zgodne i otwarte, ale nie zawiera treści promocji (decyzje moderacyjne), więc jako próbka kontekstowa.
6. **Threads API** (oficjalne, po przeglądzie aplikacji): dni, mała wartość dla polskich firm inwestycyjnych.

## Rekomendacja na dziś

- **Instagram:** IG-1, Apify `apify/instagram-scraper` na darmowym kredycie (kilkadziesiąt do kilkuset postów z 10–15 kont firm i finfluencerów, jednorazowo, z `method: apify_instagram_scraper`, `mode: replay`). Powód: jest jedyną drogą, której zadziałanie nie zależy od świeżości punktów końcowych po naszej stronie ani od IP, a koszt to centy. Instaloader (IG-2) wypróbować równolegle z domowego IP jako darmowy zapas, ale zgłoszenie #2806 z dzisiaj każe nie liczyć na niego.
- **Facebook:** reklamy: FB-1 `meta-ads-collector` jako pierwsza próba (darmowa, 10 minut), a jeśli zwróci 403 lub pusty wynik, FB-2 przez Apify. Wpisy organiczne: FB-3 (płatne, jedyna droga). Wcześniej zaproponowany własny Playwright na Bibliotece Reklam zostaje, jeśli `meta-ads-collector` zawiedzie.
- Zgoda J konieczna na koszt i ryzyko regulaminowe, zgodnie z regułami projektu; niczego nie założono ani nie zakupiono. Uczciwy komunikat dla jury jak w poprzednim raporcie: próbka jednorazowa, oznaczona jako replay, docelowo oficjalne API i Meta Content Library.

## Czego nie udało się zweryfikować

- Żadne narzędzie nie zostało uruchomione: nie wiem, czy `meta-ads-collector` przechodzi wyzwanie 403, czy zwraca polskie reklamy z naszego adresu, ani czy Instaloader dziś pobierze profil bez sesji.
- Daty ostatnich commitów większości repozytoriów GitHub: strony w odczycie nie pokazały dat; używam dat z zestawień wtórnych (Scrapfly, xpoz.ai, Thunderbit), które mogą być nieaktualne. Licencja kevinzg i innych w zestawieniu Thunderbit niepodana.
- Status Picuki, Dumpor, Picnob (nie odnalezione), Proxigram instancji, trasy RSSHub dla Instagrama i Facebooka (strony dokumentacji zwróciły 404), RSS-Bridge `FacebookBridge` (404), `igramscraper` (404).
- Dokładne punkty końcowe `meta-ads-collector`, `instaharvest_v2`, ScrapeCreators (poza `/v1/instagram/profile`), HikerAPI; nazwy pól wejścia actorów Apify (z pamięci).
- Ceny Apify (rozbieżności między nagłówkiem a README), ScrapeCreators i HikerAPI; kredyt 5 USD miesięcznie według kilku źródeł, nie z oficjalnej strony.
- Pełne brzmienie „Automated Data Collection Terms” Meta, termin i szczegóły wycofania roszczenia Meta w sprawie Bright Data, warunki Meta Content Library dla organów publicznych.
- Czy DSA Transparency Database zawiera jakiekolwiek pole z treścią posta (strona nie wymieniła); licencja danych.
- Zbiory na Hugging Face, Kaggle, Zenodo: tylko jedno wyszukiwanie, nie dowód braku.
- Crawl4AI i Firecrawl dla IG/FB: brak przykładów w wynikach; nie sprawdzałem ich dokumentacji ani zgłoszeń.
