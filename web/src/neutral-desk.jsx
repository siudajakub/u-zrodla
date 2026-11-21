import React, { createContext, useContext, useId, useRef, useState } from "react";
import { AppShell } from "@astryxdesign/core/AppShell";
import { Badge } from "@astryxdesign/core/Badge";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { DateInput } from "@astryxdesign/core/DateInput";
import { FileInput } from "@astryxdesign/core/FileInput";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, Layout, LayoutContent, LayoutHeader, LayoutPanel, StackItem, VStack } from "@astryxdesign/core/Layout";
import { ResizeHandle, useResizable } from "@astryxdesign/core/Resizable";
import { Selector } from "@astryxdesign/core/Selector";
import { Slider } from "@astryxdesign/core/Slider";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { pixel, proportional, Table } from "@astryxdesign/core/Table";
import { Heading, Text } from "@astryxdesign/core/Text";
import { TextArea } from "@astryxdesign/core/TextArea";
import { TextInput } from "@astryxdesign/core/TextInput";
import { Token } from "@astryxdesign/core/Token";
import { TopNav, TopNavHeading, TopNavItem } from "@astryxdesign/core/TopNav";
import { Link } from "@astryxdesign/core/Link";
import { useMediaQuery } from "@astryxdesign/core/hooks";
import { createProof } from "./proof.jsx";

// The table-inbox catalog template puts the queue in LayoutContent and the
// reading pane in Layout's resizable end slot. Below its split breakpoint the
// same content area is used for one surface at a time.
const NAV = [
  ["queue", "Sprawy"],
  ["sources", "Źródła"],
  ["calibration", "Kalibracja"],
  ["upload", "Nagrania"],
];
const MODULES = { M1: "Promocja twórców", M2: "Reklamy firm", M3: "Oferty doradztwa" };
const STATUS = ["new", "reviewing", "closed"];
const FILTERS = { query: "", module: "all", status: "all", flag: "all", platform: "all", risk: "all", from: "", to: "" };
const Navigation = createContext(null);

function NavAnchor({ href, onClick, ...props }) {
  const navigate = useContext(Navigation);
  return <a {...props} href={href} onClick={(event) => {
    onClick?.(event);
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(href.slice(1));
  }} />;
}

