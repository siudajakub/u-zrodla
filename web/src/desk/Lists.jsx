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
import { BANDS, COMPLETE_REASON, DISCLOSURE_ROW, DISCLOSURE_WHERE, MODULE_NAME, clock, fmtDay, moduleName, platformLabel, safeUrl } from "./labels.js";
import { ExternalLink, ImportToken, Lines, ModuleToken, OriginToken, ProofLink, RecalcToken, ReReviewToken, Strength } from "./parts.jsx";
import { hashFor } from "./route.js";
import { rowReason, shortReason } from "./model.js";

/** Przełącznik modułu z licznikami (puste liczniki, gdy API jeszcze nie odpowiedziało). */
const moduleRow = (counts) => [
  { value: "all", label: counts ? `Wszystkie ${Object.values(counts).reduce((a, b) => a + b, 0)}` : "Wszystkie" },
  ...Object.keys(MODULE_NAME).map((id) => ({ value: id, label: counts ? `${MODULE_NAME[id]} ${counts[id]}` : MODULE_NAME[id] })),
];

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
export function Filters({ filters, update, reset, showSection, report, showModule = false, moduleCounts = null, platforms = PLATFORMS }) {
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
        options={[{ value: "all", label: "Wszystkie" }, ...platforms]} />
      {showModule && <Toggles label="Moduł" value={filters.module} onChange={(v) => update("module")(v === filters.module ? "all" : v)} options={moduleRow(moduleCounts)} />}
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
  if (c.publishedAt) return <Text type="supporting">{fmtDay(c.publishedAt)}</Text>;
  if (c.publishedAtDerived?.value) return <VStack gap={0.5}><Text type="supporting">≈ {fmtDay(c.publishedAtDerived.value)}</Text><Token size="sm" color="yellow" label="data szacowana" description={c.publishedAtDerived.note || undefined} /></VStack>;
  return <VStack gap={0}><Text type="supporting">{fmtDay(c.observedAt)}</Text><Text type="supporting" color="secondary">odczyt</Text></VStack>;
}

