# InvestWatch dla analityka UKNF

Analityk otwiera sprawę i może pokazać firmie dokładnie ten materiał, który wzbudził wątpliwość. Zanim zespół oceni zgodność, musi ustalić autora, wydawcę, produkt i zakres zachowanego materiału. Źródłami wymagań są [indeks pięciu załączników](docs/INDEKS.md) i [brief](docs/brief/Urząd_Komisji_Nadzoru_Finansowego__UKNF_-_Pełna_treść_zadania_konkursowego.txt). Wersja oceniana przez panel to [plan realizacji](docs/PLAN-REALIZACJI.md).

## Golden Path

1. Operator uruchamia przegląd źródeł lub otwiera ostatni zaplanowany przebieg. Widzi także awarie i datę ostatniego sukcesu.
2. M1 pokazuje autora, firmę, cytat, URL, datę i dostępne części materiału. Powtórzenia opisu grupujemy z zachowaniem poszczególnych publikacji.
3. Analityk zapisuje decyzję. W osobnej fikcyjnej sprawie odczytuje lokalną odpowiedź firmy, porównuje zakres umowy i aneks. Zachowuje historię zmiany wyniku.
4. W M2 otwiera materiał opublikowany przez samą firmę i sprawdza ostrzeżenie w kontekście korzyści na dwóch ekranach. W M3 zestawia ofertę spersonalizowanej usługi z zakresem zezwolenia.
5. Na zamrożonej próbce zmienia próg, sprawdza fałszywe alarmy i przeoczenia oraz otwiera jeden konkretny błąd.

## Stan, role i odbiór

Kapitan integracji koordynuje kontrakty, kolejność zmian, testy i dziennik. J jest właścicielem decyzji produktowych, zgłoszenia i prezentacji. Źródła publiczne i stanowisko pobierające można sprawdzić osobno. Dashboard, analiza modelem, Compose i pełna próba sceniczna mają własne kryteria odbioru w planie. Zestaw testowy offline musi dać ten sam wynik po restarcie. Szkic pytania i fikcyjna umowa pozostają w lokalnej sprawie demonstracyjnej.

- [Tablica dostępnych prac](TEAM_BOARD.md), [kontrakty](docs/hackathon/contracts.md), [próba pokazu](docs/hackathon/demo.md), [monitor i dobór próby](docs/MONITORING.md), [arkusz odbioru każdego wymagania](docs/ODBIOR-UKNF.md).
- Do 21 XI 19:00 czasu polskiego celem jest pierwszy przebieg od skanu do zapisanej decyzji. Do 20:00 J zapisuje szkic HackTribe. Do 23:30 zespół łączy trzy raporty. Do 02:00 zamyka walidację, do 05:00 funkcje, rano wykonuje trzy próby offline. Cel przekazania 22 XI 10:30, ostateczny termin 11:00. [Przewodnik uczestnika](https://hacknation.pl/przewodnik-uczestnika)
- Na hoście sprawdzono dostęp do Docker Engine 29.1.3 i wersję Compose 2.40.3. Na wybranym stanowisku prezentacji sprawdzić czysty start całego zestawu z modelem. Brak sieci na scenie uruchamia replay z jawną datą. Wolną inferencję ograniczyć do przygotowanego korpusu i zgłosić zmierzony czas.

### Artefakty dla jury

J przygotowuje tytuł, opis, prezentację PDF, minimalny README z Quick Start i repozytorium. Opcjonalny film do 3 minut. Na dwóch minutach pokazu otwiera co najmniej jeden dowód i demonstruje jedną zmianę decyzji. Analityk zachowuje możliwość zweryfikowania każdego cytatu.
