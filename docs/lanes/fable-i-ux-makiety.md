# Makiety tekstowe: kolejka i szczegół, warianty A i B

Uzupełnienie do [rekordu linii I](2026-11-21-fable-i-ux.md). Teksty i rekordy pochodzą z `GET /v1/state` z 21 XI 2026, 18:25 UTC. Godziny podano w czasie polskim (UTC+1). Pola, których API jeszcze nie zwraca, zaznaczono `[kontrakt]`. Comparic jest pokazany jako **hipotetyczne skierowanie** wyłącznie do oceny układu. O trasie rozstrzygnie D.

## 0. Stan dzisiejszy po wdrożeniu reguły Q: oba warianty, desktop 1440

```
InvestWatch  [Co wymaga sprawdzenia 0] [Rejestr reklam 18] [Oferty WWW · M2 3] [Doradztwo · M3 3] [Niepełne dane 93] · Więcej ▾ | Źródła  Kalibracja  Dodaj dowód   ● Na żywo
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
⚠ 93 materiały mają wynik ze starszej wersji analizy (reguły 1.1 i 1.2, brak trasy przeglądu).  [Odtwórz skan]
Skan na żywo · 21 lis 2026, 17:20–17:21 · częściowy: 7 profili niedostępnych (HTTP 302) · 78 materiałów przejrzanych · 1 nowy twórca

                     Nie można jeszcze ustalić, co wymaga sprawdzenia
          Materiały czekają na przeliczenie bieżącymi regułami. Do tego czasu kolejka nie jest pusta, tylko nieobliczona.
                                   [Odtwórz skan]   [Zobacz Rejestr reklam]
```

Po przeliczeniu, jeśli D nie skieruje żadnego materiału:

```
                       Brak materiałów z mocną przesłanką do kontroli w ostatnim skanie
       Przejrzano 78 materiałów. 18 jawnych współprac jest w Rejestrze reklam, 1 materiał ma niepełne dane.
                              [Rejestr reklam]   [Niepełne dane]   [Wszystkie materiały]
```

## 1. Wariant A: tabela z rozwijanym powodem

### Desktop 1440, „Co wymaga sprawdzenia” (hipotetyczne skierowanie)

```
Co wymaga sprawdzenia · 1        Skan na żywo · 21 lis 17:20 · częściowy (7× HTTP 302) · 78 przejrzanych
[Szukaj materiału…]  [Moduł: M1 ▾] [Źródło: wszystkie ▾] [Siła: wszystkie ▾] [Od ▢] [Do ▢]   Wyczyść
┌──┬──────────────────────────────────────────────┬──────────────────┬──────────────────────────────────────┬────────────┬──────────┐
│  │ Materiał                                     │ Kanał            │ Powód                                │ Siła       │ Dowód    │
├──┼──────────────────────────────────────────────┼──────────────────┼──────────────────────────────────────┼────────────┼──────────┤
│▾ │ ARABIA SZYKUJE SIĘ NA WOJNĘ DO 2027. A ropa  │ Comparic Rynki   │ Zachęta do rejestracji z linkiem     │ mocna      │ Opis ↗   │
│  │ mimo to tanieje                              │ YouTube · seed   │ partnerskim i kodem, bez oznaczenia  │ 78 / 100   │          │
│  │ opubl. 19 lis 2026 · Nowa                    │                  │ reklamy w opisie                     │ [kontrakt] │          │
├──┴──────────────────────────────────────────────┴──────────────────┴──────────────────────────────────────┴────────────┴──────────┤
│  Wymóg      M1 · oznaczenie przekazu reklamowego · wypowiedź twórcy (osoba trzecia)                                              │
│  Twierdzenie „💰 Inwestowanie z XTB - Sprawdź XTB · 👉 https://link-pso.xtb.com/pso/GFTfa · Kod „COMPARIC” przy rejestracji      │
│              = darmowy kurs inwestowania.”                                                                                       │
│  Kontrargument „Oferowane instrumenty są ryzykowne. Inwestuj odpowiedzialnie.” To ostrzeżenie o ryzyku, nie oznaczenie relacji. │
│  Możliwe wyjaśnienie: relacja Comparic z XTB nieustalona; oznaczenie może być w filmie.                                         │
│  Zakres     opis ✓ · mowa ✗ (nie pobrano) · obraz ✗                       [Otwórz kartę]  [Opis w YouTube ↗]                     │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Karta otwiera się jako osobny widok `#case/youtube:CDk20n4u9Kk` (szablon `detail-page`), na pełnej szerokości i z „← Co wymaga sprawdzenia (filtry zachowane)”.

