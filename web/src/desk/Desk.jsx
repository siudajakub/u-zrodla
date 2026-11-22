import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@astryxdesign/core/AppShell";
import { Badge } from "@astryxdesign/core/Badge";
import { Banner } from "@astryxdesign/core/Banner";
import { Link } from "@astryxdesign/core/Link";
import { Token } from "@astryxdesign/core/Token";
import { Tooltip } from "@astryxdesign/core/Tooltip";
import { VisuallyHidden } from "@astryxdesign/core/VisuallyHidden";
import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { HStack, Layout, LayoutContent, LayoutFooter, LayoutHeader, LayoutPanel, VStack } from "@astryxdesign/core/Layout";
import { useMediaQuery } from "@astryxdesign/core/hooks";
import { ResizeHandle, useResizable } from "@astryxdesign/core/Resizable";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { Heading, Text } from "@astryxdesign/core/Text";
import { TopNav, TopNavHeading } from "@astryxdesign/core/TopNav";
import { api } from "./api.js";
import { CaseDetail } from "./CaseDetail.jsx";
import { Calibration } from "./Calibration.jsx";
import { activeCount, describeFilters, EMPTY_FILTERS, PLATFORMS, queueFor } from "./filters.js";
import { CaseList, Filters, MoreFooter, RegisterCounters, RegisterList, RegisterTable, applyRegisterFilter } from "./Lists.jsx";
import { DESTINATION, fmtDay, fmtDayRoman, fmtInt, fmtTime } from "./labels.js";
import { hashFor } from "./route.js";
import { ErrorBlock, Loading, NoResults } from "./parts.jsx";
import { TABS, TAB_BY_ID, useRoute } from "./route.js";
import { ScanBanner, Sources, isActive, useScanProgress } from "./Sources.jsx";
import { byStrengthThenDate, dataScanOf, lastScanOf } from "./model.js";
import { useCase, useDeskData, useModuleCounts, useQueue } from "./store.js";
import { Sparkline } from "./charts.jsx";

