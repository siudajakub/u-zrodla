# Co obserwuje InvestWatch i jak rozszerzyć próbę

## Przebieg jednego odczytu

| Platforma | Skąd bierzemy publikacje | Z czego pochodzi tekst | Czego brakuje do wniosku o reklamie |
|---|---|---|---|
| YouTube | Lista startowa zawiera stałe identyfikatory kanałów DETERMINACJA i Comparic Rynki. Dla każdego czytamy publiczny kanał Atom. W sondach mieścił po 15 publikacji | ID filmu, URL, tytuł, opis i data podana przez źródło. W dwóch różnych filmach padła ta sama deklaracja „Partnerem odcinka jest XTB” | Kanał może pominąć starsze filmy. Opis nie obejmuje tego, co autor powiedział lub pokazał. Płatna dystrybucja wymaga odrębnego dowodu |
| TikTok | Obserwujemy @comparic.pl i @tradewarspl przez publiczne osadzenie profilu. Łączymy URL filmu z wpisem o tym samym ID w danych tego osadzenia | Podpis filmu z pola desc. Obie obserwowane odpowiedzi udostępniały po 10 linków. W badanym formacie brak jawnej daty publikacji | Widget pokazuje ograniczony wybór. Zmiana wewnętrznego formatu może przerwać odczyt. Reklama wyłącznie w obrazie lub mowie jest poza zakresem podpisu |

