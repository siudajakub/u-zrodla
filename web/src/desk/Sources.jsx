import React, { useEffect, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
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
import { SOURCE_STATE, describeDiscovery, fmtDateTime } from "./labels.js";
import { ExternalLink, reachText } from "./parts.jsx";
import { lastScanOf } from "./model.js";

const MODE = { live: "na żywo", replay: "odtworzenie próbki", recompute: "przeliczenie", upload: "plik operatora" };
const SCAN_STATUS = { queued: "w kolejce", running: "w toku", done: "zakończony", partial: "częściowy", failed: "nieudany" };
const ERROR_HINT = { "HTTP 302": "przekierowanie do strony zgody", "HTTP 429": "limit zapytań serwisu", "HTTP 403": "dostęp odrzucony" };
const RANK = { error: 0, unavailable: 0, limit: 1, needs_key: 1, partial: 2, candidate: 3, stale: 4, empty: 5, ok: 6 };

export const isActive = (scan) => scan && (scan.status === "queued" || scan.status === "running");

export function scanLine(scan) {
  if (!scan) return "Nie uruchomiono jeszcze skanu.";
  const when = fmtDateTime(scan.createdAt);
  const s = scan.sources;
  const trouble = s ? [s.failed ? `${s.failed} z błędem` : null, s.partial ? `${s.partial} częściowo` : null].filter(Boolean).join(", ") : (scan.warnings || []).length ? `${scan.warnings.length} ostrzeżeń` : null;
  const errors = (scan.warnings || []).filter((w) => /HTTP/.test(w));
  const code = errors.length ? ` (${[...new Set(errors)].join(", ")})` : "";
  return [`Skan ${MODE[scan.mode] || scan.mode}`, when, SCAN_STATUS[scan.status] || scan.status, trouble ? `${trouble}${code}` : null, scan.captures != null ? `${scan.captures} materiałów przejrzanych` : null, scan.newCreators ? `${scan.newCreators} nowy twórca` : null].filter(Boolean).join(" · ");
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
    <Banner status="info" title={`Skan ${MODE[scan.mode] || ""} w toku od ${fmtDateTime(scan.createdAt)}${p ? ` · przejrzano ${p.done} z ${p.total} źródeł` : ""}`}
      description="Przyciski skanu są wyłączone do zakończenia. Wyniki pojawią się w kolejce."
      endContent={p ? <ProgressBar label="Postęp skanu" isLabelHidden value={p.done} max={p.total || 1} /> : undefined} />
  );
}

function sourceRows(data) {
  const health = data.sourceHealth || {};
  return [...(data.sources || [])].map((s) => {
    const key = s.id || s.name;
    const err = s.lastError || null;
    const status = s.status in SOURCE_STATE ? s.status : "ok";
    return { ...s, key, status, health: health[key], err };
  }).sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9) || String(a.name).localeCompare(String(b.name), "pl"));
}

function sourceName(s) {
  if (s.name && s.name !== "Odkrywanie profilu") return s.name;
  return s.target || s.url || s.name || s.key;
}

function errorText(s) {
  const raw = s.err ? `${s.err.code} ${s.err.message}` : s.error;
  if (!raw) return null;
  const hint = Object.entries(ERROR_HINT).find(([k]) => raw.includes(k));
  return hint ? `${raw}: ${hint[1]}` : raw;
}

