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

## Pochodzenie i zakres wyników

M1 porównuje wynik tego samego zestawu reguł dla opisu i dla opisu rozszerzonego o wypowiedzi. Dla przykładowego klipu to odpowiednio 12 i 94 punkty. Pole `speechOnlySignal` wymaga dostępnego opisu bez sygnału na poziomie 60 punktów oraz sygnału w nagraniu. Materiał z sygnałem w obu kanałach ma to pole wyłączone.

M2 zwraca 19 wierszy, tryb i uzasadnienie każdego sprawdzenia. Archiwalne pomiary XTB rejestrują kandydatów z frazą „ryzyk”, geometrię i rozmiary czcionki przy 1440, 768 i 390 px. Znamy ich położenie poza początkowym widokiem i dwa rozmiary pisma. Kontrast, rzeczywista treść całego ostrzeżenia, widok po przewinięciu i dominujący rozmiar w obszarze reklamy wymagają dalszych danych. Adresy `/evidence/browser/` prowadzą do zachowanych plików DOM i PNG w `data/probe-snapshots/browser/`. [Oferta ETF](https://www.xtb.com/pl/etf)

M3 zestawia fragment oferty z datowanymi wpisami KNF. Dla FinanceWell zwraca dwóch kandydatów z wykazu agentów i wspólnego mocodawcę. Dla DM BOŚ rozpoznaje ofertę dopasowania portfela i identyfikuje dom maklerski. W obu przypadkach zakres konkretnego zezwolenia wymaga przeglądu analityka. [FinanceWell](https://financewell.pl/o-nas/) · [DM BOŚ](https://bossa.pl/oferta/doradztwo-inwestycyjne)

Kalibracja mierzy koszt kierowania materiału do przeglądu. Zamrożony zestaw zawiera 4 publiczne przykłady oraz 9 syntetycznych kontroli, z jedną etykietą autora na przypadek. Duplikat kampanii partnerskiej z kolejnego tygodnia nie zwiększa próby. Każdy błąd ma tekst, oczekiwanie, wynik punktowy i typ. Koszt to 2 × FN + FP. Przy progu 60 występują TP 5, FP 1, TN 4 i FN 3. Zbiór ilustruje decyzję progową. Do oceny trafności na przyszłym ruchu potrzebny jest niezależnie oznaczony korpus.
