# Silnik inferencji i lokalny model: miejsce w produkcie

Linia `hack/fable/ai`, 2026-11-21. Wykonawca: agent `claude-opus-5-5`. Brief §3.2 wymaga preprocessingu, tokenów i embeddingów, silnika inferencji (vllm, llama.cpp lub Ollama) oraz modelu open source albo klasyfikatora z funkcją scoringową. Brief §5 dopuszcza wyłącznie darmowe modele uruchamiane lokalnie.

## Decyzja

1. **Reguły nadal decydują o skierowaniu.** Porównanie z Qwen3.5 jako decydentem M1 ([porównanie D](2026-11-21-fable-d-porownanie.md)) nie dało zysku. Tamtego eksperymentu nie powtarzamy.
2. **Zastosowanie A: typ materiału** (promocja, edukacja, informacja, opinia). Klasyfikator to regresja logistyczna (softmax) na wektorach E5 `multilingual-e5-small` (ONNX, CPU). Brief nazywa to wprost: klasyfikator z warstwą wyjściową, która przypisuje kategorię. Wynik to cecha opisowa w karcie i filtr dla analityka, z pewnością w skali 0–1. Pole `affectsDecision: false`. Pomyłka zmienia tylko etykietę opisu, więc nie powstaje fałszywa flaga. Reguły słownikowe sobie z tym zadaniem nie radzą (wynik niżej). Model rozpoznaje tu styl tekstu, czego regex nie uchwyci.
3. **Zastosowanie B: drugi głos LLM przez Ollama** w tym samym zadaniu, z dosłownym cytatem uzasadnienia. Walidator odrzuca cytat spoza wskazanej linii wejścia, tak jak w adapterach porównawczych. Oba silniki oceniamy na tym samym odłożonym zbiorze. LLM wchodzi do karty tylko wtedy, gdy na Macu osiągnie co najmniej trafność E5 (30/57), a walidator odrzuci najwyżej 10% odpowiedzi. Domyślnie jest wyłączony (`INVESTWATCH_LLM`). Bez usługi status brzmi `disabled` albo `unavailable`, a wynik powstaje bez modelu.
4. **Odrzucone na dziś.** (b) M3 „rekomendacja personalna kontra informacja”: w repo są 2–3 domeny M3, więc nie ma z czego zbudować zbioru oceny. (c) M2 K-09 „zrozumiałość ostrzeżenia”: rzeczywiste ostrzeżenia to kilka szablonów CFD, a etykieta jest subiektywna, więc trafności nie da się zmierzyć. (d) streszczenie uzasadnienia: wymaga oceny jakości tekstu, a nie trafności. Wrócimy do tego, gdy zastosowanie B przejdzie próg.

## Wybór modelu lokalnego

Odczyt 2026-11-21 ze stron bibliotek ollama.com, kart Hugging Face i GitHub. Rozmiary podaje Ollama.