export function Sources({ data, busy, scanning, onScan }) {
  const scan = lastScanOf(data);
  const rows = sourceRows(data);
  const creators = [...data.creatorMap.values()];
  const detail = useScanProgress(scan);
  const ok = rows.filter((r) => r.status === "ok" || r.status === "empty").length;
  const failed = rows.filter((r) => ["error", "unavailable", "limit", "needs_key"].includes(r.status)).length;
  const disabled = busy || scanning;
  const why = scanning ? "Skan w toku." : undefined;
  return (
    <VStack gap={5} padding={4}>
      <VStack gap={1}>
        <Heading level={1}>Źródła i droga odkrycia twórców</Heading>
        <Text color="secondary">Co system przeszukał, kiedy i z jakim skutkiem. Błąd źródła jest czym innym niż „0 nowych materiałów”.</Text>
      </VStack>
      <ScanBanner scan={scan} detail={detail} />
      <VStack gap={2}>
        <Heading level={2}>Ostatni skan</Heading>
        {scan ? (
          <MetadataList columns="multi">
            <Meta label="Tryb">{MODE[scan.mode] || scan.mode}</Meta>
            <Meta label="Stan">{SCAN_STATUS[scan.status] || scan.status}</Meta>
            <Meta label="Początek">{fmtDateTime(scan.createdAt)}</Meta>
            <Meta label="Koniec">{isActive(scan) ? "w toku" : fmtDateTime(scan.updatedAt)}</Meta>
            <Meta label="Źródła">{scan.sources ? `${scan.sources.ok} działa, ${scan.sources.empty} bez nowych, ${scan.sources.partial} częściowo, ${scan.sources.failed} z błędem (z ${scan.sources.total})` : `${ok} działa, ${failed} z błędem (z ${rows.length})`}</Meta>
            <Meta label="Materiały">{scan.captures ?? "—"} przejrzanych, {scan.changedFindings ?? "—"} zmienionych</Meta>
            <Meta label="Nowi twórcy">{scan.newCreators ?? "brak danych"}</Meta>
            <Meta label="Nowe do sprawdzenia">{scan.referred ?? "brak danych"}</Meta>
          </MetadataList>
        ) : <EmptyState isCompact title="Nie uruchomiono jeszcze skanu" description="Uruchom skan, aby zebrać materiały. Pusta lista nie jest błędem." />}
        {(scan?.warnings || []).length > 0 && <Text type="supporting" color="secondary">Ostrzeżenia skanu: {[...new Set(scan.warnings)].join("; ")}</Text>}
        {detail?.steps?.length > 0 && (
          <List density="compact" hasDividers>
            {detail.steps.map((step) => <Item key={step.id || step.name} label={step.name || step.sourceId} endContent={<Text type="supporting" color="secondary">{step.status}</Text>} />)}
          </List>
        )}
        <HStack gap={2} wrap="wrap">
          <Button label="Skanuj na żywo" isDisabled={disabled} tooltip={why} onClick={() => onScan("live")} />
          <Button label="Odtwórz próbkę" isDisabled={disabled} tooltip={why} onClick={() => onScan("replay")} />
          <Button label="Przelicz materiały" variant="primary" isDisabled={disabled} tooltip={why} onClick={() => onScan("recompute")} />
        </HStack>
      </VStack>
      <VStack gap={2}>
        <Heading level={2}>Stan źródeł ({rows.length})</Heading>
        <Table idKey="key" data={rows} density="balanced" verticalAlign="top" emptyState={<EmptyState isCompact title="Brak źródeł" description="Źródła pojawią się po pierwszym skanie." />} columns={[
          { key: "name", header: "Źródło", width: proportional(3, { minWidth: 180 }), renderCell: (s) => (
            <VStack gap={0.5}>
              <Text weight="semibold" maxLines={2}>{sourceName(s)}</Text>
              <Text type="supporting" color="secondary" maxLines={2}>{typeof s.scope === "string" ? s.scope : s.scope?.query ? `zapytanie „${s.scope.query}”` : s.kind || ""}</Text>
              <ExternalLink url={s.url || s.target}>Otwórz źródło</ExternalLink>
            </VStack>
          ) },
          { key: "state", header: "Stan", width: pixel(190), renderCell: (s) => {
            const [variant, label] = SOURCE_STATE[s.status] || ["neutral", s.status];
            return <HStack gap={1} vAlign="center"><StatusDot variant={variant} label={label} /><Text>{label}</Text></HStack>;
          } },
          { key: "last", header: "Ostatni sukces", width: proportional(2, { minWidth: 130 }), renderCell: (s) => <Text type="supporting">{s.lastSuccessAt ? fmtDateTime(s.lastSuccessAt) : "brak udanego odczytu"}</Text> },
          { key: "error", header: "Ostatnia awaria i następny krok", width: proportional(3, { minWidth: 190 }), renderCell: (s) => {
            const text = errorText(s);
            if (!text && (s.status === "ok" || s.status === "empty")) return <Text type="supporting" color="secondary">{s.status === "empty" ? "0 nowych materiałów (to nie błąd)" : "—"}</Text>;
            return <VStack gap={0.5}><Text type="supporting">{text || "—"}</Text>{s.err?.nextStep && <Text type="supporting" color="secondary">{s.err.nextStep}</Text>}{s.quota && <Text type="supporting" color="secondary">Kwota: {s.quota.used} z {s.quota.limit}</Text>}</VStack>;
          } },
          { key: "count", header: "Materiały", align: "end", width: pixel(100), renderCell: (s) => s.count ?? "—" },
        ]} />
      </VStack>
      <VStack gap={2}>
        <HStack gap={2} vAlign="center"><Heading level={2}>Twórcy i droga odkrycia ({creators.length})</Heading></HStack>
        <Table idKey="id" data={creators} density="balanced" verticalAlign="top" emptyState={<EmptyState isCompact title="Brak odkrytych twórców" />} columns={[
          { key: "name", header: "Twórca", width: proportional(3, { minWidth: 180 }), renderCell: (c) => (
            <VStack gap={0.5}>
              <HStack gap={1} wrap="wrap" vAlign="center">
                <Text weight="semibold" maxLines={1}>{c.name}</Text>
                {c.isNewInScan && <Token size="sm" color="green" label="nowy w skanie" />}
                {(c.seed || c.isSeed || c.status === "seed") && <Token size="sm" color="gray" label="profil monitorowany" />}
                {c.status === "candidate" && <Token size="sm" color="yellow" label="kandydat" />}
              </HStack>
              <Text type="supporting" color="secondary">{c.platform}{c.persistentId ? "" : c.status === "candidate" || !c.id.startsWith("youtube:UC") ? " · ID niepotwierdzone" : ""}</Text>
              <ExternalLink url={c.url}>Profil</ExternalLink>
            </VStack>
          ) },
          { key: "via", header: "Droga odkrycia", width: proportional(4, { minWidth: 220 }), renderCell: (c) => {
            const lines = c.discoveries.length ? c.discoveries.map(describeDiscovery) : [c.discoveredVia ? `${c.discoveredVia} (droga odkrycia sprzed rozszerzenia)` : "Droga nieustalona"];
            return <VStack gap={0.5}>{lines.slice(0, 3).map((l, i) => <Text key={i} type="supporting">{l}</Text>)}</VStack>;
          } },
          { key: "reach", header: "Zasięg", width: proportional(2, { minWidth: 150 }), renderCell: (c) => <Text type="supporting">{reachText(c.reach)}</Text> },
        ]} />
      </VStack>
    </VStack>
  );
}
