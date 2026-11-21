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
import { api } from "./api.js";
import { PLATFORM_LABEL, SCAN_MODE, SCAN_STATUS, SOURCE_STATE, describeDiscovery, fmtDateTime, fmtDay, fmtDayRoman, fmtTime } from "./labels.js";
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
function platformTiles(data, sources, counts) {
  const creators = data.creatorCounts?.byPlatform || {};
  const pick = (test) => sources.filter((s) => test(s.key));
  const yt = pick((k) => k === "youtube" || k.startsWith("youtube"));
  const tt = pick((k) => k.startsWith("tiktok"));
  const ig = pick((k) => k === "instagram" || k === "instagram-ads");
  const fb = pick((k) => k === "facebook" || k === "facebook-ads");
  const m2 = pick((k) => k.startsWith("m2:"));
  const m3 = pick((k) => k.startsWith("m3"));
  const meta = pick((k) => k === "meta_ads");
  const sum = (list) => list.reduce((n, s) => n + (s.count || 0), 0);
  const dataScan = dataScanOf(data);
  const lastOk = (list) => list.map((s) => s.lastSuccessAt).filter(Boolean).sort().pop() || null;
  const PATH_LABEL = { manual_import: "import ręczny", ad_library_api: "API Biblioteki Reklam", organic_posts: "wpisy automatycznie" };
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
      state: !best ? "nie uruchomiono" : working ? (best.path === "manual_import" ? "próbka z importu ręcznego" : null) : best.status === "access_blocked" ? "dostęp zablokowany" : best.status === "needs_key" ? "brak tokenu" : null,
      rows: [
        ...(summary ? [["Podsumowanie", summary]] : []),
        ["Materiały", String(total)],
        ["Ostatnia próba", fmtDateTime(paths.map((p) => p.at).filter(Boolean).sort().pop() || null)],
      ],
      paths: paths.map((p) => ({ ...p, label: PATH_LABEL[p.path] || p.path })),
      next: best?.nextStep || (working ? "Nic do zrobienia." : "Uruchom skan albo wgraj zapisaną stronę poniżej."),
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
        ["Materiały", String(sum(yt))],
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
        ["Materiały", String(sum(tt))],
        ["Ograniczenia", "tylko podpis i zasięg odtworzeń; mowy i kadrów nie ma; data szacowana z identyfikatora"],
        ["Ostatni sukces", lastOk(tt) ? fmtDateTime(lastOk(tt)) : "brak udanego odczytu"],
      ],
      next: tt.length ? "Transkrypcje TikToka wymagają osobnego kroku (niedostępne w tej wersji)." : "Uruchom skan, aby odkryć profile z odnośników.",
      url: "https://www.tiktok.com/",
    },
    social(ig, "Instagram", "instagram"),
    social(fb, "Facebook", "facebook"),
    {
      id: "m2", title: "WWW firm (M2)", status: m2.length ? worst(m2) : "empty", state: m2.length ? null : "brak stron",
      rows: [["Strony", String(m2.length)], ["Zrzuty ofert", String(sum(m2) || counts.offersM2 || 0)], ["Ostatni sukces", lastOk(m2) ? fmtDateTime(lastOk(m2)) : "brak"]],
      next: "Nic do zrobienia.", url: m2[0]?.url || m2[0]?.target,
    },
    {
      id: "m3", title: "WWW doradców (M3)", status: m3.length ? worst(m3) : "empty", state: m3.length ? null : "próbka",
      rows: [["Oferty w bazie", String(counts.offersM3 ?? 0)], ["Źródło", m3.length ? `${m3.length} stron` : "próbka publiczna, bez odczytu na żywo"], ["Model semantyczny", data.semantic?.status === "unavailable" ? "niedostępny: M3 działa tylko regułami" : "dostępny"]],
      next: data.semantic?.status === "unavailable" ? "Opcjonalnie: wskaż katalog modelu E5 (INVESTWATCH_SEMANTIC_DIR)." : "Nic do zrobienia.",
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
          ["Import ręczny", "reklamy z zapisanych stron są w kafelku Facebook i w ofertach M2"],
        ],
        next: err?.nextStep || "Potwierdź tożsamość w Meta, wygeneruj token użytkownika i zapisz go w ~/.config/investwatch/meta.token (kroki: docs/lanes/2026-11-21-fable-k-social.md).",
        url: "https://www.facebook.com/ads/library/",
      };
    })(),
  ];
  return tiles;
}

