# Meta FB i IG: drogi na dziś (badanie, 21 XI 2026)

Model: Sonnet 5.5. Zakres: tylko badanie, bez zmian w kodzie. Surowe wyniki: `fixtures/raw/discovery/social-2026-11-21/alt/` (dziennik żądań `requests.log`, bez sekretów i ciasteczek). Razem 21 lekkich żądań HTTP, odstęp ≥3 s, bez logowania, proxy i obchodzenia zabezpieczeń, plus jedna próba headless Chromium.

## Najważniejsze ustalenia

1. **Publiczna Biblioteka Reklam Meta renderuje się w zwykłej przeglądarce bez konta.** Pierwsza odpowiedź to 403 z wyzwaniem JS (jak w próbie K), ale standardowy headless Chromium przeszedł je sam i pokazał ok. 14 000 wyników dla `country=PL&q=XTB`, 22 karty reklam w pierwszym widoku. Bez ściany logowania i bez CAPTCHA (flagi `has_login_wall`/`has_captcha` w pliku wynikowym to fałszywe trafienia regexów po słowach w kodzie strony; zrzut ekranu to potwierdza). Dziś to jedyna droga do prawdziwych reklam FB i IG bez tokenu. Ryzyko regulaminowe poniżej.
2. **Profil Instagrama przez oficjalne osadzenie profilu `https://www.instagram.com/<konto>/embed/` zwraca HTTP 200 bez logowania i zawiera w HTML ostatnie 6 postów** z podpisem, datą (`taken_at_timestamp`), liczbą polubień, flagą `is_paid_partnership`, liczbą obserwujących. Przykład: xtb_polska, 6 postów z 16–21 XI 2026. To jedyna dziś znaleziona droga do wpisów organicznych IG. Jest to punkt końcowy osadzania, nie API, więc ryzyko regulaminowe jest realne.
3. **oEmbed bez tokenu działa** (Meta ogłosiła to 15 VI 2026: osadzenia Instagrama, Threads, wpisów i wideo Facebooka bez tokenu i bez przeglądu aplikacji). Test: `instagram_oembed?url=<post>` bez tokenu → 200. Ale odpowiedź ma tylko `html` z blokiem osadzenia („View this post on Instagram”), bez podpisu i autora. Dokumentacja zabrania użycia treści z oEmbed do czegokolwiek poza wyświetlaniem (analityka wprost wykluczona). Do analizy treści się nie nadaje.
4. Facebook: wpisów organicznych bez logowania nie udało się odczytać żadną drogą. Wtyczka strony (`plugins/page.php`) zwraca HTTP 200, ale bez wpisów w HTML (renderowana po stronie klienta).

## Tabela dróg

