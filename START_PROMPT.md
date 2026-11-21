> Archiwalny prompt sprzed kompletu załączników. Aktualne wejście do pracy to [HACKATHON.md](HACKATHON.md) i [plan po panelu](docs/PLAN-REALIZACJI.md).

# Prompt startowy: UKNF #InvestWatch (implementacja)

Wklej poniższy tekst jako pierwszą wiadomość nowej sesji Claude Code otwartej w `/home/codexdev/projects/hacknation/uknf-investwatch`.

---

Jesteśmy na HackNation 2026 i robimy zadanie **UKNF #InvestWatch – na straży inwestorów** (30 000 zł brutto). Kodowanie kończy się **22.11.2026 o 11:00**, więc wszystko musi być gotowe, zgłoszone i zamrożone przed tą godziną. Ocena odbywa się na demo, a pitch dla finalistów zaczyna się 22.11 o 15:15. Pracujesz w tym folderze. Zespół to J plus agenci, a J jest wąskim gardłem, więc oszczędzaj jego uwagę.

## Najpierw przeczytaj (w tej kolejności)
1. `/home/codexdev/projects/hacknation/session-logs/2026-11-21-handoff-wybor-zadania.md`: kontekst, decyzje J, ryzyka.
2. `docs/brief/` w całości: treść zadania i regulamin.
3. `docs/RESEARCH.md`: sprawdzone źródła danych, reguły modułu 2, licencje, MCP, „wow”, zmiany w kicie, §9 „Czego potrzebujemy od J”.
4. `docs/PLAN.md` (v3.1, bez oceny sędziów po ostatnich poprawkach) i `docs/JUDGING.md` (3 rundy: 80/82/83 i uwagi sędziów).
5. `data/probe-snapshots/`: snapshoty rejestrów KNF, ESMA i listy ostrzeżeń oraz skrypty sond.
6. Pliki kitu: `AGENTS.md`, `CLAUDE.md`, `HACKATHON.md`, `TEAM_BOARD.md`, `docs/hackathon/*`. Na razie to szablony do wypełnienia.

## Ustalenia J (obowiązują)
- **Legalność dostępu do danych nie jest blokerem.** Docelowo UKNF wynegocjuje dostęp. Liczy się działające demo. Budujemy kolektory dla **FB, IG i TikToka** (Playwright z rotacją User-Agent i proxy, czego wymaga specyfikacja), konektor do API biblioteki reklam Meta gotowy do podpięcia tokena oraz konektory do tego, co działa już dziś: rejestry KNF, lista ostrzeżeń, Google Ads Transparency, YouTube RSS/oEmbed, strony WWW firm. Na demo pokazujemy kolektory na żywo tam, gdzie się da, a resztę na próbkach z pendrive'a i na zapisanych przechwyceniach, z wyraźnym oznaczeniem źródła.
- **Nie dodawaj Claude jako współautora** w commitach ani PR. Proweniencję pracy agentów zapisujemy w trailerach `Lane:` / `Gate:` i w logu JSONL.
- **Commit, push i deploy tylko na wyraźne polecenie J.**
- **Tylko permisywne licencje** (MIT/Apache/BSD), bo prawa przechodzą na UKNF. Bez MinIO (AGPL): używamy SeaweedFS albo zwykłego FS. Bez Redis 8: używamy Valkey. Bez firecrawl (AGPL).
- **Zero płatnych API.** Modele lokalne przez Ollamę lub llama.cpp, np. Gemma 4 (Apache-2.0) albo Bielik. Każdy koszt najpierw zatwierdza J.

## Dane od J
Ten blok uzupełnia J przed wysłaniem promptu:
- Pendrive UKNF: [ścieżka do skopiowanych danych / „brak”]
- Załącznik z wymogami do modułu 2: [ścieżka / „brak”]
- Odpowiedzi mentora UKNF: [wklej]
- Klucz YouTube Data API: [w `.env`, nie w repo / „brak”]
- Token Meta Ad Library: [w `.env` / „brak”]
- Demo na: [laptop / VPS], internet na sali: [tak/nie]
- Zgoda na przegląd każdej linii drugim modelem: [tak/nie]

## Zadanie dla Ciebie: orkiestrator
Jesteś orkiestratorem i delegujesz pracę do subagentów przez narzędzie Agent. Model (`haiku` / `sonnet` / `opus`) i `effort` dobierasz do trudności, na co J wyraźnie się zgodził. Niezależne prace puszczaj równolegle, na rozłącznych plikach.

