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

Harmonogram można wstrzymać przez `systemctl --user disable --now investwatch-watch.timer`. Konta dodaje się w tools/watch_sources.json, po weryfikacji tożsamości i tego, że profil jest publiczny. Zmiana nazwy TikToka wymaga aktualizacji i zachowania poprzedniego aliasu. Operacyjna baza przechowuje konkretne obserwacje. Adaptacja do SQL aplikacji i jeden wspólny harmonogram są zadaniem linii source-adapters, która przy przejęciu pracy powinna wyłączyć równoległy harmonogram pilota.

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

## Co zmniejsza dziś szanse na maksimum

| Kryterium | Średnia trzech ocen planu / maksimum | Co ma zobaczyć jury, by uzasadnić pełną ocenę |
|---|---:|---|
| Technologia i gotowość | 27/30 | Nowy lub zmieniony dokument trafia do sprawy. Replay działa po odłączeniu sieci, trzy czyste starty na docelowym sprzęcie, zmierzone opóźnienie i RAM, sprawny dashboard i alert |
| Proces pracy z AI | 19/20 | Dla trzech linii powiązanie wymogu, kontraktu, faktycznej zmiany, niezależnej recenzji i powtórzonego testu. Pokazać wadę wykrytą przez recenzenta i skutek poprawki |
| Architektura | 18,7/20 | Jeden zapis wyniku i zdarzenia, brak dublowania po awarii, reconnect, zmiana decyzji przez dwóch operatorów, działający Compose i wyniki skanów zależności |
| Zgodność | 17,7/20 | Trzy używalne raporty, rzeczywisty przypadek transgraniczny, kompletna lista 19 kontroli M2 z wiarygodnymi stanami, kontrola M3 z adekwatnym rejestrem. Lokalny model kontra reguły na odłożonych ręcznych etykietach, FP/FN po zmianie progu |
| Atrakcyjność | 9/10 | W dwie minuty analityk wskazuje konkretny cytat, pokazuje geometrię ostrzeżenia na telefonie i wpływ aneksu na ustalenie. Juror potrafi otworzyć inny przypadek |

Stan źródeł jest nierówny. Plik esma_mif_passport_to_PL.json zawiera 26 wpisów z ae_entityTypeCode=CSP, siedzibą Head office i bez kraju przyjmującego. Do ustaleń o usługach inwestycyjnych trzeba dobrać właściwy rejestr, podmiot, kraj i usługę oraz zapisać datę weryfikacji. Lokalny wykaz 712 notyfikacji KNF daje kandydatów do sprawdzenia. Brak wpisu lub zgodność nazwy nie wystarczają do zarzutu. [Zestaw źródłowy](../data/probe-snapshots/knf/esma_mif_passport_to_PL.json) · [Notyfikacje KNF](../data/probe-snapshots/knf/knf_notyfikacje_zagr_FI.json)
