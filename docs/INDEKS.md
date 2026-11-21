# Indeks materiałów UKNF

Punkt startowy dla członka zespołu lub agenta. Brief i załączniki UKNF określają wymagania. Relacja mentora uzupełnia przebieg sprawy. Ocenę planu, wyniki sond oraz działanie aplikacji należy traktować jako osobne rodzaje dowodów.

## Najważniejsze informacje

- M1 wiąże autora, firmę, publikację i URL, także dla polskojęzycznej reklamy firmy transgranicznej. M2 dotyczy własnego marketingu firmy. M3 wymaga treści konkretnej oferty oraz sprawdzenia zakresu uprawnień.
- W briefie jest jeden silnik i trzy moduły. Tabela M2 ma 19 wierszy. W pięciu dostarczonych plikach brak korpusu postów, etykiet testowych i umów reklamowych.
- Działający monitor czterech profili ma prywatną bazę, raport dzienny i timer. Drugie wywołanie usługi potwierdziło 50 wpisów bez zmian. Odbioru wymagają automatyczne wyzwolenie zegarowe, nowe publikacje zaobserwowane prospektywnie, jakość klasyfikacji i obieg sprawy w aplikacji.
- Stare szacunki punktów pochodzą z symulacji. Ocena jury UKNF jest w skali 0–10. Przeliczenie na 100 stosuje wagi 30/20/20/20/10.

## Źródła i pliki robocze

Wykaz plików wejściowych projektu, pięciu załączników i artefaktów planowania. Pominięto wewnętrzne metadane Git i prywatne katalogi narzędzi. Prefiks SHA-256 identyfikuje treść w momencie inwentaryzacji. Bieżący plan i historia ocen są dokumentami aktualizowanymi; ich oceniane rewizje identyfikuje protokół jury.

