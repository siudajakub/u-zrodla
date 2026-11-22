# U Źródła · monitoring promocji, ryzyka i ofert doradczych

## Opis do zgłoszenia

U Źródła pomaga analitykowi UKNF wybrać z wielu publikacji sprawy warte sprawdzenia. Każde skierowanie prowadzi do źródła, konkretnego dowodu i informacji o tym, co system zdołał odczytać.

- **M1 · Materiały twórców.** System szuka polskojęzycznych kanałów YouTube przez oficjalne API i odczytuje podpisy z publicznych osadzeń wybranych profili TikTok. W materiale sprawdza dostępny opis, oznaczenie platformy i transkrypcję. Wybrane kadry pokazuje analitykowi. Jawna współpraca trafia do rejestru reklam z twórcą, firmą i adresem publikacji. Przy podejrzeniu analityk może przejść wprost do cytatu lub sekundy filmu.
- **M2 · Reklamy firm.** Na stronach firm system sprawdza 19 kryteriów UKNF. Przy informacji o potencjalnym zysku wskazuje ostrzeżenie właściwego produktu i zapisuje jego położenie na komputerze i telefonie. Analityk może porównać pomiar z obrazem strony.
- **M3 · Oferty doradcze.** System wskazuje cytat sugerujący personalizację usługi. Analityk widzi osobno, czy ustalono operatora i czy datowany wykaz wskazuje uprawnienie do tej usługi.

Urzędnik wybiera dalsze działanie, przegląda i edytuje szkic uzasadnienia, po czym zatwierdza zapis. Sprawa trafia do wewnętrznej kolejki kontroli, uzupełnienia lub zakończenia. Zespół może wpisać wynik kontroli, odnotować źródło nowych danych albo ponownie otworzyć sprawę. Historia i eksport CSV zachowują decyzję wraz ze sprawdzoną wersją materiału.

## Po co sprawdzamy mowę filmu

ForexMind i Comparic umieścili w opisach link i kod związane z XTB. W filmie ForexMind w 0:15 pada odesłanie do specjalnych ofert. W sprawdzonym opisie i transkrypcji system nie znalazł oznaczenia współpracy, więc sprawa trafia do sprawdzenia, z kadrami do oceny przez analityka. W filmie Comparic w 10:14 twórca nazywa XTB partnerem odcinka. Ta wypowiedź wyjaśnia przesłankę z opisu, a publikacja trafia do rejestru reklam. [Scenariusz pokazu](docs/hackathon/demo.md)

## Co widać dopiero po przeczytaniu podpisu

Odsyłacze z opisów YouTube doprowadziły nas do 26 kont twórców na Instagramie. W pięciu zapisanych postach @kacper.snela autor podał „[współpraca z XTB]” na początku podpisu. W każdym pole płatnej współpracy miało wartość „nie”. Analityk może wrócić do tekstu i adresu publikacji. Próbka Meta z 21 listopada obejmuje 350 postów z 31 kont Instagrama, 30 wpisów z 10 stron Facebooka i 114 reklam z filtrem kraju emisji „Polska”, razem 494 materiały. [Rejestr pozyskania i przykładowe publikacje](docs/lanes/2026-11-21-fable-k-social.md)

## Stan względem briefu

Pulpit z 22 listopada pokazał **13 690 materiałów**, **2 959 pozycji w rejestrze reklam** i **16 spraw do sprawdzenia**. To rozszerzona migawka obejmująca także starsze publikacje kanałów z wykrytymi współpracami. [Pochodzenie liczników](docs/hackathon/demo.md)

Datowane odtworzenie działa offline i obejmuje 1 922 materiały, 274 wpisy w rejestrze reklam oraz 17 spraw do sprawdzenia, w tym 7 M1, 9 M2 i 1 M3. W siedmiu sprawach M1 występuje pięć par twórca–reklamodawca i dwie marki, XTB oraz eToro. [Liczniki stanowiska](docs/hackathon/demo.md)

| Zakres | Dowód działania | Ograniczenie |
| --- | --- | --- |
| YouTube i TikTok | Odkrywanie i monitoring YouTube przez Data API v3. Stan pokazu ma 1 307 filmów YouTube i 64 posty TikToka. | Pełna transkrypcja jest dostępna dla 23 z 1 307 filmów w tej bazie. Próba Y znalazła 3 z 5 największych kanałów. Z TikToka w pokazie mamy podpisy. |
| Facebook i Instagram | Pokaz odtwarza 30 wpisów z Facebooka, 350 postów z Instagrama i 114 reklam znalezionych przy wyszukiwaniu z filtrem kraju „Polska”. Analityk może też zaimportować zapisaną stronę. | Próbkę zebrał ScrapeCreators 21 listopada 2026 r. Ocena obejmuje tekst i metadane. Odczyt reklam przez oficjalne API Meta wymaga jeszcze próby z uprawnionym tokenem. |
| M2 | Próba rynkowa objęła 25 stron 11 firm, w tym trzy oddziały zagraniczne. Jest pomiar ostrzeżeń na komputerze i telefonie. | Etykiety są ocenami agenta. Wiersz 2 jest obserwacją bez wpływu na wynik, a tablet ma dowód w starszej, mniejszej próbie. |
| M3 | 29 domen, 12 datowanych wykazów, w tym jedna rynkowa przesłanka do sprawdzenia na rdmwm.pl. BOŚ stanowi kontrolę firmy z uprawnieniem. | Operator rdmwm.pl pozostaje nieustalony. Odkrywanie rynkowe korzystało z przygotowanych wyników wyszukiwania. |
| Analiza i decyzje | Reguły wiążą skierowanie z dowodem. Lokalny E5 wspomaga rozpoznanie rodzaju materiału, Ollama dostarcza drugą opinię, a panel kalibracji pokazuje skutki zmiany progu w każdym module. | Wyniki pochodzą z ograniczonych prób z etykietami agentów. Ślepa próba M1 objęła osiem kontroli ujemnych. Walidacja wykrywania wymaga nowych kampanii i etykiet eksperckich. |

[Brief i załączniki](docs/zrodla-uknf/README.md) · [Odbiór](docs/lanes/2026-11-22-odbior-finalny.md) · [Film dla jury](presentation/film/U-Zrodla-final-stabilny-116s.mp4) · [Quick Start](README.md) · [Scenariusz](docs/hackathon/demo.md)
