// Jeden szablon karty dla M1, M2 i M3: nagłówek z jedną linią metadanych, „Droga dowodu”, „Dlaczego tutaj” i „Dowód” obok siebie,
// „Decyzja” pod nimi (na 1440 bez przewijania), „Więcej” z trzema zakładkami (Historia, Punktacja, Szczegóły).
import React, { useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Blockquote } from "@astryxdesign/core/Blockquote";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, Layout, LayoutContent, LayoutFooter, LayoutHeader, VStack } from "@astryxdesign/core/Layout";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { Thumbnail } from "@astryxdesign/core/Thumbnail";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { BAND_COLOR } from "./parts.jsx";
import { HISTORY_KIND, RESOLUTION_LABEL, ROUTES, STATUS, clock, fmtDate, fmtDateTime, fmtDay, isYoutube, platformLabel, safeUrl, strengthLabel } from "./labels.js";
import { DecisionTile, SecondOpinionLine, Tile, WhyTile } from "./cardparts.jsx";
import { EvidencePath } from "./ProofPath.jsx";
import { ProofM2, m2Details, m2Subtitle } from "./CardM2.jsx";
import { M3Banners, ProofM3, m3Details, m3Subtitle } from "./CardM3.jsx";
import { ExternalLink, ModuleToken, OriginToken, RecalcToken, ReReviewToken, SCALE_NOTE, discoveryLines, originLabel, proofOf, reachShort, reachText } from "./parts.jsx";

const isFrame = (m) => String(m.evidenceId || "").startsWith("frame-");
const oneLine = (text) => String(text || "").replace(/\s+/g, " ").trim();
const cut = (text, n) => (text.length > n ? `${text.slice(0, n - 1)}…` : text);

/* Dowód M1: do 3 wierszy (czas lub „opis”, cytat, odnośnik), pod spodem kadry. Bez etykiety wymogu. */
function momentRows(c) {
  const byId = new Map(c.evidence.map((e) => [e.id, e]));
  const seen = new Set();
  const rows = [];
  for (const m of c.moments) {
    if (isFrame(m) || seen.has(m.evidenceId)) continue;
    seen.add(m.evidenceId);
    const e = byId.get(m.evidenceId);
    rows.push({ key: m.evidenceId || `m${rows.length}`, start: m.start, text: e?.text || null, link: safeUrl(m.deepLink) || e?.link, inDescription: m.start == null });
  }
  if (!rows.length) {
    const claim = c.evidence.find((e) => e.role === "claim" && e.available);
    if (claim) rows.push({ key: claim.id, start: claim.start, text: claim.text, link: claim.link, inDescription: claim.start == null });
  }
  return rows.sort((a, b) => Number(a.start == null) - Number(b.start == null) || (a.start ?? 0) - (b.start ?? 0));
}

/** Oznaczenie współpracy, które obala podejrzenie (w mowie, w kadrze) albo jest w opisie: pierwszy wiersz dowodu. */
export function disclosureRow(c) {
  const d = c.relationship?.disclosure;
  if (!d || !["in_speech", "in_frame", "in_description", "platform_flag"].includes(d.state) || !d.text) return null;
  const ev = d.evidenceId ? c.evidence.find((e) => e.id === d.evidenceId) : null;
  const timed = d.state === "in_speech" || d.state === "in_frame";
  return { key: `disclosure-${d.state}`, start: timed ? ev?.start ?? null : null, text: d.text, link: ev?.link || safeUrl(c.url), inDescription: !timed };
}

function ProofM1({ c }) {
  const own = disclosureRow(c);
  const rest = momentRows(c).filter((r) => !own || oneLine(r.text) !== oneLine(own.text));
  const rows = (own ? [own, ...rest] : rest).slice(0, 3);
  const frames = c.evidence.filter((e) => e.kind === "frame" && e.thumbnailUrl).slice(0, 3);
  return (
    <Tile title="Dowód" id="sekcja-momenty">
      {rows.length === 0 ? <Text color="secondary">Brak wskazanego fragmentu dla tej sprawy.</Text> : (
        <VStack gap={1.5} role="list">
          {rows.map((r) => (
            <HStack key={r.key} gap={1.5} vAlign="start" role="listitem" data-moment={r.inDescription ? "opis" : clock(r.start)}>
              <VStack width={56}><Text weight="semibold" hasTabularNumbers type={r.inDescription ? "supporting" : "body"}>{r.inDescription ? "opis" : clock(r.start)}</Text></VStack>
              <Text maxLines={2}>{r.text ? `„${cut(oneLine(r.text), 140)}”` : "—"}</Text>
              {r.link ? <ExternalLink url={r.link}>↗</ExternalLink> : null}
            </HStack>
          ))}
        </VStack>
      )}
      {frames.length > 0 && (
        <HStack gap={1.5} wrap="wrap" vAlign="start">
          {frames.map((f) => (
            <VStack key={f.id} gap={0.25} hAlign="center">
              <Thumbnail src={f.thumbnailUrl} alt={`Kadr z ${clock(f.start)}`} label={`Kadr z ${clock(f.start)}`} onClick={() => f.link && window.open(safeUrl(f.link), "_blank", "noopener")} />
              <ExternalLink url={f.link}>{clock(f.start)} ↗</ExternalLink>
            </VStack>
          ))}
        </HStack>
      )}
      <SecondOpinionLine c={c} />
    </Tile>
  );
}

