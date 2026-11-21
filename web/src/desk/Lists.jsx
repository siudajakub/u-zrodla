// Listy: jeden szablon wiersza (materiał z modułem i źródłem | firma | powód | siła), jeden rząd filtrów
// (Stan, Moduł, Źródło, Siła, Data, Szukaj, Raport), rejestr reklam z licznikami „wyjaśnione automatycznie”.
// Wiersze czytają wyłącznie podsumowania z API; stronicowanie „Pokaż więcej”, filtry w adresie.
import React from "react";
import { Button } from "@astryxdesign/core/Button";
import { DateInput } from "@astryxdesign/core/DateInput";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Link } from "@astryxdesign/core/Link";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { Popover } from "@astryxdesign/core/Popover";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { Selector } from "@astryxdesign/core/Selector";
import { pixel, proportional, Table } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { ToggleButton } from "@astryxdesign/core/ToggleButton";
import { Token } from "@astryxdesign/core/Token";
import { reportUrl } from "./api.js";
import { PLATFORMS, activeCount } from "./filters.js";
import { COMPLETE_REASON, DISCLOSURE_WHERE, MODULE_NAME, STATES, clock, fmtDay, fmtInt, platformLabel, strengthLabel } from "./labels.js";
import { Lines, ModuleToken, OriginToken, RecalcToken, ReReviewToken, Strength } from "./parts.jsx";
import { hashFor } from "./route.js";
import { rowReason, shortReason } from "./model.js";

const hostOf = (url) => {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return "";
  }
};

const noCount = (label) => String(label).replace(/ \d+$/, "");

