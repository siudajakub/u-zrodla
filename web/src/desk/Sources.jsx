import React, { useEffect, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Card } from "@astryxdesign/core/Card";
import { Grid } from "@astryxdesign/core/Grid";
import { Button } from "@astryxdesign/core/Button";
import { Heading, Text } from "@astryxdesign/core/Text";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { Token } from "@astryxdesign/core/Token";
import { ToggleButton } from "@astryxdesign/core/ToggleButton";
import { api } from "./api.js";
import { EMPTY_FILTERS } from "./filters.js";
import { EvidenceForm } from "./EvidenceForm.jsx";
import { PLATFORM_LABEL, SCAN_MODE, SCAN_STATUS, SOURCE_STATE, describeDiscovery, fmtDateTime, fmtDay, fmtDayRoman, fmtInt, fmtTime } from "./labels.js";
import { Chart } from "./charts.jsx";
import { MetaImport } from "./MetaImport.jsx";
import { ExternalLink, reachText } from "./parts.jsx";
import { dataScanOf, lastScanOf } from "./model.js";

const ERROR_HINT = { "HTTP 302": "przekierowanie do strony zgody", "HTTP 429": "limit zapytań serwisu", "HTTP 403": "dostęp odrzucony" };
const RANK = { error: 0, unavailable: 0, limit: 1, needs_key: 1, partial: 2, candidate: 3, stale: 4, empty: 5, ok: 6 };

export const isActive = (scan) => scan && (scan.status === "queued" || scan.status === "running");

/** Powód częściowego skanu po ludzku, z ostrzeżeń skanu. */
export function partialReason(scan) {
  const warnings = [...new Set(scan?.warnings || [])];
  if (!warnings.length) return scan?.sources?.partial || scan?.sources?.failed ? `${(scan.sources.partial || 0) + (scan.sources.failed || 0)} źródeł z problemem` : null;
  return warnings.map((w) => {
    if (/429|quota|kwot|limit/i.test(w)) return "wyczerpany limit zapytań serwisu";
    if (/key|klucz/i.test(w)) return "brak klucza dostępu";
    if (/302/.test(w)) return "przekierowanie do strony zgody";
    if (/timeout|czas/i.test(w)) return "przekroczony czas odpowiedzi";
    return w;
  }).filter((x, i, arr) => arr.indexOf(x) === i).join("; ");
}

/** Jedna linia skanu, z którego pochodzą materiały: tryb, data, stan, liczba materiałów, powód stanu częściowego. */
export function scanLine(scan) {
  if (!scan) return "Nie uruchomiono jeszcze skanu.";
  const mode = scan.mode === "replay" ? `odtworzenie skanu z ${fmtDayRoman(scan.createdAt)}` : `${SCAN_MODE[scan.mode] || scan.mode}, ${fmtDateTime(scan.createdAt)}`;
  const partial = scan.status === "partial" || scan.sources?.partial || scan.sources?.failed ? `częściowy: ${partialReason(scan) || "część źródeł nie odpowiedziała"}` : SCAN_STATUS[scan.status] || scan.status;
  return [`Skan: ${mode}`, partial, scan.captures != null ? `${scan.captures} materiałów` : null, scan.newCreators ? `${scan.newCreators} nowych twórców` : null].filter(Boolean).join(" · ");
}

function Meta({ label, children }) {
  return <MetadataListItem label={label}>{children}</MetadataListItem>;
}

export function useScanProgress(scan) {
  const [detail, setDetail] = useState(null);
  const id = isActive(scan) ? scan.id : null;
  useEffect(() => {
    if (!id) {
      setDetail(null);
      return undefined;
    }
    let stop = false;
    const tick = async () => {
      try {
        const d = await api.scan(id);
        if (!stop) setDetail(d);
      } catch {
        /* postęp jest opcjonalny */
      }
    };
    tick();
    const t = setInterval(tick, 1500);
    return () => {
      stop = true;
      clearInterval(t);
    };
  }, [id]);
  return detail;
}

export function ScanBanner({ scan, detail }) {
  if (!isActive(scan)) return null;
  const p = detail?.progress || scan.progress;
  return (
    <Banner status="info" title={`W toku: ${SCAN_MODE[scan.mode] || "skan"}, od ${fmtDateTime(scan.createdAt)}${p ? ` · przejrzano ${p.done} z ${p.total} źródeł` : ""}`}
      description="Przyciski skanu są wyłączone do zakończenia. Wyniki pojawią się w kolejce."
      endContent={p ? <ProgressBar label="Postęp skanu" isLabelHidden value={p.done} max={p.total || 1} /> : undefined} />
  );
}