| # | Droga | Co daje | Wymagania | Czas do danych | Koszt | Ryzyko regulaminowe | Wykonalność dziś |
|---|---|---|---|---|---|---|---|
| 1 | Biblioteka Reklam Meta, strona publiczna, zwykła przeglądarka (Playwright) | Reklamy FB i IG: ID biblioteki, daty, platformy, reklamodawca, treść, link, CTA, liczba wersji. Test XTB: ~14 000 wyników | brak konta; przeglądarka; stronicowanie przez przewijanie | minuty (próba udana) | 0 | Średnie do wysokiego (automatyczny odczyt strony, patrz niżej) | tak, jednorazowy datowany zrzut próbki |
| 2 | Ad Library API (`ads_archive`) | Reklamy komercyjne dostarczone w UE, strukturalnie, `eu_total_reach`, `beneficiary_payers` | potwierdzenie tożsamości (facebook.com/ID) + aplikacja + token użytkownika | „kilka dni” wg źródeł wtórnych; brak oficjalnej liczby; starsza wzmianka Meta z 2019: do kilku tygodni | 0 | niskie (oficjalna droga) | nie (za długo), adapter gotowy |
| 3 | IG osadzenie profilu `/<konto>/embed/` | 6 ostatnich postów organicznych z podpisem, datą, polubieniami, flagą współpracy | brak konta | sekundy (próba udana, xtb_polska) | 0 | Wysokie (punkt końcowy osadzania użyty do zbierania danych; regulamin zbierania automatycznego) | tak, jako datowana próbka, nie produkt |
| 4 | IG `/p/<kod>/embed/captioned/` | Podpis i autor posta ze znanego URL | brak konta | sekundy (test na wpisie NASA/Google, 200 z `class="Caption"`) | 0 | Wysokie, jak wyżej | tak dla znanych URL, ale odkrywanie URL jest osobnym problemem |
| 5 | oEmbed bez tokenu (IG, FB post/wideo, Threads) | tylko blok osadzenia, bez podpisu | brak | natychmiast | 0 | Niskie przy osadzaniu, zakaz analityki | nie do analizy; do wyświetlenia oryginału w UI tak |
| 6 | Wayback Machine dla FB/IG | brak: `archived_snapshots: {}` dla instagram.com/xtb_polska i facebook.com/xtbpolska | brak | – | 0 | – | nie |
| 7 | Strony firm: social wall/osadzenia | xtb.com/pl, bossa.pl, etoro.com/pl: tylko linki w stopce do profili, brak osadzonych postów | brak | – | 0 | – | nie (sprawdzone 3 z 4 planowanych, bez czwartej) |
| 8 | Threads API (oficjalne) | Wpisy publiczne po słowach kluczowych (`threads_keyword_search`) | aplikacja Meta, `threads_basic`, przegląd aplikacji dla wyszukiwania publicznego; limit ok. 500 zapytań/7 dni (źródło wtórne) | dni (przegląd) | 0 | niskie | nie dziś; firmy inwestycyjne w PL rzadko tam publikują |
| 9 | TikTok Commercial Content Library (library.tiktok.com) i API | Reklamy EU/EEA; wg źródła wtórnego API nie zwraca treści reklamy | strona: SPA (200, pusty szkielet bez JS); API: wniosek i zatwierdzenie na developers.tiktok.com | strona: przeglądarka; API: dni | 0 | niskie (API) | częściowo (strona w przeglądarce, nie próbowano) |
| 10 | Google Ads Transparency Center | Reklamy Google/YouTube wg reklamodawcy i kraju, w tym wideo | strona: SPA, 200 (szkielet, 2,6 MB, bez wyników bez JS); publicznie bez konta w przeglądarce; brak oficjalnego API | przeglądarka: minuty (nie próbowano) | 0 | średnie (brak oficjalnego API, odczyt wewnętrznych wywołań RPC bez zgody) | możliwe, poza zakresem Meta |
| 11 | Apify (płatne, jednorazowo) | reklamy: oficjalny actor `apify/facebook-ads-scraper` od ok. 3,40 USD/1000 reklam (plan darmowy 5,80); actory społeczności 0,50 do 1,70 USD/1000; IG: `apify/instagram-scraper` od 1,50 USD/1000 wyników (plan darmowy 2,70), posty z podpisem i datą, bez logowania | konto Apify i klucz API | ok. 30 min | niskie, rzędu pojedynczych dolarów za próbkę; kwota darmowego kredytu nie potwierdzona na stronach | Przenosi ryzyko na dostawcę; to nadal automatyczny odczyt | tak, po zgodzie J na koszt |
| 12 | Bright Data dataset FB Ads | rekordy reklam | konto | ok. godziny | od ok. 250 USD/100 tys. rekordów (strona; nie wiadomo, czy dotyczy Biblioteki Reklam) | jak wyżej | nie warto |
| 13 | SerpApi | darmowy plan 250 zapytań/mies., płatne od 25 USD; silnik `google_ads_transparency_center` istnieje (potwierdzone w dokumentacji); silnika Meta Ad Library nie znalazłem | klucz | minuty | 0 do 25 USD | jak wyżej | tylko Google |
| 14 | Meta Content Library | publiczne treści FB i IG, także organiczne | wniosek instytucji badawczej | dni do tygodni | 0 | niskie | nie dziś (droga docelowa) |
| 15 | Graph API: `instagram_oembed`/Page Public Content Access z tokenem | oEmbed: bez podpisu (jw.); PPCA: wpisy publiczne stron FB | przegląd aplikacji | dni | 0 | niskie | nie dziś |

Nie sprawdzono (brak zasobów, nie zakładano kont): ScrapingDog (wyszukiwanie nie zwróciło strony cennika), faktycznego użycia kluczy Apify/SerpApi.

