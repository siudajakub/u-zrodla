// Kalibracja: suwak progu z natychmiastowym podglądem TP/FP/TN/FN z /v1/calibration, wykres FP i FN w funkcji progu,
// skutek dla kolejki (queueEffect), porównanie wariantów, historia progu i wariantu z przywracaniem. Zapis progu robi API.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Grid } from "@astryxdesign/core/Grid";
import { Heading, Text } from "@astryxdesign/core/Text";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Slider } from "@astryxdesign/core/Slider";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { VARIANTS, fmtDate, fmtDateTime } from "./labels.js";
import { Chart } from "./charts.jsx";
import { ExternalLink, Loading } from "./parts.jsx";

const pct = (v) => (v == null || Number.isNaN(v) ? null : `${Math.round(v * 100)}%`);
const Meta = ({ label, children }) => <MetadataListItem label={label}>{children}</MetadataListItem>;

function Tile({ title, children, aside }) {
  return (
    <Card padding={3}>
      <VStack gap={2}>
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

const GRID = [30, 50, 60, 70, 80, 90, 100];

const rates = (x) => {
  const referred = x.tp + x.fp;
  return { precision: referred ? x.tp / referred : null, recall: x.tp + x.fn ? x.tp / (x.tp + x.fn) : null };
};

/** Odpowiedzi kalibracji z pamięcią podręczną na czas pobytu w zakładce (klucz: wariant, wpis kwalifikacji, próg). */
function useCalibrationCache(variant, qualId) {
  const cache = useRef(new Map());
  useEffect(() => {
    cache.current = new Map();
  }, [variant, qualId]);
  return (t) => {
    const key = `${variant}|${qualId}|${t}`;
    if (!cache.current.has(key)) {
      const p = api.calibration(t, variant);
      cache.current.set(key, p);
      p.catch(() => cache.current.delete(key));
    }
    return cache.current.get(key);
  };
}

function Kpi({ label, value, delta, tone, hint }) {
  const d = delta == null || delta === 0 ? null : delta > 0 ? `+${delta}` : String(delta);
  return (
    <Card padding={2} aria-label={`${label}: ${value}`}>
      <VStack gap={0.5}>
        <Text type="supporting" color="secondary">{label}</Text>
        <HStack gap={1} vAlign="baseline">
          <Heading level={2}>{value}</Heading>
          {d && <Token size="sm" color={tone === "bad-up" ? (delta > 0 ? "red" : "green") : "gray"} label={`${d} względem obowiązującego`} />}
        </HStack>
        {hint && <Text type="supporting" color="secondary">{hint}</Text>}
      </VStack>
    </Card>
  );
}

const cases = (n) => `${n} ${n === 1 ? "sprawa" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "sprawy" : "spraw"}`;

function effectSentence(e, threshold) {
  if (!e) return null;
  const lost = e.lost?.length || 0;
  const gained = e.gained?.length || 0;
  if (!lost && !gained) return `Przy progu ${threshold} pkt kolejka „Co wymaga sprawdzenia” się nie zmienia (${cases(e.reviewQueueAtStored)}).`;
  const part = [lost ? `zniknie ${cases(lost)}` : null, gained ? `przybędzie ${cases(gained)}` : null].filter(Boolean).join(", ");
  return `Przy progu ${threshold} pkt z kolejki „Co wymaga sprawdzenia”: ${part} (${e.reviewQueueAtStored} → ${e.reviewQueueAtThreshold}).`;
}

export function Calibration({ data, rev, onChanged }) {
  const variant = data.qualification?.variant || data.threshold?.variant || "rules_1_2";
  const applied = data.threshold?.value ?? 60;
  const [threshold, setThreshold] = useState(applied);
  const [state, setState] = useState({ status: "loading" });
  const [curve, setCurve] = useState({});
  const [nonce, setNonce] = useState(0);
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const thresholds = useHistory(() => api.thresholdHistory(), `${rev}-${nonce}`);
  const variants = useHistory(() => api.qualificationHistory(), `${rev}-${nonce}`);
  const getCal = useCalibrationCache(variant, data.qualification?.id);
  useEffect(() => setThreshold(applied), [applied]);
  useEffect(() => {
    let cancelled = false;
    setState((s) => (s.cal ? { ...s, status: "refreshing" } : { status: "loading" }));
    const t = setTimeout(() => {
      Promise.all([getCal(threshold), getCal(applied)]).then(
        ([cal, base]) => !cancelled && setState({ status: "ready", cal, base }),
        (e) => !cancelled && setState({ status: "error", error: e.message }),
      );
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold, applied, variant, nonce, data.qualification?.id]);
  const points = useMemo(() => [...new Set([...GRID, applied, threshold])].sort((a, b) => a - b), [applied, threshold]);
  useEffect(() => {
    let cancelled = false;
    const todo = points.filter((p) => !(p in curve));
    let next = 0;
    const worker = async () => {
      while (!cancelled && next < todo.length) {
        const p = todo[next++];
        try {
          const c = await getCal(p);
          if (!cancelled) setCurve((m) => ({ ...m, [p]: { fp: c.fp, fn: c.fn, tp: c.tp } }));
        } catch {
          /* punkt wykresu pominięty */
        }
      }
    };
    Promise.all([worker(), worker(), worker()]);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points.join(","), variant, data.qualification?.id]);
  useEffect(() => setCurve({}), [variant, data.qualification?.id]);

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
  const chart = useMemo(() => {
    const xs = points.filter((p) => p in curve);
    return {
      type: "line",
      labels: xs.map(String),
      datasets: [
        { label: "Fałszywe alarmy (FP)", data: xs.map((p) => curve[p].fp), color: "orange" },
        { label: "Przeoczenia (FN)", data: xs.map((p) => curve[p].fn), color: "red" },
      ],
      yTitle: "liczba materiałów",
    };
  }, [curve, points.join(",")]);
  if (state.status === "error") {
    return <VStack padding={4}><Banner status="error" title="Nie można pobrać wyników kalibracji" description={state.error} endContent={<Button label="Spróbuj ponownie" onClick={() => setNonce((n) => n + 1)} />} /></VStack>;
  }
  if (!cal) return <Loading rows={4} label="Pobieranie wyników kalibracji…" />;
  const { precision, recall } = rates(cal);
  const ci = cal.precisionCI;
  const q = data.qualification;
  const measured = state.status === "ready";
  const effect = cal.queueEffect;
  const compare = Object.entries(cal.variants || {}).map(([id, x]) => ({ id, ...x, ...rates(x) }));
  return (
    <VStack gap={3} padding={3}>
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Heading level={1}>Kalibracja</Heading>
        <Text type="supporting" color="secondary">Jak próg i wariant reguł zgadzają się z ręcznymi etykietami.</Text>
      </HStack>
      <Banner status="warning" title="Oceny agentów, nie walidacja ekspercka" description={`${cal.disclaimer || "Wyniki opierają się na etykietach zespołu i agentów, na małej próbie."} Punkty to siła przesłanki do kontroli, nie prawdopodobieństwo.`} />
      {notice && <Banner status={notice.status} title={notice.title} isDismissable onDismiss={() => setNotice(null)} />}
      <Card padding={3}>
        <VStack gap={2}>
          <HStack gap={2} hAlign="between" vAlign="center" wrap="wrap">
            <Heading level={2}>Próg: podgląd na zbiorze etykiet</Heading>
            <HStack gap={1} wrap="wrap">
              <Token size="sm" color="blue" label={VARIANTS[variant] || variant} />
              <Token size="sm" color="gray" label={`obowiązuje ${applied} pkt`} />
            </HStack>
          </HStack>
          <Slider label={`Próg ${threshold} punktów`} value={threshold} min={0} max={100} step={5} valueDisplay="text" onChange={setThreshold}
            marks={[{ value: 0, label: "0" }, { value: applied, label: `obowiązuje ${applied}` }, { value: 100, label: "100" }]}
            description="Przesuń suwak: liczby poniżej liczą się od razu na tym samym zbiorze. Zapis zmienia kolejkę dopiero po potwierdzeniu." />
          <Grid columns={{ minWidth: 150, max: 7 }} gap={2}>
            <Kpi label="Trafienia (TP)" value={cal.tp} delta={cal.tp - base.tp} tone="good-up" />
            <Kpi label="Fałszywe alarmy (FP)" value={cal.fp} delta={cal.fp - base.fp} tone="bad-up" />
            <Kpi label="Poprawnie odrzucone (TN)" value={cal.tn} delta={cal.tn - base.tn} tone="good-up" />
            <Kpi label="Przeoczenia (FN)" value={cal.fn} delta={cal.fn - base.fn} tone="bad-up" />
            <Kpi label="Precyzja" value={precision == null ? "—" : pct(precision)} hint={ci ? `95%: ${pct(ci.low)}–${pct(ci.high)}` : "bez przedziału"} />
            <Kpi label="Pełność" value={recall == null ? "—" : pct(recall)} />
            <Kpi label="Koszt (2×FN + FP)" value={cal.cost} delta={cal.cost - base.cost} tone="bad-up" />
          </Grid>
          <HStack gap={1} vAlign="center" wrap="wrap">
            <StatusDot variant={measured ? "success" : "neutral"} label={measured ? "Podgląd aktualny" : "Liczenie…"} />
            <Text role="status" aria-live="polite" data-testid="queue-effect">{effectSentence(effect, threshold) || "Skutek dla kolejki: brak danych."}</Text>
          </HStack>
          <HStack gap={2} wrap="wrap" vAlign="center">
            {threshold !== applied && !confirm && <Button label={`Zastosuj ${threshold} pkt`} variant="primary" size="sm" onClick={() => setConfirm(true)} />}
            {confirm && (
              <>
                <Text type="supporting">Zmiana progu zmienia kolejkę „Co wymaga sprawdzenia”. Zapisze się w historii.</Text>
                <Button label="Potwierdź zmianę progu" variant="primary" size="sm" isLoading={busy} onClick={() => act(() => api.setThreshold({ value: threshold, expectedId: data.threshold.id, variant, note: "Ustawiono z pulpitu" }), `Próg ustawiony na ${threshold} pkt.`)} />
                <Button label="Anuluj" variant="ghost" size="sm" onClick={() => setConfirm(false)} />
              </>
            )}
            {threshold !== applied && !confirm && <Button label="Wróć do obowiązującego" variant="ghost" size="sm" onClick={() => setThreshold(applied)} />}
          </HStack>
          {referredNote(cal)}
        </VStack>
      </Card>
      <Grid columns={{ minWidth: 340, max: 2 }} gap={3}>
        <Tile title="Fałszywe alarmy i przeoczenia a próg">
          {chart.labels.length < 2 ? <Text color="secondary" role="status">Liczenie punktów wykresu…</Text> : (
            <Chart spec={chart} height={240} label={`Wykres: fałszywe alarmy i przeoczenia w funkcji progu. ${chart.labels.map((l, i) => `próg ${l}: FP ${chart.datasets[0].data[i]}, FN ${chart.datasets[1].data[i]}`).join("; ")}`} />
          )}
          <Text type="supporting" color="secondary">Wyższy próg zwykle zmniejsza liczbę fałszywych alarmów i zwiększa liczbę przeoczeń. Wykres liczy ten sam zbiór dla kilku progów.</Text>
        </Tile>
        <Tile title="Wariant reguł: porównanie przy progu" aside={<Token size="sm" color="gray" label={`${threshold} pkt`} />}>
          <Table idKey="id" density="compact" data={compare} columns={[
            { key: "v", header: "Wariant", width: proportional(3, { minWidth: 120 }), renderCell: (x) => <Text weight={x.id === variant ? "semibold" : undefined}>{VARIANTS[x.id] || x.id}{x.id === variant ? " (aktywny)" : ""}</Text> },
            { key: "tp", header: "TP", align: "end", width: pixel(44), renderCell: (x) => x.tp },
            { key: "fp", header: "FP", align: "end", width: pixel(44), renderCell: (x) => x.fp },
            { key: "tn", header: "TN", align: "end", width: pixel(44), renderCell: (x) => x.tn },
            { key: "fn", header: "FN", align: "end", width: pixel(44), renderCell: (x) => x.fn },
            { key: "cost", header: "Koszt", align: "end", width: pixel(60), renderCell: (x) => x.cost },
            { key: "p", header: "Precyzja", align: "end", width: pixel(80), renderCell: (x) => (x.precision == null ? "—" : pct(x.precision)) },
            { key: "r", header: "Pełność", align: "end", width: pixel(72), renderCell: (x) => (x.recall == null ? "—" : pct(x.recall)) },
          ]} />
          <Text type="supporting" color="secondary">Koszt = 2 × przeoczenia + fałszywe alarmy. Zbiór: {cal.n} przykładów z {cal.groups ?? "?"} niezależnych kampanii.</Text>
        </Tile>
        <Tile title="Aktywny wariant" aside={<Token size="sm" color="blue" label={VARIANTS[variant] || variant} />}>
          <MetadataList>
            <Meta label="Od">{fmtDateTime(q?.setAt)}</Meta>
            <Meta label="Uwaga">{q?.note || "—"}</Meta>
            <Meta label="Pomiar">{q?.validationRef ? <Text type="supporting">{q.validationRef}</Text> : "brak odnośnika do pomiaru"}</Meta>
            <Meta label="Zatwierdził">{q?.validatedBy || "—"}</Meta>
          </MetadataList>
          <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Historia wariantu ({variants.items.length})</Text>}>
            <Table idKey="id" density="compact" verticalAlign="top" data={[...variants.items].reverse()} columns={[
              { key: "v", header: "Wariant", width: proportional(2, { minWidth: 110 }), renderCell: (h) => <Text>{VARIANTS[h.variant] || h.variant}{h.id === q?.id ? " (aktywny)" : ""}</Text> },
              { key: "at", header: "Od", width: pixel(100), renderCell: (h) => <Text type="supporting">{fmtDate(h.setAt)}</Text> },
              { key: "ref", header: "Pomiar", width: proportional(3, { minWidth: 120 }), renderCell: (h) => <Text type="supporting" maxLines={2}>{h.validationRef || "bez pomiaru"}</Text> },
              { key: "do", header: "", width: pixel(104), renderCell: (h) => (h.id === q?.id ? null : <Button size="sm" label="Przywróć" isDisabled={busy} onClick={() => act(() => api.restoreQualification({ id: h.id, expectedId: q.id, note: "Przywrócono z pulpitu" }), "Przywrócono wariant. Trwa przeliczenie materiałów.")} />) },
            ]} />
          </Collapsible>
        </Tile>
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
        <Tile title="Zbiór etykiet">
          <MetadataList>
            <Meta label="Cel etykiety">{cal.labelTarget || <Token size="sm" color="yellow" label="nieopisany" />}</Meta>
            <Meta label="Liczebność">{cal.n} przykładów ({cal.publicExamples ?? "?"} publicznych, {cal.syntheticExamples ?? "?"} syntetycznych)</Meta>
            <Meta label="Niezależne kampanie">{cal.groups != null ? cal.groups : "nieznane"}</Meta>
            <Meta label="Podział">{cal.split === "holdout" ? "próba odłożona" : cal.split === "tuning" ? "zbiór strojenia" : "bez podziału"}{cal.frozenAt ? `, zamrożono ${fmtDate(cal.frozenAt)}` : ""}</Meta>
            {cal.gate?.status && <Meta label="Bramka">{cal.gate.status}{cal.gate.reason ? `: ${cal.gate.reason}` : ""}</Meta>}
          </MetadataList>
        </Tile>
      </Grid>
      {(cal.errors || []).length > 0 && (
        <Tile title="Przeoczenia i fałszywe alarmy przy tym progu">
          <Table idKey="id" density="compact" verticalAlign="top" data={cal.errors} columns={[
            { key: "t", header: "Przykład", width: proportional(3, { minWidth: 150 }), renderCell: (e) => <VStack gap={0.5}><Text weight="medium" maxLines={2}>{e.title || e.id}</Text>{e.text && <Text type="supporting" color="secondary" maxLines={2}>{e.text}</Text>}</VStack> },
            { key: "o", header: "Wynik", width: pixel(130), renderCell: (e) => <Text>{e.outcome === "fp" ? "fałszywy alarm" : "przeoczenie"}</Text> },
            { key: "s", header: "Punkty", align: "end", width: pixel(80), renderCell: (e) => e.score },
            { key: "u", header: "", width: pixel(80), renderCell: (e) => <ExternalLink url={e.url}>Źródło ↗</ExternalLink> },
          ]} />
        </Tile>
      )}
    </VStack>
  );
}

function referredNote(cal) {
  return cal.tp + cal.fp < 20 ? <Text type="supporting" color="secondary">Za mało skierowań do oceny precyzji (potrzeba 20 z różnych kampanii); wynik orientacyjny.</Text> : null;
}
