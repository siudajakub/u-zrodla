# Linia C: multimedia (napisy, kadry, pokrycie)

Data: 2026-11-21. Wykonawca: Sonnet 5.5 (claude-sonnet-5-5), poziom wysiłku zgodny z planem (high); ustawienia nie da się odczytać z sesji. Gałąź hack/integration, HEAD 491094d, bez commitu. Zgoda J z 21 XI: transkrypcje i kadry z publicznych filmów YouTube na potrzeby demo.

Zakres: `collectors/media.py`, `collectors/test_media.py`, `fixtures/raw/media/2026-11-21/`, `.runtime/media-cache/` (ignorowany przez Git, sprawdzono `git check-ignore`). `collectors/audio.py` i `analysis/transcribe.py` tylko wywoływane.

## Narzędzia

- yt-dlp 2026.10.26 (Unlicense), wyłącznie w `.runtime/venv` (`.runtime/venv/bin/pip install yt-dlp`). Bez ciasteczek, logowania i omijania zabezpieczeń. Ostrzeżenia yt-dlp o braku środowiska JS i impersonacji nie wpłynęły na wynik.
- ffmpeg 6.1.1 z hosta (`/usr/bin/ffmpeg`), lokalny Vosk `vosk-model-small-pl-0.22`.
- Blokad YouTube nie napotkano: żadnego żądania logowania ani HTTP 429 na czterech filmach.

## Interfejs

`media.enrich(capture, ctx=None, *, frames_at, frame_method="auto"|"storyboard"|"stream", allow_asr=False|True|"force", max_seconds=120, cache_dir)`; nie zgłasza wyjątków. Opcje mogą przyjść w `ctx.media` (dict). Zwraca:

- `segments[]`: `{start,end,text,modality:"speech",method,language,lang,windowId,deepLink}`. `method` ma nazwy z kontraktu H: `author_captions`, `auto_captions`, `asr` (zamiast `captions_manual`/`captions_auto` z zadania, żeby D i H nie mieli dwóch słowników).
- `frames[]` (evidence `kind:"frame"`, `modality:"frame"`): `time` (czas faktycznego kadru), `requestedTime`, `path`, `sha256`, `width`, `height`, `bytesFile`, `bytesFetched`, `deepLink` = `sourceUrlAtTime` = `url`, `sourceVersion`, `observedAt`, `available`.
- `sourceVersion {videoId, readAt, captionsSha256, descriptionSha256, ytDlpVersion}`, `mediaVersion` (skrót napisów lub audio).
- `mediaCoverage` (kształt z kontraktu H: `transcript{state,source,windows,durationSec,reason}`, `frames{state,moments,intervalSec}`) oraz `coverage` (`checked` z nazwami description/speech/frames_selected, `modalities`, `gaps[{modality,code,reason}]`, `blocksConclusion`, `label`).
- `status`: `ok`, `no_transcript`, `private`, `unavailable`, `age_restricted`, `members_only`, `login_required`, `rate_limited`, `timeout`, `error`, `unsupported`; powód w `error.reason` i `coverage.gaps`.
- `stats {requests, bytes, wallSeconds}`; `find_markers(segments, description)` zwraca leksykalne wskazówki (reklama, współpraca, partner, sponsor, link w opisie, kod, promocja, broker) z czasem i `deepLink`. To podpowiedź do przeglądu, nie kwalifikacja.

Cache: `.runtime/media-cache/<videoId>/` (`meta.json`, `raw/*.vtt`, `transcript.json`, `asr.json`, `frames/`). Powtórne wywołanie nie robi żadnego żądania (test i próba live: `requests: 0`). Statusy trwałe (prywatny, usunięty, wiek, tylko dla członków) są cache'owane, przejściowe (limit, login, timeout) nie, więc kolejne wywołanie wznawia. Odstęp między żądaniami ≥ 2 s (`MIN_GAP`, wspólny dla procesu), limit czasu na film 120 s. ASR dostaje blokadę pliku `.heavy.lock`: najwyżej jeden naraz, drugi dostaje status `busy`.

