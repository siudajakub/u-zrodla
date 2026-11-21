# InvestWatch

Lokalne stanowisko analityka rynku finansowego. Wyszukuje nowych twórców, zbiera materiały i pokazuje, który fragment opisu, mowy lub zrzutu uzasadnia sprawdzenie sprawy. Firma, autor, cytat, czas i pochodzenie dowodu pozostają dostępne po zapisaniu decyzji.

## Szybki start

Na przygotowanym beeper-devbox uruchom w katalogu repozytorium:

```sh
sh ops/demo/start.sh
```

Otwórz **http://127.0.0.1:8769**. Na zdalnym stanowisku można użyć tunelu SSH `ssh -N -L 8769:127.0.0.1:8769 beeper-devbox`. API i worker działają w dwóch lokalnych kontenerach. Brak konta lub płatnej usługi po stronie platform jest obsługiwany przez imienne statusy źródeł. Przygotowany odczyt offline pochodzi z datowanej migawki.

Pierwsze uruchomienie z czystego checkoutu na Linux x86_64 wymaga Docker Compose, Pythona 3.12 z venv/pip, systemowego FFmpeg i internetu do przygotowania publicznych modeli i pakietów. Po przygotowaniu ta sama komenda korzysta z lokalnych zależności. Maszyna demonstracyjna ma budżet 4 vCPU i 8 GiB RAM. Częstotliwość nowych poszukiwań reguluje INVESTWATCH_DISCOVERY_INTERVAL w sekundach, domyślnie 14400. Wartość 0 wyłącza automatyczne skany live na czas próby offline. Przycisk odtworzenia korzysta ze stałego zestawu. [Środowisko](ops/demo/README.md)

## Dwie minuty przy pulpicie

1. W kolejce otwórz przykład z pojedynczą wzmianką. W syntetycznym polskim klipie jedyny komunikat o marce i zachęcie do otwarcia rachunku zajmuje 0,33–3,60 s. Kliknij czas i posłuchaj. Ta sama reguła przypisuje 12 punktów samemu opisowi i 74 po dodaniu mowy. Osobny klip z jawną deklaracją współpracy daje 94. Liczby oznaczają priorytet przeglądu. Charakter relacji pozostaje do ustalenia.
2. W **Źródłach** sprawdź, skąd odkryto twórcę. Apple Podcasts i PeerTube wyszukujemy po tematach. Link do filmu znaleziony w opisie może wskazać kolejnego twórcę YouTube. Tożsamość ustalona wyłącznie przez publiczne oEmbed ma status kandydata do potwierdzenia. Worker wraca do zapamiętanych kanałów RSS i próbkuje początek wybranej nowej audycji (maks. 45 s). Dla własnych plików działają ASR i przewijanie do cytatu. Limit uploadu to 40 MiB i 120 s. W polu semantycznym można porównać fragment z polskimi wzorcami przy użyciu lokalnego E5.
3. W sprawie demonstracyjnej przygotuj pytanie o współpracę i zapisz odpowiedź firmy. Porównaj datę publikacji z fikcyjną umową, potem z aneksem. W M2 otwórz zrzut obok wyniku jednej z 19 kontroli. W M3 sprawdź fragment oferty i tożsamość podmiotu. Zmiana progu w panelu kalibracji pokazuje koszt różnych decyzji na tym samym zbiorze.

Zgłoszenie sprawy, odpowiedzi firmy i dokumenty demonstracyjne są lokalne i odpowiednio oznaczone. Próbka kalibracyjna zawiera 4 przykłady publiczne i 9 syntetycznych z roboczymi etykietami. Pokrycie całego rynku oraz skuteczność na nowych kampaniach wymagają niezależnej walidacji. [Analiza i pochodzenie nagrań](analysis/README.md) · [Prezentacja PDF](presentation/InvestWatch.pdf)

## Gdzie są dane

- W SQLite i kolejce Huey w .runtime/demo/state są sprawy, rewizje, decyzje, wydarzenia, lokalne nagrania i wyniki. Żądanie skanu ma trwały klucz, a zmiana stanu wymaga właściwej rewizji. Pulpit po rozłączeniu WebSocket ponownie czyta stan.
- Osobny proces systemd nadal obserwuje cztery ustalone profile TikToka/YouTube i zapisuje raporty w .runtime/watch. Długofalowe odkrywanie twórców wykonuje worker Compose. [Monitoring](docs/MONITORING.md)
- Dla następnej sesji uruchom `sh tools/hack_context.sh`. Testy i faktyczny zakres wdrożenia opisuje [odbiór demo](docs/DEMO-ODBIOR.md).
