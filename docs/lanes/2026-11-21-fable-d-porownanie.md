# Porównanie: reguły investwatch-rules-pl-1.2 a Qwen3.5-9B (M1)

Raport D (Opus) dla Fable, 2026-11-21, około 18:40 UTC. Zakres: dwa przypadki na identycznym wejściu, reguły obecnego silnika i adapter Qwen J (`analysis/openrouter_review.py`, `analysis/ollama_review.py`). Kod nie był zmieniany. Wejścia i surowe wyniki leżą w `fixtures/raw/review-compare/`. Model przesłanek U1–U7 pochodzi z [projektu kwalifikacji](2026-11-21-fable-d-kwalifikacja.md).

## Wynik w skrócie

- **Reguły** uruchomiono na obu przypadkach. (a) deklaracja XTB: `score 94`, `review`, czyli fałszywy alarm wobec próby Q. (b) Comparic/XTB z linkiem śledzącym i kodem: `score 24`, „Wzmianka o marce”, `no_signal`. Reguły przeoczyły tu relację handlową.
- **Qwen przez OpenRouter: brak wyniku.** Obie próby bez `--allow-paid` zwróciły `HTTP 401`. Kontrolne `GET /api/v1/key` (bezpłatne) zwróciło `401 "User not found."`. Klucz w `.env.openrouter` ma poprawny format (73 znaki, `sk-or-v1-` + 64 hex), ale OpenRouter go nie rozpoznaje. Nawet z ważnym kluczem trasa bezpłatna nie istnieje, bo katalog z 18:37 UTC nie podaje dla `qwen/qwen3.5-9b` żadnego endpointu z zerową ceną.
- **Qwen przez Ollama:** nieuruchamiany. Na devboxie nie ma Ollamy, zgodnie z poleceniem nie instalowano jej. Gotowe polecenia na Maca są niżej.
- **Według modelu D:** (a) to wpis do rejestru reklam i decyzja `uzupełnij`, bez flagi. (b) to wpis do rejestru, przesłanka U1 `warunkowa` i decyzja `uzupełnij`, bez skierowania. Rzeczywistego materiału z udokumentowaną przesłanką do skierowania nie znalazłem ani w sondzie B, ani w fiksturach, ani w bazie podglądu.

## Przypadki i wejścia

| Przypadek | Plik wejścia (sha256) | Źródło i wersja |
|---|---|---|
| (a) prawidłowo ujawniona współpraca | `case-a-xtb-declaration.json` (31b8b406…) | youtube:xtMqKkFO-0M z `fixtures/raw/discovery/2026-11-21.json` bez zmian. Opis to wycinek 26 znaków (`sampled`, `truncated`), `contentHash` d245bd33…, Atom, obserwacja 2026-11-21T15:40:13Z |
| (a-live) ten sam film, pełny opis (tylko reguły i walidator) | `case-a-live-xtb-declaration.json` (4038b49e…) | baza podglądu `GET http://localhost:8769/v1/state`, odczyt 2026-11-21T18:36:01Z, sha256 odpowiedzi 33e635cb…. Opis 3731 znaków, `contentHash` zgodny z treścią |
| (b) reklama z konkretną przesłanką | `case-b-comparic-xtb-referral.json` (e5b5c694…) | youtube:CDk20n4u9Kk (Comparic Rynki, „ARABIA SZYKUJE SIĘ NA WOJNĘ…”, publikacja 2026-11-19), ten sam odczyt podglądu. Opis 4651 znaków, `truncated: false`, `contentHash` 17916af3… zgodny z treścią |

