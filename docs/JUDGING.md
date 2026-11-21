# Rundy sędziów — UKNF #InvestWatch (ocena planu, 21.11.2026)

## Ocena po konsultacji z mentorem i przeglądzie dowodów

**Wersja 3 planu realizacji uzyskała 91, 91 i 92 punkty na 100. Średnia 91,3.** Są to warunkowe oceny trzech agentów oceniających projekt po zaliczeniu opisanych bramek. Zewnętrzne jury UKNF przyznaje do 10 punktów. Prawdopodobieństwa uzyskania tych punktów przez obecne repozytorium nie szacowaliśmy.

| Oceniany dokument | IT | Nadzór | Proces AI i walidacja | Średnia |
|---|---:|---:|---:|---:|
| Plan po konsultacji · przed naradą | 79 | 75 | 76 | 76,7 |
| Plan realizacji, wersja 1 | 80 | 85 | 83 | 82,7 |
| Plan realizacji, wersja 2 | 89 | 89 | 89 | 89,0 |
| Plan realizacji, wersja 3 | **91** | **91** | **92** | **91,3** |

W naradzie SOL high reprezentował inżynierię, TERA xhigh nadzór, TERA high analizę modeli. Dyskutowali bezpośrednio m.in. o tym, co udowadnia osadzenie filmu, jak mierzyć wyniki na małej próbce i co można uruchomić na współdzielonym CPU. Sędziowie pracowali oddzielnie. Nie dostali docelowego progu ani punktacji innych osób. Bazę oceniali SOL high, TERA high i SOL medium. Trzy kolejne wersje oceniał ten sam odrębny panel SOL high, TERA xhigh i SOL high. Zachowanie tego panelu pozwala prześledzić, czy konkretna poprawka usunęła konkretny zarzut. Sędziowie w powtórnych ocenach znali swoje poprzednie uwagi. To wewnętrzna procedura projektowa, bez kalibracji względem jurorów konkursu.

| Runda / perspektywa | Technologia /30 | Proces z AI /20 | Architektura /20 | Zgodność /20 | Atrakcyjność /10 |
|---|---:|---:|---:|---:|---:|
| Baza · IT | 25 | 13 | 17 | 15 | 9 |
| Baza · nadzór | 23 | 13 | 16 | 15 | 8 |
| Baza · AI | 25 | 11 | 17 | 15 | 8 |
| Wersja 1 · IT | 24 | 18 | 16 | 14 | 8 |
| Wersja 1 · nadzór | 24 | 18 | 18 | 17 | 8 |
| Wersja 1 · AI | 25 | 18 | 17 | 15 | 8 |
| Wersja 2 · IT | 27 | 19 | 18 | 16 | 9 |
| Wersja 2 · nadzór | 26 | 18 | 18 | 18 | 9 |
| Wersja 2 · AI | 26 | 19 | 18 | 17 | 9 |
| Wersja 3 · IT | **27** | **19** | **19** | **17** | **9** |
| Wersja 3 · nadzór | **27** | **19** | **18** | **18** | **9** |
| Wersja 3 · AI | **27** | **19** | **19** | **18** | **9** |

### Co zmieniło werdykt

