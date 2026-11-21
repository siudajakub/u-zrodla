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

Dla Qwen3.5 i Gemma 4 nie znalazłem polskiego benchmarku. Bielik 4.5B ma oficjalnie tylko Q8_0 (5,1 GB). Wybór Qwen 4B ma uzasadnienie praktyczne: licencja, rozmiar i ten sam rodzaj modelu co w porównaniu D. Nie wynika z pomiaru jakości po polsku. Ten pomiar wykona `measure-llm.sh` na Macu. Ollama: najnowsze wydanie v0.40.17, `/api/chat` przyjmuje `format` jako schemat JSON, `think: false`, `options.temperature/seed/num_ctx`, `keep_alive`.

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

**LLM: niezmierzony.** Na devboxie było 3,0–3,7 GB dostępnej pamięci, a warunek startu to co najmniej 6 GB. Ollamy nie instalowałem. `ops/mac/measure-llm.sh` przeszedł od początku do końca tylko przeciw atrapie serwera Ollama, więc to dowód działania potoku, nie trafności. Odsetek odrzuceń walidatora i czas LLM czekają na Maca.

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
                    "promptVersion": "mt-llm-1", "latencyMs": 900.0, "affectsDecision": false},
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
