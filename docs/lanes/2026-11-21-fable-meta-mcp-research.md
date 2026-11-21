# Meta FB i IG: MCP, API pośredników, wyszukiwarki, narzędzia analityczne i drogi oficjalne (przegląd, 21 XI 2026)

Model: Sonnet 5.5. Zakres: wyłącznie przegląd źródeł (WebSearch, strony dokumentacji i cenników), bez zmian w kodzie, bez zakładania kont, bez instalacji i zakupów, bez żadnego żądania do facebook.com, instagram.com ani graph.facebook.com. Nie powtarzam ustaleń z `2026-11-21-fable-k-social.md` i `2026-11-21-fable-meta-alternatywy.md`. Ceny i limity pochodzą ze stron dostawców oraz opisów wyszukiwarki z 21 XI 2026; wiele stron zwracało sprzeczne liczby, co zaznaczam. Nic nie było uruchamiane na kluczach.

## Wnioski w pięciu zdaniach

1. Najkrótsza droga do próbki, którą agent wywoła sam z Claude Code, to **ScrapeCreators** (hostowany MCP + oficjalny skill; pokrywa jednocześnie IG: posty profilu, i FB: Biblioteka Reklam wg firmy/słowa i kraju, posty stron; 100 darmowych kredytów bez karty, 1 kredyt = 1 zapytanie) albo **Apify MCP** (darmowe 5 USD/mies. bez karty; IG scraper 2,70 USD/1000 wyników na planie Free).
2. Najmniejszy pakiet płatny ScrapeCreators to 47 USD (25 000 kredytów), czyli powyżej budżetu „kilka do kilkunastu USD"; dla próbki wystarczą jednak darmowe 100 kredytów lub Apify w ramach darmowych 5 USD.
3. Serwery MCP od „meta-ads" (Pipeboard i podobne) to **inna rzecz niż Biblioteka Reklam**: wymagają konta reklamowego i tokenu reklamodawcy, więc nie nadają się.
4. Wyszukiwarki: operator `site:` jest ignorowany przez dostępne tu narzędzie, ale z filtrem domeny zwracane są profile i strony IG/FB z fragmentami treści (patrz próby). To wystarcza do odkrywania adresów i pojedynczych podpisów, nie do zebrania listy wpisów z datą.
5. Oficjalnie dla IG: Business Discovery wymaga własnego konta IG Business i tokenu z uprawnieniami wymagającymi weryfikacji aplikacji poza trybem deweloperskim, a w dokumentacji nie potwierdzono pól `caption`/`timestamp` (patrz niżej); właściciel nie weryfikuje konta Meta, więc ta droga odpada na dziś.

## 1. Serwery MCP i narzędzia dla agentów

Przeszukano katalogi (mcpservers.org, Glama, Smithery, rejestr Apify, wyniki wyszukiwarki dla awesome-mcp-servers). Nie znalazłem w wynikach stron PulseMCP ani mcp.so, więc ich nie oceniam. Aktywność „2026" podaję tylko tam, gdzie źródło ją podaje.

