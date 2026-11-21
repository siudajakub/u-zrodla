# InvestWatch — docelowy plan rozwiązania (v3.1 — poprawki po rundzie 3, nieoceniane przez sędziów)

Aktualny [plan realizacji po ocenie sędziów](PLAN-REALIZACJI.md) rozwija [pierwszą wersję po konsultacji](PLAN-PO-KONSULTACJI.md). Poniżej zachowano wersję v3.1 do porównania.

Zespół: J (jeden inżynier) + równolegli agenci kodujący. Czas budowy: 21.11 ok. 16:00 → 22.11 11:00.
Sprzęt demo: 4 vCPU, 14 GB RAM, bez GPU. Całość startuje przez `docker compose up`.

## 1. Co pokazujemy jury (golden path, 2–3 min)

1. `docker compose up` na czystym checkoucie (modele i Chromium są w obrazach, start bez internetu); logowanie; dashboard wstaje z danymi z ostatniego przebiegu, konsola przeglądarki jest pusta.
2. Operator klika „Uruchom skan”. W widoku kolejki widać zadania per kolektor, rotację UA/proxy, liczbę pobranych dokumentów. Główna ścieżka to skan na żywo (licznik żądań i rotacja UA/proxy z prawdziwych odpowiedzi); `DEMO_MODE=replay` jest ścieżką awaryjną i gwarantuje alert, gdy źródło akurat nic nowego nie zwróci.
3. Przychodzi alert Socket.io „wysokie ryzyko” — nowa reklama CFD bez wymaganego ostrzeżenia. Kliknięcie otwiera kartę znaleziska.
3a. Inspektor otwiera w swojej przeglądarce post na TikToku / Instagramie / Facebooku i klika rozszerzenie „Zgłoś do InvestWatch”: treść, zrzut i URL trafiają do tego samego potoku, po kilku sekundach przychodzi alert z oceną (ukryta reklama z kodem polecającym, bez oznaczenia).
4. Karta znaleziska: zrzut ekranu z nałożonymi ramkami (ostrzeżenie vs. nagłówek z zyskiem), pomiar „czcionka ostrzeżenia 8 px / dominująca 16 px = 0,5 < 1,0”, lista reguł, które zadziałały, z cytatem i podstawą prawną, dane firmy z rejestru KNF, status rekordu do zmiany (nowy → w analizie → potwierdzony / odrzucony).
5. Panel kalibracji: suwak progu przelicza na żywo TP/FP/FN/TN, precision, recall i punkt na krzywej P/R na oznaczonym zbiorze walidacyjnym; lista znalezisk powyżej progu zmienia się od razu.
6. Widok „Reklamujący”: finfluencer (platforma, identyfikator, zasięg) ↔ link afiliacyjny / kod polecający ↔ firma inwestycyjna, z flagą „brak oznaczenia reklamy” i sprawdzeniem w rejestrze agentów firm inwestycyjnych; kolejka spraw sortowana wg ryzyko × zasięg.
7. „Teczka dowodowa” PDF jednym kliknięciem: zrzut, SHA-256, znacznik czasu, URL, reguły, podstawy prawne; wpis w dzienniku dowodów (tylko dopisywanie, łańcuch hashy). Harmonogram ponownie odwiedza URL-e znalezisk i pokazuje, czy treść zniknęła lub zmieniła się po interwencji.
8. Strona `/process` (generowana z danych repozytorium): linie pracy agentów, modele, bramki jakości z przykładami zablokowanych scaleń, raport skanu zależności, SBOM.

## 2. Źródła danych i kolektory

Każdy kolektor implementuje jeden interfejs (`Collector.discover()` / `fetch()` → `RawDocument` JSON) i ma „kartę legalności” (podstawa dostępu, robots.txt, limit zapytań). Wszystkie korzystają ze wspólnego klienta HTTP z rotacją User-Agent, pulą proxy z `.env` (domyślnie pusta = ruch bezpośredni), limitem zapytań na domenę i ponowieniami.

