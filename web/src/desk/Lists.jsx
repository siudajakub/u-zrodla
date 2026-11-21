// Listy kolejek: zwarte tabele (jedna linia powodu), stronicowanie „Pokaż więcej”, filtry w adresie.
import React from "react";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { DateInput } from "@astryxdesign/core/DateInput";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Link } from "@astryxdesign/core/Link";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { Selector } from "@astryxdesign/core/Selector";
import { pixel, proportional, Table } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { activeCount } from "./filters.js";
import { BANDS, MODULES, fmtDay, safeUrl } from "./labels.js";
import { hashFor } from "./route.js";
import { DisclosureProof, ExternalLink, Lines, OriginToken, ProofLink, RecalcToken, ReReviewToken, Strength, proofOf } from "./parts.jsx";
import { rowReason } from "./model.js";

export function Filters({ filters, sources, update, reset, showSection }) {
  const count = activeCount(filters);
  const body = (
    <Grid columns={{ minWidth: 150, max: 6 }} gap={2}>
      <Selector label="Moduł" value={filters.module} onChange={update("module")}
        options={[{ label: "Wszystkie moduły", value: "all" }, ...Object.entries(MODULES).map(([id, label]) => ({ value: id, label: `${id} · ${label}` }))]} />
      <Selector label="Źródło" value={filters.source} onChange={update("source")}
        options={[{ label: "Wszystkie źródła", value: "all" }, ...sources.map((s) => ({ value: s, label: s }))]} />
      <Selector label="Siła przesłanki" value={filters.risk} onChange={update("risk")}
        options={[{ label: "Dowolna", value: "all" }, { label: "Co najmniej średnia (60 pkt)", value: "moderate" }, { label: "Co najmniej mocna (75 pkt)", value: "strong" }]} />
      {showSection && <Selector label="Rejestr" value={filters.section} onChange={update("section")}
        options={[{ label: "Wszystkie", value: "all" }, { label: "Potwierdzone", value: "confirmed" }, { label: "Do potwierdzenia", value: "candidate" }]} />}
      <DateInput label="Odczytano od" value={filters.from || undefined} onChange={update("from")} />
      <DateInput label="Odczytano do" value={filters.to || undefined} onChange={update("to")} />
      <HStack vAlign="end"><Button variant="ghost" label="Wyczyść filtry" isDisabled={!count} onClick={reset} /></HStack>
    </Grid>
  );
  return (
    <VStack gap={1}>
      <TextInput label="Szukaj materiału lub kanału" isLabelHidden type="search" startIcon="search" placeholder="Szukaj w tytule lub kanale" value={filters.q} onChange={update("q")} />
      <Collapsible defaultIsOpen={count > 0} trigger={<Text type="supporting">Filtry{count ? ` (${count})` : ""}</Text>}>
        <VStack padding={2}>{body}</VStack>
      </Collapsible>
    </VStack>
  );
}

/** Stopka listy: „Pokazano N z M” i przycisk kolejnej strony (kursor API). */
export function MoreFooter({ shown, total, hasMore, loading, onMore }) {
  if (!total) return null;
  return (
    <HStack gap={3} vAlign="center" hAlign="center" padding={2}>
      <Text type="supporting" color="secondary" role="status">Pokazano {shown} z {total}</Text>
      {hasMore && <Button label="Pokaż więcej" isLoading={loading} onClick={onMore} />}
    </HStack>
  );
}

function TitleLink({ c, route, filters, active, onOpen }) {
  const href = hashFor(route, { caseId: c.id, filters });
  return (
    <Link href={href} id={`row-${c.id}`} aria-current={active ? "true" : undefined} onClick={(event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey) return;
      event.preventDefault();
      onOpen(c.id);
    }}>
      <Text weight="semibold" maxLines={2}>{c.title}</Text>
    </Link>
  );
}

const sub = (c) => [c.creatorName, c.publishedAt && fmtDay(c.publishedAt)].filter(Boolean).join(" · ");

function incompleteReason(c) {
  if (c.needsRecalc) return "Starsza wersja analizy: wymaga przeliczenia.";
  return c.reason || "Brak wystarczającego zakresu do oceny.";
}

function reasonFor(kind, c, detail) {
  if (kind === "review") return detail?.reasons?.[0] || rowReason(detail || c);
  if (kind === "incomplete") return incompleteReason(c);
  if (kind === "closed") return c.lastDecision ? c.lastDecision.note || "Decyzja zapisana." : rowReason(c);
  return c.reason || "Materiał demonstracyjny.";
}
const REASON_HEADER = { review: "Dlaczego tutaj", incomplete: "Czego brakuje", closed: "Decyzja", demo: "Opis" };