| Plik | Znaczenie | SHA-256 (prefiks) |
|---|---|---|
| [Opis Wyzwania HackNation UKNF 19.11.pdf](/home/codexdev/.codex/attachments/23c9b7f4-6a2a-4983-9d7f-d107361f0cb1/Opis%20Wyzwania%20HackNation%20UKNF%2019.11.pdf) | Ta sama treść co brief w repo. | 0f81bb48a02078 |
| [ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.docx](/home/codexdev/.codex/attachments/23c9b7f4-6a2a-4983-9d7f-d107361f0cb1/ZASO%CC%81B%20DLA%20UCZESTNIKO%CC%81W%20-%20InvestWatch%20-%20kryteria%20oceny%20informacji%20o%20ryzyku.docx) | Oficjalne 19 pozycji M2, z rozbiciem ID 12. Tabela nie określa wag. | 3b04ddfe41acf7 |
| [Załącznik do Tematu 1 Wyzwanie KNF HackNation.docx](/home/codexdev/.codex/attachments/23c9b7f4-6a2a-4983-9d7f-d107361f0cb1/Za%C5%82a%CC%A8cznik%20do%20Tematu%201%20Wyzwanie%20KNF%20HackNation.docx) | Definicje firm i pięć odsyłaczy do rejestrów. T1 i T2 mają tę samą część merytoryczną. | 8fdb8e8207c6a7 |
| [Załącznik do Tematu 2 Wyzwanie KNF HackNation.docx](/home/codexdev/.codex/attachments/23c9b7f4-6a2a-4983-9d7f-d107361f0cb1/Za%C5%82a%CC%A8cznik%20do%20Tematu%202%20Wyzwanie%20KNF%20HackNation.docx) | Definicje firm i pięć odsyłaczy do rejestrów. T1 i T2 mają tę samą część merytoryczną. | 4b071d6a865ac3 |
| [Załącznik do tematu 3 Wyzwanie KNF HackNation 2026.docx](/home/codexdev/.codex/attachments/23c9b7f4-6a2a-4983-9d7f-d107361f0cb1/Za%C5%82a%CC%A8cznik%20do%20tematu%203%20Wyzwanie%20KNF%20HackNation%202026.docx) | Definicja rekomendacji osobistej i instrumentów. | 1787295e85632b |
| [settings.json](../.claude/settings.json) | Hooki SessionStart i PreCompact. | 62de13ac1d573c |
| [AGENTS.md](../AGENTS.md) | Reguły pracy projektu. | c552463b8125c5 |
| [CLAUDE.md](../CLAUDE.md) | Wejście dla agentów, worktree i przeglądy. | 224926a133ecb7 |
| [HACKATHON.md](../HACKATHON.md) | Misja, harmonogram i bramki. | 61957fe2c97093 |
| [START_PROMPT.md](../START_PROMPT.md) | Historyczny prompt uruchomieniowy, decyzje kosztowe i stan sprzed kompletu załączników. | a86e26f7fc36e4 |
| [TEAM_BOARD.md](../TEAM_BOARD.md) | Cztery linie z rozłącznym zakresem i kryteriami. | 7548f7a9d512f1 |
| [2026-11-21-additional-sites.json](../data/probe-snapshots/2026-11-21-additional-sites.json) | Trzy odkryte strony usług BDM i błąd dostępu innego źródła. | 1f91ddb8aeb6b3 |
| [2026-11-21-browser-check.json](../data/probe-snapshots/2026-11-21-browser-check.json) | Sonda materiału ETF na trzech rozmiarach ekranu i oferty doradczej, wybrane elementy DOM i skróty zrzutów. | 90bf7000691495 |
| [2026-11-21-browser-files.json](../data/probe-snapshots/2026-11-21-browser-files.json) | Zrzuty PNG i ekstrakty DOM z dopasowanymi skrótami bajtów. | 87f411d36c44c1 |
| [2026-11-21-discovery-check.json](../data/probe-snapshots/2026-11-21-discovery-check.json) | Odsyłacze od domen, dwa datowane cytaty partnerstwa i dodatkowe profile. | d938a42087f858 |
| [2026-11-21-evidence.sha256](../data/probe-snapshots/2026-11-21-evidence.sha256) | Lista utrwalonych wejść do walidacji. | 53e5bc3de2be8d |
| [bos-1440.json](../data/probe-snapshots/browser/bos-1440.json) | Wybrane elementy, styl i geometria z tego widoku. | 951ce729b6ddcf |
| [bos-1440.png](../data/probe-snapshots/browser/bos-1440.png) | Zrzut początkowego widoku. | 2d8a22fe4f64c6 |
| [xtb-1440.json](../data/probe-snapshots/browser/xtb-1440.json) | Wybrane elementy, styl i geometria z tego widoku. | f2eb7e2c8b54ee |
| [xtb-1440.png](../data/probe-snapshots/browser/xtb-1440.png) | Zrzut początkowego widoku. | 190ea12e24765f |
| [xtb-390.json](../data/probe-snapshots/browser/xtb-390.json) | Wybrane elementy, styl i geometria z tego widoku. | f2bafc9519c693 |
| [xtb-390.png](../data/probe-snapshots/browser/xtb-390.png) | Zrzut początkowego widoku. | c33ed1efdb6eef |
| [xtb-768.json](../data/probe-snapshots/browser/xtb-768.json) | Wybrane elementy, styl i geometria z tego widoku. | 9d3fdb58c64fa3 |
| [xtb-768.png](../data/probe-snapshots/browser/xtb-768.png) | Zrzut początkowego widoku. | 95c6c422d42899 |
| [esma_mif_passport_to_PL.json](../data/probe-snapshots/knf/esma_mif_passport_to_PL.json) | 26 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 3d290d5443217a |
| [knf_FI_historyczne.json](../data/probe-snapshots/knf/knf_FI_historyczne.json) | 52 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 85b1cae8bfe7c9 |
| [knf_TFI.json](../data/probe-snapshots/knf/knf_TFI.json) | 53 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | ce493c9018c5be |
| [knf_agenci_prawne.json](../data/probe-snapshots/knf/knf_agenci_prawne.json) | 26 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 5ac08758e6ba42 |
| [knf_banki_art70.json](../data/probe-snapshots/knf/knf_banki_art70.json) | 17 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | f3f400d398a605 |
| [knf_banki_maklerskie.json](../data/probe-snapshots/knf/knf_banki_maklerskie.json) | 10 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | f42c0992b69487 |
| [knf_banki_powiernicze.json](../data/probe-snapshots/knf/knf_banki_powiernicze.json) | 11 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 61a0e71a8b9de3 |
| [knf_categories.json](../data/probe-snapshots/knf/knf_categories.json) | 13 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 50cfc5fcf9e4d2 |
| [knf_cofniete_zezwolenie.json](../data/probe-snapshots/knf/knf_cofniete_zezwolenie.json) | 3 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 11a767b366e1b1 |
| [knf_domy_maklerskie.json](../data/probe-snapshots/knf/knf_domy_maklerskie.json) | 28 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 86f8fdeded4791 |
| [knf_notyfikacje_zagr_FI.json](../data/probe-snapshots/knf/knf_notyfikacje_zagr_FI.json) | 712 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | b39b74327db56f |
| [knf_oddzialy_zagr_FI.json](../data/probe-snapshots/knf/knf_oddzialy_zagr_FI.json) | 10 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 24cd10f19aa46e |
| [knf_rejestr_FI.json](../data/probe-snapshots/knf/knf_rejestr_FI.json) | 51 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 69e702e4decaf5 |
| [knf_subcategories.json](../data/probe-snapshots/knf/knf_subcategories.json) | 13 grup. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | 5a0372c81bc02c |
| [knf_warnings_parsed.json](../data/probe-snapshots/knf/knf_warnings_parsed.json) | 669 rekordów. Kategoria według nazwy pliku; liczby różnych rejestrów mogą się pokrywać. | f01637abf0ee37 |
| [crawl2.py](../data/probe-snapshots/scripts/crawl2.py) | Sonda stronicowanych kategorii KNF. | b265e6d6516818 |
| [crawl_knf.py](../data/probe-snapshots/scripts/crawl_knf.py) | Pobiera strukturę kategorii KNF. Błąd HTTP w tym skrypcie może zwrócić pustą listę. | 3fc0c4a7a539c8 |
| [rsc_parse.py](../data/probe-snapshots/scripts/rsc_parse.py) | Parser zapisu stanu HTML użyty do rozpoznania źródeł. | fde6b0b96f4c48 |
| [2026-11-21-source-check.json](../data/probe-snapshots/social/2026-11-21-source-check.json) | Dwie pary odczytów YouTube/TikTok, URL, hashe i długości opisów. | fc21de8d5f5d80 |
| [gat.out](../data/probe-snapshots/social/gat.out) | HTML strony biblioteki reklam Google. | f479b3f9997d13 |
| [gatc_creatives.out](../data/probe-snapshots/social/gatc_creatives.out) | 5 metadanych kreacji, dwa elementy z odsyłaczem do obrazu. | 57586e69bedc8f |
| [tt_oembed.out](../data/probe-snapshots/social/tt_oembed.out) | Osadzenie pojedynczego filmu, ograniczone metadane. | ef7ba1731c4cbc |
| [JUDGING.md](JUDGING.md) | Historia symulacji i punktacja kolejnych wersji. | wersjonowany opis |
| [PLAN-PO-KONSULTACJI.md](PLAN-PO-KONSULTACJI.md) | Pierwsza wersja po konsultacji, zawęża demo do analityka. | wersjonowany opis |
| [PLAN-REALIZACJI.md](PLAN-REALIZACJI.md) | Bieżący plan wykonawczy, próby odbioru i warunki prezentacji. | wersjonowany opis |
| [PLAN.md](PLAN.md) | v3.1, szeroka architektura i hipotezy. Do porównań historycznych. | wersjonowany opis |
| [RESEARCH.md](RESEARCH.md) | Historyczne sondy, pomiary modelu, źródła i ryzyka. Część hipotez zweryfikowano na nowo. | ce2c0bbeab79b3 |
| [UKNF - Pełna treść zadania konkursowego.pdf](brief/UKNF%20-%20Pe%C5%82na%20tre%C5%9B%C4%87%20zadania%20konkursowego.pdf) | Dokument źródłowy. Trzy moduły, wymagania techniczne i walidacja. | 3833db29bceaf2 |
| [UKNF - Regulamin Zadania Konkursowego.pdf](brief/UKNF%20-%20Regulamin%20Zadania%20Konkursowego.pdf) | Dokument źródłowy. Warunki zgłoszenia, terminy, wagi oceny i załączniki formalne. | 739237ba9fa6b0 |
| [Urząd_Komisji_Nadzoru_Finansowego__UKNF_-_Pełna_treść_zadania_konkursowego.txt](brief/Urz%C4%85d_Komisji_Nadzoru_Finansowego__UKNF_-_Pe%C5%82na_tre%C5%9B%C4%87_zadania_konkursowego.txt) | Kopia robocza tekstu. Trzy moduły, wymagania techniczne i walidacja. | 250944779676d4 |
| [Urząd_Komisji_Nadzoru_Finansowego__UKNF_-_Regulamin_Zadania_Konkursowego.txt](brief/Urz%C4%85d_Komisji_Nadzoru_Finansowego__UKNF_-_Regulamin_Zadania_Konkursowego.txt) | Kopia robocza tekstu. Warunki zgłoszenia, terminy, wagi oceny i załączniki formalne. | d3c1f530ffb47e |
| [contracts.md](hackathon/contracts.md) | Pięć kontraktów do integracji z wariantami awarii. | f6a5622f28519c |
| [demo.md](hackathon/demo.md) | Scenariusz pokazu trzech modułów i odtworzenia offline. | 50a4e004a552b3 |
| [integration.md](hackathon/integration.md) | Zasady integracji, READY i awans wersji. | 03fc70e9bf7530 |
| [playbook.md](hackathon/playbook.md) | Procedura pracy i integracji. | 8bd6a6517f5c3e |
| [README.md](lanes/README.md) | Instrukcja katalogu rekordów linii. | 3ab2c9ab67d74c |
| [TEMPLATE.md](lanes/TEMPLATE.md) | Wzór rekordu linii od przyjęcia do przekazania. | 0c8fb9494f6962 |
| [oceny-wersje-planu.tar.gz](oceny-wersje-planu.tar.gz) | Dwie wcześniejsze wersje dokumentu ocenione w tej sesji. | 0ca87ad8e83a6c |
| [check_agent_docs.py](../tools/check_agent_docs.py) | Sprawdza strukturę instrukcji i składnię narzędzi, nie gotowość produktu. | cc66b19454e294 |
| [check_plan_evidence.py](../tools/check_plan_evidence.py) | Sprawdza kompletność archiwum, spójność twierdzeń i skróty plików. | bbd351225a0ffb |
| [hack_context.sh](../tools/hack_context.sh) | Ładowanie statusu przy starcie sesji. | 92ae6238e095dd |
| [hack_join.py](../tools/hack_join.py) | Wybór wolnej linii z tablicy. | e28339e92e0e29 |
| [hack_ready.sh](../tools/hack_ready.sh) | Weryfikacja czystej linii i integralności przed integracją. | 219d52f6a9dd4d |
| [hack_start.sh](../tools/hack_start.sh) | Tworzenie worktree i rekordu linii. | ecb32e0ab35871 |
| [hack_status.py](../tools/hack_status.py) | Odczyt zajętych linii i rekordów. | 1f3817a0db1234 |
| [test_plan_evidence.py](../tools/test_plan_evidence.py) | Odtwarza błędne przypadki wykryte w niezależnej recenzji bramki. | 06d86b2a578033 |
| [MONITORING.md](MONITORING.md) | Stan i granice obserwacji, plan rozszerzenia próby i braki do pełnej punktacji. | 26c550178a11cc |
| [ODBIOR-UKNF.md](ODBIOR-UKNF.md) | Macierz wymagań, stan, właściciele i próby odbioru. | 6d0b457e8ae6f8 |
| [watch_sources.py](../tools/watch_sources.py) | Pobieranie, wersjonowanie i raport dzienny. | 6f2cb8040a88eb |
| [watch_sources.json](../tools/watch_sources.json) | Lista czterech profili pod obserwacją. | d2a0a6fa60b9ca |
| [test_watch_sources.py](../tools/test_watch_sources.py) | Testy parserów, wersji, błędów i historii. | 900d008e808788 |
| [session_log.py](../tools/session_log.py) | Atomowy dziennik podsumowań sesji. | b0922388b6ba1e |
| [test_agent_context.py](../tools/test_agent_context.py) | Test synchronizacji, izolacji i równoległego zapisu. | a771cffd5c2f25 |
| [investwatch-watch.timer](../ops/user-systemd/investwatch-watch.timer) | Harmonogram czasu polskiego. | abddb9465a3ac6 |
| [investwatch-watch.service](../ops/user-systemd/investwatch-watch.service) | Lokalna jednostka pobierająca. | 86e771a5570c6b |
| [run-watch.sh](../ops/user-systemd/run-watch.sh) | Zapis dziennego raportu i wyniku przebiegu. | eb0a24c13a001a |