const plural = (n, one, few, many) => (n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

/** Raport CSV (GET /v1/report): moduł i kolejka wybranej listy. */
const reportFor = (tab, filters, queue) => {
  if (tab === "register") return { module: "M1", queue: "adRegister" };
  const mixedWorkflow = ["control", "supplement", "closed"].includes(queue);
  return { module: filters.module !== "all" ? filters.module : mixedWorkflow ? "all" : "M1", queue };
};

/** Etykieta trybu danych: „odtworzenie skanu z 21 XI” (tło szare) albo „skan na żywo z 21 lis” (zielone tylko dla skanu na żywo). */
export function modeLabel(data, scan) {
  const mode = data.scanMode || scan?.mode;
  const at = scan?.createdAt;
  if (mode === "replay") return { text: at ? `odtworzenie skanu z ${fmtDayRoman(at)}` : "odtworzenie skanu", color: "gray" };
  if (mode === "live") return { text: at ? `skan na żywo z ${fmtDay(at)}` : "skan na żywo", color: "green" };
  return { text: data.scanLabel || "brak skanu", color: "gray" };
}

function DataLine({ data, go, scan, filters }) {
  const f = data.funnel;
  const counts = data.counts || {};
  const e = f?.explainedAutomatically;
  const explained = e ? (e.bySpeech || 0) + (e.byPlatformFlag || 0) + (e.byFrame || 0) : null;
  const step = (n, label, onClick, href) => (
    <Link type="supporting" href={href} onClick={(ev) => { ev.preventDefault(); onClick(); }}><Text weight="semibold">{fmtInt(n)}</Text> {label}</Link>
  );
  return (
    <HStack gap={4} vAlign="center" wrap="wrap" aria-label="Stan danych">
      <HStack gap={1} vAlign="center" wrap="wrap">
        {step(counts.all ?? f?.materials, plural(counts.all ?? f?.materials, "materiał", "materiały", "materiałów"), () => go("review", { filters: { ...EMPTY_FILTERS, state: "all" } }), hashFor("review", { filters: { ...EMPTY_FILTERS, state: "all" } }))}
        <Text type="supporting" color="secondary" aria-hidden="true">→</Text>
        {step(f?.adRegister ?? counts.adRegister, "w rejestrze reklam", () => go("register"), hashFor("register"))}
        <Text type="supporting" color="secondary" aria-hidden="true">→</Text>
        {step(f?.review ?? counts.review, "do sprawdzenia", () => go("review", { filters: { ...EMPTY_FILTERS } }), hashFor("review"))}
      </HStack>
      {explained != null && (
        <Tooltip content={`W mowie ${fmtInt(e.bySpeech || 0)} · flaga YouTube ${fmtInt(e.byPlatformFlag || 0)} · w kadrze ${fmtInt(e.byFrame || 0)}. Takie oznaczenie obala podejrzenie: materiał trafia do rejestru, nie do alarmu.`}>
          <Text type="supporting" data-testid="explained"><Text weight="semibold">{fmtInt(explained)}</Text> wyjaśnione automatycznie</Text>
        </Tooltip>
      )}

    </HStack>
  );
}

function emptyFor(state, tab, counts, scan) {
  const reviewed = scan?.captures != null ? `Przejrzano ${fmtInt(scan.captures)} materiałów. ` : "";
  if (tab === "register") return ["W zbadanych materiałach nie znaleziono relacji reklamowych", `${reviewed}Zakres: opis i dostępna mowa.`];
  switch (state) {
    case "review":
      return ["Brak materiałów z mocną przesłanką do kontroli", `${reviewed}${counts.adRegister ?? 0} jawnych współprac jest w Rejestrze reklam, ${counts.incomplete ?? 0} ma niepełne dane. To nie jest błąd.`];
    case "control":
      return ["Brak spraw przekazanych do kontroli", "Po skierowaniu sprawy pojawią się tutaj."];
    case "supplement":
      return ["Brak spraw do uzupełnienia", "Skierowane sprawy pojawią się tutaj."];
    case "incomplete":
      return ["Wszystkie materiały mają wystarczający zakres do oceny", "To nie jest błąd."];
    case "closed":
      return ["Nie ma jeszcze zakończonych spraw", "Sprawa trafia tutaj po zatwierdzeniu decyzji."];
    case "demo":
      return ["Brak materiałów demonstracyjnych i własnych plików", "Własny plik dodasz w zakładce Źródła, w sekcji „Dodaj materiał”."];
    default:
      return ["Brak materiałów dla tego modułu", "Sprawdź zakładkę Źródła."];
  }
}

function QueueScreen({ tab, route, go, desk, narrow, actions, onDecision }) {
  const { data, rev, refresh } = desk;
  const counts = data.counts || {};
  const filters = route.filters;
  const isRegister = tab === "register";
  const queueName = isRegister ? "adRegister" : queueFor(filters.state, filters.module);
  const split = !isRegister;
  const discOn = isRegister && filters.disc !== "all";
  const queue = useQueue(queueName, filters, data, rev, discOn ? 500 : 50);
  const scan = dataScanOf(data);
  const [panelClosed, setPanelClosed] = useState(false);
  const [reload, setReload] = useState(0);
  const headingRef = useRef(null);
  const lastRow = useRef(null);
  const pane = useResizable({ defaultSize: "54%", minSize: "40%", maxSize: "72%", isReversed: true });
  const ready = queue.status === "ready" || queue.status === "refreshing";
  const sortedBy = !isRegister && filters.state === "review";
  const rawItems = ready ? queue.items : [];
  const items = discOn ? applyRegisterFilter(rawItems, filters.disc) : rawItems;
  const queueOf = useCallback((m) => (isRegister ? "adRegister" : queueFor(filters.state, m)), [isRegister, filters.state]);
  const moduleCounts = null;
  const autoId = split && !narrow && !route.caseId && !panelClosed && items[0] ? items[0].id : null;
  const shownId = route.caseId || autoId;
  const current = useCase(shownId, data, rev, reload);
  const update = (name) => (value) => go(tab, { filters: { ...filters, [name]: value ?? EMPTY_FILTERS[name] }, caseId: route.caseId }, { replace: true });
  const reset = () => go(tab, { caseId: route.caseId, filters: { ...EMPTY_FILTERS, state: filters.state } }, { replace: true });
  const open = useCallback((id) => {
    lastRow.current = id;
    setPanelClosed(false);
    go(tab, { filters, caseId: id });
  }, [go, tab, filters]);
  const close = useCallback(() => {
    setPanelClosed(true);
    go(tab, { filters });
    requestAnimationFrame(() => {
      const row = lastRow.current && document.getElementById(`row-${lastRow.current}`);
      row?.focus();
    });
  }, [go, tab, filters]);
  useEffect(() => {
    if (route.caseId && current.c?.id === route.caseId && lastRow.current === route.caseId) {
      requestAnimationFrame(() => headingRef.current?.focus({ preventScroll: true }));
    }
  }, [route.caseId, current.c?.id]);
  useEffect(() => setPanelClosed(false), [tab]);
  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== "Escape" || event.defaultPrevented || !route.caseId) return;
      const open = [...document.querySelectorAll("[role=listbox], [role=dialog], [role=menu], dialog[open]")].some((e) => e.getClientRects().length > 0);
      if (open) return;
      close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [route.caseId, close]);
  const pin = useCallback((id) => {
    if (!route.caseId) go(tab, { filters, caseId: id }, { replace: true });
  }, [route.caseId, go, tab, filters]);
  const onConflict = useCallback(async () => {
    desk.invalidate();
    setReload((n) => n + 1);
    await refresh();
  }, [refresh, desk.invalidate]);
  const onSaved = useCallback(async (decision) => {
    const index = items.findIndex((item) => item.id === decision.caseId);
    const next = items.slice(index + 1).concat(items.slice(0, Math.max(index, 0))).find((item) => item.id !== decision.caseId);
    setPanelClosed(!next);
    go(tab, { filters, caseId: next?.id || null }, { replace: true });
    onDecision(decision);
    desk.invalidate();
    await refresh();
  }, [items, tab, filters, go, onDecision, desk.invalidate, refresh]);

  const [emptyTitle, emptyText] = emptyFor(filters.state, tab, counts, scan);
  const filterText = describeFilters(filters);
  const total = discOn ? items.length : queue.total;
  const nothingShown = ready && items.length === 0;
  const empty = !ready ? null : activeCount(filters) === 0
    ? <EmptyState isCompact title={emptyTitle} description={emptyText} actions={<HStack gap={2} wrap="wrap">
        {tab !== "register" && <Button label="Rejestr reklam" onClick={() => go("register")} />}
        {!(tab === "review" && filters.state === "incomplete") && !isRegister && <Button label="Niepełne" onClick={() => go("review", { filters: { ...EMPTY_FILTERS, state: "incomplete" } })} />}
      </HStack>} />
    : <NoResults filterText={filterText} clear={reset} hint={tab === "review" && filters.state === "review" && counts.adRegister ? `${counts.adRegister} materiałów z jawną współpracą jest w Rejestrze reklam.` : "Zmień filtry albo wyczyść je."} />;

  const detailBox = !shownId ? null : current.status === "error"
    ? <VStack padding={4}><ErrorBlock message={current.error} title={current.notFound ? "Nie znaleziono sprawy" : "Nie można pobrać sprawy"} /></VStack>
    : !current.c ? <Loading rows={4} label="Pobieranie sprawy…" />
      : <CaseDetail key={current.c.id} c={current.c} headingRef={headingRef} narrow={narrow} onSaved={onSaved} onConflict={onConflict} onPin={pin} onBack={narrow || !split ? close : null} />;

  let list;
  if (queue.status === "error") list = queue.legacy
    ? <VStack padding={4}><Banner status="warning" title="Starsze API: brak kolejek" description={queue.error} /></VStack>
    : <ErrorBlock message={queue.error} retry={refresh} />;
  else if (!ready) list = <Loading label="Pobieranie listy…" />;
  else if (isRegister) {
    list = items.length === 0 ? empty : narrow ? <RegisterList items={items} tab={tab} filters={filters} /> : <RegisterTable items={items} filters={filters} onOpen={open} emptyState={empty} />;
  } else {
    list = <CaseList items={items} tab={tab} kind={filters.state} narrow={narrow} selectedId={shownId} filters={filters} onOpen={open} emptyState={empty} />;
  }

  const recalc = ready ? items.filter((c) => c.needsRecalc && c.module === "M1").length : 0;
  const filtersBar = (
    <Filters filters={filters} update={update} reset={reset} tab={tab} narrow={narrow} report={reportFor(tab, filters, queueName)} moduleCounts={moduleCounts} stateCounts={counts} platforms={isRegister ? PLATFORMS.filter((p) => p.value !== "web") : PLATFORMS} />
  );
  const workflowNav = !isRegister && <HStack gap={1} wrap="wrap" aria-label="Etapy pracy">
    {[["review", "Do sprawdzenia"], ["control", "Kontrola"], ["supplement", "Do uzupełnienia"], ["closed", "Zakończone"]].map(([state, label]) => (
      <Button key={state} label={counts[state] != null ? `${label} (${fmtInt(counts[state])})` : label} variant={filters.state === state ? "primary" : "secondary"} aria-pressed={filters.state === state} onClick={() => go("review", { filters: { ...EMPTY_FILTERS, state } })} />
    ))}
  </HStack>;
  const head = narrow ? null : (
    <LayoutHeader padding={0} hasDivider>
      <VStack paddingInline={3} paddingBlock={1.5} gap={1.5}>
        <VisuallyHidden><Heading level={1}>{TAB_BY_ID[tab].label}</Heading></VisuallyHidden>
        {workflowNav}
        {filtersBar}
      </VStack>
    </LayoutHeader>
  );

  const body = (
    <VStack gap={2} padding={narrow ? 2 : 3}>
      {narrow && <VisuallyHidden><Heading level={1}>{TAB_BY_ID[tab].label}</Heading></VisuallyHidden>}
      {recalc > 0 && (
        <Banner status="warning" title={`${recalc} ${plural(recalc, "wiersz ma", "wiersze mają", "wierszy ma")} wynik ze starszych reguł`}
          endContent={<Button label="Przelicz materiały" size="sm" isDisabled={actions.busy || actions.scanning} onClick={() => actions.scan("recompute")} />} />
      )}
      {narrow && workflowNav}
      {narrow && filtersBar}
      {isRegister && <RegisterCounters funnel={data.funnel} filters={filters} update={update} go={go} />}
      {list}
      {ready && <MoreFooter shown={items.length} total={total} hasMore={!!queue.nextCursor && !discOn} loading={queue.loadingMore} onMore={queue.more} />}
    </VStack>
  );

  // Telefon i widoki tabelaryczne: karta jako osobny ekran.
  if ((narrow || !split) && route.caseId) {
    return <Layout height="fill" content={<LayoutContent padding={0}>{detailBox}</LayoutContent>} />;
  }
  return (
    <Layout height="fill" header={head || undefined}
      content={<LayoutContent padding={0} isScrollable>{body}</LayoutContent>}
      end={split && !narrow && (
        <>
          <ResizeHandle resizable={pane.props} direction="horizontal" isReversed hasDivider label="Zmień szerokość szczegółów" />
          <LayoutPanel padding={0} resizable={pane.props} role="complementary" label="Szczegóły wybranej sprawy">
            {detailBox || (
              <VStack padding={6}><EmptyState title={nothingShown ? "Nie ma czego otwierać" : "Wybierz materiał"} description={nothingShown ? "Gdy lista będzie pusta, szczegół nie otwiera się sam." : "Tutaj zobaczysz powód, dowód i zapiszesz decyzję."} /></VStack>
            )}
          </LayoutPanel>
        </>
      )} />
  );
}

