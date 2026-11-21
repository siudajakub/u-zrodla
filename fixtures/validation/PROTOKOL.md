# Protokół walidacji InvestWatch · wersja 1.0

Zamrożono 21 listopada 2026, przed strojeniem reguł, promptu i progu oraz przed skanem YouTube z linii B. Skrót SHA-256 tego pliku zapisano w [FREEZE.json](FREEZE.json). Każda zmiana po zamrożeniu tworzy wersję 1.1 z nowym skrótem i powodem. Wyniki policzone według wersji 1.0 zachowują jej numer. Narzędzie: [tools/eval_validation.py](../../tools/eval_validation.py). Wymagania pochodzą z [próby Q i bramki](../../docs/fable/ODBIOR.md) oraz wiersza G [planu](../../docs/fable/REALIZACJA.md).

## 1. Jednostka i etykieta

Jednostką jest **materiał**: jedna publikacja w konkretnej wersji (URL, skrót treści lub rewizja dowodu, czas obserwacji) wraz z zakresem dostępnych modalności. Oceniający widzi całą publikację w dostępnym zakresie, a nie wycinek wybrany przez system.

Etykieta odpowiada na pytanie: **„materiał zawiera udokumentowaną przesłankę wymagającą kontroli”**. Odpowiedź twierdząca wymaga jednocześnie:

1. konkretnego twierdzenia lub okoliczności z dosłownym cytatem i lokalizatorem (zakres znaków, sekunda, kadr lub współrzędne);
2. wymogu właściwego dla rodzaju materiału: M1 przesłanki U1–U6 z [kontraktu D](../../docs/lanes/2026-11-21-fable-d-kwalifikacja.md) przy osobie trzeciej, M2 jeden z 19 ID z [tabeli UKNF](../../docs/zrodla-uknf/KRYTERIA-M2.md), M3 oznaki indywidualnego doradztwa świadczonego bez zezwolenia;
3. braku w materiale rozstrzygającego wyjaśnienia (np. właściwego ostrzeżenia bezpośrednio przy twierdzeniu).

Sama jawna współpraca, zasięg, wysoka zgodność semantyczna lub brak napisu w niepełnym materiale nie są przesłanką. Reguły własnej reklamy firmy z M2 nie przechodzą automatycznie na wypowiedź osoby trzeciej. Etykieta nie stwierdza naruszenia prawa.

## 2. Klasy

| Klasa | Znaczenie | Rola w macierzy |
|---|---|---|
| `skieruj` | Udokumentowana przesłanka według §1 | pozytyw |
| `rejestr` | Potwierdzona reklama, współpraca lub oferta bez przesłanki, np. jawny sponsor albo oferta podmiotu z właściwym zezwoleniem | negatyw; osobny licznik „prawidłowe reklamy w kolejce” |
| `bez_sygnalu` | Brak reklamy firmy inwestycyjnej i brak przesłanki (edukacja, neutralna treść, promocja podmiotu spoza zakresu) | negatyw |
| `nieustalone` | Nie da się rozstrzygnąć. Kod powodu: `brak_modalnosci`, `tozsamosc`, `zakres_uprawnien`, `jezyk`, `inne` | poza macierzą, raportowane per moduł |

Etykieta dotyczy dostępnego zakresu. Pole `coverage` zapisuje, czego nie zbadano. Wyniki raportujemy także osobno dla materiałów z pełnym pokryciem głównej modalności, gdy taki podzbiór istnieje.

## 3. Oceniający i ślepy odczyt

**Dwa niezależne rodzaje ocen, nigdy mieszane w jednym wyniku:**

- **Wzorzec ekspercki** (`referenceKind: expert`). Osoba z udokumentowaną kompetencją w ocenie komunikacji marketingowej firm inwestycyjnych (art. 24 MiFID II, art. 44 rozporządzenia 2017/565) albo w nadzorze nad usługami inwestycyjnymi, np. analityk UKNF, prawnik rynku kapitałowego, pracownik compliance domu maklerskiego. Rekord oceniającego podaje rolę, zakres doświadczenia i deklarację braku konfliktu interesów wobec ocenianych podmiotów. Tylko ten wzorzec może zamknąć bramkę.
- **Oceny agentów** (`referenceKind: agent`). Modele językowe z zapisanym identyfikatorem. Służą do strojenia, wykrywania sporów i przygotowania pakietów. Raport zawsze oznacza je jako „oceny agentów — nie są niezależnym wzorcem eksperckim”. Wynik modelu ocenianego wariantu nigdy nie staje się etykietą.

