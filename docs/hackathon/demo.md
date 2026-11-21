# Pokaz dla jury UKNF

Scenariusz opiera się na datowanym replayu z 21 XI 2026. Liczby pochodzą z bazy podglądu (`/v1/overview` o ok. 21:50 UTC). Kolejka „Co wymaga sprawdzenia” ma 4 filmy, rejestr reklam M1 ma 269 pozycji, oferty M2 31, oferty M3 2, a „Niepełne dane” 241, w tym 1288 materiałów czeka na transkrypcję. Kroki oznaczone **[po wpięciu]** wymagają kart M2 i M3 z commitu `59a386a` w bazie pokazu. Przed próbą sprawdź, czy już się pojawiły. Uruchomienie opisuje [README](../../README.md), a granice wyniku [odbiór UKNF](../ODBIOR-UKNF.md).

Adres pulpitu po `sh ops/demo/start.sh` to `http://127.0.0.1:8769/theme-preview/`. W tekście nazywamy go dalej „pulpitem”.

## Wersja 2 minuty

| Czas | Klik | Powiedz |
|---|---|---|
| 0:00–0:25 | **Co wymaga sprawdzenia** → „Freedom24 Alternatywy: Którego brokera wybrać? (2026)” (ForexMind). Pokaż **Dlaczego tutaj**, potem kliknij **Otwórz w filmie od 0:15** | „System sam znalazł ten film w YouTube. W opisie jest skrócony link przy XTB i kod twórcy TRADEXTB. Oznaczenia współpracy nie ma w opisie, w całej mowie (0:00–3:24) ani w sprawdzonych kadrach. W 15. sekundzie twórca mówi: »znajdziesz linki do specjalnych ofert w opisie poniżej«. To przesłanka do kontroli, a nie zarzut. Karta podaje też niewinne wyjaśnienie.” |
| 0:25–0:50 | **Rejestr reklam M1** → szukaj „Konopskyy” → film z „[reklama] Zarejestruj się w XTB z kodem KONOP”. Potem szukaj „Comparic” → „ARABIA SZYKUJE SIĘ NA WOJNĘ…” | „Jawna współpraca to poprawne zachowanie twórcy, więc trafia do rejestru, a nie do alarmu. Tak jest u Konopskyy’ego (2,1 mln subskrybentów) i w Kanale Zero. Comparic ma w opisie link i kod XTB bez słowa »reklama«, co wyglądało na podejrzenie. W 614 sekundzie pada jednak: »znajdziecie u partnera tego odcinka XTB«. Podejrzenie obaliła mowa.” |
| 0:50–1:10 | **Kalibracja** → przesuń suwak z 60 na 95 | „Na 26 materiałach z 20 kampanii przy progu 60 są 4 trafienia i 0 fałszywych alarmów. Przy 95 dwa trafienia przechodzą w przeoczenia, a koszt 2×FN+FP rośnie z 0 do 4. Poprzednie reguły dawały 7 fałszywych alarmów. Żółty pasek mówi uczciwie, że to oceny agentów na zbiorze strojenia, a nie walidacja ekspercka.” Kliknij **Wróć do obowiązującego** |
| 1:10–1:30 | **Źródła** → kafle YouTube, TikTok, Instagram, Facebook | „YouTube: 381 kanałów, 1345 materiałów i kwota pod kontrolą. TikTok: profile znalezione z odsyłaczy w opisach YouTube, 64 posty, sam podpis. Facebook i Instagram: automatyczny odczyt bez tokenu Meta jest zablokowany i tego nie obchodzimy. Widać datowaną próbkę z Biblioteki Reklam, import ręczny i następny krok: Ad Library API albo Meta Content Library.” |
| 1:30–1:45 | Wróć do karty ForexMind → **Decyzja** → status i uzasadnienie → zapisz | „Decyzja ma rewizję i uzasadnienie. Druga karta pulpitu odświeża się przez WebSocket.” |
| 1:45–2:00 | **Co wymaga sprawdzenia** → **Pobierz raport** | „Raport M1 ma kolumny wymagane przez UKNF: firma, podmiot reklamujący, treść, URL, platforma, data publikacji i odczytu oraz decyzja.” |

## Wersja 5 minut

Wersja 5-minutowa zawiera całą wersję 2-minutową i dodaje poniższe kroki po kroku 0:50.