const AD_STATUS = { active: "aktywna", inactive: "zakończona" };
/* Dowód reklamy z Biblioteki Reklam Meta i postu z importu: cytat treści i emisja w jednej linii. */
function ProofAd({ c }) {
  const r = c.raw;
  const from = r.adDeliveryStartDate && fmtDate(r.adDeliveryStartDate);
  const to = r.adDeliveryStopDate && fmtDate(r.adDeliveryStopDate);
  const delivery = from ? `${from} – ${to || "nadal emitowana"}${AD_STATUS[r.adStatus] ? ` (${AD_STATUS[r.adStatus]})` : ""}` : null;
  return (
    <Tile title="Dowód" id="sekcja-momenty">
      {r.adBody ? <Blockquote>{cut(oneLine(r.adBody), 420)}</Blockquote> : <Text color="secondary">Brak tekstu reklamy.</Text>}
      {delivery && <Text type="supporting"><Text weight="semibold" type="supporting">Emisja: </Text>{delivery}</Text>}
    </Tile>
  );
}

/* Post z importu bez kart kryteriów: fragment treści jako dowód. */
function ProofText({ c }) {
  const claim = c.evidence.find((e) => e.role === "claim" && e.available) || c.evidence.find((e) => e.available);
  const text = claim?.text || c.raw.description || c.raw.summary;
  return (
    <Tile title="Dowód" id="sekcja-momenty">
      {text ? <Blockquote>{cut(oneLine(text), 420)}</Blockquote> : <Text color="secondary">Brak wskazanego fragmentu dla tej sprawy.</Text>}
      <SecondOpinionLine c={c} />
    </Tile>
  );
}

function describeHistory(h) {
  const kind = h.changeKind || (h.action === "capture" ? "content" : h.action);
  const d = h.details || {};
  const label = HISTORY_KIND[kind] || h.action;
  const resolution = kind === "decision" && d.resolution ? `: ${RESOLUTION_LABEL[d.resolution] || d.resolution}` : "";
  const extra = kind === "analysis" && (d.rulesFrom || d.scoreFrom != null) ? `: ${d.scoreFrom != null ? `siła ${d.scoreFrom} → ${d.scoreTo}` : "przeliczono"}` : d.version && kind === "content" ? ` (wersja ${d.version})` : "";
  return { label: `${label}${resolution}${extra}`, note: kind === "content" ? "" : h.note };
}

const AD_DETAILS = (c) => {
  const r = c.raw;
  return [
    r.callToAction && ["Wezwanie (CTA)", r.callToAction],
    r.linkDomain && ["Domena linku", r.linkDomain],
    r.versionsCount != null && ["Wersje reklamy", `${r.versionsCount}${r.multipleVersions ? " (kilka wariantów treści)" : ""}`],
    r.importNote && ["Import", `${r.importNote}${r.importLayoutNote ? `: ${r.importLayoutNote}` : ""}`],
  ].filter(Boolean);
};

function firmEntries(c) {
  const list = c.relationship?.firm?.candidates || [];
  if (!list.length) return null;
  return (
    <Table idKey="registryId" density="compact" verticalAlign="top" data={list} columns={[
      { key: "name", header: "Nazwa", width: proportional(2, { minWidth: 100 }), renderCell: (x) => <Text>{x.name}</Text> },
      { key: "cat", header: "Wykaz", width: proportional(3, { minWidth: 120 }), renderCell: (x) => <Text type="supporting" color="secondary">{x.category}{x.checkedAt ? `, stan z ${fmtDate(x.checkedAt)}` : ""}</Text> },
    ]} />
  );
}

