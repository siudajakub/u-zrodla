# Odbiór lokalnego demo

## Bieżące stanowisko

Pokaż drogę od automatycznego wskazania materiału do dosłownego dowodu i zapisanej decyzji. W jasnym podglądzie Astryx wybierz filtr spraw oznaczonych do sprawdzenia. Przy dowodzie otwórz źródło, kontekst, wersję i czas. W M2 linki do zrzutu i DOM odnoszą się do konkretnego pomiaru. W M3 sprawdź cytat oraz zakres uprawnienia na rzeczywistej ofercie DM BOŚ. [Scenariusz](../hackathon/demo.md) · [Brief UKNF](../zrodla-uknf/BRIEF.md)

Próba podglądu w Chromium na odizolowanej bazie przeszła kolejkę, odsłuch 0,33–3,60, decyzję i odczyt historii, odnośniki do dokładnych plików M2, źródła oraz zmianę progu przy 1440 i 390 px. Przełączenie zakładki zachowało czas odtwarzacza i treść uzasadnienia. Próba użyła materiałów z bazowego replay. Wyniki pomiaru z nowszych archiwów przypisuje się do ich własnych odcisków i dat. [Powtórzenie próby](../../tests/offline/README.md)

### Sprawdzenie wersji z archiwami XTB i BOŚ

Na odizolowanej bazie z 20 sprawami replay oba pulpity przeszły w Chromium scenariusz przy 1440 × 1000 i 390 × 844. Podgląd przeszedł dodatkowo filtr wskazań modelu i pomiarów, rzeczywisty konflikt 409 z zachowaniem szkicu oraz zapis decyzji na sprawie BDM ze znakiem ukośnika w ID.

W kryterium 3 ETF sprawdzono odnośniki przypisane do zapisanych stanów strony. Widok po przewinięciu pokazuje dosłowną wzmiankę o dywidendach oraz oddzielnie zmierzone ostrzeżenie. W telefonie wzmianka zajmuje 100% swojej widocznej powierzchni, a ostrzeżenie pozostaje poza kadrem. Zrzut, DOM i zapisane pomiary odnoszą się do tej samej wersji. W sprawie DM BOŚ odtworzono sugestię modelu E5 z dosłownym kontekstem, źródło oraz pozycję 5 z datowanego wykazu KNF. [Test przeglądarkowy](../../tests/offline/README.md)

Widok kryterium 3 na [komputerze](pokaz/etf-desktop.png) i [telefonie](pokaz/etf-telefon.png) pokazuje twierdzenie o dywidendach. [Karta M3](pokaz/oferta-m3.png) zawiera sugestię i kontekst oferty BOŚ. Obrazy pochodzą z interaktywnej próby zespołu na wersji interfejsu o skrócie JS 51407984.

Na końcowym odcisku b572eda8 powtórzono oba pulpity na osobnej bazie. Pełna próba Chromium dodatkowo sprawdziła nowy upload WAV, lokalne ASR, odpowiedź firmy, umowę i aneks, 409, HTTP Range 206 oraz odświeżenie. Nie zarejestrowano błędów JavaScript. [Trzy starty Compose offline i odcisk kodu](../../tests/offline/proof-zip-2026-11-21.json) · [Oceny sędziów](JUDGING.md)

## Środowisko pokazu i łańcuch dostaw · 21 XI 2026 (linia L)

**Stan startowy pokazu.** `sh ops/demo/start.sh` na czystym stanie odtwarza datowany replay skanu z 21 XI (najpierw replay M2, potem `bootstrap-youtube-replay-v1`, potem kolejki) z paczką mediów zamontowaną do odczytu (`INVESTWATCH_REPLAY_MEDIA=/replay-media`) i harmonogramem live wyłączonym. Oczekiwana kolejka „Co wymaga sprawdzenia”: 4 filmy (7M0rC6-Rueo, AqXHkxDzSDI, OIyPE0z2mng, ZJrT-X08Xwc) w wariancie `qual_d`, próg 60. Bez paczki mediów skrypt odmawia startu (kod 3). Wariant bez Dockera: `sh ops/demo/start-local.sh`. Paczka jest artefaktem poza Gitem: `sh ops/demo/pack-media.sh` tworzy `replay-media-2026-11-21.tar.gz` z sumą SHA-256, a start weryfikuje ją manifestem z repozytorium. Sprawdzono na devboxie Linux x86_64 przy obciążonym hoście (inne procesy, load average 20–60), więc czasy są górnym oszacowaniem; Maca nie uruchamiano.

