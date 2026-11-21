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
import { BANDS, HISTORY_KIND, RESOLUTIONS, RESOLUTION_LABEL, STATUS, VARIANTS, clock, fmtDate, fmtDateTime, fmtDayRoman, isYoutube, safeUrl } from "./labels.js";
import { ExternalLink, OriginToken, RecalcToken, ReReviewToken, SCALE_NOTE, discoveryLines, originLabel, proofOf, reachText } from "./parts.jsx";

function Tile({ title, id, children, aside }) {
  return (
    <Card padding={3} id={id}>
      <VStack gap={2}>
        <HStack gap={2} hAlign="between" vAlign="center">
          <Heading level={3}>{title}</Heading>
          {aside}
        </HStack>
        {children}
      </VStack>
    </Card>
  );
}

const isFrame = (m) => String(m.evidenceId || "").startsWith("frame-");

/* 1. Dlaczego tutaj: maksymalnie trzy punkty z API, reszta pod „pokaż wszystkie”. */
function WhyTile({ c }) {
  const reasons = c.reasons;
  const lead = reasons.slice(0, 3);
  const rest = reasons.slice(3);
  const bullets = (list) => (
    <VStack gap={1.5} role="list">
      {list.map((text, i) => (
        <HStack key={i} gap={1.5} vAlign="start" role="listitem"><Text color="secondary">•</Text><Text>{text}</Text></HStack>
      ))}
    </VStack>
  );
  return (
    <Tile title="Dlaczego tutaj" aside={c.route === "refer" ? <Token size="sm" color="blue" label="do sprawdzenia" /> : <Token size="sm" color="gray" label={c.route || "bez oceny"} />}>
      {c.needsRecalc && !c.isV2 ? (
        <Text color="secondary">Wynik ze starszej wersji analizy. Przelicz materiały, aby zobaczyć uzasadnienie.</Text>
      ) : reasons.length ? (
        <>
          {bullets(lead)}
          {rest.length > 0 && <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Pokaż wszystkie ({reasons.length})</Text>}>{bullets(rest)}</Collapsible>}
        </>
      ) : <Text>{c.reason || "Brak uzasadnienia w tej wersji analizy."}</Text>}
    </Tile>
  );
}

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
          { key: "open", header: "Otwórz", width: pixel(96), renderCell: (r) => (r.link ? <ExternalLink url={r.link}>{r.inDescription ? "Film ↗" : `od ${clock(r.start)} ↗`}</ExternalLink> : <Text type="supporting" color="secondary">—</Text>) },
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
  if (m.platformFlags) {
    const p = m.platformFlags;
    rows.push({ key: "p", name: "Oznaczenie YouTube", ok: p.paidPromotion != null, text: p.paidPromotion == null ? "nie sprawdzono" : p.paidPromotion ? "płatna promocja: tak" : "brak" });
  }
  return rows;
}

