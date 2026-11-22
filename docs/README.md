# Dokumentacja U Źródła

U Źródła zbiera materiały inwestycyjne, zachowuje dowody i pozwala analitykowi zapisać decyzję. Poniżej znajdziesz przebieg pokazu, pochodzenie danych i instrukcje uruchomienia.

| Szukasz | Otwórz |
| --- | --- |
| Pokaz i przykładowe sprawy | [Scenariusz dla jury](hackathon/demo.md) · [Zgłoszenie](../HACKATHON.md) |
| Liczby, źródła i zakres odczytu | [Monitoring](MONITORING.md) · [Spis danych](../fixtures/README.md) |
| Uruchomienie, modele i tryb offline | [Start lokalny i Compose](../ops/demo/README.md) · [Modele i reguły](../analysis/README.md) · [Apple Silicon](../ops/mac/README.md) |
| Budowa systemu i integracja | [Architektura](ARCHITEKTURA.md) · [Kontrakty API](hackathon/contracts.md) |
| Wymagania konkursowe i weryfikacja | [Brief UKNF](zrodla-uknf/BRIEF.md) · [Macierz odbioru](ODBIOR-UKNF.md) · [Testy](../tests/README.md) |
| Licencje | [Zależności, modele i usługi](LICENCJE.md) |

## Kod

| Katalog | Rola |
| --- | --- |
| [collectors](../collectors/README.md) | Odkrywa źródła, pobiera materiały i zapisuje pochodzenie. |
| [analysis](../analysis/README.md) | Wskazuje fragmenty źródeł, ocenia reguły i przygotowuje cytaty. |
| [api](../api/README.md) | Obsługuje skany, sprawy, decyzje, kalibrację i raporty. |
| [web](../web/README.md) | Pulpit analityka z kolejką, kartami spraw i historią decyzji. |
| [ops](../ops/README.md) | Uruchomienie, paczki danych i harmonogram. |
| [tools](../tools/README.md) | Pomiary, walidatory i wsparcie pracy zespołu. |

## Dokumentacja prac

[Proces AI](PROCES-AI.md) · [Rekordy linii](lanes/README.md) · [Tablica zespołu](../TEAM_BOARD.md) · [Integracja](hackathon/integration.md) · [Archiwum](archiwum/README.md)
