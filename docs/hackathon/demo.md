# Dwuminutowy pokaz dla UKNF

J prowadzi pokaz na stanowisku pod `/theme-preview/`. Przygotuj odtworzenie skanu, kartę ETF, ofertę DM BOŚ i klip **Od czego zacząć?**. Zapisz odcisk użytej wersji. [Próba offline](../../tests/offline/README.md) · [Brief UKNF](../zrodla-uknf/BRIEF.md)

| Czas | Co pokazać | Co widzi jury |
|---|---|---|
| 0–40 s | Wybierz filtr **Oznaczone do sprawdzenia**, otwórz ofertę ETF XTB i rozwiń **Korzyść a istotne ryzyko** (kryterium 3). Otwórz zrzut i odpowiadający mu DOM dla telefonu. | Reguła wskazała deklarację o dochodzie z dywidend i ostrzeżenie dotyczące tej samej oferty ETF. Ramki tekstu dzieli 384,5 CSS px na komputerze, 1037 na tablecie i 921 na telefonie. Na mobilnym ujęciu po przewinięciu do dywidend wzmianka jest widoczna, a ostrzeżenie znajduje się poza kadrem. Otwórz drugie ujęcie, żeby pokazać ostrzeżenie. |
| 40–66 s | Przejdź do rzeczywistej oferty doradztwa DM BOŚ. Rozwiń kontekst sugestii E5, potem otwórz dowód z rejestru. | Cytat „My podpowiadamy co kupić i sprzedać, Ty decydujesz” i wersja modelu prowadzą do źródła. Odczyt KRS i datowany zakres uprawnienia w pozycji 5 pomagają ocenić, czy sprawa wymaga dalszych czynności. |
| 66–96 s | W klipie **Od czego zacząć?** kliknij 0,33–3,60 s. W **Źródłach** pokaż jedną drogę odkrycia rzeczywistego twórcy. | Vosk odnalazł zachętę do otwarcia rachunku w mowie. Wynik reguł rośnie z 12 do 74 po dodaniu transkrypcji syntetycznego klipu. Droga odkrycia rzeczywistego źródła pokazuje katalog, odcinek lub odsyłacz prowadzący do profilu. |
| 96–120 s | Wróć do ETF. Zapisz uzasadnienie w **Decyzji** i pokaż wpis w historii. Gdy zostało kilka sekund, zmień próg w **Kalibracji**. | Decyzja ma rewizję i uzasadnienie. Suwak przelicza FP, FN i koszt `2 × FN + FP` na tej samej próbce z roboczymi etykietami. |

## Zapis dowodu ETF

Strona XTB podaje „Rozszerz swoje źródła dochodu o dywidendy wypłacane przez fundusze ETF w które zainwestowałeś.” W odrębnym elemencie widnieje „Oferowane instrumenty finansowe są ryzykowne.” Pomiar dotyczy twierdzenia o dochodzie. Nagłówek „0% prowizji” opisuje koszt. Reguła kieruje materiał do przeglądu. Ocenę istotności i czytelności podejmuje analityk. [Strona XTB](https://www.xtb.com/pl/etf)

Odczyt Chromium z 21 listopada 2026 o 16:58 UTC ma SHA-256 wersji `03314e378d10e0b031af9cc750badab85f05cab5d3370083ae74a6b02da65912`. Zrzuty i DOM wiążą pomiar z określoną szerokością i stanem przechwycenia. [Manifest ETF](../../data/probe-snapshots/m2/manifests/xtb-etf.json) · [Zrzut telefonu przy wzmiance o dochodzie](../../data/probe-snapshots/m2/assets/21cb517dc326ff191dfcd97475298a5e41892545b6be0f70ad598844ca8a8e2b.png) · [DOM przy wzmiance](../../data/probe-snapshots/m2/assets/83107f356d799621d24147c505da975066f772f54228c09d6b43aa484d1487a1.json) · [Zrzut telefonu przy ostrzeżeniu](../../data/probe-snapshots/m2/assets/65a2c62c81064eecdfbb4e0315a64b17f7528694f355d4b98afa23390f326536.png)

## Przygotowanie i wariant offline

1. Na maszynie prezentacji przejdź od skanu do decyzji i otwórz oba ujęcia ETF. Sprawdź pulpit przy 1440 i 390 px. Na osobnej bazie wykonaj próbę konfliktu rewizji i zapis odpowiedzi w fikcyjnej sprawie. [Instrukcja środowiska](../../ops/demo/README.md)
2. Bez internetu użyj przycisku **Odtwórz skan**, lokalnego klipu i zarchiwizowanych stron. W **Źródłach** pokaż czas obserwacji, tryb odczytu i ostatni udany dostęp przy wyniku częściowym.
3. Pokaż granice wyniku. W M2 „brak danych” oznacza potrzebę uzupełnienia materiału. W M3 kolizja nazw wymaga potwierdzenia tożsamości. Próbka kalibracyjna zawiera starsze wycinki i służy do sprawdzenia wpływu progu. Ocena jakości na nowych kampaniach wymaga niezależnego zbioru.
4. Zapisz rewizję, sprzęt, czas i wynik próby startu offline. Przed pokazem sprawdź PDF, README oraz obraz i dźwięk nagrania zapasowego. [Odbiór demo](../DEMO-ODBIOR.md) · [Prezentacja PDF](../../presentation/InvestWatch.pdf)