- **Baza → wersja 1.** Zarzuty dotyczyły braku dowodu automatycznego pozyskiwania na platformie z briefu oraz niekonkretnego procesu AI. Rada nadzorcza odrzuciła oEmbed pojedynczego filmu jako dowód wykrywania postów. Rada techniczna zaproponowała publiczny widget profilu. Dwa prawdziwe odczyty polskiego TikToka dały 10 adresów i podpisów, dwa odczyty YouTube po 15 publikacji. Plan dostał kontrakty, zachowanie po restarcie i standard przeglądu zmian.
- **Wersja 1 → 2.** Sędziowie nie uznali transportu danych za dowód jakości aplikacji. Pobraliśmy rzeczywisty materiał M2 w trzech rozmiarach i ofertę doradczą. Z domeny XTB odkryliśmy trzy produkty. Analiza dwóch aktualnych publikacji dała ten sam opis z deklaracją partnerstwa. Do planu weszły pomiar zakresu automatyzacji, porównanie modelu z regułami, test dwóch workerów i próba krótkiej prezentacji.
- **Wersja 2 → 3.** Niezależny przegląd odtworzył fałszywie pozytywną weryfikację manifestu m.in. po usunięciu źródła lub wpisaniu fikcyjnego skrótu. Powstały cztery rzeczywiste PNG i odpowiadające im ekstrakty DOM. Dodatkowa sonda odkryła trzy strony usług BDM. Określiliśmy warunek użycia modelu, działanie przy niekorzystnym wyniku, docelową kompletność danych i czas oczekiwania w kolejce. W krótszej prezentacji są wszystkie trzy moduły.
- **Wynik bazuje na wersji 3.** Punktowany jest plan pełnej realizacji. Potwierdzono treść źródeł i pochodzenie obserwacji na poziomie sond. Na dzień ocen nie zbudowano aplikacji, nie przeprowadzono testu E2E w Compose, nie zebrano zamrożonych ludzkich etykiet i nie uzyskano wyniku jakości M1/M2/M3.
- **Po głosowaniu** poprawiono dodatkowe usterki walidatora dotyczące kompletności indeksu, starszego odczytu geometrii, dat, adresów i rekordów rejestru. Te poprawki nie podniosły przytoczonych punktów. Narzędzie sprawdza lokalną spójność archiwum i wybrane twierdzenia z planu. Skróty nie stanowią zewnętrznego poświadczenia autentyczności źródła.

### Za co jury wciąż odjęło punkty

| Kryterium | Co trzeba pokazać przy odbiorze | Pozostała luka |
|---|---|---|
| Technologia | Automatyczne wykrycie i odświeżenie, działający live/replay, trzy zimne starty, powtarzalna macierz pomyłek | Przy minimum pięciu dodatnich przypadkach jeden błąd zmienia recall o 20 pp. |
| Proces AI | Rzeczywisty niezależny kontrprzykład, naprawa, ponowienie testu na rewizji kandydata i decyzja kapitana | Merytoryczny poziom przeglądu wymaga oceny człowieka; drugi ludzki etykietujący zależy od dostępności. |
| Architektura | Dwa procesy, izolacja renderu, restart, spójna kopia z obiektami, odtworzenie | Jeden host i 20 dokumentów nie dowodzą niezawodności wielowęzłowej. |
| Zgodność | Trzy moduły, dowód dobrej i błędnej decyzji, mapa 19 reguł i faktyczny udział automatycznych wyników | Selektywne profile, ograniczony materiał audiowizualny i niepotwierdzony prospektywny przypadek M3. |
| Atrakcyjność | Juror zmienia warunki sprawy i sprawdza zmianę decyzji na konkretnych dowodach | Odpowiedź firmy i aneks są fikcyjne. Trzeba to jasno zakomunikować w ograniczonym czasie. |

Wykonalność wszyscy ocenili jako ryzykowną. Nadzór podał **5/5 ryzyka**. Pierwszeństwo mają zintegrowana karta do 19:00 oraz offline, wznowienie i wykaz przypadków do 23:30. Jeżeli zespół obetnie zakres lub nie zaliczy bramek, trzeba ponownie ocenić faktycznie dostarczony wariant.

**Identyfikatory ocenionych plików SHA-256:** plan po konsultacji 11d0e0abb3f9dc30fd78d4f42f35c2ff2d41f0babbc6f196d9d664a94502f82c; wersja 1 96ec0ee932c0ff674fc641280d11dc4d61968e833e23bc87a6c3cdaf0295fce6; wersja 2 a683486291257ee1a91154300f7f112331691e9676fe6345e8ceb6cf5c52569c; wersja 3 336b66c76a76cb57c6935623a22b4a6402debd8753eec737fc5a9cb22be8822d. Są to skróty bajtów dokumentu, nie rewizje Git.

[Plan ocenionej wersji](PLAN-REALIZACJI.md) · [Indeks materiałów](INDEKS.md) · [Dwie poprzednie ocenione wersje w archiwum](oceny-wersje-planu.tar.gz) · [Bramka lokalna](../tools/check_plan_evidence.py)

## Wcześniejszy panel przed otrzymaniem załączników

**Wynik: cel ≥95 od każdego sędziego nie został osiągnięty.** Po trzech rundach: 88 / 79 / 83 (średnia 83). Wszyscy sędziowie niezależnie podali realny sufit 88–92 i ocenili wykonalność pełnego planu przez „J + agenci” na 25–35%.

