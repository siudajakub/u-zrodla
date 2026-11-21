# Trzy starty bez dostępu do Internetu

Na hoście z Dockerem, gotowym obrazem i zależnościami demonstratora uruchom:

```sh
python3 tests/offline/verify.py --root "$PWD"
```

Każda próba tworzy osobny projekt Compose, kontenery API i workera oraz puste katalogi pod `.runtime/proof`. Wewnętrzna sieć bez wyjścia na Internet, wyłączony harmonogram live i wyłącznie lokalne wagi są częścią testu. Limit CPU wynosi 1 na usługę. Skrypt sprawdza rozwiązane montowania przed startem i faktyczną sieć po starcie. Odczyt HTTP pochodzi z loopbacku w kontenerze API, ponieważ wewnętrzny bridge może wyłączyć forwarding portu na hoście. Kontenery i sieć testowa są zamykane również po niepowodzeniu.

21 XI 2026 wszystkie trzy starty dostarczyły **17 spraw, 17 wersji i 17 wyników lokalnego modelu semantycznego**. Czas od wywołania Compose do gotowej kolejki HTTP wyniósł kolejno **3,67 s**, **4,01 s** i **4,63 s**. W pierwszej próbie dodatkowy upload MP4 został rozpoznany przez lokalny Vosk. Cytat z jedną nazwą marki miał zakres 0,33–3,60 s. Najwyższy odczyt `memory.peak` workera wyniósł 635,7 MiB przy limicie 1200 MiB. Dla API było to 55,5 MiB. Docker nie wskazał zakończenia przez OOM.

W trzeciej próbie skrypt czeka na atomowe przejęcie zadania, wysyła SIGKILL do własnego workera, przyspiesza wygaśnięcie wyłącznie tej dzierżawy na bazie testowej i wznawia kontener. Drugi właściciel ukończył ten sam identyfikator zadania. Baza miała jeden zakończony skan, dwie próby przetworzenia i 17 różnych identyfikatorów spraw. Szczyt pamięci trzeciego przebiegu dotyczy wznowionego kontenera.

Wyniki maszynowe zawiera [raport](proof-2026-11-21.json). HEAD podczas próby zawierał dodatkowe robocze poprawki rejestracji zadań Huey. Pole `codeSha256` obejmuje rzeczywiste pliki montowanych modułów i Compose, również nowe pliki spoza indeksu. Skrót zgadzał się przed i po trzech próbach. Aby porównać zawartość przyszłej rewizji:

```sh
python3 tests/offline/verify.py --root "$PWD" --fingerprint-only
```