## Pomiary: napisy (próba live, pierwszy przebieg bez cache)

Jedno wywołanie yt-dlp `--skip-download --write-subs --write-auto-subs --sub-langs "pl.*" --sub-format vtt --write-info-json` daje metadane, pliki napisów i adresy storyboardów. Żaden film nie ma napisów autora, wszystkie cztery mają automatyczne polskie (`pl-orig`).

| Film | Metoda | Czas ścienny | Bajty napisów (VTT) | Segmenty | Długość |
|---|---|---|---|---|---|
| CDk20n4u9Kk Comparic Rynki | auto_captions | 2,18 s | 142 464 B | 434 | 1065 s |
| xtMqKkFO-0M DETERMINACJA | auto_captions | 2,01 s | 21 593 B | 75 | 204 s |
| -HpCSKp9bqk Cymcyk | auto_captions | 1,95 s | 169 832 B | 516 | 1095 s |
| 9Fcwo1jlwe4 Cymcyk (nie Freedom24) | auto_captions | 2,18 s | 320 229 B | 975 | 2128 s |

Bajty to jeden plik `pl-orig` (yt-dlp zapisuje też identyczny `pl`, więc pobiera dwa razy). Skróty plików VTT: `fixtures/raw/media/2026-11-21/<id>.json`. Ruch ekstraktora yt-dlp (strona i player API, `info.json` ma ok. 1,1 MB po rozpakowaniu) nie został zmierzony. Film 9Fcwo1jlwe4 to materiał o Nvidii z promocją Freedom24 w mowie i opisie, nie film Freedom24.

## Pomiary: kadry bez pobierania filmu

Zmierzono na xtMqKkFO-0M (204 s) i długich filmach:

| Droga | Wynik | Koszt |
|---|---|---|
| A. `yt-dlp --download-sections "*60-62"` w formacie 144p | działa, 7 kB pliku, kadr trzeba wyciąć | 3,1–3,4 s i drugie wywołanie ekstraktora na kadr |
| B. `yt-dlp -g` + `ffmpeg -ss T -i <URL> -frames:v 1`, 360p | działa, kadr dokładny co do sekundy, 640x360 | 131–206 kB odczytanych z sieci na kadr (ffmpeg `Statistics: bytes read`), 1,8 s na filmie 204 s, 3–8 s na filmach 1000–2100 s |
| C. Storyboard `sb0` (publiczny arkusz miniatur i.ytimg.com), 320x180 | działa, jedno żądanie arkusza daje 9 kadrów | 17–65 kB na arkusz, czyli ok. 2–7 kB na kadr, 0,2 s |

Wybór: droga C domyślnie, gdy kafelki są gęste (film ok. 3 min: co 1,96 s; film ok. 18–35 min: co ~9,9 s, za rzadko, żeby wskazać moment). Tryb `auto` używa więc storyboardu tylko przy odstępie ≤ 5 s, w pozostałych przypadkach drogi B (koszt na kadr: ~130–210 kB i 3–8 s). Droga A odrzucona, bo drożej niż B i wymaga wycinania. Żadna droga nie pobiera całego filmu.

Kadry obejrzane w rzeczywistym materiale:

- CDk20n4u9Kk 614 s (B, 640x360, 140 433 B): w lewym górnym rogu etykieta „REKLAMA” nad banerem XTB, dolny pasek XTB z ostrzeżeniem o ryzyku. Oznaczenie widoczne na ekranie.
- -HpCSKp9bqk 95 s (B): logo XTB w studiu, bez etykiety i tekstu współpracy. 104 s (B): plansza „PARTNEREM ODCINKA JEST XTB” z ostrzeżeniem o ryzyku.
- xtMqKkFO-0M 109 s (C): „Z kodem: DETERMINACJA”, „Partnerem kanału jest XTB”, czytelne mimo 320x180.
- 9Fcwo1jlwe4 195 s (B, 206 057 B): mały druk „REKLAMA” w lewym dolnym rogu, logo FREEDOM, QR do założenia konta.

