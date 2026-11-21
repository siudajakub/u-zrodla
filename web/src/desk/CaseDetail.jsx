// Karta sprawy: pasek nagłówka (zawsze widoczny) + kafelki z tabelami i punktami; reszta w zwijanym „Więcej”.
import React, { useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Blockquote } from "@astryxdesign/core/Blockquote";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, Layout, LayoutContent, LayoutFooter, LayoutHeader, VStack } from "@astryxdesign/core/Layout";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { TextArea } from "@astryxdesign/core/TextArea";
import { Thumbnail } from "@astryxdesign/core/Thumbnail";
import { Heading, Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { BANDS, HISTORY_KIND, RESOLUTIONS, ROUTES, RESOLUTION_LABEL, STATUS, VARIANTS, clock, fmtDate, fmtDateTime, fmtDayRoman, isYoutube, safeUrl } from "./labels.js";
import { DecisionTile, Tile, WhyTile } from "./cardparts.jsx";
import { M2FirmTile, M2ScopeTile, RisksTile, m2Subtitle } from "./CardM2.jsx";
import { AxesTile, M3ScopeTile, MissingTile, PermissionsTile, m3Subtitle } from "./CardM3.jsx";
import { ExternalLink, ImportToken, OriginToken, RecalcToken, ReReviewToken, SCALE_NOTE, discoveryLines, originLabel, proofOf, reachText } from "./parts.jsx";


const isFrame = (m) => String(m.evidenceId || "").startsWith("frame-");


/* 2. Momenty do sprawdzenia: tabela czas | co | otwórz, miniatury kadrów pod spodem. */
function momentRows(c) {
  const byId = new Map(c.evidence.map((e) => [e.id, e]));
  const seen = new Set();
  const rows = [];
  for (const m of c.moments) {
    if (isFrame(m) || seen.has(m.evidenceId)) continue;
    seen.add(m.evidenceId);
    const e = byId.get(m.evidenceId);
    rows.push({ key: m.evidenceId || `m${rows.length}`, start: m.start, label: m.label, text: e?.text || null, link: safeUrl(m.deepLink) || e?.link, inDescription: m.start == null });
  }
  if (!rows.length) {
    const claim = c.evidence.find((e) => e.role === "claim" && e.available);
    if (claim) rows.push({ key: claim.id, start: claim.start, label: "Fragment dowodowy", text: claim.text, link: claim.link, inDescription: claim.start == null });
  }
  return rows.sort((a, b) => Number(a.start == null) - Number(b.start == null) || (a.start ?? 0) - (b.start ?? 0));
}

function MomentsTile({ c }) {
  const rows = momentRows(c);
  const frames = c.evidence.filter((e) => e.kind === "frame" && e.thumbnailUrl);
  return (
    <Tile title="Momenty do sprawdzenia" id="sekcja-momenty">
      {rows.length === 0 ? <Text color="secondary">Brak wskazanego fragmentu dla tej sprawy.</Text> : (
        <Table idKey="key" density="compact" verticalAlign="top" data={rows} columns={[
          { key: "t", header: "Czas", width: pixel(64), renderCell: (r) => (r.inDescription ? <Text type="supporting">opis</Text> : <Text weight="semibold" hasTabularNumbers>{clock(r.start)}</Text>) },
          { key: "what", header: "Co", width: proportional(4, { minWidth: 120 }), renderCell: (r) => (
            <VStack gap={0.5}>
              <Text weight="medium">{r.label}</Text>
              {r.text && <Text type="supporting" color="secondary" maxLines={2}>„{r.text}”</Text>}
            </VStack>
          ) },
          { key: "open", header: "Otwórz", width: pixel(96), renderCell: (r) => (r.link ? <ExternalLink url={r.link}>{r.inDescription ? (isYoutube(r.link) ? "Film ↗" : "Źródło ↗") : `od ${clock(r.start)} ↗`}</ExternalLink> : <Text type="supporting" color="secondary">—</Text>) },
        ]} />
      )}
      {frames.length > 0 && (
        <VStack gap={1}>
          <HStack gap={2} wrap="wrap" vAlign="start">
            {frames.map((f) => (
              <VStack key={f.id} gap={0.5} width={104}>
                <Thumbnail src={f.thumbnailUrl} alt={`Kadr z ${clock(f.start)}`} label={`Kadr z ${clock(f.start)}`} onClick={() => f.link && window.open(safeUrl(f.link), "_blank", "noopener")} />
                <ExternalLink url={f.link}>{clock(f.start)} ↗</ExternalLink>
              </VStack>
            ))}
          </HStack>
          <Text type="supporting" color="secondary">Tekst z obrazu nie jest odczytywany automatycznie.</Text>
        </VStack>
      )}
    </Tile>
  );
}

/* 3. Co zbadano: tabela ze znaczkami, luki wyróżnione. */
function coverageRows(c) {
  const cov = c.coverage;
  if (!cov) return [{ key: "none", name: "Zakres", ok: false, text: "nieznany: brak oznaczenia dotyczy tylko zbadanego opisu" }];
  if (cov.legacyText) return [{ key: "legacy", name: "Zakres (starsza analiza)", ok: false, text: cov.legacyText }];
  const m = cov.modalities;
  const rows = [];
  const full = (s) => s === "full" || s === "observed";
  if (m.description) rows.push({ key: "d", name: "Opis", ok: full(m.description.state), text: full(m.description.state) ? `całość${m.description.chars ? `, ${m.description.chars} znaków` : ""}` : m.description.reason || "nie zbadano" });
  if (m.transcript) {
    const t = m.transcript;
    const span = t.windows?.length ? `${clock(t.windows[0].start)}–${clock(t.windows[t.windows.length - 1].end)}` : null;
    rows.push({ key: "t", name: "Mowa", ok: t.state === "full", text: t.state === "full" ? `${span || "cała"}${t.source === "auto_captions" ? ", auto-napisy" : ""}` : [t.state === "pending" ? "czeka na transkrypcję" : t.state === "unavailable" ? "niedostępna" : "tylko fragment", span, t.reason].filter(Boolean).join(", ") });
  }
  if (m.frames) {
    const n = m.frames.moments?.length || 0;
    rows.push({ key: "f", name: "Kadry", ok: m.frames.state !== "not_collected" && n > 0, text: n ? `${n} ${n === 1 ? "kadr" : n < 5 ? "kadry" : "kadrów"}; tekst z obrazu nieodczytywany` : m.frames.reason || "nie zbadano" });
  }
  if (m.adText) rows.push({ key: "a", name: "Tekst reklamy", ok: m.adText.state === "full", text: m.adText.state === "full" ? "całość, z zapisanej strony" : "nie zbadano" });
  if (m.media) rows.push({ key: "m", name: "Obraz i wideo", ok: false, text: "nie zbadano" });
  if (m.render) rows.push({ key: "r", name: "Wygląd (render)", ok: false, text: "nie zbadano" });
  if (m.platformFlags) {
    const p = m.platformFlags;
    rows.push({ key: "p", name: c.platform === "youtube" ? "Oznaczenie YouTube" : "Oznaczenie platformy", ok: p.paidPromotion != null, text: p.paidPromotion == null ? "nie sprawdzono" : p.paidPromotion ? "płatna promocja: tak" : "brak" });
  }
  return rows;
}

function ScopeTile({ c }) {
  const rows = coverageRows(c);
  const gaps = (c.coverage?.gaps || []).map((g) => g.reason).filter(Boolean);
  return (
    <Tile title="Co zbadano">
      {c.coverage?.label && <Text weight="medium">{c.coverage.label}</Text>}
      {c.platform === "tiktok" && <Text type="supporting">Zbadano tylko podpis pod filmem. Mowy i obrazu nie badano, więc brak oznaczenia w podpisie nie jest wnioskiem.</Text>}
      {(c.platform === "facebook" || c.platform === "instagram") && <Text type="supporting">Zbadano tylko tekst reklamy. Obrazu i strony docelowej nie badano.</Text>}
      <Table idKey="key" density="compact" verticalAlign="top" data={rows} columns={[
        { key: "n", header: "Zakres", width: proportional(2, { minWidth: 100 }), renderCell: (r) => <Text weight="medium">{r.name}</Text> },
        { key: "s", header: "Stan", width: pixel(84), renderCell: (r) => <Token size="sm" color={r.ok ? "green" : "yellow"} label={r.ok ? "zbadano" : "luka"} /> },
        { key: "x", header: "Szczegóły", width: proportional(3, { minWidth: 120 }), renderCell: (r) => <Text type="supporting" color="secondary">{r.text}</Text> },
      ]} />
      {gaps.length > 0 && <Text type="supporting">Luki: {gaps.join("; ")}.</Text>}
      {c.coverage?.blocksConclusion && <Banner status="info" title="Wniosek o braku oznaczenia wstrzymany" />}
    </Tile>
  );
}

/* 4. Firma: nazwa | typ | wykaz KNF. */
const FIRM_ROLE = { advertiser: "reklamodawca", payer: "płatnik", beneficiary: "beneficjent", mentioned: "wspomniana w treści" };

function FirmTile({ c }) {
  const fr = c.raw.firmRelation;
  if (fr && !c.relationship) {
    return (
      <Tile title="Firma">
        <MetadataList>
          <MetadataListItem label="Firma">{fr.label || fr.firm}</MetadataListItem>
          <MetadataListItem label="Rola">{FIRM_ROLE[fr.role] || fr.role || "—"}</MetadataListItem>
          {fr.quote && <MetadataListItem label="Podstawa">„{fr.quote}”</MetadataListItem>}
        </MetadataList>
      </Tile>
    );
  }
  const firm = c.relationship?.firm;
  const candidates = firm?.candidates || [];
  if (!firm?.mention && !candidates.length) {
    return <Tile title="Firma"><Text color="secondary">Nie ustalono firmy.</Text></Tile>;
  }
  const kind = candidates.length ? [...new Set(candidates.map((x) => (x.category || "").replace(/^Firmy inwestycyjne - /, "").replace(/^Notyfikacje zagranicznych firm inwestycyjnych na terytorium RP$/, "zagraniczna (notyfikacja)")))].join(" / ") : "—";
  const count = candidates.length === 0 ? "brak wpisu" : `${candidates.length} ${candidates.length === 1 ? "wpis" : candidates.length < 5 ? "wpisy" : "wpisów"}${firm.identityStatus === "candidates" ? ", do rozstrzygnięcia" : ""}`;
  return (
    <Tile title="Firma">
      <Table idKey="name" density="compact" verticalAlign="top" data={[{ name: firm.mention || candidates[0]?.name, kind, count }]} columns={[
        { key: "name", header: "Firma", width: proportional(2, { minWidth: 80 }), renderCell: (r) => <Text weight="semibold">{r.name}</Text> },
        { key: "kind", header: "Typ podmiotu", width: proportional(3, { minWidth: 110 }), renderCell: (r) => <Text type="supporting">{r.kind}</Text> },
        { key: "count", header: "Wykaz KNF", width: proportional(2, { minWidth: 100 }), renderCell: (r) => <Text type="supporting">{r.count}</Text> },
      ]} />
      {candidates.length > 0 && (
        <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Wpisy w wykazie KNF</Text>}>
          <Table idKey="registryId" density="compact" verticalAlign="top" data={candidates} columns={[
            { key: "name", header: "Nazwa", width: proportional(2, { minWidth: 100 }), renderCell: (x) => <Text>{x.name}</Text> },
            { key: "cat", header: "Wykaz", width: proportional(3, { minWidth: 120 }), renderCell: (x) => <Text type="supporting" color="secondary">{x.category}{x.checkedAt ? `, stan z ${fmtDate(x.checkedAt)}` : ""}</Text> },
          ]} />
        </Collapsible>
      )}
    </Tile>
  );
}