| Kolektor | Moduł | Dostęp (sprawdzony 21.11) | Status w MVP |
|---|---|---|---|
| Rejestry KNF (domy maklerskie, banki, TFI, oddziały, 712 notyfikacji transgranicznych z nazwami handlowymi i domenami, agenci firm inwestycyjnych) | 1, 2, 3 | JSON API wyszukiwarki podmiotów KNF, bez klucza | na żywo + snapshot |
| Lista ostrzeżeń publicznych KNF (669 wpisów) | 1, 3 | jedna strona HTML | na żywo + snapshot |
| Google Ads Transparency Center, region PL | 2 (reklamy samych firm), 1 | publiczny endpoint bez logowania (nieoficjalny) | na żywo, cache |
| Strony WWW firm inwestycyjnych z rejestru (strony produktowe, landing pages) — Playwright, zrzut ekranu + DOM | 2 | publiczne, z poszanowaniem robots.txt | na żywo |
| YouTube: RSS kanałów, Data API v3 (klucz w `.env`), opisy i napisy PL | 1 | oficjalne API / RSS | na żywo |
| Strony firm doradczych / wealth management / family office. Odkrywanie nowych podmiotów: zapytania frazowe („wealth management”, „family office”, „doradztwo inwestycyjne”, „zarządzanie portfelem”) do Google Ads Transparency (reklamodawcy w PL) i YouTube Data API, linki wychodzące z już zebranych treści, lista seedów; każdy podmiot zestawiany z rejestrami KNF — interesują nas ci, których tam nie ma. Lista ostrzeżeń służy do weryfikacji i jako przykłady pozytywne, nie jako główne źródło | 3 | publiczne | na żywo |
| Rozszerzenie przeglądarki „Zgłoś do InvestWatch” (Manifest V3): inspektor przegląda FB/IG/TikTok jak zwykły użytkownik, jednym kliknięciem wysyła tekst posta, zrzut widoku, URL, autora i liczniki zasięgu | 1, 2, 3 | działanie użytkownika, bez automatu | na żywo |
| Monitor zgłoszonych URL-i: harmonogram ponownie sprawdza adresy zgłoszone rozszerzeniem (oficjalne oEmbed TikToka i YouTube'a, dla pozostałych dostępność strony), z rotacją UA/proxy | 1, 2, 3 | oficjalne oEmbed | na żywo |
| Instagram Graph API (Business Discovery): posty i zasięg obserwowanych kont twórców | 1 | oficjalne API, wymaga aplikacji Meta i tokenu | włączany, jeśli token będzie dostępny przed 23:00; inaczej kolektor na nagraniach |
| Meta Ad Library (Facebook + Instagram), oficjalne API `ads_archive` | 1, 2 | wymaga tokenu po weryfikacji tożsamości (dni) | kolektor gotowy, testowany na nagranych odpowiedziach; na żywo po wpisaniu tokenu |
| TikTok Commercial Content API | 1, 2 | wymaga zatwierdzonej aplikacji | poza MVP; interfejs kolektora i karta legalności opisane |
| Import plików (zrzut ekranu, wideo do 90 s, paczka danych od UKNF z pendrive'a) | 1, 2, 3 | — | na żywo |

Stron Facebooka, Instagrama i TikToka nie scrapujemy automatem: ich regulaminy i robots.txt tego zabraniają, a narzędzie organu nadzoru musi działać zgodnie z prawem. Pokrycie tych platform w MVP: (a) rozszerzenie przeglądarki — także dla organicznych postów finfluencerów, których biblioteki reklam nie widzą; (b) kolektory oficjalnych API gotowe na tokeny; (c) YouTube (w tym Shorts) jako w pełni automatyczny kanał wideo; (d) parser publicznych stron tych platform nie wchodzi do MVP — jeśli UKNF jako organ uzna go za dopuszczalny, jest to nowa klasa kolektora. Wideo z importu i rozszerzenia: klatki co 2 s → OCR (ostrzeżenie wyświetlane, czas ekspozycji); napisy i opis jako tekst. Rozpoznawanie mowy jest poza MVP.

Dane podmiotu reklamującego (moduł 1): platforma, identyfikator konta, nazwa wyświetlana, URL profilu, zasięg (obserwujący / wyświetlenia), powiązane konta na innych platformach (po linkach i kodach), status w rejestrze agentów.

## 3. Moduły analityczne

Wspólny potok: usunięcie HTML → normalizacja → deduplikacja (hash + podobieństwo) → embeddingi (`multilingual-e5-small`, MIT) w pgvector → reguły → klasyfikator → scoring → ujednolicony obiekt `Finding`.

- **Moduł 1 (podmioty trzecie, finfluencerzy):** rozpoznanie firmy inwestycyjnej w treści (słownik marka → podmiot → status z rejestru KNF), wykrycie linków afiliacyjnych i kodów polecających, brak oznaczenia reklamy, obietnice zysku, promocja CFD bez ostrzeżenia, rekomendacja dotycząca konkretnego instrumentu bez ujawnienia tożsamości i konfliktu interesów (MAR art. 20, rozp. 2016/958). Wynik: baza „firma – reklamujący – treść – URL”, odświeżana harmonogramem; każda wersja treści zachowana.
- **Moduł 2 (informacja o ryzyku):** 25 reguł wyprowadzonych z art. 44 rozporządzenia 2017/565, art. 83c ustawy o obrocie, decyzji KNF o CFD (wzorce obowiązkowych ostrzeżeń, limity dźwigni, zakaz bonusów) i wytycznych ESMA. Reguły tekstowe (regex, słowniki), layoutowe (OCR RapidOCR + DOM: wysokość czcionki ostrzeżenia vs. dominującej, kontrast, pozycja, proporcja znaków ryzyko/korzyść) i semantyczne (klasyfikator). Każda reguła w pliku YAML ma: podstawę prawną z dokładnością do litery przepisu, typ detektora, wagę i oznaczenie, czy próg wynika wprost z przepisu (np. czcionka ostrzeżenia ≥ dominującej — art. 44 ust. 2 rozp. 2017/565; dokładna litera każdego przepisu jest sprawdzana ze źródłem przed zamrożeniem reguł), czy jest wskaźnikiem pomocniczym (np. kontrast). Oficjalny załącznik UKNF mapujemy bez zmian w kodzie.
- **Moduł 3 (shadow advisory):** frazy silne i słabe wskazujące na rekomendacje osobiste lub zarządzanie portfelem, kontr-sygnały (zezwolenie KNF, wpis w rejestrze agentów), sprawdzenie podmiotu w rejestrach i na liście ostrzeżeń, wzbogacenie z KRS. Podstawy: art. 69 i 76 ustawy o obrocie (zezwolenie, definicja doradztwa), art. 9 rozp. 2017/565 (rekomendacja osobista), art. 178 (sankcja). W module 1 każdy sygnał wskazuje właściwość: KNF (art. 79, 83c, decyzja CFD) albo UOKiK (nieoznaczona reklama).
- **Scoring:** cechy regułowe + embedding → regresja logistyczna z kalibracją Platta, osobno dla każdego modułu; wynik ciągły 0–1, cztery kategorie (niskie / do przeglądu / wysokie / krytyczne). Każda flaga ma cytat lub ramkę na zrzucie oraz podstawę prawną („bez dowodu nie ma flagi”); dla flagi z klasyfikatora dowodem jest zdanie o najwyższym wkładzie w wynik.
- **LLM lokalny:** Ollama, domyślnie Gemma 4 E2B (Apache-2.0); Bielik 4.5B v3 (Apache-2.0) zastępuje ją tylko, jeśli wygra porównanie na 30 próbkach (decyzja w ADR). Rola: asynchroniczne uzasadnienie po polsku w JSON dla znalezisk powyżej progu (cytat weryfikowany jako podciąg źródła) oraz wariant „LLM zero-shot” w tabeli ablacji. Nie zmienia wyniku liczbowego, więc panel kalibracji pozostaje odtwarzalny. Treść ze stron jest traktowana jako dane — test odporności na wstrzyknięcie instrukcji jest w zestawie ewaluacyjnym.
- **Zbiór kalibracyjny:** ok. 150 realnych próbek dobranych warstwowo (znane reklamy CFD dla M2, treści podmiotów z listy ostrzeżeń dla M3, posty z linkami afiliacyjnymi dla M1; częstość klas pokazana w panelu). Człowiek oznacza według jednostronicowej instrukcji **zanim** zobaczy etykiety modelu: 40 próbek na ślepo między 19:00 a 20:30, resztę do 01:00. Zgodność raportujemy pod właściwą nazwą: „człowiek–model”; „człowiek–człowiek” na 40 próbkach, o których oznaczenie prosimy mentora UKNF lub innego uczestnika. Reguły są zamrażane przed oznaczaniem. Negatywy: materiały firm z rejestru z poprawnym ostrzeżeniem, treści edukacyjne, oferty doradztwa nieinwestycyjnego. Warianty syntetyczne służą wyłącznie do treningu. Podział grupowy bez wycieku; zbiór testowy zamrożony, jego hash w repo. Próbki UKNF z pendrive'a stają się osobnym zbiorem testowym z precision/recall per moduł. Generowane automatycznie: karta modelu i karta zbioru danych.
- **Panel kalibracji:** liczy metryki z zapisanych wyników bez ponownej inferencji, pokazuje przedziały ufności (bootstrap), tabelę ablacji (same reguły / reguły + embeddingi / LLM zero-shot) krzywą niezawodności z wynikiem Briera i rekomendowany próg operacyjny wyliczony z ustawianego stosunku kosztu przeoczenia do kosztu fałszywego alarmu. Próg dobierany na walidacji, raportowany na teście. Każdy moduł ma własny próg i suwak; kategorie są stałymi przedziałami wyniku. Panel pokazuje wprost, że precision dotyczy częstości klas w zbiorze, nie w produkcji.
- **Pętla zwrotna:** decyzje analityka (potwierdzone / odrzucone) trafiają do kolejki etykiet; „retrenuj” tworzy nową wersję modelu porównywaną z bieżącą na zamrożonym teście, promocję zatwierdza człowiek.
- **Odtwarzalność decyzji:** `Finding` zapisuje wersję kolektora, modelu, zestawu reguł i próg obowiązujący w chwili flagowania.

## 4. Architektura (Docker Compose, lekkie serwisy)

Jedno repozytorium, niezależne katalogi `services/<nazwa>/`, każdy z własnym Dockerfile i lockfile, bez wspólnego workspace. Wspólne są tylko `contracts/` (OpenAPI, AsyncAPI dla zdarzeń Socket.io, JSON Schema obiektu `Finding`) i `docker-compose.yml`.

| Serwis | Technologia | Rola |
|---|---|---|
| `dashboard` | React + Vite + TypeScript (build produkcyjny serwowany przez nginx), Recharts, socket.io-client, TanStack Table | filtry (data, źródło, ryzyko, moduł), trendy, statusy, alerty, kalibracja, widok „Reklamujący”, `/process` |
| `api` | FastAPI + python-socketio, Alembic | REST, agregator `Finding`, logowanie (JWT, role analityk/administrator), statusy z dziennikiem audytu (kto, kiedy, z czego na co), przypisanie sprawy, notatki, eksport CSV/XLSX i teczki PDF, alerty WebSocket |
| `crawler` | Python, arq (kolejka + cron z `schedules.yaml`), httpx, Playwright | kolektory (w tym synchronizacja rejestrów KNF), kolejka zadań, harmonogram, ponowienia |
| `ai` | Python, sentence-transformers, scikit-learn, RapidOCR | preprocessing, embeddingi, reguły, scoring, dopasowanie podmiotów |
| `ollama` (profil `full`) | Ollama | lokalny LLM |
| `postgres` | PostgreSQL + pgvector | metadane, treści, wektory, wyniki |
| `valkey` | Valkey (BSD) | kolejka i pub/sub |
| `objectstore` | SeaweedFS (Apache-2.0), API S3 | zrzuty ekranu, surowy HTML, PDF |

Osiem kontenerów, z czego pięć naszych. Własność danych: do bazy pisze wyłącznie `api` (migracje Alembic); `crawler` i `ai` zapisują przez jego wewnętrzne REST. Socket.io używa adaptera Valkey, więc `api` można replikować. Modele Pydantic i typy TypeScript są generowane z `contracts/`, więc serwisy nie rozjeżdżają się ze schematem.

Uruchomienie on-prem: obrazy przypięte po digest, modele (e5, klasyfikatory, OCR) i Chromium wbudowane w obrazy, wagi LLM jako osobny wolumen w pakiecie offline; `make offline-bundle` (`docker save`) i test startu bez sieci; `healthcheck` + `depends_on: service_healthy`; limity pamięci i budżet RAM per serwis w README (łącznie poniżej 6 GB w profilu domyślnym bez LLM, ok. 10 GB w profilu `full`). Frontend łączy Socket.io dopiero po pozytywnym `/health` serwowanym przez nginx, więc restart `api` nie zostawia błędów w konsoli. Crawler działa bez roota w osobnej sieci wyjściowej, z blokadą adresów prywatnych (ochrona przed SSRF przy imporcie URL).

Przepływ: harmonogram (cron w `crawler`) → kolejka → `crawler` → surowy dokument (object store + metadane) → kolejka analizy → `ai` → `Finding` → `api` → Socket.io → `dashboard`. Skalowanie: `docker compose up --scale crawler=N` (workery kolejki); `ai` skaluje się liczbą workerów w ramach budżetu RAM. Nowe źródło = nowa klasa kolektora; nowa reguła = wpis YAML.

Tryby: produkcyjnie domyślny jest tryb na żywo; `DEMO_MODE=replay` odtwarza nagrane odpowiedzi źródeł przez ten sam potok (deterministyczny alert na scenie, działa bez internetu).

## 5. Bezpieczeństwo i jakość

- `make security`: pip-audit, npm audit, osv-scanner, trivy, gitleaks, SBOM CycloneDX (syft), bramka licencji pakietów i wag modeli (tylko permisywne; brak AGPL/GPL). Progi blokujące dla zależności własnych: podatność High lub wyższa albo niedozwolona licencja zatrzymuje scalenie; podatności obrazów bazowych trafiają do `docs/security/EXCEPTIONS.md` (właściciel, uzasadnienie, data wygaśnięcia). Raport w `docs/security/REPORT.md`.
- Sekrety wyłącznie w `.env` (jest `.env.example`). Zero płatnych API.
- „Console.log”: ESLint `no-console`, test Playwright sprawdzający brak błędów i ostrzeżeń konsoli na każdym ekranie, także po restarcie `api` (ponowne połączenie Socket.io bez błędów); backend loguje JSON (structlog) z identyfikatorem korelacji.
- README do 120 linii: Quick Start, wymagania sprzętowe, konfiguracja serwisów; lint odrzucający pustosłowie.

## 6. Proces wytwarzania z asystentami AI

Opisany w `docs/process/AI_SDLC.md` (jeden ekran + diagram) i egzekwowany skryptami:

specyfikacja (wymagania R-01…R-nn z briefu) → kontrakt → linia pracy (jeden agent, własny worktree, zadeklarowane pliki, model i effort) → implementacja → bramki: testy, kontrakt, przegląd innym modelem, ewaluacja klasyfikatora (próg regresji F1), bezpieczeństwo → kolejka scalania → bramka demo.

Pięć standardów z twardym dowodem w repo (każdy do otwarcia w 30 sekund):

| Standard | Dowód |
|---|---|
| AGENTS.md (Linux Foundation) | `AGENTS.md` — jedne reguły dla ludzi i agentów; walidator dokumentów koordynacyjnych |
| Spec-driven development | `docs/spec/requirements.md` + macierz śledzenia generowana z historii gita (wymaganie → linia → commit → test) |
| OpenAPI 3.1 / AsyncAPI 3 / JSON Schema | `contracts/`, walidowane bramką, z nich generowane typy |
| ADR (MADR) + Conventional Commits | `docs/decisions/`, hook `commit-msg` |
| CycloneDX + OSV (łańcuch dostaw) | `sbom/`, `docs/security/REPORT.md`, bramka blokująca |

Dodatkowo, wyraźnie oznaczone jako „mapowanie, nie deklaracja zgodności”: jedna tabela NIST SSDF 800-218A i OWASP Top 10 for LLM (test wstrzyknięcia instrukcji w ewaluacji), karta modelu i karta zbioru, nadzór człowieka nad decyzją (status i próg ustawia analityk; dziennik audytu).

Artefakty powstają automatycznie: rejestr sesji agentów (JSONL z hooków: linia, model, effort, commit), metryki procesu, raporty przeglądów innym modelem, **dziennik bramek z każdym zablokowanym scaleniem i jego przyczyną**, `docs/process/AI_USAGE.md` (jakie dane wolno przekazać asystentom; dane UKNF z pendrive'a nie trafiają do asystentów chmurowych; runtime w 100% on-prem). Człowiek zatwierdza specyfikację, kontrakty i decyzje (ADR); po zielonych bramkach scalenie zatwierdza człowiek jednym kliknięciem (czas przeglądu jest mierzony); zmiany reguł, modelu i kontraktów wymagają pełnego przeglądu człowieka. Bramka ewaluacji: test McNemara na zamrożonym zbiorze testowym. Strona `/process` pokazuje liczby: sesje agentów, scalenia, scalenia zablokowane z przyczyną, uwagi z przeglądów naprawione przed scaleniem. Jest statycznym widokiem tych danych i nie podlega cięciu.

## 7. Harmonogram

| Czas | Etap | Warunek wyjścia |
|---|---|---|
| 21.11 16:00–18:30 | rozszerzenie procesu, wymagania, kontrakty, szkielet Compose z healthcheckami, snapshot rejestrów, zbieranie próbek do oznaczenia | kontrakty zamrożone, `docker compose up` daje pusty dashboard |
| 18:30–23:00 | fala 1: kolejka + kolektory (KNF, Google Ads, WWW), reguły tekstowe M2, API z logowaniem i audytem, lista znalezisk, tryb replay, rozszerzenie przeglądarki; człowiek oznacza próbki | pierwsza integracja: realne znalezisko i zgłoszenie z rozszerzenia widać w UI |
| 23:00–02:30 | fala 2: YouTube, M1, M3, scoring, panel kalibracji, alerty, statusy, pomiar layoutu z ramkami, teczka PDF | wszystkie trzy moduły w UI, suwaki działają na realnych etykietach |
| 02:30–05:00 | fala 3: dziennik dowodów, OCR klatek wideo, `/process`, widok „Reklamujący”, monitor URL-i | feature freeze 05:00 |
| 05:00–08:30 | stabilizacja: czysty checkout bez sieci, test konsoli, skan zależności, pakiet offline, uzasadnienia LLM (profil `full`) jeśli stabilne | tag demo |
| 08:30–10:30 | README, prezentacja PDF, film do 3 min, zgłoszenie | wysłane do 10:30 |

Poza MVP od początku: rozpoznawanie mowy, analiza obrazu przez LLM, metawyszukiwarka, Telegram, wizualizacja grafu (jest tabela powiązań), TikTok Commercial Content API. Kolejność cięć, gdy zabraknie czasu: OCR klatek wideo → monitor URL-i → kolektor Meta Ad Library na nagraniach → pętla zwrotna → uzasadnienia LLM. Nie tniemy: trzech modułów, kolejki, alertów, paneli kalibracji z realnymi etykietami, rozszerzenia przeglądarki, skanu zależności, startu offline, `/process`.

## 8. Jawne ograniczenia

- Facebook, Instagram i TikTok: automatyczne odkrywanie treści dopiero po uzyskaniu tokenów oficjalnych API; w MVP treści z tych platform zgłasza inspektor rozszerzeniem przeglądarki.
- Endpoint Google Ads Transparency jest nieoficjalny i może się zmienić; jest cache i tryb replay.
- Zbiór kalibracyjny jest mały (ok. 150 realnych próbek); metryki podajemy z przedziałami ufności, osobno dla danych realnych i syntetycznych.
- Reguły modułu 2 są wstępne do czasu otrzymania oficjalnego załącznika.
