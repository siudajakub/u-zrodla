# Materiały konkursowe UKNF

Źródłem wymagań jest [uknf.zip](uknf.zip) przekazany przez J. Archiwum zawiera pięciostronicowy opis wyzwania i cztery załączniki Word. Poniższe opracowania pozwalają sprawdzić wymaganie bez dostępu do katalogu załączników czatu.

| Dokument w ZIP | Opracowanie | Co rozstrzyga |
|---|---|---|
| Opis Wyzwania HackNation UKNF 19.11.pdf | [Brief, strony 1–5](BRIEF.md) | Cel, wyniki trzech modułów, MVP, wymagania techniczne i formalne, sposób sprawdzenia i punktacja |
| Załącznik do Tematu 1 Wyzwanie KNF HackNation.docx | [Temat 1](TEMAT-1.md) | Definicje firm i pięć odsyłaczy rejestrowych wykorzystywanych przy promocji przez osoby trzecie |
| Załącznik do Tematu 2 Wyzwanie KNF HackNation.docx | [Temat 2](TEMAT-2.md) | Te same definicje i rejestry, tym razem w odniesieniu do materiałów publikowanych przez firmę |
| ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.docx | [Kryteria M2](KRYTERIA-M2.md) | Cztery kolumny i 19 kryteriów, od 1 do 18 z osobnymi 12a i 12b |
| Załącznik do tematu 3 Wyzwanie KNF HackNation 2026.docx | [Temat 3](TEMAT-3.md) | Definicja osobistej rekomendacji i katalog instrumentów finansowych |

SHA-256 archiwum wynosi `ad609dbb0fc9a97e2114c5358101a7ca6039b822b30151fcb48ffdfee5018043`. Polecenie `unzip -t docs/zrodla-uknf/uknf.zip` sprawdza integralność wszystkich pięciu plików. Weryfikacja względem przekazanego oryginału polega na porównaniu SHA-256. Cztery załączniki DOCX są zgodne bajt w bajt ze skrótami odnotowanymi przed tą falą. Tekst wcześniejszej kopii PDF w docs/brief i PDF z ZIP jest identyczny po ekstrakcji pdftotext i normalizacji białych znaków. Same pliki PDF mają różne skróty.

ZIP nie zawiera etykiet jakości, korpusu publikacji, treści umów ani odrębnego regulaminu. Brief wskazuje możliwość odbioru próbek przy stoisku. [Regulamin przechowany wcześniej w projekcie](../brief/Urząd_Komisji_Nadzoru_Finansowego__UKNF_-_Regulamin_Zadania_Konkursowego.txt) ma inne pochodzenie. Materiały znalezione przez kolektory, dane syntetyczne i wyniki testów opisuje [arkusz odbioru](../ODBIOR-UKNF.md).