/* „Więcej”: historia, punktacja, szczegóły; domyślnie zamknięte. */
function MoreTabs({ c, kind }) {
  const [tab, setTab] = useState("history");
  const entries = [...c.history].reverse();
  const counter = c.counter.filter((e) => e.counterKind !== "neutral_context" && e.effect).slice(0, 4);
  const extra = kind === "m2" ? m2Details(c) : kind === "m3" ? m3Details(c) : kind === "ad" ? AD_DETAILS(c) : [];
  const knf = kind === "m1" || kind === "ad" ? firmEntries(c) : null;
  const panels = {
    history: entries.length === 0 ? <Text color="secondary">Brak wpisów w historii.</Text> : (
      <List density="compact" hasDividers>
        {entries.map((h, i) => {
          const x = describeHistory(h);
          return <Item key={h.seq ?? i} label={x.label} description={x.note || undefined} endContent={<Text type="supporting" color="secondary">{fmtDateTime(h.at)}</Text>} />;
        })}
      </List>
    ),
    score: (
      <VStack gap={2}>
        {c.score?.value != null ? <Text>Siła: {strengthLabel(c.score.band, c.score.value)} z 100 pkt.</Text> : <Text color="secondary">Brak wyliczonej siły{c.score?.notComputableReason ? `: ${c.score.notComputableReason}` : ""}.</Text>}
        {c.score?.components?.length > 0 && (
          <Table idKey="label" density="compact" data={c.score.components.map((x) => (Array.isArray(x) ? { label: x[0], points: x[1] } : { label: x.label || x.id, points: x.points }))} columns={[
            { key: "label", header: "Składnik", width: proportional(4, { minWidth: 140 }) },
            { key: "points", header: "Pkt", align: "end", width: pixel(60) },
          ]} />
        )}
        <Text type="supporting" color="secondary">{SCALE_NOTE}</Text>
        {counter.map((e, i) => <Text key={e.id || i} type="supporting">Kontrargument: {e.text ? `„${e.text}” ` : ""}{e.effect}</Text>)}
      </VStack>
    ),
    details: (
      <VStack gap={2}>
        <MetadataList>
          <MetadataListItem label="Pochodzenie">{originLabel(c.origin, c.observedAt)}</MetadataListItem>
          {kind !== "m2" && <MetadataListItem label="Odczytano">{fmtDateTime(c.observedAt)}</MetadataListItem>}
          {c.discovery.map((d, i) => <MetadataListItem key={i} label={i === 0 ? "Droga odkrycia" : ""}>{discoveryLines([d])[0]}</MetadataListItem>)}
          {c.reach && kind !== "m2" && kind !== "m3" && <MetadataListItem label="Zasięg">{reachText(c.reach)}</MetadataListItem>}
          {extra.map(([k, v]) => <MetadataListItem key={k} label={k}>{v}</MetadataListItem>)}
          <MetadataListItem label="Identyfikator">{c.id}</MetadataListItem>
          {c.url && <MetadataListItem label="Adres">{c.url}</MetadataListItem>}
        </MetadataList>
        {knf && <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Wpisy w wykazie KNF ({c.relationship.firm.candidates.length})</Text>}>{knf}</Collapsible>}
        {c.raw.description && (
          <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">{c.platform === "youtube" ? "Pełny opis filmu" : "Pełny podpis lub tekst"}</Text>}>
            <Blockquote>{c.raw.description}</Blockquote>
          </Collapsible>
        )}
      </VStack>
    ),
  };
  return (
    <Collapsible defaultIsOpen={false} trigger={<Text weight="semibold">Więcej: historia, punktacja, szczegóły</Text>}>
      <VStack gap={2} padding={2}>
        <TabList role="tablist" size="sm" value={tab} onChange={setTab}>
          <Tab value="history" label="Historia" panelId="more-panel" />
          <Tab value="score" label="Punktacja" panelId="more-panel" />
          <Tab value="details" label="Szczegóły" panelId="more-panel" />
        </TabList>
        <VStack id="more-panel" role="tabpanel">{panels[tab]}</VStack>
      </VStack>
    </Collapsible>
  );
}

const jump = (id) => () => {
  const el = document.getElementById(id);
  el?.scrollIntoView({ behavior: "smooth", block: "start" });
  if (id === "sekcja-decyzja") requestAnimationFrame(() => el?.querySelector("button")?.focus({ preventScroll: true }));
};

/** Rodzaj karty: strona firmy (M2), oferta doradcza (M3), reklama z biblioteki Meta, inne (film, post). */
export function kindOf(c) {
  if (c.raw.adBody) return "ad";
  if (c.module === "M2" && c.raw.m2Card && c.checks.length > 0) return "m2";
  if (c.module === "M3" && c.raw.identity && c.checks.length > 0) return "m3";
  return c.module === "M1" || c.platform === "youtube" || c.platform === "tiktok" ? "m1" : "text";
}

