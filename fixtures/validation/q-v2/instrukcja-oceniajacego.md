# Instrukcja oceniającego · M1 (filmy YouTube twórców)

Oceniasz 17 publicznych polskojęzycznych filmów YouTube. Każdy plik `<videoId>.txt` w tym katalogu zawiera: kanał, tytuł, opis, flagę płatnej promocji z YouTube API, pełną automatyczną transkrypcję mowy z sekundami oraz listę kadrów (pliki JPG w katalogu `frames/` podanym w pakiecie) z notatkami innego agenta. Kadry obejrzyj sam narzędziem do czytania plików (obrazy). Nie otwieraj żadnych innych plików ani repozytorium, nie szukaj w sieci, nie konsultuj się z nikim.

## Pytanie

Czy materiał zawiera **udokumentowaną przesłankę wymagającą kontroli**? W M1 przesłanką jest wyłącznie **nieoznaczona współpraca handlowa z firmą inwestycyjną** (broker, dom maklerski, platforma inwestycyjna/kryptowalutowa/forex, fundusz, bank w zakresie usług inwestycyjnych):

- **skieruj (TAK)**: w opisie jest dowód relacji handlowej z firmą inwestycyjną (np. link afiliacyjny/referencyjny z kodem, kod promocyjny, „zarejestruj się z mojego linku”, bonus za otwarcie konta przez link) ORAZ jednocześnie brak oznaczenia współpracy w opisie, w mowie, w sprawdzonych kadrach i brak flagi płatnej promocji YouTube (`True` = oznaczono).
- **rejestr (NIE)**: współpraca jest jawna/ujawniona w dowolnej modalności — flaga płatnej promocji `True`, albo słowa typu „sponsor”, „partner odcinka/kanału”, „współpraca reklamowa”, „link partnerski/afiliacyjny”, „reklama”, „materiał sponsorowany” w opisie, mowie lub na kadrze. Ujawnienie choćby w jednej modalności wystarcza.
- **bez_sygnalu (NIE)**: brak relacji handlowej z firmą inwestycyjną (opinia, edukacja, wzmianka o brokerze bez linku/kodu), albo relacja dotyczy firmy spoza zakresu (np. sklep, VPN, kurs własny twórcy, aplikacja budżetowa, wydarzenie), albo własne produkty twórcy.
- **nieustalone**: nie da się rozstrzygnąć z dostępnych danych (podaj kod: `brak_modalnosci`, `tozsamosc`, `inne`).

Uwagi: jeśli flaga płatnej promocji jest „NIEZNANA”, oceniaj na podstawie opisu, mowy i kadrów i odnotuj to w `coverageNote`. Brak kadrów to luka pokrycia — odnotuj. Sam fakt, że twórca mówi dobrze o brokerze, nie jest relacją handlową. Etykieta nie stwierdza naruszenia prawa. Jeśli w jednym filmie jest kilka firm, oceniaj najsilniejszą relację z firmą inwestycyjną i wpisz jej nazwę w `firm`.

## Wynik

Zapisz do pliku `oceny-B.jsonl` w tym katalogu (jeden obiekt JSON na linię, 17 linii):

```
{"materialId": "youtube:<videoId>", "label": "skieruj|rejestr|bez_sygnalu|nieustalone", "firm": "nazwa firmy albo null", "requirement": "M1:nieoznaczona-wspolpraca albo null", "quote": "dosłowny cytat z opisu/mowy/kadru (relacja lub ujawnienie)", "locator": "opis | mowa NNs | kadr plik", "reason": "uzasadnienie 1-3 zdania", "counterArgument": "najmocniejszy kontrargument", "coverageNote": "czego nie zbadano", "confidence": "niska|średnia|wysoka"}
```
