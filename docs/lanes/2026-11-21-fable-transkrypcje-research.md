# Research: skalowalne pozyskiwanie transkrypcji polskich filmów YouTube

- Data: 2026-11-21 (wszystkie ceny i limity odczytane tego dnia ze stron dostawców; mogą się zmienić)
- Model agenta: Sonnet 5.5 (claude-sonnet-5-5)
- Zakres: tylko research i lekkie próby; zero zmian w kodzie, zero kont u dostawców, zero płatności.

## 1. Wynik prób z hosta

Wykonano 5 wywołań narzędzi (odstęp ≥6 s), 4 różne filmy, bez cookies, proxy i logowania. Uwaga: jedno wywołanie yt-dlp/biblioteki to kilka żądań HTTP, więc faktyczna liczba żądań do YouTube była większa niż 15 (szacunkowo 20-25), choć liczba filmów i wywołań była mała.

| Próba | Film | Wynik |
|---|---|---|
| yt-dlp `--skip-download --write-subs --write-auto-subs --sub-langs "pl.*"` | ToDbSFwhAeM (24:52) | OK, bez 429. Pobrane `pl.vtt` i `pl-orig.vtt` (po 224 KiB). |
| youtube-transcript-api 1.2.5 (`fetch(..., languages=['pl'])`) | ToDbSFwhAeM | OK: 688 segmentów, `language_code=pl`, `is_generated=True`, start/duration w sekundach. |
| youtube-transcript-api | j4amiLUeeJE (19:44) | OK: 552 segmenty, auto. |
| yt-dlp tylko auto-napisy | 9phCZoGM2N0 (11:44) | OK, 3 pliki VTT (`pl`, `pl-pl`, `pl-orig`). |
| yt-dlp `-f worstaudio` | BUlIHYaiLh8 (1:18) | OK. Format 233-0, HLS, 13 fragmentów, `a_BUlIHYaiLh8.mp4`, 475 727 B (ok. 6 KB/s, czyli ok. 8-9 MB na 25 min). |

Wniosek: w momencie prób host NIE dostawał 429 ani blokady, ani na napisy (yt-dlp), ani na audio, ani przez youtube-transcript-api. Nie da się więc wykazać, czy youtube-transcript-api „obchodzi" 429 z yt-dlp. Najprostsze wyjaśnienie zgodne z danymi: 429 jest czasowy (limit szybkości lub reputacja adresu po serii ok. 40 żądań) i po przerwie ustąpił. To hipoteza, nie dowód: nie sprawdziłem, czy kolejna seria wywoła 429 ponownie. Katalog `.runtime/tmp-research/` został usunięty. Zainstalowano `youtube-transcript-api` 1.2.5 (MIT) w `.runtime/venv` (zależności: requests, defusedxml, urllib3, certifi, charset-normalizer).

Ważne dla projektu: pliki audio w najniższej jakości są małe (ok. 9 MB na 25 min), więc ścieżka ASR jest technicznie wykonalna, ale pobieranie audio to więcej żądań na film (kilka plików player + manifest + fragmenty HLS), więc szybciej wyzwoli limit niż napisy.

## 2. Przegląd opcji

### (a) Biblioteki open source

| Narzędzie | Endpoint | Limit / uwagi |
|---|---|---|
| yt-dlp (obecne) | strona watch, odpowiedzi odtwarzacza innertube, potem `timedtext` | Ten sam typ ruchu, co poniżej; 429 po serii z jednego IP. |
| youtube-transcript-api (MIT, jdepoix) | nieudokumentowane API klienta webowego YouTube (innertube) i `timedtext` | Ten sam backend YouTube, inna ścieżka żądań; README ostrzega, że YouTube blokuje większość adresów chmurowych (`RequestBlocked`/`IpBlocked`) i zaleca rotowane proxy rezydencyjne (wbudowane Webshare). Nie ma osobnego, wyższego limitu. Autor ostrzega, że API może przestać działać w każdej chwili. Daje segmenty ze znacznikami, flaga `is_generated`. |
| Inne klienty innertube (np. `innertube`, `pytubefix`) | ten sam innertube | Nie zbadane osobno; to samo ryzyko limitu na IP. |

Dla nas: zmiana biblioteki NIE zwiększa limitu na adres IP. Daje redundancję na wypadek, gdy jedna ścieżka żądań jest czasowo blokowana (w próbie obie działały).

### (b) Płatne API transkrypcji (odczyt 2026-11-21)

