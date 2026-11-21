// Listy kolejek: zwarte tabele czytające wyłącznie podsumowania z API (bez dociągania kart), stronicowanie „Pokaż więcej”,
// filtry w adresie (platforma i moduł jako rząd przełączników, kanał, data z wyborem pola, pasmo) i raport CSV/JSON.
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
import { ToggleButton } from "@astryxdesign/core/ToggleButton";
import { Token } from "@astryxdesign/core/Token";
import { reportUrl } from "./api.js";
import { PLATFORMS, activeCount } from "./filters.js";
import { BANDS, COMPLETE_REASON, DISCLOSURE_ROW, DISCLOSURE_WHERE, MODULES, clock, fmtDay, platformLabel, safeUrl } from "./labels.js";
import { ExternalLink, Lines, OriginToken, ProofLink, RecalcToken, ReReviewToken, Strength } from "./parts.jsx";
import { hashFor } from "./route.js";
import { rowReason } from "./model.js";

const MODULE_ROW = [{ value: "all", label: "Wszystkie" }, ...Object.keys(MODULES).map((id) => ({ value: id, label: id }))];

function Toggles({ label, value, options, onChange }) {
  return (
    <HStack gap={1} vAlign="center" wrap="wrap" role="group" aria-label={label}>
      <Text type="supporting" color="secondary">{label}</Text>
      {options.map((o) => (
        <ToggleButton key={o.value} size="sm" label={o.label} isPressed={value === o.value} onPressedChange={() => onChange(o.value)}>{o.label}</ToggleButton>
      ))}
    </HStack>
  );
}

