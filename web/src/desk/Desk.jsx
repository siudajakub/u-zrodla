import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@astryxdesign/core/AppShell";
import { Badge } from "@astryxdesign/core/Badge";
import { Banner } from "@astryxdesign/core/Banner";
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
import { applyFilters, describeFilters, EMPTY_FILTERS } from "./filters.js";
import { CaseList, Filters, OffersList, OffersTable, RegisterList, RegisterTable } from "./Lists.jsx";
import { fmtTime } from "./labels.js";
import { ErrorBlock, Loading, NoResults } from "./parts.jsx";
import { TABS, TAB_BY_ID, useRoute } from "./route.js";
import { ScanBanner, Sources, isActive, scanLine, useScanProgress } from "./Sources.jsx";
import { lastScanOf } from "./model.js";
import { useDeskData, useQueue } from "./store.js";

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

const undecided = (counts) => counts.review === 0 && !counts.adRegister && counts.incomplete > 0;

function describe(tab, n, counts) {
  if (tab === "review" && n === 0 && undecided(counts)) return "Nie można jeszcze ustalić, co wymaga sprawdzenia: materiały mają wynik ze starszych reguł. Kolejka nie jest pusta, tylko nieobliczona.";
  const items = (one, few, many) => `${n} ${plural(n, one, few, many)}`;
  switch (tab) {
    case "review":
      return `${items("materiał", "materiały", "materiałów")} z mocną przesłanką do kontroli i dostępnym dowodem. Jawna współpraca bez osobnej przesłanki nie trafia tutaj, tylko do Rejestru reklam (${counts.adRegister ?? 0}).`;
    case "register":
      return "Jawna współpraca nie jest uchybieniem. Do kontroli trafia dopiero osobna, udokumentowana przesłanka.";
    case "m2":
      return "Zrzuty ofert na stronach firm i ocena 19 kryteriów. „Brak danych” przy kryterium jest widoczny, a nie ukryty.";
    case "m3":
      return "Oferty doradztwa. Status uprawnień pochodzi z wykazu KNF na dzień odczytu.";
    case "incomplete":
      return "Materiały bez wystarczającego zakresu analizy albo ze starszą wersją analizy. Brak napisu w niepełnym materiale nie jest wnioskiem.";
    case "closed":
      return "Sprawy z zapisaną decyzją. Nowa wersja materiału po decyzji wraca do kolejki jako „Nowa wersja po decyzji”.";
    default:
      return "Materiały syntetyczne zespołu i pliki operatora. Nie pochodzą z bieżącego rynku i nie wchodzą do rzeczywistych kolejek.";
  }
}

function emptyFor(tab, counts, scan) {
  const reviewed = scan?.captures != null ? `Przejrzano ${scan.captures} materiałów. ` : "";
  switch (tab) {
    case "review":
      return counts.incomplete > 0 && counts.review === 0 && counts.adRegister === 0
        ? ["Nie można jeszcze ustalić, co wymaga sprawdzenia", `${counts.incomplete} materiałów czeka na przeliczenie bieżącymi regułami. Kolejka nie jest pusta, tylko nieobliczona.`]
        : ["Brak materiałów z mocną przesłanką do kontroli w ostatnim skanie", `${reviewed}${counts.adRegister ?? 0} jawnych współprac jest w Rejestrze reklam, ${counts.incomplete ?? 0} ma niepełne dane. To nie jest błąd.`];
    case "register":
      return ["W zbadanych materiałach nie znaleziono relacji reklamowych", `${reviewed}Zakres: opis i dostępna mowa.${counts.incomplete > 0 ? ` ${counts.incomplete} materiałów bez ustalonej relacji czeka na przeliczenie, więc rejestr może być niepełny.` : ""}`];
    case "m2":
      return ["Brak przechwyconych stron M2 w tym skanie", "Sprawdź zakładkę Źródła: ostatni udany odczyt i stan źródeł stron."];
    case "m3":
      return ["Brak przechwyconych ofert M3 w tym skanie", "Sprawdź zakładkę Źródła: ostatni udany odczyt i stan rejestru."];
    case "incomplete":
      return ["Wszystkie materiały mają wystarczający zakres do oceny", "To nie jest błąd."];
    case "closed":
      return ["Nie ma jeszcze zamkniętych spraw", "Sprawa trafia tutaj po zapisaniu decyzji „Zamknij”."];
    default:
      return ["Brak materiałów demonstracyjnych i własnych plików", "Własny plik dodasz przyciskiem „Dodaj dowód”."];
  }
}