### Desktop 1440, Rejestr reklam M1 (oba warianty)

```
Rejestr reklam · 18     Jawna współpraca nie jest uchybieniem. Do kontroli trafia dopiero osobna, udokumentowana przesłanka.
┌──┬────────────┬──────────────────────────────┬──────────────────────────────────────────┬──────────┬────────────────┬──────────────────────────────┬────────────────────┐
│  │ Publikacja │ Kanał                        │ Materiał                                 │ Firma    │ Relacja        │ Oznaczenie                   │ Kontrola           │
├──┼────────────┼──────────────────────────────┼──────────────────────────────────────────┼──────────┼────────────────┼──────────────────────────────┼────────────────────┤
│▸ │ 16 lis     │ Finanse Bardzo Osobiste: o…  │ FBO 349: Gdzie założyć IKE lub IKZE w…   │ mBank    │ link partnerski│ ✓ „[reklama_mBank] … w ramach│ bez osobnego       │
│  │            │                              │                                          │          │                │   płatnej współpracy”        │ sygnału            │
│▸ │ 15 lis     │ DETERMINACJA                 │ Dokupiłem Netflix za 200 zł... Efekt mn… │ XTB      │ sponsor        │ ✓ „📢Partnerem odcinka jest  │ bez osobnego       │
│  │            │                              │                                          │          │                │   XTB”                       │ sygnału            │
│▸ │ 10 lis     │ Finanse Bardzo Osobiste: o…  │ FBO 348: Stałe oprocentowanie kredytu…   │ Hipoteka │ sponsor        │ ✓ „…w ramach płatnej         │ bez osobnego       │
│  │            │                              │                                          │ Direct   │                │   współpracy”                │ sygnału            │
│▸ │  8 lis     │ DETERMINACJA                 │ Wittchen -41%, Energy Fuels -33%... Cz…  │ XTB      │ sponsor        │ ✓ „📢Partnerem odcinka jest  │ bez osobnego       │
│  │            │                              │                                          │          │                │   XTB”                       │ sygnału            │
│▸ │  6 lis     │ Finanse Bardzo Osobiste: o…  │ FBO 347: IKE, IKZE czy OKI? Nie wystar…  │ mBank    │ link partnerski│ ? „(link partnerski)” – do   │ do oceny D         │
│  │            │                              │                                          │          │                │   oceny wystarczalności      │                    │
│  │ …          │ (13 kolejnych DETERMINACJA, 2 VIII – 1 XI)                                                                                                    │
└──┴────────────┴──────────────────────────────┴──────────────────────────────────────────┴──────────┴────────────────┴──────────────────────────────┴────────────────────┘
```

### Telefon 390, wariant A

```
┌──────────────────────────────────────┐
│ InvestWatch                ● Na żywo │
│ [Co wymaga spr. 1][Rejestr 18][M2 3]→│  ← TabList przewijany
│ Skan na żywo · 21 lis 17:20          │
│ częściowy · 78 przejrzanych          │
│ [Filtry (0) ▾]                       │
├──────────────────────────────────────┤
│ ▾ ARABIA SZYKUJE SIĘ NA WOJNĘ DO     │
│   2027. A ropa mimo to tanieje       │
│   Comparic Rynki · YouTube · 19 lis  │
│   Zachęta z linkiem partnerskim i    │
│   kodem, bez oznaczenia reklamy      │
│   [mocna · 78/100]                   │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│   Wymóg: M1 · oznaczenie reklamy     │
│   „…link-pso.xtb.com/pso/GFTfa ·     │
│   Kod „COMPARIC” przy rejestracji…”  │
│   Zakres: opis ✓ mowa ✗ obraz ✗      │
│   [Otwórz kartę] [Opis w YouTube ↗]  │
└──────────────────────────────────────┘
```

## 2. Wariant B: lista i szczegół

### Desktop 1440

