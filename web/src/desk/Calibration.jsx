// Kalibracja: kafelki (wariant, próg, pomiar, zbiór etykiet) z historią i przywracaniem. Próg i wariant zapisuje API.
import React, { useEffect, useState } from "react";
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
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { VARIANTS, fmtDate, fmtDateTime } from "./labels.js";
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

export function Calibration({ data, rev, onChanged }) {
  const variant = data.qualification?.variant || data.threshold?.variant || "rules_1_2";
  const applied = data.threshold?.value ?? 60;
  const [threshold, setThreshold] = useState(applied);
  const [state, setState] = useState({ status: "loading" });
  const [nonce, setNonce] = useState(0);
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const thresholds = useHistory(() => api.thresholdHistory(), `${rev}-${nonce}`);
  const variants = useHistory(() => api.qualificationHistory(), `${rev}-${nonce}`);
  useEffect(() => setThreshold(applied), [applied]);
  useEffect(() => {
    let cancelled = false;
    setState((s) => (s.cal ? { ...s, status: "refreshing" } : { status: "loading" }));
    const t = setTimeout(() => {
      api.calibration(threshold, variant).then(
        (cal) => !cancelled && setState({ status: "ready", cal }),
        (e) => !cancelled && setState({ status: "error", error: e.message }),
      );
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [threshold, variant, nonce, data.qualification?.id]);

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
  if (state.status === "error") {
    return <VStack padding={4}><Banner status="error" title="Nie można pobrać wyników kalibracji" description={state.error} endContent={<Button label="Spróbuj ponownie" onClick={() => setNonce((n) => n + 1)} />} /></VStack>;
  }
  if (!cal) return <Loading rows={4} label="Pobieranie wyników kalibracji…" />;
  const referred = cal.tp + cal.fp;
  const precision = referred ? cal.tp / referred : null;
  const recall = cal.tp + cal.fn ? cal.tp / (cal.tp + cal.fn) : null;
  const ci = cal.precisionCI;
  const q = data.qualification;
  return (
    <VStack gap={3} padding={3}>
      <HStack gap={2} vAlign="center" wrap="wrap">
        <Heading level={1}>Kalibracja</Heading>
        <Text type="supporting" color="secondary">Jak próg i wariant reguł zgadzają się z ręcznymi etykietami.</Text>
      </HStack>
      <Banner status="warning" title="Oceny agentów, nie walidacja ekspercka" description="Wyniki opierają się na etykietach zespołu i agentów, na małej próbie. Punkty to siła przesłanki do kontroli, nie prawdopodobieństwo." />
      {notice && <Banner status={notice.status} title={notice.title} isDismissable onDismiss={() => setNotice(null)} />}
      <Grid columns={{ minWidth: 340, max: 2 }} gap={3}>
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
        <Tile title="Próg" aside={<Token size="sm" color="gray" label={`obowiązuje ${applied} pkt`} />}>
          <Slider label={`Próg ${threshold} punktów`} value={threshold} valueDisplay="none" onChange={setThreshold} description="Przesuń, aby zobaczyć wynik na tym samym zbiorze." />
          <HStack gap={2} wrap="wrap" vAlign="center">
            {threshold !== applied && !confirm && <Button label={`Zastosuj ${threshold} pkt`} variant="primary" size="sm" onClick={() => setConfirm(true)} />}
            {confirm && (
              <>
                <Text type="supporting">Zmiana progu zmienia kolejkę „Co wymaga sprawdzenia”. Zapisze się w historii.</Text>
                <Button label="Potwierdź zmianę progu" variant="primary" size="sm" isLoading={busy} onClick={() => act(() => api.setThreshold({ value: threshold, expectedId: data.threshold.id, variant, note: "Ustawiono z pulpitu" }), `Próg ustawiony na ${threshold} pkt.`)} />
                <Button label="Anuluj" variant="ghost" size="sm" onClick={() => setConfirm(false)} />
              </>
            )}
          </HStack>
          <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Historia progu ({thresholds.items.length})</Text>}>
            {thresholds.status === "error" ? <Text color="secondary">Nie można pobrać historii: {thresholds.error}</Text> : (
              <Table idKey="id" density="compact" verticalAlign="top" data={[...thresholds.items].reverse()} columns={[
                { key: "v", header: "Próg", width: pixel(80), renderCell: (h) => <Text>{h.value} pkt{h.id === data.threshold?.id ? " (aktywny)" : ""}</Text> },
                { key: "at", header: "Od", width: pixel(100), renderCell: (h) => <Text type="supporting">{fmtDate(h.setAt)}</Text> },
                { key: "note", header: "Uwaga", width: proportional(3, { minWidth: 100 }), renderCell: (h) => <Text type="supporting" maxLines={2}>{h.note || "—"}</Text> },
                { key: "do", header: "", width: pixel(104), renderCell: (h) => (h.id === data.threshold?.id ? null : <Button size="sm" label="Przywróć" isDisabled={busy} onClick={() => act(() => api.restoreThreshold({ id: h.id, expectedId: data.threshold.id, note: "Przywrócono z pulpitu" }), `Przywrócono próg ${h.value} pkt.`)} />) },
              ]} />
            )}
          </Collapsible>
        </Tile>
        <Tile title={`Pomiar przy progu ${threshold}`}>
          <Table idKey="metric" density="compact" columns={[
            { key: "metric", header: "Wynik", width: proportional(3) },
            { key: "value", header: "Wartość", align: "end", width: proportional(2) },
          ]} data={[
            { metric: "Trafienia", value: cal.tp },
            { metric: "Fałszywe alarmy", value: cal.fp },
            { metric: "Poprawnie odrzucone", value: cal.tn },
            { metric: "Przeoczenia", value: cal.fn },
            { metric: "Precyzja", value: referred ? `${pct(precision)}${ci ? ` (95%: ${pct(ci.low)}–${pct(ci.high)})` : ", bez przedziału"}` : "brak skierowań" },
            { metric: "Pełność", value: recall == null ? "brak podstaw" : pct(recall) },
            { metric: "Koszt (2 × przeoczenia + alarmy)", value: cal.cost },
            { metric: "Wstrzymane (bez wniosku)", value: cal.withheld ?? "brak danych" },
          ]} />
        </Tile>
        <Tile title="Zbiór etykiet">
          <MetadataList>
            <Meta label="Cel etykiety">{cal.labelTarget || <Token size="sm" color="yellow" label="nieopisany" />}</Meta>
            <Meta label="Liczebność">{cal.n} przykładów ({cal.publicExamples ?? "?"} publicznych, {cal.syntheticExamples ?? "?"} syntetycznych)</Meta>
            <Meta label="Niezależne kampanie">{cal.groups != null ? cal.groups : "nieznane"}</Meta>
            <Meta label="Podział">{cal.split === "holdout" ? "próba odłożona" : cal.split === "tuning" ? "zbiór strojenia" : "bez podziału"}{cal.frozenAt ? `, zamrożono ${fmtDate(cal.frozenAt)}` : ""}</Meta>
          </MetadataList>
          {referred < 20 && <Text type="supporting">Za mało skierowań do oceny precyzji (potrzeba 20 z różnych kampanii); wynik orientacyjny.</Text>}
        </Tile>
      </Grid>
      {(cal.errors || []).length > 0 && (
        <Tile title="Przeoczenia i fałszywe alarmy">
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
