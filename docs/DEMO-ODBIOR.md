# Odbiór lokalnego demo

## Bieżące stanowisko

Pokaż drogę od automatycznego wskazania materiału do dosłownego dowodu i zapisanej decyzji. W jasnym podglądzie Astryx wybierz filtr spraw oznaczonych do sprawdzenia. Przy dowodzie otwórz źródło, kontekst, wersję i czas. W M2 linki do zrzutu i DOM odnoszą się do konkretnego pomiaru. W M3 sprawdź cytat oraz zakres uprawnienia na rzeczywistej ofercie DM BOŚ. [Scenariusz](hackathon/demo.md) · [Brief UKNF](zrodla-uknf/BRIEF.md)

Próba podglądu w Chromium na odizolowanej bazie przeszła kolejkę, odsłuch 0,33–3,60, decyzję i odczyt historii, odnośniki do dokładnych plików M2, źródła oraz zmianę progu przy 1440 i 390 px. Przełączenie zakładki zachowało czas odtwarzacza i treść uzasadnienia. Próba użyła materiałów z bazowego replay. Wyniki pomiaru z nowszych archiwów przypisuje się do ich własnych odcisków i dat. [Powtórzenie próby](../tests/offline/README.md)

### Sprawdzenie wersji z archiwami XTB i BOŚ

Na odizolowanej bazie z 20 sprawami replay oba pulpity przeszły w Chromium scenariusz przy 1440 × 1000 i 390 × 844. Podgląd przeszedł dodatkowo filtr wskazań modelu i pomiarów, rzeczywisty konflikt 409 z zachowaniem szkicu oraz zapis decyzji na sprawie BDM ze znakiem ukośnika w ID.

W kryterium 3 ETF sprawdzono odnośniki przypisane do zapisanych stanów strony. Widok po przewinięciu pokazuje dosłowną wzmiankę o dywidendach oraz oddzielnie zmierzone ostrzeżenie. W telefonie wzmianka zajmuje 100% swojej widocznej powierzchni, a ostrzeżenie pozostaje poza kadrem. Zrzut, DOM i zapisane pomiary odnoszą się do tej samej wersji. W sprawie DM BOŚ odtworzono sugestię modelu E5 z dosłownym kontekstem, źródło oraz pozycję 5 z datowanego wykazu KNF. [Test przeglądarkowy](../tests/offline/README.md)

Widok kryterium 3 na [komputerze](pokaz/etf-desktop.png) i [telefonie](pokaz/etf-telefon.png) pokazuje twierdzenie o dywidendach. [Karta M3](pokaz/oferta-m3.png) zawiera sugestię i kontekst oferty BOŚ. Obrazy pochodzą z interaktywnej próby zespołu na wersji interfejsu o skrócie JS 51407984.

Na końcowym odcisku b572eda8 powtórzono oba pulpity na osobnej bazie. Pełna próba Chromium dodatkowo sprawdziła nowy upload WAV, lokalne ASR, odpowiedź firmy, umowę i aneks, 409, HTTP Range 206 oraz odświeżenie. Nie zarejestrowano błędów JavaScript. [Trzy starty Compose offline i odcisk kodu](../tests/offline/proof-zip-2026-11-21.json) · [Oceny sędziów](JUDGING.md)

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

Trzy odrębne projekty Compose dostały puste bazy i wewnętrzną sieć Docker bez wyjścia do internetu. W każdym HTTP zwrócił 17 spraw i 17 sugestii semantycznych. Zmierzono kolejno 4,37 s, 3,69 s i 4,92 s. W trzecim przebiegu po zatrzymaniu workera i przyspieszeniu wygaśnięcia jego dzierżawy drugi właściciel ukończył ten sam skan. Liczba wersji pozostała równa liczbie spraw. Najwyższy zmierzony szczyt pamięci workera to 949,9 MiB. Rewizję próby, odcisk kodu, metodę i wyniki zapisuje [raport](../tests/offline/proof-2026-11-21.json). [Powtórzenie próby](../tests/offline/README.md)

W przebiegu z końcową integracją odsyłaczy kolejka live uzyskała **78 materiałów i jednego nowego kandydata** względem utrwalonego stanu. Raport zawiera stan częściowy m.in. z powodu przekierowań do strony zgody. Baza pulpitu po tym przebiegu miała 93 odrębne sprawy oraz 22 zapamiętane tożsamości źródłowe, w tym kandydatów, wydawców i profile startowe. Liczby te nie są liczbą naruszeń ani oszacowaniem całego rynku.