const SEVERITY = { error: 0, unavailable: 0, limit: 1, needs_key: 1, access_blocked: 2, partial: 2, candidate: 3, stale: 4, empty: 5, ok: 6 };
const worst = (list) => list.reduce((a, s) => ((SEVERITY[s.status] ?? 9) < (SEVERITY[a] ?? 9) ? s.status : a), "ok");
const errorOf = (s) => s.lastError || s.health?.lastError || null;

/** Połączenie wiersza źródła z jego szczegółem zdrowia (lastAttemptAt, lastError, quota.keys). */
function withHealth(data) {
  const detail = data.sourceHealthDetail || {};
  return (data.sources || []).map((s) => {
    const key = s.id || s.name;
    return { ...s, key, status: s.status in SOURCE_STATE ? s.status : "ok", health: detail[key] || null };
  });
}

const ok = (n, one, few, many) => `${n} ${n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many}`;

/** Definicje kafelków platform: które wiersze źródeł do nich należą i co o nich powiedzieć po ludzku. */
function platformTiles(data, sources, counts, totals) {
  const creators = data.creatorCounts?.byPlatform || {};
  const pick = (test) => sources.filter((s) => test(s.key));
  const yt = pick((k) => k === "youtube" || k.startsWith("youtube"));
  const tt = pick((k) => k.startsWith("tiktok"));
  const ig = pick((k) => k === "instagram" || k === "instagram-ads");
  const fb = pick((k) => k === "facebook" || k === "facebook-ads");
  const m2 = pick((k) => k.startsWith("m2:") || k.startsWith("m2-market:"));
  const m3 = pick((k) => k.startsWith("m3"));
  const meta = pick((k) => k === "meta_ads");
  const sum = (list) => list.reduce((n, s) => n + (s.count || 0), 0);
  const dataScan = dataScanOf(data);
  const lastOk = (list) => list.map((s) => s.lastSuccessAt).filter(Boolean).sort().pop() || null;
  const PATH_LABEL = { vendor_sample: "próbka z usługi zewnętrznej", manual_import: "import ręczny", ad_library_api: "API Biblioteki Reklam", organic_posts: "wpisy automatycznie" };
  const latest = (list, field) => list.map((s) => s[field]).filter(Boolean).sort().pop() || null;
  const web = [...(data.creatorMap?.values?.() || [])].filter((x) => x.platform === "web");
  const m2Firms = web.filter((x) => !String(x.id).endsWith(":m3")).length;
  const PATH_RANK = { ok: 0, partial: 1, needs_key: 2, access_blocked: 3 };
  /** Droga z wiersza: `paths[]` z API, a dla starego wiersza jedna droga z samego wiersza. */
  const pathsOf = (s) => (s.paths?.length ? s.paths : [{ path: s.key.endsWith("-ads") ? "ad_library_api" : "organic_posts", status: s.status, detail: s.lastError?.message || s.error || s.scope || "", nextStep: s.lastError?.nextStep || null, at: s.health?.lastAttemptAt || s.checkedAt, count: s.count }]);
  const social = (list, title, id) => {
    const all = list.flatMap((s) => pathsOf(s).map((p) => ({ ...p, rowId: s.key })));
    const byPath = new Map();
    for (const p of all) {
      const cur = byPath.get(p.path);
      if (!cur || (PATH_RANK[p.status] ?? 9) < (PATH_RANK[cur.status] ?? 9) || (p.derived !== "legacy" && cur.derived === "legacy" && p.status === cur.status)) byPath.set(p.path, p);
    }
    const paths = [...byPath.values()].sort((x, y) => (PATH_RANK[x.status] ?? 9) - (PATH_RANK[y.status] ?? 9));
    const best = paths[0];
    const working = best && (best.status === "ok" || best.status === "partial");
    const summary = list.map((s) => s.pathsSummary).filter(Boolean)[0];
    const total = paths.filter((p) => p.status === "ok" || p.status === "partial").reduce((n, p) => n + (p.count || 0), 0);
    return {
      id, title, status: !best ? "needs_key" : working ? "ok" : best.status,
      state: !best ? "nie uruchomiono" : working ? (best.path === "vendor_sample" ? "próbka z usługi zewnętrznej" : best.path === "manual_import" ? "próbka z importu ręcznego" : null) : best.status === "access_blocked" ? "dostęp zablokowany" : best.status === "needs_key" ? "brak tokenu" : null,
      rows: [
        ...(summary ? [["Podsumowanie", summary]] : []),
        ["Materiały w bazie", String(totals?.[id] ?? total)],
        ...(creators[id] != null ? [["Konta w bazie", String(creators[id])]] : []),
        ["Ostatnia próba", fmtDateTime(paths.map((p) => p.at).filter(Boolean).sort().pop() || null)],
      ],
      paths: paths.map((p) => ({ ...p, label: PATH_LABEL[p.path] || p.path })),
      next: best?.nextStep || (working ? "Nic do zrobienia." : "Uruchom skan albo wgraj zapisaną stronę w sekcji „Dodaj materiał”."),
      url: list[0]?.url || list[0]?.target,
    };
  };
  const ytRow = yt.find((s) => s.key === "youtube");
  const keys = ytRow?.quota?.keys || ytRow?.health?.quota?.keys || [];
  const tiles = [
    {
      id: "youtube", title: "YouTube", status: yt.length ? worst(yt) : "empty", state: null,
      rows: [
        ["Kanały w bazie", String(creators.youtube ?? "—")],
        ["Materiały w bazie", String(totals?.youtube ?? sum(yt))],
        ...(keys.length
          ? keys.map((k, i) => [`Klucz ${i + 1} (${k.keyId})`, `${k.used} z ${k.limit} jednostek${k.exhaustedAt ? ", wyczerpany" : ""}`])
          : ytRow?.quota?.limit != null ? [["Kwota", `${ytRow.quota.used} z ${ytRow.quota.limit} jednostek${ytRow.quota.resetAt ? `, odnowienie ${fmtDateTime(ytRow.quota.resetAt)}` : ""}`]] : []),
        ["Ostatni skan", dataScan ? fmtDateTime(dataScan.createdAt) : "brak"],
      ],
      next: yt.some((s) => s.status === "limit") ? "Kwota odnowi się po resecie dobowym; drugi klucz działa dalej." : "Nic do zrobienia.",
      url: "https://www.youtube.com/",
    },
    {
      id: "tiktok", title: "TikTok", status: tt.length ? worst(tt.filter((s) => s.status !== "skipped")) : "empty", state: null,
      rows: [
        ["Profile", `${tt.length} (z odnośników w opisach YouTube)`],
        ["Materiały w bazie", String(totals?.tiktok ?? sum(tt))],
        ["Ograniczenia", "tylko podpis i zasięg odtworzeń; mowy i kadrów nie ma; data szacowana"],
        ["Ostatni sukces", lastOk(tt) ? fmtDateTime(lastOk(tt)) : "brak udanego odczytu"],
      ],
      next: tt.length ? "Transkrypcje TikToka wymagają osobnego kroku (niedostępne w tej wersji)." : "Uruchom skan, aby odkryć profile z odnośników.",
      url: "https://www.tiktok.com/",
    },
    social(ig, "Instagram", "instagram"),
    social(fb, "Facebook", "facebook"),
    {
      id: "m2", title: "Strony firm", status: m2.length ? worst(m2) : "empty", state: m2.length ? null : "brak stron",
      rows: [
        ["Firmy", String(m2Firms)],
        ["Strony", String(m2.length)],
        ["Odczytano", latest(m2, "observedAt") ? fmtDateTime(latest(m2, "observedAt")) : "brak"],
        ["Ograniczenie", m2[0]?.scope || "render strony z odnośników strony głównej firmy"],
      ],
      next: "Nic do zrobienia.", url: m2[0]?.url || m2[0]?.target,
    },
    {
      id: "m3", title: "Strony doradców", status: m3.length ? worst(m3) : "empty", state: m3.length ? null : "próbka",
      rows: [
        ["Podmioty", String(m3.reduce((n, s) => n + (s.count || 0), 0) || counts.offersM3 || 0)],
        ["Strony odczytane", m3.some((s) => s.pages != null) ? String(m3.reduce((n, s) => n + (s.pages || 0), 0)) : "—"],
        ["Odczytano", latest(m3, "observedAt") ? fmtDateTime(latest(m3, "observedAt")) : "brak"],
        ["Ograniczenie", m3.map((s) => s.message).filter(Boolean)[0] || "odczyt z listy ziaren; bez własnej wyszukiwarki"],
        ["Model typu materiału", data.semantic?.status === "unavailable" ? "wyłączony: ocena działa tylko regułami" : "dostępny"],
      ],
      next: m3.length ? "Dopisz domeny do listy startowej albo podłącz wyszukiwarkę z kluczem." : "Uruchom skan.", 
    },
    (() => {
      const s = meta[0];
      const err = s && errorOf(s);
      return {
        id: "meta", title: "Biblioteka Reklam Meta", status: s ? worst(meta) : "needs_key", state: s ? null : "brak tokenu",
        rows: [
          ["Zakres", "reklamy firm na Facebooku i Instagramie, zasięg w UE"],
          ["Ostatnia próba", s ? fmtDateTime(s.health?.lastAttemptAt || s.checkedAt || s.observedAt) : "nie uruchomiono w tym skanie"],
          ["Materiały", s ? String(sum(meta)) : "0"],
          ["Import ręczny", "reklamy z zapisanych stron są w wierszu Facebook i w M2"],
        ],
        next: err?.nextStep?.replace(/\s*\(?(?:~|\/)[^\s)]*\)?/g, "").trim() || "Potrzebny token Ad Library API (instytucji).",
        url: "https://www.facebook.com/ads/library/",
      };
    })(),
  ];
  const WAY = { youtube: "API YouTube, napisy i kadry", tiktok: "odnośniki z opisów YouTube, sam podpis", m2: "render stron firm: komputer i telefon", m3: "odczyt zapisanych stron firm", meta: "Biblioteka Reklam Meta (API)" };
  const COUNT = ["Materiały w bazie", "Materiały", "Strony", "Podmioty"];
  const LAST = ["Ostatnia próba", "Ostatni sukces", "Odczytano", "Ostatni skan"];
  for (const t of tiles) {
    t.way = WAY[t.id] || t.paths?.filter((p) => p.status === "ok" || p.status === "partial").map((p) => p.label).join(", ") || t.paths?.[0]?.label || "—";
    t.count = t.rows.find((r) => COUNT.includes(r[0]))?.[1] ?? "—";
    t.last = t.rows.find((r) => LAST.includes(r[0]))?.[1] ?? "—";
  }
  return tiles;
}