## Kontekst hackathonu

- [2026-11-19-szkielety.md](../../session-logs/2026-11-19-szkielety.md) — Handoff 2026-11-19: przygotowanie do HackNation
- [2026-11-21-handoff-risk-miner.md](../../session-logs/2026-11-21-handoff-risk-miner.md) — Handoff 21.11.2026 (ok. 15:40): Risk Miner (MFiPR)
- [2026-11-21-handoff-wybor-zadania.md](../../session-logs/2026-11-21-handoff-wybor-zadania.md) — Handoff 21.11.2026 (ok. 15:15): wybór zadania HackNation i stan przygotowań
- [2026-11-21-investwatch-plan-po-panelu.md](../../session-logs/2026-11-21-investwatch-plan-po-panelu.md) — InvestWatch · wynik panelu i start implementacji
- [2026-11-21-investwatch-po-konsultacji.md](../../session-logs/2026-11-21-investwatch-po-konsultacji.md) — InvestWatch po konsultacji z UKNF · 21 listopada 2026
- [2026-11-21-risk-miner-plan-julie-91.md](../../session-logs/2026-11-21-risk-miner-plan-julie-91.md) — Risk Miner · 21.11.2026, 16:20 CET

W katalogu nadrzędnym dokumenty ANALIZA, TLDR, RANKING, KONKURENCJA, KONKURENCJA_REPO i CSV dotyczyły porównania wyzwań. NAGRODY zestawia warunki nagród. PRZEWAGI, PRZEWAGA_ML i TRUDNE_RZECZY opisują wcześniejsze przewagi i ryzyka różnych projektów. PITCH zawiera szablon pokazu. Te źródła zachowują kontekst wyboru zadania. Katalogi innych konkursów i repozytoria vendor są projektami zewnętrznymi wobec materiałów UKNF.