| Próba (devbox, 21 XI 2026) | Wynik |
|---|---|
| `start-local.sh` od zera, port 18810, nowe venv i pusty stan | `GOTOWE`: 2 skany bootstrapu, kolejka review = 4 filmy, wariant `qual_d`, paczka 17 filmów `ok`, E5 `ready`; skan YouTube replay trwał ok. 7 min (krok analizy 6,5 min) |
| `docker compose config` | poprawny, paczka montowana `read_only`, `INVESTWATCH_DISCOVERY_INTERVAL=0` |
| Czysty start Compose (`start.sh --reset`, projekt `iw-l-test`, port 18811, osobny stan) | `GOTOWE po 397 s`: review = 4 (te same identyfikatory), `all` 1323, `offersM3` 4; limit 1,5 CPU i 1200 MiB, brak OOM i restartów |
| `tests/offline/verify.py` (3 zimne starty, sieć wewnętrzna bez Internetu, 1 CPU) | 3 z 3 przeszły: review = 4 filmy, 296,8 / 290,2 / 296,3 s, E5 `ready`, ASR uploadu 0,33–3,60 s, odtworzenie po SIGKILL workera; końcowa asercja odcisku kodu nie przeszła, bo inni agenci zmieniali kod w trakcie (próba do powtórzenia na zamrożonej wersji) |
| Brak paczki, uszkodzona suma, uszkodzone archiwum | start odmawia z instrukcją (kod 3), nic nie jest uruchamiane |

**Audyty zależności (21 XI 2026, dane z publicznych rejestrów: npm advisory, OSV/PyPI).**

| Zakres | Narzędzie i wersje | Pozycje | Wykrycia |
|---|---|---|---|
| `web/package-lock.json` (React 19.3.1, Astryx 0.7.17, StyleX 0.19.2, esbuild 0.28.2) | `npm audit` (npm 11.19.0, Node 24.21.0), `--package-lock-only` | 181 (13 prod, 169 dev, 26 opcjonalnych) | 0 (info 0, low 0, moderate 0, high 0, critical 0) |
| `api/requirements.lock` (fastapi 0.165.0, starlette 1.10.0, pydantic 2.14.4, uvicorn 0.54.0, huey 3.5.4 i inne) | `pip-audit` 2.10.1, `--no-deps` (zainstalowany tylko w `.runtime/venv`) | 16 | 0 |
| `analysis/semantic-requirements.txt` (numpy 2.2.6, onnxruntime 1.22.1, tokenizers 0.21.4) | `pip-audit` 2.10.1 | 3 | 0 |
| Tryb live mediów: yt-dlp 2026.10.26, youtube-transcript-api 1.2.5 | `pip-audit` 2.10.1 | 2 | 0 |

Nic nie wymagało poprawki. Ograniczenia: baza advisory pokazuje tylko znane wykrycia (brak wykryć nie dowodzi bezpieczeństwa); `--no-deps` sprawdza dokładnie przypięte wersje, nie rozwiązuje zależności przechodnich spoza lockfile (lockfile jest pełny); nie skanowano obrazu `python:3.12-bookworm`, FFmpeg z Debiana ani wag modeli (brak skanera w środowisku). Prymitywów Radix w `web/package-lock.json` w momencie audytu nie było (J1 ich jeszcze nie dodał); po ich dodaniu powtórz `npm audit` w `web/`. yt-dlp i youtube-transcript-api nie należą do `api/requirements.lock` ani do obrazu Compose, więc pobieranie mediów z YouTube w trybie live działa tylko lokalnie: `start-local.sh --live` instaluje je z przypiętych wersji (`ops/demo/live-requirements.txt`).

## Historyczny odbiór · 21 XI 2026

J zatwierdził lokalny commit bazowy 3d03e71 i cztery osobne worktree. SOL odpowiadał za odkrywanie i semantykę, ASTRA za dźwięk i analizę trzech modułów, TERA za interfejs i uruchomienie. Kapitan połączył linie przez API i kolejkę. Aplikacja działa na loopback beeper-devbox. Repozytorium i prezentacja są lokalne.

### Co odtworzyliśmy

| Próba | Faktyczny wynik |
|---|---|
| Kolektor social | Pierwszy przebieg monitora zapisał 50 publikacji z 4 kont, drugi 50 bez zmian. YouTube dostarczył 30 materiałów z 15 różnymi opisami. TikTok dostarczył 20 podpisów bez dat publikacji. |
| Odkrywanie | Niezależna próba z katalogów znalazła 13 twórców poza ośmioma skonfigurowanymi tożsamościami: 11 z Apple Podcasts i 2 z PeerTube. Kolejny skan zapamiętał twórców i odczytał 8 dodatkowych odcinków dzięki rotacji źródeł. Zachowujemy także puste wyniki. Lokalny worker w działającej aplikacji rozpoznał polską mowę w pierwszym wycinku rzeczywistego podcastu „Oszczędnościowe obligacje skarbowe – wybór i inwestowanie w praktyce”. |
| Nagranie spoza demo | Chromium wysłał nowo zakodowany WAV przez pulpit. Lokalny Vosk zwrócił „pobierz aplikację aurora i otwórz rachunek”, od 0,33 do 3,60 s. HTTP Range zwrócił 206. Oryginalny polski materiał i marka są syntetyczne. |
| Obieg analityka | W Chromium działają przejście do czasu nagrania, decyzja i 409 po użyciu starej rewizji, szkic pytania, zapis odpowiedzi i dwa porównania z fikcyjną umową. M2 dostarczył 19 wierszy i działający zrzut. Zmiana progu zmieniła FP/FN w zbiorze 13 grup. Przeglądarka nie zgłosiła błędu JS, widok na 390 px zmieścił się bez poziomego przewijania. |
| Niezależny przegląd i naprawa | Przy przejściu replay → identyczny live skorygowaliśmy pochodzenie bez dublowania wersji. Pierwszy test uploadu wykazał odmienne nazwy zadań przy rejestracji przez HTTP i worker. Ujednoliciliśmy punkt wejścia i powtórzyliśmy test przez prawdziwą przeglądarkę. |
| Zależności | pip-audit sprawdził 37 wersji w zestawieniu Python/Vosk, a npm audit pięć zależności grafu React 18.3.1. Oba zgłosiły zero znanych podatności w sprawdzonym zakresie. Osobnej oceny wymagają obraz bazowy, natywne libvosk, FFmpeg i same wagi. |