## Wyszukane momenty (leksykalnie; auto-napisy bywają błędne)

- CDk20n4u9Kk: 614 s „znajdziecie u partnera tego odcinka XTB.”, 617 s „A z kodem Komparik dorzucają jeszcze darmowy kurs inwestowania.” (kod w opisie to „COMPARIC”, auto-napisy błędnie zapisały nazwę). Opis zawiera link afiliacyjny XTB i kod, ale nie ma słów „reklama” ani „współpraca”. Mowa i obraz oznaczają współpracę, więc podejrzenie nieoznaczonej współpracy opiera się tylko na opisie.
- xtMqKkFO-0M: 109 s „Partnerem odcinka jest XTB, a z kodem DETERMINACJA możecie odebrać darmowy kurs”. Opis ma #współpraca i „Partnerem odcinka jest XTB”.
- -HpCSKp9bqk: 94–106 s „dzięki partnerowi tego odcinka, jakim jest XTB … konto z linka w opisie, podacie kod DN na rynków” (kod w opisie to DNARYNKOW). Inni partnerzy w mowie: Lantre 115 s, e-Faktury 153 s. Opis ma link i kod XTB, ale nie ma słów „reklama” ani „współpraca” przy XTB.
- 9Fcwo1jlwe4: 192–213 s partner kanału Freedom24, „konto z linka w opisie”, 20 darmowych akcji. Dalej partnerzy Lantre i Faktor, 2089 s „filmiku, który powstał dzięki partnerowi”. Kadr 195 s ma etykietę REKLAMA.

Pełna lista z czasem i cytatem (do 300 znaków) jest w `fixtures/raw/media/2026-11-21/<id>.json`.

## Ścieżka ASR (ciężka), jeden przebieg na xtMqKkFO-0M

Wymuszona (`allow_asr="force"`) na filmie 204 s: audio najniższej jakości `--download-sections "*0-120"` (731 560 B, m4a), Vosk 13,8 s, razem 17,6 s, 20 segmentów w oknie 0–120 s (`partial`). Jakość jest nieużyteczna: małe polskie Vosk daje ciąg niezwiązanych słów na tym materiale (tło, muzyka), np. „topór foliowy skanuje tępy łask”. Wniosek: ASR to mechanicznie działający awaryjny dowód obecności mowy, nie źródło cytatów. Auto-napisy YouTube są wielokrotnie lepsze i tańsze (2 s, 0 B audio). `analysis.transcribe` ogranicza analizę do 120 s, więc dłuższe filmy bez napisów mają `coverage.transcript.state="partial"` i `blocksConclusion=true`.

## Błąd znaleziony w trakcie

Pierwsza wersja parsera VTT gubiła pierwszy cue pliku, bo YouTube zapisuje linię złożoną z jednej spacji tuż po nagłówku cue. Naprawiono (koniec cue to linia dokładnie pusta), test używa tej linii. Transkrypty z cache przeliczono.

## Ograniczenia i znane luki

- Napisy automatyczne mają błędy nazw własnych i liczb (np. „Komparik”, „DN na rynków”). Cytat dosłowny, `match` dla D to `approximate`.
- Brak flagi „płatna promocja” YouTube: yt-dlp jej nie zwraca, `paidPromotionFlag` należy do B (Data API).
- Brak napisów polskich dla filmu w innym języku nie uruchamia tłumaczenia: `pl` bez `pl-orig` przy `language` ≠ pl jest oznaczane `translated`.
- Storyboard w trybie `auto` nie jest używany przy rzadkich kafelkach. Adresy storyboardów w `meta.json` mają podpisy czasowe: po wygaśnięciu (403) kadr kończy się luką `frames` w `coverage.gaps`; `refresh=True` pobiera nowe.
- Ruch ekstraktora yt-dlp nie jest wliczony do `stats.bytes`. Warunki YouTube: zgoda J obejmuje demo; poprzedni zapis w lane B (`yt-dlp` poza warunkami serwisu) pozostaje ryzykiem produkcyjnym.
- Nie podłączono do `api/jobs.py` (to S8 po stronie H). Nie uruchamiano Chromium ani Compose.