## Wyniki prób (kody i co wróciło)

| Próba | Kod | Wynik |
|---|---|---|
| `instagram_oembed` bez tokenu, URL profilu xtb_polska | 400 | `OAuthException` 100/2207047: URL nie jest osadzalnym medium (profile nie są wspierane mimo opisu w dokumentacji) |
| `instagram_oembed` bez tokenu, URL posta | 200 | 7 kB JSON: `html` z blockquote, bez podpisu i autora |
| `threads_oembed` bez tokenu | 400 | `GraphMethodException` 100/33: ścieżka `threads_oembed` nie istnieje w Graph API w tej formie (nazwa punktu nie potwierdzona) |
| `instagram.com/p/<kod>/embed/captioned/` | 200 | 245 kB HTML, podpis i autor w `class="Caption"`, bez logowania |
| `instagram.com/xtb_polska/embed/` | 200 | 245 kB, 6 postów z podpisem, datą, polubieniami (próbka: `ig-xtb_polska-extracted-sample.json`) |
| `instagram.com/etoro/embed/`, `trading212_pl/embed/` | 200 | 0 postów w HTML (profile bez publicznych postów lub inne konto; do sprawdzenia, czy to właściwe konta) |
| `facebook.com/plugins/page.php?...ComparicPL&tabs=timeline` | 200 | 81 kB, bez wpisów w HTML |
| `adstransparency.google.com/?region=PL&query=XTB` | 200 | 2,6 MB szkielet aplikacji, treść ładowana przez JS |
| `library.tiktok.com/ads?region=PL&adv_name=XTB` | 200 | 41 kB, pusty szkielet; `/api/v1/search` → 404 (zgadnięty adres, nie oficjalny) |
| Wayback `available` dla instagram.com/xtb_polska i facebook.com/xtbpolska | 200 | `archived_snapshots: {}`; CDX dla IG przekroczył czas |
| `xtb.com/pl`, `bossa.pl`, `etoro.com/pl` | 200 | tylko linki do profili (etoro: facebook.com/eToro, instagram.com/etoro_official); brak osadzeń |
| `facebook.com/apps/site_scraping_tos_terms.php` | 301 | na `legal/automated_data_collection_terms`; po przekierowaniu stronę zwraca JS (nie dało się odczytać tekstu) |
| **Biblioteka Reklam Meta, Chromium headless, jedna próba** | 403 → przeglądarka przeszła wyzwanie | Strona „Biblioteka reklam”, „Liczba wyników ~ 14 000”, 22 karty w pierwszym widoku. Baner cookies: przycisk nie wystąpił lub nie zablokował widoku (nie kliknięto nic poza ewentualnym zwykłym przyciskiem; w wyniku brak `cookie_click`). Zrzut: `metaadlib-browser.png`. Tekst DOM: `metaadlib-browser-body.txt` |

Uwaga do próby przeglądarki: pierwsze dwa uruchomienia zakończyły się błędem narzędzia (wersja Chromium w venv nie zgadzała się z zainstalowaną, potem konflikt `queue.py` w katalogu skryptu); strona Meta nie została wtedy załadowana ani zrzucona. Trzecie uruchomienie dało wynik powyżej. Użyto zainstalowanego `chrome-headless-shell` 1234, bez pobierania. Inny Chromium nie działał (sprawdzone `pgrep`). Dopiero po pierwszym `pgrep` zauważono, że obciążenie hosta było wysokie (load 40), potem spadło do 4.

### Pola widoczne na karcie (dwie pierwsze karty, tekst DOM)

Karta 1: Identyfikator biblioteki 1421543096020676; „Nieaktywna”; 18 wrz 2025 – 1 wrz 2026; platformy (ikony FB, IG, Audience Network); „Reklama ma kilka wersji”, liczba reklam z tym materiałem: 12; reklamodawca „XTB Online Investing”, „Sponsorowane”; treść „Nie tylko zarabiaj pieniądze. Zacznij inwestować w akcje i ETF-y z 0% prowizji”; domena XTB.PL; tytuł „Inwestuj w akcje i ETF-y bez prowizji”; opis; CTA „Sign Up”.
Karta 2: ID 1859210128043429; 1 lis 2025 – 1 wrz 2026; wideo 0:10; liczba reklam z tym materiałem: 4; ta sama treść, wersja wideo.
Brak na karcie bez wejścia w szczegóły: `eu_total_reach`, płatnik/beneficjent, targetowanie (są w panelu „Zobacz szczegóły podsumowania”, nieotwierany).