/** Filtry nad listą. `report` = { module, queue }: przycisk „Pobierz raport” z aktualnymi filtrami. */
export function Filters({ filters, update, reset, showSection, report }) {
  const count = activeCount(filters);
  const hasDates = !!(filters.from || filters.to);
  const more = (
    <Grid columns={{ minWidth: 150, max: 5 }} gap={2}>
      <Selector label="Data" value={filters.dateField} onChange={update("dateField")}
        options={[{ label: "Odczytano", value: "observedAt" }, { label: "Opublikowano", value: "publishedAt" }]} />
      <DateInput label={filters.dateField === "publishedAt" ? "Opublikowano od" : "Odczytano od"} value={filters.from || undefined} onChange={update("from")} />
      <DateInput label={filters.dateField === "publishedAt" ? "Opublikowano do" : "Odczytano do"} value={filters.to || undefined} onChange={update("to")} />
      <Selector label="Siła przesłanki" value={filters.band} onChange={update("band")}
        options={[{ label: "Dowolna", value: "all" }, { label: "Mocna", value: "strong" }, { label: "Średnia", value: "moderate" }, { label: "Słaba", value: "weak" }]} />
      {showSection && <Selector label="Rejestr" value={filters.section} onChange={update("section")}
        options={[{ label: "Wszystkie", value: "all" }, { label: "Potwierdzone", value: "confirmed" }, { label: "Do potwierdzenia", value: "candidate" }]} />}
    </Grid>
  );
  return (
    <VStack gap={1.5}>
      <HStack gap={2} vAlign="center" wrap="wrap">
        <TextInput label="Szukaj po kanale lub tytule" isLabelHidden type="search" startIcon="search" placeholder="Szukaj po kanale lub tytule" width="min(100%, 28rem)" value={filters.q} onChange={update("q")} />
        {report && (
          <HStack gap={1}>
            <Button label="Pobierz raport" size="sm" href={reportUrl({ ...report, format: "csv", filters })} tooltip="Plik CSV z aktualnymi filtrami (UTF-8, Excel)" />
            <Button label="JSON" size="sm" variant="ghost" href={reportUrl({ ...report, format: "json", filters })} target="_blank" tooltip="Ten sam raport jako JSON" />
          </HStack>
        )}
      </HStack>
      <Toggles label="Platforma" value={filters.source} onChange={(v) => update("source")(v === filters.source ? "all" : v)}
        options={[{ value: "all", label: "Wszystkie" }, ...PLATFORMS]} />
      <Toggles label="Moduł" value={filters.module} onChange={update("module")} options={MODULE_ROW} />
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Collapsible defaultIsOpen={hasDates || filters.band !== "all" || filters.section !== "all"} trigger={<Text type="supporting">Data, siła{showSection ? ", rejestr" : ""}</Text>}>
          <VStack padding={2}>{more}</VStack>
        </Collapsible>
        {count > 0 && <Button variant="ghost" size="sm" label={`Wyczyść filtry (${count})`} onClick={reset} />}
      </HStack>
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

const sub = (c) => [c.creatorName, platformLabel(c.platform), c.publishedAt && fmtDay(c.publishedAt)].filter(Boolean).join(" · ");

/** Data w wierszu: opublikowano, a gdy platforma jej nie podaje (np. TikTok), data odczytu z oznaczeniem. */
function When({ c }) {
  return c.publishedAt
    ? <Text type="supporting">{fmtDay(c.publishedAt)}</Text>
    : <VStack gap={0}><Text type="supporting">{fmtDay(c.observedAt)}</Text><Text type="supporting" color="secondary">odczyt</Text></VStack>;
}

function incompleteReason(c) {
  if (c.needsRecalc) return "Starsza wersja analizy: wymaga przeliczenia.";
  return COMPLETE_REASON[c.completeReason] || c.reason || "Brak wystarczającego zakresu do oceny.";
}

function reasonFor(kind, c) {
  if (kind === "review") return rowReason(c);
  if (kind === "incomplete") return incompleteReason(c);
  if (kind === "closed") return c.lastDecision ? c.lastDecision.note || "Decyzja zapisana." : rowReason(c);
  return c.reason || "Materiał demonstracyjny.";
}
const REASON_HEADER = { review: "Dlaczego tutaj", incomplete: "Czego brakuje", closed: "Decyzja", demo: "Opis" };

/** Jak ujawniono: rodzaj, miejsce (z czasem w mowie) i cytat z API. */
export function disclosureLine(d) {
  if (!d) return null;
  if (d.state === "not_found_in_scope") return { title: "nie znaleziono w zbadanym zakresie", text: null };
  const kind = DISCLOSURE_ROW[d.kind] || "oznaczenie";
  const where = [DISCLOSURE_WHERE[d.where] || DISCLOSURE_WHERE[d.state], d.atSec != null ? clock(d.atSec) : null].filter(Boolean).join(" ");
  return { title: `${kind}${where ? `, ${where}` : ""}`, text: d.text || null };
}

/** Wiersz zwarty: film i kanał | powód w jednej linii | siła | dowód. */
export function CaseList({ items, tab, narrow, selectedId, filters, onOpen, emptyState }) {
  const kind = tab === "review" || tab === "incomplete" || tab === "closed" || tab === "demo" ? tab : "review";
  const props = { route: tab, filters, selectedId, onOpen };
  if (narrow) {
    return (
      <List density="spacious" hasDividers>
        {items.length === 0 ? emptyState : items.map((c) => (
          <Item key={c.id} density="spacious" isSelected={c.id === selectedId} labelLines={2} descriptionLines={3}
            href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[c.score?.value != null ? `Siła: ${BANDS[c.score.band] || ""} · ${c.score.value}/100` : null, sub(c), reasonFor(kind, c)]} />} />
        ))}
      </List>
    );
  }
  const columns = [
    { key: "title", header: "Materiał i kanał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} {...props} active={c.id === selectedId} />
        <Text type="supporting" color="secondary" maxLines={1}>{sub(c)}</Text>
        <HStack gap={1} wrap="wrap">{c.origin !== "replay" && <OriginToken origin={c.origin} at={c.observedAt} />}<RecalcToken c={c} /><ReReviewToken c={c} /></HStack>
      </VStack>
    ) },
    { key: "reason", header: REASON_HEADER[kind], width: proportional(3, { minWidth: 150 }), renderCell: (c) => <Text maxLines={1} type="supporting">{reasonFor(kind, c)}</Text> },
    ...(kind === "review" || kind === "closed" ? [{ key: "strength", header: "Siła", width: pixel(104), renderCell: (c) => <Strength c={c} /> }] : []),
    ...(kind === "review" ? [{ key: "proof", header: "Dowód", width: pixel(104), renderCell: (c) => <ProofLink c={c} /> }] : []),
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

/** Rejestr reklam: materiał | jak ujawniono (rodzaj, miejsce, cytat) | podstawa wpisu | kiedy. Wszystko z podsumowania API. */
export function RegisterTable({ items, filters, onOpen, emptyState }) {
  const columns = [
    { key: "title", header: "Materiał i kanał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} route="register" filters={filters} onOpen={onOpen} />
        <Text type="supporting" color="secondary" maxLines={1}>{[c.creatorName, platformLabel(c.platform)].filter(Boolean).join(" · ")}</Text>
      </VStack>
    ) },
    { key: "disclosure", header: "Jak ujawniono", width: proportional(3, { minWidth: 200 }), renderCell: (c) => {
      const d = disclosureLine(c.disclosure);
      return d ? (
        <VStack gap={0.5}>
          <Text weight="medium">{d.title}</Text>
          {d.text && <Text type="supporting" color="secondary" maxLines={2}>„{d.text}”</Text>}
        </VStack>
      ) : <Text type="supporting" color="secondary">—</Text>;
    } },
    { key: "basis", header: "Podstawa wpisu", width: proportional(3, { minWidth: 180 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <Text type="supporting" maxLines={2}>{c.registryInfo?.summary || c.reason || "—"}</Text>
        {c.registry === "candidate" && <Token size="sm" color="yellow" label="do potwierdzenia" />}
      </VStack>
    ) },
    { key: "date", header: "Kiedy", width: pixel(84), renderCell: (c) => <When c={c} /> },
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

export function RegisterList({ items, filters, tab }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => {
        const d = disclosureLine(c.disclosure);
        return (
          <Item key={c.id} density="spacious" labelLines={2} descriptionLines={3} href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[sub(c), d ? `${d.title}${d.text ? `: „${d.text}”` : ""}` : null, c.registryInfo?.summary]} />} />
        );
      })}
    </List>
  );
}