/** Jedna linia metadanych: autor · źródło · data · zasięg · firma. */
function metaLine(c, kind) {
  if (kind === "m2") return m2Subtitle(c);
  if (kind === "m3") return m3Subtitle(c);
  const published = c.publishedAt ? fmtDate(c.publishedAt) : c.publishedAtDerived?.value ? `≈ ${fmtDate(c.publishedAtDerived.value)}` : null;
  const candidates = c.relationship?.firm?.candidates?.length || 0;
  const firm = c.raw.firmShort || c.relationship?.firmName || c.raw.firmRelation?.label;
  const firmText = firm ? `Firma: ${firm}${candidates ? ` (${candidates} ${candidates === 1 ? "wpis" : candidates < 5 ? "wpisy" : "wpisów"} KNF)` : ""}` : null;
  return [c.creatorName || c.raw.author, platformLabel(c.platform), published, reachShort(c.reach), firmText].filter(Boolean).join(" · ");
}

export function CaseDetail({ c, headingRef, onBack, onSaved, narrow }) {
  const kind = kindOf(c);
  const proof = proofOf(c);
  const refute = c.relationship?.disclosure?.state === "in_speech" ? disclosureRow(c) : null;
  const openUrl = kind === "m2" || kind === "m3" ? safeUrl(c.url) : refute?.link || proof?.url;
  const openAt = refute?.start ?? proof?.start;
  const strength = c.score?.value != null ? strengthLabel(c.score.band, c.score.value) : null;
  const header = (
    <LayoutHeader padding={0} hasDivider>
      <VStack gap={0.5} padding={narrow ? 2 : 2}>
        <HStack gap={2} hAlign="between" vAlign="center" wrap="wrap">
          <HStack gap={1} wrap="wrap" vAlign="center">
            {strength && c.score.value > 0 && <Token size="sm" color={BAND_COLOR[c.score.band] || "gray"} label={strength} />}
            <ModuleToken module={c.module} />
            {c.route && <Text type="supporting" color="secondary">{ROUTES[c.route] || c.route}</Text>}
            {c.status !== "new" && <Token size="sm" color="gray" label={STATUS[c.status] || c.status} />}
            {(c.origin === "synthetic" || c.origin === "upload") && <OriginToken origin={c.origin} at={c.observedAt} />}
            <RecalcToken c={c} />
            <ReReviewToken c={c} />
          </HStack>
          {onBack && <Button label="Wróć do listy" variant="ghost" size="sm" onClick={onBack} />}
        </HStack>
        <Heading level={2} ref={headingRef} tabIndex={-1}>{c.title}</Heading>
        <Text type="supporting" color="secondary" maxLines={2}>{metaLine(c, kind)}</Text>
        {openUrl && <HStack gap={2} wrap="wrap"><Button label={kind === "m2" ? "Otwórz stronę" : kind === "m3" ? "Otwórz ofertę" : !isYoutube(openUrl) ? "Otwórz źródło" : openAt != null ? `Otwórz w filmie od ${clock(openAt)}` : "Otwórz w filmie"} size="sm" variant="primary" href={openUrl} target="_blank" /></HStack>}
      </VStack>
    </LayoutHeader>
  );
  const proofTile = kind === "m2" ? <ProofM2 c={c} /> : kind === "m3" ? <ProofM3 c={c} /> : kind === "ad" ? <ProofAd c={c} /> : kind === "text" ? <ProofText c={c} /> : <ProofM1 c={c} />;
  const body = (
    <VStack gap={1.5} padding={narrow ? 2 : 2}>
      {c.origin === "synthetic" || c.origin === "upload" ? (
        <Banner status="info" title={c.origin === "upload" ? "Plik operatora" : "Materiał demonstracyjny"} description="Nie pochodzi z bieżącego rynku." />
      ) : null}
      {c.needsRecalc && c.module === "M1" && <Banner status="warning" title="Wynik ze starszej wersji analizy" description={c.needsRecalcReason || "Wymaga przeliczenia."} />}
      {kind === "m3" && <M3Banners c={c} />}
      <EvidencePath c={c} narrow={narrow} />
      <Grid columns={{ minWidth: 300, max: 2 }} gap={2}>
        <WhyTile c={c} />
        {proofTile}
      </Grid>
      <DecisionTile c={c} onSaved={onSaved} key={c.id} />
      <MoreTabs c={c} kind={kind} />
    </VStack>
  );
  const footer = narrow && (
    <LayoutFooter padding={2} hasDivider>
      <HStack gap={2}>
        <Button label="Dowód" onClick={jump("sekcja-momenty")} />
        <Button label="Decyzja" variant="primary" onClick={jump("sekcja-decyzja")} />
      </HStack>
    </LayoutFooter>
  );
  return <Layout height="fill" header={header} content={<LayoutContent padding={0} isScrollable>{body}</LayoutContent>} footer={footer || undefined} />;
}