/* Reklama z Biblioteki Reklam Meta (import): treść, reklamodawca, daty emisji, CTA, domena, wersje. */
const AD_STATUS = { active: "aktywna", inactive: "zakończona" };
function AdTile({ c }) {
  const r = c.raw;
  const from = r.adDeliveryStartDate && fmtDate(r.adDeliveryStartDate);
  const to = r.adDeliveryStopDate && fmtDate(r.adDeliveryStopDate);
  const dates = from ? `${from} – ${to || "nadal emitowana"}` : "brak w zapisanym pliku";
  return (
    <Tile title="Treść reklamy" id="sekcja-momenty" aside={<ImportToken c={c} />}>
      {r.adBody ? <Blockquote>{r.adBody}</Blockquote> : <Text color="secondary">Brak tekstu reklamy.</Text>}
      <MetadataList>
        <MetadataListItem label="Reklamodawca">{r.author || c.creatorName || "—"}</MetadataListItem>
        <MetadataListItem label="Emisja">{dates}{AD_STATUS[r.adStatus] ? ` (${AD_STATUS[r.adStatus]})` : ""}</MetadataListItem>
        <MetadataListItem label="Wezwanie (CTA)">{r.callToAction || "brak"}</MetadataListItem>
        <MetadataListItem label="Domena linku">{r.linkDomain || "brak w zapisanym pliku"}</MetadataListItem>
        <MetadataListItem label="Wersje reklamy">{r.versionsCount ?? 1}{r.multipleVersions ? " (kilka wariantów treści)" : ""}</MetadataListItem>
        <MetadataListItem label="Zasięg w UE">{reachText(c.reach)}</MetadataListItem>
      </MetadataList>
      {r.importNote && <Text type="supporting" color="secondary">{r.importNote}{r.importLayoutNote ? `: ${r.importLayoutNote}` : ""}</Text>}
    </Tile>
  );
}