## Weryfikacja tożsamości Ad Library API: co wiadomo

- Oficjalne strony Meta (facebook.com/ads/library/api, transparency.meta.com) nie oddają treści zwykłemu odczytowi (403 lub szkielet JS), a referencja `ads_archive` nie podaje czasu zatwierdzenia ani wymagań tożsamości. Cytat z referencji: „Ads that did not reach any location in the EU will only return if they are about social issues, elections or politics.” Wynika z niego, że reklamy komercyjne dostarczone w UE są zwracane, w tym finansowe.
- Czas: źródła wtórne (blogi z 2025–2026) mówią o „kilku dniach” (1–3 dni robocze); stary wpis Meta z 2019 mówił o „kilku tygodniach”. Godzinowej ścieżki przyspieszonej nie znalazłem. Nie znalazłem też potwierdzenia, że konto zweryfikowane do reklam politycznych lub biznesowych (Business Manager) skraca proces; źródła wtórne mówią, że bramką jest osobista weryfikacja facebook.com/ID, odrębna od weryfikacji firmy. Jedno źródło wspomina o kodzie wysyłanym pocztą (prawdopodobnie przestarzałe).
- Token aplikacji bez weryfikacji użytkownika: brak potwierdzenia, że daje dostęp. Zakładam, że nie.
- Wniosek: nie ma drogi „dziś” przez API. Jeśli J ma już potwierdzoną tożsamość na facebook.com/ID (np. po reklamach politycznych), warto sprawdzić od razu testem z kroku 7 listy K, zamiast czekać.

## Zgodność z warunkami (ryzyko wprost)

- Nie udało się odczytać tekstu „Automated Data Collection Terms” Meta w tej sesji (strona renderowana JS, wyszukiwanie nie zwróciło brzmienia). Z pamięci: zapis mówi, że nie wolno zbierać danych automatycznie bez pisemnej zgody Meta; **traktuj to jako niezweryfikowane i sprawdź przed pokazem**. Nie ma też w znalezionych źródłach wyjątku dla Biblioteki Reklam.
- Strona Biblioteki Reklam jest publicznym narzędziem przejrzystości (DSA), ale warunki Meta kierują odczyt maszynowy do API (strona narzędzi mówi, że API służy do głębszej analizy reklam, także dostarczanych w UE). Okazjonalny, jednorazowy, ręcznie uruchomiony odczyt jednej próbki do datowanego replay jest mniejszym ryzykiem niż stały scraper, ale nie jest „dopuszczalny wg warunków” w sensie potwierdzonym zapisem. Realne skutki: blokada IP lub konta, nie roszczenie karne; do decyzji J.
- oEmbed: dokumentacja wprost: użycie tylko do osadzania, analityka zabroniona.
- Osadzenia profilu i posta IG (drogi 3 i 4): to nie API; użycie do zbierania treści jest ryzykowne regulaminowo i może zniknąć bez ostrzeżenia. Nie zalecam w produkcie.
- Płatni pośrednicy (Apify): ryzyko przechodzi na wykonawcę, ale dane i tak powstają automatycznym odczytem. RODO: dane publiczne mogą być danymi osobowymi (zastrzeżenie samego dostawcy).

## Rekomendacje

