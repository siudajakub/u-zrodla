# InvestWatch

Prototyp dla UKNF wyszukuje publikacje i oferty inwestycyjne, wskazuje fragmenty wymagające sprawdzenia i przechowuje dowód z decyzją analityka. M1 dotyczy reklam osób trzecich, M2 reklamy własnej firmy, M3 potencjalnego nieuprawnionego doradztwa.

## Quick Start

Na przygotowanym stanowisku Linux x86_64 uruchom z katalogu projektu:

```sh
sh ops/demo/start.sh
```

[Pulpit](http://127.0.0.1:8769/) i [podgląd Astryx](http://127.0.0.1:8769/theme-preview/) korzystają z lokalnego API. Przy połączeniu zdalnym przekaż port poleceniem `ssh -N -L 8769:127.0.0.1:8769 beeper-devbox`. Do próby bez dostępu do publicznych źródeł wybierz odtworzenie datowanej próbki.

## Wymagania i konfiguracja

Stanowisko demonstracyjne przewiduje 4 vCPU i 8 GiB RAM, Docker Compose, Python 3.12, FFmpeg i lokalne wagi E5 oraz Vosk PL. Przy pierwszym przygotowaniu potrzebny jest internet do pobrania publicznych pakietów i modeli. Podgląd Astryx buduje Node.js z przypiętych zależności npm. API oraz worker Huey działają w dwóch kontenerach. SQLite zapisuje dane w .runtime/demo/state. Worker wyszukuje źródła co cztery godziny, interwał określa INVESTWATCH_DISCOVERY_INTERVAL w sekundach. Wartość 0 wyłącza harmonogram live. [Przygotowanie środowiska](ops/demo/README.md)

[Zakres UKNF i pięć plików źródłowych](docs/zrodla-uknf/README.md) · [Co działa i z jakimi ograniczeniami](docs/ODBIOR-UKNF.md) · [Scenariusz pokazu](docs/hackathon/demo.md) · [Prezentacja PDF](presentation/InvestWatch.pdf)

Test porównawczy oceny pojedynczej reklamy przez OpenRouter i lokalnie na Apple Silicon opisuje [instrukcja OpenRouter / Mac M3](docs/fable/OPENROUTER-M3.md).