function ScopeTile({ c }) {
  const rows = coverageRows(c);
  const gaps = (c.coverage?.gaps || []).map((g) => g.reason).filter(Boolean);
  return (
    <Tile title="Co zbadano">
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
function FirmTile({ c }) {
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

/* 5. Twórca i zasięg. */
function CreatorTile({ c }) {
  const known = c.creator?.isSeed || c.creator?.seed ? "znany (monitorowany)" : c.creator?.isNewInScan ? "nowy w skanie" : "znany";
  const disc = c.discovery[0] || c.creator?.discoveries?.[0];
  return (
    <Tile title="Twórca i zasięg">
      <MetadataList>
        <MetadataListItem label="Kanał">{c.creatorName || "—"} · {known}</MetadataListItem>
        <MetadataListItem label="Zasięg filmu">{reachText(c.reach)}</MetadataListItem>
        {c.creator?.reach && <MetadataListItem label="Zasięg kanału">{reachText(c.creator.reach)}</MetadataListItem>}
        <MetadataListItem label="Jak odkryto">{disc ? discoveryLines([disc])[0] : "Droga odkrycia sprzed rozszerzenia kontraktu"}</MetadataListItem>
        <MetadataListItem label="Opublikowano">{fmtDate(c.publishedAt)}</MetadataListItem>
      </MetadataList>
    </Tile>
  );
}

/* 6. Decyzja: cztery rodzaje, notatka, ostatnia decyzja w jednym wierszu. */
function DecisionTile({ c, onSaved }) {
  const [resolution, setResolution] = useState(null);
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState(null);
  const input = useRef(null);
  async function save() {
    if (busy) return;
    if (!resolution) {
      setInvalid("Wybierz rodzaj decyzji.");
      return;
    }
    if (!note.trim()) {
      setInvalid("Wpisz uzasadnienie decyzji.");
      input.current?.focus();
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await api.decide(c, { resolution, note: note.trim() });
      setNote("");
      setResolution(null);
      setConflict(false);
      setMessage("Decyzja została zapisana.");
      await onSaved();
    } catch (e) {
      if (e.status === 409) {
        setConflict(true);
        await onSaved();
      } else setMessage(`Nie zapisano decyzji: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }
  const last = c.lastDecision;
  const lastLabel = last && (RESOLUTION_LABEL[last.resolution] || STATUS[last.status] || last.status);
  const chosen = RESOLUTIONS.find((r) => r.value === resolution);
  return (
    <Tile title="Decyzja" id="sekcja-decyzja">
      {last && <Text type="supporting" color="secondary">Ostatnia: {lastLabel}, {fmtDateTime(last.at)}{last.note ? ` · ${last.note}` : ""}</Text>}
      {conflict && <Banner status="warning" title="Sprawa zmieniła się podczas edycji" description="Pobrano bieżący stan. Szkic uzasadnienia zachowany; zapisz ponownie." />}
      <HStack gap={2} wrap="wrap" role="group" aria-label="Rodzaj decyzji">
        {RESOLUTIONS.map((r) => (
          <Button key={r.value} label={r.label} size="sm" variant={resolution === r.value ? "primary" : "secondary"} aria-pressed={resolution === r.value} onClick={() => { setResolution(r.value); setInvalid(null); }} />
        ))}
      </HStack>
      <Text type="supporting" color="secondary">{chosen ? chosen.hint : "Wybierz rodzaj decyzji."}</Text>
      <TextArea label="Uzasadnienie decyzji" ref={input} rows={2} htmlMaxLength={2000} value={note}
        onChange={(v) => { setNote(v); setInvalid(null); }}
        status={invalid ? { type: "error", message: invalid } : undefined} />
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Button label="Zapisz decyzję" variant="primary" isLoading={busy} onClick={save} />
        {message && <Text as="p" role="status" type="supporting" color="secondary">{message}</Text>}
      </HStack>
      <Text type="supporting" color="secondary">System nie rozstrzyga o naruszeniu; to Ty decydujesz, czy kierujesz materiał do kontroli.</Text>
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
          <Table idKey="label" density="compact" data={c.score.components.map(([label, points]) => ({ label, points }))} columns={[
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
          <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Pełny opis filmu</Text>}>
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
            <RecalcToken c={c} />
            <ReReviewToken c={c} />
          </HStack>
          {onBack && <Button label="Wróć do listy" variant="ghost" size="sm" onClick={onBack} />}
        </HStack>
        <Heading level={2} ref={headingRef} tabIndex={-1}>{c.title}</Heading>
        <Text type="supporting" color="secondary" maxLines={1}>{[c.creatorName, firm].filter(Boolean).join(" · ")}</Text>
        <HStack gap={2} wrap="wrap">
          {proof?.url && <Button label={proof.start != null ? `Otwórz w filmie od ${clock(proof.start)}` : isYoutube(proof.url) ? "Otwórz w filmie" : "Otwórz źródło"} size="sm" variant="primary" href={proof.url} target="_blank" />}
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
      {c.needsRecalc && <Banner status="warning" title="Wynik ze starszej wersji analizy" description={c.needsRecalcReason || "Wymaga przeliczenia."} />}
      <Grid columns={{ minWidth: 300, max: 2 }} gap={3}>
        <WhyTile c={c} />
        <MomentsTile c={c} />
        <ScopeTile c={c} />
        <FirmTile c={c} />
        <CreatorTile c={c} />
        <DecisionTile c={c} onSaved={onSaved} key={c.id} />
      </Grid>
      <MoreTabs c={c} />
    </VStack>
  );
  const footer = narrow && (
    <LayoutFooter padding={2} hasDivider>
      <HStack gap={2}>
        <Button label="Momenty" onClick={jump("sekcja-momenty")} />
        <Button label="Decyzja" variant="primary" onClick={jump("sekcja-decyzja")} />
      </HStack>
    </LayoutFooter>
  );
  return <Layout height="fill" header={header} content={<LayoutContent padding={0} isScrollable>{body}</LayoutContent>} footer={footer || undefined} />;
}