**A. Najlepsza droga na dziś.**
- **Facebook i Instagram, reklamy (moduł 1 i 2):** jednorazowy odczyt publicznej Biblioteki Reklam przeglądarką (droga 1), dla marek z `firm-index.json`, z datą i zapisem surowych kart (ID biblioteki, tekst, daty, platformy), bez klikania w szczegóły i bez obchodzenia czegokolwiek, 3–5 zapytań na całą próbkę. Czas: ok. 1–2 h pracy (skrypt Playwright + parser kart + zapis do formatu capture `facebook:ad-<id>` i `instagram:ad-<id>`, jak w `meta_ads.py`). Konieczna zgoda J na ryzyko; jawnie oznaczyć w danych `method: browser_public_ad_library`, `mode: replay`.
- **Instagram, wpisy organiczne:** `…/<konto>/embed/` (droga 3) dla kilkunastu kont firm, jednorazowo, datowany replay, z zastrzeżeniem ryzyka. 6 postów na konto, bez historii. Czas: 30–60 min. Alternatywa regulaminowo czystsza: Apify `instagram-scraper` (ok. 1,50–2,70 USD/1000 postów), po zgodzie J na koszt; ryzyko tylko przesunięte.
- **Facebook, wpisy organiczne:** nic bezpiecznego dziś nie działa. Zostaje oznaczony import ręczny (wklejone URL i tekst) albo Apify (nie sprawdzono konkretnego actora dla stron FB).
- Równolegle uruchomić proces Ad Library API (kroki z `2026-11-21-fable-k-social.md`); jeśli tożsamość jest już potwierdzona na facebook.com/ID, token może działać od razu.

**B. Droga docelowa dla UKNF.** Dwie oficjalne ścieżki: (1) Ad Library API po potwierdzeniu tożsamości organu (reklamy komercyjne w UE), przez już gotowy `collectors/meta_ads.py`; (2) Meta Content Library i API dla wpisów organicznych FB i IG (wniosek instytucji, art. 40 DSA jako podstawa wniosku badawczego; nie dowód uprawnienia). Dla TikToka: Commercial Content API. Dla Google/YouTube: Ads Transparency Center (brak oficjalnego API, więc wymaga uzgodnienia). Produkt bez płatnych API: wszystkie powyższe są bezpłatne.

**C. Co uczciwie powiedzieć jury.** Gdy brak wpisów organicznych FB: „Prototyp zbiera TikTok i YouTube w pełni automatycznie z jawnych publicznych źródeł. Dla Facebooka i Instagrama Meta nie udostępnia wpisów organicznych bez zatwierdzenia instytucji (Meta Content Library) lub tokenu z potwierdzoną tożsamością. Pokazujemy datowaną próbkę reklam z publicznej Biblioteki Reklam i kilka kont IG zebranych jednorazowo, wyraźnie oznaczoną jako replay, a docelowo podłączamy oficjalne API; adapter jest gotowy i testowany na odpowiedziach zgodnych z referencją, nie z żywym API.” Nie mówić, że zbieranie jest „w pełni zgodne z warunkami Meta” ani że działa ciągle.

## Kroki dla właściciela

1. Zdecydować, czy dopuszcza ryzyko regulaminowe dróg 1 i 3 dla jednorazowej próbki (tak/nie). Bez „tak” nie uruchamiam skryptu.
2. Sprawdzić na facebook.com/ID, czy konto ma potwierdzoną tożsamość; jeśli tak, przejść od razu kroki 2–7 z listy w `2026-11-21-fable-k-social.md` i zapisać token do `~/.config/investwatch/meta.token` (chmod 600).
3. Jeśli ma być Apify: założyć konto (apify.com), skopiować token API z Settings → Integrations do `~/.config/investwatch/apify.token` (chmod 600), potwierdzić limit kosztu (kilka USD). Niczego nie założyłem ani nie kupiłem.
4. Jeśli ma być wniosek Meta Content Library: Research Tools Manager, wniosek instytucji; czas dni do tygodni.

## Ograniczenia

Nie przeczytałem oficjalnych stron Meta o warunkach i tożsamości (zwracają JS lub 403), więc czas zatwierdzenia i brzmienie zakazu automatycznego zbierania pochodzą ze źródeł wtórnych lub pamięci. Biblioteki TikToka i Google nie sprawdzałem w przeglądarce, tylko lekkim HTTP. Panel „Zobacz szczegóły podsumowania” (zasięg w UE, płatnik) nie był otwierany. Próba przeglądarki dotyczy jednej frazy (XTB). Ceny Apify, Bright Data i SerpApi pochodzą ze stron lub opisów wyszukiwarki z 21 XI 2026 i mogły się zmienić. Nic nie scommitowano, kod bez zmian.