## Metoda

- Trzech sędziów na rundę, każdy to świeży agent (model opus, effort high) bez pamięci poprzednich rund.
- Sędzia dostaje wyłącznie treść zadania (`docs/brief/…Pełna_treść…txt`) i plan (`docs/PLAN.md`). Nie widzi researchu ani uzasadnień.
- Pytanie: ile punktów dostałby projekt zrealizowany dokładnie według planu (deklarowane ograniczenia pozostają ograniczeniami).
- Rubryka = oficjalne kryteria × 10: A technologia i demo 30, B proces z asystentami AI 20, C architektura 20, D zgodność ze specyfikacją 20, E atrakcyjność 10. Wykonalność w czasie jest osobną flagą, poza punktami.
- Persony: S1 zastępca dyrektora Departamentu Informatyki, S2 naczelnik w pionie nadzoru nad rynkiem kapitałowym (autor zadania), S3 ekspert ds. AI Governance i modeli.
- Ograniczenie metody: to symulacja. Sędziowie-agenci oceniają dokument, nie działające demo, i nie znają konkurencji. Prawdziwe jury może ważyć inaczej, zwłaszcza brak automatycznego scrapingu FB/IG/TikTok.

## Wyniki

| Runda | Plan | S1 (IT) | S2 (nadzór) | S3 (AI) | Średnia | Wykonalność (S1 / S2 / S3) |
|---|---|---|---|---|---|---|
| 1 | v1 | 83 | 79 | 79 | 80,3 | żółta 40% / żółta 30% / żółta 35% |
| 2 | v2 | 84 | 78 | 84 | 82,0 | czerwona 25% / czerwona 25% / czerwona-żółta 25% |
| 3 | v3 | 88 | 79 | 83 | 83,3 | czerwona 25% (rdzeń 60%) / żółta 30% / żółta 35% |

Punkty cząstkowe (A/B/C/D/E):

| Runda | S1 | S2 | S3 |
|---|---|---|---|
| 1 | 25/18/15/17/8 | 22/18/17/15/7 | 23/14/17/17/8 |
| 2 | 24/18/16/18/8 | 23/16/17/14/8 | 25/16/17/17/9 |
| 3 | 26/18/17/18/9 | 24/17/17/13/8 | 24/17/17/17/8 |

## Runda 1 (plan v1)

Główne zarzuty:
- FB/IG/TikTok tylko z importu ręcznego i nagrań; ukryta reklama finfluencera (organiczny post) to sedno nadzoru (S2: −9).
- Zbiór 300–400 etykiet w jedną noc jest nierealny, a ewaluacja kołowa, jeśli etykiety robią agenci lub reguły (S3: −4).
- Brak startu offline z modelami w obrazach, brak właściciela schematu bazy, brak logowania i audytu zmian statusu, brak izolacji crawlera (S1: −10).
- `Finding` bez wersji modelu, reguł i progu; brak progu operacyjnego i ablacji (S3).
- Lista 11 standardów bez dowodu, że bramki coś zatrzymały (S3).

Zmiany w v2: rozszerzenie przeglądarki „Zgłoś do InvestWatch”; zbiór ok. 150 realnych próbek oznaczanych przez człowieka, test na próbkach z pendrive'a, ablacja, próg operacyjny; obrazy z modelami, pakiet offline, healthchecki; schemat tylko w `api` (Alembic); JWT, audyt, eksport; izolacja crawlera; pola proweniencji w `Finding`; dziennik zablokowanych scaleń; precyzyjne podstawy prawne; wycięcie SearXNG.

## Runda 2 (plan v2)

Punkty wzrosły nieznacznie (+1,7), a ocena wykonalności spadła do czerwonej: poprawki dodały zakres.