J podejmuje decyzje produktowe i **nie etykietuje** materiałów ani nie rozstrzyga sporów. Brak eksperta oznacza status „brak wzorca eksperckiego”, a nie przeniesienie oceny na J.

Instrukcja dla każdego z dwóch oceniających:

1. Otrzymujesz pakiet: URL, treść w dostępnym zakresie, zakres pokrycia i neutralny kontekst rejestrowy (datowane wpisy KNF). Pakiet nie zawiera wyniku, punktów, stanu kolejki, ścieżki odkrycia ani warstwy próby (alarm albo losowa).
2. Nie otwierasz repozytorium, interfejsu ani wyników systemu. Nie konsultujesz się z drugim oceniającym.
3. Dla każdego materiału zapisujesz klasę, ID wymogu, dosłowny cytat, uzasadnienie, najmocniejszy kontrargument, notę o pokryciu i pewność (niska, średnia, wysoka).
4. Rekord zapisujesz z czasem przed połączeniem z predykcjami. Plik ocen otrzymuje skrót SHA-256 w dzienniku zamrożeń, zanim ktokolwiek uruchomi ewaluację.
5. Pole `blindToPrediction` mówi prawdę. Oceniający, który wcześniej widział wynik systemu dla danego materiału, ma `false`, a jego ocena nie może być jedyną podstawą etykiety.

## 4. Rozstrzyganie sporów

Zgodność dwóch oceniających raportujemy jako odsetek zgodnych i kappę Cohena. Przy sporze o klasę:

- wzorzec ekspercki: trzeci ekspert czyta oba uzasadnienia i materiał, wybiera klasę albo `nieustalone` i zapisuje powód; oryginalne oceny zostają w pliku;
- oceny agentów: bez eksperta etykieta końcowa brzmi `nieustalone` z kodem `spór_bez_eksperta`. Kolejny agent nie rozstrzyga sporu.

## 5. Kampanie i deduplikacja

Klucz kampanii ustala się przed podziałem i przed predykcją:

- M1: reklamujący (trwałe ID twórcy) + firma + ta sama współpraca. Kolejne odcinki z tą samą deklaracją partnerstwa tworzą jedną kampanię.
- M2: firma + ta sama oferta lub kreacja. Różne szerokości, stany przewinięcia i wersje tej samej strony należą do jednej kampanii. Różne produkty tej samej firmy to osobne kampanie ze wspólnym polem `advertiser`. Raport podaje również liczbę różnych reklamodawców.
- M3: podmiot + ta sama oferta usługi, niezależnie od adresu URL.
- Materiał bez reklamy firmy tworzy własną jednostkę niezależną (`P-…`).

Duplikaty jednego twórcy nie zwiększają liczby niezależnych kampanii. Materiały syntetyczne, ręcznie przesłane i demonstracyjne pozostają w regresji i są wykluczane z walidacji (`synthetic: true`).

## 6. Podział na strojenie i zamknięty test

- Podział według kampanii: wszystkie materiały kampanii trafiają do tej samej części.
- Podział według czasu: test obejmuje wyłącznie kampanie, których pierwszy materiał system zaobserwował **po** dacie zamrożenia zbioru testowego `T_cut` i które nie występują w zbiorze strojenia. Twórca lub domena ze zbioru strojenia może wnieść do testu tylko kampanię z innym reklamodawcą; nakładanie się twórców jest raportowane.
- Materiały, na których budowano lub omawiano reguły przed zamrożeniem, należą do strojenia. Stan 21 XI 2026 opisuje [inwentarz](INWENTARZ.md): odłożony test liczy dziś 0 kampanii.
- Próg wybiera się na strojeniu przy możliwie wysokiej pełności z uwzględnieniem kosztu 2:1. Test uruchamia się raz, z zapisanym progiem, commitem kodu i metadanymi przebiegu.

## 7. Metryki

Dla każdego modułu, kanału odkrycia, warstwy próby i co najmniej dwóch progów (domyślnie 30, 60, 80; próg bramki zapisany przed testem):

- TP, FP, TN, FN, liczebność i liczba etykiet `nieustalone`;
- precyzja TP/(TP+FP), pełność TP/(TP+FN), obie z 95% przedziałem Wilsona;
- odsetek wstrzymanych: predykcja `insufficient`, `decision: withheld` albo jej brak. Wstrzymanie liczy się jako brak skierowania, więc obniża pełność;
- koszt `2 × FN + FP`;
- liczba skierowań z różnych kampanii, macierz na poziomie kampanii (kampania pozytywna, gdy co najmniej jeden jej materiał ma etykietę `skieruj`);
- liczba prawidłowych reklam (`rejestr`) w kolejce;
- lista błędów FP i FN z cytatem oraz kandydaci odrzuceni i niejednoznaczni.