```
Co wymaga sprawdzenia · 1    Skan na żywo · 21 lis 17:20 · częściowy (7× HTTP 302)   │ M1 · Nowa · YouTube · opubl. 19 lis 2026 · odczyt 21 lis 17:20
[Szukaj…] [M1 ▾] [Źródło ▾] [Siła ▾] [Od][Do]                                       │ ARABIA SZYKUJE SIĘ NA WOJNĘ DO 2027. A ropa mimo to tanieje
┌──────────────────────────────────┬──────────────────────────┬────────┐            │ Comparic Rynki · seed · zasięg nieznany [kontrakt]    Oryginał ↗
│ Materiał                         │ Powód                    │ Siła   │            │ ─ Dlaczego tutaj ───────────────────────────────────────────
├──────────────────────────────────┼──────────────────────────┼────────┤            │ Zachęta do rejestracji z linkiem partnerskim i kodem, bez
│▌ARABIA SZYKUJE SIĘ NA WOJNĘ DO   │ Link partnerski i kod    │ mocna  │            │ oznaczenia reklamy w opisie.
│▌2027. A ropa mimo to tanieje     │ bez oznaczenia reklamy   │ 78     │            │ Wymóg: M1 · oznaczenie przekazu reklamowego (osoba trzecia)
│▌Comparic Rynki · YouTube         │ [Dowód ↗]                │        │            │ Siła 78/100: siła przesłanki do kontroli, nie prawdopodobieństwo.
└──────────────────────────────────┴──────────────────────────┴────────┘            │ Możliwe wyjaśnienie: relacja nieustalona; oznaczenie może być w filmie.
                                                                                    │ Reguły investwatch-rules-pl-1.3 [kontrakt]
 Inne zakładki: Rejestr reklam 18 · M2 3 · M3 3 · Niepełne dane 1                   │ ─ Fakty ────────────────────────────────────────────────────
                                                                                    │ Firma          XTB (rejestr KNF: [kontrakt])
                                                                                    │ Relacja        link partnerski + kod „COMPARIC”
                                                                                    │ Oznaczenie     nie znaleziono w opisie · mowa i obraz niezbadane
                                                                                    │ Odkryto        Profil monitorowany (seed) · Atom 21 lis 16:40
                                                                                    │ ─ Dowody ───────────────────────────────────────────────────
                                                                                    │ [Opis] „💰 Inwestowanie z XTB - Sprawdź XTB”
                                                                                    │ [Opis] „👉 https://link-pso.xtb.com/pso/GFTfa”
                                                                                    │ [Opis] „Kod „COMPARIC” przy rejestracji = darmowy kurs…”
                                                                                    │        Otwórz źródło cytatu ↗  ▸ Akapit źródłowy
                                                                                    │ ─ Kontrargumenty i zakres ──────────────────────────────────
                                                                                    │ „Oferowane instrumenty są ryzykowne…” (ostrzeżenie, nie oznaczenie)
                                                                                    │ Opis ✓ · Mowa ✗ nie pobrano · Obraz ✗
                                                                                    │ [Dowody] [Decyzja] [Historia (2)]
```

Kontrprzykład w tym samym układzie: wybór wiersza w Rejestrze reklam.

```
│ M1 · Nowa · YouTube · opubl. 2 sie 2026
│ XTB dodało długo wyczekiwaną funkcję!
│ DETERMINACJA · Profil monitorowany                                        Oryginał ↗
│ ─ Dlaczego tutaj ────────────────────────────────────────────────────────────────
│ Jawna współpraca z XTB zadeklarowana w opisie. Nie wykryto osobnej przesłanki
│ do kontroli w zbadanym zakresie (opis).        Kontrola: bez osobnego sygnału
│ ─ Fakty ─────────────────────────────────────────────────────────────────────────
│ Relacja     sponsor · XTB         Oznaczenie  ✓ „📢Partnerem odcinka jest XTB” (opis)
│ Zakres      opis ✓ · mowa ✗ · obraz ✗
```

### Telefon 390, wariant B (dwa ekrany)