| Dostawca | Cena / 1000 | Darmowy pakiet | Polski i auto-napisy | Znaczniki / format | Limit szybkości | Start |
|---|---|---|---|---|---|---|
| Supadata (`GET api.supadata.ai/v1/transcript`) | 1 kredyt = 1 transkrypcja. Pro $17/mc za 3000 kr. = $5,67; Mega $47/mc za 30 000 = $1,57; Basic $5/mc za 300 (tylko rocznie, $60/rok) = $16,7. Dokup: ok. $10 / 1000 kr. (Basic/Pro), $10 / 5000 (Mega). Brak transkrypcji w trybie native też kosztuje 1 kredyt. | 100 kredytów/mc, bez karty (jedno źródło trzecie mówi: jednorazowo; strona dostawcy mówi: miesięcznie) | Parametr `lang` (ISO 639-1), `mode=native/auto/generate`. Brak oficjalnej deklaracji „pl" i „auto-napisy"; przy braku języka zwraca pierwszy dostępny + `availableLangs`. Tryb AI: 2 kr./min filmu. | JSON: `content[]` z `text`, `offset` (ms), `duration` (ms), `lang`; `text=true` daje czysty tekst. 202 + `jobId` dla zadań asynchronicznych. | Free 1/s, Basic i Pro 10/s, Mega 50/s | Konto na supadata.ai, klucz w panelu, nagłówek `x-api-key` |
| TranscriptAPI (transcriptapi.com) | $5/mc za 1000 kr. = $5; dokup $2,50/1000 (mies.) lub $1,50/1000 (roczny $54) | 100 kredytów, bez karty | Parametr `language` (np. `de,en,asr`; `asr` = auto-napisy), polski nie wymieniony wprost. Nieudane żądania nie są liczone. | JSON `transcript[]` z `text`, `start`, `duration` | 200/min (mies.), 300/min (roczny) | Rejestracja, klucz API. Uwaga: to dostawca z własnym blogiem porównawczym, więc jego zestawienia konkurencji są stronnicze. |
| ScrapingDog (YouTube Transcripts API) | koszt w kredytach na żądanie nie podany; plan Lite $40/mc za 200 000 kr. (do ustalenia w dokumentacji) | 100 kredytów, bez karty | Parametr `language`; polski niepotwierdzony | JSON `transcripts[]`: `text`, `start`, `duration` | zależnie od planu (Free: 1 współbieżne) | Rejestracja, `api_key` w zapytaniu |
| SearchAPI.io | brak potwierdzenia, że ma silnik transkrypcji; plany od $4/1000 zapytań (Developer $40 za 10 000) | 100 zapytań | brak danych | brak danych | brak danych | Nie weryfikowane; nie polecam bez potwierdzenia silnika transkrypcji. |
| SerpApi | strona cennika nie wspomina o transkrypcjach; plany od $10-25/1000 | 250 wyszukiwań/mc | brak danych | brak danych | brak danych | Drogi, pominąć. |
| Apify (aktory zewnętrzne) | od $0,60 do $50 / 1000 wyników, zależnie od aktora; typowo $1-5 | plan darmowy z kredytem miesięcznym | Dwa aktory deklarują auto-napisy; polski nie potwierdzony w żadnym | zależnie od aktora | zależnie od planu | Konto Apify, token API, wywołanie aktora przez API. Ryzyko: aktory od osób trzecich, bywają porzucane. |
| youtube-transcript.io | cennik nie odczytany | 25 transkrypcji bez konta | nie wiadomo | nie wiadomo | nie wiadomo | Nie weryfikowane. |
| Bright Data, Oxylabs, ScrapingBee, RapidAPI | nie badane; to ogólne usługi scrapingu lub proxy, rozliczane za żądanie/GB | zależnie | n/d | n/d | n/d | Pominięte: ten sam efekt, co własny scraping przez proxy, ale bez gotowego formatu transkrypcji. |

Wszystkie powyższe usługi pozyskują napisy z YouTube w imieniu klienta, więc jakość to te same auto-napisy YouTube (nie Whisper). Żadnej z nich nie testowałem.

### (c) Własne ASR z dźwięku (wymaga pobrania ścieżki audio)

Założenie liczbowe: średnia długość filmu w kolejce ok. 20 min, więc 550 filmów to ok. 183 h audio. Średnia nie była zmierzona; dla innej długości skaluj liniowo.