function PlatformTile({ t }) {
  const [variant, label] = SOURCE_STATE[t.status] || ["neutral", t.status];
  const shown = t.state || label;
  return (
    <Card padding={3} aria-label={`Źródło: ${t.title}`} data-tile={t.id}>
      <VStack gap={1.5}>
        <HStack gap={2} hAlign="between" vAlign="start">
          <Heading level={3}>{t.title}</Heading>
          <HStack gap={1} vAlign="center"><StatusDot variant={variant} label={shown} /><Text type="supporting">{shown}</Text></HStack>
        </HStack>
        <MetadataList>
          {t.rows.map(([k, v]) => <Meta key={k} label={k}>{v}</Meta>)}
          <Meta label="Następny krok">{t.next}</Meta>
        </MetadataList>
        {t.paths?.length > 0 && (
          <Table idKey="path" density="compact" verticalAlign="top" data={t.paths} columns={[
            { key: "p", header: "Droga", width: proportional(2, { minWidth: 90 }), renderCell: (p) => <Text weight="medium">{p.label}</Text> },
            { key: "s", header: "Stan", width: proportional(2, { minWidth: 90 }), renderCell: (p) => <Text type="supporting">{(SOURCE_STATE[p.status] || [0, p.status])[1]}{p.count ? ` (${p.count})` : ""}</Text> },
            { key: "d", header: "Szczegół", width: proportional(3, { minWidth: 120 }), renderCell: (p) => <Text type="supporting" color="secondary" maxLines={3}>{p.detail || "—"}</Text> },
            { key: "n", header: "Następny krok", width: proportional(3, { minWidth: 120 }), renderCell: (p) => <Text type="supporting" color="secondary" maxLines={3}>{p.nextStep || "—"}</Text> },
          ]} />
        )}
        {t.url && <ExternalLink url={t.url}>Otwórz źródło ↗</ExternalLink>}
      </VStack>
    </Card>
  );
}

const HEALTH = { ok: ["success", "Wszystkie źródła działają"], degraded: ["warning", "Część źródeł ma problem"], failed: ["error", "Żadne źródło nie działa"] };
const MODE_SHORT = { live: "na żywo", replay: "odtworzenie", recompute: "przeliczenie", enrich: "transkrypcje", upload: "plik" };

