// Kalibracja: suwak progu z natychmiastowym podglądem z /v1/calibration (M1, M2 i M3), FP i FN jako duże liczby z różnicą,
// macierz 2×2, wykres FP i FN w funkcji progu (krzywa z `series`), skutek dla kolejki, zastrzeżenie „oceny agentów” w jednej linii.
// Historia ustawień, porównanie reguł i zbiór etykiet są pod „Więcej”. Zapis progu M1 robi API.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Grid } from "@astryxdesign/core/Grid";
import { Heading, Text } from "@astryxdesign/core/Text";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { Slider } from "@astryxdesign/core/Slider";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { MODULE_NAME, fmtDate, fmtDateTime } from "./labels.js";
import { Chart } from "./charts.jsx";
import { ExternalLink, Loading } from "./parts.jsx";

const pct = (v) => (v == null || Number.isNaN(v) ? null : `${Math.round(v * 100)}%`);
const Meta = ({ label, children }) => <MetadataListItem label={label}>{children}</MetadataListItem>;
const plural = (n, one, few, many) => (n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);
const cases = (n) => `${n} ${plural(n, "sprawa", "sprawy", "spraw")}`;
const PREVIOUS = { rules_1_2: "Poprzednie reguły" };

function Tile({ title, children, aside }) {
  return (
    <Card padding={2}>
      <VStack gap={1.5}>
        <HStack gap={2} hAlign="between" vAlign="center"><Heading level={2}>{title}</Heading>{aside}</HStack>
        {children}
      </VStack>
    </Card>
  );
}