| Opcja | Cena | Darmowy limit | Polski | Uwagi |
|---|---|---|---|---|
| faster-whisper / whisper.cpp lokalnie | 0 USD (licencje MIT; wagi Whisper: MIT) | n/d | tak, Whisper jest wielojęzyczny; jakość po polsku dla small < medium < large-v3 / large-v3-turbo (nie mam zmierzonych WER; wyszukiwanie ich nie znalazło) | Rozmiary wag (z pamięci, niezweryfikowane): small ok. 0,5 GB, medium ok. 1,5 GB, large-v3-turbo ok. 1,6 GB (fp16). Prędkość: NIE MIERZONA. Wyszukiwanie nie dało wiarygodnych liczb dla 4 vCPU ani M3. Moje oszacowanie z doświadczenia: large-v3-turbo int8 na 4 vCPU rzędu 0,3-1x czasu rzeczywistego, czyli 183 h audio to ok. 3-10 dni, więc za wolno na ten host; na M3 ok. 10x czasu rzeczywistego (whisper.cpp/MLX), czyli ok. 18 h dla 183 h. Do sprawdzenia próbą przed decyzją. |
| Groq Whisper (`whisper-large-v3-turbo`) | $0,04/h (strona: odczyt 2026-11-21); large-v3 $0,111/h; min. 10 s na żądanie | brak podanego darmowego kredytu | tak (parametr `language=pl`) | Format: `verbose_json` ze znacznikami segmentów/słów oraz `avg_logprob`, `no_speech_prob`. Plik do 25 MB (free) lub 100 MB (dev). Limity bazowe: 20 RPM, 2000 RPD, 7200 s audio na godzinę i 28 800 s na dobę. To oznacza ok. 8 h audio na dobę, czyli 183 h zajęłoby ok. 23 dni, chyba że konto Developer ma wyższe limity (strona nie rozróżnia planów). Koszt 183 h = ok. $7,3. |
| Deepgram Nova-3 | $0,0043/min mono (PAYG), $0,0052/min multilingual, Whisper Large $0,0048/min; 183 h = ok. $47-57 | $200 kredytu, bez wygaśnięcia, bez karty | strona nie wymienia polskiego; "60+ języków", trzeba potwierdzić w dokumentacji | Słowa i znaczniki czasu. Z darmowego kredytu zaległość wychodzi za 0 USD. |
| AssemblyAI Universal-2 | $0,15/h; 183 h = ok. $27 | $50 kredytu, bez karty | strona nie wymienia polskiego | Do potwierdzenia na liście języków. |
| OpenAI | od $0,0045/min do $0,006/min (whisper-1); 183 h = ok. $49-66 | brak | tak | Najdroższe w zestawieniu. |

Wspólne zastrzeżenie: każda droga ASR wymaga pobrania audio z YouTube, a więc wyzwala ten sam limit szybkości i dodatkowo wprost objęta jest punktem regulaminu o pobieraniu treści (sekcja 4).

### (d) Inne legalne źródła tej samej treści

- Napisy dostarczone przez twórcę (transkrypcja ręczna): już obsługiwane w łańcuchu `author_captions`; najwyższa jakość, ale rzadkie.
- Bliźniaki podcastowe z RSS: wiele kanałów finansowych publikuje te same odcinki jako podcast. Audio z RSS jest pobierane z hostingu twórcy, nie z YouTube, więc nie ma limitu YouTube, a regulamin YouTube nie obowiązuje. Wymaga dopasowania odcinka (tytuł, data, długość). Nie badałem pokrycia na naszej liście kanałów; to najtańszy pomysł do sprawdzenia osobno.
- YouTube Researcher Program: (research.youtube.com/how-it-works) przyjmuje studentów, pracowników badawczych i wykładowców akredytowanej, nie dla zysku uczelni, w ok. 60 krajach; daje „skalowany dostęp do metadanych filmów" przez Data API. Strona nie wspomina o napisach/transkrypcjach, więc nie rozwiązuje problemu, a zespół hackathonowy zapewne nie spełnia kryterium. Odrębna ścieżka DSA art. 40(4) dotyczy niezależnych jednostek niekomercyjnych, też bez deklaracji transkrypcji.
- YouTube Data API `captions.download`: wymaga uprawnień właściciela filmu (zgodnie z opisem zadania); odpada.

## 3. Rekomendacja

### A. Zaległość ~550 filmów (dziś/jutro)