/* 5. Twórca i zasięg. */
const REACH_LABEL = { plays: "Odtworzenia", eu_reach: "Zasięg w UE", views: "Zasięg filmu", subscribers: "Zasięg filmu" };

function CreatorTile({ c }) {
  const known = c.creator?.isSeed || c.creator?.seed ? "znany (monitorowany)" : c.creator?.isNewInScan ? "nowy w skanie" : "znany";
  const disc = c.discovery[0] || c.creator?.discoveries?.[0];
  return (
    <Tile title="Twórca i zasięg">
      <MetadataList>
        <MetadataListItem label="Kanał">{c.creatorName || "—"} · {known}</MetadataListItem>
        <MetadataListItem label={REACH_LABEL[c.reach?.metric] || "Zasięg filmu"}>{reachText(c.reach)}</MetadataListItem>
        {c.creator?.reach && <MetadataListItem label="Zasięg kanału">{reachText(c.creator.reach)}</MetadataListItem>}
        <MetadataListItem label="Jak odkryto">{disc ? discoveryLines([disc])[0] : "Droga odkrycia sprzed rozszerzenia kontraktu"}</MetadataListItem>
        <MetadataListItem label="Opublikowano">{c.publishedAt ? fmtDate(c.publishedAt) : c.publishedAtDerived?.value ? <HStack gap={1} vAlign="center" wrap="wrap"><Text>≈ {fmtDate(c.publishedAtDerived.value)}</Text><Token size="sm" color="yellow" label="data szacowana" description={c.publishedAtDerived.note || undefined} /><Text type="supporting" color="secondary">{c.publishedAtDerived.note || "Szacunek, nie data z platformy."}</Text></HStack> : "—"}</MetadataListItem>
      </MetadataList>
    </Tile>
  );
}