#### Przejście z podcastu do nowego kanału

W rzeczywistym opisie polskiego podcastu znaleźliśmy link do filmu gPv19SFBprA. Oficjalne oEmbed YouTube podało publicznego autora i profil @zainwestowani. Strona profilu przekierowała do ekranu zgody. Zapisujemy pochodzenie i status kandydata; ten odczyt nie potwierdził stabilnego ID kanału ani publikacji pobranych z jego Atom. Odrębny test przechodzi dwie fale odkrycia i ponownie otwiera potwierdzony profil po zniknięciu linku. [Film, z którego odczytano autora](https://www.youtube.com/watch?v=gPv19SFBprA)

### Granice pomiaru

M2 zachowuje wszystkie 19 kryteriów, jednak w rzeczywistym przechwyceniu XTB ocenialne są tylko wybrane obserwacje. „Brak danych” pozostaje widoczny. W M3 podobne nazwy FinanceWell prowadzą do dwóch wierszy rejestru, a ustalenie uprawnień i treści oferty należy do analityka. System nie wyprowadza niedozwolonej usługi z samego braku nazwy w rejestrze. Kalibracja dotyczy reguł. Model E5 dostarcza odrębnej sugestii z cytatem, podobieństwem i informacją o niejednoznaczności. Brak wypowiedzianej marki w próbce audio nie mówi, co pokazano w obrazie lub co padło później.

Demo używa SQLite i Huey, dwóch procesów i współdzielonego lokalnego dysku. Wersja demonstracyjna jest przeznaczona dla jednego prywatnego stanowiska. Wdrożenie urzędowe będzie wymagało w szczególności tożsamości operatorów, uprawnień, zasad retencji i odpornych na modyfikację dowodów. Priorytet reguł oraz sugestia modelu nie są rozstrzygnięciem prawnym.

### Modele i licencje

React 18.3.1 korzysta z MIT. Vosk i model PL 0.22 wskazują Apache 2.0. Bazowy multilingual-e5-small ma MIT. Konwersja ONNX jest przypięta do rewizji i sum, a jej karta nie podaje osobnej licencji. Przed redystrybucją wag należy rozstrzygnąć prawa do konkretnego artefaktu lub skonwertować model bazowy we własnym procesie. W użytej dystrybucji osobny systemowy FFmpeg jest kompilacją GPL-2.0-or-later. Zespół nie dołącza prywatnego katalogu runtime do repozytorium. [Vosk](https://alphacephei.com/vosk/models) · [Model bazowy E5](https://huggingface.co/intfloat/multilingual-e5-small) · [Konwersja ONNX](https://huggingface.co/Xenova/multilingual-e5-small) · [FFmpeg](https://ffmpeg.org/legal.html)

### Próba uruchomienia offline

Trzy odrębne projekty Compose dostały puste bazy i wewnętrzną sieć Docker bez wyjścia do internetu. W każdym HTTP zwrócił 17 spraw i 17 sugestii semantycznych. Zmierzono kolejno 4,37 s, 3,69 s i 4,92 s. W trzecim przebiegu po zatrzymaniu workera i przyspieszeniu wygaśnięcia jego dzierżawy drugi właściciel ukończył ten sam skan. Liczba wersji pozostała równa liczbie spraw. Najwyższy zmierzony szczyt pamięci workera to 949,9 MiB. Rewizję próby, odcisk kodu, metodę i wyniki zapisuje [raport](../../tests/offline/proof-2026-11-21.json). [Powtórzenie próby](../../tests/offline/README.md)

W przebiegu z końcową integracją odsyłaczy kolejka live uzyskała **78 materiałów i jednego nowego kandydata** względem utrwalonego stanu. Raport zawiera stan częściowy m.in. z powodu przekierowań do strony zgody. Baza pulpitu po tym przebiegu miała 93 odrębne sprawy oraz 22 zapamiętane tożsamości źródłowe, w tym kandydatów, wydawców i profile startowe. Liczby te nie są liczbą naruszeń ani oszacowaniem całego rynku.
