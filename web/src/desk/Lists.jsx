import React, { useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { DateInput } from "@astryxdesign/core/DateInput";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Link } from "@astryxdesign/core/Link";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { Selector } from "@astryxdesign/core/Selector";
import { pixel, proportional, Table, useTableRowExpansion } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { Token } from "@astryxdesign/core/Token";
import { Blockquote } from "@astryxdesign/core/Blockquote";
import { EMPTY_FILTERS, activeCount } from "./filters.js";
import { BANDS, MODULES, REL_STATUS, fmtDay, fmtDate, fmtDateTime, safeUrl } from "./labels.js";
import { hashFor } from "./route.js";
import { DisclosureProof, ExternalLink, Lines, OriginToken, ProofLink, RecalcToken, ReReviewToken, Strength, disclosureText, locatorText, proofOf } from "./parts.jsx";
import { rowReason } from "./model.js";

export function Filters({ filters, sources, update, reset }) {
  const count = activeCount(filters);
  const body = (
    <Grid columns={{ minWidth: 150, max: 6 }} gap={2}>
      <Selector label="Moduł" value={filters.module} onChange={update("module")}
        options={[{ label: "Wszystkie moduły", value: "all" }, ...Object.entries(MODULES).map(([id, label]) => ({ value: id, label: `${id} · ${label}` }))]} />
      <Selector label="Źródło" value={filters.source} onChange={update("source")}
        options={[{ label: "Wszystkie źródła", value: "all" }, ...sources.map((s) => ({ value: s, label: s }))]} />
      <Selector label="Siła przesłanki" value={filters.risk} onChange={update("risk")}
        options={[{ label: "Dowolna", value: "all" }, ...Object.entries(BANDS).map(([value, label]) => ({ value, label })), { label: "Bez oceny", value: "none" }]} />
      <DateInput label="Opublikowano od" value={filters.from || undefined} onChange={update("from")} />
      <DateInput label="Opublikowano do" value={filters.to || undefined} onChange={update("to")} />
      <HStack vAlign="end"><Button variant="ghost" label="Wyczyść filtry" isDisabled={!count} onClick={reset} /></HStack>
    </Grid>
  );
  return (
    <VStack gap={2}>
      <TextInput label="Szukaj materiału, kanału lub firmy" isLabelHidden type="search" startIcon="search" placeholder="Szukaj materiału, kanału lub firmy" value={filters.q} onChange={update("q")} />
      <Collapsible defaultIsOpen={count > 0} trigger={<Text type="supporting">Filtry{count ? ` (${count})` : ""}: moduł, źródło, siła, data</Text>}>
        <VStack padding={2}>{body}</VStack>
      </Collapsible>
    </VStack>
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

function incompleteReason(c) {
  if (c.needsRecalc) return c.needsRecalcReason ? `Starsza wersja analizy: ${c.needsRecalcReason}.` : "Starsza wersja analizy.";
  const gaps = c.coverage?.gaps?.map((g) => g.reason).filter(Boolean);
  if (c.route === "complete" || c.route === "insufficient") return [c.reason, gaps?.length ? `Brakuje: ${gaps.join("; ")}` : null].filter(Boolean).join(" ") || "Brak wystarczającego zakresu do oceny.";
  if (gaps?.length) return `Brakuje: ${gaps.join("; ")}. Wniosek o braku oznaczenia wstrzymany.`;
  return "Zakres analizy nieznany.";
}

const REASON = {
  review: rowReason,
  incomplete: incompleteReason,
  closed: (c) => c.lastDecision ? `${c.lastDecision.note || "Decyzja zapisana."}` : rowReason(c),
  demo: (c) => c.reason || c.summary || "Materiał demonstracyjny.",
};
const REASON_HEADER = { review: "Dlaczego tutaj", incomplete: "Czego brakuje", closed: "Decyzja", demo: "Opis" };

function titleCell(c, props) {
  return (
    <VStack gap={0.5}>
      <TitleLink c={c} {...props} active={c.id === props.selectedId} />
      <Text type="supporting" color="secondary" maxLines={1}>{[c.creatorName, c.platform, c.publishedAt && fmtDay(c.publishedAt)].filter(Boolean).join(" · ")}</Text>
      <HStack gap={1} wrap="wrap"><OriginToken origin={c.origin} /><RecalcToken c={c} /><ReReviewToken c={c} /></HStack>
    </VStack>
  );
}

/** Lista kolejki: tabela na desktopie, List/Item na telefonie. */
export function CaseList({ items, tab, narrow, selectedId, filters, onOpen, emptyState }) {
  const kind = tab === "review" || tab === "incomplete" || tab === "closed" || tab === "demo" ? tab : "review";
  const reasonOf = REASON[kind];
  const props = { route: tab, filters, selectedId, onOpen };
  if (narrow) {
    return (
      <List density="spacious" hasDividers>
        {items.length === 0 ? emptyState : items.map((c) => (
          <Item key={c.id} density="spacious" isSelected={c.id === selectedId} labelLines={3} descriptionLines={3}
            href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[c.score?.value != null ? `Siła: ${BANDS[c.score.band] || ""}, ${c.score.value} z 100 pkt` : null, [c.creatorName, c.platform, c.publishedAt && fmtDay(c.publishedAt)].filter(Boolean).join(" · "), reasonOf(c)]} />} />
        ))}
      </List>
    );
  }
  const columns = [
    { key: "title", header: "Materiał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => titleCell(c, props) },
    { key: "reason", header: REASON_HEADER[kind], width: proportional(3, { minWidth: 170 }), renderCell: (c) => <Text maxLines={3} type="supporting">{reasonOf(c)}</Text> },
    ...(kind === "review" || kind === "closed" ? [{ key: "strength", header: "Siła sygnału", width: pixel(130), renderCell: (c) => <Strength c={c} /> }] : []),
    ...(kind === "review" ? [{ key: "proof", header: "Dowód", width: pixel(110), renderCell: (c) => <ProofLink c={c} /> }] : []),
  ];
  return <Table idKey="id" columns={columns} data={items} density="balanced" hasHover verticalAlign="top" emptyState={emptyState} />;
}

function ExpandedRegister({ c, onOpen }) {
  const proof = proofOf(c);
  return (
    <VStack gap={2} padding={3}>
      {c.relationship?.disclosure?.text && <Blockquote>{c.relationship.disclosure.text}</Blockquote>}
      <HStack gap={3} wrap="wrap" vAlign="center">
        {proof?.field && <Text type="supporting" color="secondary">{locatorText(proof.field)}</Text>}
        <ExternalLink url={c.url}>Oryginał</ExternalLink>
        <Button size="sm" label="Otwórz kartę" onClick={() => onOpen(c.id)} />
      </HStack>
      <Text type="supporting" color="secondary">Jawna współpraca nie jest uchybieniem. Do kontroli trafia dopiero osobna, udokumentowana przesłanka.</Text>
    </VStack>
  );
}

function useExpandable(getLabel, render) {
  const [open, setOpen] = useState(() => new Set());
  return useTableRowExpansion({
    expandedKeys: open,
    onToggle: (key) => setOpen((set) => {
      const next = new Set(set);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    }),
    getRowKey: (c) => c.id,
    getRowLabel: getLabel,
    renderExpanded: render,
  });
}

function controlText(c) {
  if (c.registry === "candidate") return "do potwierdzenia: bez oznaczenia w zbadanym zakresie";
  if (c.route === "refer") return "także w kontroli";
  return "bez osobnego sygnału";
}

export function RegisterTable({ items, onOpen, emptyState }) {
  const plugin = useExpandable((c) => c.title, (c) => <ExpandedRegister c={c} onOpen={onOpen} />);
  const columns = [
    { key: "date", header: "Publikacja", width: pixel(110), renderCell: (c) => <Text type="supporting">{fmtDay(c.publishedAt)}</Text> },
    { key: "creator", header: "Kanał", width: proportional(2, { minWidth: 130 }), renderCell: (c) => <Text maxLines={2}>{c.creatorName}</Text> },
    { key: "title", header: "Materiał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => <Text maxLines={2} weight="semibold">{c.title}</Text> },
    { key: "firm", header: "Firma", width: proportional(1.5, { minWidth: 120 }), renderCell: (c) => <VStack gap={0.5}><Text>{c.relationship?.firmName || "—"}</Text>{c.relationship?.firm?.crossBorder === true && <Text type="supporting" color="secondary">transgraniczna</Text>}</VStack> },
    { key: "rel", header: "Relacja", width: proportional(2, { minWidth: 130 }), renderCell: (c) => <Text type="supporting">{REL_STATUS[c.relationship?.status] || "nieustalona"}{c.relationship?.basis ? ` · ${c.relationship.basis}` : ""}</Text> },
    { key: "disclosure", header: "Typ ujawnienia", width: proportional(3, { minWidth: 190 }), renderCell: (c) => <DisclosureProof c={c} /> },
    { key: "control", header: "Kontrola", width: proportional(2, { minWidth: 130 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{controlText(c)}</Text> },
  ];
  return <Table idKey="id" columns={columns} data={items} density="balanced" hasHover verticalAlign="top" plugins={{ expansion: plugin }} emptyState={emptyState} />;
}

export function RegisterList({ items, onOpen, filters, tab }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => (
        <Item key={c.id} density="spacious" labelLines={3} descriptionLines={4} href={hashFor(tab, { caseId: c.id, filters })}
          label={c.title}
          description={<Lines lines={[`${c.creatorName} · ${c.relationship?.firmName || "firma nieustalona"} · ${fmtDay(c.publishedAt)}`, `Oznaczenie: ${disclosureText(c)}`]} />} />
      ))}
    </List>
  );
}

const CHECK_STATE = { obserwacja: "obserwacja", "brak danych": "brak danych", "nie dotyczy": "nie dotyczy" };

function ExpandedOffer({ c, onOpen }) {
  const strongest = c.checks.filter((x) => x.state === "obserwacja").slice(0, 3);
  return (
    <VStack gap={2} padding={3}>
      {c.summary && <Text>{c.summary}</Text>}
      {strongest.map((x) => (
        <VStack gap={0.5} key={x.id}>
          <Text weight="semibold">{x.id}. {x.label}: {CHECK_STATE[x.state] || x.state}</Text>
          <Text type="supporting" color="secondary">{x.evidence}</Text>
        </VStack>
      ))}
      {c.checks.length > 0 && <Text type="supporting" color="secondary">Brak danych nie jest oceną: kryterium bez pomiaru zostaje widoczne jako „brak danych”.</Text>}
      <HStack gap={3} wrap="wrap" vAlign="center">
        <ExternalLink url={c.url}>Otwórz stronę</ExternalLink>
        <Button size="sm" label="Otwórz kartę" onClick={() => onOpen(c.id)} />
      </HStack>
    </VStack>
  );
}

export function OffersTable({ items, module, onOpen, emptyState }) {
  const plugin = useExpandable((c) => c.title, (c) => <ExpandedOffer c={c} onOpen={onOpen} />);
  const isM2 = module === "M2";
  const columns = [
    { key: "firm", header: isM2 ? "Firma" : "Podmiot", width: proportional(2, { minWidth: 130 }), renderCell: (c) => <VStack gap={0.5}><Text weight="semibold">{c.raw.brand || c.creatorName || "—"}</Text><HStack><OriginToken origin={c.origin} /></HStack></VStack> },
    { key: "page", header: isM2 ? "Strona" : "Oferta", width: proportional(3, { minWidth: 170 }), renderCell: (c) => <VStack gap={0.5}><Text maxLines={2}>{c.title}</Text><ExternalLink url={c.url}>{safeUrl(c.url) ? new URL(c.url, "http://x/").host : "adres"}</ExternalLink></VStack> },
    ...(isM2
      ? [
          { key: "when", header: "Odczyt", width: pixel(150), renderCell: (c) => <Text type="supporting">{fmtDateTime(c.observedAt)}</Text> },
          { key: "checks", header: "Kryteria z 19", width: proportional(3, { minWidth: 190 }), renderCell: (c) => <Text type="supporting">{c.checkCounts ? Object.entries(c.checkCounts).map(([k, n]) => `${k} ${n}`).join(" · ") : "—"}</Text> },
        ]
      : [
          { key: "kind", header: "Charakter usługi", width: proportional(2, { minWidth: 150 }), renderCell: (c) => <Text type="supporting">{c.semantic?.label || c.summary || "nieustalony"}</Text> },
          { key: "reg", header: "Uprawnienia", width: proportional(2, { minWidth: 150 }), renderCell: (c) => <Text type="supporting">{c.title.includes("tożsamości") ? "tożsamość do ustalenia" : c.raw.brand?.includes("BOŚ") ? "podmiot uprawniony: kontrola zakresu" : "status uprawnień: sprawdź w szczególe"}</Text> },
        ]),
    { key: "state", header: "Stan", width: pixel(150), renderCell: (c) => (c.needsRecalc ? <RecalcToken c={c} /> : <Text type="supporting">{c.legacyScore != null ? `${c.legacyScore} pkt (reguły ${c.raw.rulesVersion?.replace("investwatch-rules-pl-", "") || "?"})` : "—"}</Text>) },
  ];
  return <Table idKey="id" columns={columns} data={items} density="balanced" hasHover verticalAlign="top" plugins={{ expansion: plugin }} emptyState={emptyState} />;
}

export function OffersList({ items, filters, tab }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => (
        <Item key={c.id} density="spacious" labelLines={3} descriptionLines={3} href={hashFor(tab, { caseId: c.id, filters })}
          label={c.title} description={<Lines lines={[c.raw.brand || c.creatorName, c.summary]} />} />
      ))}
    </List>
  );
}