const HEALTH = { ok: ["neutral", "Źródła w zestawieniu"], degraded: ["warning", "Część źródeł ma problem"], failed: ["error", "Żadne źródło nie działa"] };
const MODE_SHORT = { live: "na żywo", replay: "odtworzenie", recompute: "przeliczenie", enrich: "transkrypcje", upload: "plik" };

/** Materiały i skierowania w czasie: dwa osobne wykresy, każdy z własną skalą i liczbami nad słupkami (bez drugiej osi). */
export function TrendTile({ trend }) {
  const days = trend?.byDay || [];
  const scans = (trend?.byScan || []).filter((s) => s.mode !== "recompute" || s.referred);
  const perScan = days.length < 2;
  const rows = perScan ? scans : days;
  const type = perScan ? "bar" : "line";
  const labels = rows.map((r) => (perScan ? `${MODE_SHORT[r.mode] || r.mode} ${fmtTime(r.at)}` : fmtDay(r.day)));
  const materials = React.useMemo(() => ({ type, labels, valueLabels: true, datasets: [{ label: "Materiały przejrzane", data: rows.map((r) => r.captures || 0), color: "blue" }], yTitle: "materiały" }), [trend]);
  const referrals = React.useMemo(() => ({ type: "bar", labels, valueLabels: true, datasets: [{ label: "Skierowania do sprawdzenia", data: rows.map((r) => r.referred || 0), color: "orange" }], yTitle: "skierowania" }), [trend]);
  if (!rows.length) return <EmptyState isCompact title="Brak danych o skanach" description="Wykres pojawi się po pierwszym skanie." />;
  const part = (r) => `${perScan ? `${MODE_SHORT[r.mode] || r.mode} ${fmtTime(r.at)}` : fmtDay(r.day)}`;
  return (
    <VStack gap={1.5}>
      <Grid columns={{ minWidth: 300, max: 2 }} gap={3}>
        <VStack gap={1}>
          <Text weight="semibold">Materiały przejrzane</Text>
          <Chart spec={materials} label={`Wykres: materiały przejrzane w czasie. ${rows.map((r) => `${part(r)}: ${r.captures}`).join("; ")}`} height={150} />
        </VStack>
        <VStack gap={1}>
          <Text weight="semibold">Skierowania do sprawdzenia</Text>
          <Chart spec={referrals} label={`Wykres: skierowania do sprawdzenia w czasie. ${rows.map((r) => `${part(r)}: ${r.referredKnown === false ? "?" : r.referred || 0}`).join("; ")}`} height={150} />
        </VStack>
      </Grid>
      <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Dane wykresu (tabela)</Text>}>
        <Table idKey="k" density="compact" data={rows.map((r, i) => ({ k: i, ...r }))} columns={[
          { key: "when", header: perScan ? "Skan" : "Dzień", width: proportional(2, { minWidth: 120 }), renderCell: (r) => <Text>{perScan ? `${MODE_SHORT[r.mode] || r.mode}, ${fmtDateTime(r.at)}` : fmtDay(r.day)}</Text> },
          { key: "captures", header: "Materiały", align: "end", width: pixel(96), renderCell: (r) => r.captures },
          { key: "referred", header: "Skierowania", align: "end", width: pixel(104), renderCell: (r) => (r.referredKnown === false ? "?" : r.referred || 0) },
          { key: "new", header: perScan ? "Nowi twórcy" : "Nowe materiały", align: "end", width: pixel(120), renderCell: (r) => (perScan ? r.newCreators : r.newMaterials) ?? "—" },
        ]} />
      </Collapsible>
    </VStack>
  );
}