Główne zarzuty:
- Nadal brak automatycznego kolektora choćby jednej platformy z briefu (S2: −9, S1: −2, S3: −4).
- 10 kontenerów, niezdecydowana własność danych, pamięć (S1, S3).
- Protokół etykiet: zakotwiczenie na etykietach agenta, „kappa” człowiek–model nazwana zgodnością oceniających; bramka F1 na ~30 próbkach tonie w szumie (S3).
- Standardy „szeroko, ale płytko” (S2, S3).
- Moduł 3 znajduje to, co KNF już zna (seedy z listy ostrzeżeń); brak MAR art. 20 w module 1 (S2).
- Konsola po restarcie `api`; bramka „High blokuje” bez rejestru wyjątków (S1).
- S3 zakwestionował literę przepisu o czcionce (lit. b zamiast lit. c). Research odczytał lit. c z EUR-Lex; do sprawdzenia przed zamrożeniem reguł.

Zmiany w v3: 8 kontenerów (harmonogram i rejestry w `crawler`), zapis tylko przez `api`; pięć standardów z twardym dowodem, reszta jako „mapowanie”; etykiety na ślepo przed modelem, uczciwe nazwy zgodności, próg per moduł; odkrywanie nowych podmiotów w module 3 przez zapytania frazowe; MAR art. 20; monitor zgłoszonych URL-i; dziennik dowodów z łańcuchem hashy; `/health` przed połączeniem Socket.io; rejestr wyjątków bezpieczeństwa; rozpoznawanie mowy, Telegram i graf poza MVP; freeze o 05:00.

## Runda 3 (plan v3)

- S1: 88. Zarzuty: scraping na scenie z nagrania, automatyczne scalanie bez człowieka, brak OIDC/retencji/RFC 3161, zapis przez REST jako wąskie gardło, whisper w obrazach mimo wycięcia mowy.
- S2: 79. Zarzuty: inspektor sam musi znaleźć post, więc narzędzie „nie wyszukuje, tylko przyjmuje zgłoszenia” (D 13/20); rotacja UA/proxy nie dotyczy kanałów z zadania; metryki zawyżone, bo pozytywy pochodzą z list znanych naruszeń; niezweryfikowane litery przepisów.
- S3: 83. Zarzuty: jeden oznaczający będący autorem reguł, brak krzywej niezawodności, bramka F1 praktycznie nieblokująca, LLM na marginesie, brak pętli zwrotnej od decyzji analityka.

Poprawki po rundzie 3 (plan v3.1, **nieoceniane**): scalenie zatwierdza człowiek; bramka McNemara; krzywa niezawodności i Brier; pętla zwrotna z retreningiem; skan na żywo jako główna ścieżka demo, replay awaryjnie; whisper usunięty z obrazów; pomiar layoutu i teczka PDF przeniesione do fali 2; 40 próbek do oznaczenia przez mentora.

Sugestie sędziów odrzucone świadomie:
- Kolektor Playwright na webowej Meta Ad Library i TikTok Ad Library (S2). Sonda: Meta zwraca 403 z wyzwaniem JS, a robots.txt obu serwisów zakazuje automatu. Obchodzenie zabezpieczeń jest poza naszymi zasadami. Można to odwrócić tylko decyzją UKNF (pytanie do mentora).
- Tryb „sesji przeglądu” w rozszerzeniu, zbierający paczką wszystkie wyrenderowane posty (S2). To automatyczne zbieranie w zalogowanej sesji, czyli ta sama szara strefa. Do rozstrzygnięcia z mentorem.
- Keycloak, Prometheus, RFC 3161 (S1). Poza zakresem 19 h; opisane jako jawne ograniczenia.

## Wnioski

1. **Sufit planu to ok. 88–92**, nie 95–100. Blokuje go jedna rzecz: brak legalnego, automatycznego odkrywania treści na Facebooku, Instagramie i TikToku w 24 h. Sędzia w roli autora zadania konsekwentnie odejmuje za to 9 punktów.
2. **Wykonalność jest głównym ryzykiem**, większym niż punktacja: 25–35% na cały golden path, ok. 60% na rdzeń (kroki 1–5). Wąskim gardłem jest jeden człowiek: integracja, etykiety i decyzje naraz.
3. Każda runda poprawek podnosiła punkty o 1–2 i zwiększała zakres. Dalsze poprawianie planu nie ma sensu; zysk dałoby tylko obcięcie zakresu albo druga osoba.
4. Mocne strony widziane przez wszystkich: pomiar czcionki ostrzeżenia z ramkami i podstawą prawną, teczka dowodowa, panel kalibracji na realnych etykietach, proces z dowodami w repo (B stabilnie 16–18/20).