function QueueScreen({ tab, route, go, desk, counts, narrow, actions }) {
  const meta = TAB_BY_ID[tab];
  const { data, loadedAt, refresh } = desk;
  const queue = useQueue(meta.queue, data, loadedAt);
  const filters = route.filters;
  const scan = lastScanOf(data);
  const [panelClosed, setPanelClosed] = useState(false);
  const headingRef = useRef(null);
  const lastRow = useRef(null);
  const pane = useResizable({ defaultSize: "52%", minSize: "38%", maxSize: "66%", isReversed: true });
  const ready = queue.status === "ready" || queue.status === "refreshing";
  const items = ready ? applyFilters(queue.items, filters) : [];
  const sources = [...new Set(queue.items.map((c) => c.platform).filter(Boolean))].sort();
  const find = (id) => queue.items.find((c) => c.id === id) || data.cases.find((c) => c.id === id) || null;
  const selected = route.caseId ? find(route.caseId) : null;
  const split = meta.mode === "split";
  const auto = split && !narrow && !route.caseId && !panelClosed && items[0] ? items[0] : null;
  const shown = selected || auto;
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
    if (route.caseId && shown?.id === route.caseId && lastRow.current === route.caseId) {
      requestAnimationFrame(() => headingRef.current?.focus({ preventScroll: true }));
    }
  }, [route.caseId, shown?.id]);
  useEffect(() => setPanelClosed(false), [tab]);

  const real = (c) => c.origin === "live" || c.origin === "replay";
  const recalc = tab === "review" ? data.cases.filter((c) => c.module === "M1" && c.needsRecalc && real(c)).length : queue.items.filter((c) => c.needsRecalc).length;
  const [emptyTitle, emptyText] = emptyFor(tab, counts, scan);
  const filterText = describeFilters(filters);
  const nothingShown = ready && items.length === 0;
  const empty = !ready ? null : queue.items.length === 0
    ? <EmptyState isCompact title={emptyTitle} description={emptyText} actions={<HStack gap={2} wrap="wrap">
        {tab !== "register" && <Button label="Rejestr reklam" onClick={() => go("register")} />}
        {tab !== "incomplete" && <Button label="Niepełne dane" onClick={() => go("incomplete")} />}
      </HStack>} />
    : <NoResults filterText={filterText} clear={reset} hint={tab === "review" && counts.adRegister ? `${counts.adRegister} materiałów z jawną współpracą jest w Rejestrze reklam.` : "Zmień filtry albo wyczyść je."} />;

  const detail = shown && <CaseDetail key={shown.id} c={shown} headingRef={headingRef} onSaved={refresh} onBack={narrow || !split ? close : null} />;

  let list;
  if (queue.status === "error") list = <ErrorBlock message={queue.error} retry={refresh} />;
  else if (!ready) list = <Loading label="Pobieranie listy…" />;
  else if (meta.mode === "table" && !narrow) {
    list = tab === "register" ? <RegisterTable items={items} onOpen={open} emptyState={empty} /> : <OffersTable items={items} module={tab === "m2" ? "M2" : "M3"} onOpen={open} emptyState={empty} />;
  } else if (meta.mode === "table") {
    list = items.length === 0 ? empty : tab === "register" ? <RegisterList items={items} tab={tab} filters={filters} /> : <OffersList items={items} tab={tab} filters={filters} />;
  } else {
    list = <CaseList items={items} tab={tab} narrow={narrow} selectedId={shown?.id} filters={filters} onOpen={open} emptyState={empty} />;
  }

  // Odnośniki do wierszy potrzebują id do powrotu fokusu.
  const head = (
    <LayoutHeader padding={0} hasDivider>
      <VStack padding={4} gap={2}>
        <HStack gap={2} vAlign="center" wrap="wrap">
          <Heading level={1}>{TITLES[tab]}</Heading>
          {ready && <Badge label={tab === "review" && undecided(counts) ? "—" : String(queue.items.length)} />}
        </HStack>
        <Text color="secondary">{ready ? (narrow ? describe(tab, queue.items.length, counts).split(". ")[0] + "." : describe(tab, queue.items.length, counts)) : "Pobieranie danych…"}</Text>
        {tab === "review" && <Text type="supporting" color="secondary">Siła sygnału to punkty 0–100 z jawnych składników reguł, nie prawdopodobieństwo naruszenia.</Text>}
        <Text type="supporting" color="secondary" maxLines={narrow ? 2 : 0}>{scanLine(scan)}{queue.route === "adapter" ? " · lista zbudowana w przeglądarce (API kolejek jeszcze nie istnieje)" : ""}</Text>
      </VStack>
    </LayoutHeader>
  );

  const body = (
    <VStack gap={3} padding={narrow ? 2 : 4}>
      {recalc > 0 && (tab === "review" || tab === "incomplete") && (
        <Banner status="warning" title={`${recalc} ${plural(recalc, "materiał ma", "materiały mają", "materiałów ma")} wynik ze starszych reguł`}
          description={narrow ? undefined : tab === "review" ? "Takie materiały nie są tu uwzględnione, dopóki nie zostaną przeliczone. Ręczne decyzje i historia pozostają." : "Przeliczenie nie zmienia decyzji i historii."}
          endContent={<Button label="Przelicz materiały" isDisabled={actions.busy || actions.scanning} onClick={() => actions.scan("recompute")} />} />
      )}
      <Filters filters={filters} sources={sources} update={update} reset={reset} />
      {list}
    </VStack>
  );

  // Telefon i widoki tabelaryczne: jeden ekran naraz.
  if ((narrow || !split) && shown && route.caseId) {
    return (
      <Layout height="fill" content={<LayoutContent padding={0} isScrollable>{detail}</LayoutContent>} />
    );
  }
  return (
    <Layout height="fill" header={head}
      content={<LayoutContent padding={0} isScrollable>{body}</LayoutContent>}
      end={split && !narrow && (
        <>
          <ResizeHandle resizable={pane.props} direction="horizontal" isReversed hasDivider label="Zmień szerokość szczegółów" />
          <LayoutPanel padding={0} isScrollable resizable={pane.props} role="complementary" label="Szczegóły wybranej sprawy">
            {detail || (
              <VStack padding={6}><EmptyState title={nothingShown ? "Nie ma czego otwierać" : "Wybierz materiał"} description={nothingShown ? "Gdy lista będzie pusta, szczegół nie otwiera się sam." : "Tutaj zobaczysz uzasadnienie, dowody i zapiszesz decyzję."} /></VStack>
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
  const counts = data ? api.counts(data) : {};
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
  else if (tab === "sources") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><Sources data={data} busy={busy} scanning={scanning} onScan={startScan} /></LayoutContent>} />;
  else if (tab === "calibration") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><Calibration data={data} /></LayoutContent>} />;
  else if (tab === "evidence") content = <Layout height="fill" content={<LayoutContent padding={0} isScrollable><EvidenceForm onDone={schedule} onOpenDemo={() => go("demo")} /></LayoutContent>} />;
  else content = <QueueScreen key={tab} tab={tab} route={route} go={go} desk={desk} counts={counts} narrow={narrow} actions={actions} />;

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
                      endContent={data && t.queue && counts[t.queue] != null ? <Badge label={t.id === "review" && undecided(counts) ? "—" : String(counts[t.queue])} /> : undefined} />
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