| Model | Tag Ollama | Pobranie | Licencja | Rola |
|---|---|---|---|---|
| Qwen3.5 4B | `qwen3.5:4b-q4_K_M` | 3,3 GB | Apache-2.0 ([karta](https://huggingface.co/Qwen/Qwen3.5-4B)) | **domyślny**, mieści się w 8 GB |
| Qwen3.5 2B | `qwen3.5:2b-q4_K_M` | 1,9 GB | Apache-2.0 (karta 4B, rodzina) | awaryjny przy 8 GB i obciążonym systemie |
| Qwen3.5 9B | `qwen3.5:9b-q4_K_M` | 6,6 GB | Apache-2.0 (przyjęte z karty 4B) | wariant dla 16 GB |
| Bielik 11B v3.1 | `SpeakLeash/bielik-11b-v3.1-instruct:Q4_K_M` (przestrzeń społeczności) | 6,7 GB | Apache-2.0 ([karta](https://huggingface.co/speakleash/Bielik-11B-v3.1-Instruct)) | polski model, alternatywa przy 16 GB, poza oficjalną biblioteką |
| Gemma 4 E2B | `gemma4:e2b-it-qat` | 4,3 GB | Apache 2.0 ([karta E4B](https://huggingface.co/google/gemma-4-E4B-it)) | dopuszczalna, ale większa od Qwen 4B |

Tabela wyżej to stan przed pomiarem; wynik i rekomendacja w sekcji „Pomiar LLM przez OpenRouter”. Dla Qwen3.5 i Gemma 4 nie znalazłem polskiego benchmarku. Bielik 4.5B ma oficjalnie tylko Q8_0 (5,1 GB). Wybór Qwen 4B ma uzasadnienie praktyczne: licencja, rozmiar i ten sam rodzaj modelu co w porównaniu D. Nie wynika z pomiaru jakości po polsku. Ten pomiar wykona `measure-llm.sh` na Macu. Ollama: najnowsze wydanie v0.40.17, `/api/chat` przyjmuje `format` jako schemat JSON, `think: false`, `options.temperature/seed/num_ctx`, `keep_alive`.

## Pomiar

Zbiór oceny: `fixtures/labeled/ai-material-type.json`. Zawiera 160 polskich materiałów YouTube z replay `youtube-api-2026-11-21`, z tytułem i opisem po preprocessingu. Losowanie z seedem, deduplikacja po tekście, najwyżej 3 materiały na twórcę. Podział po twórcy: strojenie 103 materiały i 64 kanały, odłożony 57 materiałów, bez wspólnych kanałów. Etykiety nadał jeden agent i zapisał je w commicie `4125285`, przed pierwszym uruchomieniem klasyfikatora. Reguły słownikowe w tym samym commicie powstały przed oceną. Hiperparametr L2 wybrano 5-krotną walidacją krzyżową po twórcach, wyłącznie na zbiorze strojenia (CV 0,563). Zbiór odłożony oceniono raz.

**Zbiór odłożony, n = 57** (`fixtures/labeled/ai-material-type-result-e5.json`):

| Metoda | Trafne | Trafność | Macro-F1 |
|---|---|---|---|
| E5 + regresja logistyczna | 30/57 | 0,526 | 0,47 |
| E5 z abstencją (pewność < 0,5) | 29/51 odpowiedzi, 6 abstencji | 0,569 wśród odpowiedzi | 0,49 |
| Zawsze „opinia” (najliczniejsza klasa w odłożonym) | 23/57 | 0,404 | – |
| Najliczniejsza klasa strojenia („edukacja”) | 14/57 | 0,246 | 0,10 |
| Reguły słownikowe | 13/57 | 0,228 | 0,21 |

Macierz pomyłek E5 (wiersz to etykieta, kolumna to predykcja; kolejność promocja, edukacja, informacja, opinia):

| | prom. | eduk. | inf. | opinia |
|---|---|---|---|---|
| promocja (3) | 1 | 0 | 2 | 0 |
| edukacja (14) | 2 | 9 | 1 | 2 |
| informacja (17) | 2 | 2 | 12 | 1 |
| opinia (23) | 3 | 3 | 9 | 8 |

Precyzja i czułość: edukacja 0,64 i 0,64, informacja 0,50 i 0,71, opinia 0,73 i 0,35, promocja 0,12 i 0,33. Czas: 3,0 s na materiał na tym devboxie (CPU współdzielony z innymi agentami, onnxruntime na 1 wątku, 256 tokenów). Przy trenowaniu na tym samym hoście wyszło około 0,3 s na materiał, więc wynik 3,0 s odzwierciedla obciążenie hosta. Na Macu pomiaru nie było.

**LLM: zmierzony przez API, nie lokalnie.** Decyzja J: na devboxie nie instalujemy modeli ani Ollamy, wybór modelu mierzymy przez OpenRouter, a produkt działa lokalnie. Szczegóły w sekcji „Pomiar LLM przez OpenRouter” niżej. Trafność i odrzucenia walidatora pochodzą z wag w BF16 u dostawcy API, więc kwantyzacja Q4 i czas na Macu nadal wymagają `ops/mac/measure-llm.sh`.

## Pomiar LLM przez OpenRouter

Narzędzie: `tools/measure_llm_openrouter.py` (transport z `analysis/openrouter_review.py`, backend `INVESTWATCH_LLM_BACKEND=openrouter` w `analysis/inference.py`). Te same 57 materiałów odłożonych, te same wejścia co E5, ten sam prompt, schemat JSON (strict), temperatura 0, seed 0, walidator cytatów. Backend openrouter działa tylko przez transport rejestrowany przez narzędzie pomiarowe. `inference.py` nie czyta klucza, więc worker produktu go nie dostaje. Limity: lokalna kontrola cennika przed pierwszym żądaniem, `--max-price-per-mtok 3`, 0,30 USD na model i 1,50 USD łącznie wg `usage.cost`, jedno żądanie naraz, `data_collection: deny`, endpoint wybierany wśród tych ze `structured_outputs` (najtańszy). Łączny koszt całego pomiaru (dwie serie po 6 modeli i próba na 3 materiałach): około 0,10 USD.

**Prompt.** Seria 1 (`mt-llm-1`) pokazała, że Gemma 3 4B wpisywała w `lineId` treść linii zamiast klucza `L0` (38 z 57 odpowiedzi odrzuconych jako `line_missing`). Dodałem do promptu jedno zdanie (`lineId` to klucz linii, nigdy jej treść) i powtórzyłem całą serię jako `mt-llm-2`. Zmiana dotyczy formatu, nie etykiet, ale **zbiór odłożony oceniono przez to dwukrotnie**: przy wyborze modelu traktuj wynik jako optymistyczny. Wyniki serii 1 zostały w `ai-material-type-result-<model>-mt-llm-1.json`.

**Wyniki `mt-llm-2`, zbiór odłożony n = 57** (`fixtures/labeled/ai-material-type-result-<model>.json`; E5 to 30/57, macro-F1 0,47):

| Model (OpenRouter) | Dostawca, kwant. | Trafne /57 | Macro-F1 | Odrzucone walidatorem | Zgodność z E5 | Koszt | Q4 (Ollama) | Licencja | Tag Ollama |
|---|---|---|---|---|---|---|---|---|---|
| gemma-3-12b-it | DeepInfra, bf16 | **36** | 0,60 | 0/57 (0%) | 0,46 | 0,0029 | 8,2 GB | Gemma Terms of Use (nie permisywna) | `gemma3:12b-it-q4_K_M` |
| ministral-8b-2512 | Mistral, brak danych | 35 | **0,64** | 5/57 (8,8%) | 0,52 | 0,0065 | 6,0 GB | Apache-2.0 (karta HF) | `ministral-3:8b-instruct-2512-q4_K_M` |
| qwen3.5-9b | DeepInfra, bf16 | 32 | 0,58 | 3/57 (5,3%) | 0,51 | 0,0056 | 6,6 GB | Apache-2.0 | `qwen3.5:9b-q4_K_M` |
| ministral-3b-2512 | Mistral, brak danych | 31 | 0,53 | 5/57 (8,8%) | 0,53 | 0,0043 | 3,0 GB | Apache-2.0 | `ministral-3:3b-instruct-2512-q4_K_M` |
| granite-4.2-8b | CoreWeave, bf16 | 24 | 0,42 | 6/57 (10,5%) | 0,37 | 0,0029 | brak potwierdzonego tagu 4.2 (w bibliotece jest `granite4:*`) | Apache-2.0 (karta HF) | – |
| gemma-3-4b-it | Parasail, bf16 | 25 | 0,56 | 22/57 (38,6%) + 1 błąd dostawcy | 0,56 | 0,0021 | 3,4 GB | Gemma Terms of Use | `gemma3:4b-it-q4_K_M` |

Zgodność z E5 liczona wśród odpowiedzi modelu z przyjętym cytatem. Kolumna „Q4” to rozmiar pobrania z biblioteki Ollama; RAM podczas pracy to rozmiar plus KV-cache dla `num_ctx` 4096, czyli orientacyjnie +1 GB (nie mierzono). Mediany czasu z API (0,6–3,4 s) to opóźnienie sieci i dostawcy, nie czas na Macu.

Czego nie ma w katalogu OpenRouter: Qwen3.5 2B i 4B, Bielik (w żadnym rozmiarze), Gemma 4 E2B/E4B (jest tylko 26B-A4B i 31B, za duże na 16 GB), Phi-4-mini. Dlatego dotychczasowy domyślny `qwen3.5:4b-q4_K_M` i awaryjny 2B **nie mają żadnego pomiaru**. Gemma 3 4B/12B to nie obecna generacja Gemmy, tylko najmniejsze warianty dostępne przez API. Llama odrzucona z powodu licencji.

### Wnioski z pomiaru

- **Próg przyjęcia (≥30/57 i ≤10% odrzuceń) spełniają cztery modele**: Gemma 3 12B, Ministral 8B, Qwen3.5 9B i Ministral 3B. Granite (10,5%) i Gemma 3 4B nie.
- **Czy bijają E5? Nie da się tego powiedzieć.** Najlepszy wynik to 36/57 wobec 30/57, czyli +6 trafień. Przy n = 57 przedział ufności wynosi ±0,13 (±7 trafień), a etykiety pochodzą od jednego agenta. Różnica jest w granicach szumu, a Ministral 3B i Qwen 9B mają +1 i +2. Macro-F1 jest wyraźniej wyższe (0,53–0,64 wobec 0,47), głównie dzięki klasie „promocja” (3 przykłady), więc to też niepewne.
- Przy zadaniu z wyraźną dwuznacznością etykiet (opinia kontra informacja) żaden model nie schodzi z 36–40% błędów. Zgodność z E5 to tylko 0,46–0,56, więc **drugi głos LLM ma realną wartość jako niezależny sygnał**, nawet bez dowodu na wyższą trafność.
- Odrzucenia walidatora u modeli ≥8B wynikają głównie z cytatów spoza linii lub o złej długości, nie ze złamania schematu. Strict `json_schema` respektowali wszyscy wybrani dostawcy (DeepInfra, Parasail, CoreWeave, Mistral). Endpoint Alibaba pominięto (łamał schemat 20/20 w wcześniejszym pomiarze); wybór jest wymuszony przez filtr `structured_outputs` i `provider.only`.

### Rekomendacja

- **16 GB: Ministral 3 8B** (`ministral-3:8b-instruct-2512-q4_K_M`, 6,0 GB, Apache-2.0): 35/57, najwyższe macro-F1 (0,64) spośród modeli na permisywnej licencji. Odrzucenia 8,8% są blisko progu 10%. Zapas daje Qwen3.5 9B (32/57, 5,3%, 6,6 GB, Apache-2.0). Gemma 3 12B jest najlepsza (36/57, 0% odrzuceń), ale licencja Gemma Terms of Use nie jest permisywna, a brief wymaga modeli otwartych; wykluczona z produktu, zostaje punktem odniesienia.
- **8 GB awaryjnie: Ministral 3 3B** (`ministral-3:3b-instruct-2512-q4_K_M`, 3,0 GB, Apache-2.0): 31/57, odrzucenia 8,8%, najszybszy w API. Margines nad progiem to 1 trafienie, więc to „działa na styk”.
- **Status w produkcie bez zmian: LLM wyłączony domyślnie** (`INVESTWATCH_LLM`), a E5 pozostaje klasyfikatorem. Dowód jest tylko po stronie API w BF16, bez zbioru potwierdzającego (zbiór odłożony zużyty dwa razy) i bez pomiaru na Macu. Włączenie drugiego głosu wymaga `sh ops/mac/measure-llm.sh --pull --model ministral-3:8b-instruct-2512-q4_K_M` i spełnienia progu na kwantyzacji Q4. Ollama musi też obsłużyć `format` ze schematem dla architektury Ministral 3 (niesprawdzone; przy braku wsparcia pozostaje Qwen3.5 9B). `DEFAULT_MODEL` w kodzie nie zmieniono, bo żaden z zalecanych modeli nie ma jeszcze pomiaru lokalnego. Ograniczenie wyboru: pomiar obejmuje 6 modeli z tych, które OpenRouter ma w katalogu.

Powtórzenie: `.runtime/venv/bin/python -B tools/measure_llm_openrouter.py --model mistralai/ministral-8b-2512 --public-source` (klucz z `.env.openrouter`, koszt około 0,01 USD).

### Co to znaczy

- Klasyfikator przewyższa reguły słownikowe o 17 trafień na 57 i stałą najczęstszą klasę o 7. To realny, ale umiarkowany zysk. Główny błąd: opinia czytana jako informacja (9 z 23). Komentarz rynkowy i wiadomość mają podobne słownictwo, a różni je teza autora.
- Klasa „promocja” ma 3 przykłady w zbiorze odłożonym. Jej precyzji (1 z 8) nie wolno pokazywać jako miary. Tylko jeden oznaczający, bez drugiej oceny. Granica między edukacją a opinią jest umowna. Zgodności między oceniającymi nie znamy.
- Dlatego typ materiału trafia do karty jako **wskazówka z pewnością**, bez wpływu na kolejkę. Przy pewności poniżej 0,5 karta pokazuje „nieustalone”.

## Wpięcie (do wykonania przez właściciela `analysis/engine.py`)

Łatka: [2026-11-21-fable-ai-inferencja-patch.diff](2026-11-21-fable-ai-inferencja-patch.diff). Przy `INVESTWATCH_MODEL_ANNOTATE=1` funkcja `analyze()` wywołuje `analysis.inference.annotate(finding, capture)` i wpisuje wersję do `analysisVersion.model`. Domyślnie łatka niczego nie zmienia. Sprawdzono to na kopii repo z nałożoną łatką. Bez flagi i z flagą: 113 testów, 9–10 pominiętych, 1 porażka już istniejąca (`test_qualification` szuka `.runtime/media-cache` w katalogu worktree). Kontrakt pola:

```json
"model": {
  "task": "material_type", "engine": "e5-logreg", "status": "ready|empty|unavailable",
  "label": "promocja|edukacja|informacja|opinia|nieustalone", "leadingLabel": "opinia",
  "confidence": 0.74, "probabilities": {"promocja": 0.05, "edukacja": 0.1, "informacja": 0.11, "opinia": 0.74},
  "quote": null, "modelId": "Xenova/multilingual-e5-small", "version": "mt-e5lr-1-…", "digest": "<sha256 pliku wag>",
  "promptVersion": null, "inputSha256": "…", "latencyMs": 310.2, "affectsDecision": false,
  "secondOpinion": {"task": "material_type", "engine": "ollama", "status": "disabled|ready|abstained|rejected|busy|unavailable|empty",
                    "label": "opinia", "quote": "dosłowny cytat", "evidence": {"field": "description", "lineId": "L2", "text": "…", "charStart": 0, "charEnd": 31},
                    "modelId": "qwen3.5:4b-q4_K_M", "digest": "sha256:…", "quantization": "Q4_K_M",
                    "promptVersion": "mt-llm-2", "latencyMs": 900.0, "affectsDecision": false},
  "agreement": true, "meaning": "Typ materiału opisuje treść dla analityka; nie zmienia skierowania ani punktów."
}
```

Karta pokazuje typ, pewność i wersję. Drugi głos z cytatem pojawia się tylko przy statusie `ready`. Statusy `rejected`, `busy` i `unavailable` oznaczają brak drugiego głosu, nigdy „brak sygnału”. Koszt CPU: E5 liczy się raz na materiał (256 tokenów). Przy replay 1300 materiałów warto adnotować tylko materiały w kolejce i w rejestrze.

## Serwis `inference` w Compose (opis dla agenta operacji; `compose.yaml` bez zmian)

```yaml
  inference:
    image: ollama/ollama:0.40.17          # tag niesprawdzony w Docker Hub; przypiąć digest po pierwszym pobraniu
    volumes: ['./.runtime/ollama:/root/.ollama']   # wagi; jednorazowo: docker compose run --rm inference ollama pull qwen3.5:4b-q4_K_M
    environment: {OLLAMA_CONTEXT_LENGTH: '4096', OLLAMA_NUM_PARALLEL: '1', OLLAMA_MAX_LOADED_MODELS: '1', OLLAMA_KEEP_ALIVE: '10m'}
    expose: ['11434']                     # tylko sieć Compose, bez portu na hoście
    mem_limit: 6g
    restart: unless-stopped
  # w x-common.environment dla api i worker:
  #   OLLAMA_HOST: inference:11434
  #   INVESTWATCH_LLM: '${INVESTWATCH_LLM:-0}'
  #   INVESTWATCH_LLM_MODEL: '${INVESTWATCH_LLM_MODEL:-qwen3.5:4b-q4_K_M}'
  #   INVESTWATCH_MODEL_ANNOTATE: '${INVESTWATCH_MODEL_ANNOTATE:-0}'
```

- Po jednorazowym `pull` usługa działa offline, bo wagi leżą w wolumenie. Obraz `ollama/ollama` ma około 1–2 GB (wersji obrazu nie sprawdzałem).
- Mac: Docker Desktop nie daje kontenerom dostępu do Metal, więc Ollama w kontenerze liczy na CPU maszyny wirtualnej. Na Macu serwis `inference` pomijamy, Ollamę uruchamiamy natywnie (`OLLAMA_CONTEXT_LENGTH=4096 ollama serve`), a api i worker dostają `OLLAMA_HOST=host.docker.internal:11434`. Alternatywą jest profil Compose `inference` włączany tylko na Linuksie.
- Klient trzyma jedno żądanie naraz (`QUEUE_SECONDS` 5 s, potem `busy`) i twardy limit `INVESTWATCH_LLM_TIMEOUT` (domyślnie 60 s). Wynik trafia do pamięci podręcznej po skrócie wejścia, wersji promptu i digestu wag.

## Polecenia dla właściciela na Macu

```sh
brew install ollama python@3.12            # albo aplikacja z ollama.com
OLLAMA_CONTEXT_LENGTH=4096 ollama serve &  # przy aplikacji: launchctl setenv OLLAMA_CONTEXT_LENGTH 4096
sh ops/mac/measure-llm.sh --pull                        # qwen3.5:4b-q4_K_M, 57 materiałów odłożonych
sh ops/mac/measure-llm.sh --pull --model qwen3.5:9b-q4_K_M   # tylko przy 16 GB, gdy swap nie rośnie
```

Do rekordu linii odeślij `.runtime/mac/llm-*.json`, a w nim: trafność, macierz pomyłek, `rejectedShare`, medianę czasu, digest, kwantyzację, swap przed i po. Próg przyjęcia: trafność co najmniej 30/57, a `rejectedShare` najwyżej 10%. Poniżej progu drugi głos zostaje wyłączony, a w demo pokazujemy E5 jako klasyfikator i Ollamę jako gotowy, zmierzony, ale odrzucony wariant.

## Ograniczenia

- Etykiety pochodzą od jednego agenta, bez eksperta i bez drugiej oceny. Zbiór odłożony ma 57 materiałów, w tym tylko 3 promocje. Przedział ufności trafności 0,526 przy n = 57 wynosi mniej więcej ±0,13.
- Oznaczający widział około 380 pierwszych znaków. Model widzi do 1200 znaków i 256 tokenów, czyli w praktyce około 900–1000 znaków.
- Nie zmierzono LLM, czasu na Macu ani trafności na materiałach M2 i M3 (strony WWW). Typ materiału oceniano tylko na YouTube.
- Wagi klasyfikatora (`analysis/material-type-weights.json`, 23 KB) są związane z rewizją E5 z `semantic-lock.json`. Zmiana E5 wymaga ponownego `python -m analysis.material_classifier train`.
