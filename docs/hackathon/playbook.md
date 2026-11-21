# Praca nad jedną wersją demonstracyjną

ASTRA wyznacza próbę akceptacyjną i przydziela osobne zakresy, modele oraz poziom reasoning na [tablicy](../../TEAM_BOARD.md). SOL i TERRA zaczynają od konkretnego dokumentu UKNF, danych i przykładu przeciwnego. Wykonawca odtwarza próbę przez normalne wejście, drugi agent sprawdza oczekiwany wynik niezależnie od autora. Zachowujemy również nieudane próby i granice danych.

1. Odczytaj stan worktree i istniejące edycje. Przydziel jednego piszącego do linii oraz właściciela każdej zmiany kontraktu.
2. Powiąż wymaganie z sekcją [briefu](../zrodla-uknf/BRIEF.md) lub ID kryterium oraz cechą pełnego materiału. Do powtórki zachowaj źródło, czas, wersję i pochodzenie.
3. Zintegruj kod po przeglądzie różnic, uruchom próbę negatywną i regresję. Oddziel pracę lokalną od wdrożenia. Publiczne zgłoszenie, koszt, commit i push wymagają dyspozycji J.
4. Podaj działającą ścieżkę, komendę testu i wynik w [rekordzie linii](../lanes/README.md) i dzienniku sesji. Przy ocenie porównuj tę samą wersję na tych samych danych. [Protokół integracji](integration.md)
