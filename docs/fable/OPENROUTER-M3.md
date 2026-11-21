# Aktualizacja dla Fable · ocena reklam i demo na Macu M3

Kontynuuj START_PROMPT.md i istniejące zadania. Zmień zakres D, G, H, L i M przed rozpoczęciem nowej fali. W produkcie M1 deklaracja „Partnerem odcinka jest XTB” obecnie daje score 94 i może sama skierować film do przeglądu. M2 kwalifikuje na podstawie reguł i geometrii strony, M3 używa lokalnego E5 i dodatkowych warunków. Rozróżnij ryzyko problemu, wykrytą relację i pewność skierowania na wszystkich wejściach, także w zdarzeniach high_risk oraz przy ponownym odczycie starych spraw.

- D / Opus high przeprowadza porównanie dotychczasowych reguł i reguł + Qwen3.5-9B. Użyj jawnego polecenia deweloperskiego z wybraną publiczną próbką. Wymagaj wskazania konkretnego problemu, prawdziwego cytatu i sprawdzalnej wersji źródła. Zasada wykrycia sponsora daje osobny wpis w rejestrze. Dla niedostępnego kontekstu przewiduj wstrzymanie wyniku.
- G / Opus high zamraża pełne kampanie i etykiety przed strojeniem. Użyj próby Q z ODBIOR.md. Policz TP, FP, FN, TN, precyzję, pełność i koszt 2×FN+FP, zwłaszcza dla prawidłowo oznaczonych reklam. Oceny modelu nie zastępują etykiet. Porównaj wrażliwość wyniku na kwantyzację i środowisko. Zapisz identyfikator modelu, dostawcę, lokalny digest, parametry, wersję promptu, czas, tokeny i koszt, gdy dostawca udostępnia pomiar.
- H / Sonnet high pozostawia OpenRouter jako jawny eksperyment na wybranych publicznych materiałach. Aktualizuje rzeczywistą kolejkę i zdarzenia aplikacji na podstawie zwalidowanego wariantu lokalnego po odbiorze jakości. Zachowuje odtwarzalny fallback oraz decyzje analityka.
- L / Sonnet high przygotowuje stanowisko na MacBooku M3. Sprawdź rzeczywistą pamięć zunifikowaną i wolne miejsce, dostęp do hosta, Ollama i identyfikator pobranych wag. Na Macu wywołaj qwen3.5:9b z małym kontekstem, zmierz czas i szczyt pamięci. Jeśli wybrany wariant nie mieści się w pamięci, przetestuj mniejszą kwantyzację albo mniejszy model, z osobnym pomiarem trafności. Lokalna analiza demo ma działać także bez Internetu. Dotychczasowy Quick Start jest dla Linux x86_64. Sprawdź ARM64, architekturę natywnej biblioteki Vosk oraz komunikację kontenera z Ollama na hoście, zanim ogłosisz gotowość stanowiska.
- M / Sonnet high najpierw wykonuje testy offline z atrapą API, następnie porównanie na identycznym wejściu na OpenRouter i na Macu. Spróbuj danych niepełnych, odpowiedzi bez dowodu, 401, limitu, timeoutu, niedostępnego modelu i rozbieżności między modelami. Na końcu odbierz rzeczywistą drogę od skanu do decyzji w pulpicie.
- Fable prowadzi rejestr kosztów. Wydatki wymagają uprzedniej zgody J na konkretny budżet. Samo ustawienie klucza nie stanowi zgody. Korzystaj z nieobciążających testów na devboxie. Nie uruchamiaj tam dużego modelu Qwen. Zapisz blokady dostępu do Maca lub brak klucza i kontynuuj niezależne zadania.

## Pierwsza próba

Klucz tylko w zmiennej OPENROUTER_API_KEY lub w lokalnym pliku .env.openrouter (tryb 600), w jednej linii OPENROUTER_API_KEY=wartość bez cudzysłowów. Skrypt ops/review/openrouter.sh odczytuje ten plik. Na innym komputerze utwórz plik lokalnie. Do pierwszego testu wybierz datowany publiczny opis, który ujawnia sponsora. Cytat w tej próbce nie pozwala rozstrzygnąć zgodności całego filmu.

```sh
sh ops/review/openrouter.sh fixtures/raw/discovery/2026-11-21.json --capture-id youtube:xtMqKkFO-0M --public-source
```

Przed wysłaniem materiału adapter pobiera publiczny cennik modelu (`GET /api/v1/models/<id>/endpoints`, bez klucza). Bez opcji płatnej odmawia lokalnie, jeśli żaden zgodny endpoint nie ma zerowej ceny. Dla `qwen/qwen3.5-9b` tak jest, więc wywołanie bez `--allow-paid` kończy się błędem `paid_model_requires_opt_in`, a materiał nie opuszcza hosta. Opcji `--allow-paid` używaj dopiero po zgodzie J na konkretny budżet. Opcja `--max-price-per-mtok` (domyślnie 1.0) ustala najwyższą cenę w USD za 1 mln tokenów wejścia i wyjścia. Adapter przekazuje ją dostawcy jako `provider.max_price` i odmawia lokalnie, gdy żaden endpoint się w niej nie mieści. Każdy wynik zawiera `usage.cost`, dostawcę, tokeny, czas i surową odpowiedź. Koszt licz z `usage.cost`, bo licznik klucza może obejmować inne sesje.

```sh
sh ops/review/openrouter.sh fixtures/raw/review-compare/case-b-comparic-xtb-referral.json --public-source --allow-paid --max-price-per-mtok 1
sh ops/review/openrouter.sh <plik> --public-source --allow-paid --model qwen/qwen3.5-27b --max-price-per-mtok 2
```

Opcja `--provider <nazwa>` zawęża routing do jednego dostawcy (`provider.only`). Dla `qwen/qwen3.5-27b` endpoint Alibaba zwracał tablice zamiast obiektu wymaganego schematem, a Chutes trzymał się schematu (2026-11-21). Oba adaptery wysyłają te same parametry: `temperature 0`, `max_tokens 1024`, `seed 0` i wyłączone rozumowanie. Ollama czyta model z `INVESTWATCH_REVIEW_MODEL`, a adres z `OLLAMA_HOST`. Na Macu Ollama udostępnia qwen3.5:9b. Sprawdź dostępne warianty i ilość pamięci przed pobraniem. [OpenRouter](https://openrouter.ai/qwen/qwen3.5-9b) · [Wagi Apache 2.0](https://huggingface.co/Qwen/Qwen3.5-9B) · [Ollama](https://ollama.com/library/qwen3.5:9b)

Na Macu z działającą Ollama pobierz model jednokrotnie i uruchom z katalogu projektu:

```sh
ollama pull qwen3.5:9b
python3 -m analysis.ollama_review fixtures/raw/discovery/2026-11-21.json --capture-id youtube:xtMqKkFO-0M
```

Oba adaptery porównawcze działają poza harmonogramem i produkcyjnym workerem. Testy adapterów uruchamia się bez modelu i klucza poleceniem `python3 -m unittest analysis.test_openrouter_review analysis.test_ollama_review`.