1. **M2, ETF XTB.** **Oferty WWW M2** → „Fundusze ETF w aplikacji XTB” (trasa do przeglądu, 60 pkt). Powiedz: „Strona obiecuje dochód z dywidend. Ostrzeżenie dotyczące ETF stoi w osobnym miejscu, a na telefonie przy wzmiance o dywidendach jest poza kadrem. Zrzut i DOM mają odcisk wersji. Ocenę istotności podejmuje analityk.” [Manifest ETF](../../data/probe-snapshots/m2/manifests/xtb-etf.json)
2. **M2, para XTB akcje i ETF [po wpięciu].** Dziś karta akcji XTB ma w bazie pokazu trasę „bez sygnału”. Po wpięciu kart rynkowych obie strony dostają przesłankę ID 3. Akcje mają tylko ostrzeżenie CFD, które nie dotyczy akcji, a ETF ma ostrzeżenie daleko od dywidend ([rekord M2](../lanes/2026-11-21-fable-e-m2.md)).
3. **M2, Noble IKE [po wpięciu].** Strona `noblesecurities.pl/klient-indywidualny/rachunek-ike/`. Cytat „Zyskaj więcej na przyszłość, inwestując w akcje, obligacje i ETF-y bez podatku od zysków kapitałowych.” stoi bez ryzyka tego samego produktu, a korzyść podatkowa bez zastrzeżenia, że zależy od sytuacji klienta ([ocena M2](../../fixtures/labeled/m2-agent-eval.json)).
4. **M3, kontrola uprawnionego.** **Oferty M3** → „DM BOŚ · portfel rekomendowany”. Powiedz: „Oferta ma wszystkie cechy doradztwa, ale wykaz KNF podaje zezwolenie z pozycją 5, czyli doradztwem. To kontrola przed fałszywym alarmem.” Potem „FinanceWell · ustalenie tożsamości”: kolizja nazw, system nie wybiera podmiotu po samej nazwie ([próba M3](../archiwum/M3-WERYFIKACJA-2026-11-21.md)).
5. **M3, rdmwm.pl [po wpięciu].** Jedyna sprawa skierowana na 31 materiałów z 29 domen. Cytat „Na podstawie tych danych dobieramy proporcje między akcjami, obligacjami…” dotyczy personalizacji i doboru instrumentów. Operatora strony nie ustalono, więc karta prosi o ustalenie podmiotu, a nie stawia zarzutu ([rekord M3](../lanes/2026-11-21-fable-f-m3.md)).
6. **Import Meta.** **Dodaj dowód** → „Wgraj zapisaną stronę Biblioteki Reklam Meta lub profilu Instagram” → plik `fixtures/raw/discovery/social-2026-11-21/alt/metaadlib-browser-body.txt` → **Wgraj do analizy**. Powiedz: „Tak analityk dodaje dziś to, czego nie da się czytać automatycznie. Plik nie jest otwierany ani wykonywany, czytamy z niego tylko tekst.” Na próbie sprawdź, czy import nie dubluje 22 reklam z próbki.
7. **Niepełne dane.** Powiedz: „Tu trafia to, czego system nie mógł zbadać do końca, np. film bez transkrypcji. Taki film nie trafia do alarmu, dopóki nie zbadamy mowy.”
8. **Alert w drugiej karcie.** Otwórz drugą kartę pulpitu. Zdarzenie `high_risk` pojawia się, gdy skan przenosi sprawę do kolejki. Decyzja z kroku 1:30 wysyła zdarzenie `case`. Baner `high_risk` najpewniej wywoła start z `--reset` przy otwartej drugiej karcie (do potwierdzenia na próbie).

## Lista kontrolna przed pokazem

- [ ] `sh ops/demo/start.sh` kończy się kolejką 4 filmów (7M0rC6-Rueo, AqXHkxDzSDI, OIyPE0z2mng, ZJrT-X08Xwc). Zimny start trwa kilka minut, więc uruchom go wcześniej. Czysty stan daje `--reset`.
- [ ] Paczka mediów `.runtime/dist/replay-media-2026-11-21.tar.gz` z `.sha256` leży na komputerze pokazu. Bez niej kolejka jest pusta.
- [ ] Sieć odłączona: pulpit, karty i zrzuty działają. Harmonogram live jest wyłączony w trybie pokazu.
- [ ] Na Macu wykonano procedurę z [ops/mac/README.md](../../ops/mac/README.md). Do chwili zapisu nie była uruchamiana.
- [ ] Przejście 2-minutowe na 1440 px i 390 px. Druga karta otwarta.
- [ ] Zapisz rewizję (`git rev-parse HEAD`), sprzęt i czas startu. Otwórz [PDF](../../presentation/InvestWatch.pdf).