export function createNeutralViews(shared) {
  const { list, date, text, status, linkUrl, modeLabel, provenanceText } = shared;
  const { Evidence, History } = createProof(shared);
  const statusOptions = STATUS.map((value) => ({ value, label: status(value) }));

  function SourceLink({ url, children }) {
    const href = linkUrl(url);
    return href ? <Link href={href} target="_blank">{children}</Link> : null;
  }

  function Facts({ finding, creator }) {
    const name = creator?.name || finding.creatorName || finding.brand;
    return (
      <HStack gap={2} wrap="wrap" vAlign="center">
        <Text type="supporting" color="secondary">
          {[name, finding.platform, ((finding.publishedAt || finding.observedAt) && date(finding.publishedAt || finding.observedAt))].filter(Boolean).join(" · ")}
        </Text>
        <SourceLink url={finding.url || creator?.url}>Materiał źródłowy</SourceLink>
      </HStack>
    );
  }

  function Decision({ finding, save, busy }) {
    const [state, setState] = useState({ status: null, note: "", revision: null });
    const [validation, setValidation] = useState(false);
    const input = useRef(null);
    const changed = state.revision != null && state.revision !== finding.revision;
    function update(fields) {
      setState((draft) => ({ ...draft, revision: draft.revision ?? finding.revision, ...fields }));
    }
    async function submit(event) {
      event.preventDefault();
      if (busy || changed) return;
      if (!state.note.trim()) {
        setValidation(true);
        input.current?.focus();
        return;
      }
      if (await save({ ...finding, revision: state.revision ?? finding.revision }, state.status || finding.status || "new", state.note)) {
        setState({ status: null, note: "", revision: null });
        setValidation(false);
      }
    }
    return (
      <VStack gap={4}>
        {changed && <Banner status="warning"
          title="Sprawa zmieniła się podczas edycji"
          description="Sprawdź bieżący stan i historię. Szkic uzasadnienia jest nadal dostępny."
          endContent={<Button label="Przejrzałem zmiany" onClick={() => update({ revision: finding.revision })} />} />}
        <form onSubmit={submit}>
          <VStack gap={3}>
            <Selector label="Status sprawy" value={state.status || finding.status || "new"} options={statusOptions}
              onChange={(value) => update({ status: value })} />
            <TextArea label="Uzasadnienie decyzji" value={state.note} ref={input} rows={3} htmlMaxLength={2000}
              onChange={(value) => { update({ note: value }); setValidation(false); }}
              status={validation ? { type: "error", message: "Wpisz uzasadnienie decyzji." } : undefined} />
            <HStack>
              <Button type="submit" label="Zapisz decyzję" variant="primary" isLoading={busy} isDisabled={changed} />
            </HStack>
          </VStack>
        </form>
        <History finding={finding} />
      </VStack>
    );
  }

  function Detail({ finding, creator, close, focusRef, save, busy, saveContract, inquiry }) {
    const [tab, setTab] = useState("evidence");
    const tabsId = useId();
    const media = useRef(null);
    const currentState = status(finding.status);
    const tabs = [
      ["evidence", "Dowody", <Evidence finding={finding} media={media} />],
      ["decision", "Decyzja", <Decision finding={finding} save={save} busy={busy} />],
      ...(finding.contractDemo ? [["contract", "Umowa", <section className="preview-support">
        <shared.Contract finding={finding} save={saveContract} inquiry={inquiry} busy={busy} />
      </section>]] : []),
    ];
    return (
      <article className="desk-detail" aria-label="Szczegóły sprawy">
        <VStack gap={3} padding={4}>
          <HStack gap={2} hAlign="space-between" wrap="wrap" vAlign="center">
            <Text type="supporting" color="secondary">{finding.module} · {MODULES[finding.module]} · {currentState}</Text>
            {close && <Button label="Wróć do kolejki" variant="ghost" size="sm" onClick={close} />}
          </HStack>
          <h2 tabIndex={-1} ref={focusRef} className="case-heading">{finding.title}</h2>
          <Facts finding={finding} creator={creator} />
          {finding.summary && <Text>{finding.summary}</Text>}
          <TabList value={tab} role="tablist" hasDivider onChange={(value) => {
            if (value !== "evidence") media.current?.pause();
            setTab(value);
          }}>
            {tabs.map(([id, label]) => <Tab key={id} value={id} label={label} panelId={tabsId + id} />)}
          </TabList>
          {tabs.map(([id, label, content]) =>
            <section key={id} id={tabsId + id} role="tabpanel" aria-label={label} hidden={tab !== id}>{content}</section>
          )}
        </VStack>
      </article>
    );
  }

  function Filters({ filters, platforms, update, reset }) {
    return (
      <VStack gap={2}>
        <TextInput label="Szukaj spraw" isLabelHidden type="search" startIcon="search" placeholder="Szukaj spraw"
          value={filters.query} onChange={update("query")} />
        <Grid columns={{ minWidth: 125, max: 2 }} gap={2}>
          <Selector label="Moduł" isLabelHidden value={filters.module} onChange={update("module")}
            options={[{ label: "Wszystkie moduły", value: "all" }, ...Object.entries(MODULES).map(([id, label]) => ({ value: id, label: `${id} · ${label}` }))]} />
          <Selector label="Sygnał do sprawdzenia" isLabelHidden value={filters.flag} onChange={update("flag")}
            options={[{ label: "Wszystkie sprawy", value: "all" }, { label: "Oznaczone do sprawdzenia", value: "review" }]} />
        </Grid>
        <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Więcej filtrów</Text>}>
          <VStack gap={2} padding={2}>
            <Grid columns={{ minWidth: 125, max: 2 }} gap={2}>
              <Selector label="Status" value={filters.status} onChange={update("status")}
                options={[{ label: "Wszystkie statusy", value: "all" }, ...statusOptions]} />
              <Selector label="Platforma" value={filters.platform} onChange={update("platform")}
                options={[{ label: "Wszystkie platformy", value: "all" }, ...platforms]} />
              <Selector label="Priorytet" value={filters.risk} onChange={update("risk")}
                options={[{ label: "Wszystkie wyniki", value: "all" }, { label: "Od 60 punktów", value: "high" },
                  { label: "Poniżej 60 punktów", value: "low" }]} />
              <DateInput label="Data od" value={filters.from || undefined} onChange={update("from")} />
              <DateInput label="Data do" value={filters.to || undefined} onChange={update("to")} />
            </Grid>
            <HStack><Button variant="ghost" label="Wyczyść filtry" onClick={reset} /></HStack>
          </VStack>
        </Collapsible>
      </VStack>
    );
  }

  function Queue(props) {
    const { data, select, selected, refresh, scan, busy } = props;
    const narrow = useMediaQuery("(max-width: 63rem)");
    const [filters, setFilters] = useState(FILTERS);
    const [hasClosed, setHasClosed] = useState(false);
    const row = useRef(null);
    const detailTitle = useRef(null);
    const searchContainer = useRef(null);
    const pane = useResizable({ defaultSize: "55%", minSize: "38%", maxSize: "65%", isReversed: true });
    const findings = list(data.findings);
    const creators = new Map(list(data.creators).map((creator) => [creator.id, creator]));
    const filtered = findings.filter((finding) => {
      const haystack = [finding.title, finding.summary, finding.platform, creators.get(finding.creatorId)?.name, finding.url]
        .join(" ").toLocaleLowerCase("pl-PL");
      const day = String(finding.publishedAt || finding.observedAt || "").slice(0, 10);
      return haystack.includes(filters.query.trim().toLocaleLowerCase("pl-PL"))
        && (filters.module === "all" || filters.module === finding.module)
        && (filters.status === "all" || filters.status === finding.status)
        && (filters.flag === "all" || filters.flag === finding.reviewSuggestion?.state)
        && (filters.platform === "all" || filters.platform === finding.platform)
        && (filters.risk === "all" || (finding.score != null && (filters.risk === "high" ? finding.score >= 60 : finding.score < 60)))
        && (!filters.from || (day && day >= filters.from))
        && (!filters.to || (day && day <= filters.to));
    }).sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
    const finding = findings.find((item) => item.id === selected) || (!narrow && !hasClosed ? filtered[0] : null);
    const isFullWidth = narrow && !!finding;
    function open(id) {
      setHasClosed(false);
      select(id);
      requestAnimationFrame(() => {
        detailTitle.current?.closest(".desk-detail")?.scrollIntoView({ block: "start" });
        detailTitle.current?.focus({ preventScroll: true });
      });
    }
    function close() {
      setHasClosed(true);
      select(null);
      requestAnimationFrame(() => {
        const button = row.current && document.getElementById(row.current);
        (button || searchContainer.current?.querySelector("input"))?.focus();
      });
    }
    const columns = [
      {
        key: "title", header: "Materiał", width: proportional(3, { minWidth: 148 }),
        renderCell: (item) => (
          <VStack gap={0.5}>
            <button className="desk-case-link" type="button" aria-current={item.id === finding?.id ? "true" : undefined}
              id={`case-${item.id}`} onClick={(event) => {
                row.current = event.currentTarget.id;
                open(item.id);
              }}>
              {item.title}
            </button>
            <Text type="supporting" color="secondary">
              {[item.module, item.platform, creators.get(item.creatorId)?.name].filter(Boolean).join(" · ")}
            </Text>
            {item.reviewSuggestion?.state === "review" && <HStack>
              <Token size="sm" color="gray" label={item.reviewSuggestion.source === "semantic" ? "Model wskazał materiał" : "Reguły wskazały materiał"} />
            </HStack>}
          </VStack>
        ),
      },
      {
        key: "status", header: "Status", width: proportional(1, { minWidth: 80 }),
        renderCell: (item) => <Text type="supporting" color="secondary">{status(item.status)}</Text>,
      },
      {
        key: "score", header: "Reguły", align: "end", width: pixel(80),
        renderCell: (item) => <Text weight="semibold">{item.score ?? "—"}</Text>,
      },
    ];
    const detail = finding && (
      <Detail {...props} key={finding.id} finding={finding} creator={creators.get(finding.creatorId)}
        focusRef={detailTitle} close={close} />
    );
    const lastScan = list(data.scans)[0];
    return (
      <Layout height="fill"
        header={!isFullWidth && (
          <LayoutHeader padding={0} hasDivider>
            <HStack padding={4} gap={3} vAlign="center" wrap="wrap">
              <StackItem size="fill">
                <VStack gap={0.5}>
                  <HStack gap={2} vAlign="center"><Heading level={1}>Kolejka spraw</Heading><Badge label={String(findings.length)} /></HStack>
                  {lastScan && <Text type="supporting" color="secondary">
                    Skan {modeLabel(lastScan.mode)} · {status(lastScan.status)}{lastScan.error ? ` · ${lastScan.error}` : ""}
                  </Text>}
                </VStack>
              </StackItem>
              <HStack gap={1} wrap="wrap">
                <Button label="Odśwież" variant="ghost" onClick={refresh} />
                <Button label="Skanuj na żywo" isDisabled={busy} onClick={() => scan("live")} />
                <Button label="Odtwórz skan" variant="primary" isDisabled={busy} onClick={() => scan("replay")} />
              </HStack>
            </HStack>
          </LayoutHeader>
        )}
        content={
          <LayoutContent padding={isFullWidth ? 0 : 4} isScrollable ref={searchContainer}>
            {isFullWidth ? detail : (
              <VStack gap={3}>
                <Filters filters={filters} platforms={[...new Set(findings.map((item) => item.platform).filter(Boolean))].sort()}
                  update={(name) => (value) => setFilters((current) => ({ ...current, [name]: value }))}
                  reset={() => setFilters(FILTERS)} />
                <Table idKey="id" columns={columns} data={filtered} density="balanced" hasHover
                  emptyState={<EmptyState isCompact title={findings.length ? "Brak pasujących spraw" : "Brak spraw"}
                    description={findings.length ? "Zmień filtry albo wyszukiwane hasło." : "Uruchom skan, aby dodać materiały do kolejki."} />} />
              </VStack>
            )}
          </LayoutContent>
        }
        end={!narrow && (
          <>
            <ResizeHandle resizable={pane.props} direction="horizontal" isReversed hasDivider label="Zmień szerokość szczegółów" />
            <LayoutPanel padding={0} resizable={pane.props} role="complementary" label="Szczegóły wybranej sprawy">
              {detail || <VStack padding={6}><EmptyState title="Wybierz sprawę" description="Tutaj otworzysz dowody i zapiszesz decyzję." /></VStack>}
            </LayoutPanel>
          </>
        )}
      />
    );
  }

  function Sources({ data }) {
    const sources = list(data.sources);
    const creators = list(data.creators);
    const scans = list(data.scans);
    return (
      <Layout height="fill" contentWidth={960} content={
        <LayoutContent padding={4}>
          <VStack gap={5}>
            <Heading level={1}>Źródła i twórcy</Heading>
            <VStack gap={2}>
              <Heading level={2}>Stan źródeł</Heading>
              <Table data={sources} idKey={(source) => source.id || source.name}
                emptyState={<EmptyState isCompact title="Brak źródeł w ostatnim skanie" />} columns={[
                  { key: "name", header: "Źródło", width: proportional(2), renderCell: (source) => (
                    <VStack gap={0.5}>
                      <Text weight="semibold">{source.name || source.id}</Text>
                      {source.url && <SourceLink url={source.url}>Otwórz źródło</SourceLink>}
                      {(source.lastSuccessAt || source.lastSuccess || source.last_success) && <Text type="supporting" color="secondary">
                        Ostatni udany odczyt: {date(source.lastSuccessAt || source.lastSuccess || source.last_success)}
                      </Text>}
                      {(source.scope || source.mode) && <Text type="supporting" color="secondary">{provenanceText(source)}</Text>}
                      {source.error && <Text type="supporting">{source.error}</Text>}
                    </VStack>
                  ) },
                  { key: "status", header: "Stan", renderCell: (source) => status(source.status) },
                  { key: "count", header: "Materiały", align: "end", renderCell: (item) => item.count ?? "—" },
                ]} />
            </VStack>
            <VStack gap={2}>
              <HStack gap={2} vAlign="center"><Heading level={2}>Odkryci twórcy</Heading><Badge label={String(creators.length)} /></HStack>
              <Table data={creators} idKey="id" emptyState={<EmptyState isCompact title="Brak odkrytych twórców" />} columns={[
                { key: "name", header: "Twórca", width: proportional(2), renderCell: (creator) => (
                  <VStack gap={0.5}>
                    {creator.url ? <SourceLink url={creator.url}>{creator.name}</SourceLink> : <Text>{creator.name}</Text>}
                    {creator.status === "candidate" && <Text type="supporting">ID kanału do potwierdzenia</Text>}
                    {creator.crosslinkDiscovery?.videoUrl && <SourceLink url={creator.crosslinkDiscovery.videoUrl}>Film, który wskazał twórcę</SourceLink>}
                  </VStack>
                ) },
                { key: "platform", header: "Platforma" },
                { key: "discoveredVia", header: "Odkryto przez", width: proportional(2), renderCell: (creator) => (
                  <VStack gap={0.5}>
                    <Text>{text(creator.discoveredVia)}</Text>
                    {creator.firstSeen && <Text type="supporting" color="secondary">{date(creator.firstSeen)}</Text>}
                  </VStack>
                ) },
              ]} />
            </VStack>
            {scans.length > 0 && <VStack gap={2}>
              <Heading level={2}>Ostatnie skany</Heading>
              <Table data={scans.slice(0, 8)} idKey="id" columns={[
                { key: "createdAt", header: "Data", renderCell: (scan) => date(scan.createdAt) },
                { key: "mode", header: "Tryb", renderCell: (scan) => modeLabel(scan.mode) },
                { key: "status", header: "Stan", renderCell: (scan) => (
                  <VStack gap={0.5}><Text>{status(scan.status)}</Text>{scan.error && <Text>{scan.error}</Text>}</VStack>
                ) },
              ]} />
            </VStack>}
          </VStack>
        </LayoutContent>
      } />
    );
  }

  function Calibration({ openFinding, findings }) {
    const { threshold, setThreshold, cal, retry } = shared.useCalibration();
    return (
      <VStack gap={4}>
        <Heading level={1}>Kalibracja analizy</Heading>
        <Slider label={`Próg ${threshold}`} value={threshold} valueDisplay="none" onChange={setThreshold}
          description="Przesuń próg, aby porównać wyniki na tym samym zbiorze." />
        <Text color="secondary">{shared.calibrationLabels}</Text>
        {cal?.error ? <Banner status="error" title="Nie można pobrać wyników" description={cal.error}
          endContent={<Button label="Spróbuj ponownie" onClick={retry} />} /> : !cal ? (
          <p role="status">Pobieranie wyników…</p>
        ) : (
          <VStack gap={3}>
            <Table data={[
              { metric: "Trafienia", count: cal.tp },
              { metric: "Fałszywe alarmy", count: cal.fp },
              { metric: "Poprawnie odrzucone", count: cal.tn },
              { metric: "Przeoczenia", count: cal.fn },
              { metric: "Koszt (2 × przeoczenia + fałszywe alarmy)", count: cal.cost },
            ]} idKey="metric" columns={[
              { key: "metric", header: "Wynik", width: proportional(3) },
              { key: "count", header: "Liczba", align: "end", renderCell: (item) => item.count ?? "—" },
            ]} />
            <Text type="supporting" color="secondary">
              {cal.n} przykładów · {cal.publicExamples ?? "—"} publicznych · {cal.syntheticExamples ?? "—"} syntetycznych · Zbiór {text(cal.datasetId)}
            </Text>
            {cal.description && <Text>{cal.description}</Text>}
            {list(cal.errors).length > 0 && <VStack gap={2}>
              <Heading level={2}>Przeoczenia i fałszywe alarmy</Heading>
              {cal.errors.map((item) => (
                <Collapsible key={item.id} defaultIsOpen={false} trigger={<Text>
                  {item.title || item.id} · {item.outcome === "fp" ? "fałszywy alarm" : "przeoczenie"} · {item.score} / 100
                </Text>}>
                  <VStack gap={2} padding={2}>
                    {item.text && <Text>{item.text}</Text>}
                    <Text type="supporting">Oczekiwano: {item.expected ? "sygnał do analizy" : "brak sygnału"}</Text>
                    <HStack gap={2} wrap="wrap">
                      <SourceLink url={item.url}>Otwórz materiał źródłowy</SourceLink>
                      {list(findings).some((finding) => finding.id === item.id) &&
                        <Button label="Otwórz sprawę" onClick={() => openFinding(item)} />}
                    </HStack>
                  </VStack>
                </Collapsible>
              ))}
            </VStack>}
          </VStack>
        )}
      </VStack>
    );
  }

  function Upload({ upload, busy, lastUpload, openUpload }) {
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [file, setFile] = useState(null);
    return (
      <form onSubmit={(event) => {
        event.preventDefault();
        if (!busy) upload(file, title.trim(), description);
      }}>
        <VStack gap={3}>
          <Heading level={1}>Własne nagranie</Heading>
          <FileInput label="Plik audio lub wideo" placeholder="Wybierz nagranie" mode="dropzone" value={file} onChange={setFile}
            description="Limit 40 MiB. Analiza obejmuje maks. 120 sekund." maxSize={40 * 1024 * 1024}
            accept="audio/*,video/*,.mp4,.wav,.mp3,.m4a,.webm,.ogg,.mov,.mkv,.aac,.flac" />
          <TextInput label="Tytuł (opcjonalnie)" value={title} onChange={setTitle} htmlMaxLength={180} />
          <TextArea label="Opis (opcjonalnie)" value={description} onChange={setDescription} htmlMaxLength={5000} />
          <HStack gap={2} wrap="wrap">
            <Button type="submit" variant="primary" label="Prześlij do analizy" isLoading={busy} />
            {lastUpload && <Button label="Otwórz przesłaną analizę" onClick={openUpload} />}
          </HStack>
        </VStack>
      </form>
    );
  }

  function Desk(props) {
    const { data, page, setPage, error, refresh, connection, toast } = props;
    return (
      <Navigation.Provider value={setPage}>
        <AppShell variant="section" mobileNav={false} topNav={
          <TopNav label="Pulpit InvestWatch"
            heading={<TopNavHeading heading="InvestWatch" />}
            startContent={<HStack gap={0.5} wrap="wrap">{NAV.map(([id, label]) =>
              <TopNavItem key={id} label={label} as={NavAnchor} href={`#${id}`} isSelected={page === id} />
            )}</HStack>}
            endContent={<StatusDot variant={connection ? "success" : "warning"}
              label={connection ? "Dane aktualizowane na żywo" : "Ponowne łączenie"} />}
          />
        }>
          <section id="main" tabIndex={-1} className="desk-surface">
            {error && <Banner status="error" title={error}
              endContent={<Button label="Spróbuj ponownie" onClick={refresh} />} />}
            {!data && !error && <VStack padding={4}><p role="status">Pobieranie spraw…</p></VStack>}
            {data && (page === "queue" ? <Queue {...props} /> : page === "sources" ? <Sources data={data} /> : (
              <Layout height="fill" contentWidth={960} content={<LayoutContent padding={4}>
                {page === "calibration"
                  ? <Calibration openFinding={props.openFinding} findings={data.findings} />
                  : <Upload upload={props.upload} busy={props.busy} lastUpload={props.lastUpload} openUpload={props.openUpload} />}
              </LayoutContent>} />
            ))}
            {toast && <aside className="desk-feedback" role="status">
              <Banner status={/^(Nie |Sprawa została zmieniona)/.test(toast) ? "warning" : "info"} title={toast} />
            </aside>}
          </section>
        </AppShell>
      </Navigation.Provider>
    );
  }
  return { Desk };
}