/** Materiały i skierowania w czasie: słupki per skan przy jednym dniu danych, linie per dzień przy kilku. */
export function TrendTile({ trend }) {
  const days = trend?.byDay || [];
  const scans = (trend?.byScan || []).filter((s) => s.mode !== "recompute" || s.referred);
  const perScan = days.length < 2;
  const rows = perScan ? scans : days;
  const spec = React.useMemo(() => ({
    type: perScan ? "bar" : "line",
    labels: rows.map((r) => (perScan ? `${MODE_SHORT[r.mode] || r.mode} ${fmtTime(r.at)}` : fmtDay(r.day))),
    datasets: [
      { label: "Materiały przejrzane", data: rows.map((r) => (perScan ? r.captures : r.captures) || 0), axis: "y", color: "blue" },
      { label: "Skierowania do sprawdzenia", data: rows.map((r) => r.referred || 0), axis: "y2", color: "orange" },
    ],
    yTitle: "materiały",
    y2Title: "skierowania",
  }), [trend]);
  if (!rows.length) return <EmptyState isCompact title="Brak danych o skanach" description="Wykres pojawi się po pierwszym skanie." />;
  const summary = rows.map((r) => `${perScan ? `${MODE_SHORT[r.mode] || r.mode} ${fmtTime(r.at)}` : fmtDay(r.day)}: ${r.captures} materiałów, ${r.referredKnown === false ? "?" : r.referred || 0} skierowań`).join("; ");
  return (
    <VStack gap={1.5}>
      <Chart spec={spec} label={`Wykres: materiały i skierowania w czasie. ${summary}`} height={230} />
      <Text type="supporting" color="secondary">{perScan ? "Jeden dzień danych: słupki pokazują kolejne skany." : `Dni: ${rows.length}.`} Skierowania to nowe sprawy w kolejce „Co wymaga sprawdzenia” po skanie.</Text>
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
    Promise.all([
      ...PLATFORM_ORDER.map((p) => api.queue("all", { source: p }, { limit: 1 }).then((r) => [p, r.total])),
      api.queue("offersM3", { source: "web" }, { limit: 1 }).then((r) => ["web", r.total]),
    ]).then((pairs) => {
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

function PlatformChart({ totals }) {
  const spec = React.useMemo(() => totals && ({
    type: "bar",
    labels: PLATFORM_ORDER.map((p) => PLATFORM_LABEL[p]),
    datasets: [{ label: "Materiały", data: PLATFORM_ORDER.map((p) => totals[p] || 0), color: "blue" }],
    yTitle: "materiały",
  }), [totals]);
  if (!totals) return <Text color="secondary" role="status">Liczenie materiałów…</Text>;
  const summary = PLATFORM_ORDER.map((p) => `${PLATFORM_LABEL[p]} ${totals[p] || 0}`).join(", ");
  return <Chart spec={spec} label={`Wykres: materiały per platforma. ${summary}`} height={230} />;
}

function stepRows(detail) {
  return (detail?.steps || []).map((x) => ({ ...x, label: x.name || x.sourceId || x.id }));
}

const STEP_STATE = { done: "zakończony", running: "w toku", queued: "w kolejce", failed: "błąd", skipped: "pominięty" };

export function Sources({ data, busy, scanning, onScan, rev, onRefresh }) {
  const scan = lastScanOf(data);
  const dataScan = dataScanOf(data);
  const sources = withHealth(data);
  const counts = data.counts || {};
  const tiles = platformTiles(data, sources, counts);
  const creators = [...data.creatorMap.values()];
  const [allCreators, setAllCreators] = useState(false);
  const detail = useScanProgress(scan);
  const [lastSteps, setLastSteps] = useState(null);
  const totals = usePlatformTotals(rev);
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
  const shown = allCreators ? creators : creators.slice(0, 25);
  const active = scanning ? detail : lastSteps;
  const steps = stepRows(active);
  const progress = (scanning ? detail?.progress || scan?.progress : null) || (steps.length ? { done: steps.filter((s) => s.status === "done" || s.status === "skipped").length, total: steps.length } : null);
  const blocked = dataScan?.accessBlocked || [];
  return (
    <VStack gap={4} padding={3}>
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Heading level={1}>Źródła i droga odkrycia</Heading>
        {summary && <HStack gap={1} vAlign="center"><StatusDot variant={hv} label={hl} /><Text type="supporting">{hl}{summary.problems ? ` (${summary.problems} z ${summary.total})` : ` (${summary.total})`}{summary.accessBlocked ? `, ${ok(summary.accessBlocked, "zablokowany dostęp", "zablokowane dostępy", "zablokowanych dostępów")}` : ""}</Text></HStack>}
      </HStack>
      <ScanBanner scan={scan} detail={detail} />
      <Card padding={3}>
        <VStack gap={2}>
          <Heading level={2}>Materiały i skierowania w czasie</Heading>
          <TrendTile trend={data.trend} />
        </VStack>
      </Card>
      <VStack gap={2}>
        <Heading level={2}>Platformy ({tiles.length})</Heading>
        <Grid columns={{ minWidth: 300, max: 3 }} gap={3}>{tiles.map((t) => <PlatformTile key={t.id} t={t} />)}</Grid>
      </VStack>
      <Card padding={3} data-section="meta-import"><MetaImport onDone={() => [500, 2500, 6000].forEach((ms) => setTimeout(onRefresh, ms))} /></Card>
      <Grid columns={{ minWidth: 340, max: 2 }} gap={3}>
        <Card padding={3}>
          <VStack gap={2}>
            <Heading level={2}>Źródła: materiały per platforma</Heading>
            <PlatformChart totals={totals} />
          </VStack>
        </Card>
        <Card padding={3}>
          <VStack gap={2}>
            <Heading level={2}>Skan materiałów</Heading>
            <Text>{scanLine(dataScan)}</Text>
            {dataScan && (
              <MetadataList columns="multi">
                <Meta label="Początek">{fmtDateTime(dataScan.createdAt)}</Meta>
                <Meta label="Koniec">{fmtDateTime(dataScan.updatedAt)}</Meta>
                <Meta label="Źródła">{dataScan.sources ? `${dataScan.sources.ok} działa, ${dataScan.sources.empty} bez nowych, ${dataScan.sources.partial} częściowo, ${dataScan.sources.failed} z błędem${dataScan.sources.accessBlocked ? `, ${dataScan.sources.accessBlocked} z zablokowanym dostępem` : ""}` : "—"}</Meta>
                <Meta label="Do sprawdzenia">{dataScan.referred ?? "brak danych"}</Meta>
              </MetadataList>
            )}
            {blocked.length > 0 && (
              <VStack gap={1} role="region" aria-label="Zablokowane dostępy">
                <Text weight="semibold">Zablokowane dostępy ({blocked.length})</Text>
                <List density="compact" hasDividers>
                  {blocked.map((b) => <Item key={b.id} label={b.name} labelLines={2} description={b.nextStep} descriptionLines={3} endContent={<Text type="supporting" color="secondary">próba {fmtDateTime(b.attemptedAt)}</Text>} />)}
                </List>
              </VStack>
            )}
            {progress && <ProgressBar label={scanning ? "Postęp skanu" : "Kroki ostatniego skanu"} value={progress.done} max={progress.total || 1} />}
            {steps.length > 0 && (
              <Collapsible defaultIsOpen={scanning} trigger={<Text type="supporting">Kroki skanu ({progress ? `${progress.done} z ${progress.total}` : steps.length})</Text>}>
                <Table idKey="id" density="compact" data={steps} columns={[
                  { key: "name", header: "Krok skanu", width: proportional(3, { minWidth: 140 }), renderCell: (x) => x.label },
                  { key: "status", header: "Stan", width: pixel(110), renderCell: (x) => <Text type="supporting">{STEP_STATE[x.status] || x.status}</Text> },
                ]} />
              </Collapsible>
            )}
            <HStack gap={2} wrap="wrap">
              <Button label="Skanuj na żywo" isDisabled={disabled} tooltip={why} onClick={() => onScan("live")} />
              <Button label="Odtwórz skan" isDisabled={disabled} tooltip={why} onClick={() => onScan("replay")} />
              <Button label="Przelicz materiały" variant="primary" isDisabled={disabled} tooltip={why} onClick={() => onScan("recompute")} />
            </HStack>
          </VStack>
        </Card>
      </Grid>
      <VStack gap={2}>
        <Heading level={2}>Twórcy i droga odkrycia ({data.creatorCounts?.total ?? creators.length})</Heading>
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
            const lines = c.discoveries.length ? c.discoveries.map(describeDiscovery) : [c.discoveredVia ? `${c.discoveredVia}` : "Droga nieustalona"];
            return <VStack gap={0.5}>{lines.slice(0, 2).map((l, i) => <Text key={i} type="supporting" maxLines={1}>{l}</Text>)}</VStack>;
          } },
          { key: "reach", header: "Zasięg", width: proportional(2, { minWidth: 130 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{reachText(c.reach)}</Text> },
        ]} />
        {creators.length > 25 && <HStack hAlign="center"><Button label={allCreators ? "Pokaż mniej" : `Pokaż wszystkich (${creators.length})`} onClick={() => setAllCreators((v) => !v)} /></HStack>}
      </VStack>
    </VStack>
  );
}
