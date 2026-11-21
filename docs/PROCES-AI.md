# Proces wytwarzania z asystentami AI

Opis stanu z 21 XI 2026. Dotyczy drugiej rundy prac, prowadzonej w Claude Code. Pierwsza runda w Codex (ASTRA, SOL, TERRA) dostarczyła bazę `eaa9c10` ([tablica](../TEAM_BOARD.md)). Reguły wspólne dla obu narzędzi są w [AGENTS.md](../AGENTS.md), a plan drugiej rundy w [REALIZACJA](fable/REALIZACJA.md).

## Role

| Rola | Kto | Co robi | Czego nie robi |
|---|---|---|---|
| Właściciel produktu | J (człowiek) | Podejmuje decyzje produktowe (np. jawna współpraca trafia do rejestru, a nie do alarmu), zatwierdza koszty i zgłoszenie | Nie etykietuje materiałów ([protokół §3](../fixtures/validation/PROTOKOL.md)) |
| Orkiestrator | Fable (sesja Claude Code) | Rozdziela zakresy, uzgadnia kontrakty, sam powtarza testy przy odbiorze, scala, prowadzi rejestr kosztów | Nie implementuje. Implementację, testy i ocenę zleca agentom Opus i Sonnet ([START_PROMPT](../START_PROMPT.md)) |
| Wykonawcy | Agenci A–N, po jednym na linię | Piszą w wyłącznym zakresie plików, oddają rekord linii z poleceniem testu, wynikiem, jednym przypadkiem błędu i ograniczeniami | Nie dotykają cudzych plików. Jedynym właścicielem `api/` i schematu jest H |
| Oceniający i sędziowie | Świeże agenty bez dostępu do wyników | Etykietują na ślepo, oceniają wersję według §8 briefu, próbują obalić flagę | Nie widzą predykcji ani ocen drugiego sędziego |

## Standardy, które faktycznie stosowaliśmy

1. **Kontrakt przed kodem.** H spisał inwentarz, luki i kontrakt v2 przed pierwszą zmianą w `api/` ([rekord H](lanes/2026-11-21-fable-h-kontrakt.md)). Krok S0 to testy kontraktowe z `expectedFailure`, które przechodzą na zielone w kolejnych krokach ([test](../tests/core/test_contract_v2_qualification.py)).
2. **Osobny worktree i commit na funkcję.** Gałąź `hack/integration`, jeden piszący na plik. W chwili pisania 72 ze 103 commitów mają trailery `Lane:` i `Gate:` z faktycznie uruchomionym sprawdzeniem. Starsze commity z pierwszej rundy ich nie mają.
3. **Zamrożony protokół etykiet.** [PROTOKOL 1.0](../fixtures/validation/PROTOKOL.md) zamrożono przed strojeniem reguł i przed skanem YouTube. Skróty plików są w [FREEZE.json](../fixtures/validation/FREEZE.json). Każda zmiana tworzy nową wersję.
4. **Ślepe etykiety przed pierwszym uruchomieniem reguł.** Tak powstały etykiety M2 (`9d5cb05` przed `6bebaa4`), M3 (`1bd9caf` przed `f4bfce9`) i typów materiału (`4125285` przed klasyfikatorem). Raport zawsze nazywa je „ocenami agentów”, a nie wzorcem eksperckim.
5. **Lista referencyjna ukryta przed wyszukującym.** Listę kanałów Y zamrożono, zanim B uruchomił skan. Kontrola skażenia wykazała, że żaden z 82 ID nie występuje w kodzie ani w zapytaniach ([WYNIK-Y](../fixtures/validation/y-reference/WYNIK-Y-2026-11-21.md)).
6. **Koszty za zgodą i z rejestrem.** Budżet OpenRouter wynosi 10 USD, wydano ok. 0,14 USD. Licznik Fable odczytuje zużycie przed każdą turą i po niej ([rejestr kosztów](../TEAM_BOARD.md)). Z usługi ScrapeCreators zużyto 74 ze 100 darmowych kredytów bez zakupów ([rekord K](lanes/2026-11-21-fable-k-social.md)). Produkt nie woła płatnych API.
7. **Sekrety poza repo.** Klucze leżą w środowisku i w `~/.config/investwatch/`. W zapisanych żądaniach widnieje `key=REDACTED`, a wzór zmiennych jest w [.env.example](../.env.example).
8. **Raport mówi, co zrobiono i czego nie sprawdzono.** Każdy rekord linii ma sekcje Verification i Handoff. Przykład z commita `7d25695`: „Not yet run on macOS”.