Podstawowa: **istniejący yt-dlp, ale z ograniczeniem tempa i wycofywaniem po 429, plus youtube-transcript-api jako druga ścieżka.** Koszt 0 USD. Przy przerwie 20-30 s między filmami 550 filmów to ok. 3-5 h. Opieram to na tym, że w próbach 429 nie wystąpił i hipotezie o czasowym limicie; hipoteza nie jest sprawdzona. Wdrożenie: 0,5-1 h (pętla z opóźnieniem losowym 20-40 s, przerwa 15-30 min po pierwszym 429, wznowienie z cache `.runtime/media-cache`, który już pomija pobrane).

Zapasowa: **Supadata, tryb `native`.** Konto bez karty daje 100 kredytów (100 filmów za 0 USD), więc można nim obsłużyć część; cała zaległość: Pro $17 za jeden miesiąc (3000 kredytów) = ok. $31 za 1000 filmów liczone na zaległość 550, krańcowo $5,67/1000. Alternatywnie TranscriptAPI: $5 za miesiąc (1000 kredytów) = $5 za zaległość (ok. $9 za 1000 przy 550). Oba wymagają sprawdzenia polskiego na 3-5 filmach z darmowego pakietu, zanim się zapłaci.

### B. Stała praca u nadzorcy (setki do kilku tysięcy dziennie)

Podstawowa: **Supadata Mega ($47/mc, 30 000 kredytów, ok. $1,57/1000, 50 żądań/s)** w trybie `native`, z yt-dlp jako pierwszym darmowym krokiem. Przy 1000 filmów/dzień (30 000/mc) koszt to ok. $47/mc. TranscriptAPI jest tańsze przy niższym wolumenie ($5-$10 za 1000-3000), ale ma najmniej niezależnych opinii; wybór między nimi rozstrzygnie test jakości polskiego.

Zapasowa dla filmów bez napisów: **Groq `whisper-large-v3-turbo` ($0,04/h, ok. $0,013 za film 20-min, czyli ok. $13/1000 filmów)** lub Deepgram z darmowym kredytem $200. Wymaga pobrania audio (patrz ryzyko). Uwaga na limit Groq 8 h audio na dobę.

### Wpięcie w `collectors/media.py`

Obecny łańcuch: `captions(vid, meta, cache, now=...)` (yt-dlp, ok. linia 347) oraz `asr_audio(...)` (ok. linia 383, Vosk, 120 s). Proponowana zmiana (do wykonania przez kogoś innego, ja nie zmieniałem kodu):

1. W `captions` po `author_captions` i `auto_captions` (yt-dlp) dodać `external_captions(vid)`: jeśli w środowisku jest `SUPADATA_API_KEY`, wywołać `GET /v1/transcript?url=...&lang=pl&mode=native` (nagłówek `x-api-key`), zmapować `content[]` (`offset`/`duration` w ms) na segmenty w tym samym formacie, co `parse_vtt`, ustawić `source="supadata-native"`, `is_generated=true`. Statusy 206/403/404 mapować na istniejące statusy (`unavailable`, `private`). Respektować kolejny cache: wynik trafia do `.runtime/media-cache/<id>/`, powtórka nie robi żądania.
2. W `asr_audio` dodać backend wybierany zmienną środowiskową `ASR_BACKEND` (`vosk` domyślnie, `groq`); dla `groq` zamiast limitu 120 s wysłać cały plik (po konwersji do FLAC/mp3 mono 16 kHz, <25 MB) z `language=pl`, `response_format=verbose_json`, zapisać `avg_logprob`/`no_speech_prob` jako sygnał niepewności.
3. Rozróżniać źródło w polu `source` (auto-napisy YouTube, Supadata, Whisper), żeby kontrola trafności i cytaty niosły informację o pochodzeniu.

Czas wdrożenia: dodatkowa metoda API z cache i testami ok. 2-3 h; backend ASR ok. 2-3 h.

### Jakość cytatów

Auto-napisy YouTube i API, które je przekazują, mają ten sam tekst, w tym błędy nazw własnych i brak interpunkcji. Whisper large-v3/turbo zwykle poprawia interpunkcję i wielkie litery, ale może „halucynować" na ciszy i muzyce (dlatego zapisuj `no_speech_prob`); nie mam zmierzonego porównania na polskich filmach finansowych, więc to wymaga próby na kilku filmach z oznaczonymi cytatami (np. marker reklamowy) przed zmianą domyślnego źródła. Dla dowodów/cytatów w demie: replay zapisuje już datowane segmenty, więc źródło może się różnić między filmami, o ile jest zapisane.

## 4. Ryzyko prawne i regulaminowe (nazwane wprost)