Przykład źródłowy można otworzyć i porównać z jego zachowanym cytatem. Samo słowo „partner” uruchamia wyszukiwanie kandydata. Dopiero właściwy kontekst wskazuje, kto z kim deklaruje współpracę. Oznaczenie sponsora, link afiliacyjny, zwykła wzmianka, potwierdzenie płatnej emisji oraz odpowiedź firmy są osobnymi obserwacjami. [Przykład deklaracji](https://www.youtube.com/watch?v=xtMqKkFO-0M) · [Publiczny mechanizm kanału YouTube](https://developers.google.com/youtube/data/guides/push_notifications) · [Osadzenie profilu TikTok](https://developers.tiktok.com/docs/en/embed-creator-profiles)

Na wersję językową, wizerunek lub obietnicę wypowiedzianą w 12. sekundzie filmu potrzebujemy drugiego wejścia. W pilocie analityk może załączyć dozwolony materiał, transkrypt lub klatkę z oznaczeniem czasu i pochodzenia. Ścieżka rozbudowy przewiduje lokalne rozpoznawanie mowy i OCR, odsyłacz do sekundy oraz kontrolę jakości na ręcznej transkrypcji. API YouTube wymaga uprawnienia do edycji filmu do pobrania napisów. [Dokumentacja captions.download](https://developers.google.com/youtube/v3/docs/captions/download)

## Monitoring na hoście

Pojedynczy lekki proces i SQLite obsługują cztery publiczne profile. Definicje jednostek leżą w ops/user-systemd. Harmonogram to 00:10, 04:10, 08:10, 12:10, 16:10 i 20:10 czasu polskiego. Przy uśpieniu lub niedostępności hosta systemd nadrabia jeden pominięty przebieg. Kolejne rzeczywiste publikacje zależą od aktywności kont. Pierwsze uruchomienie ustala punkt odniesienia. Przerwa dłuższa niż okno ostatnich pozycji może powodować luki. Przy braku wspólnych ID pomiędzy dwoma udanymi skanami operator powinien oznaczyć możliwą lukę, sprawdzić źródło i w razie potrzeby zwiększyć częstotliwość dla konta.

Dane robocze leżą w .runtime/watch pod głównym checkoutem. Po wywołaniu usługi plik reports/YYYY-MM-DD.json zawiera wynik dla polskiej daty obserwacji. Powtarzane odczyty uaktualniają raport tego dnia. Rejestr rozróżnia pierwsze zaobserwowanie, potwierdzoną nową publikację, edycję i wpis bez zmian. Data publikacji może być nieznana. W statystykach zachowujemy również nieudane skany. Stan usługi, historię i raport można odczytać z katalogu repozytorium.

```sh
systemctl --user list-timers investwatch-watch.timer
python3 tools/watch_sources.py status --db .runtime/watch/watch.sqlite3
python3 tools/watch_sources.py report --db .runtime/watch/watch.sqlite3 --date 2026-11-21 --timezone Europe/Warsaw
journalctl --user -u investwatch-watch.service -n 12
```

Harmonogram można wstrzymać przez `systemctl --user disable --now investwatch-watch.timer`. Konta dodaje się w tools/watch_sources.json, po weryfikacji tożsamości i tego, że profil jest publiczny. Zmiana nazwy TikToka wymaga aktualizacji i zachowania poprzedniego aliasu. Operacyjna baza przechowuje konkretne obserwacje. Monitor czterech profili i worker odkrywający twórców mają różne zakresy i osobne harmonogramy. W odczycie z hosta 21 XI 2026 przed 20:10 CET timer był aktywny, a LastTriggerUSec pusty. Termin zaplanowany nie stanowi dowodu automatycznego wyzwolenia.

Usługę sprawdzono dwoma ręcznymi wyzwoleniami systemd 21 XI ok. 16:40 czasu polskiego. Pierwsze zapisało 50 obserwacji, drugie znalazło te same 50 identyfikatorów i 0 zmian. Baza miała 50 wersji z pełnym tekstem, 15 różnych opisów na 30 filmów YouTube oraz 20 różnych podpisów dla 20 TikToków. Timer był w stanie active/enabled. Pierwsze wyzwolenie zegarowe przypadało na 20:10 tego dnia. W raporcie domyślne 10 pozycji dobrano naprzemiennie z profili z priorytetem dla sygnałów partnerstwa lub ryzyka. Taki wybór nadaje się do przeglądu, ale estymacja częstości wymaga osobnego losowania.

Usługa ma jawne ustawienie `--keep-text`. W prywatnej bazie SQLite zachowuje oryginalny tekst pola opisu lub podpisu, na YouTube także tytuł, dla każdej widzianej wersji. W raporcie zostają krótkie cytaty. Przy usunięciu wpisu pierwotny zapis nadal można sprawdzić. Zniknięcie wpisu z krótkiego okna może wynikać także z nowych publikacji. Zapytanie analityka przyjmuje parametry platformy i ID z raportu.

```sql
SELECT version, text, title FROM post_texts
WHERE platform = ? AND post_id = ? ORDER BY version;
```

## Odkrywanie całej niszy

1. Zdefiniować populację roboczą jako publiczne konta publikujące po polsku o instrumentach lub usługach inwestycyjnych dla odbiorcy w Polsce. Oznaczać język i produkt. PL w parametrze regionCode YouTube dotyczy dostępności filmu do oglądania. Ręcznie rozstrzygać konta pośrednie, edukacyjne i wielojęzyczne. [Semantyka YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list)
2. Co tydzień zbierać kandydatów co najmniej trzema sposobami. Pierwszy wychodzi od aliasów firm z rejestrów KNF, w tym transgranicznych. Drugi szuka po niezależnych frazach o temacie, np. „portfel ETF”, „obligacje”, „rachunek maklerski”, z wariantem bez słowa „reklama”. Trzeci wychodzi od ujawnionych partnerstw i odsyłaczy twórców. Zapisać zapytanie, czas, metodę, pozycję, tożsamość platformową i decyzję o przyjęciu. Ten etap jest osobnym zadaniem od częstego sprawdzania obserwowanych kont.
3. Biblioteki treści komercyjnych i reklam pozwalają sprawdzić niezależne przykłady. Zachowywać, czy rekord mówi o partnerstwie twórcy, promocji własnej czy płatnej dystrybucji. W demo dopuszczamy oznaczony import ręczny. Automatyczny dostęp wymaga odpowiedniego interfejsu i uprawnień. [TikTok Commercial Content Library](https://support.tiktok.com/en/account-and-privacy/personalized-ads-and-data/commercial-content-library/) · [TikTok Commercial Content API](https://developers.tiktok.com/docs/en/commercial-content-api-query-commercial-content) · [Meta Ad Library](https://www.facebook.com/ads/library/) · [YouTube Branded Content](https://support.google.com/youtube/answer/17596007?hl=en-GB)
4. Raportować liczbę kwalifikowanych kont wg platformy i metody, nowe konta na godzinę poszukiwań, pokrycie odłożonej listy kontrolnej, udane skany względem zaplanowanych, wiek ostatniego sukcesu, zakres tekst/obraz/audio i duplikaty przekazu. Losować materiały także spoza alertów. Do oceny jakości rozdzielać całe kampanie pomiędzy strojenie i test, osobno raportować każdą platformę. Zakres pilota jest znany. Całkowita liczba polskich finfluencerów pozostaje nieustalona.

Stan źródeł jest nierówny. Plik esma_mif_passport_to_PL.json zawiera 26 wpisów z ae_entityTypeCode=CSP, siedzibą Head office i bez kraju przyjmującego. Do ustaleń o usługach inwestycyjnych trzeba dobrać właściwy rejestr, podmiot, kraj i usługę oraz zapisać datę weryfikacji. Lokalny wykaz 712 notyfikacji KNF daje kandydatów do sprawdzenia. Brak wpisu lub zgodność nazwy nie wystarczają do zarzutu. [Zestaw źródłowy](../data/probe-snapshots/knf/esma_mif_passport_to_PL.json) · [Notyfikacje KNF](../data/probe-snapshots/knf/knf_notyfikacje_zagr_FI.json)

## Stan aplikacji po integracji

Od wieczornej implementacji worker Compose sam uruchamia wyszukiwanie po polskich tematach w Apple Podcasts i PeerTube. Zachowuje odkrytych twórców oraz sprawdza kolejne odcinki RSS również po wypadnięciu z wyników wyszukiwania. Dodatkowa fraza zmienia się w czterogodzinnych oknach. Powrót do znanego twórcy i pierwsze odkrycie mają osobne liczniki. Proces na żywo może odsłuchać początek jednej wybranej audycji na skan. Aktywacja ścieżki zależy od dozwolonego źródła, dostępu do publicznego audio i zainstalowania modeli. Zakres pomiaru jest widoczny w karcie. Pozyskanie materiałów z prywatnego konta i systematyczne pokrycie wszystkich polskich twórców pozostają poza zakresem. [Odbiór demonstracji](DEMO-ODBIOR.md)

## Oszczędne budowanie bazy kanałów YouTube

Decyzja J z 21 XI 2026: zakres to Polska. Szukamy po polsku i po tematach inwestycyjnych, budujemy trwałą bazę kanałów i ją monitorujemy. Poniższe zasady obowiązują adapter collectors/youtube.py i każdego agenta, który uruchamia skan.

1. **Kwota.** Darmowa pula YouTube Data API v3 to 10 000 jednostek na dobę i odnawia się o północy czasu pacyficznego, czyli o 9:00 czasu polskiego. Strona wyszukiwania kosztuje 100 jednostek, odczyt filmów, kanałów lub listy przesłanych po 1 jednostce za 50 pozycji. Każdy przebieg ma jawny budżet i wpis w księdze kwoty. Testy nigdy nie wychodzą do sieci.
2. **Odkrywanie tylko tam, gdzie daje nowe polskie kanały.** Pomiar z 21 XI na równym budżecie 800 jednostek: frazy tematyczne dały 152 polskojęzyczne kanały, nazwy firm 51, frazy promocyjne 52 przy 300 jednostkach. Domyślny zestaw to polskie frazy tematyczne i promocyjne. Nazwy firm zostają tylko w polskim brzmieniu z kontekstem, na przykład „XTB opinie” lub „konto maklerskie XTB”. Zapytania eToro, Trading 212 i Interactive Brokers nie zwróciły żadnego kanału z listy referencyjnej i wypadają z domyślnego zestawu.
3. **Zawsze regionCode=PL i relevanceLanguage=pl, a o języku decyduje treść.** Kanał dostaje trwałą etykietę języka po pierwszym odczycie. Kanały niepolskie trafiają na listę pominięć i nie zużywają już kwoty ani pobrań mediów.
4. **Kanał raz odkryty jest monitorowany tanio.** Nowe filmy znanego kanału czytamy z listy przesłanych za 1 jednostkę na 50 filmów albo z kanału Atom bez kwoty. Wyszukiwanie służy do znajdowania nowych kanałów, a nowe filmy pochodzą z monitoringu.
5. **Podział budżetu przebiegu.** Najpierw monitoring znanych polskich kanałów z sygnałem promocji, potem pozostałych znanych, na końcu odkrywanie. Zapytanie, które w dwóch kolejnych przebiegach nie przyniosło nowego polskiego kanału, schodzi na rzadszy cykl. Kursor stron jest zapisywany, więc przerwany przebieg wznawia się bez powtórnych wydatków.
6. **Pamięć podręczna.** Okno dat z dokładnością do dnia, wyniki wyszukiwania ważne dobę, statystyki odświeżane osobnym tanim odczytem. Powtórka tego samego zapytania w tej samej dobie nie kosztuje nic.
7. **Kolejność pobierania mediów.** Transkrypcja najpierw dla filmów z dowodem relacji w opisie, potem z nazwą firmy z rejestru, potem według zasięgu. YouTube ogranicza pobieranie napisów z jednego hosta. Po odmowie czekamy z długą przerwą i nie zmieniamy tożsamości klienta.
8. **Drugi klucz.** J dopuścił podpięcie klucza z drugiego projektu Google na czas hackathonu. Klucze leżą poza repo w ~/.config/investwatch/. Każdy klucz ma własny wiersz w księdze kwoty. Warunki YouTube API nie przewidują mnożenia projektów dla zwiększenia puli, więc docelowo UKNF powinien wystąpić o podwyższenie kwoty.
9. **Raport przebiegu.** Zużyte jednostki, nowe polskie kanały na 100 jednostek dla każdej rodziny zapytań, liczba kanałów w bazie i liczba filmów czekających na transkrypcję.
