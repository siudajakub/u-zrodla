# M1 · ślepa próba diagnostyczna z 22 listopada 2026

Dwie oceny agentów zgodziły się w sprawie wszystkich ośmiu filmów. Trzy zawierały jawną współpracę, a w pięciu obaj oceniający nie znaleźli podstaw do wpisu ani skierowania. `qual_d` przy progu 60 pozostawił wszystkie filmy poza kolejką. W próbie było **0 pozytywów i 0 skierowań**, więc pełność i precyzja są nieobliczalne. Wynik nie zmienia oceny trafności ani statusu bramki eksperckiej.

## Dobór i pokrycie

Z bazy `s4-live`, otwartej tylko do odczytu, pobrano 954 materiały YouTube. Dla 925 pierwszy lokalny odczyt w zachowanych danych przypadał po `T_cut` z 21 listopada 2026, godz. 18:46:53 UTC. Po odjęciu twórców z odczytami sprzed granicy pozostały 922 materiały. Wyłączenie znanych filmów i twórców z q-v1, q-v2, wcześniejszej próby losowej i paczki pokazu zostawiło 624. Spośród nich 47 miało pełny publiczny opis i zapis całej mowy po polsku. Ograniczenie czasu filmu do 45–1800 sekund dało 30 materiałów. [Protokół](../../fixtures/validation/PROTOKOL.md) · [Zamrożenie](../../fixtures/validation/FREEZE.json)

Przed odtworzeniem predykcji dobrano po jednym filmie od ośmiu twórców. Trzy pochodziły z grupy jawnych znaczników w opisie lub metadanych platformy (3 z 11), jeden z grupy linku lub kodu (1 z 1), cztery z grupy bez dosłownego znacznika w opisie (4 z 7). Grupy wyznaczono z tekstu źródłowego i autentycznej flagi YouTube. Kolejność wynikała z SHA-256 identyfikatora z ziarnem `investwatch-2026-11-22-01`. Osiem pierwszych lokalnych odczytów mieści się między 19:34:53 a 19:34:56 UTC.

Oceniający dostali opisy, napisy z czasami i flagę platformy. Siedem filmów miało napisy automatyczne, jeden autorskie. Dla wybranej ósemki nie było zweryfikowanych JPG ani pełnego obrazu. Pakiet nie zawierał odrębnego wyciągu z wykazów KNF. W plikach ocen brakuje deklaracji `blindToPrediction` i czasu zapisania każdej etykiety. Osiem twórców jest rozłącznych z listą wykluczoną przy doborze, lecz XTB i Saxo Bank występują we wcześniejszych próbach. Wcześniej analizowana baza i brak pełnej historii kampanii ograniczają wynik do diagnozy retrospektywnej.

## Zgodność i wynik kolejki

| Miara | Wynik |
| --- | --- |
| Zgodność klas SOL i TERRA | 8/8, κ Cohena = 1,00 |
| Etykiety zgodne | `rejestr` 3, `bez_sygnalu` 5, `skieruj` 0, `nieustalone` 0 |
| Predykcja `qual_d/60` | 0 skierowań, 0 wstrzymań, 0 braków predykcji |
| Macierz skierowań | TP 0, FP 0, TN 8, FN 0 |
| Jawne współprace w kolejce | 0/3. Wszystkie trzy mają wpis w rejestrze produktu |
| Precyzja i pełność | Oba mianowniki wynoszą 0. Brak podstaw do obliczenia i do podania przedziałów Wilsona |
| Jednostki diagnostyczne | 8 filmów różnych twórców, w tym 3 z jawną współpracą. 0 kampanii skierowanych |

Macierz opisuje ten zestaw kontroli ujemnych. Zerowa liczba przeoczeń przy zerowej liczbie pozytywów nie daje podstaw do oceny wykrywania. Do bramki potrzeba zamkniętego testu ze wzorcem eksperckim i co najmniej 20 skierowań z różnych kampanii. [Narzędzie ewaluacji](../../tools/eval_validation.py) · [Protokół, §7–8](../../fixtures/validation/PROTOKOL.md#7-metryki)

## Rozbieżności w dowodach

- **Telewizja BIZNES24.** Obaj oceniający nadali `bez_sygnalu`. Twórca mówi o 0:45 „XTB nie jest naszym reklamodawcą”. Produkt zachował `no_signal` i pusty rejestr, ale przypisał „materiałach reklamowych” z 5:58 do pola `adRelationship.disclosure` jako dowód oznaczenia współpracy. Fragment dotyczy obowiązku dodawania ostrzeżeń do reklam. Błąd w powiązaniu dowodu nie zmienił trasy. [Materiał, 0:45](https://www.youtube.com/watch?v=Ar6xxxp2_ck&t=45s) · [Fragment, 5:58](https://www.youtube.com/watch?v=Ar6xxxp2_ck&t=358s)
- **Stockbroker pl i Saxo Bank.** Oceniający wskazali deklarację wynagrodzenia w opisie. W mowie o 1:17 pada też „prowadzę współpracę komercyjną”. Produkt wybrał poprawną firmę i wpisał materiał do rejestru, ale jako oznaczenie pokazał wyłącznie flagę YouTube. Opis wskazuje, kto finansuje publikację. [Materiał, 1:17](https://www.youtube.com/watch?v=A3aX1vkkWAk&t=77s)
- **Marcin Iwuć.** Obaj oceniający wskazali `rejestr`, lecz SOL wybrał XTB jako głównego reklamodawcę, a TERRA mBank. Opis zawiera oddzielne deklaracje płatnej współpracy dla obu firm. Produkt wybrał mBank w głównym wpisie, a XTB zachował jako dodatkową relację. Zgodność klasy nie rozstrzyga, jak liczyć kampanie w materiale z kilkoma reklamodawcami. [Materiał](https://www.youtube.com/watch?v=sutNVKMTwUE)

## Odtworzenie

Przebieg zapisano dla `qual_d/60`, `investwatch-m1-qual-1.0`, `investwatch-rules-pl-1.2` i HEAD `47c6898`. Skrypt zachował również skróty analizowanych plików roboczych. Odtworzenie bez modeli i sieci zwróciło osiem identycznych rekordów punktacji, tras, uzasadnień i dowodów. Wszystkie cytaty z ocen udało się dopasować do zapisanych opisów lub napisów.

Pakiet i zapieczętowane zapisy znajdują się lokalnie w `.runtime/blind-followup`. Surowe oceny agentów mają następujące skróty SHA-256.

| Plik | SHA-256 |
| --- | --- |
| `input.json` | `68f6e8e375f5541e7231376ed3786a0d9de544920bd75608ee469dd60e2e8bdc` |
| `predictions.private.json` | `8c7aa45faa70d4bdb9244777f5d521e0331373dd0c21b7ed508f29035f7887a0` |
| `rater-sol.json` | `63ca3e09d956aad88ba17844938fd72180c3b129724b94fef4deb041c5eb18e6` |
| `rater-terra.json` | `945e7bf982479b07d34db6c43613338cefda60d511bfe3bb0567b9eecfdd1738` |