/** Filtry nad listą w jednym rzędzie. Telefon: Stan i Moduł oraz przycisk „Filtry (n)” z resztą. `report` = { module, queue }. */
export function Filters({ filters, update, reset, tab, narrow, report, moduleCounts = null, stateCounts = {}, platforms = PLATFORMS }) {
  const count = activeCount(filters);
  const isReview = tab === "review";
  const moduleOptions = [
    { value: "all", label: moduleCounts ? `Wszystkie ${Object.values(moduleCounts).reduce((a, b) => a + b, 0)}` : "Wszystkie" },
    ...Object.keys(MODULE_NAME).map((id) => ({ value: id, label: moduleCounts ? `${MODULE_NAME[id]} ${moduleCounts[id]}` : MODULE_NAME[id] })),
  ];
  const stateOptions = STATES.map((s) => ({ value: s.value, label: stateCounts[s.queue] != null && s.value !== "all" ? `${s.label} ${stateCounts[s.queue]}` : s.label }));
  const stateSelect = isReview && (
    <Selector label="Stan" isLabelHidden variant="secondary" size="sm" width={narrow ? 168 : undefined} value={filters.state} onChange={(v) => update("state")(v || "review")} options={stateOptions} renderValue={(o) => narrow ? noCount(o.label) : `Stan: ${noCount(o.label)}`} />
  );
  const moduleControl = narrow ? (
    <Selector label="Moduł" isLabelHidden variant="secondary" size="sm" width={narrow ? 128 : undefined} value={filters.module} onChange={(v) => update("module")(v || "all")} options={moduleOptions} renderValue={(o) => narrow ? noCount(o.label) : `Moduł: ${noCount(o.label)}`} />
  ) : (
    <SegmentedControl label="Moduł" size="sm" value={filters.module} onChange={update("module")}>
      {moduleOptions.map((o) => <SegmentedControlItem key={o.value} value={o.value} label={o.label} />)}
    </SegmentedControl>
  );
  const source = (
    <Selector label="Źródło" isLabelHidden variant="secondary" size="sm" value={filters.source} onChange={(v) => update("source")(v || "all")}
      options={[{ value: "all", label: "Wszystkie" }, ...platforms]} renderValue={(o) => `Źródło: ${o.label}`} />
  );
  const band = (
    <Selector label="Siła" isLabelHidden variant="secondary" size="sm" value={filters.band} onChange={(v) => update("band")(v || "all")}
      options={[{ label: "Dowolna", value: "all" }, { label: "mocna", value: "strong" }, { label: "średnia", value: "moderate" }, { label: "słaba", value: "weak" }]} renderValue={(o) => `Siła: ${o.label}`} />
  );
  const field = filters.dateField === "publishedAt" ? "Opublikowano" : "Odczytano";
  const dateLabel = filters.from || filters.to ? `Data: ${filters.from || "…"} – ${filters.to || "…"}` : "Data";
  const date = (
    <Popover label="Zakres dat" content={
      <VStack gap={2}>
        <Selector label="Pole daty" size="sm" value={filters.dateField} onChange={update("dateField")} options={[{ label: "Odczytano", value: "observedAt" }, { label: "Opublikowano", value: "publishedAt" }]} />
        <DateInput label={`${field} od`} size="sm" hasClear value={filters.from || undefined} onChange={update("from")} />
        <DateInput label={`${field} do`} size="sm" hasClear value={filters.to || undefined} onChange={update("to")} />
      </VStack>
    }>
      <Button label={dateLabel} size="sm" variant="secondary" />
    </Popover>
  );
  const section = tab === "register" && (
    <Selector label="Rejestr" isLabelHidden variant="secondary" size="sm" value={filters.section} onChange={(v) => update("section")(v || "all")}
      options={[{ label: "Wszystkie", value: "all" }, { label: "Potwierdzone", value: "confirmed" }, { label: "Do potwierdzenia", value: "candidate" }]} renderValue={(o) => `Rejestr: ${o.label}`} />
  );
  const search = (
    <TextInput label="Szukaj po autorze lub tytule" isLabelHidden type="search" startIcon="search" size="sm" placeholder="Szukaj po autorze lub tytule" width={narrow ? "100%" : "18rem"} value={filters.q} onChange={update("q")} />
  );
  const reportButton = report && <Button label="Raport" size="sm" href={reportUrl({ ...report, format: "csv", filters })} tooltip="Raport CSV z aktualnymi filtrami (UTF-8, Excel)" />;
  const clear = count > 0 && <Button variant="ghost" size="sm" label={`Wyczyść filtry (${count})`} onClick={reset} />;
  if (narrow) {
    const extra = count - (filters.module !== "all" ? 1 : 0);
    return (
      <VStack gap={1}>
        <HStack gap={1} vAlign="center" wrap="wrap">
          {stateSelect}
          {tab !== "register" && moduleControl}
          <Popover label="Filtry" placement="below" content={<VStack gap={2}>{search}{source}{band}{date}{section}{reportButton}{clear}</VStack>}>
            <Button label={`Filtry${extra > 0 ? ` (${extra})` : ""}`} size="sm" variant="secondary" />
          </Popover>
        </HStack>
      </VStack>
    );
  }
  return (
    <HStack gap={1.5} vAlign="center" wrap="wrap">
      {stateSelect}
      {tab !== "register" && moduleControl}
      {source}
      {band}
      {date}
      {section}
      {search}
      {reportButton}
      {clear}
    </HStack>
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

/** Autor (kanał, konto) albo domena dla stron firm i doradców. */
const authorOf = (c) => (c.module !== "M1" && c.platform === "web" ? hostOf(c.url) || c.creatorName : c.creatorName);

/** Data w wierszu: opublikowano, szacunek z „≈”, a dla stron data odczytu. */
export const whenOf = (c) => (c.publishedAt ? fmtDay(c.publishedAt) : c.publishedAtDerived?.value ? `≈ ${fmtDay(c.publishedAtDerived.value)}` : c.observedAt ? fmtDay(c.observedAt) : null);

const firmOf = (c) => c.firmShort || c.firm;
const sub = (c) => [authorOf(c), platformLabel(c.platform), whenOf(c)].filter(Boolean).join(" · ");

/** Kontrola ujemna M3: podmiot z wykazu KNF. Pole `licensed` z API; dla starszego API rozpoznanie ze zdania o uprawnieniach. */
export const isLicensed = (c) => c.module === "M3" && (c.licensed ?? (c.route === "no_signal" && /uprawnion|agent firmy inwestycyjnej|kontrola ujemna/i.test(c.reason || "")));

function incompleteReason(c) {
  if (c.needsRecalc && c.module === "M1") return "Starsza wersja analizy: wymaga przeliczenia.";
  if (c.module === "M2" && c.reason) return c.reason;
  return COMPLETE_REASON[c.completeReason] || c.reason || "Brak danych do oceny.";
}

function reasonFor(kind, c) {
  if (kind === "review") return rowReason(c);
  if (kind === "incomplete") return incompleteReason(c);
  if (kind === "closed") return c.lastDecision ? c.lastDecision.note || "Decyzja zapisana." : rowReason(c);
  if (kind === "demo") return c.reason || "Materiał demonstracyjny.";
  if (isLicensed(c)) return c.reason || c.firstReason || "—";
  return c.firstReason || c.reason || COMPLETE_REASON[c.completeReason] || null;
}
const REASON_HEADER = { review: "Dlaczego tutaj", incomplete: "Czego brakuje", closed: "Decyzja", demo: "Opis", all: "Powód" };

/** Pierwsza kolumna: tytuł, plakietka modułu i jedna linia autor · źródło · data. */
function Material({ c, props, selectedId }) {
  return (
    <VStack gap={0.5}>
      <TitleLink c={c} {...props} active={c.id === selectedId} />
      <HStack gap={1} wrap="wrap" vAlign="center">
        <ModuleToken module={c.module} />
        <Text type="supporting" color="secondary" maxLines={1}>{sub(c)}</Text>
        {isLicensed(c) && <Token size="sm" color="green" label="kontrola: podmiot uprawniony" />}
        {c.origin !== "replay" && <OriginToken origin={c.origin} at={c.observedAt} />}
        <RecalcToken c={c} />
        <ReReviewToken c={c} />
      </HStack>
    </VStack>
  );
}

/** Wiersz zwarty, 4 kolumny: materiał (moduł, autor, źródło, data) | firma | powód w jednej linii | siła. */
export function CaseList({ items, tab, kind, narrow, selectedId, filters, onOpen, emptyState }) {
  const props = { route: tab, filters, selectedId, onOpen };
  if (narrow) {
    return (
      <List density="spacious" hasDividers>
        {items.length === 0 ? emptyState : items.map((c) => {
          const strength = c.score?.value != null ? strengthLabel(c.score.band, c.score.value) : null;
          return (
            <Item key={c.id} density="spacious" isSelected={c.id === selectedId} labelLines={2} descriptionLines={4}
              href={hashFor(tab, { caseId: c.id, filters })}
              label={c.title}
              description={<Lines lines={[[strength, c.module, firmOf(c), platformLabel(c.platform), whenOf(c)].filter(Boolean).join(" · "), shortReason(reasonFor(kind, c))]} />} />
          );
        })}
      </List>
    );
  }
  const columns = [
    { key: "title", header: "Materiał", width: proportional(4, { minWidth: 200 }), renderCell: (c) => <Material c={c} props={props} selectedId={selectedId} /> },
    { key: "firm", header: "Firma", width: proportional(2, { minWidth: 90 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{firmOf(c) || "—"}</Text> },
    { key: "reason", header: REASON_HEADER[kind] || "Powód", width: proportional(4, { minWidth: 150 }), renderCell: (c) => <Text maxLines={2} type="supporting">{shortReason(reasonFor(kind, c)) || "—"}</Text> },
    { key: "strength", header: "Siła", width: pixel(112), renderCell: (c) => <Strength c={c} /> },
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

/** Jak ujawniono: miejsce (z czasem w mowie) i cytat z API. Rodzaj wynika z miejsca, nie z pola `kind`. */
export function disclosureLine(d, platform) {
  if (!d) return null;
  if (d.state === "not_found_in_scope") return { title: "brak w zbadanym zakresie", text: null };
  let where = DISCLOSURE_WHERE[d.state] || DISCLOSURE_WHERE[d.where] || "ujawnione";
  if (d.state === "platform_flag" && platform && platform !== "youtube") where = "flaga platformy";
  if (d.atSec != null) where = `${where} ${clock(d.atSec)}`;
  return { title: where, text: d.text ? d.text.replace(/\s*\(odczyt z [^)]*\)/, "") : null };
}

const REGISTER_FILTERS = {
  in_description: (c) => c.disclosure?.state === "in_description",
  in_speech: (c) => c.disclosure?.state === "in_speech",
  platform_flag: (c) => c.disclosure?.state === "platform_flag",
};
export const applyRegisterFilter = (items, disc) => (REGISTER_FILTERS[disc] ? items.filter(REGISTER_FILTERS[disc]) : items);

/** Liczniki nad rejestrem: ujawnione w opisie · w mowie · flaga YouTube klikalne (zawężają listę), czeka na mowę prowadzi do Niepełnych. */
export function RegisterCounters({ funnel, filters, update, go }) {
  const e = funnel?.explainedAutomatically;
  if (!e) return null;
  const toggle = (value, label, n, hint) => n == null ? null : (
    <ToggleButton key={value} size="sm" label={`${label} ${fmtInt(n)}`} tooltip={hint} isPressed={filters.disc === value} onPressedChange={() => update("disc")(filters.disc === value ? "all" : value)}>{`${label} ${fmtInt(n)}`}</ToggleButton>
  );
  return (
    <HStack gap={1} vAlign="center" wrap="wrap" role="group" aria-label="Jak ujawniono współpracę">
      <Text type="supporting" color="secondary">Ujawnione:</Text>
      {toggle("in_description", "w opisie", e.byDescription, "Oznaczenie współpracy jest w opisie materiału")}
      {toggle("in_speech", "w mowie", e.bySpeech, "Oznaczenie padło dopiero w mowie: film trafia do rejestru, nie do alarmu")}
      {toggle("platform_flag", "flaga YouTube", e.byPlatformFlag, "Platforma oznacza materiał jako płatną promocję")}
      {funnel.heldBySpeechGate != null && (
        <ToggleButton size="sm" label={`czeka na mowę ${fmtInt(funnel.heldBySpeechGate)}`} tooltip="Kandydaci wstrzymani do czasu transkrypcji mowy; lista w stanie Niepełne" isPressed={false} onPressedChange={() => go("review", { filters: { ...filters, state: "incomplete", disc: "all", section: "all" } })}>{`czeka na mowę ${fmtInt(funnel.heldBySpeechGate)}`}</ToggleButton>
      )}
    </HStack>
  );
}

/** Rejestr reklam: materiał (autor, źródło, data) | firma | jak ujawniono (miejsce i cytat w jednej linii). */
export function RegisterTable({ items, filters, onOpen, emptyState }) {
  const columns = [
    { key: "title", header: "Materiał", width: proportional(4, { minWidth: 200 }), renderCell: (c) => (
      <VStack gap={0.5}>
        <TitleLink c={c} route="register" filters={filters} onOpen={onOpen} />
        <Text type="supporting" color="secondary" maxLines={1}>{sub(c)}</Text>
      </VStack>
    ) },
    { key: "firm", header: "Firma", width: proportional(2, { minWidth: 100 }), renderCell: (c) => <Text type="supporting" maxLines={2}>{firmOf(c) || "—"}</Text> },
    { key: "disclosure", header: "Jak ujawniono", width: proportional(5, { minWidth: 200 }), renderCell: (c) => {
      const d = disclosureLine(c.disclosure, c.platform);
      return d ? (
        <VStack gap={0.5}>
          <HStack gap={1} vAlign="center" wrap="wrap">
            <Text weight="medium">{d.title}</Text>
            {c.registry === "candidate" && <Token size="sm" color="yellow" label="do potwierdzenia" />}
          </HStack>
          {d.text && <Text type="supporting" color="secondary" maxLines={1}>„{d.text.length > 80 ? `${d.text.slice(0, 79)}…` : d.text}”</Text>}
        </VStack>
      ) : <Text type="supporting" color="secondary">—</Text>;
    } },
  ];
  return <Table idKey="id" columns={columns} data={items} density="compact" hasHover verticalAlign="top" emptyState={emptyState} />;
}

export function RegisterList({ items, filters, tab }) {
  return (
    <List density="spacious" hasDividers>
      {items.map((c) => {
        const d = disclosureLine(c.disclosure, c.platform);
        return (
          <Item key={c.id} density="spacious" labelLines={2} descriptionLines={3} href={hashFor(tab, { caseId: c.id, filters })}
            label={c.title}
            description={<Lines lines={[[firmOf(c), platformLabel(c.platform), whenOf(c)].filter(Boolean).join(" · "), d ? `${d.title}${d.text ? `: „${d.text}”` : ""}` : null]} />} />
        );
      })}
    </List>
  );
}
