# web/

Pulpit analityka. Bieżący: React 19 + Astryx w `src/desk`, budowany esbuildem do `theme-preview/` (poza Gitem). Starszy: `legacy.html` + `app.js`. Zasady komponentów Astryx: [AGENTS.md](AGENTS.md) (`GEMINI.md` tylko je importuje).

| Plik `src/desk/` | Odpowiedzialność |
|---|---|
| `main.jsx` | wejście: motyw, i18n pl-PL, render `Desk` |
| `Desk.jsx` | AppShell, zakładki, układ lista + karta, start skanu |
| `route.js` | stan widoku w `#`: 4 zakładki, filtry, przekierowania starych adresów |
| `store.js` | hooki danych: overview, kolejki, karta, liczniki, WebSocket |
| `api.js` | jedyny klient `/v1` (schemat 2), adres raportu, WebSocket z ponawianiem |
| `model.js` | normalizacja sprawy, wiersza i stanu z kontraktu v2 |
| `filters.js`, `labels.js` | filtry listy; polskie etykiety i formaty |
| `Lists.jsx` | wiersze kolejki, filtry, rejestr reklam, „Pokaż więcej” |
| `CaseDetail.jsx` | szablon karty M1/M2/M3: Droga dowodu, Dlaczego tutaj, Dowód, Decyzja, Więcej |
| `CardM2.jsx`, `CardM3.jsx` | dowód i szczegóły karty M2 i M3 |
| `ProofPath.jsx` | „Droga dowodu” z `proofPath[]` |
| `cardparts.jsx`, `parts.jsx`, `decision.js` | wybór działania, edytowalny szkic, wspólne elementy kart i tokeny |
| `Calibration.jsx`, `charts.jsx` | suwak progu, FP/FN, macierz 2×2; wykresy Chart.js |
| `Sources.jsx` | platformy, drogi odczytu, ostatni skan, modele, twórcy, „Dodaj materiał” |
| `EvidenceForm.jsx`, `MetaImport.jsx` | upload nagrania; import zapisanej strony Meta |

Pozostałe pliki:

- `index.html`: serwowany pod `/`, ładuje `/theme-preview/preview.js`; przy błędzie przechodzi do `/legacy.html`.
- `src/preview.js`, `src/preview.html`, `src/astryx-themes.js`, `build-preview.mjs`: wejście, szablon i motyw kompilacji do `theme-preview/`.
- Starszy pulpit: `legacy.html`, `boot.js`, `app.js`, `style.css`, `vendor/` (React UMD). Czyta schemat 1 API.
- `dev-server.mjs`: serwer bez backendu, odpowiada kształtami z `sample/export.json`; `node web/dev-server.mjs [--port 18790] [--legacy]`.
- `sample/`: `build_sample.py` pobiera eksport działającego API do `export.json`, miniatury kadrów i zrzutów M2.

Serwowanie: w Compose nginx ([ops/web/nginx.conf](../ops/web/nginx.conf)) podaje `web/` statycznie, blokuje `src/`, `sample/`, `*.mjs`, `*.md`, proxy `/v1`, `/uploads`, `/evidence`, `/media` do API. Lokalnie `web/` serwuje API (zob. [api/README.md](../api/README.md)).

Dane: `/v1/overview` (fallback `/v1/state?compact=1`), `/v1/queues/{name}`, `/v1/cases/{id}` (+ `/versions`, `PATCH`), `/v1/scans`, `/v1/trend`, `/v1/threshold`, `/v1/qualification`, `/v1/calibration`, `/v1/report`, `POST /v1/media`, `POST /v1/import/meta`, `WS /v1/events`.

Budowa i testy:

- `npm run build` w `web/` (`node build-preview.mjs`); start lokalny robi to przez [ops/demo/prepare-preview.sh](../ops/demo/prepare-preview.sh) (Node ≥ 22.13, `npm --offline`).
- `node tests/ui/render-smoke.cjs` z katalogu głównego: render starego pulpitu i SSR `src/desk` na `sample/export.json`, bez przeglądarki.
- [tests/ui/](../tests/ui/) Playwright/Chromium: `desk-flow.py --base URL` (desktop, telefon, błędy i zapisy na osobnej kopii bazy), `film-walk.py --base URL` (scenariusz prezentacji), `workflow-flow.py --base URL` (decyzje i etapy; zapisuje w kopii). Starsze scenariusze zachowano jako `*-legacy.py`; sprawdzają poprzedni układ. `node tests/ui/queue-cache.mjs` sprawdza unieważnienie pamięci kolejki.
