<!-- Generated from AGENTS.md. Edit AGENTS.md and run python3 tools/check_agent_docs.py --sync. -->

# UKNF #InvestWatch

InvestWatch automatycznie odkrywa i flaguje materiały z polskiego rynku. Źródło wymagań to [ZIP UKNF i pięć opracowań](docs/zrodla-uknf/README.md). [Cel i wyróżnik](HACKATHON.md), [macierz odbioru](docs/ODBIOR-UKNF.md) i [kolejność prac](docs/PLAN-REALIZACJI.md) rozdzielają wymagania, dowody i decyzje zespołu. J odpowiada za decyzje produktowe. Trafność oceniaj na całych kampaniach z udokumentowanymi etykietami i mianownikami. Zachowaj pełny kontekst materiału, niepewność i kontrolę ujemną.

## Start sesji

1. Uruchom `sh tools/hack_context.sh`. Zobaczysz status linii i ostatni wpis każdej z najnowszych sesji. Claude Code wykonuje ten odczyt przy starcie, wznowieniu i po kompaktowaniu.
2. Przeczytaj [TEAM_BOARD.md](TEAM_BOARD.md) i [kontrakty](docs/hackathon/contracts.md) dla swojego zakresu. Gdy wracasz do konkretnej sesji, użyj `python3 tools/session_log.py latest --session ID`. Jeśli pracujesz w linii, przeczytaj jej [rekord](docs/lanes/README.md).
3. Zgoda na bazę została udzielona. Gałęzie main i hack/integration oraz cztery izolowane worktree istnieją. Sprawdź aktualny HEAD i stan linii poleceniami git status i python3 tools/hack_status.py. Kapitan scala do hack/integration i promuje sprawdzony commit do main.

## Orkiestracja i odbiór

W sesji Claude Code prowadzonej na polecenie J obowiązuje [prompt Fable](START_PROMPT.md) i [plan Opus/Sonnet](docs/fable/REALIZACJA.md). Fable wyłącznie orkiestruje, a wykonanie i niezależny odbiór deleguje Opus i Sonnet. Poniższy przydział dotyczy sesji Codex.

ASTRA pełni wyłącznie rolę orkiestratora. Wyznacza cel, rozdziela zakresy, uzgadnia kontrakty, ocenia dowody, koordynuje integrację i komunikuje wynik J. Wykonanie, test i niezależny przegląd deleguje agentom SOL i TERRA. Historyczne nazwy gałęzi opisują poprzednią rundę.

Każdą falę prowadź z agentami. Do rutynowych zmian i odtwarzalnych sprawdzeń wybieraj niższy lub średni reasoning, do diagnoz, niejednoznacznych danych i architektury wysoki. Przy spornej hipotezie niech jeden agent ją sprawdzi, drugi spróbuje obalić na tym samym materiale. Zapisz kontrprzykład, decyzję i test rozstrzygający. Do oceny angażuj osobnych sędziów SOL i TERRA, zanim poznają nawzajem swoje punkty. Dbaj o limit zasobów hosta.

Najpierw odbierz funkcję w normalnej ścieżce użytkownika, następnie upraszczaj wygląd i optymalizuj. Po zmianie UI powtórz ten sam scenariusz na desktopie i telefonie. W web/ obowiązują też lokalne instrukcje Astryx. Rozpoczynając kontynuację przeczytaj [mapę kolejnej fali](docs/KONTYNUACJA.md).

## Log sesji

Przy istotnej decyzji, zakończeniu etapu i przekazaniu pracy zapisz krótki wpis. Podaj cel, następny krok oraz decyzję i wynik próby, jeśli je masz.

```sh
python3 tools/session_log.py append --goal 'Sprawdzić odtwarzanie skanu' \
  --decision 'Użyć dwóch datowanych stanów replay' --test 'Drugi odczyt zwrócił zero zmian' \
  --next 'Podłączyć kartę źródła do API'
python3 tools/session_log.py latest
```

CLI sam rozpoznaje ID sesji w Codex oraz w Claude Code z aktywnym hookiem. Jeśli środowisko go nie udostępnia, uruchom `python3 tools/session_log.py id` raz i podawaj ten sam identyfikator przez `--session ID`. Log projektu to osobne, dopisywane zdarzenia JSONL w ignorowanym katalogu `session-logs/` głównego checkoutu, wspólnym dla powiązanych worktree na tym hoście. Zapisuj skrót operacyjny bez sekretów, danych osobowych i transkryptów.

Rekord linii przechowuje zakres plików, stan, weryfikację i krok integracji. Handoff obejmujący więcej projektów HackNation trafia do nadrzędnego `hacknation/session-logs/`.

## Co działa i jak sprawdzać

Działające demo, komendę startową i dwa przypadki do odsłuchania opisują [README](README.md) i [odbiór](docs/DEMO-ODBIOR.md). [Monitoring](docs/MONITORING.md) łączy znane profile z odkrywaniem twórców. Modele i prywatne dane robocze są poza Gitem.

```sh
python3 tools/check_agent_docs.py
python3 tools/check_plan_evidence.py
python3 -B -m unittest discover -s tools -p 'test_*.py'
```

Edytuj tutaj reguły wspólne dla Codex i Claude Code. Po zmianie uruchom `python3 tools/check_agent_docs.py --sync`, aby odtworzyć `CLAUDE.md`. Domyślne uruchomienie walidatora wykrywa rozjazd.

## Linie i integracja

- Kapitan zarządza `hack/integration` i promocją zweryfikowanego demo na `main`. Po przygotowaniu bazy każda linia `hack/<owner>/<feature>` ma osobny worktree, jednego piszącego, kryterium odbioru i rozłączny zakres. Uzgodnij zależności przed rozpoczęciem kodowania.
- Buduj działające piony z obsługą pustego wyniku, oczekiwania, błędu i powtórzenia. Przy zmianie kontraktu uzgodnij ją z odbiorcami i odnotuj w dokumentacji integracji. Przy blokadzie powyżej 15 minut zapisz przyczynę, wariant awaryjny i powiadom kapitana.
- Zapisz komendę i faktyczny wynik sprawdzenia w rekordzie linii. Zmiany gotowe do scalenia wymagają świeżego przeglądu przez drugiego agenta i bramki `sh tools/hack_ready.sh`. Kolejność ustala [protokół integracji](docs/hackathon/integration.md).
- Commit, push i deploy wykonuj dopiero na wyraźne polecenie J. W zatwierdzonych commitach używaj trailerów `Lane:` i `Gate:`. Proweniencję pracy agentów zapisuj w logu i rekordzie linii. Pomiń automatyczne przypisywanie współautorstwa modelom.
- Koszty wymagają zgody J. Kod produktu korzysta z zależności i modeli na licencjach permisywnych. Trzymaj klucze, dokumenty prywatne i dane osobowe poza repo i próbkami do demonstracji.
- Gotowość demo wymaga przejścia [scenariusza i wariantu awaryjnego](docs/hackathon/demo.md) oraz pełnych sprawdzeń na dokładnie tej wersji, którą zobaczy jury.
