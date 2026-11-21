# Przekazanie po rewizji źródeł UKNF

W sesji Claude obowiązuje [plan Fable z priorytetem YouTube](../fable/REALIZACJA.md). Poniżej zachowano stan poprzedniej fali.

Zacznij od [pięciu dokumentów konkursowych](../zrodla-uknf/README.md). [Macierz odbioru](../ODBIOR-UKNF.md) określa, co można pokazać i na jakim materiale. [Plan](PLAN-REALIZACJI.md) wyjaśnia, jaki test musi przejść kolejna funkcja.

| Miejsce | Co sprawdzić w kontynuacji |
|---|---|
| M1 | Przejść od skanu do twórcy, cytatu i dokładnego URL. Sprawdzić, czy źródło jest nowo odkryte, monitorowane czy syntetyczne. Wynik warunków umowy pochodzi z osobnego scenariusza demonstracyjnego. |
| M2 | Otworzyć flagę twierdzenia o potencjalnym zysku. Porównać ekran z twierdzeniem z ekranem ostrzeżenia o tym samym produkcie. Sprawdzić osobno ryzyko innego instrumentu i reklamę niskich opłat. |
| M3 | Porównać ofertę i edukację na pełnym dostępnym tekście. Wskazać rzeczywisty fragment modelu, stan tożsamości i datowany zakres zezwolenia. |
| Kalibracja | Pokazać oba rodzaje błędów i rozmiar próby. J podejmuje decyzje produktowe. Etykiety eksperckie wymagają niezależnej osoby z właściwą wiedzą oraz materiału źródłowego w kontekście. |
| Pokaz | Powtórzyć test na dokładnej prezentowanej wersji. Publikacja, commit, koszty i wysyłka wymagają decyzji J. |

Pierwszy panel demo ocenił eaa9c10. Stare pomiary i nowa implementacja mają oddzielne dowody. Lokalny checkout i worktree desk zawierały niezacommitowane zmiany sprzed tej fali. [Testy demo](DEMO-ODBIOR.md) · [Tablica prac](../../TEAM_BOARD.md)

Najnowszy kandydat dał 20 spraw przy każdym z trzech czystych startów offline. [Wyniki tej wersji](../../tests/offline/proof-zip-2026-11-21.json) · [Oceny dwóch sędziów](JUDGING.md). Kolejna próba produktowa dotyczy znalezienia rzeczywistej pełnej oferty podmiotu spoza sprawdzonej pary kontrolnej M3 i ustalenia jej tożsamości, zakresu oraz daty.

Do obejrzenia na beeper-devbox przygotowano lokalny podgląd na porcie 18784 z osobną bazą i wyłączonym odpytywaniem live. Połączenie z innego komputera: `ssh -N -L 18784:127.0.0.1:18784 beeper-devbox`, następnie [otwórz podgląd](http://127.0.0.1:18784/theme-preview/). Zwykły Quick Start na osobnym stanowisku używa portu 8769. Odnośniki do lokalnych plików dowodowych w prezentacji PDF używają standardowego portu 8769, a obrazy dwóch mobilnych ujęć są osadzone w samej prezentacji.