Pusty mianownik daje tekst „brak podstaw do obliczenia”. Wynik reguł to punkty siły sygnału, nie prawdopodobieństwo. Określenie „prawdopodobieństwo” wymaga niezależnej kalibracji z wykresem zgodności i Brier score. Symulację progu raportuje się osobno od zastosowania progu w rzeczywistej kolejce, wraz z historią zmian.

## 8. Bramka produktowa

Domyślna kolejka przechodzi bramkę, gdy na zamkniętym teście z wzorcem eksperckim ma **precyzję ≥ 90% przy ≥ 20 skierowaniach z różnych kampanii**. Raport podaje też 95% przedział Wilsona dla precyzji, pełność i przeoczenia. Przy 20 z 20 trafnych dolna granica przedziału wynosi 0,839, więc sama bramka nie dowodzi precyzji 90% z ufnością 95%. Mała próba, brak pozytywów, oceny agentów albo sam werdykt sędziów O/P dają status „brak podstaw do oceny” lub „nie dotyczy”. Zmiana domyślnej kolejki w produkcie wymaga wcześniejszego pomiaru FP i FN na odłożonych kampaniach.

## 9. Losowa próba spoza alarmów

Dla oszacowania przy realnej częstości: z wszystkich materiałów zeskanowanych w oknie testu, które system nie skierował, losujemy prostą próbę z ziarnem zapisanym przed losowaniem. Celujemy w co najmniej 50 materiałów na moduł albo w całą warstwę, gdy jest mniejsza. Oceniający nie wie, z której warstwy pochodzi materiał. Narzędzie liczy estymację ważoną: waga warstwy to liczebność populacji podzielona przez liczbę ocenionych (`--strata`). Wśród negatywów celowo umieszczamy prawidłowe reklamy.

## 10. Ponowna ślepa próba

Każde użycie testu do zmiany reguł, promptu, modelu, kwantyzacji lub progu zapisujemy w dzienniku zamrożeń. Od tej chwili test staje się zbiorem strojenia. Końcowy pomiar wymaga nowej ślepej próby kampanii zaobserwowanych po nowym `T_cut`, oznaczonej przed predykcją.

## 11. Formaty plików

Etykiety końcowe (JSONL): `materialId`, `module`, `campaignId`, `label`, `referenceKind`, opcjonalnie `discoveryChannel`, `split` (`tuning` albo `test`), `stratum`, `synthetic`, `advertiser`, `agreement`, `requirement`, `quote`, `coverage`.

Oceny surowe (JSONL): `materialId`, `raterId`, `raterKind`, `model` albo kompetencje, `blindToPrediction`, `label`, `requirement`, `quote`, `reason`, `counterArgument`, `coverageNote`, `confidence`, `labeledAt`.

Predykcje (JSONL): opcjonalny pierwszy rekord przebiegu `{"type": "run", ...}` i po jednym rekordzie na materiał: `materialId` z `score` (liczba albo null) i opcjonalnym `state` (`insufficient` oznacza wstrzymanie) albo `decision` (`refer`, `no_refer`, `withheld`) dla wariantu niezależnego od progu. Predykcja zawierająca `label`, `referenceKind`, `raterId` lub `final` jest odrzucana.

Rekord przebiegu ma pola: `variant`, `rulesVersion`, `codeCommit`, `modelId`, `provider`, `weightsDigest` (lokalny digest wag, np. z `ollama show --modelfile` lub SHA-256 pliku GGUF), `quantization`, `parameters` (temperatura, max_tokens, reasoning, kontekst), `promptMethod` (stała `METHOD` z `analysis/openrouter_review.py`, dziś `investwatch-text-review-v1`), `startedAt`, `finishedAt`, `durationSeconds`, `tokens` (`prompt`, `completion`, `source`), `cost` (`amount`, `currency`, `source`: pomiar dostawcy albo „brak pomiaru”), `environment` (host, system, architektura, wersja Ollama lub trasa dostawcy, pamięć). Pole niedostępne ma wartość null i powód. Narzędzie wypisuje brakujące pola.

Porównanie wrażliwości: `--compare drugi.jsonl` liczy metryki obu przebiegów na tych samych etykietach i wypisuje każdy materiał, którego decyzja lub wstrzymanie różni się przy danym progu, oraz maksymalną różnicę punktów.
