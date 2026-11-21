import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@astryxdesign/core/AppShell";
import { Badge } from "@astryxdesign/core/Badge";
import { Banner } from "@astryxdesign/core/Banner";
import { Link } from "@astryxdesign/core/Link";
import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { HStack, Layout, LayoutContent, LayoutHeader, LayoutPanel, VStack } from "@astryxdesign/core/Layout";
import { useMediaQuery } from "@astryxdesign/core/hooks";
import { ResizeHandle, useResizable } from "@astryxdesign/core/Resizable";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { Heading, Text } from "@astryxdesign/core/Text";
import { TopNav, TopNavHeading } from "@astryxdesign/core/TopNav";
import { api } from "./api.js";
import { CaseDetail } from "./CaseDetail.jsx";
import { Calibration } from "./Calibration.jsx";
import { EvidenceForm } from "./EvidenceForm.jsx";
import { activeCount, describeFilters, EMPTY_FILTERS } from "./filters.js";
import { CaseList, Filters, MoreFooter, OffersList, OffersTable, RegisterList, RegisterTable } from "./Lists.jsx";
import { VARIANTS, fmtDayRoman, fmtTime } from "./labels.js";
import { hashFor } from "./route.js";
import { ErrorBlock, Loading, NoResults } from "./parts.jsx";
import { TABS, TAB_BY_ID, useRoute } from "./route.js";
import { ScanBanner, Sources, isActive, scanLine, useScanProgress } from "./Sources.jsx";
import { dataScanOf, lastScanOf } from "./model.js";
import { useCase, useDeskData, useQueue } from "./store.js";
import { Sparkline } from "./charts.jsx";

