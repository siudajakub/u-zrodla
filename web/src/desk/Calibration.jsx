import React, { useEffect, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { Heading, Text } from "@astryxdesign/core/Text";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Slider } from "@astryxdesign/core/Slider";
import { Table, proportional } from "@astryxdesign/core/Table";
import { Token } from "@astryxdesign/core/Token";
import { api } from "./api.js";
import { fmtDate, fmtDateTime } from "./labels.js";
import { ExternalLink, Loading } from "./parts.jsx";

const pct = (v) => (v == null || Number.isNaN(v) ? null : `${Math.round(v * 100)}%`);
function Meta({ label, children }) {
  return <MetadataListItem label={label}>{children}</MetadataListItem>;
}

export function Calibration({ data }) {
  const [threshold, setThreshold] = useState(data.threshold?.value ?? 60);
  const [state, setState] = useState({ status: "loading" });
  const [history, setHistory] = useState(undefined);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setState((s) => (s.cal ? { ...s, status: "refreshing" } : { status: "loading" }));
    const t = setTimeout(() => {
      api.calibration(threshold).then(
        (cal) => !cancelled && setState({ status: "ready", cal }),
        (e) => !cancelled && setState({ status: "error", error: e.message }),
      );
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [threshold, nonce]);
  useEffect(() => {
    api.thresholdHistory().then(setHistory, () => setHistory(null));
  }, []);
  const cal = state.cal;
  const retry = () => setNonce((n) => n + 1);
  if (state.status === "error") {
    return <VStack padding={4}><Banner status="error" title="Nie można pobrać wyników kalibracji" description={state.error} endContent={<Button label="Spróbuj ponownie" onClick={retry} />} /></VStack>;
  }
  if (!cal) return <Loading rows={4} label="Pobieranie wyników kalibracji…" />;
  const referred = cal.tp + cal.fp;
  const precision = referred ? cal.tp / referred : null;
  const recall = cal.tp + cal.fn ? cal.tp / (cal.tp + cal.fn) : null;
  const ci = cal.precisionCI;
  const noTarget = !cal.labelTarget;
  return (
    <VStack gap={5} padding={4}>
      <VStack gap={1}>
        <Heading level={1}>Kalibracja progu</Heading>
        <Text color="secondary">Sprawdza, jak próg punktów zgadza się z ręcznymi etykietami. Punkty to siła przesłanki do kontroli, nie prawdopodobieństwo.</Text>
      </VStack>
      <VStack gap={2}>
        <Heading level={2}>Zbiór etykiet</Heading>
        <MetadataList columns="multi">
          <Meta label="Cel etykiety">{cal.labelTarget || <Token size="sm" color="yellow" label="cel etykiet nieopisany" />}</Meta>
          <Meta label="Liczebność">{cal.n} przykładów ({cal.publicExamples ?? "?"} publicznych, {cal.syntheticExamples ?? "?"} syntetycznych)</Meta>
          <Meta label="Niezależne kampanie">{cal.groups != null ? cal.groups : "nieznane (grupy nie są opisane)"}</Meta>
          <Meta label="Podział">{cal.split === "holdout" ? "próba odłożona" : cal.split === "tuning" ? "zbiór strojenia" : "bez podziału"}{cal.frozenAt ? `, zamrożono ${fmtDate(cal.frozenAt)}` : ""}</Meta>
          <Meta label="Autor etykiet">{cal.labelers?.length ? cal.labelers.map((l) => `${l.role}${l.independent ? " (niezależny)" : " (niezależność niepotwierdzona)"}`).join("; ") : "nieznany"}</Meta>
          <Meta label="Zbiór">{cal.datasetId || "—"}</Meta>
        </MetadataList>
        {referred < 20 && <Banner status="warning" title={`Próba zbyt mała do oceny precyzji (n = ${cal.n}, ${cal.syntheticExamples ?? "?"} syntetycznych)`} description="Bramka produktowa wymaga co najmniej 20 skierowań z różnych kampanii w odłożonej próbie. Wynik jest tylko orientacyjny." />}
        {noTarget && <Banner status="info" title="Wyniki orientacyjne" description="Zbiór nie opisuje celu etykiet, więc nie wiadomo, czy jawna współpraca jest w nim liczona jako trafienie. Bieżąca definicja: „materiał zawiera udokumentowaną przesłankę wymagającą kontroli”." />}
      </VStack>
      <VStack gap={2}>
        <Heading level={2}>Próg</Heading>
        <Slider label={`Próg ${threshold} punktów`} value={threshold} valueDisplay="none" onChange={setThreshold} description="Przesuń, aby porównać wyniki na tym samym zbiorze." />
        <MetadataList columns="multi">
          <Meta label="Obowiązujący próg">{data.threshold ? `${data.threshold.value} pkt (wariant ${data.threshold.variant}, od ${fmtDateTime(data.threshold.setAt)})` : "60 pkt (domyślny)"}</Meta>
          <Meta label="Historia progu">{history === undefined ? "ładowanie…" : history === null ? "API historii progu jeszcze nie istnieje" : history.length ? history.map((h) => `${h.value} pkt od ${fmtDate(h.setAt)}`).join("; ") : "brak zmian"}</Meta>
        </MetadataList>
      </VStack>
      <VStack gap={2}>
        <Heading level={2}>Wynik przy progu {threshold}</Heading>
        <Table idKey="metric" density="compact" columns={[
          { key: "metric", header: "Wynik", width: proportional(3) },
          { key: "value", header: "Wartość", align: "end", width: proportional(2) },
        ]} data={[
          { metric: "Trafienia (TP)", value: cal.tp },
          { metric: "Fałszywe alarmy (FP)", value: cal.fp },
          { metric: "Poprawnie odrzucone (TN)", value: cal.tn },
          { metric: "Przeoczenia (FN)", value: cal.fn },
          { metric: "Precyzja", value: referred ? `${pct(precision)}${ci ? ` (95%: ${pct(ci.low)}–${pct(ci.high)}, ${ci.method})` : ", bez przedziału niepewności"}` : `brak podstaw do obliczenia${cal.notComputableReason ? `: ${cal.notComputableReason}` : " (brak skierowań)"}` },
          { metric: "Pełność", value: recall == null ? "brak podstaw do obliczenia" : pct(recall) },
          { metric: "Koszt (2 × FN + FP)", value: cal.cost },
          { metric: "Etykiety nieustalone", value: cal.unresolved ?? "brak danych" },
          { metric: "Wstrzymane (bez wniosku)", value: cal.withheld ?? "brak danych" },
        ]} />
      </VStack>
      {(cal.errors || []).length > 0 && (
        <VStack gap={2}>
          <Heading level={2}>Przeoczenia i fałszywe alarmy</Heading>
          {cal.errors.map((item) => (
            <Collapsible key={item.id} defaultIsOpen={false} trigger={<Text>{item.title || item.id} · {item.outcome === "fp" ? "fałszywy alarm" : "przeoczenie"} · {item.score} z 100</Text>}>
              <VStack gap={1} padding={2}>
                {item.text && <Text>{item.text}</Text>}
                <Text type="supporting" color="secondary">Oczekiwano: {item.expected ? "przesłanka do sprawdzenia" : "brak przesłanki"} · pochodzenie: {item.origin}</Text>
                <ExternalLink url={item.url}>Materiał źródłowy</ExternalLink>
              </VStack>
            </Collapsible>
          ))}
        </VStack>
      )}
    </VStack>
  );
}
