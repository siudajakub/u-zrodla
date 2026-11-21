# Analiza dowodów InvestWatch

## Odsłuch własnego nagrania

Wymagane są Python 3.11+, ffmpeg oraz Linux x86-64 lub ARM64. Na stanowisku pokazowym sprawdzono Linux x86-64. Pierwsze polecenie pobiera model i bibliotekę. Weryfikuje SHA-256 z `analysis/asr-lock.json` i instaluje pliki w ignorowanym katalogu `.runtime/asr`. Ponowne rozpoznawanie działa offline, na CPU.

```sh
python3 -m analysis.setup_asr
python3 -m analysis.transcribe /ścieżka/do/nagrania.mp4
python3 -B -m unittest analysis.test_engine
```

`analysis.transcribe.transcribe_file(path)` obsługuje lokalny MP4/M4A, WAV, WebM, MP3, FLAC, AIFF, AAC lub Ogg. Dekoder konwertuje pierwszą ścieżkę audio na mono PCM 16 kHz. Limit całego nagrania wynosi 120 sekund. Funkcja zwraca surowe wypowiedzi z początkiem i końcem w sekundach oraz średnią pewnością słów ASR. Cisza daje pustą listę. Błąd dekodowania i brak modelu mają odrębne komunikaty. `transcribe_excerpt(path, seconds=45)` analizuje początek pliku, także zapisane kompletne ramki częściowego MP3 z RSS. Przy montowaniu własnych wag można ustawić `INVESTWATCH_VOSK_MODEL` i `INVESTWATCH_VOSK_LIBRARY`. Do środowiska wykonawczego wystarczą katalog modelu, biblioteka oraz ffmpeg. Na tej maszynie zajmują odpowiednio 92 i 25 MiB przed doliczeniem ffmpeg.

Model języka polskiego to `vosk-model-small-pl-0.22`, a natywny silnik pochodzi z oficjalnego pakietu Vosk 0.3.45. Oba udostępniono na Apache 2.0. [Katalog modeli](https://alphacephei.com/vosk/models) · [Pakiet i dystrybucje](https://pypi.org/project/vosk/0.3.45/) · [Licencja silnika](https://github.com/alphacep/vosk-api/blob/master/COPYING)

## Próbka do odtworzenia

Zespół napisał scenariusz i wygenerował głos w eSpeak-NG 1.51 oraz planszę poglądową. Autor, firma, data publikacji i umowa w tym przykładzie są fikcyjne. Plik `analysis/media/studio.mp4` zawiera obraz H.264 i dźwięk AAC. Model rozpoznał trzy wypowiedzi. Przy 4,35–7,26 s rozpoznaje „partnerem programu jest firma aurora”. Przy 8,61–12,51 s rozpoznaje „ten materiał powstał we współpracy z firmą aurora”. Opis zawiera jedynie zapowiedź przewodnika. Wynik określa priorytet przeglądu i pozwala odsłuchać oba fragmenty. Potwierdzenie płatności wymaga dodatkowego dowodu.

```sh
python3 -m analysis.transcribe --replay analysis/media/studio.mp4
```

Replay wymaga identycznego SHA-256. Nowy plik trafia do modelu poleceniem bez `--replay`. Przy odtwarzaniu próbki wystarczają dołączone media i zachowany JSON. Aby zbudować ją ponownie, użyj `python3 -m analysis.make_sample` z eSpeak-NG, Pillow, fontami FreeFont i ffmpeg/libx264 w środowisku deweloperskim. Następnie zapisz świeży wynik CLI z nowego pliku. Głos i wartość confidence odnoszą się do rozpoznania słów. Reguły wskazujące reklamę mają własny wynik punktowy.

Drugi klip to fikcyjna publikacja „Od czego zacząć?”. Zawiera jedną wypowiedź, którą Vosk odczytał od 0,33 do 3,60 s jako „pobierz aplikację aurora i otwórz rachunek”. Marka pojawia się raz. Reguła łączy ją z zachętą do otwarcia rachunku i podnosi priorytet z 12 do 74. W dostępnym opisie nie wykryto etykiety reklamy. Karta pozostawia pytanie o charakter relacji analitykowi. Ten sam tekst z oznaczonym opisem, neutralna wzmianka i deklaracja partnerstwa stanowią odrębne kontrole.

```sh
python3 -m analysis.transcribe analysis/media/wezwanie.mp4
python3 -m analysis.transcribe --replay analysis/media/wezwanie.mp4
```

Generator ze znacznikiem `--cta` odtwarza drugą próbkę.

## Pochodzenie i zakres wyników

M1 porównuje wynik tego samego zestawu reguł dla opisu i dla opisu rozszerzonego o wypowiedzi. Dla przykładowego klipu to odpowiednio 12 i 94 punkty. Pole `speechOnlySignal` wymaga dostępnego opisu bez sygnału na poziomie 60 punktów oraz sygnału w nagraniu. Materiał z sygnałem w obu kanałach ma to pole wyłączone.

## Od wskazania do dowodu

Kolejka oznacza sprawę, gdy analiza zwraca `reviewSuggestion.state=review`. Karta pokazuje powód, źródło wskazania i dokładny fragment. Przy wskazaniu semantycznym pokazuje nazwę oraz wersję modelu, jeśli są w zapisie. Stan niepewny pozostaje widoczny w szczegółach. Reguły mają osobny wynik punktowy. Brak sygnału i brak wyniku modelu mają osobne stany.

M2 zwraca 19 wierszy, tryb i uzasadnienie każdego sprawdzenia. Dla przechwyconych widoków kliknięcie w kryterium odsłania zrzut i odpowiadający mu DOM. Odcisk i data wiążą wniosek z wersją materiału. Karta pokazuje dostępne współrzędne, wielkość pisma, widoczność, kontrast i odległość między elementami. W starszej migawce XTB zachowano kandydata wykrytego po słowie „ryzyk” przy 1440, 768 i 390 px. Kandydat był poza pierwszym ekranem. Dokładny kontrast i dopasowanie ostrzeżenia wymagają właściwego pomiaru. Materiał o prowizji i twierdzenie o potencjalnym zysku mają osobne znaczenie. [Oferta ETF](https://www.xtb.com/pl/etf)

M3 przedstawia literalny fragment, operatora strony i datowane ustalenia z rejestrów. Oferta DM BOŚ jest rzeczywistą kontrolą pozytywną dla rozpoznania usługi i kontrolą fałszywego alarmu o braku uprawnienia. W starszym zapisie FinanceWell wyszukiwanie nazwy zwraca dwie pozycje z wykazu agentów oraz wspólnego mocodawcę. Przypisanie sprawy do konkretnego wiersza wymaga pewnej tożsamości i zakresu. [Oferta DM BOŚ](https://bossa.pl/oferta/doradztwo-inwestycyjne) · [FinanceWell](https://financewell.pl/o-nas/)

Kalibracja mierzy koszt kierowania materiału do przeglądu. Zapisuje liczebność próbki, odcisk zbioru, macierz TP/FP/TN/FN i błędy z treścią oraz oczekiwaniem. Koszt to `2 × FN + FP`. Historyczna próbka zawierała 4 publiczne przykłady i 9 syntetycznych kontroli z etykietami autora. Przy progu 60 dawała TP 5, FP 1, TN 4 i FN 3. Próba ilustruje decyzję progową. Odrębny, wcześniej oznaczony zbiór kampanii pozwala ocenić skuteczność na nowym ruchu. [Próby odbiorowe](../docs/DEMO-ODBIOR.md)
