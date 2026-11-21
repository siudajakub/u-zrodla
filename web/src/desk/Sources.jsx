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
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { SCAN_MODE, SCAN_STATUS, SOURCE_STATE, describeDiscovery, fmtDateTime, fmtDay, fmtDayRoman } from "./labels.js";
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

function sourceRows(data) {
  const detail = data.sourceHealthDetail || {};
  return [...(data.sources || [])].map((s) => {
    const key = s.id || s.name;
    const status = s.status in SOURCE_STATE ? s.status : "ok";
    return { ...s, key, status, health: detail[key], err: s.lastError || detail[key]?.lastError || null };
  }).sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9) || String(a.name).localeCompare(String(b.name), "pl"));
}

function sourceName(s) {
  if (s.name && s.name !== "Odkrywanie profilu") return s.name;
  return s.target || s.url || s.name || s.key;
}

function errorText(s) {
  const raw = s.err ? `${s.err.code || ""} ${s.err.message || ""}`.trim() : s.error;
  if (!raw) return null;
  const hint = Object.entries(ERROR_HINT).find(([k]) => raw.includes(k));
  return hint ? `${raw}: ${hint[1]}` : raw;
}

function nextStep(s) {
  if (s.err?.nextStep) return s.err.nextStep;
  if (s.retryAt) return `Ponowna próba: ${fmtDateTime(s.retryAt)}`;
  if (s.status === "limit") return s.quota?.resetAt ? `Kwota odnowi się ${fmtDateTime(s.quota.resetAt)}` : "Poczekaj na odnowienie kwoty";
  if (s.status === "needs_key") return "Uzupełnij klucz dostępu";
  if (s.status === "ok" || s.status === "empty") return "Nic do zrobienia";
  return "Sprawdź źródło lub uruchom skan ponownie";
}

function SourceTile({ s }) {
  const [variant, label] = SOURCE_STATE[s.status] || ["neutral", s.status];
  const err = errorText(s);
  return (
    <Card padding={3}>
      <VStack gap={1.5}>
        <HStack gap={2} hAlign="between" vAlign="start">
          <Text weight="semibold" maxLines={2}>{sourceName(s)}</Text>
          <HStack gap={1} vAlign="center"><StatusDot variant={variant} label={label} /><Text type="supporting">{label}</Text></HStack>
        </HStack>
        <MetadataList>
          <Meta label="Ostatni sukces">{s.lastSuccessAt ? fmtDateTime(s.lastSuccessAt) : "brak udanego odczytu"}</Meta>
          {s.quota?.limit != null && <Meta label="Kwota">{s.quota.used} z {s.quota.limit}{s.quota.resetAt ? `, odnowienie ${fmtDateTime(s.quota.resetAt)}` : ""}</Meta>}
          {s.count != null && <Meta label="Materiały">{s.count}</Meta>}
          {err && <Meta label="Ostatnia awaria">{err}</Meta>}
          <Meta label="Następny krok">{nextStep(s)}</Meta>
        </MetadataList>
        <ExternalLink url={s.url || s.target}>Otwórz źródło ↗</ExternalLink>
      </VStack>
    </Card>
  );
}

const HEALTH = { ok: ["success", "Wszystkie źródła działają"], degraded: ["warning", "Część źródeł ma problem"], failed: ["error", "Żadne źródło nie działa"] };

function TrendTable({ trend }) {
  const days = [...(trend?.byDay || [])].reverse();
  const max = Math.max(1, ...days.map((d) => d.referred || 0));
  return (
    <VStack gap={2}>
      <Heading level={2}>Trend skanów</Heading>
      <Table idKey="day" density="compact" data={days} emptyState={<EmptyState isCompact title="Brak danych o skanach" />} columns={[
        { key: "day", header: "Dzień", width: pixel(96), renderCell: (d) => <Text>{fmtDay(d.day)}</Text> },
        { key: "scans", header: "Skany", align: "end", width: pixel(64), renderCell: (d) => d.scans },
        { key: "captures", header: "Przejrzane", align: "end", width: pixel(96), renderCell: (d) => d.captures },
        { key: "newMaterials", header: "Nowe materiały", align: "end", width: pixel(120), renderCell: (d) => d.newMaterials },
        { key: "referred", header: "Do sprawdzenia", width: proportional(2, { minWidth: 140 }), renderCell: (d) => (
          <HStack gap={2} vAlign="center"><Text hasTabularNumbers>{d.referredKnown === false ? "?" : d.referred}</Text><ProgressBar label="Do sprawdzenia" isLabelHidden value={d.referred || 0} max={max} /></HStack>
        ) },
      ]} />
    </VStack>
  );
}