const plural = (n, one, few, many) => (n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

const TITLES = {
  review: "Co wymaga sprawdzenia",
  register: "Rejestr reklam M1",
  m2: "Oferty WWW (M2)",
  m3: "Oferty doradztwa (M3)",
  incomplete: "Niepełne dane",
  closed: "Zamknięte sprawy",
  demo: "Demo i własne pliki",
};

const SENTENCE = {
  review: "Poprawna współpraca trafia do rejestru; brak oznaczenia w opisie, mowie i kadrach trafia tutaj.",
  register: "Jawna współpraca nie jest uchybieniem. Do kontroli trafia dopiero osobna przesłanka.",
  m2: "Zrzuty ofert na stronach firm i ocena 19 kryteriów; „brak danych” jest widoczny.",
  m3: "Oferty doradztwa; status uprawnień z wykazu KNF na dzień odczytu.",
  incomplete: "Za mało danych do oceny (np. mowa czeka na transkrypcję). Brak napisu w niepełnym materiale nie jest wnioskiem.",
  closed: "Sprawy z zapisaną decyzją. Nowa wersja materiału po decyzji wraca do kolejki.",
  demo: "Materiały syntetyczne i pliki operatora; nie wchodzą do rzeczywistych kolejek.",
};

/** Raport CSV/JSON (GET /v1/report) dla zakładek, w których ma sens: moduł i kolejka. */
const REPORT = { review: { module: "M1", queue: "review" }, register: { module: "M1", queue: "adRegister" }, m2: { module: "M2", queue: "offersM2" }, m3: { module: "M3", queue: "offersM3" } };

function TrendGlance({ trend, go }) {
  const scans = (trend?.byScan || []).filter((s) => s.mode !== "recompute");
  if (!scans.length) return null;
  const total = trend.byDay?.reduce((n, d) => n + (d.captures || 0), 0) ?? 0;
  const referred = trend.byDay?.reduce((n, d) => n + (d.referred || 0), 0) ?? 0;
  const label = `Trend: ${scans.length} ${plural(scans.length, "skan", "skany", "skanów")}, ${total} przejrzanych materiałów, ${referred} skierowań`;
  return (
    <HStack gap={2} vAlign="center" wrap="wrap">
      <Sparkline values={scans.map((s) => s.captures || 0)} label={`Przejrzane materiały w kolejnych skanach: ${scans.map((s) => s.captures).join(", ")}`} />
      <Link type="supporting" href={hashFor("sources")} onClick={(e) => { e.preventDefault(); go("sources"); }}>{label}</Link>
    </HStack>
  );
}

function emptyFor(tab, counts, scan) {
  const reviewed = scan?.captures != null ? `Przejrzano ${scan.captures} materiałów. ` : "";
  switch (tab) {
    case "review":
      return ["Brak materiałów z mocną przesłanką do kontroli", `${reviewed}${counts.adRegister ?? 0} jawnych współprac jest w Rejestrze reklam, ${counts.incomplete ?? 0} ma niepełne dane. To nie jest błąd.`];
    case "register":
      return ["W zbadanych materiałach nie znaleziono relacji reklamowych", `${reviewed}Zakres: opis i dostępna mowa.`];
    case "m2":
      return ["Brak przechwyconych stron M2", "Sprawdź zakładkę Źródła."];
    case "m3":
      return ["Brak przechwyconych ofert M3", "Sprawdź zakładkę Źródła."];
    case "incomplete":
      return ["Wszystkie materiały mają wystarczający zakres do oceny", "To nie jest błąd."];
    case "closed":
      return ["Nie ma jeszcze zamkniętych spraw", "Sprawa trafia tutaj po zapisaniu decyzji."];
    default:
      return ["Brak materiałów demonstracyjnych i własnych plików", "Własny plik dodasz przyciskiem „Dodaj dowód”."];
  }
}

function QueueScreen({ tab, route, go, desk, narrow, actions }) {
  const meta = TAB_BY_ID[tab];
  const { data, rev, refresh } = desk;
  const counts = data.counts || {};
  const filters = route.filters;
  const queue = useQueue(meta.queue, filters, data, rev);
  const scan = dataScanOf(data);
  const waiting = counts.transcriptPending ?? null;
  const [panelClosed, setPanelClosed] = useState(false);
  const [reload, setReload] = useState(0);
  const headingRef = useRef(null);
  const lastRow = useRef(null);
  const pane = useResizable({ defaultSize: "60%", minSize: "44%", maxSize: "72%", isReversed: true });
  const ready = queue.status === "ready" || queue.status === "refreshing";
  const items = ready ? queue.items : [];
  const split = meta.mode === "split";
  const autoId = split && !narrow && !route.caseId && !panelClosed && items[0] ? items[0].id : null;
  const shownId = route.caseId || autoId;
  const current = useCase(shownId, data, rev, reload);
  const update = (name) => (value) => go(tab, { filters: { ...filters, [name]: value ?? EMPTY_FILTERS[name] }, caseId: route.caseId }, { replace: true });
  const reset = () => go(tab, { caseId: route.caseId }, { replace: true });
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
      const open = [...document.querySelectorAll("[role=listbox], [role=dialog], [role=menu]")].some((e) => e.getClientRects().length > 0);
      if (open) return;
      close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [route.caseId, close]);
  const onSaved = useCallback(async () => {
    setReload((n) => n + 1);
    await refresh();
  }, [refresh]);

  const [emptyTitle, emptyText] = emptyFor(tab, counts, scan);
  const filterText = describeFilters(filters);
  const total = queue.total;
  const nothingShown = ready && items.length === 0;
  const empty = !ready ? null : activeCount(filters) === 0
    ? <EmptyState isCompact title={emptyTitle} description={emptyText} actions={<HStack gap={2} wrap="wrap">
        {tab !== "register" && <Button label="Rejestr reklam" onClick={() => go("register")} />}
        {tab !== "incomplete" && <Button label="Niepełne dane" onClick={() => go("incomplete")} />}
      </HStack>} />
    : <NoResults filterText={filterText} clear={reset} hint={tab === "review" && counts.adRegister ? `${counts.adRegister} materiałów z jawną współpracą jest w Rejestrze reklam.` : "Zmień filtry albo wyczyść je."} />;

  const detailBox = !shownId ? null : current.status === "error"
    ? <VStack padding={4}><ErrorBlock message={current.error} title={current.notFound ? "Nie znaleziono sprawy" : "Nie można pobrać sprawy"} /></VStack>
    : !current.c ? <Loading rows={4} label="Pobieranie sprawy…" />
      : <CaseDetail key={current.c.id} c={current.c} headingRef={headingRef} narrow={narrow} onSaved={onSaved} onBack={narrow || !split ? close : null} />;

  let list;
  if (queue.status === "error") list = queue.legacy
    ? <VStack padding={4}><Banner status="warning" title="Starsze API: brak kolejek" description={queue.error} /></VStack>
    : <ErrorBlock message={queue.error} retry={refresh} />;
  else if (!ready) list = <Loading label="Pobieranie listy…" />;
  else if (meta.mode === "table" && !narrow) {
    list = items.length === 0 ? empty : tab === "register" ? <RegisterTable items={items} filters={filters} onOpen={open} emptyState={empty} /> : <OffersTable items={items} module={tab === "m2" ? "M2" : "M3"} filters={filters} onOpen={open} emptyState={empty} />;
  } else if (meta.mode === "table") {
    list = items.length === 0 ? empty : tab === "register" ? <RegisterList items={items} tab={tab} filters={filters} /> : <OffersList items={items} tab={tab} filters={filters} />;
  } else {
    list = <CaseList items={items} tab={tab} narrow={narrow} selectedId={shownId} filters={filters} onOpen={open} emptyState={empty} />;
  }

  const recalc = ready ? items.filter((c) => c.needsRecalc && c.module === "M1").length : 0;
  const variantName = VARIANTS[data.qualification?.variant] || data.qualification?.variant;
  const head = (
    <LayoutHeader padding={0} hasDivider>
      <VStack padding={narrow ? 2 : 3} gap={1}>
        <HStack gap={2} vAlign="center" wrap="wrap">
          <Heading level={1}>{TITLES[tab]}</Heading>
          <Badge label={String(counts[meta.queue] ?? (ready ? total : "…"))} />
          {!narrow && <Text type="supporting" color="secondary" maxLines={1}>{SENTENCE[tab]}</Text>}
        </HStack>
        {narrow && <Text type="supporting" color="secondary">{SENTENCE[tab]}</Text>}
        <Text type="supporting" color="secondary" maxLines={narrow ? 3 : 1}>{scanLine(scan)}</Text>
        {tab === "review" && <TrendGlance trend={data.trend} go={go} />}
        {(tab === "review" || tab === "incomplete") && (
          <HStack gap={2} wrap="wrap" vAlign="center">
            <Text type="supporting" color="secondary">Reguły: {variantName}{data.qualification?.setAt ? `, od ${fmtDayRoman(data.qualification.setAt)} ${fmtTime(data.qualification.setAt)}` : ""}.</Text>
            {waiting != null && waiting > 0 && (tab === "incomplete"
              ? <Text type="supporting" color="secondary">{waiting} czeka na transkrypcję.</Text>
              : <Link type="supporting" href={hashFor("incomplete")} onClick={(e) => { e.preventDefault(); go("incomplete"); }}>{waiting} czeka na transkrypcję: Niepełne dane</Link>)}
          </HStack>
        )}
      </VStack>
    </LayoutHeader>
  );

  const body = (
    <VStack gap={2} padding={narrow ? 2 : 3}>
      {recalc > 0 && (
        <Banner status="warning" title={`${recalc} ${plural(recalc, "wiersz ma", "wiersze mają", "wierszy ma")} wynik ze starszych reguł`}
          endContent={<Button label="Przelicz materiały" size="sm" isDisabled={actions.busy || actions.scanning} onClick={() => actions.scan("recompute")} />} />
      )}
      <Filters filters={filters} update={update} reset={reset} showSection={tab === "register"} report={REPORT[tab]} />
      {list}
      {ready && <MoreFooter shown={items.length} total={total} hasMore={!!queue.nextCursor} loading={queue.loadingMore} onMore={queue.more} />}
    </VStack>
  );

  // Telefon i widoki tabelaryczne: karta jako osobny ekran.
  if ((narrow || !split) && route.caseId) {
    return <Layout height="fill" content={<LayoutContent padding={0}>{detailBox}</LayoutContent>} />;
  }
  return (
    <Layout height="fill" header={head}
      content={<LayoutContent padding={0} isScrollable>{body}</LayoutContent>}
      end={split && !narrow && (
        <>
          <ResizeHandle resizable={pane.props} direction="horizontal" isReversed hasDivider label="Zmień szerokość szczegółów" />
          <LayoutPanel padding={0} resizable={pane.props} role="complementary" label="Szczegóły wybranej sprawy">
            {detailBox || (
              <VStack padding={6}><EmptyState title={nothingShown ? "Nie ma czego otwierać" : "Wybierz materiał"} description={nothingShown ? "Gdy lista będzie pusta, szczegół nie otwiera się sam." : "Tutaj zobaczysz powód, momenty do sprawdzenia i zapiszesz decyzję."} /></VStack>
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

  useEffect(() => {
    document.title = `${TITLES[tab] || TABS.find((t) => t.id === tab)?.label || "InvestWatch"} · InvestWatch`;
  }, [tab]);

  const tabs = TABS.filter((t) => t.id !== "evidence");
  let content;
  if (error && !data) content = <ErrorBlock message={error} retry={desk.refresh} />;
  else if (!data) content = <Loading label="Pobieranie danych…" />;
  else if (tab === "sources") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><Sources data={data} busy={busy} scanning={scanning} onScan={startScan} rev={desk.rev} onRefresh={() => desk.schedule({ heavy: true })} /></LayoutContent>} />;
  else if (tab === "calibration") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><Calibration data={data} rev={desk.rev} onChanged={() => desk.refresh({ heavy: true })} /></LayoutContent>} />;
  else if (tab === "evidence") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><EvidenceForm onDone={schedule} onOpenDemo={() => go("demo")} /></LayoutContent>} />;
  else content = <QueueScreen key={tab} tab={tab} route={route} go={go} desk={desk} narrow={narrow} actions={actions} />;

  return (
    <AppShell variant="section" mobileNav={false} topNav={
      <TopNav label="Pulpit InvestWatch" heading={<TopNavHeading heading="InvestWatch" />}
        endContent={
          <HStack gap={2} vAlign="center">
            <StatusDot variant={live ? "success" : "warning"} label={live ? "Dane aktualizowane na żywo" : "Ponowne łączenie"} tooltip={live ? "Połączenie na żywo" : "Ponowne łączenie z serwerem"} />
            <Text type="supporting" color="secondary">{live ? "na żywo" : "łączenie…"}</Text>
            <Button label="Dodaj dowód" size="sm" variant={tab === "evidence" ? "primary" : "secondary"} onClick={() => go("evidence")} />
          </HStack>
        } />
    }>
      <Layout height="fill"
        header={
          <LayoutHeader padding={0} hasDivider>
            <VStack gap={0}>
              {alerts.map((a) => (
                <Banner key={a.id} container="section" status="error" isDismissable onDismiss={() => dismissAlert(a.id)}
                  title={`Nowy alert wysokiego ryzyka: ${a.message}`}
                  description="Przesłanka do sprawdzenia o wysokiej sile. To nie jest ocena prawna."
                  endContent={<Button label="Otwórz" onClick={() => { dismissAlert(a.id); go("review", { caseId: a.ref }); }} />} />
              ))}
              {notice && <Banner container="section" status={notice.status} title={notice.title} isDismissable onDismiss={() => setNotice(null)} />}
              {refreshError && data && <Banner container="section" status="warning" title={`Pokazujemy dane z ${fmtTime(loadedAt)}. Odświeżenie nie powiodło się: ${refreshError}`}
                endContent={<Button label="Spróbuj ponownie" onClick={desk.refresh} />} />}
              {scanning && <ScanBanner scan={scan} detail={detail} />}
              <HStack paddingInline={narrow ? 1 : 3}>
                <TabList role="tablist" value={tab} overflow="scroll" size={narrow ? "sm" : "md"} onChange={(value) => go(value)}>
                  {tabs.map((t) => (
                    <Tab key={t.id} value={t.id} label={t.label} panelId="desk-panel"
                      endContent={data && t.queue && counts[t.queue] != null ? <Badge label={String(counts[t.queue])} /> : undefined} />
                  ))}
                </TabList>
              </HStack>
            </VStack>
          </LayoutHeader>
        }
        content={<LayoutContent padding={0} id="desk-panel" role="tabpanel">{content}</LayoutContent>} />
    </AppShell>
  );
}