const PLATFORM_ORDER = ["youtube", "tiktok", "instagram", "facebook", "web"];

/** Liczba materiałów per platforma z kolejki „wszystkie” (limit=1, ważna jest liczność). */
function usePlatformTotals(rev) {
  const [totals, setTotals] = useState(null);
  useEffect(() => {
    let off = false;
    Promise.all(PLATFORM_ORDER.map((p) => api.queue("all", { source: p }, { limit: 1 }).then((r) => [p, r.total]))).then((pairs) => {
      if (off) return;
      const t = {};
      for (const [p, n] of pairs) t[p] = (t[p] || 0) + n;
      setTotals(t);
    }, () => !off && setTotals(null));
    return () => {
      off = true;
    };
  }, [rev]);
  return totals;
}

function stepRows(detail) {
  return (detail?.steps || []).map((x) => ({ ...x, label: x.name || x.sourceId || x.id }));
}

const STEP_STATE = { done: "zakończony", running: "w toku", queued: "w kolejce", failed: "błąd", skipped: "pominięty" };

/** Jedna tabela platform: stan, droga odczytu, materiały, ostatni odczyt, następny krok; wiersz rozwija drogi odczytu i kwoty. */
/** Następny krok bez adresów tras API i ścieżek plików. */
const plainStep = (text) => String(text || "—").replace(/\s*\([^)]*(?:\/v1\/|\/home\/|~\/|docs\/)[^)]*\)/g, "").replace(/\s+/g, " ").trim();