## Bramki

- Walidatory dokumentów i dowodów: `python3 tools/check_agent_docs.py`, `python3 tools/check_plan_evidence.py`.
- Testy modułów (`tests/core`, `collectors`, `analysis`, `tools`). Orkiestrator powtarza je sam na spokojnym drzewie, zanim przyjmie linię. Wynik powtórzenia trafia do trailera `Gate:` (np. `bd9ea4b`).
- `sh tools/hack_ready.sh` przed scaleniem oraz świeży przegląd przez drugiego agenta ([integracja](hackathon/integration.md)).
- Niezależny sędzia na tej samej wersji, tylko do odczytu ([ocena](lanes/2026-11-21-fable-ocena-kryteria.md)). Sędzia oszacował wynik na 6,25/10 i podał listę luk, która wyznaczyła kolejną falę.

## Dobór modelu i wysiłku

Opus z wysokim namysłem dostał diagnozy, sporne dane, walidację i sędziowanie. Sonnet dostał integrację, UI i adaptery. Na polecenie J od fali 2 domyślny poziom to medium, a high zostaje dla diagnoz i sędziów ([tablica](../TEAM_BOARD.md)). Faktyczny model zapisuje każdy rekord linii, np. Sonnet 5.5 przy naprawie 429 ([rekord C](lanes/2026-11-21-fable-c-media.md)). Modele do produktu mierzyliśmy przez OpenRouter, bo na devboxie nie wolno ich uruchamiać. Produkt działa na lokalnych regułach i E5 ([rekord AI](lanes/2026-11-21-fable-ai-inferencja.md)).

## Agent złapał błąd agenta albo człowieka