| Narzędzie | URL | Utrzymuje | Co daje | Zaplecze | Konto Meta | Koszt i darmowy pakiet | Uruchomienie w Claude Code | Licencja / aktywność |
|---|---|---|---|---|---|---|---|---|
| **ScrapeCreators MCP + skill + CLI** | scrapecreators.com, docs.scrapecreators.com | ScrapeCreators (firma) | IG: profil, posty (`/v2/instagram/user/posts`), reels, wyszukiwanie po haśle i profilach, komentarze. FB: profil, posty profilu, reels, komentarze, grupy; **Biblioteka Reklam**: reklamy firmy (`pageId` lub nazwa; kraj, status, daty, typ medium), wyszukiwanie po słowie i kraju | własny scraping jako usługa (dane „na żywo z publicznych źródeł"); nie jest to Graph API | nie | 100 darmowych kredytów bez karty (+ do 1200 bonusowych za ankietę, gwiazdkę na GitHub i recenzję G2); pakiety 47 USD/25 000 kredytów, 497 USD/500 000; 1 kredyt = 1 zapytanie, wyniki z cache za darmo, kredyty nie wygasają | `claude mcp add --transport http scrape-creators https://api.scrapecreators.com/mcp`, potem `/mcp` → Authenticate → wklejenie klucza w przeglądarce; alternatywnie nagłówek `x-api-key` | zamknięty SaaS; aktywny (strona i dokumentacja aktualne) |
| **Apify MCP** (hostowany i `@apify/actors-mcp-server`) | github.com/apify/apify-mcp-server, docs.apify.com/platform/integrations/mcp | Apify (firma) | Dostęp do całego sklepu actorów: `search-actors`, `fetch-actor-details`, `call-actor` (+ pobranie wyników). Konkretnie: IG, FB posty/strony, Biblioteka Reklam | actory (cudze lub Apify) uruchamiane w chmurze Apify | nie (actory „bez logowania"; część wymaga cookies, patrz ryzyko) | plan Free: 5 USD platformy miesięcznie, bez karty, niewykorzystane przepada; opłata za wynik zależnie od actora; `maxTotalChargeUsd` i `maxItems` w `call-actor` ograniczają koszt | `claude mcp add apify "https://mcp.apify.com" -t http` (OAuth przy pierwszym użyciu); ograniczenie do jednego actora: `?tools=apify/instagram-scraper`; wariant z tokenem: `Authorization: Bearer` lub zmienna `APIFY_TOKEN` | MIT; 1523 commity; data ostatniego wydania niepotwierdzona na stronie |
| HasData Instagram MCP | mcpservers.org/servers/hasdata/instagram-mcp | HasData | IG: profil (przy profilu publicznym odpowiedź zawiera 12 ostatnich postów), strumień postów, komentarze; trzy narzędzia | hostowane API HasData | nie | 1000 darmowych kredytów miesięcznie bez karty; jedno wywołanie ok. 10 kredytów, czyli ok. 100 wywołań | `claude mcp add --transport http instagram "https://mcp.hasdata.com/mcp?apis=instagram" --header "x-api-key: <klucz>"` | MIT; wersja 1.0.8 sprawdzona 3 XI 2026, 13 do 16 gwiazdek; FB nie sprawdzono |
| Bright Data MCP (`@brightdata/mcp`) | brightdata.com/pricing/mcp-server | Bright Data | narzędzia `web_data_instagram_profiles/posts/reels`, `web_data_facebook_posts`; ogólne: wyszukiwanie, Web Unlocker | zaplecze datasetów i odblokowywania Bright Data | nie | 5000 zapytań miesięcznie darmowo; strona nie rozstrzyga, czy dane strukturalne IG/FB wchodzą do darmowego pakietu (tabela cennika wymienia „structured data" na każdym poziomie, inne źródło wiąże 60+ narzędzi z trybem Pro); dalej 1,5 USD/1000 w pay-as-you-go, Scale 499 USD/mies. | `npx @brightdata/mcp` z `API_TOKEN` | strona pakietu npm miała ostrzeżenie o łańcuchu dostaw (axios), do sprawdzenia przed instalacją |
| Firecrawl MCP | firecrawl.dev | Firecrawl | ogólny scraping stron | własne | nie | – | – | wg źródeł konkurencji domyślnie blokuje IG/FB („This website is no longer supported"), odblokowanie przez wsparcie; nieweryfikowane u źródła; **nie nadaje się** |
| Browserbase/Stagehand, Hyperbrowser, Oxylabs Agent Browser | browserbase.com itd. | firmy | chmurowa przeglądarka sterowana przez agenta | przeglądarka + proxy | IG pokazuje ścianę logowania; żadne źródło niezależne nie potwierdza stabilnego obejścia | od planów płatnych | MCP każdego z nich | tylko deklaracje dostawców; **nie polecam** (gorsze niż gotowe actory i grozi blokadą) |
| instamcp (`mpython77/instagram-mcp`, PyPI `instamcp`) | github.com/mpython77/instagram-mcp | indywidualny autor | 82 narzędzia IG; 22 anonimowe, 59 z `cookies.json` z zalogowanej sesji | własny klient z podszywaniem się pod TLS Chrome (`curl_cffi`) | anonimowo część; reszta cookies z konta | 0 | `pip install instamcp` | MIT; 1 gwiazdka, brak wydań; anonimowe wyszukiwanie hasztagów bywa blokowane; **nie polecam** (obchodzenie zabezpieczeń, nieznany autor, ryzyko dla konta) |
| Pipeboard `meta-ads-mcp`, inne „facebook-ads-mcp" | github.com/pipeboard-co/meta-ads-mcp | Pipeboard | zarządzanie własnymi kampaniami przez Marketing API | oficjalne API z tokenem użytkownika | **tak**, konto reklamowe i token | – | – | **inna rzecz niż Biblioteka Reklam**: czyta konto reklamodawcy, nie publiczne reklamy cudzych firm; **odrzucone** |
| SocialAPIs Hub, Caelario, Gumloop Instagram, `jsonscraper/instagram-mcp-server` | mcpservers.org, glama.ai | różni | FB i IG, w tym Biblioteka Reklam (SocialAPIs Hub, 47 narzędzi read-only) | hostowane API lub OAuth | zależnie | niezbadane | niezbadane | wymieniam jako kandydatów rezerwowych; opisy w katalogach niespójne (jeden wpis mówi, że IG jest na roadmapie) |
| Exa / Tavily / Brave Search MCP | exa.ai, tavily.com, brave.com | firmy | wyszukiwanie w sieci; indeks zawiera część stron IG/FB (patrz sekcja 2) | własne indeksy | nie | Exa: 20 USD jednorazowo + 10 USD miesięcznie darmowych (źródła niespójne: 4 lub 7 USD/1000); Brave: od 02.2026 brak planu zerowego, 5 USD kredytu miesięcznie (ok. 1000 zapytań), wg źródeł wtórnych wymaga karty | MCP lub klucz | – |
| Apify: konkretne actory | apify.com | Apify oraz społeczność | IG: `apify/instagram-scraper` 2,70 USD/1000 wyników na Free (2,30 Starter, 1,50 Business), plan Free: limit komentarzy; `apify/instagram-profile-scraper` 2,30/1000 (wg wyszukiwarki); FB posty: oficjalny 5 USD/1000 na Free wg porównania konkurenta (niepotwierdzone), actory społeczności 1,40 do 5,80 USD/1000; FB Ad Library: oficjalny `apify/facebook-ads-scraper` od 3,40 USD/1000 (wcześniej odnotowane), społeczności 0,20 do 1,70 USD/1000 (np. `curious_coder/facebook-ads-library-scraper` 0,75); `instagram-hashtag-scraper` i `facebook-pages-scraper` oficjalne: cen nie potwierdziłem | actory | nie | z darmowych 5 USD: ok. 1850 wyników IG po 2,70 USD, ok. 6600 reklam po 0,75 USD | zob. wiersz Apify MCP | – |

Uwaga: szczegóły ScrapeCreators dla Biblioteki Reklam z dokumentacji: parametry `pageId`/`companyName`, `country` (jeden kod albo `ALL`), `status` (ALL/ACTIVE/INACTIVE), `media_type`, `language`, `start_date`/`end_date`, `cursor`; odpowiedź zawiera `ad_archive_id`, `page_name`, `page_id`, `start_date`/`end_date`, `publisher_platform`, `snapshot.body.text`, `collation_id`/`collation_count`, `is_active`, obrazy i wideo, `regional_regulation_data` (przykład zawiera sekcję `finserv`; znaczenia nie potwierdza). Wielkość strony wyników nie jest podana, więc koszt kredytów na markę jest oszacowaniem.

## 2. Wyszukiwarki i indeksy

Zrobiłem 8 z 10 dopuszczonych prób WebSearch (żadnych żądań do Meta; to zapytania do wyszukiwarki). Obserwacja kluczowa: **operator `site:` jest ignorowany** (4 próby: wyniki z xtb.com, moneteo, hypeauditor, bez ani jednego URL-a instagram.com/facebook.com), natomiast **parametr `allowed_domains` zawęża do domeny i działa**. Cztery próby z filtrem domeny:

| # | Zapytanie (filtr) | URL wyniku | Fragment z treścią |
|---|---|---|---|
| 1 | `XTB Polska instagram konto maklerskie post` (instagram.com) | `https://www.instagram.com/xtb_polska/` | profil; ostatni podpis zawiera ostrzeżenie „74% rachunków detalicznych CFD odnotowuje straty"; ok. 39 tys. obserwujących, 711 postów |
| 2 | `XTB Polska inwestowanie facebook post` (facebook.com) | `https://www.facebook.com/xtbpl/` (strona XTB Online Investing); wideo `facebook.com/xtbpl/videos/...455815948614838/` | treść wpisów i wideo (tytuł „Czy już czas kupować polskie akcje? Trader 21 na XTB Trading Masterclass 2019"); także wpis finfluencera Inwestomat.eu z linkiem polecającym do XTB (`m.facebook.com/Inwestomat.eu/photos/...`) z pełnym tekstem wpisu |
| 3 | `kod promocyjny broker konto inwestycyjne bonus akcje za darmo` (facebook.com) | `facebook.com/promocje.rabaty/`, `facebook.com/akcieonline` | strony agregatorów promocji; opis z kodem polecającym XTB (slovacka strona), zwykle bez daty |
| 4 | `inwestowanie ETF finanse osobiste edukacja finansowa współpraca reklamowa` (instagram.com) | `instagram.com/mateuszhabowski/`, `instagram.com/mateusz_dasal/`, `instagram.com/beta_etf/` | opis profilu Mateusza Habowskiego zawiera kod promocyjny XTB (typowa afiliacja finfluencerska) |

Wnioski: indeks wyszukiwarki obejmuje **profile IG (opis, podpis ostatniego posta), strony FB i część pojedynczych wpisów/wideo FB z pełnym tekstem**, ale nie daje listy postów z datami ani ciągłego pobierania; daty bywają niewiarygodne (streszczenie wyszukiwarki; niezweryfikowano na stronie). Użyteczne do **odkrywania kont i wyłapywania kodów promocyjnych w opisach profili** (kod XTB w opisie finfluencera), nie do próbki wpisów. Cała ta metoda jest pośrednia: wyszukiwarka sama indeksuje, nie scrapujemy Meta.

Pozostałe:
- **Common Crawl**: indeks CDX (`index.commoncrawl.org/CC-MAIN-2026-43-index`, lista kolekcji pobrana poprawnie) zwrócił HTTP 504 przy czterech zapytaniach (profile xtb_polska, xtbpl i `instagram.com/p/*`), więc **nie udało się potwierdzić, czy indeksuje IG/FB**. Do powtórzenia później (serwer przeciążony). Nie wysłano żadnego żądania do Meta.
- **Wayback**: wcześniej `archived_snapshots: {}` (plik alternatywy).
- **API wyszukiwarek**: Brave Search API: od II 2026 brak planu zerowego, 5 USD kredytu miesięcznie, ok. 5 USD/1000 zapytań, wg części źródeł wymagana karta. SerpApi: Free 250 wyszukiwań/mies. (limit 50/h), płatny od 25 USD/1000. Serper: 2500 kredytów jednorazowo, ważne 6 miesięcy. Exa: patrz tabela. Bing Search API, Google Programmable Search, You.com, Tavily: nie sprawdzałem. Ważne ograniczenie: w prawdziwym API operator `site:` (Google, Brave) zwykle działa, ale zwracane są tylko tytuł, adres i fragment, więc to najwyżej wskaźnik do odkrywania.

## 3. Agregatory i narzędzia analityczne

| Narzędzie | Co w trialu | Eksport treści | API | Uwagi |
|---|---|---|---|---|
| Brand24 (PL) | 14 dni bez karty; FB i IG (przez integrację Meta for Business wg opinii użytkowników; nie jest to pełny scraping wszystkich kont) | eksport każdej wzmianki do Excel/CSV | niespójne źródła: dodatek 99 USD albo w wyższych planach | wzmianki o słowach kluczowych, nie pełne strumienie wpisów wskazanych kont; zasięg FB/IG wymaga weryfikacji w trialu |
| Modash | 14 dni triala (źródła niespójne co do planu Free); od ok. 199 USD/mies. | niepotwierdzone | w planach wyższych | baza influencerów; filtr kraj+temat finanse niepotwierdzony |
| HypeAuditor | plan darmowy z ograniczonym narzędziem (odkrywanie i analiza); od ok. 299 USD/mies. | niepotwierdzone | płatne | strony `hypeauditor.com/instagram/<konto>` są publiczne i indeksowane (statystyki: obserwujący, ER); przydatne do **listy finfluencerów PL** (np. inwestowanie, finansopedia) |
| Mention, Talkwalker, Sprout, Metricool, Not Just Analytics, SocialBlade | nie sprawdzałem | – | – | poza zakresem czasu |

Wniosek: dla próbki nie warto; Brand24 ma sens jako pomocnik odkrywania wzmianek w trialu (bez karty), ale nie zastępuje pobrania wpisów konkretnych kont.

## 4. Drogi oficjalne bez konta właściciela

- **Instagram Business Discovery**: wywołanie jest wykonywane na koncie IG Business/Creator **użytkownika aplikacji** z jego tokenem (`GET /<IG_USER_ID>/business_discovery`); zwraca dane publiczne **innych kont Business/Creator** (liczba obserwujących, liczba postów, ID, a przez rozwinięcie `/media` listę mediów z `comments_count`, `like_count`, `view_count`). Strona przeglądu nie wymienia w przykładach `caption`, `timestamp`, `permalink`; odsyła do referencji IG Media, której treści nie udało mi się potwierdzić (nie twierdzę, że pól nie ma). Wymagane uprawnienia wg referencji: token użytkownika Facebooka z `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement` (plus `ads_management` lub `ads_read` przy roli przez Business Manager). Konta nieletnich (age-gated) nie są zwracane; pobranie zwróconego mediów obiektu bezpośrednio kończy się brakiem uprawnień. Aplikacja bez przeglądu: dokumentacja mówi, że aplikacja używana tylko przez osoby z rolą w aplikacji lub w Business Managerze nie wymaga App Review, a użytkownicy spoza ról wymagają Advanced Access (przegląd i weryfikacja firmy). **Limity dla Business Discovery nie zostały potwierdzone** (strony Meta sprzeczne). Wniosek: technicznie możliwe w trybie deweloperskim, ale potrzebne jest **własne** konto IG Business powiązane ze Stroną FB i tokenem, czyli konto Meta, którego właściciel nie chce weryfikować; cel (wpisy z podpisami wielu firm) nie jest potwierdzony w dokumentacji.
- **Instagram Hashtag Search**: wymaga App Review z funkcją Instagram Public Content Access i `instagram_basic`; limit 30 unikalnych hasztagów na 7 dni na konto Business; bez Stories. Do monitorowania haseł typu `#kodpromocyjny` użyteczne, ale tylko po przeglądzie.
- **Page Public Content Access**: wpisy publiczne stron FB; wymaga przeglądu aplikacji (wcześniej odnotowane).
- **Meta Content Library**: kwalifikują się placówki naukowe i organizacje non-profit prowadzące badania naukowe lub w interesie publicznym; wniosek przez Research Tools Manager, weryfikacja przez ICPSR, zwykle 4 do 6 tygodni, bezpłatnie, coroczna rekertyfikacja. **Organ państwowy nie jest wymieniony jako uprawniony** (formularz zawiera pole „government agency", co nie rozstrzyga o kwalifikacji).
- **DSA art. 40**: ust. 4 do 8 dotyczą danych niepublicznych dla zweryfikowanych badaczy (akt delegowany 2025/2050 wszedł w życie 29 X 2025; wnioski przechodzą przez koordynatora usług cyfrowych państwa, w Polsce UKE); ust. 12 dotyczy dostępu do danych publicznych dla badaczy (poza aktem delegowanym). Art. 40 ust. 1 pozwala koordynatorowi i Komisji żądać danych od bardzo dużych platform, ale **wyłącznie w celu monitorowania zgodności z DSA**. Z mojej wiedzy o tekście rozporządzenia (nie zweryfikowanej tu na EUR-Lex): krajowy organ nadzoru finansowego **nie** ma na tej podstawie prawa żądać danych o promocji inwestycji; skorzystałby co najwyżej przez koordynatora lub w ramach wniosku badawczego.

## 5. Ryzyko regulaminowe i zgodność z briefem „bez płatnych API"

Stan prawny (ważne, bo to kluczowe dla opisu ryzyka): w sprawie **Meta v. Bright Data** (N.D. Cal., styczeń 2024) sąd uznał, że warunki Facebooka i Instagrama nie zakazują scrapowania danych publicznych **bez logowania**; Meta wycofała pozostałe roszczenie (luty 2024). To orzeczenie sądu pierwszej instancji w USA, ograniczone do faktów sprawy, bez wartości precedensu apelacyjnego i niewiążące w Polsce. Brzmienia aktualnych „Automated Data Collection Terms" Meta nie udało mi się odczytać (strona JS); fragment warunków platformy deweloperskiej mówi o unikaniu ułatwiania automatycznego dostępu do danych platformy, a podsumowanie wygenerowane maszynowo mówi o zakazie bez zgody niezależnie od logowania (niezweryfikowane).

| Droga | Kto narusza warunki Meta | Legalność pozyskania danych | Zgodność z „bez płatnych API" |
|---|---|---|---|
| ScrapeCreators, Apify, HasData, Bright Data (usługa płatna lub z darmowym pakietem) | dostawca prowadzi automatyczny odczyt; my jesteśmy klientem, nie obchodzimy zabezpieczeń sami; Meta może blokować dostawcę, nie nas (poza naruszeniem umowy z dostawcą), ryzyko dla nas to utrata dostępu do usługi i spór o uczciwość procesu | dane publiczne bez logowania; RODO: dane publiczne mogą być danymi osobowymi (wpisy osób prywatnych, finfluencerzy); dostawcy zwykle zastrzegają odpowiedzialność użytkownika | **produkt**: nie (zależność od płatnej usługi); **jednorazowa próbka**: tak, jeśli opisana w danych jako zebrana zewnętrzną usługą, z datą i bez wniosku, że produkt jej wymaga |
| actory/serwery z cookies lub kontem (część Apify, instamcp w trybie 59 narzędzi, przeglądarka z sesją) | **my** (konto Meta użyte do automatyzacji; naruszenie regulaminu użytkownika, możliwa blokada konta) | wyższe ryzyko, bo wyrok Bright Data dotyczy odczytu bez logowania | nie rekomenduję |
| Biblioteka Reklam przeglądarką (z poprzedniego raportu) | my (odczyt maszynowy narzędzia przejrzystości; warunki kierują do API) | dane publiczne w ramach przejrzystości DSA | produkt: tak (bez płatności), ale ryzykowne regulaminowo |
| Wyszukiwarka jako pośrednik | wyszukiwarka indeksuje; my nie odczytujemy Meta | publiczne fragmenty; ograniczone | produkt: tak, jeśli API bezpłatne (Brave i SerpApi mają darmowe progi z limitem; Brave bez karty niepotwierdzone) |
| Oficjalne API (Ad Library API, Business Discovery, MCL) | nikt | pełna zgodność | produkt: tak; wymagają konta/instytucji/zatwierdzenia |
| Panele analityczne (Brand24, Modash) | dostawca (licencje/integracje wg ich zapewnień) | licencje dostawcy | nie jako produkt |

Rozróżnienie dla briefu: wymóg „bez płatnych API" dotyczy **produktu**. Jednorazowe zebranie datowanej próbki do pokazu przez płatną lub darmową usługę nie czyni produktu zależnym od niej, o ile (1) kolektor produktu pozostaje na darmowych źródłach lub oficjalnych API (Biblioteka Reklam API, MCL), (2) próbka jest zapisana jako zapis „replay" z polami `method`, `collected_at`, `vendor`, (3) w prezentacji nie ma sugestii, że produkt działa ciągle na tej usłudze.

## 6. Rekomendacje

### A. Najszybsza droga na dziś (próbka IG: firmy i finfluencerzy; FB: reklamy i wpisy stron)

Rekomendacja: **ScrapeCreators**. Jedno konto, jeden klucz, ten sam dostawca obsługuje IG (posty profilu), FB (posty strony) i Bibliotekę Reklam, z dokumentacją pól i parametrów (kraj PL). Czas do pierwszych danych: ok. 15 do 30 minut od założenia konta.

Koszt: 0 USD na pierwszą partię (100 darmowych kredytów bez karty; 1 kredyt = 1 zapytanie). Szacunek: ok. 15 firm × (1 zapytanie postów IG + 1 do 2 FB reklam + 1 postów FB) = ok. 60 do 100 kredytów. Jeśli 100 nie wystarczy: pakiet 47 USD (25 000 kredytów, czyli powyżej budżetu rzędu kilkunastu USD; wymaga zgody właściciela) albo opcja Apify poniżej. Dodatkowe 100 kredytów za „jak nas znalazłeś" i 100 za gwiazdkę GitHub są dostępne, ale 1000 za recenzję G2 byłby wystawieniem opinii: nie robić.

Opcja zapasowa: **Apify** (5 USD miesięcznie bez karty): `apify/instagram-scraper` (ok. 2,70 USD/1000 wyników) dla postów profili IG, oficjalny lub społecznościowy actor Biblioteki Reklam (0,75 do 3,40 USD/1000), actor postów strony FB (1,40 do 5 USD/1000). Wystarczy na ok. 1850 wyników IG albo mieszankę. Ma to tę zaletę, że mieści się w darmowym pakiecie przy limicie `maxItems`.

Kroki dla właściciela (każdy krok mały; wykonuje właściciel, nic nie założyłem):
1. Wejść na scrapecreators.com, założyć konto (adres e-mail; bez karty), skopiować klucz API z `app.scrapecreators.com`.
2. Zapisać klucz do pliku poza repo: `mkdir -p ~/.config/investwatch && umask 077 && printf '%s' 'KLUCZ' > ~/.config/investwatch/scrapecreators.token`, potem `chmod 600 ~/.config/investwatch/scrapecreators.token`.
3. Potwierdzić, że wolno użyć darmowego pakietu i ewentualnie 47 USD (decyzja kosztowa).
4. Powiedzieć mi „klucz jest"; zrobię jedną próbę (np. `instagram/profile?handle=xtb_polska`, 1 kredyt), potem partię według listy z `firm-index.json`.

Wywołanie bezpośrednio (bez MCP): `curl -s -H "x-api-key: $(cat ~/.config/investwatch/scrapecreators.token)" "https://api.scrapecreators.com/v1/facebook/adLibrary/company/ads?companyName=XTB&country=PL&status=ALL"`. Nazwy parametrów zaczerpnięto ze strony dokumentacji; domyślny `status` to ACTIVE, więc do historii trzeba `ALL`.

### B. Droga wywoływana przez agenta w Claude Code (MCP)

Konfiguracja (po założeniu klucza): 
`claude mcp add --transport http scrape-creators https://api.scrapecreators.com/mcp`, następnie w Claude Code `/mcp` → wybrać Scrape Creators → Authenticate, w oknie przeglądarki wkleić klucz. Alternatywa: ten sam serwer przez nagłówek `x-api-key` (klient Claude Code musi obsługiwać nagłówki; w dokumentacji ScrapeCreators brak przykładu, ale polecenie `claude mcp add ... --header` istnieje). Jest też „first-party skill" ScrapeCreators dla Claude Code i Codex (nie sprawdzałem jego treści).

Alternatywa: **Apify MCP**: `claude mcp add apify "https://mcp.apify.com" -t http`; przy pierwszym użyciu OAuth w przeglądarce (konto Apify, bez karty); ograniczenie do jednego actora i kosztu: `https://mcp.apify.com?tools=apify/instagram-scraper` oraz `maxTotalChargeUsd`/`maxItems` w `call-actor`. Token w środowisku bez przeglądarki: `APIFY_TOKEN` z `~/.config/investwatch/apify.token`.

Uwaga praktyczna: konfiguracja MCP zapisuje się w `~/.claude.json` poza repozytorium; klucz nie trafia do Gita. Nie dodawać wpisu MCP do `.mcp.json` w repo z kluczem.

### C. Budżet = 0

1. **ScrapeCreators 100 darmowych kredytów** (bez karty) i/lub **Apify 5 USD/mies. bez karty** (czysty zero, jeśli mieści się w pakiecie). Wystarcza na kilka do kilkunastu firm i kilka finfluencerów.
2. **HasData MCP**: 1000 kredytów miesięcznie, ok. 100 wywołań profilu IG (każde ze strumieniem 12 postów); tylko IG.
3. **Wyszukiwarka z filtrem domeny** do odkrywania kont i kodów promocyjnych w opisach profili (jak w próbach 1 do 4): bez kluczy, wyniki to profile i pojedyncze posty z pełnym tekstem, bez lat; dobre do próbki finfluencerów (np. kod XTB w opisie Mateusza Habowskiego).
4. Brand24 14-dniowy trial bez karty dla wzmianek w FB/IG; eksport CSV; do sprawdzenia, ile treści wpisów oddaje.
5. Poprzedni raport: Biblioteka Reklam w zwykłej przeglądarce (reklamy) i embed profilu IG; ryzyko regulaminowe wyższe.
6. Ścieżka oficjalna równolegle: Ad Library API (po potwierdzeniu tożsamości) i wniosek Meta Content Library przez instytucję non-profit/akademicką (np. partner badawczy), 4 do 6 tygodni.

## 7. Czego nie udało się zweryfikować

- Czy ScrapeCreators naprawdę zwraca posty IG i reklamy FB dla polskich firm (nie wykonano ani jednego wywołania; brak klucza).
- Ile kredytów kosztuje zapytanie o reklamy i o posty strony FB oraz rozmiar strony wyników (strona dokumentacji podaje 1 kredyt/zapytanie dla Biblioteki Reklam; dla pozostałych cena nie była widoczna). Rozbieżność: strona główna mówi o 20 endpointach IG i 12 FB, dokumentacja wymienia więcej.
- Czy dane strukturalne IG/FB Bright Data wchodzą do darmowych 5000 zapytań.
- Common Crawl (HTTP 504), PulseMCP, mcp.so, Bing/Google CSE/You.com/Tavily, Mention/Talkwalker/Sprout/Metricool/Not Just Analytics/SocialBlade: nie sprawdzono.
- Ceny oficjalnych actorów Apify dla postów strony FB, hasztagów IG i stron FB; część cen pochodzi z wyników wyszukiwarki lub z porównań konkurentów.
- Pola `caption`/`timestamp` w Business Discovery, limity zapytań tej drogi, oraz to, czy w trybie deweloperskim wystarczy konto bez weryfikacji firmy (dokumentacja mówi: rola w aplikacji wystarcza; wymagane i tak własne konto IG Business).
- Brzmienie „Automated Data Collection Terms" Meta; stan sprawy Meta v. Voyager Labs; czy wyrok Bright Data dotyczy też odczytu przez usługę, którą opłaca polski klient.
- Stwierdzenie, że art. 40 DSA nie daje krajowemu organowi nadzoru finansowego prawa żądania danych, pochodzi z mojej wiedzy o treści przepisu, nie z odczytu EUR-Lex.
- Daty podawane w streszczeniach wyszukiwarki (np. wpisy XTB z listopada 2026) nie były sprawdzone na stronach.
- Wyniki wyszukiwarek mogą być zniekształcone przez streszczający model WebSearch; URL-e podaję z wyniku, treści traktuj jako fragmenty.

Nic nie scommitowano; kod bez zmian. Jedyny zapisany plik: ten.