- Regulamin YouTube (youtube.com/t/terms, wersja polska, odczyt 2026-11-21) zabrania dostępu do Usługi „za pomocą jakichkolwiek automatycznych środków (takich jak roboty, botnety lub scrapery)" poza wyszukiwarkami zgodnie z robots.txt lub za pisemną zgodą YouTube, oraz „dostępu do jakiejkolwiek części Usługi lub jakiejkolwiek Treści ani jej powielania, pobierania" poza dozwolonymi przez Usługę sposobami. Dotyczy to yt-dlp, youtube-transcript-api i każdego scrapera, a pobieranie audio do ASR jest najbardziej narażone na zarzut „pobierania treści".
- Płatne API przerzucają ruch na dostawcę, ale nie zdejmują odpowiedzialności umownej z nas: korzystamy z danych pozyskanych w sposób sprzeczny z regulaminem. To ryzyko dostawcy i nasze, nie ocenione prawnie. Nie jest to porada prawna; decyzję o akceptacji ryzyka podejmuje właściciel produktu. Wcześniejsza decyzja właściciela (21.11.2026) dopuszcza pobieranie napisów publicznych filmów do demo.
- Bez logowania, cookies, proxy i zmiany tożsamości (zasada projektu): rotowane proxy rezydencyjne zalecane w README youtube-transcript-api są poza tym zakresem i NIE rekomenduję ich.
- Bezpieczniejsze ścieżki: podcastowe bliźniaki z RSS (hosting twórcy) i napisy przekazane przez twórców.
- Demo działa z replay, więc brak zależności od usługi w czasie pokazu; dane osobowe nie są wysyłane poza URL publicznego filmu (dla ASR w chmurze wysyłany jest sam dźwięk publicznego filmu).

## 5. Co dokładnie musi zrobić właściciel

1. Założyć konto na supadata.ai (bez karty, 100 darmowych kredytów), skopiować klucz API z panelu i zapisać w lokalnym pliku środowiska poza Gitem (np. `.runtime/secrets.env`: `SUPADATA_API_KEY=...`). Ścieżkę pliku i nazwę zmiennej ustali wdrażający adapter; obecnie projekt nie ma takiego pliku (nie sprawdzałem konwencji sekretów).
2. Zdecydować o płatności za Pro ($17) tylko po teście polskiego na kilku filmach z darmowego pakietu.
3. Opcjonalnie dla ASR: konto Deepgram (bez karty, $200) lub Groq; klucz do tego samego pliku (`DEEPGRAM_API_KEY` / `GROQ_API_KEY`).
4. Zaakceptować lub odrzucić ryzyko regulaminowe z sekcji 4.

## 6. Ograniczenia researchu

- Nie testowałem żadnej usługi płatnej ani chmurowej; ceny i limity pochodzą ze stron dostawców (odczyt 2026-11-21) i zestawień stron trzecich, część od dostawców z własnym interesem.
- Nie potwierdziłem obsługi języka polskiego dla żadnego płatnego API transkrypcji, ani dla Deepgram, AssemblyAI (strony ich nie wymieniają).
- Prędkość Whisper na 4 vCPU i M3 oraz WER po polsku NIE zostały zmierzone ani znalezione; podane wartości to oszacowania i muszą być zweryfikowane próbą.
- Próby z hosta były małe (4 filmy, 5 wywołań) i w momencie prób 429 nie występował; nie wiem, czy limit wróci po kolejnej serii ani jakie jest jego okno czasowe.
- Średnia długość filmu w kolejce (20 min) jest założeniem.
- Bright Data, Oxylabs, ScrapingBee, RapidAPI, youtube-transcript.io oraz pokrycie podcastowych bliźniaków RSS nie zostały zbadane.

## Źródła (odczyt 2026-11-21)

- https://supadata.ai/pricing, https://docs.supadata.ai/get-transcript
- https://transcriptapi.com/pricing, https://transcriptapi.com/blog/youtube-transcript-api-comparison
- https://www.scrapingdog.com/youtube-transcripts-api/
- https://www.searchapi.io/pricing, https://serpapi.com/pricing
- https://github.com/jdepoix/youtube-transcript-api, https://pypi.org/project/youtube_transcript_api
- https://console.groq.com/docs/speech-to-text, https://console.groq.com/docs/rate-limits
- https://www.deepgram.com/pricing, https://www.assemblyai.com/pricing, https://developers.openai.com/api/docs/pricing
- https://research.youtube.com/how-it-works
- https://www.youtube.com/t/terms