Dlaczego Comparic jako (b): sonda B (`fixtures/raw/discovery/youtube-probe-2026-11-21/`) zawiera tylko deklaracje („Partnerem odcinka”, „#Reklama”, „współpraca”) bez twierdzeń o zysku. Grep fraz „gwarantowany zysk”, „pewny zysk”, „zysk bez ryzyka”, „zarobisz N%” nie dał trafień. W fiksturach M1 też nie ma takiego materiału. Comparic jest jedynym rzeczywistym materiałem z konkretną przesłanką. Opis zawiera blok:

> 💰 Inwestowanie z XTB - Sprawdź XTB / 👉 https://link-pso.xtb.com/pso/GFTfa / … / Kod „COMPARIC” przy rejestracji = darmowy kurs inwestowania. / Oferowane instrumenty są ryzykowne. Inwestuj odpowiedzialnie.

W pełnym opisie nie ma słów „reklama”, „współpraca”, „partner” ani „sponsor”. To przesłanka U1 (dowód relacji handlowej bez oznaczenia w zbadanym zakresie). Materiał nie jest syntetyczny. Przypadek syntetyczny nie był potrzebny.

## Tabela: 2 przypadki × (reguły, Qwen)

| Przypadek | Reguły 1.2 | Qwen3.5-9B | Model D (oczekiwanie) |
|---|---|---|---|
| (a) | `score 94`, `signalType declaration`, `reviewSuggestion review/rules`. Cytat „Partnerem odcinka jest XTB”, występuje w wejściu: tak. Powód: „Deklaracja współpracy lub partnerstwa. Ustal warunki współpracy z firmą.” | OpenRouter free-only: `provider_http`, HTTP 401 (nieważny klucz). Ollama: nieuruchamiany | Rejestr: XTB, kandydaci 6884980 (XTB S.A.) i 9439233 (XTB Ltd), reklamujący DETERMINACJA, cytat jw. Flaga: brak. Decyzja `uzupełnij`, `reviewScore: brak_podstaw` (26-znakowy wycinek, brak mowy i obrazu) |
| (a-live) | `score 94`, `review/rules`. Cytat „📢Partnerem odcinka jest XTB”, w wejściu: tak | nie wysyłano (jedna próba na przypadek) | Rejestr: XTB S.A. (tożsamość ustalona: linki geolink.xtb.com i nazwa „XTB S.A.” w zastrzeżeniu), oznaczenie `#współpraca` + deklaracja. Przesłanki w opisie: brak. W opisie jest standardowe ostrzeżenie CFD. „ZERO prowizji” to korzyść cenowa, nie twierdzenie o zysku. Decyzja `uzupełnij` (mowa niezbadana) |
| (b) | `score 24`, `signalType neutral_mention`, `reviewSuggestion no_signal/rules`. Cytat „💰 Inwestowanie z XTB - Sprawdź XTB”, w wejściu: tak. Powód: „Wzmianka o marce w zbadanym zakresie.” | OpenRouter free-only: `provider_http`, HTTP 401. Ollama: nieuruchamiany | Rejestr: XTB (relacja `udokumentowana`: link śledzący w domenie xtb.com i kod twórcy). U1 `warunkowa`: cytat „Kod „COMPARIC” przy rejestracji = darmowy kurs inwestowania.”, w wejściu: tak, wersja `contentHash` 17916af3…, obserwacja 15:40:13Z. Oznaczenia nie znaleziono w pełnym opisie. Mowa, kadry i flaga płatnej promocji YouTube niesprawdzone. Decyzja `uzupełnij`, punkty ≤ 45. Kontrargument: blok jest wyraźnie promocyjny, więc ocena, czy to „jednoznaczne oznaczenie”, należy do analityka. Ostrzeżenie o ryzyku jest obecne, więc brak U4. „Regulowany przez KNF” to fakt, nie U6 |

Zasada sponsora: deklaracja i link partnerski tworzą wpis rejestru, nie flagę. Niedostępny kontekst (mowa, kadry) oznacza wstrzymanie wniosku (`uzupełnij`), nie „brak sygnału”.

Sprawdzenie cytatów: wszystkie cytaty reguł występują dosłownie w opisie wejścia (`quoteInInput: true` w `rules-results.json`). Cytaty modelu D sprawdzono przez `str.find` na opisie wejścia.

## Inne rozstrzygnięcia z bazy podglądu (zgłoszenie agenta I)

| Materiał | Reguły dziś | Model D | Usterka reguł |
|---|---|---|---|
| Comparic: CDk20n4u9Kk, eQYmvRfHtr8, YQH4FEP9exI | 24, „Wzmianka o marce” | jak (b): rejestr XTB, U1 `warunkowa`, `uzupełnij`. eQYmvRfHtr8 ma też link referencyjny InvestingPro, a YQH4FEP9exI promocję samochodu. To produkty spoza zakresu M1, bez wpisu w rejestrze M1 | `CTA` nie zna „Sprawdź XTB”. `REFERRAL` nie łapie „Kod „COMPARIC” przy rejestracji”. Brak rozpoznania domen śledzących firm (link-pso.xtb.com, geolink.xtb.com) |
| FBO 347 (apple-podcasts:946719109:episode:4fc2b057…) | 66, `affiliate_code`, streszczenie „W zbadanym opisie nie wykryto oznaczenia” | Rejestr: mBank (eMakler) i Saxo Bank, relacja `udokumentowana`, oznaczenie jawne w opisie: „[reklama_mBank] Link mBanku wstawiamy w ramach płatnej współpracy.” Przesłanek brak. Decyzja `uzupełnij`, bo audio podcastu niezbadane. Status Saxo Bank w wykazach nieustalony w tej próbie | Błąd: `DISCLOSURE_LABEL` nie dopasowuje „[reklama_mBank]” (sufiks po podkreślniku) ani odmiany „w ramach płatnej współpracy”. Streszczenie twierdzi nieprawdę o materiale |
| FBO 349 | 66, to samo błędne streszczenie | Rejestr: mBank, XTB („[reklama_XTB] Link XTB wstawiamy w ramach płatnej współpracy”), Saxo. Przesłanek brak, przy XTB jest ostrzeżenie. Decyzja `uzupełnij` | jw. |
| FBO 348 | 94, deklaracja, trafia do przeglądu | Relacja jawna z Hipoteka Direct sp. z o.o. (pośrednik kredytowy). Firma spoza zakresu M1 (to nie firma inwestycyjna). Brak wpisu w rejestrze M1, `bez_sygnału` | Reguły nie sprawdzają, czy reklamodawca jest firmą inwestycyjną, więc 94 to fałszywy alarm spoza zakresu |
| 15 deklaracji DETERMINACJA/XTB w podglądzie (nie 2) | 94 każda | Rejestr, jedna kampania z 15 materiałami, `uzupełnij` | Wszystkie trafiają do filtra „wysokie ryzyko” i wyzwalają `high_risk` |

## Co zablokowane i przez co

| Blokada | Dowód | Właściciel i następny krok |
|---|---|---|
| Klucz OpenRouter nieważny | Adapter: HTTP 401 dla obu przypadków o 18:37:24Z. `GET /api/v1/key`: `401 {"message":"User not found."}`. Klucz nie wypisany | J: wygenerować nowy klucz z limitem kredytów (np. 1 USD) i zapisać lokalnie w `.env.openrouter` (tryb 600) |
| Brak bezpłatnej trasy dla qwen/qwen3.5-9b | `openrouter-endpoints-qwen3.5-9b-2026-11-21T1837Z.json`: 8 endpointów, wszystkie z ceną > 0, brak wariantu `:free` | J: zgoda na koszt i `--allow-paid` |
| Brak Ollamy na devboxie | zgodnie z poleceniem nieinstalowana | L/J: uruchomić na Macu M3 |

Gotowe polecenia (identyczne wejścia, uruchamiane z katalogu repo):

```sh
# (i) OpenRouter, wyłącznie po zgodzie J na limit i z nowym kluczem
sh ops/review/openrouter.sh fixtures/raw/review-compare/case-a-xtb-declaration.json --public-source --allow-paid
sh ops/review/openrouter.sh fixtures/raw/review-compare/case-b-comparic-xtb-referral.json --public-source --allow-paid

# (ii) Mac z Ollama
ollama pull qwen3.5:9b
python3 -m analysis.ollama_review fixtures/raw/review-compare/case-a-xtb-declaration.json
python3 -m analysis.ollama_review fixtures/raw/review-compare/case-b-comparic-xtb-referral.json
```

Uwaga: `--allow-paid` usuwa cały blok `max_price`, więc pojedyncze żądanie nie ma limitu ceny. Ograniczeniem jest wyłącznie limit kredytów klucza.

## Szacunek kosztu

Stawki: publiczny katalog OpenRouter `GET /api/v1/models/qwen/qwen3.5-9b/endpoints`, odczyt 2026-11-21T18:37:45Z (zapisany w `fixtures/raw/review-compare/`). Rozpiętość wynosi 0,08–0,17 USD za 1 mln tokenów wejścia i 0,12–0,25 USD za 1 mln tokenów wyjścia (najtaniej DeepInfra flex, najdrożej Together i PrimeIntellect). Adapter nie wybiera dostawcy, więc liczę według stawek maksymalnych.

Tokeny wejścia z rzeczywistego promptu `review_messages` (tokenizer Qwen3.5-9B, BPE w czystym Pythonie, przybliżenie około ±5%, `token-counts.json`): (a) 569 + 101 schematu = około 670; (b) 2181 + 101 = około 2280; prompt systemowy to 511 tokenów.

| Scenariusz | Wyjście | (a) | (b) |
|---|---|---|---|
| Typowy: sama odpowiedź JSON | około 60 tokenów | około 0,00013 USD | około 0,0004 USD |
| Najgorszy: rozumowanie do `max_tokens` 4096 | 4096 tokenów | około 0,0011 USD | około 0,0014 USD |

Seria 50 materiałów wielkości (b): typowo około 0,02 USD, najgorzej około 0,07 USD. Przy maksymalnym dopuszczalnym wejściu adaptera (24 000 znaków, około 9 tys. tokenów) najgorzej około 0,13 USD. Nie sprawdziłem minimalnej kwoty zakupu kredytów w OpenRouter. Realnym progiem kosztu może być właśnie ten zakup, a nie zużycie.

## Ocena promptu i taksonomii `SIGNALS` względem U1–U7

| Przesłanka D | Pokrycie w adapterze M1 |
|---|---|
| U1 nieujawniona współpraca | Brak. `affiliate_promotion` ma status `control` niezależnie od tego, czy oznaczenie jest obecne. Przypadek (b) w najlepszym razie wyjdzie jako `control` |
| U2 oznaczenie niejednoznaczne | Brak |
| U3 podmiot spoza wykazu | Brak, model słusznie nie ocenia tożsamości. Musi to robić D z wykazów |
| U4 zysk bez ryzyka | Brak w M1. Istnieje tylko w M2 (`potential_return_claim` jako `control`) |
| U5 obietnica lub prognoza | Częściowo: tylko `unqualified_investment_guarantee` z regexem gwarancji i instrumentu. „Zrobicie 20% rocznie” czy prognoza bez słowa „gwarantowany” lub „pewny” nie przejdą walidacji |
| U6 aprobata nadzoru | Brak w M1 |
| U7 sygnał M3 | Tylko w module M3 |

Ryzyka:
1. W M1 jest jedna kategoria `review` (gwarancja zysku). Model nie wykryje więc praktycznie żadnej przesłanki z rzeczywistych materiałów, które widzieliśmy. Jego realną rolą w M1 jest potwierdzenie relacji (`declared_partnership`, `affiliate_promotion`), a to już robią reguły.
2. Odpowiedź ma jedną etykietę. Materiał z deklaracją sponsora i odrębnym problemem zwróci jedną z nich. Wpis rejestru musi więc pochodzić z reguł, a nie z modelu.
3. `affiliate_promotion` łączy zachętę przy marce (słaby dowód relacji) z kodem lub linkiem afiliacyjnym (mocny dowód).
4. Prompt nie wie, które modalności przeanalizowano. Abstencje dotyczą niejednoznaczności tekstu, a nie pokrycia materiału. Wstrzymanie z powodu braku mowy lub obrazu musi nastąpić poza modelem.
5. Odpowiedź walidatora odrzucona jako `ungrounded_response` jest zwracana jako błąd, a nie wstrzymanie. Integracja musi mapować błąd na `uzupełnij` lub „brak podstaw”, nigdy na `bez_sygnału`.
6. Boilerplate z ostrzeżeniami w opisie (Comparic, DETERMINACJA) może skłonić model do uznania ryzyka za „towarzyszące” każdej treści.

## Usterki adapterów (nie edytowano; do właściciela J lub H)

1. **Duplikat cytatu daje fałszywy błąd.** `validate_recommendation` odrzuca cytat występujący w fragmencie więcej niż raz. Potwierdzone offline na (a-live): poprawny cytat „🎁 Wpisz przy rejestracji kod DETERMINACJA, aby otrzymać darmowy kurs! 🎁” (dwa wystąpienia) daje `ungrounded_response`. Lepiej przyjąć pierwsze wystąpienie i zapisać liczbę wystąpień.
2. **Różne parametry backendów.** Ollama wysyła `temperature 0`, `reasoning_effort "none"`, `max_tokens 384`. OpenRouter wysyła `max_tokens 4096` bez temperatury i bez kontroli rozumowania. Porównanie „na identycznym wejściu” nie ma identycznych parametrów, a wynik OpenRouter jest niedeterministyczny i może rosnąć kosztowo przez tokeny rozumowania.
3. **Ollama `max_tokens 384`.** Jeśli `reasoning_effort: "none"` nie wyłączy rozumowania w danej wersji Ollamy (nie zweryfikowałem), odpowiedź utnie się (`finish_reason length`) i da `incomplete_response`. Do sprawdzenia na Macu.
4. **OpenRouter `timeout=30` s** może nie wystarczyć przy rozumowaniu i da `provider_unavailable`.
5. **`ops/review/openrouter.sh` robi `cd` do katalogu repo.** Względne ścieżki wejścia podane z innego katalogu przestają działać, wbrew komentarzowi „from any working directory”.
6. **Wersja źródła w wyniku jest niepełna.** Wynik zawiera `sourceSha256` promptu i `sourceUrl`, ale nie `contentHash`, `observedAt` ani `provenance.sourceVersion` materiału. Dla „sprawdzalnej wersji źródła” warto je przepisać z Capture.
7. **Błąd 401 nie odróżnia nieważnego klucza od braku uprawnień.** Komunikat nie podpowiada sprawdzenia klucza. Drobne.
8. **Tryb free-only dla tego modelu nie może się powieść** (brak trasy z zerową ceną). Domyślne polecenie z `docs/fable/OPENROUTER-M3.md` zawsze skończy się błędem HTTP, co warto opisać w dokumencie.

Testy adapterów: `python3 -B -m unittest analysis.test_openrouter_review analysis.test_ollama_review`, 17 testów OK (bez sieci).

## Ograniczenia

- Brak jakiejkolwiek odpowiedzi Qwen. Kolumna modelu w tabeli to odmowa lub blokada, nie wynik.
- Model D to projekt bez kodu. Jego kolumny to rozstrzygnięcie ręczne według reguł z projektu kwalifikacji, nie wynik programu.
- Liczby tokenów są przybliżone (pre-tokenizer bez `\p{L}`, szablon czatu przybliżony, bez narzutu dostawcy).
- Wejście (a) to wycinek z fikstury, zgodnie z poleceniem. Pełny opis tego samego filmu (a-live) zmienia ustalenie tożsamości firmy, ale nie zmienia decyzji.
- Rzeczywistego materiału kwalifikującego się do `skieruj` nie znalazłem. To nadal zadanie B/C (mowa, pełne opisy, szersza sonda).

## Fala 2: kwalifikacja D w kodzie (2026-11-21, około 19:00 UTC)

Moduł `analysis/qualification.py` (reguły `investwatch-m1-qual-1.0`, niewpięty w silnik) policzono na tych samych realnych wejściach. Pełny zapis dla G jest w `fixtures/raw/review-compare/qualification-results.json`: stara decyzja, nowa decyzja, cytaty, momenty i zakres. Wszystkie cytaty sprawdzono w wejściu. Kolumna „opis+mowa+kadry” korzysta z pełnych auto-napisów agenta C (cache `.runtime/media-cache/`, poza Gitem) i z jego kadrów.

| Materiał | Reguły 1.2 (opis) | D: sam opis | D: opis+mowa+kadry |
|---|---|---|---|
| DETERMINACJA/XTB xtMqKkFO-0M | 94, `review` | `complete` (mowa niezbadana), rejestr `included` | `no_signal`, rejestr `included`; oznaczenie w opisie (#współpraca, deklaracja) i w mowie 109 s |
| Comparic CDk20n4u9Kk | 24, `no_signal` | `refer` 85, U1: „https://link-pso.xtb.com/pso/GFTfa” + „Kod „COMPARIC” przy rejestracji…”, „mowy nie zbadano” | `no_signal`, U1 obalona: mowa 614 s „znajdziecie u partnera tego odcinka XTB.”, kadr 614 s „REKLAMA”; kod z mowy „Komparik” ≈ COMPARIC (dopasowanie przybliżone) |
| Comparic eQYmvRfHtr8, YQH4FEP9exI | 24, `no_signal` | `refer` 85 (U1, jak wyżej) | brak mowy od C |
| -HpCSKp9bqk (XTB) | 24, `no_signal` | `refer` 85, U1: „https://link-pso.xtb.com/pso/kdg44” + kod DNARYNKOW | `no_signal`, U1 obalona: mowa 94 s „dzięki partnerowi tego odcinka, jakim”, kadr 104 s „PARTNEREM ODCINKA JEST XTB” |
| 9Fcwo1jlwe4 (Freedom24) | 12, `no_signal` | `refer` 75, U1: link c.freedom24.com z `ref1` | `no_signal`, U1 obalona: mowa 192 s „freedom, partnera, partnera tego kanału,”, kadr 195 s „REKLAMA” |
| o2GfnmVVkO8 (Freedom24), ePfzHQVf-lc (XTB) | 12 i 24, `no_signal` | `refer` 75 i 85 (U1) | brak mowy od C |
| FBO 347, FBO 349 | 66, `no_signal`, „nie wykryto oznaczenia” | `complete` (Saxo Bank bez wpisu w kopii wykazu), rejestr mBank (i XTB w 349) `included` | brak audio |
| FBO 348 | 94, `review` | `no_signal`: Hipoteka Direct spoza zakresu M1 | brak audio |
| Saxo _aqCM37gK1U | 12, `no_signal` | `complete` (`identity_unresolved`), rejestr `included` | brak mowy od C |

Po dodaniu mowy nie zostaje żaden realny materiał z `route=refer`. Wszystkie 4 filmy z transkrypcją ujawniają współpracę w mowie lub kadrze, choć opis tego nie robi. `refer` zostaje wyłącznie tam, gdzie mowy jeszcze nie zbadano (Comparic 2 i 3, o2GfnmVVkO8, ePfzHQVf-lc), i wynika z decyzji J5. Wobec wzorca tego kanału (oznaczenie w mowie) to najpewniej fałszywe alarmy do czasu transkrypcji. Rzeczywistego przypadku uzasadnionej flagi M1 nadal nie mamy.

## Fala 2: porównanie z Qwen na OpenRouter, zablokowane

Przygotowane, nieuruchomione:
- Wejścia z opisem i transkrypcją (tylko okna ±90 s wokół znaczników `find_markers`, bez pełnych transkryptów) w `fixtures/raw/review-compare/qwen/input-{comparic,cymcyk-xtb,freedom24,determinacja}-opis-mowa.json`. W polu `source` każdy plik zapisuje, co wycięto. Freedom24 zawęziłem do znaczników rodzaju partner/reklama/sponsor, bo pełny zestaw okien przekraczał limit adaptera 24 000 znaków. Wynik: 21 078 znaków, 449 segmentów.
- Kontrola offline: wszystkie 6 wejść przechodzi `capture_fragments` i `_public_url` adaptera.
- Zużycie klucza przed próbą (bezpłatne `GET /api/v1/key`, 19:01:13Z): `usage` 18,525064 USD, `limit_remaining` 81,474936 USD.

Blokada: wywołanie `sh ops/review/openrouter.sh … --public-source --allow-paid` zostało odrzucone przez klasyfikator uprawnień sesji (kategoria: działanie niepożądane lub kosztowe). Nie wykonano żadnego płatnego wywołania, więc zużycie się nie zmieniło. Zgoda J na budżet dotarła przez orkiestratora, a sesja nie traktuje wiadomości agenta jako zgody użytkownika. Potrzebne jest uruchomienie przez J albo reguła uprawnień dla tego polecenia.

Polecenia do uruchomienia (każdy przypadek 2 razy, 12 wywołań, szacunek łącznie poniżej 0,05 USD):

```sh
for f in case-a-xtb-declaration case-b-comparic-xtb-referral qwen/input-comparic-opis-mowa qwen/input-cymcyk-xtb-opis-mowa qwen/input-freedom24-opis-mowa qwen/input-determinacja-opis-mowa; do
  for i in 1 2; do sh ops/review/openrouter.sh "$PWD/fixtures/raw/review-compare/$f.json" --public-source --allow-paid; done
done
```

Adapter nie zwraca dostawcy, tokenów, kosztu ani czasu, bo odrzuca `provider` i `usage` z odpowiedzi. Pomiar kosztu jest więc możliwy tylko z różnicy `usage` w `GET /api/v1/key` przed i po. To kolejna usterka adaptera do zgłoszenia J.

Oczekiwany wynik wynikający z taksonomii, nie ze zmierzonego modelu: w M1 jedynym sygnałem `review` jest gwarancja zysku. Na tych 6 wejściach model może zwrócić co najwyżej `declared_partnership` albo `affiliate_promotion`, czyli `control`, albo abstencję. Nie ma kategorii dla nieoznaczonej współpracy (U1) ani dla obalenia jej przez mowę. Propozycja zmiany promptu (tekst do decyzji J; adaptera nie edytowałem):

> Dodaj sygnał `undisclosed_partnership` („review”): „Opis zawiera dowód relacji handlowej z firmą inwestycyjną (link śledzący w domenie firmy, kod twórcy przy rejestracji, deklarację wynagrodzenia), a żaden podany fragment (opis, transkrypcja) nie oznacza materiału jako reklamy, współpracy ani partnerstwa. W cytacie pokaż dowód relacji.” Dodaj też pole `disclosureQuote` (dosłowny cytat oznaczenia albo pusty) i wymagaj, żeby przy sygnale `declared_partnership` znalezionym tylko w transkrypcji cytat pochodził z fragmentu `transcript:N`. Walidator powinien odrzucać `undisclosed_partnership`, jeśli reguły D znalazły oznaczenie w którymkolwiek fragmencie.

## Fala 3: adaptery v2, przebieg Qwen v2 i poprawki kwalifikacji D (2026-11-21, ok. 19:15–20:00 UTC)

Zakres zgody J (przez orkiestratora): adaptery porównawcze, testy offline, budżet OpenRouter do 10 USD, potem `analysis/qualification.py` i jego testy. Nic nie commitowano.

### Zmiany adapterów (`investwatch-text-review-v2`)

- Walidator cytatu: pozycje modelu (`charStart`, `charEnd`) zgodne z jednym z wystąpień dają `match:"verbatim"`. Jedno wystąpienie bez pozycji to też `verbatim`. Błędne pozycje albo kilka wystąpień bez pozycji dają pierwsze wystąpienie we wskazanym fragmencie i `match:"relocated"`. Wynik ma `occurrences`. Zdanie mowy rozcięte granicą auto-napisów jest przyjmowane jako `match:"span"` (sąsiednie segmenty złączone spacją, maks. 12, `fragmentIds`). Cytat nieobecny we wskazanym fragmencie nadal jest odrzucany (`quote_not_in_fragment`, `quote_in_other_fragment`).
- M1: sygnał `undisclosed_partnership` (`review`) i pole `disclosureQuote` (dosłowny cytat oznaczenia albo null, sprawdzane w całym wejściu). Walidator woła `analysis.qualification.qualify` na tych samych fragmentach (`rulesCheck`). Jeśli reguły D znajdą oznaczenie, `undisclosed_partnership` dostaje `status:"hold"`. Dla `declared_partnership` przy oznaczeniu tylko w mowie wymagany jest cytat z `transcript:N`. Cytat deklaracji musi zawierać oznaczenie (`declared_without_disclosure_cue`). `affiliate_promotion` bez żadnego oznaczenia daje `hold` (`affiliate_without_disclosure`). `disclosure.confirmedByRules` odróżnia oznaczenie od np. linii kontaktowej „Współpraca: biuro@…”. Prompt podaje obecne i brakujące modalności (tytuł, opis lub wycinek, transkrypcja pełna lub okna, brak kadrów).
- Te same parametry w obu backendach: `temperature 0`, `max_tokens 1024`, `seed 0`, rozumowanie wyłączone (OpenRouter `reasoning:{enabled:false}`, Ollama `reasoning_effort:"none"`). Ollama: `INVESTWATCH_REVIEW_MODEL` (domyślnie `qwen3.5:9b`) i `OLLAMA_HOST` (domyślnie `127.0.0.1:11434`, tylko `http`). Timeout OpenRouter: 120 s.
- Wynik i błąd zawierają: `rawResponse` (≤ 4000 znaków), `usage` (tokeny, koszt, tokeny rozumowania), `provider`, `wallSeconds`, `source` (`contentHash`, `observedAt`, `mediaVersion`, `sourceVersion`), `parameters`, `pricing`, `modelMismatch`, `error.reason`.
- Koszt: przed wysłaniem materiału adapter wykonuje `GET /api/v1/models/<id>/endpoints` (bez klucza, bez przekierowań). Bez `--allow-paid` lokalnie odmawia, gdy brak endpointu z zerową ceną (`paid_model_requires_opt_in`). Z `--allow-paid` przekazuje `provider.max_price` z `--max-price-per-mtok` (domyślnie 1,0 USD) i odmawia, gdy nic się nie mieści (`price_above_cap`). Gdy żaden endpoint nie obsługuje wymaganych parametrów, zwraca `no_compatible_endpoint`. Błąd cennika: `pricing_unavailable`. `compare_recommendations(a, b)` zwraca `agree`, `disagreement` albo `hold` z decyzją `refer`/`no_refer`/`withheld`.
- `ops/review/openrouter.sh` nie robi już `cd`, więc ścieżki są względne wobec bieżącego katalogu. `PYTHONPATH` wskazuje repo. Klucz pochodzi z pierwszej pasującej linii pliku, po obcięciu `export`, CR, spacji i cudzysłowów.

### Przebieg Qwen v2 (płatny, OpenRouter)

Polecenie: `sh ops/review/openrouter.sh <wejście> --public-source --allow-paid`. Dziesięć wejść po 2 wywołania daje 20 wywołań (limit tury: 30). Surowe wyniki: `qwen/run-2026-11-21T1920Z-openrouter-v2.jsonl` (6 wejść z fali 2) i `qwen/run-2026-11-21T1933Z-openrouter-v2-refer.jsonl` (4 filmy `refer` z pakietu C2, opis i pełna transkrypcja: `qwen/input-<id>-opis-mowa.json`). Ponowna walidacja zapisanych odpowiedzi końcowym walidatorem bez nowych wywołań: `qwen/revalidated-v2-2026-11-21.jsonl`. Predykcje w formacie G: `predykcje-qwen3.5-9b-v2.jsonl`.

Model: `qwen/qwen3.5-9b`, `reportedModel` zgodny przy wszystkich 20 wywołaniach. Dostawca w 20/20 to Darkbloom (endpoint `darkbloom/fp4`, kwantyzacja fp4). Tokeny rozumowania: 0. Średni czas ścienny: 3,3 s.

| Materiał (wejście) | Reguły 1.2 (opis) | Kwalifikacja D (to samo wejście) | Qwen v2 (końcowy walidator, para) |
|---|---|---|---|
| xtMqKkFO-0M, wycinek opisu | 94 `review`, „Partnerem odcinka jest XTB” | `complete`, rejestr, oznaczenie „Partnerem odcinka jest XTB” | `control` `declared_partnership` „Partnerem odcinka jest XTB” ×2, para identyczna |
| CDk20n4u9Kk, sam opis | 24 `no_signal`, „💰 Inwestowanie z XTB - Sprawdź XTB” | `refer` U1: „https://link-pso.xtb.com/pso/GFTfa” | (1) `control` `neutral_or_denied_partnership` z zastrzeżeniem prawnym („Prezentowane treści mają wyłącznie charakter informacyjny…”); (2) `declared_partnership` „Inwestowanie z XTB - Sprawdź XTB”, odrzucone `declared_without_disclosure_cue`. Para różna, U1 przeoczona |
| CDk20n4u9Kk, opis + mowa (okna) | 24 `no_signal` | `no_signal`, rejestr, mowa „znajdziecie u partnera tego odcinka XTB.” | `control` `declared_partnership` „kontrakty na ropę Brent znajdziecie u partnera tego odcinka XTB.” (span `transcript:37–38`) ×2 |
| -HpCSKp9bqk, opis + mowa | 24 `no_signal` | `no_signal`, „dzięki partnerowi tego odcinka, jakim” | `control` `declared_partnership` „dzięki partnerowi tego odcinka, jakim jest XTB, polska aplikacja inwestycyjna.” (span) ×2 |
| 9Fcwo1jlwe4, opis + mowa | 12 `no_signal` | `no_signal`, „freedom, partnera, partnera tego kanału,” | `control` `declared_partnership` „partnera, partnera tego kanału,” ×2; `disclosureQuote` „Współpraca” to linia kontaktowa (`confirmedByRules:false`) |
| xtMqKkFO-0M, opis + mowa | 94 `review` | `complete` (okna mowy), oznaczenie „#współpraca” | `control` `declared_partnership` „Partnerem odcinka jest XTB, a z kodem DETERMINACJA możecie odebrać darmowy kurs o inwestowaniu.” (span) ×2 |
| 7M0rC6-Rueo, opis + pełna mowa | 24 `no_signal` | `refer` U1: „https://link-pso.xtb.com/pso/7SA9k” | `declared_partnership` z zastrzeżeniem „…Ten materiał ma charakter edukacyjny…”, odrzucone `declared_without_disclosure_cue` ×2 |
| OIyPE0z2mng, opis + pełna mowa | 66 `no_signal` (kod wojtek50) | `refer` U1: „https://link-pso.xtb.com/pso/u0V2g” | `declared_partnership` z zastrzeżeniem „Informacje przedstawione na kanale są moimi prywatnymi opiniami…”, odrzucone ×2 |
| ZJrT-X08Xwc, opis + pełna mowa | 66 `no_signal` | `refer` U1: „https://link-pso.xtb.com/pso/u0V2g” | `abstained` `insufficient_evidence` ×2 |
| AqXHkxDzSDI, opis + pełna mowa | 24 `no_signal` | `refer` U1: „https://bit.ly/44BfO3V” + kod TRADEXTB | `affiliate_promotion` „Znajdziesz linki…” (wielka litera zamiast małej, cytat niedosłowny), odrzucone `quote_not_in_fragment` ×2 |

Odrzucenia walidatora:
- W chwili przebiegu: 10/20, wszystkie `quote_not_in_fragment`. Na podstawie surowych odpowiedzi 8 z nich to artefakt walidatora: zdanie rozcięte granicą segmentów auto-napisów. Poprawka `span` je przyjmuje. Pozostałe 2 to błąd modelu (zmieniona wielkość litery).
- Końcowo: 7/20 (35%). 5× `declared_without_disclosure_cue`: model podał zastrzeżenie prawne albo linię marki jako deklarację współpracy, czyli błąd modelu złapany nową regułą. 2× `quote_not_in_fragment`: błąd modelu.
- Pierwszego przebiegu v1 (7× `ungrounded_response`) nie da się rozłożyć, bo nie zapisywano surowej odpowiedzi.

Stabilność: 9/10 par ma identyczną surową odpowiedź (temperature 0, seed 0, jeden dostawca). Różna była para dla CDk20n4u9Kk z samym opisem.

Koszt: według `usage.cost` dostawcy 0,00798 USD za 20 wywołań (96 938 tokenów wejścia, 1 759 wyjścia). Razem z falą 2 wychodzi 0,0086 USD. Licznik klucza (`GET /api/v1/key`) wzrósł w tym czasie z 18,541092 do 18,567848 USD (+0,0268), ale między moimi seriami urósł o 0,0229 bez moich wywołań. Klucza używa więc też ktoś inny i różnica licznika nie mierzy tego przebiegu.

Wniosek: Qwen3.5-9B nie wnosi nic ponad reguły D. Na 5 materiałach, które D kieruje (U1), model ani razu nie zwrócił `undisclosed_partnership`. Wybierał `declared_partnership` z zastrzeżeniem prawnym, abstencję albo niedosłowny cytat. Zgadza się z D tylko tam, gdzie D samo znajduje oznaczenie (4 materiały z mową). Po poprawce walidatora model zwykle cytuje dosłownie (13/20), ale myli zastrzeżenia z deklaracją. Propozycja jednego większego modelu, nieuruchomionego: `qwen/qwen3.5-27b` (ta sama rodzina i prompt, gęsty 27B, otwarte wagi; licencję Apache 2.0 potwierdzić na karcie HF przed użyciem; w Q4 około 17 GB, mieści się na Macu M3 z ≥ 32 GB). Katalog OpenRouter z 2026-11-21 ok. 19:40 UTC podaje cenę modelu 0,195 USD za 1 mln tokenów wejścia i 1,56 USD wyjścia, z `response_format`, `seed` i `reasoning`. Wymaga `--max-price-per-mtok 2`. Te same 20 wywołań kosztowałoby około 0,02 USD. Przed uruchomieniem warto przypiąć kwantyzację (`provider.quantizations`), bo cały przebieg 9B poszedł na fp4.

### Kwalifikacja D: poprawki z pakietu C2 i flagi B

- Flaga `youtube.paidPromotionFlag=true` (Data API B) to oznaczenie na poziomie platformy. Obala U1, daje relację `declared` i rejestr `included`. W `counterEvidence` pojawia się jako „oznaczenie płatnej promocji YouTube (API, odczyt <czas>)”, `modality:"platform"`, `adRelationship.disclosure.state:"platform_flag"`. Wartości `false` i `null` niczego nie dowodzą. Na replay B: 276 rekordów z flagą, żaden nie dostaje `refer`.
- Mowa jest dopasowywana w przesuwnych złączeniach 5 kolejnych segmentów (przerwa > 10 s albo zmiana okna kończy złączenie). Nowe frazy: „partnerem mojego/naszego kanału”, „X, partnera tego odcinka”, „sponsorowany przez”, „link partnerski”, „program partnerski”. Dowód wielosegmentowy ma `joinedSegments`. „Link partnerski” bez nazwy firmy przypisuje się jedynej firmie z indeksu wymienionej w materiale.
- Siła ujawnienia: `explicit_ad`, `partner_mention`, `affiliate_link_mention`, `platform_flag`. Trafia do `adRelationship.disclosure.kind`/`kinds` i `adRegistry.disclosureKind`. Wszystkie obalają U1.
- Dowód relacji: skrócony link (bit.ly, tinyurl, rb.gy i podobne) przy nazwie firmy albo z nazwą w adresie (`short_link`). Kod w tej samej linii co nazwa firmy liczy się bez słów „rejestracja”/„konto”. Link do newslettera bez nazwy firmy nie jest dowodem.
- `refer` z dowodem tylko w opisie: momenty mają `kind:"text"` z lokalizatorem opisu. Dodatkowo `kind:"time"` z `deepLink` do wezwania „linki … w opisie” w mowie (AqXHkxDzSDI: 15,7 s, segment „24. A jeśli chcesz otworzyć konto, znajdziesz linki do specjalnych ofert w opisie poniżej.”; pakiet C podaje 13 s, inna granica segmentu). W uzasadnieniu: „Nie znaleziono oznaczenia reklamy w opisie, w całej transkrypcji (0–204 s) i w 3 kadrach.”
- Trasy końcowe (opis, pełna mowa, kadry C, flaga B) zgodne z rozstrzygnięciem Fable dla wszystkich 13 filmów, stabilne dla okien 3, 5 i 7 segmentów, także bez flagi. Bez złączania (okno 1) o2GfnmVVkO8 wraca do `refer`. `qualification-results.json`: przeliczone 17 dotychczasowych pozycji i 26 nowych (13 filmów × {opis+flaga, opis+mowa+kadry+flaga}), wszystkie cytaty zweryfikowane w wejściu.
- Zmiany kontraktu, addytywne: `adRelationship.disclosure.kind/kinds`, `adRegistry.disclosureKind`, `moments[].kind`, `evidence[].joinedSegments`, `evidence[].modality:"platform"` (nie ma tej wartości w enumie kontraktu §evidence, do decyzji H). Sygnatura `qualify` i nazwy pól bez zmian.

Testy: `python3 -m unittest analysis.test_openrouter_review analysis.test_ollama_review` (21 OK); `tests.core.test_review_adapters_offline` (65 OK, 0 expectedFailure); `tests/core` (185 OK przy ostatnim przebiegu; między przebiegami chwiały się testy API/shadow H, bo `api/` było równolegle edytowane); `-s analysis -t .` (91 OK, 2 pominięte). Szczegóły w raporcie D dla Fable.

## Fala 4: próba większego modelu `qwen/qwen3.5-27b` (2026-11-21, ok. 19:39–19:46 UTC)

Licencja: karta HF `Qwen/Qwen3.5-27B` podaje `license: apache-2.0` (odczyt 2026-11-21; karta wskazuje już nowszy `Qwen3.6-27B`). Katalog endpointów (`openrouter-endpoints-qwen3.5-27b-2026-11-21T1939Z.json`), cena za 1 mln tokenów wejścia/wyjścia:

| Dostawca | Kwantyzacja | Cena | Wymagane parametry |
|---|---|---|---|
| Alibaba | brak danych | 0,195 / 1,56 | tak |
| Chutes | fp8 | 0,20 / 1,75 | tak |
| SiliconFlow | fp8 | 0,25 / 2,00 | brak `seed` |
| DeepInfra | fp8 | 0,26 / 2,60 | tak |
| Novita | bf16 | 0,30 / 2,40 | tak |

Przy `--max-price-per-mtok 2` mieszczą się tylko Alibaba i Chutes.

Przebieg: prompt v2, parametry jak w 9B. Limit tury 30 wywołań został wykorzystany w całości. Koszt 0,0331 USD według `usage.cost`.
- **Alibaba**, 20 wywołań (10 wejść × 2), `qwen/run-2026-11-21T1939Z-openrouter-v2-27b.jsonl`: 20/20 odrzucone jako `invalid_response`/`schema`. Mimo `strict json_schema` i `require_parameters` dostawca zwraca tablicę obiektów, często z wymyślonymi identyfikatorami fragmentów („1”, „desc_1”). To wina endpointu, nie walidatora. Pary: 7/10 identycznych. Diagnostycznie walidacja pierwszego elementu tablicy też nie daje ani jednego `undisclosed_partnership`.
- **Chutes**, 10 wywołań (5 materiałów U1 i 5 z oznaczeniem, po 1), `qwen/run-2026-11-21T1943Z-openrouter-v2-27b-chutes.jsonl`. Do wyboru dostawcy dodałem do adaptera opcję `--provider` (`provider.only`, sprawdzana też lokalnie w cenniku). Na pary zabrakło limitu wywołań.

Ponowna walidacja: `qwen/revalidated-v2-27b-{alibaba,chutes}-2026-11-21.jsonl`. Predykcje G: `predykcje-qwen3.5-27b-v2.jsonl` (Chutes, 8 materiałów opis + mowa).

| Materiał | Kwalifikacja D | 9B (para) | 27B (Chutes) |
|---|---|---|---|
| CDk20n4u9Kk, sam opis (U1) | refer, „https://link-pso.xtb.com/pso/GFTfa” | zastrzeżenie prawne / odrzucone | `affiliate_promotion`, cały blok XTB z linkiem i kodem → `hold` (jako `disclosureQuote` podał kod „COMPARIC”, `confirmedByRules:false`) |
| 7M0rC6-Rueo (U1) | refer, link-pso | odrzucone ×2 | `affiliate_promotion` „✅Konto maklerskie (XTB) (z kodem " WYPRAWA "): https://link-pso.xtb.com/pso/7SA9k” → `hold` |
| OIyPE0z2mng (U1) | refer, link-pso | odrzucone ×2 | linia cashback ze złączonymi wierszami, cytat niedosłowny → odrzucone |
| ZJrT-X08Xwc (U1) | refer, link-pso | abstencja ×2 | `affiliate_promotion` z kodem „wojtek50” (nie XTB) → `hold` |
| AqXHkxDzSDI (U1) | refer, bit.ly + kod | odrzucone ×2 | `affiliate_promotion` „🥇XTB: https://bit.ly/44BfO3V (Użyj kodu "TRADEXTB"…)” → `hold` |
| xtMqKkFO-0M, wycinek opisu | complete, rejestr | `declared_partnership` ×2 | `declared_partnership` „Partnerem odcinka jest XTB” |
| CDk20n4u9Kk, opis + mowa | no_signal, rejestr | `declared_partnership` (span) ×2 | `declared_partnership` „kontrakty na ropę Brent znajdziecie u partnera tego odcinka XTB.” (span) |
| -HpCSKp9bqk | no_signal | `declared_partnership` ×2 | `declared_partnership` „dzięki partnerowi tego odcinka, jakim jest XTB, polska aplikacja inwestycyjna.” |
| 9Fcwo1jlwe4 | no_signal | `declared_partnership` ×2 | `declared_partnership` „freedom, partnera, partnera tego kanału,” |
| xtMqKkFO-0M, opis + mowa | complete | `declared_partnership` ×2 | `declared_partnership` „#xtb #współpraca\n📢Partnerem odcinka jest XTB” |

- 27B na 5 materiałach U1 zwrócił `undisclosed_partnership` 0 razy. W 4/5 trafnie wskazał dowód relacji, ten sam co D, ale nazwał go `affiliate_promotion`. Na 5 materiałach z oznaczeniem nie dał fałszywego `undisclosed_partnership` (5/5 poprawne `declared_partnership` z dosłownym cytatem).
- Odrzucenia walidatora: Alibaba 20/20 (`schema`, endpoint), Chutes 1/10 (`quote_not_in_fragment`, złączone wiersze opisu). 4/10 to `hold` z reguły spójności.
- Doprecyzowałem regułę `affiliate_without_disclosure`: `disclosureQuote` niepotwierdzony przez reguły D, np. kod twórcy, nie zwalnia już z `hold`. Wyniki 9B się nie zmieniły.

**Wniosek:** ani 9B, ani 27B nie wnosi nic ponad reguły D. 27B poprawnie lokalizuje dowód relacji i oznaczenie, ale nie wyciąga wniosku o braku oznaczenia. W produkcie można go najwyżej trzymać jako niewpięty drugi głos do streszczania uzasadnienia D, z cytatami weryfikowanymi walidatorem i tylko na endpoincie, który respektuje schemat (Chutes, nie Alibaba). Nie jako źródło decyzji.