function describeHistory(h) {
  const kind = h.changeKind || (h.action === "capture" ? "content" : h.action);
  const d = h.details || {};
  const label = HISTORY_KIND[kind] || h.action;
  const resolution = kind === "decision" && d.resolution ? `: ${RESOLUTION_LABEL[d.resolution] || d.resolution}` : "";
  const extra = kind === "analysis" && (d.rulesFrom || d.scoreFrom != null) ? `: ${d.scoreFrom != null ? `wynik ${d.scoreFrom} → ${d.scoreTo}` : "przeliczono"}` : d.version && kind === "content" ? ` (wersja ${d.version})` : "";
  return { label: `${label}${resolution}${extra}`, note: kind === "content" ? "" : h.note };
}

/* „Więcej”: historia, punktacja, źródło, surowe dane; domyślnie zamknięte. */
function MoreTabs({ c }) {
  const [tab, setTab] = useState("history");
  const entries = [...c.history].reverse();
  const counter = c.counter.filter((e) => e.counterKind !== "neutral_context" && e.effect).slice(0, 4);
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
        {c.score?.value != null ? <Text>Siła przesłanki: {c.score.value} z 100 pkt ({BANDS[c.score.band] || "bez pasma"}).</Text> : <Text color="secondary">Brak wyliczonej siły{c.score?.notComputableReason ? `: ${c.score.notComputableReason}` : ""}.</Text>}
        {c.score?.components?.length > 0 && (
          <Table idKey="label" density="compact" data={c.score.components.map((x) => (Array.isArray(x) ? { label: x[0], points: x[1] } : { label: x.label || x.id, points: x.points }))} columns={[
            { key: "label", header: "Składnik", width: proportional(4, { minWidth: 140 }) },
            { key: "points", header: "Pkt", align: "end", width: pixel(60) },
          ]} />
        )}
        <Text type="supporting" color="secondary">{SCALE_NOTE}</Text>
        {c.alternative && <Text type="supporting">Możliwe wyjaśnienie: {c.alternative}</Text>}
        {counter.map((e, i) => <Text key={e.id || i} type="supporting">Kontrargument: {e.text ? `„${e.text}” ` : ""}{e.effect}</Text>)}
      </VStack>
    ),
    source: (
      <VStack gap={2}>
        <MetadataList>
          <MetadataListItem label="Pochodzenie">{originLabel(c.origin, c.observedAt)}</MetadataListItem>
          <MetadataListItem label="Odczytano">{fmtDateTime(c.observedAt)}</MetadataListItem>
          {c.discovery.map((d, i) => <MetadataListItem key={i} label={i === 0 ? "Droga odkrycia" : ""}>{discoveryLines([d])[0]}</MetadataListItem>)}
        </MetadataList>
        {c.raw.description && (
          <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">{c.platform === "youtube" ? "Pełny opis filmu" : "Pełny podpis lub tekst"}</Text>}>
            <Blockquote>{c.raw.description}</Blockquote>
          </Collapsible>
        )}
      </VStack>
    ),
    raw: (
      <MetadataList>
        <MetadataListItem label="Identyfikator">{c.id}</MetadataListItem>
        <MetadataListItem label="Rewizja i wersja">{c.revision} · {c.version}</MetadataListItem>
        <MetadataListItem label="Wariant reguł">{VARIANTS[c.activeVariant] || c.activeVariant || "—"}{c.ruleVersion ? ` · ${c.ruleVersion}` : ""}</MetadataListItem>
        <MetadataListItem label="Skan">{c.discovery[0]?.scanId || c.firstScanId || "—"}</MetadataListItem>
        {c.url && <MetadataListItem label="Adres">{c.url}</MetadataListItem>}
      </MetadataList>
    ),
  };
  return (
    <Collapsible defaultIsOpen={false} trigger={<Text weight="semibold">Więcej: historia, punktacja, źródło, surowe dane</Text>}>
      <VStack gap={2} padding={2}>
        <TabList role="tablist" size="sm" value={tab} onChange={setTab}>
          <Tab value="history" label="Historia" panelId="more-panel" />
          <Tab value="score" label="Punktacja" panelId="more-panel" />
          <Tab value="source" label="Źródło" panelId="more-panel" />
          <Tab value="raw" label="Surowe dane" panelId="more-panel" />
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

export function CaseDetail({ c, headingRef, onBack, onSaved, narrow }) {
  const proof = proofOf(c);
  const isAd = c.module === "M2" && !!c.raw.adBody;
  const isM2Card = c.module === "M2" && !isAd && !!c.raw.m2Card && c.checks.length > 0;
  const isM3Card = c.module === "M3" && !!c.raw.identity && c.checks.length > 0;
  const openUrl = isM2Card || isM3Card ? safeUrl(c.url) : proof?.url;
  const band = c.score?.value != null ? `${BANDS[c.score.band] || ""} · ${c.score.value}/100` : null;
  const firm = c.relationship?.firmName;
  const header = (
    <LayoutHeader padding={0} hasDivider>
      <VStack gap={1.5} padding={narrow ? 2 : 3}>
        <HStack gap={2} hAlign="between" vAlign="center" wrap="wrap">
          <HStack gap={1} wrap="wrap" vAlign="center">
            {band && <Token size="sm" color={c.score.band === "strong" ? "red" : c.score.band === "moderate" ? "orange" : "gray"} label={`Siła: ${band}`} />}
            {!narrow && <Token size="sm" color="gray" label={STATUS[c.status] || c.status} />}
            {!narrow && <OriginToken origin={c.origin} at={c.observedAt} />}
            <ImportToken c={c} />
            <RecalcToken c={c} />
            <ReReviewToken c={c} />
          </HStack>
          {onBack && <Button label="Wróć do listy" variant="ghost" size="sm" onClick={onBack} />}
        </HStack>
        <Heading level={2} ref={headingRef} tabIndex={-1}>{c.title}</Heading>
        <Text type="supporting" color="secondary" maxLines={1}>{isM2Card ? m2Subtitle(c) : isM3Card ? m3Subtitle(c) : [c.creatorName, firm].filter(Boolean).join(" · ")}</Text>
        <HStack gap={2} wrap="wrap">
          {openUrl && <Button label={isM2Card ? "Otwórz stronę" : isM3Card ? "Otwórz ofertę" : !isYoutube(openUrl) ? "Otwórz źródło" : proof.start != null ? `Otwórz w filmie od ${clock(proof.start)}` : "Otwórz w filmie"} size="sm" variant="primary" href={openUrl} target="_blank" />}
          {!narrow && <Button label="Decyzja" size="sm" onClick={jump("sekcja-decyzja")} />}
        </HStack>
      </VStack>
    </LayoutHeader>
  );
  const body = (
    <VStack gap={3} padding={narrow ? 2 : 3}>
      {c.origin === "synthetic" || c.origin === "upload" ? (
        <Banner status="info" title={c.origin === "upload" ? "Plik operatora" : "Materiał syntetyczny"} description="Nie pochodzi z bieżącego rynku." />
      ) : null}
      {c.needsRecalc && c.module === "M1" && <Banner status="warning" title="Wynik ze starszej wersji analizy" description={c.needsRecalcReason || "Wymaga przeliczenia."} />}
      {isM2Card ? (
        <>
          <WhyTile c={c} />
          <RisksTile c={c} narrow={narrow} />
          <Grid columns={{ minWidth: 300, max: 2 }} gap={3}><M2ScopeTile c={c} /><M2FirmTile c={c} /></Grid>
          <DecisionTile c={c} onSaved={onSaved} key={c.id} />
        </>
      ) : isM3Card ? (
        <>
          <WhyTile c={c} />
          <AxesTile c={c} narrow={narrow} />
          <Grid columns={{ minWidth: 300, max: 2 }} gap={3}>
            <PermissionsTile c={c} />
            <VStack gap={3}><M3ScopeTile c={c} /><MissingTile c={c} /></VStack>
          </Grid>
          <DecisionTile c={c} onSaved={onSaved} key={c.id} />
        </>
      ) : (
      <Grid columns={{ minWidth: 300, max: 2 }} gap={3}>
        <WhyTile c={c} />
        {isAd ? <AdTile c={c} /> : <MomentsTile c={c} />}
        <ScopeTile c={c} />
        <FirmTile c={c} />
        {!isAd && <CreatorTile c={c} />}
        <DecisionTile c={c} onSaved={onSaved} key={c.id} />
      </Grid>
      )}
      <MoreTabs c={c} />
    </VStack>
  );
  const footer = narrow && (
    <LayoutFooter padding={2} hasDivider>
      <HStack gap={2}>
        <Button label={isAd ? "Treść" : isM2Card ? "Kryteria" : isM3Card ? "Cechy" : "Momenty"} onClick={jump("sekcja-momenty")} />
        <Button label="Decyzja" variant="primary" onClick={jump("sekcja-decyzja")} />
      </HStack>
    </LayoutFooter>
  );
  return <Layout height="fill" header={header} content={<LayoutContent padding={0} isScrollable>{body}</LayoutContent>} footer={footer || undefined} />;
}