1. **Domknij plan (maks. 45 min).**
   - Wpisz dane z pendrive'a i odpowiedzi mentora.
   - Zamknij lukę FB/IG/TikTok zgodnie z ustaleniami J.
   - Zaktualizuj reguły modułu 2 według załącznika.
   - Utnij zakres do golden path, który na pewno zdąży, z jawnym planem cięć.
   - Wypełnij `HACKATHON.md` (misja, golden path, zamrożenia, plan cięć), `AGENTS.md` (komendy, zasady, licencje, proweniencja), `CLAUDE.md`, `TEAM_BOARD.md` (linie AVAILABLE: rozłączne pliki, kryteria akceptacji, zależności, model i effort), `docs/hackathon/contracts.md` (kontrakty między serwisami z przykładowym JSON) oraz `docs/hackathon/demo.md`.
   - Walidator musi przejść: `python3 tools/check_agent_docs.py`.
2. **Jedna szybka runda 3 sędziów** (opus, wysoki effort; mogą to być `bullseye:hackathon-judge`) według oficjalnej rubryki UKNF przeliczonej na 100 pkt (30/20/20/20/10), z flagą wykonalności. Popraw tylko to, co jest tanie. Zapisz wynik w `docs/JUDGING.md` jako rundę 4.
3. **Implementacja w liniach** (worktree lub gałąź `hack/<owner>/<feature>` na linię, według kitu), mniej więcej w tej kolejności:
   - L0 szkielet: Docker Compose jedną komendą, Postgres, Valkey + kolejka, SeaweedFS lub FS, `.env.example`, healthchecki, skan zależności (pip-audit / npm audit) w Makefile lub CI;
   - L1 kolektory: rejestry KNF, lista ostrzeżeń, Google Ads Transparency, YouTube, strony WWW firm; FB, IG i TikTok przez Playwright z rotacją oraz konektor Meta API; harmonogram;
   - L2 przetwarzanie i AI: preprocessing, deduplikacja, embeddingi, lokalny model przez Ollamę, scoring, agregator 3 modułów;
   - L3 reguły modułu 2: deterministyczne i modelowe, pomiar wyraźności ostrzeżenia na zrzucie z podstawą prawną;
   - L4 moduł 3, czyli shadow advisory: porównanie z rejestrem KNF i listą ostrzeżeń;
   - L5 dashboard React: filtry, wykresy trendów, statusy rekordów, Socket.io, **panel kalibracji** (suwak progu z krzywą precyzji i pełności na zbiorze oznaczonym);
   - L6 „wow”: rozszerzenie przeglądarki „Zgłoś do InvestWatch” i strona `/process` z historią pracy agentów;
   - L7 zbiór kalibracyjny: ok. 200 próbek oznaczonych regułami lub LLM i zweryfikowanych na próbce przez J albo mentora.
4. **Bramki:**
   - każda linia ma testy i działa w Compose przed scaleniem;
   - kod bez `console.log` (UKNF ocenia „Console.log”);
   - README minimalny, „bez AI slop”.
5. **Materiały do zgłoszenia:**
   - opis i tytuł;
   - PDF (bullseye `pitch-deck`);
   - README;
   - wideo do 3 min (bullseye `demo-video`, opcjonalne);
   - kontrola liczb (bullseye `prove-it`);
   - końcowy przegląd (bullseye `submission-pack` / `final-sweep`);
   - skan sekretów (`vendor/hackathon-playbook/scripts/secret_scan.sh`) przed upublicznieniem repo.
6. **Harmonogram** (rozpisz w `HACKATHON.md`, użyj podium `clock`):
   - draft w HackTribe do 20:00 (robi J);
   - zamrożenie funkcji ok. 05:00;
   - zamrożenie demo ok. 08:00;
   - kompletne zgłoszenie ok. 10:00 (bufor do 11:00).
7. **Handoff:** przy każdym kamieniu milowym aktualizuj worklog lub lane record według kitu, a na końcu dopisz handoff do `/home/codexdev/projects/hacknation/session-logs/`.

## Pierwsza odpowiedź do J
Krótko:
- co zrozumiałeś;
- czego jeszcze brakuje z bloku „Dane od J”;
- plan pierwszych 60 minut;
- które linie odpalasz równolegle i jakim modelem.

Potem działaj bez zbędnych pytań. Zatrzymuj się tylko przy kosztach, kontach, commitach i decyzjach produktowych.
