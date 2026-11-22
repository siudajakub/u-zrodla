# Kolektory materiałów

Kolektory odkrywają publiczne źródła, pobierają materiały i zapisują je jako rekordy Capture. Każdy rekord łączy materiał z adresem i pochodzeniem. Odtwarzanie korzysta z wcześniej zapisanych odpowiedzi. [Pokrycie platform](../docs/MONITORING.md) · [Analiza](../analysis/README.md)

| Plik | Odpowiedzialność | Główne wejścia | Testy |
|---|---|---|---|
| `adapter.py` | Kontrakt adaptera v2: wynik, limity dzienne, stan źródła, ścieżki odczytu | `Adapter`, `AdapterContext`, `execute`, `MemoryRunner`, `validate_adapter_result` | `test_meta_*`, `test_social`, `test_vendor_social`, `tests/core/test_contract_v2_*` |
| `discovery.py` | Rejestr adapterów (`ADAPTERS`), skan live/replay, scalanie Capture | `discover`, `planned_steps`, `m3_domain`; CLI `live\|replay` | `test_discovery` |
| `common.py` | Walidacja publicznego URL, pobieranie bez przekierowań, proxy, User-Agent, pola Capture | `safe_get`, `open_url`, `public_link`, `capture`, `digest` | `test_common` |
| `youtube.py` | YouTube Data API v3 + Atom, baza kanałów, klucze, budżet jednostek | `discover`, `replay`, `detect_language`; CLI | `test_youtube` |
| `media.py` | Napisy, kadry i ASR filmu YouTube (yt-dlp, Vosk) | `enrich`, `captions`; CLI `VIDEO [--frames] [--asr]` | `test_media` |
| `audio.py` | Ograniczony prefiks MP3 podcastu do transkrypcji | `fetch_excerpt`, `provider_for` | `test_discovery` |
| `catalogs.py` | Apple Podcasts, RSS, PeerTube, ziarna M3 | `read_podcast`, `read_apple`, `read_peertube`, `load_m3_seeds` | `test_discovery`, `test_catalogs_m3` |
| `sites.py` | Strony firm o jeden link od strony głównej, oferty M3 | `read_site`, `discover_m3`, `m3_entity_captures`; CLI | `test_discovery`, `test_sites_m3` |
| `social.py` | Monitor YouTube/TikTok (odczyt bez zapisu do jego bazy), adaptery FB/IG | `read_social`, `discover_tiktok`, `make_meta_adapter`, `firm_signals` | `test_social` |
| `crosslinks.py` | Profile społecznościowe linkowane z opisów | `extend_from_posts` | `test_crosslinks` |
| `meta_ads.py` | Meta Ad Library (Graph API `ads_archive`) | `discover`, `relate` | `test_meta_ads` |
| `meta_import.py` | Import stron Meta zapisanych ręcznie przez analityka, bez sieci | `import_files`, `discover`; CLI | `test_meta_import` |
| `vendor_social.py` | IG/FB/Ad Library pobrane raz przez ScrapeCreators; replay próbki | `discover`; CLI `collect\|build` | `test_vendor_social` |
| `m2_discovery.py` | Strony ofert firm z rejestru KNF, od strony głównej | CLI `--output` | `test_m2_market` |
| `m2_capture.py`, `m2_capture.js` | Render Playwright desktop + telefon, archiwum `data/probe-snapshots/m2/market/` | CLI (playwright-python) | brak |
| `m2_market.py` | Odczyt archiwum M2 rynku jako Capture | `market_captures`, `material`, `asset` | `test_m2_market` |
| `m2_browser.py`, `m2_browser.js` | Worker Chromium dla zatwierdzonych stron M2 (`TARGETS`) | `refresh_from_worker`; CLI `NAME --output --chromium` | `test_m2_archive` |
| `m2_archive.py` | Wersjonowane zapisy M2 adresowane SHA-256 | `staged_captures`, `apply_rendered`, `asset_bytes` | `test_m2_archive` |
| `__init__.py` | Pakiet | — | — |

## Kto woła

- `api/jobs.py` (wołany przez `api/worker.py`): `discovery`, `adapter`, `m2_archive`, `m2_browser.refresh_from_worker`, `m2_market`.
- `api/store.py`: `adapter`, `discovery.ADAPTERS`, `youtube`. `api/server.py`: `common`, `m2_market`, `m2_archive`.
- `api/enrich.py`: `media`. `api/listen.py`: `audio`. `api/import_meta.py`: `meta_import`.
- `analysis/engine.py`: `youtube.detect_language`. `analysis/m2_card.py`, `analysis/m2_eval.py`: `m2_market`.
- `tools/youtube_probe.py`: `youtube`, `crosslinks`.

Zmienne: `INVESTWATCH_ADAPTERS` (lista włączonych adapterów), `INVESTWATCH_YT_KEY_FILES`, `INVESTWATCH_META_TOKEN_FILE`, `INVESTWATCH_PROXIES`, `INVESTWATCH_USER_AGENTS`.

```sh
python3 -m collectors.discovery replay                         # skan z archiwum 21 XI, bez sieci
python3 -m collectors.meta_import ŚCIEŻKA --out wynik.json     # import zapisanych stron Meta
python3 -m collectors.media VIDEO_ID                           # napisy filmu (sieć)
python3 -B -m unittest discover -s collectors -t . -p 'test_*.py'
```

Kontrakt adaptera: [docs/lanes/2026-11-21-fable-h-kontrakt.md](../docs/lanes/2026-11-21-fable-h-kontrakt.md). Źródła i limity: [docs/MONITORING.md](../docs/MONITORING.md).
