# Inwentarz danych do walidacji · stan 21 XI 2026

Przegląd objął HEAD 491094d z niezacommitowanymi zmianami w dokumentach. Zasady podziału określa [PROTOKOL.md](PROTOKOL.md), a wynik zamrożenia znajduje się w [q-v1](q-v1/README.md). Liczby są rzeczywistymi mianownikami, bez ekstrapolacji.

## Źródła w repozytorium

| Źródło | Co zawiera | Status w walidacji |
|---|---|---|
| `fixtures/labeled/calibration.json` (`868efb7e2016`) | 13 wierszy: 4 publiczne (yt-partner, dom-etf, M3-boś, M3-agent) i 9 syntetycznych. Etykiety robocze jednego autora reguł, nie ślepe, z dawnym celem „skierowanie do przeglądu / rozpoznanie usługi” | **Historyczny zbiór ilustracyjny, nie zmieniany.** Syntetyczne wiersze zostają w regresji. Publiczne materiały są w q-v1 z etykietami według nowej jednostki |
| `fixtures/labeled/showcase.json` | 6 kart demo: 3 syntetyczne (demo-studio-aurora, demo-aurora-kod, demo-pracownia-edukacja) i 3 publiczne (dom-xtb-etf, public-financewell-agent, public-bos-profil) | Syntetyczne i ich `analysis/media/*.mp4` (2 klipy eSpeak) wyłącznie w regresji. Publiczne w q-v1 |
| `fixtures/raw/discovery/2026-11-21.json` | Replay: 21 twórców, 21 źródeł, 11 materiałów (10 M1 i 1 M2 BDM w formie tekstu) | 10 materiałów M1 w q-v1. BDM zastępuje wersja renderowana z archiwum M2 |
| `fixtures/validation/bossa-*-2026-11-21.json` | 2 materiały M3: oferta doradztwa DM BOŚ i strona edukacyjna | W q-v1 |
| `fixtures/validation/knf-extract-2026-11-21.json` | Wyciąg KNF (zakres 5, KRS) | Kontekst rejestrowy, nie materiał |
| `data/probe-snapshots/m2/` | 3 manifesty z ujęciami Chromium: xtb-etf, xtb-akcje, bdm-rachunek | W q-v1, w tym xtb-akcje |
| `data/probe-snapshots/2026-11-21-discovery-check.json` | 30 pozycji Atom (po 15 z DETERMINACJA i Comparic Rynki); zachowano tylko 2 deklaracje oraz skróty XTB „plany inwestycyjne” i KID bossa | Nie nadaje się. Brakuje treści pozostałych 28 pozycji, a dla dwóch stron zachowano tylko skróty |
| `data/probe-snapshots/social/` | Linki do postów TikTok bez treści | Nie nadaje się |

## Zbiór q-v1 według modułów

| Moduł | Materiały | Jednostki niezależne | Kampanie reklamowe firm inwestycyjnych | `skieruj` (agenci) | `rejestr` | `bez_sygnalu` | `nieustalone` | Pełne pokrycie głównej modalności |
|---|---|---|---|---|---|---|---|---|
| M1 | 10 | 9 | 1 (DETERMINACJA × XTB, 2 filmy) | 0 | 2 | 8 | 0 | 0. Same tytuły i fragmenty opisów, bez mowy i obrazu |
| M2 | 3 | 3 (2 reklamodawców) | 3 | 2 (XTB ETF, XTB akcje) | 1 | 0 | 0 | 3 w tekście DOM, bez stopki |
| M3 | 4 | 3 | 1 (oferta DM BOŚ, 2 adresy) | 0 | 2 | 1 | 1 (FinanceWell, tożsamość) | 2 z 4. Pozostałe dwa to wycinki |
| **Razem** | **17** | **15** | **5** | **2** | **5** | **9** | **1** | |

Dodatkowe ograniczenia:

- Zamknięty test liczy 0 kampanii. Wszystkie materiały były widziane przy budowie reguł i zostały zaobserwowane 21 XI 2026, więc należą do strojenia.
- Nie ma losowej próby spoza alarmów, bo brak populacji skanu z zapisanym losowaniem. Nie ma też wzorca eksperckiego.
- W M1 brakuje rzeczywistej przesłanki `skieruj`, promocji wyłącznie w mowie i polskojęzycznej promocji firmy transgranicznej. Kontrakt D potwierdza brak takiego materiału w fiksturach.
- W M3 brakuje rzeczywistego przypadku nieuprawnionej usługi.
- Obie pozytywne kampanie M2 pochodzą od jednego reklamodawcy i wynikają z tego samego szablonu strony.
- Seedy (DETERMINACJA, Comparic Rynki, comparic.pl, tradewarspl) wnoszą 5 z 10 materiałów M1. Odkrycie przez wyszukiwanie dotyczy 5 materiałów: 3 z Apple Podcasts i 2 z PeerTube.

## Różnica wobec historycznych etykiet

| Wpis w calibration.json | Dawna etykieta | Klasa w q-v1 | Powód |
|---|---|---|---|
| yt-partner (youtube:xtMqKkFO-0M) | `true` | `rejestr` (false) | Jawna współpraca bez odrębnej przesłanki, zgodnie z kontraktem D. Razem z 04mmNbAlHFo jedna kampania |
| dom-etf | `true` | `skieruj` | Twierdzenie o dochodzie z dywidend i ostrzeżenie ok. 921 px CSS dalej na 390 px (M2:3) |
| M3-boś (public-bos-profil) | `true` | `rejestr` (false) | Podmiot z kodem zakresu 5. Dawna etykieta oznaczała rozpoznanie usługi, nie przesłankę kontroli |
| M3-agent (financewell) | `true` | `nieustalone` | Dwa wpisy w wykazie agentów, brak opisu usługi |

Obecne reguły na historycznym zbiorze przy progu 60 dają TP 4, FP 1, TN 4, FN 4 i koszt 9 (`analysis.engine.calibration(60)`, odczyt 21 XI 2026). Ten wynik nie jest porównywalny z q-v1, bo cel etykiety jest inny, a 9 z 13 przykładów jest syntetycznych.

## Ile brakuje do bramki

Bramka wymaga ≥ 20 skierowań z różnych kampanii w odłożonym teście, precyzji ≥ 90% i wzorca eksperckiego. Dziś test liczy 0 kampanii. Potrzeba co najmniej 18 trafnych i 20 skierowanych kampanii zaobserwowanych po `T_cut`, ocenionych przez dwóch ekspertów, oraz losowej próby co najmniej 50 nieskierowanych materiałów na moduł. Realnie potrzeba więcej pozytywów, bo obecna pełność na strojeniu wynosi 1/2.