function incompleteReason(c) {
  if (c.needsRecalc && c.module === "M1") return "Starsza wersja analizy: wymaga przeliczenia.";
  if (c.module === "M2" && c.reason) return c.reason;
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

/** Pierwsza kolumna: tytuł, plakietka modułu, źródło (platforma) i kanał. */
function Material({ c, props, selectedId }) {
  const where = [platformLabel(c.platform), c.module === "M1" ? c.creatorName : null, c.publishedAt && fmtDay(c.publishedAt)].filter(Boolean).join(" · ");
  return (
    <VStack gap={0.5}>
      <TitleLink c={c} {...props} active={c.id === selectedId} />
      <HStack gap={1} wrap="wrap" vAlign="center">
        <ModuleToken module={c.module} />
        <Text type="supporting" color="secondary" maxLines={1}>{where}</Text>
      </HStack>
      {(c.origin !== "replay" || c.importLabel || c.needsRecalc || c.pendingReReview || c.reviewStale) && (
        <HStack gap={1} wrap="wrap">{c.origin !== "replay" && <OriginToken origin={c.origin} at={c.observedAt} />}<ImportToken c={c} /><RecalcToken c={c} /><ReReviewToken c={c} /></HStack>
      )}
    </VStack>
  );
}

/** Wiersz zwarty: materiał (moduł, źródło) | firma | powód w jednej linii | siła | dowód. */
export function CaseList({ items, tab, narrow, selectedId, filters, onOpen, emptyState }) {
  const kind = tab === "review" || tab === "incomplete" || tab === "closed" || tab === "demo" ? tab : "review";
  const props = { route: tab, filters, selectedId, onOpen };
  if (narrow) {
    return (
      <List density="spacious" hasDividers>
        {items.length === 0 ? emptyState : items.map((c) => (
          <Item key={c.id} density="spacious" isSelected={c.id === selectedId} labelLines={2} descriptionLines={4}
            href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[`${moduleName(c.module)} · ${platformLabel(c.platform)}${c.firm ? ` · ${c.firm}` : ""}`, c.score?.value != null ? `Siła: ${BANDS[c.score.band] || ""} · ${c.score.value}/100` : null, shortReason(reasonFor(kind, c))]} />} />
        ))}
      </List>
    );
  }
  const columns = [
    { key: "title", header: "Materiał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => <Material c={c} props={props} selectedId={selectedId} /> },
    { key: "firm", header: "Firma", width: proportional(2, { minWidth: 96 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{c.firm || "—"}</Text> },
    { key: "reason", header: REASON_HEADER[kind], width: proportional(3, { minWidth: 150 }), renderCell: (c) => <Text maxLines={2} type="supporting">{shortReason(reasonFor(kind, c))}</Text> },
    ...(kind === "review" || kind === "closed" ? [{ key: "strength", header: "Siła", width: pixel(96), renderCell: (c) => <Strength c={c} /> }] : []),
    ...(kind === "review" ? [{ key: "proof", header: "Dowód", width: pixel(84), renderCell: (c) => <ProofLink c={c} /> }] : []),
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

/** Rejestr reklam: materiał | jak ujawniono (rodzaj, miejsce, cytat) | podstawa wpisu | kiedy. Wszystko z podsumowania API. */
export function RegisterTable({ items, filters, onOpen, emptyState }) {
  const columns = [
    { key: "title", header: "Materiał", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} route="register" filters={filters} onOpen={onOpen} />
        {c.creatorName && <Text type="supporting" color="secondary" maxLines={1}>{c.creatorName}</Text>}
      </VStack>
    ) },
    { key: "firm", header: "Firma", width: proportional(2, { minWidth: 100 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{c.firm || "nie ustalono"}</Text> },
    { key: "platform", header: "Platforma", width: pixel(96), renderCell: (c) => <Text type="supporting">{platformLabel(c.platform)}</Text> },
    { key: "disclosure", header: "Typ ujawnienia", width: proportional(3, { minWidth: 180 }), renderCell: (c) => {
      const d = disclosureLine(c.disclosure);
      return d ? (
        <VStack gap={0.5}>
          <Text weight="medium">{d.title}</Text>
          {d.text && <Text type="supporting" color="secondary" maxLines={2}>„{d.text}”</Text>}
          {c.registry === "candidate" && <Token size="sm" color="yellow" label="do potwierdzenia" />}
        </VStack>
      ) : <Text type="supporting" color="secondary">—</Text>;
    } },
    { key: "date", header: "Kiedy", width: pixel(140), renderCell: (c) => <When c={c} /> },
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

/** Kontrola ujemna M3: podmiot z wykazu KNF (wiersz kolejki niesie tylko zdanie o uprawnieniach). */
const licensedControl = (c) => c.module === "M3" && c.route === "no_signal" && /uprawnion|agent firmy inwestycyjnej|kontrola ujemna/i.test(c.reason || "");

export function OffersTable({ items, module, filters, onOpen, emptyState }) {
  const isM2 = module === "M2";
  const tab = isM2 ? "m2" : "m3";
  const columns = [
    { key: "page", header: isM2 ? "Strona" : "Oferta", width: proportional(3, { minWidth: 170 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} route={tab} filters={filters} onOpen={onOpen} />
        <HStack gap={1} wrap="wrap" vAlign="center">
          {safeUrl(c.url) && <ExternalLink url={c.url}>{new URL(c.url, "http://x/").host}</ExternalLink>}
          <ImportToken c={c} />
          {licensedControl(c) && <Token size="sm" color="green" label="kontrola: podmiot uprawniony" />}
          {c.platform && c.platform !== "web" && <Text type="supporting" color="secondary">{platformLabel(c.platform)}</Text>}
        </HStack>
      </VStack>
    ) },
    { key: "firm", header: isM2 ? "Firma" : "Podmiot", width: proportional(2, { minWidth: 110 }), renderCell: (c) => <Text maxLines={2}>{c.firm || c.creatorName || "—"}</Text> },
    { key: "reason", header: isM2 ? "Przesłanka" : "Powód", width: proportional(3, { minWidth: 150 }), renderCell: (c) => <Text type="supporting" color="secondary" maxLines={2}>{c.reason || c.firstReason ? shortReason(licensedControl(c) ? c.reason : c.firstReason || c.reason) : "—"}</Text> },
    { key: "strength", header: "Siła", width: pixel(104), renderCell: (c) => <Strength c={c} /> },
    { key: "state", header: "Stan", width: pixel(130), renderCell: (c) => (c.needsRecalc && !c.reason ? <RecalcToken c={c} /> : <Text type="supporting">{c.route ? ({ refer: "do sprawdzenia", complete: "uzupełnij dane", no_signal: licensedControl(c) ? "bez przesłanki" : "bez przesłanki", insufficient: "za mało danych" })[c.route] || c.route : "—"}</Text>) },
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