export function Desk() {
  const [route, go] = useRoute();
  const desk = useDeskData();
  const narrow = useMediaQuery("(max-width: 63rem)");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const { data, error, refreshError, alerts, dismissAlert, schedule, live, loadedAt } = desk;
  const scan = data ? lastScanOf(data) : null;
  const scanning = isActive(scan);
  const detail = useScanProgress(scan);
  const counts = data?.counts || {};
  const tab = route.tab;

  async function startScan(mode) {
    setBusy(true);
    try {
      await api.startScan(mode);
      setNotice({ status: "info", title: mode === "recompute" ? "Przeliczanie uruchomione." : "Skan uruchomiony. Wyniki pojawią się w kolejkach." });
      [400, 1500, 4000, 9000].forEach((ms) => setTimeout(schedule, ms));
    } catch (e) {
      setNotice({ status: e.status === 409 ? "warning" : "error", title: `Nie uruchomiono skanu: ${e.message}` });
    } finally {
      setBusy(false);
    }
  }
  const actions = { busy, scanning, scan: startScan };
  const onDecision = useCallback(({ result, resolution, caseId, title }) => {
    const destination = result?.workflowStage || DESTINATION[resolution];
    const label = { control: "Przekazane do kontroli", supplement: "Do uzupełnienia", closed: "Zakończone", review: "Do sprawdzenia" }[destination];
    const buttonLabel = { control: "Otwórz w kontroli", supplement: "Otwórz do uzupełnienia", closed: "Otwórz w zakończonych", review: "Otwórz do sprawdzenia" }[destination];
    setNotice({ status: "success", title: `Decyzja zatwierdzona: ${title}`, description: `Sprawa trafiła do kolejki „${label}”.`, destination, caseId, label, buttonLabel });
  }, []);

  useEffect(() => {
    document.title = `${TAB_BY_ID[tab]?.label || "InvestWatch"} · InvestWatch`;
  }, [tab]);

  const tabs = TABS;
  let content;
  if (error && !data) content = <ErrorBlock message={error} retry={desk.refresh} />;
  else if (!data) content = <Loading label="Pobieranie danych…" />;
  else if (tab === "sources") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><Sources data={data} busy={busy} scanning={scanning} onScan={startScan} rev={desk.rev} onRefresh={() => desk.schedule({ heavy: true })} openAdd={route.add} go={go} narrow={narrow} /></LayoutContent>} />;
  else if (tab === "calibration") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><Calibration data={data} rev={desk.rev} onChanged={() => desk.refresh({ heavy: true })} /></LayoutContent>} />;
  else content = <QueueScreen key={tab} tab={tab} route={route} go={go} desk={desk} narrow={narrow} actions={actions} onDecision={onDecision} />;

  return (
    <AppShell variant="section" mobileNav={false} topNav={
      <TopNav label="Pulpit InvestWatch" heading={<TopNavHeading heading="InvestWatch" logo={<Token color="blue" label="IW" />} />}
        endContent={
          <HStack gap={2} vAlign="center">
            <StatusDot variant={live ? "success" : "warning"} label={live ? "Połączono: alerty na żywo" : "Ponowne łączenie"} tooltip={live ? "Połączenie z serwerem: nowe sprawy i decyzje pojawiają się od razu" : "Ponowne łączenie z serwerem"} />
            <Text type="supporting" color="secondary">{live ? "połączono" : "łączenie…"}</Text>
          </HStack>
        } />
    }>
      <Layout height="fill"
        header={
          <LayoutHeader padding={0} hasDivider>
            <VStack gap={0}>
              {alerts.map((a) => (
                <Banner key={a.id} container="section" status="error" isDismissable onDismiss={() => dismissAlert(a.id)}
                  title={`Nowa sprawa: ${a.message}`}
                  endContent={<Button label="Otwórz" onClick={() => { dismissAlert(a.id); go("review", { caseId: a.ref }); }} />} />
              ))}
              {notice && <Banner container="section" status={notice.status} title={notice.title} description={notice.description} isDismissable onDismiss={() => setNotice(null)}
                endContent={notice.destination && <Button label={notice.buttonLabel} onClick={() => { go("review", { filters: { ...EMPTY_FILTERS, state: notice.destination }, caseId: notice.caseId }); setNotice(null); }} />} />}
              {refreshError && data && <Banner container="section" status="warning" title={`Pokazujemy dane z ${fmtTime(loadedAt)}. Odświeżenie nie powiodło się: ${refreshError}`}
                endContent={<Button label="Spróbuj ponownie" onClick={desk.refresh} />} />}
              {scanning && <ScanBanner scan={scan} detail={detail} />}
              <HStack paddingInline={narrow ? 0 : 3}>
                <TabList role="tablist" value={tab} overflow="scroll" size={narrow ? "sm" : "md"} onChange={(value) => go(value)}>
                  {tabs.map((t) => (
                    <Tab key={t.id} value={t.id} label={narrow && t.id === "register" ? "Rejestr" : t.label} panelId="desk-panel"
                      endContent={data && !narrow && (t.id === "review" || t.queue) && counts[t.id === "review" ? "review" : t.queue] != null ? <Badge label={fmtInt(counts[t.id === "review" ? "review" : t.queue])} /> : undefined} />
                  ))}
                </TabList>
              </HStack>
            </VStack>
          </LayoutHeader>
        }
        content={<LayoutContent padding={0} id="desk-panel" role="tabpanel">{content}</LayoutContent>}
        footer={<LayoutFooter padding={1} hasDivider><HStack hAlign="center"><Text type="supporting" color="secondary">{narrow ? "Przesłanki, nie ocena prawna." : "Przesłanki do sprawdzenia, nie ocena prawna. Decyzję podejmuje analityk."}</Text></HStack></LayoutFooter>} />
    </AppShell>
  );
}