```
┌──────────────────────────────────────┐   ┌──────────────────────────────────────┐
│ InvestWatch                ● Na żywo │   │ ← Wróć do listy        Dowód Decyzja │  ← przyklejony pasek
│ [Co wymaga spr. 1][Rejestr 18][M2 3]→│   │ M1 · Nowa · YouTube · 19 lis 2026    │
│ Skan na żywo · 21 lis 17:20 · częśc. │   │ ARABIA SZYKUJE SIĘ NA WOJNĘ DO 2027. │
│ [Filtry (0) ▾]                       │   │ A ropa mimo to tanieje               │
├──────────────────────────────────────┤   │ Comparic Rynki          Oryginał ↗   │
│ ARABIA SZYKUJE SIĘ NA WOJNĘ DO       │   │ Dlaczego tutaj                       │
│ 2027. A ropa mimo to tanieje       › │   │ Zachęta z linkiem partnerskim i      │
│ Comparic Rynki · YouTube             │   │ kodem, bez oznaczenia reklamy.       │
│ Link partnerski i kod bez oznaczenia │   │ Wymóg: M1 · oznaczenie reklamy       │
│ mocna · 78/100                       │   │ Siła 78/100 (nie prawdopodobieństwo) │
└──────────────────────────────────────┘   │ Dowód                                │
                                           │ „…Kod „COMPARIC” przy rejestracji…”  │
                                           │ [Opis w YouTube ↗]                   │
                                           │ Zakres: opis ✓ mowa ✗ obraz ✗        │
                                           │ Decyzja ▾ …                          │
                                           └──────────────────────────────────────┘
```

## 3. Stany szczególne na rzeczywistych rekordach

```
Długi tytuł (2 linie, podpowiedź z pełnym tekstem):
  @podrozewojownika o przygodach z Bitcoinami i nieruchomościach w Tajlandii Nieruchomości w Tajl…
  Trade Wars · TikTok
Długa nazwa kanału (1 linia):
  Finanse Bardzo Osobiste: oszczędzanie | inwestowanie | pieni…
Starsze dane (wiersz w „Niepełne dane”):
  ITR DROŻSZY W EUROPIE · Comparic Rynki        [Do ponownego przeliczenia]  wynik z reguł 1.2; bieżące 1.3
Brak treści:
  #92 | Mój portfel 2026 - sukcesy i porażki    Brak podstaw do wyliczenia: opis niedostępny, mowa niezbadana
M3 uprawniony podmiot:
  DM BOŚ · portfel rekomendowany   [podmiot uprawniony – kontrola zakresu]  wpis KNF ID 8353437 z 21 XI
Syntetyczny (tylko w „Materiały demonstracyjne”):
  Jak działa konto inwestycyjne?  [syntetyczny · studio zespołu]  mowa 0:04,35–0:07,26 „partnerem programu jest firma aurora”
Źródło z awarią:
  Odkrywanie profilu · https://www.youtube.com/@… [kontrakt: target]  ● Błąd HTTP 302 – przekierowanie do strony zgody · 21 lis 17:20 · Ponów
```

## 4. Komponenty Astryx (sprawdzone przez `npx --no-install astryx`, v0.7.17)

| Element | Wariant A | Wariant B |
|---|---|---|
| Rama i nawigacja | `AppShell`, `TopNav`, `TopNavItem` | to samo |
| Zakładki kolejek | `TabList`, `Tab` z `endContent` (licznik jako `Badge`), `overflow="auto"` | to samo |
| Lista | `Table` z pluginem `useTableRowExpansion` (`renderExpanded`), na telefonie `List` z `Item` (`labelLines`, `descriptionLines`) i `Collapsible` | szablon `table-inbox`: `Layout`, `LayoutContent`, `LayoutPanel`, `ResizeHandle`, `useResizable`, `Table`; na telefonie `List` z `Item` |
| Szczegół | szablon `detail-page`, `MetadataList`, `Section`, `Heading`, `Text` | `LayoutPanel` z `MetadataList`, `Section`, `TabList` (Dowody / Decyzja / Historia) |
| Stany | `Skeleton`, `EmptyState`, `Banner`, `StatusDot`, `Token` | to samo |
| Filtry i decyzja | `TextInput`, `Selector`, `DateInput`, `Collapsible`, `TextArea`, `Button` | to samo |
| Opcjonalnie | `Drawer` (inspektor zamiast osobnego widoku, `experimental.isFullWidthOnMobile`) | brak |