function PlatformsTable({ tiles, narrow }) {
  const [open, setOpen] = useState(null);
  const current = tiles.find((t) => t.id === open);
  const stateOf = (t) => {
    const [variant, label] = SOURCE_STATE[t.status] || ["neutral", t.status];
    return { variant, text: t.state || label };
  };
  if (narrow) {
    return (
      <List density="spacious" hasDividers aria-label="Platformy i drogi odczytu">
        {tiles.map((t) => {
          const s = stateOf(t);
          return (
            <Item key={t.id} density="spacious" label={t.title} labelLines={1} descriptionLines={5}
              endContent={<HStack gap={1} vAlign="center"><StatusDot variant={s.variant} label={s.text} /><Text type="supporting">{s.text}</Text></HStack>}
              description={<VStack gap={0.5}>
                <Text type="supporting" color="secondary">{t.way} · materiały {t.count} · ostatni odczyt {t.last}</Text>
                <Text type="supporting" color="secondary">Następny krok: {plainStep(t.next)}</Text>
              </VStack>} />
          );
        })}
      </List>
    );
  }
  return (
    <VStack gap={1.5}>
      <Table idKey="id" density="compact" verticalAlign="top" data={tiles} aria-label="Platformy i drogi odczytu" columns={[
        { key: "p", header: "Platforma", width: proportional(2, { minWidth: 120 }), renderCell: (t) => <Text weight="semibold">{t.title}</Text> },
        { key: "s", header: "Stan", width: proportional(2, { minWidth: 120 }), renderCell: (t) => { const s = stateOf(t); return <HStack gap={1} vAlign="center"><StatusDot variant={s.variant} label={s.text} /><Text type="supporting">{s.text}</Text></HStack>; } },
        { key: "w", header: "Droga odczytu", width: proportional(3, { minWidth: 150 }), renderCell: (t) => <Text type="supporting" maxLines={2}>{t.way}</Text> },
        { key: "c", header: "Materiały", align: "end", width: pixel(92), renderCell: (t) => <Text type="supporting" hasTabularNumbers>{t.count}</Text> },
        { key: "l", header: "Ostatni odczyt", width: proportional(2, { minWidth: 120 }), renderCell: (t) => <Text type="supporting" maxLines={2}>{t.last}</Text> },
        { key: "n", header: "Następny krok", width: proportional(4, { minWidth: 170 }), renderCell: (t) => <Text type="supporting" color="secondary" maxLines={2}>{plainStep(t.next)}</Text> },
        { key: "d", header: "", width: pixel(96), renderCell: (t) => <Button label={open === t.id ? "Zwiń drogi" : "Drogi"} size="sm" variant="ghost" aria-expanded={open === t.id} onClick={() => setOpen(open === t.id ? null : t.id)} /> },
      ]} />
      {current && (
        <Card padding={2} aria-label={`Drogi odczytu: ${current.title}`}>
          <VStack gap={1.5}>
            <Heading level={3}>Drogi odczytu: {current.title}</Heading>
            <MetadataList>{current.rows.map(([k, v]) => <Meta key={k} label={k}>{v}</Meta>)}</MetadataList>
            {current.paths?.length > 0 && (
              <Table idKey="path" density="compact" verticalAlign="top" data={current.paths} columns={[
                { key: "p", header: "Droga", width: proportional(3, { minWidth: 130 }), renderCell: (p) => <Text weight="medium">{p.label}</Text> },
                { key: "s", header: "Stan", width: proportional(2, { minWidth: 90 }), renderCell: (p) => <Text type="supporting">{(SOURCE_STATE[p.status] || [0, p.status])[1]}{p.count ? ` (${p.count})` : ""}</Text> },
                { key: "d", header: "Szczegół", width: proportional(3, { minWidth: 120 }), renderCell: (p) => <Text type="supporting" color="secondary" maxLines={3}>{p.detail || "—"}</Text> },
                { key: "n", header: "Następny krok", width: proportional(3, { minWidth: 120 }), renderCell: (p) => <Text type="supporting" color="secondary" maxLines={3}>{plainStep(p.nextStep)}</Text> },
              ]} />
            )}
            {current.url && <ExternalLink url={current.url}>Otwórz źródło ↗</ExternalLink>}
          </VStack>
        </Card>
      )}
    </VStack>
  );
}