## Jak powtórzyć

```sh
.runtime/venv/bin/python -B -m unittest collectors.test_media
PYTHONPATH=. .runtime/venv/bin/python -B -m collectors.media https://www.youtube.com/watch?v=xtMqKkFO-0M --frames 109
PYTHONPATH=. .runtime/venv/bin/python -B -m collectors.media -HpCSKp9bqk --frames 95,104 --frame-method stream
```

Test: 20 testów offline (parser, deduplikacja, cache, statusy błędów, odstęp 2 s, deepLink, kadry ze storyboardu, ASR wstrzyknięty), wynik OK.

## Paczka 2: 13 filmów kandydatów (napisy, kadry, `qualify`)

Wyniki zbiorcze: `fixtures/raw/media/2026-11-21/kandydaci-wyniki.json` oraz `<videoId>.json` dla każdego filmu. Opisy z `replay.json.gz` (YQH4FEP9exI spoza replay: opis z yt-dlp, flaga nieznana). `qualify` wywołano na `capture` z `youtube.paidPromotionFlag` w obu wariantach (A: sam opis, B: opis + `segments` + `frames` z `observation` + `mediaCoverage`).

Koszt: napisy 13 filmów 29,3 s (jedno żądanie na film, odstęp ≥ 2 s), 3 560 844 B plików VTT (pl i pl-orig razem); kadry 61,1 s i ok. 1 077 kB (storyboard 18–49 kB na arkusz, stream 360p 49–206 kB na kadr). Brak blokad YouTube, brak 429, brak żądania logowania. ASR nie uruchamiano.

Wnioski o `qualify` (do D, bez edycji analysis/):

- yIbtMnfP25Q: mowa 57 s „używam i polecam konto XTB, które jest partnerem mojego kanału”. `qualify` mimo to daje `refer` z „nie znaleziono oznaczenia w mowie (pełny zakres)”. Fraza „partnerem mojego kanału” nie jest rozpoznana ani przy łączeniu segmentów po 3 i 5. Fałszywe skierowanie w wariancie B.
- o2GfnmVVkO8: mowa 77 s „Freedom partnera tego odcinka” (auto-napisy gubią czasownik). `refer` przy segmentach pojedynczych i po 3, `no_signal` dopiero po 5 połączonych segmentach: wynik zależy od granic segmentów. Warto, by D łączył sąsiednie segmenty w okna.
- O5YmmKadQQw (eToro) i AqXHkxDzSDI (XTB, kod TRADEXTB i skrócony link bit.ly): `no_signal` „wzmianka o firmie bez relacji reklamowej” już w wariancie A, mimo linku i kodu w opisie bez oznaczenia. Linki tinyurl/bit.ly i kod w nawiasie nie liczą się jako dowód relacji. Do decyzji D/J.
- eQYmvRfHtr8, YQH4FEP9exI, ePfzHQVf-lc: wariant A `refer`, wariant B `no_signal` (oznaczenie „partner odcinka” w mowie). Zgodne z intencją.
- Kadry: etykiet „REKLAMA”/„współpraca” nie znaleziono w żadnym z 20 obejrzanych kadrów 6 filmów bez oznaczenia w opisie i mowie (wcześniejsza próba: etykieta była na Comparic 614 s i Freedom24 195 s). Kadry Shortów mają tylko 101x180 (storyboard) lub 144x256 (stream), drobny druk byłby nieczytelny.