function useHistory(load, rev) {
  const [state, setState] = useState({ status: "loading", items: [], error: null });
  useEffect(() => {
    let off = false;
    load().then((items) => !off && setState({ status: "ready", items, error: null }), (e) => !off && setState({ status: "error", items: [], error: e.message }));
    return () => {
      off = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rev]);
  return state;
}

/** Odpowiedzi kalibracji z pamięcią podręczną na czas pobytu w zakładce (klucz: moduł, wariant, wpis kwalifikacji, próg). */
function useCalibrationCache(variant, qualId, module) {
  const cache = useRef(new Map());
  useEffect(() => {
    cache.current = new Map();
  }, [variant, qualId, module]);
  return (t) => {
    const key = `${module}|${variant}|${qualId}|${t ?? "stored"}`;
    if (!cache.current.has(key)) {
      const p = api.calibration(t, module === "M1" ? variant : undefined, module);
      cache.current.set(key, p);
      p.catch(() => cache.current.delete(key));
    }
    return cache.current.get(key);
  };
}

/** Duża liczba z różnicą względem obowiązującego progu (zielona poprawa, czerwone pogorszenie). */
function Big({ label, value, delta, hint }) {
  const d = delta == null || delta === 0 ? null : delta > 0 ? `+${delta}` : String(delta);
  return (
    <Card padding={2} aria-label={`${label}: ${value}`} data-kpi={label}>
      <VStack gap={0.5}>
        <Text type="supporting" color="secondary">{label}</Text>
        <HStack gap={1} vAlign="baseline">
          <Heading level={2}>{value}</Heading>
          {d && <Token size="sm" color={delta > 0 ? "red" : "green"} label={`${d} względem obowiązującego`} />}
        </HStack>
        {hint && <Text type="supporting" color="secondary">{hint}</Text>}
      </VStack>
    </Card>
  );
}

function effectSentence(e, threshold) {
  if (!e) return null;
  const lost = e.lost?.length || 0;
  const gained = e.gained?.length || 0;
  if (!lost && !gained) return `Przy progu ${threshold} pkt kolejka „Do sprawdzenia” się nie zmienia (${cases(e.reviewQueueAtStored)}).`;
  const part = [lost ? `zniknie ${cases(lost)}` : null, gained ? `przybędzie ${cases(gained)}` : null].filter(Boolean).join(", ");
  return `Przy progu ${threshold} pkt z kolejki „Do sprawdzenia”: ${part} (${e.reviewQueueAtStored} → ${e.reviewQueueAtThreshold}).`;
}

const groupsText = (g) => (typeof g === "number" ? `${g} ${plural(g, "kampania", "kampanie", "kampanii")}` : g?.firms ? `${g.firms} ${plural(g.firms, "firma", "firmy", "firm")}` : null);
const splitText = (cal) => (cal.split === "holdout" ? "próba odłożona" : cal.split === "tuning" || cal.evaluationStatus === "agent_labels_tuning_set" ? "zbiór strojenia" : null);

export function Calibration({ data, rev, onChanged }) {
  const variant = data.qualification?.variant || data.threshold?.variant || "rules_1_2";
  const [module, setModule] = useState("M1");
  const [threshold, setThreshold] = useState(null);
  const [state, setState] = useState({ status: "loading" });
  const [nonce, setNonce] = useState(0);
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const thresholds = useHistory(() => api.thresholdHistory(), `${rev}-${nonce}`);
  const variants = useHistory(() => api.qualificationHistory(), `${rev}-${nonce}`);
  const getCal = useCalibrationCache(variant, data.qualification?.id, module);
  useEffect(() => setThreshold(null), [module, data.threshold?.value]);
  useEffect(() => {
    let cancelled = false;
    setState((s) => (s.cal ? { ...s, status: "refreshing" } : { status: "loading" }));
    const t = setTimeout(async () => {
      try {
        const first = await getCal(null);
        const stored = first.storedThreshold ?? first.threshold;
        const cal = threshold == null || threshold === stored ? first : await getCal(threshold);
        if (cancelled) return;
        setState(first.module && first.module !== module ? { status: "unsupported", got: first.module } : { status: "ready", cal, base: first, stored });
      } catch (e) {
        if (!cancelled) setState({ status: "error", error: e.message });
      }
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold, variant, nonce, data.qualification?.id, module]);

  async function act(fn, ok) {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      setConfirm(false);
      await onChanged?.();
      setNonce((n) => n + 1);
      setNotice({ status: "success", title: ok });
    } catch (e) {
      setNotice({ status: e.status === 409 ? "warning" : "error", title: e.status === 409 ? "Ktoś zmienił ustawienie w międzyczasie. Odświeżono dane; spróbuj ponownie." : `Nie zapisano: ${e.message}` });
      await onChanged?.();
    } finally {
      setBusy(false);
    }
  }

  const cal = state.cal;
  const base = state.base || cal;
  const applied = state.stored ?? data.threshold?.value ?? 60;
  const shown = threshold ?? applied;
  const series = base?.series;
  const chart = useMemo(() => {
    const rows = (series || []).filter((r) => r.threshold >= 20);
    return {
      type: "line",
      labels: rows.map((r) => String(r.threshold)),
      datasets: [
        { label: "Fałszywe alarmy (FP)", data: rows.map((r) => r.fp), color: "orange" },
        { label: "Przeoczenia (FN)", data: rows.map((r) => r.fn), color: "red" },
      ],
      yTitle: "liczba materiałów",
    };
  }, [series]);
  if (state.status === "error") {
    return <VStack padding={4}><Banner status="error" title="Nie można pobrać wyników kalibracji" description={state.error} endContent={<Button label="Spróbuj ponownie" onClick={() => setNonce((n) => n + 1)} />} /></VStack>;
  }
  const moduleSwitch = (
    <SegmentedControl label="Moduł kalibracji" size="sm" value={module} onChange={(v) => { setState({ status: "loading" }); setModule(v); }}>
      {Object.keys(MODULE_NAME).map((m) => <SegmentedControlItem key={m} value={m} label={MODULE_NAME[m]} />)}
    </SegmentedControl>
  );
  const head = <HStack gap={2} vAlign="center" wrap="wrap"><Heading level={1}>Kalibracja</Heading>{moduleSwitch}</HStack>;
  if (state.status === "unsupported") {
    return (
      <VStack gap={3} padding={3}>
        {head}
        <Banner status="info" title={`Brak kalibracji dla ${MODULE_NAME[module]}`} description={`API zwraca kalibrację tylko dla ${MODULE_NAME[state.got] || state.got}. Pulpit niczego nie liczy sam.`} />
      </VStack>
    );
  }
  if (!cal) return <VStack gap={3} padding={3}>{head}<Loading rows={4} label="Pobieranie wyników kalibracji…" /></VStack>;
  const measured = state.status === "ready";
  const effect = cal.queueEffect;
  const isM1 = module === "M1";
  const previous = Object.entries(cal.variants || {}).filter(([id]) => id !== (cal.variant || variant) && PREVIOUS[id]).map(([id, x]) => `${PREVIOUS[id]} przy tym progu: FP ${x.fp}, FN ${x.fn}`)[0];
  const ci = cal.precisionCI;
  const lowN = cal.tp + cal.fp < 20;
  const split = splitText(cal);
  const banner = `Oceny agentów, nie walidacja ekspercka · ${cal.n} ${plural(cal.n, "materiał", "materiały", "materiałów")}${groupsText(cal.groups) ? ` · ${groupsText(cal.groups)}` : ""}${split ? ` · ${split}` : ""}`;
  const compare = Object.entries(cal.variants || {}).map(([id, x]) => ({ id, ...x }));
  const q = data.qualification;
  return (
    <VStack gap={2} padding={3}>
      {head}
      <Banner status="warning" title={banner} />
      {notice && <Banner status={notice.status} title={notice.title} isDismissable onDismiss={() => setNotice(null)} />}
      <Card padding={2}>
        <VStack gap={2}>
          <Slider label={`Próg ${shown} punktów`} value={shown} min={0} max={100} step={5} valueDisplay="text" onChange={setThreshold}
            marks={[{ value: 0, label: "0" }, { value: applied, label: `obowiązuje ${applied}` }, { value: 100, label: "100" }]}
            description="Przesuń suwak: liczby poniżej liczą się od razu na tym samym zbiorze." />
          <Grid columns={{ minWidth: 200, max: 4 }} gap={2}>
            <Big label="Fałszywe alarmy (FP)" value={cal.fp} delta={cal.fp - base.fp} />
            <Big label="Przeoczenia (FN)" value={cal.fn} delta={cal.fn - base.fn} />
            <Card padding={2} data-kpi="Wynik">
              <VStack gap={0.5}>
                <Text type="supporting" color="secondary">Wynik na zbiorze</Text>
                <Text weight="semibold">{cal.tp} {plural(cal.tp, "trafienie", "trafienia", "trafień")}, {cal.fp} {cal.fp === 1 ? "fałszywy alarm" : "fałszywych alarmów"} na {cal.n} {plural(cal.n, "materiale", "materiałach", "materiałach")}</Text>
                <Text type="supporting" color="secondary">{ci ? `Skierowano ${cal.tp + cal.fp}, przedział trafności ${pct(ci.low)}–${pct(ci.high)}. ` : ""}Koszt (2×FN + FP): {cal.cost}.{lowN ? " Za mało skierowań do oceny precyzji: wynik orientacyjny." : ""}</Text>
              </VStack>
            </Card>
            <Table idKey="row" density="compact" aria-label="Macierz pomyłek" data={[
              { row: "Skierowane", yes: `${cal.tp} trafnych`, no: `${cal.fp} fałszywych` },
              { row: "Nie skierowane", yes: `${cal.fn} przeoczonych`, no: `${cal.tn} poprawnie` },
            ]} columns={[
              { key: "row", header: "", width: proportional(2, { minWidth: 90 }), renderCell: (r) => <Text weight="medium">{r.row}</Text> },
              { key: "yes", header: "Agent: przesłanka", width: proportional(2, { minWidth: 90 }), renderCell: (r) => r.yes },
              { key: "no", header: "Agent: brak", width: proportional(2, { minWidth: 90 }), renderCell: (r) => r.no },
            ]} />
          </Grid>
          <VStack gap={0.5}>
            <HStack gap={1} vAlign="center" wrap="wrap">
              <StatusDot variant={measured ? "success" : "neutral"} label={measured ? "Podgląd aktualny" : "Liczenie…"} />
              <Text role="status" aria-live="polite" data-testid="queue-effect">{effectSentence(effect, shown) || "Skutek dla kolejki: brak danych."}</Text>
            </HStack>
            {previous && <Text type="supporting" color="secondary">{previous}.</Text>}
          </VStack>
          {isM1 && (
            <HStack gap={2} wrap="wrap" vAlign="center">
              {shown !== applied && !confirm && <Button label={`Zastosuj ${shown} pkt`} variant="primary" size="sm" onClick={() => setConfirm(true)} />}
              {confirm && (
                <>
                  <Text type="supporting">Zmiana progu zmienia kolejkę „Do sprawdzenia”. Zapisze się w historii.</Text>
                  <Button label="Potwierdź zmianę progu" variant="primary" size="sm" isLoading={busy} onClick={() => act(() => api.setThreshold({ value: shown, expectedId: data.threshold.id, variant, note: "Ustawiono z pulpitu" }), `Próg ustawiony na ${shown} pkt.`)} />
                  <Button label="Anuluj" variant="ghost" size="sm" onClick={() => setConfirm(false)} />
                </>
              )}
              {shown !== applied && !confirm && <Button label="Wróć do obowiązującego" variant="ghost" size="sm" onClick={() => setThreshold(null)} />}
            </HStack>
          )}
          {!isM1 && shown !== applied && <HStack><Button label="Wróć do obowiązującego" variant="ghost" size="sm" onClick={() => setThreshold(null)} /></HStack>}
        </VStack>
      </Card>
      <Tile title="Fałszywe alarmy i przeoczenia a próg">
        {chart.labels.length < 2 ? <Text color="secondary" role="status">Liczenie punktów wykresu…</Text> : (
          <Chart spec={chart} height={220} label={`Wykres: fałszywe alarmy i przeoczenia w funkcji progu. ${chart.labels.map((l, i) => `próg ${l}: FP ${chart.datasets[0].data[i]}, FN ${chart.datasets[1].data[i]}`).join("; ")}`} />
        )}
      </Tile>
      {(cal.errors || []).length > 0 && (
        <Tile title="Przeoczenia i fałszywe alarmy przy tym progu">
          <Table idKey="id" density="compact" verticalAlign="top" data={cal.errors} columns={[
            { key: "t", header: "Przykład", width: proportional(3, { minWidth: 150 }), renderCell: (e) => <VStack gap={0.5}><Text weight="medium" maxLines={2}>{e.firm && e.title === e.id ? e.firm : e.title || e.id}</Text>{e.text && <Text type="supporting" color="secondary" maxLines={2}>{e.text.replace(/trasa (\w+)/, (_, r) => `trasa: ${({ no_signal: "bez przesłanki", refer: "do sprawdzenia", complete: "niepełne", insufficient: "niepełne" })[r] || r}`).replace(/wynik reguł/, "siła")}</Text>}</VStack> },
            { key: "o", header: "Wynik", width: pixel(130), renderCell: (e) => <Text>{e.outcome === "fp" ? "fałszywy alarm" : "przeoczenie"}</Text> },
            { key: "s", header: "Siła", align: "end", width: pixel(80), renderCell: (e) => e.score },
            { key: "u", header: "", width: pixel(80), renderCell: (e) => <ExternalLink url={e.url}>Źródło ↗</ExternalLink> },
          ]} />
        </Tile>
      )}
      <Collapsible defaultIsOpen={false} trigger={<Text weight="semibold">Więcej: historia ustawień, porównanie reguł, zbiór etykiet</Text>}>
        <Grid columns={{ minWidth: 340, max: 2 }} gap={3} padding={2}>
          {compare.length > 0 && (
            <Tile title="Porównanie reguł przy progu" aside={<Token size="sm" color="gray" label={`${shown} pkt`} />}>
              <Table idKey="id" density="compact" data={compare} columns={[
                { key: "v", header: "Reguły", width: proportional(3, { minWidth: 120 }), renderCell: (x) => <Text weight={x.id === (cal.variant || variant) ? "semibold" : undefined}>{PREVIOUS[x.id] || "Obowiązujące reguły"}{x.id === (cal.variant || variant) ? " (aktywne)" : ""}</Text> },
                { key: "tp", header: "TP", align: "end", width: pixel(44), renderCell: (x) => x.tp },
                { key: "fp", header: "FP", align: "end", width: pixel(44), renderCell: (x) => x.fp },
                { key: "tn", header: "TN", align: "end", width: pixel(44), renderCell: (x) => x.tn },
                { key: "fn", header: "FN", align: "end", width: pixel(44), renderCell: (x) => x.fn },
                { key: "cost", header: "Koszt", align: "end", width: pixel(60), renderCell: (x) => x.cost },
              ]} />
              <Text type="supporting" color="secondary">Koszt = 2 × przeoczenia + fałszywe alarmy.</Text>
            </Tile>
          )}
          {isM1 && (
            <Tile title="Historia progu" aside={<Token size="sm" color="gray" label={`${thresholds.items.length} wpisów`} />}>
              {thresholds.status === "error" ? <Text color="secondary">Nie można pobrać historii: {thresholds.error}</Text> : (
                <Table idKey="id" density="compact" verticalAlign="top" data={[...thresholds.items].reverse()} columns={[
                  { key: "v", header: "Próg", width: pixel(110), renderCell: (h) => <Text>{h.value} pkt{h.id === data.threshold?.id ? " (aktywny)" : ""}</Text> },
                  { key: "at", header: "Od", width: pixel(100), renderCell: (h) => <Text type="supporting">{fmtDate(h.setAt)}</Text> },
                  { key: "note", header: "Uwaga", width: proportional(3, { minWidth: 100 }), renderCell: (h) => <Text type="supporting" maxLines={2}>{h.note || "—"}</Text> },
                  { key: "do", header: "", width: pixel(104), renderCell: (h) => (h.id === data.threshold?.id ? null : <Button size="sm" label="Przywróć" isDisabled={busy} onClick={() => act(() => api.restoreThreshold({ id: h.id, expectedId: data.threshold.id, note: "Przywrócono z pulpitu" }), `Przywrócono próg ${h.value} pkt.`)} />) },
                ]} />
              )}
            </Tile>
          )}
          {isM1 && (
            <Tile title="Obowiązujące reguły">
              <MetadataList>
                <Meta label="Od">{fmtDateTime(q?.setAt)}</Meta>
                <Meta label="Uwaga">{q?.note || "—"}</Meta>
              </MetadataList>
              <Table idKey="id" density="compact" verticalAlign="top" data={[...variants.items].reverse()} columns={[
                { key: "at", header: "Od", width: pixel(100), renderCell: (h) => <Text type="supporting">{fmtDate(h.setAt)}{h.id === q?.id ? " (aktywne)" : ""}</Text> },
                { key: "note", header: "Uwaga", width: proportional(3, { minWidth: 120 }), renderCell: (h) => <Text type="supporting" maxLines={2}>{h.note || "—"}</Text> },
                { key: "do", header: "", width: pixel(104), renderCell: (h) => (h.id === q?.id ? null : <Button size="sm" label="Przywróć" isDisabled={busy} onClick={() => act(() => api.restoreQualification({ id: h.id, expectedId: q.id, note: "Przywrócono z pulpitu" }), "Przywrócono reguły. Trwa przeliczenie materiałów.")} />) },
              ]} />
            </Tile>
          )}
          <Tile title="Zbiór etykiet">
            <MetadataList>
              <Meta label="Cel etykiety">{cal.labelTarget || "nieopisany"}</Meta>
              <Meta label="Liczebność">{cal.n} przykładów ({cal.publicExamples ?? "?"} publicznych, {cal.syntheticExamples ?? "?"} syntetycznych)</Meta>
              <Meta label="Niezależne jednostki">{groupsText(cal.groups) || "nieznane"}</Meta>
              <Meta label="Etykietowali">{typeof cal.labelers === "string" ? cal.labelers : cal.labelers && typeof cal.labelers === "object" ? `${Object.keys(cal.labelers).length} niezależnych oceniających` : "—"}</Meta>
              <Meta label="Podział">{split || "bez podziału"}{cal.frozenAt ? `, zamrożono ${fmtDate(cal.frozenAt)}` : ""}</Meta>
            </MetadataList>
          </Tile>
        </Grid>
      </Collapsible>
    </VStack>
  );
}