const fmtMeasured = (m) => (m && m.n != null ? `${m.ready} z ${m.n} odpowiedzi przyjętych, ${m.rejected} odrzucona (cytat nie przeszedł walidacji)` : null);

/** Modele AI: klasyfikator typu materiału i drugi głos, z licencją, wymaganiami, trybem i zmierzonymi wynikami (pole `models` z API). */
function ModelsTile({ models }) {
  if (!models) return null;
  const e5 = models.materialType;
  const so = models.secondOpinion;
  const e5m = e5?.measured;
  const rows = [
    e5 && {
      id: "e5", name: "Klasyfikator typu materiału", model: e5.name, license: "Apache-2.0", needs: "działa na procesorze, bez karty graficznej",
      mode: `${e5.status === "unavailable" || e5.annotation === "off" ? "wyłączony w tej bazie" : "lokalnie"}; tylko opis, nie wpływa na decyzję`,
      measured: e5m && e5m.n ? `${e5m.correct} z ${e5m.n} trafnie na zbiorze odłożonym (słownik reguł: ${Math.round((e5m.keywordRulesAccuracy || 0) * e5m.n)} z ${e5m.n})` : "—",
    },
    so && {
      id: "so", name: "Drugi głos modelu", model: so.name || "—", license: so.weightsLicense || "—",
      needs: so.localMemoryGb ? `ok. ${so.localMemoryGb} GB pamięci` : "—",
      mode: so.modeLabel || so.mode,
      measured: [
        so.measuredModel && `Eksperyment API · ${so.measuredModel}`,
        so.measured?.M1 && `M1: ${fmtMeasured(so.measured.M1)}`,
        so.measured?.M3 && `M3: ${fmtMeasured(so.measured.M3)}`,
        so.labels,
      ].filter(Boolean).join(" · ") || "—",
    },
  ].filter(Boolean);
  return (
    <VStack gap={1.5}>
      <Heading level={2}>Modele</Heading>
      <Table idKey="id" density="compact" verticalAlign="top" data={rows} aria-label="Modele AI" columns={[
        { key: "n", header: "Zadanie", width: proportional(2, { minWidth: 120 }), renderCell: (r) => <Text weight="semibold">{r.name}</Text> },
        { key: "m", header: "Model", width: proportional(2, { minWidth: 120 }), renderCell: (r) => <Text type="supporting">{r.model}</Text> },
        { key: "l", header: "Licencja", width: pixel(100), renderCell: (r) => <Text type="supporting">{r.license}</Text> },
        { key: "r", header: "Wymagania", width: proportional(2, { minWidth: 130 }), renderCell: (r) => <Text type="supporting" maxLines={3}>{r.needs}</Text> },
        { key: "t", header: "Tryb", width: proportional(3, { minWidth: 150 }), renderCell: (r) => <Text type="supporting" maxLines={3}>{r.mode}</Text> },
        { key: "z", header: "Zmierzone", width: proportional(4, { minWidth: 180 }), renderCell: (r) => <Text type="supporting" maxLines={4}>{r.measured}</Text> },
      ]} />
    </VStack>
  );
}