export function OffersTable({ items, module, filters, onOpen, emptyState }) {
  const isM2 = module === "M2";
  const tab = isM2 ? "m2" : "m3";
  const columns = [
    { key: "page", header: isM2 ? "Strona" : "Oferta", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} route={tab} filters={filters} onOpen={onOpen} />
        {safeUrl(c.url) && <ExternalLink url={c.url}>{new URL(c.url, "http://x/").host}</ExternalLink>}
      </VStack>
    ) },
    { key: "firm", header: isM2 ? "Firma" : "Podmiot", width: proportional(2, { minWidth: 110 }), renderCell: (c) => <Text maxLines={1}>{c.creatorName || "—"}</Text> },
    { key: "strength", header: "Siła", width: pixel(104), renderCell: (c) => <Strength c={c} /> },
    { key: "state", header: "Stan", width: pixel(150), renderCell: (c) => (c.needsRecalc ? <RecalcToken c={c} /> : <Text type="supporting">{c.route ? ({ refer: "do sprawdzenia", complete: "uzupełnij dane", no_signal: "bez przesłanki", insufficient: "za mało danych" })[c.route] || c.route : "—"}</Text>) },
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

export function OffersList({ items, filters, tab }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => (
        <Item key={c.id} density="spacious" labelLines={2} descriptionLines={3} href={hashFor(tab, { caseId: c.id, filters })}
          label={c.title} description={<Lines lines={[c.creatorName, c.score?.value != null ? `${BANDS[c.score.band] || ""} · ${c.score.value}/100` : null]} />} />
      ))}
    </List>
  );
}