/** Wiersz zwarty: film i kanał | powód w jednej linii | siła | dowód. */
export function CaseList({ items, tab, narrow, selectedId, filters, onOpen, emptyState, details }) {
  const kind = tab === "review" || tab === "incomplete" || tab === "closed" || tab === "demo" ? tab : "review";
  const props = { route: tab, filters, selectedId, onOpen };
  const detailOf = (c) => details?.get(c.id);
  if (narrow) {
    return (
      <List density="spacious" hasDividers>
        {items.length === 0 ? emptyState : items.map((c) => (
          <Item key={c.id} density="spacious" isSelected={c.id === selectedId} labelLines={2} descriptionLines={3}
            href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[c.score?.value != null ? `Siła: ${BANDS[c.score.band] || ""} · ${c.score.value}/100` : null, sub(c), reasonFor(kind, c, detailOf(c))]} />} />
        ))}
      </List>
    );
  }
  const columns = [
    { key: "title", header: "Film i kanał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} {...props} active={c.id === selectedId} />
        <Text type="supporting" color="secondary" maxLines={1}>{sub(c)}</Text>
        <HStack gap={1} wrap="wrap">{c.origin !== "replay" && <OriginToken origin={c.origin} at={c.observedAt} />}<RecalcToken c={c} /><ReReviewToken c={c} /></HStack>
      </VStack>
    ) },
    { key: "reason", header: REASON_HEADER[kind], width: proportional(3, { minWidth: 150 }), renderCell: (c) => <Text maxLines={1} type="supporting">{reasonFor(kind, c, detailOf(c))}</Text> },
    ...(kind === "review" || kind === "closed" ? [{ key: "strength", header: "Siła", width: pixel(104), renderCell: (c) => <Strength c={c} /> }] : []),
    ...(kind === "review" ? [{ key: "proof", header: "Dowód", width: pixel(104), renderCell: (c) => <ProofLink c={detailOf(c) || c} /> }] : []),
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

/** Rejestr reklam: film | kanał | firma | jak ujawniono | kiedy. Firma i sposób ujawnienia idą ze szczegółu sprawy. */
export function RegisterTable({ items, filters, onOpen, emptyState, details }) {
  const columns = [
    { key: "title", header: "Film", width: proportional(3, { minWidth: 170 }), renderCell: (c) => <TitleLink c={c} route="register" filters={filters} onOpen={onOpen} /> },
    { key: "creator", header: "Kanał", width: proportional(2, { minWidth: 110 }), renderCell: (c) => <Text maxLines={1}>{c.creatorName || "—"}</Text> },
    { key: "firm", header: "Firma", width: proportional(1.5, { minWidth: 90 }), renderCell: (c) => <Text maxLines={1}>{details.get(c.id)?.relationship?.firmName || (details.has(c.id) ? "—" : "…")}</Text> },
    { key: "disclosure", header: "Jak ujawniono", width: proportional(3, { minWidth: 200 }), renderCell: (c) => (details.get(c.id) ? <DisclosureProof c={details.get(c.id)} /> : <Text type="supporting" color="secondary">{c.reason || "…"}</Text>) },
    { key: "date", header: "Kiedy", width: pixel(84), renderCell: (c) => <Text type="supporting">{fmtDay(c.publishedAt)}</Text> },
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

export function RegisterList({ items, filters, tab, details }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => {
        const d = details.get(c.id);
        return (
          <Item key={c.id} density="spacious" labelLines={2} descriptionLines={3} href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[`${c.creatorName || "—"} · ${d?.relationship?.firmName || "firma nieustalona"} · ${fmtDay(c.publishedAt)}`, d?.registrySummary || d?.relationship?.disclosure?.summary || c.reason]} />} />
        );
      })}
    </List>
  );
}

const CHECK_STATE = { obserwacja: "obserwacja", "brak danych": "brak danych", "nie dotyczy": "nie dotyczy" };

export function OffersTable({ items, module, filters, onOpen, emptyState, details }) {
  const isM2 = module === "M2";
  const tab = isM2 ? "m2" : "m3";
  const columns = [
    { key: "page", header: isM2 ? "Strona" : "Oferta", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} route={tab} filters={filters} onOpen={onOpen} />
        {safeUrl(c.url) && <ExternalLink url={c.url}>{new URL(c.url, "http://x/").host}</ExternalLink>}
      </VStack>
    ) },
    { key: "firm", header: isM2 ? "Firma" : "Podmiot", width: proportional(2, { minWidth: 110 }), renderCell: (c) => <Text maxLines={1}>{details.get(c.id)?.raw?.brand || c.creatorName || "—"}</Text> },
    ...(isM2
      ? [{ key: "checks", header: "Kryteria z 19", width: proportional(3, { minWidth: 190 }), renderCell: (c) => { const k = details.get(c.id)?.checkCounts; return <Text type="supporting">{k ? Object.entries(k).map(([n, v]) => `${CHECK_STATE[n] || n} ${v}`).join(" · ") : "—"}</Text>; } }]
      : [{ key: "kind", header: "Charakter usługi", width: proportional(3, { minWidth: 150 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{details.get(c.id)?.semantic?.label || details.get(c.id)?.summary || "nieustalony"}</Text> }]),
    { key: "state", header: "Stan", width: pixel(150), renderCell: (c) => (c.needsRecalc ? <RecalcToken c={c} /> : <Text type="supporting">{c.score?.value != null ? `${c.score.value} pkt` : "—"}</Text>) },
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

export function OffersList({ items, filters, tab, details }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => (
        <Item key={c.id} density="spacious" labelLines={2} descriptionLines={3} href={hashFor(tab, { caseId: c.id, filters })}
          label={c.title} description={<Lines lines={[details.get(c.id)?.raw?.brand || c.creatorName, details.get(c.id)?.summary]} />} />
      ))}
    </List>
  );
}