export function Sources({ data, busy, scanning, onScan, rev, onRefresh, openAdd, go, narrow }) {
  const scan = lastScanOf(data);
  const dataScan = dataScanOf(data);
  const sources = withHealth(data);
  const counts = data.counts || {};
  const totals = usePlatformTotals(rev);
  const tiles = platformTiles(data, sources, counts, totals);
  const creators = [...data.creatorMap.values()];
  const [allCreators, setAllCreators] = useState(false);
  const [newOnly, setNewOnly] = useState(false);
  const [addOpen, setAddOpen] = useState(!!openAdd);
  useEffect(() => { if (openAdd) setAddOpen(true); }, [openAdd]);
  const detail = useScanProgress(scan);
  const [lastSteps, setLastSteps] = useState(null);
  useEffect(() => {
    if (!dataScan?.id) return undefined;
    let off = false;
    api.scan(dataScan.id).then((d) => !off && setLastSteps(d), () => !off && setLastSteps(null));
    return () => {
      off = true;
    };
  }, [dataScan?.id, scan?.status]);
  const summary = data.sourceHealthSummary;
  const [hv, hl] = HEALTH[summary?.status] || ["neutral", "Stan źródeł nieznany"];
  const disabled = busy || scanning;
  const why = scanning ? "Skan w toku." : undefined;
  const filtered = newOnly ? creators.filter((c) => c.isNewInScan) : creators;
  const shown = allCreators ? filtered : filtered.slice(0, 25);
  const active = scanning ? detail : lastSteps;
  const steps = stepRows(active);
  const progress = (scanning ? detail?.progress || scan?.progress : null) || null;
  const mode = dataScan ? (dataScan.mode === "replay" ? `odtworzenie skanu z ${fmtDayRoman(dataScan.createdAt)}` : `${SCAN_MODE[dataScan.mode] || dataScan.mode}, ${fmtDateTime(dataScan.createdAt)}`) : null;
  const sourcesLine = dataScan?.sources ? `${dataScan.sources.ok + (dataScan.sources.empty || 0)} z ${dataScan.sources.ok + (dataScan.sources.empty || 0) + (dataScan.sources.partial || 0) + (dataScan.sources.failed || 0) + (dataScan.sources.accessBlocked || 0)} źródeł działa${dataScan.sources.accessBlocked ? `, ${dataScan.sources.accessBlocked} z zablokowanym dostępem` : ""}` : null;
  const lastScanLine = mode ? ["Ostatni skan", mode, dataScan.captures != null ? `${fmtInt(dataScan.captures)} materiałów` : null, sourcesLine,].filter(Boolean).join(" · ") : "Nie uruchomiono jeszcze skanu.";
  return (
    <VStack gap={3} padding={3}>
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Heading level={1}>Źródła</Heading>
        {summary && <HStack gap={1} vAlign="center"><StatusDot variant={hv} label={hl} /><Text type="supporting">{hl}{summary.problems ? ` (${summary.problems} z ${summary.total})` : ` (${summary.total})`}</Text></HStack>}
      </HStack>
      <ScanBanner scan={scan} detail={detail} />
      <VStack gap={1.5}>
        <Text data-testid="scan-line">{lastScanLine}</Text>
        <HStack gap={2} wrap="wrap" vAlign="center">
          <Button label="Skanuj na żywo" variant="primary" isDisabled={disabled} tooltip={why} onClick={() => onScan("live")} />
          <Button label="Przelicz materiały" isDisabled={disabled} tooltip={why} onClick={() => onScan("recompute")} />
        </HStack>
        {progress && <ProgressBar label="Postęp skanu" value={progress.done} max={progress.total || 1} />}
      </VStack>
      <Collapsible defaultIsOpen={false} trigger={<Text weight="semibold">Materiały i skierowania w czasie</Text>}><TrendTile trend={data.trend} /></Collapsible>
      <VStack gap={1.5}>
        <Heading level={2}>Platformy</Heading>
        <PlatformsTable tiles={tiles} narrow={narrow} />
      </VStack>
      <ModelsTile models={data.models} />
      <Collapsible isOpen={addOpen} onOpenChange={setAddOpen} trigger={<Heading level={2}>Dodaj materiał</Heading>}>
        <Grid columns={{ minWidth: 340, max: 2 }} gap={3} padding={2}>
          <Card padding={3} data-section="add-file"><EvidenceForm onDone={onRefresh} onOpenDemo={() => go?.("review", { filters: { ...EMPTY_FILTERS, state: "demo" } })} /></Card>
          <Card padding={3} data-section="meta-import"><MetaImport onDone={() => [500, 2500, 6000].forEach((ms) => setTimeout(onRefresh, ms))} /></Card>
        </Grid>
      </Collapsible>
      {steps.length > 0 && (
        <Collapsible defaultIsOpen={scanning} trigger={<Text type="supporting">Kroki ostatniego skanu ({steps.filter((s) => s.status === "done" || s.status === "skipped").length} z {steps.length})</Text>}>
          <Table idKey="id" density="compact" data={steps} columns={[
            { key: "name", header: "Krok skanu", width: proportional(3, { minWidth: 140 }), renderCell: (x) => x.label },
            { key: "status", header: "Stan", width: pixel(110), renderCell: (x) => <Text type="supporting">{STEP_STATE[x.status] || x.status}</Text> },
          ]} />
        </Collapsible>
      )}
      <VStack gap={1.5}>
        <HStack gap={2} vAlign="center" wrap="wrap">
          <Heading level={2}>Twórcy i droga odkrycia ({data.creatorCounts?.total ?? creators.length})</Heading>
          <ToggleButton size="sm" label="nowi w skanie" isPressed={newOnly} onPressedChange={setNewOnly}>nowi w skanie</ToggleButton>
        </HStack>
        <Table idKey="id" data={shown} density="compact" verticalAlign="top" emptyState={<EmptyState isCompact title="Brak odkrytych twórców" />} columns={[
          { key: "name", header: "Twórca", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
            <VStack gap={0.5}>
              <HStack gap={1} wrap="wrap" vAlign="center">
                <Text weight="semibold" maxLines={1}>{c.name}</Text>
                <Token size="sm" color="gray" label={PLATFORM_LABEL[c.platform] || c.platform || "?"} />
                {c.isNewInScan && <Token size="sm" color="green" label="nowy" />}
                {(c.seed || c.isSeed || c.status === "seed") && <Token size="sm" color="gray" label="monitorowany" />}
              </HStack>
              <ExternalLink url={c.url}>Profil ↗</ExternalLink>
            </VStack>
          ) },
          { key: "via", header: "Jak odkryto", width: proportional(4, { minWidth: 200 }), renderCell: (c) => {
            const lines = c.discoveries.length ? c.discoveries.map(describeDiscovery) : [c.discoveredVia ? `${c.discoveredVia}` : "—"];
            return <VStack gap={0.5}>{lines.slice(0, 2).map((l, i) => <Text key={i} type="supporting" maxLines={1}>{l}</Text>)}</VStack>;
          } },
          { key: "reach", header: "Zasięg", width: proportional(2, { minWidth: 130 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{c.reach ? reachText(c.reach) : "—"}</Text> },
        ]} />
        {filtered.length > 25 && <HStack hAlign="center"><Button label={allCreators ? "Pokaż mniej" : `Pokaż wszystkich (${filtered.length})`} onClick={() => setAllCreators((v) => !v)} /></HStack>}
      </VStack>
    </VStack>
  );
}