## Wariant awaryjny

1. **Bez Dockera:** `sh ops/demo/start-local.sh`, ten sam stan i ta sama paczka. Zatrzymanie: `--stop`.
2. **Bez działającej kolejki:** ten sam datowany replay na drugiej maszynie albo podgląd API z gotową bazą.
3. **Bez pulpitu:** zrzuty z [tests/ui/screens/2026-11-21-r3/](../../tests/ui/screens/2026-11-21-r3/) w kolejności scenariusza: `1440-2-karta-flagi-momenty.png`, `1440-4-rejestr-reklam.png`, `1440-7-kalibracja.png`, `1440-6-zrodla.png`, `1440-9-oferty-m2.png`, `1440-10-oferty-m3.png`.

## Trudne pytania jury

| Pytanie | Odpowiedź |
|---|---|
| Gdzie Facebook i Instagram? | Bez tokenu Meta strony kończą się wyzwaniem 403 albo ścianą logowania, a tego nie obchodzimy ([próby](../lanes/2026-11-21-fable-k-social.md)). Pokazujemy datowaną próbkę (22 reklamy, 6 postów IG) i import ręczny. Adapter Ad Library API czeka na token, który UKNF może uzyskać jako instytucja. |
| Na czym opiera się trafność? | M1: 26 materiałów z 20 kampanii, FP 0 i FN 0 wobec FP 7 i FN 4 dla poprzednich reguł. Pozytywne są jednak tylko 3 kampanie jednego reklamodawcy, etykiety dały dwa modele Claude, a to zbiór strojenia ([WYNIK-M1](../../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md)). Deklarujemy przesiew do przeglądu. Pierwszym krokiem pilota powinny być etykiety ekspertów UKNF na nowych kampaniach. |
| M2 i M3 też? | M2: 25 stron 11 firm, etykiety agenta zapisane przed pierwszym uruchomieniem reguł. Przy progu 30 wynik to TP 9, FP 1, TN 12, FN 3. M3: 31 materiałów. Reguły v1 na ślepo dały TP 0, FP 3, FN 1. V2 poprawiono na tym samym zbiorze, więc nie jest to wynik niezależny. |
| M3 ma jedną sprawę? | Tak. Z 31 materiałów skierowano jeden (rdmwm.pl), a 15 wymaga uzupełnienia danych. Wolimy jedną dobrze udokumentowaną przesłankę niż listę zarzutów. Operatora strony system każe ustalić, nie przesądza go. |
| YouTube ToS i transkrypcje? | Odkrywanie i metadane idą przez oficjalne Data API v3 z księgą kwoty. Napisów cudzych filmów oficjalne API nie udostępnia. Prototyp pobiera lokalnie i powoli publiczne oryginalne napisy (yt-dlp), co wykracza poza warunki YouTube. We wdrożeniu potrzebna jest zgoda platformy albo ASR z uprawnionego źródła ([kontrakt, N1](../lanes/2026-11-21-fable-h-kontrakt.md)). |
| Czemu reguły, a nie LLM? | Każda flaga musi mieć cytat i lokalizator, który analityk sprawdzi. Qwen 9B i 27B nie wniosły nic ponad reguły w M1 ([porównanie](../lanes/2026-11-21-fable-d-porownanie.md)). Lokalny E5 klasyfikuje typ materiału (30/57 wobec 13/57 dla słownika) jako cechę opisową, bez wpływu na decyzję ([rekord AI](../lanes/2026-11-21-fable-ai-inferencja.md)). |
| Jak to skalować przy SQLite? | Dziś jest jedno stanowisko: SQLite z kolejką Huey, dzierżawą zadań i odzyskaniem po awarii workera. Wzrost obsłużą Postgres i osobne workery na kolejce, bez zmiany kontraktu i adapterów. Ścieżka wzrostu: [architektura](../ARCHITEKTURA.md). |
| Co jest replay, a co live? | Pokaz to datowany replay z 21 XI: 1300 materiałów z Data API, 45 z Atom, 17 filmów z mowami i kadrami, 64 posty TikToka, 22 reklamy i 6 postów Meta oraz 3 strony M2. Live włącza `sh ops/demo/start.sh --live` ze skanem co 4 h i kluczem YouTube. Na żywo podczas pokazu nie skanujemy, bo ryzykujemy 429 i kwotę. |