| # | Błąd | Kto i jak go złapał | Skutek i dowód |
|---|---|---|---|
| 1 | Reguły 1.2 dawały jawnej deklaracji „Partnerem odcinka jest XTB” 94 pkt i kierowały ją do przeglądu. Comparic z linkiem i kodem XTB bez oznaczenia dostawał 24 pkt, czyli brak sygnału | D w kontrakcie kwalifikacji, G w pomiarze na q-v2 | Na 26 materiałach z 20 kampanii `rules_1_2` daje FP 7 i FN 4, a `qual_d` FP 0 i FN 0. To zbiór strojenia z etykietami agentów. [Rekord D](lanes/2026-11-21-fable-d-kwalifikacja.md) · [WYNIK-M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md) · `8e55a2a` |
| 2 | W opisie Comparic (CDk20n4u9Kk) jest link i kod XTB, ale nie ma słowa „reklama”, więc wyglądało to na podejrzenie nieoznaczonej współpracy | C przeczytał mowę i kadry | W 614 s pada „znajdziecie u partnera tego odcinka XTB”, a kadr ma etykietę. Film trafił do rejestru, a nie do alarmu. Podobnie Freedom24 (192 s mowa, 195 s „REKLAMA”). [Rekord C](lanes/2026-11-21-fable-c-media.md) · [porównanie](lanes/2026-11-21-fable-d-porownanie.md) |
| 3 | „Blokada hosta 429” na napisach YouTube zatrzymała dociąganie transkrypcji | Sonnet (C) powtórzył jedno wywołanie | 429 dotyczyło żądania maszynowo tłumaczonych ścieżek (`tlang=`) angielskiego filmu z czoła kolejki. Inne filmy pobierały się bez błędu. Adapter żąda teraz tylko oryginalnych polskich napisów i odróżnia 429 jednego filmu od blokady hosta (`e3f3930`, `1c99fa7`) |
| 4 | Ten sam czas zapisany jako `+00:00` i `Z` tworzył nową wersję sprawy. Wdrożenie normalizacji zrobiłoby nowe wersje istniejącym sprawom | H w inwentarzu przed kodem (§1.8) | Odcisk po normalizacji plus rozpoznanie starego odcisku. Test `test_s2_recognises_what_v1_stored_for_real_fixtures` w [test_contract_v2_schema.py](../tests/core/test_contract_v2_schema.py) |
| 5 | Testy H wywołały prawdziwe Data API i zużyły ok. 2900 jednostek kwoty | Fable po księdze kwoty | Klucz jest teraz wyszukiwany przy wywołaniu, domyślny budżet to 0, a `setUp` każdej klasy blokuje `urlopen`. Osobno: klucz cache z sekundami w `publishedAfter` spalił 118 j. [Rekord B](lanes/2026-11-21-fable-b-youtube.md) |
| 6 | Hipoteza, że LLM (Qwen) poprawi kwalifikację M1 | D porównał Qwen 9B i 27B z regułami na tych samych wejściach | Żaden model nie wniósł nic ponad reguły D. Koszt wyniósł 0,0417 USD. Qwen nie trafił do ścieżki decyzji. [Porównanie](lanes/2026-11-21-fable-d-porownanie.md) |
| 7 | Endpoint Alibaba łamał wymagany schemat JSON mimo trybu strict | Walidator odpowiedzi | 20/20 odpowiedzi odrzucono. Routing przypięto do dostawcy, który trzyma schemat ([OPENROUTER-M3](fable/OPENROUTER-M3.md)) |
| 8 | Klasyfikator uprawnień sesji zablokował płatne wywołanie OpenRouter i automatyczny odczyt stron Meta | Mechanizm uprawnień, orkiestrator uszanował blokadę | Blokady nie obchodzono. Płatne polecenie przekazano J. FB i IG mają status `access_blocked` z datowaną próbą i import ręczny zapisanych stron (`7deca91`, `40b881d`, [MONITORING](MONITORING.md)) |
| 9 | Pokrycie kanałów: skan B znalazł 3 z 5 największych kanałów listy Y przy progu 4 z 5 | G na zamrożonym protokole | Werdykt zostaje niezaliczony. Wariant bez krypto (4/5) służy tylko do analizy wrażliwości. Zmiana strategii: najpierw monitoring bazy znanych polskich kanałów, odkrywanie potem (`bd9ea4b`, `233e303`) |
| 10 | Compose z Quick Start nie montował paczki mediów, więc kolejka pokazu wychodziła pusta. PDF i scenariusz opisywały produkt sprzed YouTube | Niezależny sędzia | Compose montuje paczkę tylko do odczytu, a `start.sh` ją weryfikuje (`7d25695`). Scenariusz i PDF przepisano w tej linii |

## Co nie zadziałało

- **Brak wzorca eksperckiego.** Wszystkie miary trafności opierają się na ocenach agentów. Dwa modele jednej rodziny mają kappa 1,000, co może wynikać ze wspólnych założeń. Oceniający G-A zobaczył tabelę etykiet drugiego oceniającego przed zapisem własnych ocen, co odnotowano w danych ([WYNIK-M1](../fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md)). Reguły M3 v2 poprawiono na tym samym zbiorze, na którym je oceniono ([rekord F](lanes/2026-11-21-fable-f-m3.md)).
- **Brak CI.** Bramki uruchamiają agenci i orkiestrator ręcznie. Trailer `Gate:` jest deklaracją, a nie wynikiem automatu.
- **Zasoby hosta i limity.** Na hoście mieści się jeden ciężki przebieg naraz (Chromium, model). Agent UI zapętlił raport i został zatrzymany (wpis 21:05 UTC w dzienniku sesji poza Gitem). Przeliczenie na podglądzie 18801 czekało na worker ponad godzinę (`/v1/overview`, pole `recompute`).
- **Objętość dokumentacji.** Rekordy linii są obszerne. Sędzia ostrzegł, że może to wyglądać na generowany tekst bez treści. Dlatego README i ten opis są krótkie, a szczegóły zostały w rekordach.
- **Nieprzetestowana platforma pokazu.** Do chwili zapisu nikt nie uruchomił ścieżki na macOS.
