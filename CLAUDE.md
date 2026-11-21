<!-- Generated from AGENTS.md. Edit AGENTS.md and run python3 tools/check_agent_docs.py --sync. -->

# UKNF #InvestWatch

Zbuduj jeden obieg sprawy dla analityka UKNF, od odkrycia materiału do decyzji z dowodem. Zacznij od [HACKATHON.md](HACKATHON.md) i [planu realizacji](docs/PLAN-REALIZACJI.md). [Indeks materiałów](docs/INDEKS.md) prowadzi do briefu, załączników i wyników sond.

## Start sesji

1. Uruchom `sh tools/hack_context.sh`. Zobaczysz status linii i ostatni wpis każdej z najnowszych sesji. Claude Code wykonuje ten odczyt przy starcie, wznowieniu i po kompaktowaniu.
2. Przeczytaj [TEAM_BOARD.md](TEAM_BOARD.md) i [kontrakty](docs/hackathon/contracts.md) dla swojego zakresu. Gdy wracasz do konkretnej sesji, użyj `python3 tools/session_log.py latest --session ID`. Jeśli pracujesz w linii, przeczytaj jej [rekord](docs/lanes/README.md).
3. Zgoda na bazę została udzielona. Gałęzie main i hack/integration oraz cztery izolowane worktree istnieją. Sprawdź aktualny HEAD i stan linii poleceniami git status i python3 tools/hack_status.py. Kapitan scala do hack/integration i promuje sprawdzony commit do main.

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
