# Próba Y · niezależna lista referencyjna kanałów YouTube

> **Zakaz.** Tej listy, nazw, uchwytów ani ID kanałów nie wolno przekazywać adapterowi wyszukiwania, seedom, `tools/watch_sources.json`, konfiguracji kolektorów ani promptom linii B. Lista służy wyłącznie do porównania **po** skanie. Każde użycie listy do strojenia zapytań unieważnia próbę Y i wymaga nowej listy z innego źródła.

Zamrożono 21 listopada 2026, przed skanem YouTube. Skrót pliku [channels.json](channels.json) zapisano w [FREEZE.json](../FREEZE.json). Protokół ogólny: [PROTOKOL.md](../PROTOKOL.md).

## Źródło i dobór

Źródłem członkostwa jest raport [InvestTube, październik 2026](https://img1.wsimg.com/blobby/go/2a4f2eb6-0235-4b97-bba5-2fbf3943288a/InvestTube_pazdziernik26.pdf). Wydawcy to Polak Inwestor (iKsync) i Fundacja Invest Cuffs, Warszawa, listopad 2026. Raport pobrano 21 XI 2026 ze strony [polak-inwestor.pl/rankingi](https://polak-inwestor.pl/rankingi). SHA-256 PDF wynosi `83a199a4…eafaa5f`. Kontrolnie użyto raportu za wrzesień 2026, którego skrót jest w JSON. Metodologia InvestTube uwzględnia wyświetlenia wyłącznie długich filmów opublikowanych w badanym miesiącu. Wyklucza Shorts, filmy dopalane reklamami i oficjalne kanały domów maklerskich. Raport analizuje 83 kanały.

- **Populacja:** wszystkie 83 kanały raportu październikowego.
- **Kwalifikuje się:** kanał występuje w co najmniej jednej zakładce inwestycyjnej InvestTube (INWESTOWANIE, TRADING, POLSKA GIEŁDA, RYNKI GLOBALNE), ma ustalone trwałe ID i jest pojedynczym kanałem. Wynik: 69 kanałów.
- **Wątpliwy:** występuje tylko w zakładkach MAKRO/GOSPODARKA, MEDIA, WEB3 lub MARKI OSOBISTE, jest agregatem sieci albo ma nieustaloną tożsamość. Wynik: 14 kanałów, każdy z powodem.
- **Ranking:** kanały kwalifikujące się według publicznego licznika subskrybentów.
- **Okno:** członkostwo obejmuje filmy z 1–31 X 2026. Liczniki odczytano 21 XI 2026 w godz. 18:28–18:36 UTC.
- **Język:** przyjęty za zakresem raportu („ranking polskich kanałów”). Języka poszczególnych filmów nie sprawdzono.

Liczbę subskrybentów odczytano z publicznego licznika YouTube w wynikach wyszukiwania kanałów po dokładnej nazwie z raportu. YouTube zaokrągla licznik do trzech cyfr znaczących. Dla 11 dużych kanałów pobrano również stronę kanału (`subscribersCrossCheck`). Własny licznik potwierdzono tam dla 9 z nich. Na stronach Piotra Ostapowicza i Independent Trader widać tylko liczniki polecanych kanałów, więc dla nich zostaje wartość z wyników wyszukiwania. Wyszukiwanie po nazwie posłużyło wyłącznie do identyfikacji kanału już wybranego przez raport. Nie decydowało o członkostwie.

## Top 5 · wariant główny

| # | Kanał (nazwa w raporcie) | Subskrybenci 21 XI 2026 | Zakładki inwestycyjne |
|---|---|---|---|
| 1 | Marcin Iwuć | 446 tys. | INWESTOWANIE |
| 2 | Piotr Ostapowicz | 219 tys. | INWESTOWANIE, TRADING (+ WEB3) |
| 3 | Pankracy | 212 tys. | INWESTOWANIE |
| 4 | Zawód Inwestor | 208 tys. | RYNKI GLOBALNE, INWESTOWANIE, TRADING |
| 5 | Independent Trader | 201 tys. | RYNKI GLOBALNE, INWESTOWANIE (+ MEDIA) |

Wrażliwość rankingu: po wyłączeniu kanałów z zakładki WEB3 (`cryptoDominant`) piąte miejsce zajmuje Tomasz Trela – Twój człowiek na Wall Street (177 tys.) zamiast Piotra Ostapowicza. W wariancie szerokim, ze wszystkimi zakładkami, pięć pierwszych pozycji zajmują kanały z grupy „wątpliwy”: Globalista TV (928 tys.), Damian Olszewski (661 tys.), Maciej Wieczorek (534 tys.), namzalezy.pl (520 tys.) i didaskalia (454 tys.). Dlatego definicję „kanału związanego z inwestowaniem” zamrożono przed skanem. Odbiór Y raportuje wariant główny, a pozostałe dwa jako analizę wrażliwości. Miejsca 3–5 dzieli 11 tys. subskrybentów. Zaokrąglenie YouTube ich nie zamienia, ale zmiana licznika w ciągu kilku tygodni może zmienić kolejność.

## Ograniczenia i konflikt interesów

- InvestTube współredaguje Marcin Wenus (Invest Cuffs), który prowadzi kanał Comparic Rynki. Ten kanał występuje na liście i jest już seedem w repozytorium (`alreadySeededInRepo: true`). Na stronach XTB w archiwum M2 widnieje nagroda „dom maklerski roku według Invest Cuffs 2025”. iKsync deklaruje pośrednictwo między markami a twórcami. Ranking może więc pomijać twórców spoza tego środowiska.
- Ranking mierzy bieżące wyświetlenia, a nie subskrypcje. Kanał z dużą bazą subskrybentów, ale słabym miesiącem, mógł wypaść z raportu. Kanały korporacyjne są wykluczone z założenia, co odpowiada zakresowi M1, a nie M2.
- Ostatnie badanie SII OBI 2024 i strona sii.org.pl zwróciły HTTP 403. Zestawienie freenance.io podaje nieopisane, niedatowane przybliżenia. Żadnego z tych źródeł nie użyto do członkostwa. Mamy więc jedno źródło członkostwa i jedno źródło liczników.
- Jeden kanał (Comparic Media Group, agregat) nie ma ustalonego ID. Pozostałe 82 kanały mają ID.

## Jak mierzyć odbiór Y

Po skanie z linii B porównaj zbiór trwałych ID kanałów odkrytych przez wyszukiwarkę z polem `channelId` z tej listy. Raportuj liczbę znalezionych z top 5 (cel ≥ 4/5), wynik dla 69 kanałów kwalifikujących się oraz liczbę wszystkich odkrytych twórców. Kanał już seedowany (Comparic Rynki) nie liczy się jako odkrycie. Podaj budżet zapytań, osobno dla zapytań tematycznych i markowych.