export function Sources({ data, busy, scanning, onScan }) {
  const scan = lastScanOf(data);
  const dataScan = dataScanOf(data);
  const rows = sourceRows(data);
  const creators = [...data.creatorMap.values()];
  const [allCreators, setAllCreators] = useState(false);
  const detail = useScanProgress(scan);
  const [steps, setSteps] = useState(null);
  useEffect(() => {
    if (!dataScan?.id) return undefined;
    let off = false;
    api.scan(dataScan.id).then((d) => !off && setSteps(d.steps || []), () => !off && setSteps(null));
    return () => {
      off = true;
    };
  }, [dataScan?.id]);
  const summary = data.sourceHealthSummary;
  const [hv, hl] = HEALTH[summary?.status] || ["neutral", "Stan źródeł nieznany"];
  const disabled = busy || scanning;
  const why = scanning ? "Skan w toku." : undefined;
  const shown = allCreators ? creators : creators.slice(0, 25);
  return (
    <VStack gap={4} padding={3}>
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Heading level={1}>Źródła i droga odkrycia</Heading>
        {summary && <HStack gap={1} vAlign="center"><StatusDot variant={hv} label={hl} /><Text type="supporting">{hl}{summary.problems ? ` (${summary.problems} z ${summary.total})` : ` (${summary.total})`}</Text></HStack>}
      </HStack>
      <ScanBanner scan={scan} detail={detail} />
      <Card padding={3}>
        <VStack gap={2}>
          <Heading level={2}>Ostatni skan materiałów</Heading>
          <Text>{scanLine(dataScan)}</Text>
          {dataScan && (
            <MetadataList columns="multi">
              <Meta label="Początek">{fmtDateTime(dataScan.createdAt)}</Meta>
              <Meta label="Koniec">{fmtDateTime(dataScan.updatedAt)}</Meta>
              <Meta label="Źródła">{dataScan.sources ? `${dataScan.sources.ok} działa, ${dataScan.sources.empty} bez nowych, ${dataScan.sources.partial} częściowo, ${dataScan.sources.failed} z błędem` : "—"}</Meta>
              <Meta label="Do sprawdzenia">{dataScan.referred ?? "brak danych"}</Meta>
            </MetadataList>
          )}
          {steps?.length > 0 && (
            <Table idKey="id" density="compact" data={steps} columns={[
              { key: "name", header: "Krok skanu", width: proportional(3, { minWidth: 140 }), renderCell: (x) => x.name || x.sourceId },
              { key: "status", header: "Stan", width: pixel(110), renderCell: (x) => <Text type="supporting">{({ done: "zakończony", running: "w toku", queued: "w kolejce", failed: "błąd", skipped: "pominięty" })[x.status] || x.status}</Text> },
            ]} />
          )}
          <HStack gap={2} wrap="wrap">
            <Button label="Skanuj na żywo" isDisabled={disabled} tooltip={why} onClick={() => onScan("live")} />
            <Button label="Odtwórz skan" isDisabled={disabled} tooltip={why} onClick={() => onScan("replay")} />
            <Button label="Przelicz materiały" variant="primary" isDisabled={disabled} tooltip={why} onClick={() => onScan("recompute")} />
          </HStack>
        </VStack>
      </Card>
      <VStack gap={2}>
        <Heading level={2}>Stan źródeł ({rows.length})</Heading>
        {rows.length === 0 ? <EmptyState isCompact title="Brak źródeł" description="Źródła pojawią się po pierwszym skanie." /> : (
          <Grid columns={{ minWidth: 300, max: 3 }} gap={3}>{rows.map((s) => <SourceTile key={s.key} s={s} />)}</Grid>
        )}
      </VStack>
      <TrendTable trend={data.trend} />
      <VStack gap={2}>
        <Heading level={2}>Twórcy i droga odkrycia ({creators.length})</Heading>
        <Table idKey="id" data={shown} density="compact" verticalAlign="top" emptyState={<EmptyState isCompact title="Brak odkrytych twórców" />} columns={[
          { key: "name", header: "Twórca", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
            <VStack gap={0.5}>
              <HStack gap={1} wrap="wrap" vAlign="center">
                <Text weight="semibold" maxLines={1}>{c.name}</Text>
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
