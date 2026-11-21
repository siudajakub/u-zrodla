// Karta M2 (strona firmy z renderu): kryteria ryzyka zwinięte do przesłanek, z pomiarem, cytatem i zrzutami; co zbadano; firma.
import React from "react";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { Shots, StateToken, Tile } from "./cardparts.jsx";
import { fmtDateTime, fmtDate, viewLabel } from "./labels.js";
import { ExternalLink } from "./parts.jsx";

const STATE_ORDER = ["przesłanka", "spełnione", "nie dotyczy", "brak danych"];

/** Zrzuty kryterium: po jednym na widok (komputer, potem telefon), z pomiarów kryterium. */
export function shotsOf(check) {
  const seen = new Map();
  for (const m of check.measurements || []) {
    if (m.screenshot && !seen.has(m.screenshot)) seen.set(m.screenshot, { url: m.screenshot, viewport: m.viewport || "" });
  }
  return [...seen.values()].sort((a, b) => Number(a.viewport.startsWith("phone")) - Number(b.viewport.startsWith("phone"))).slice(0, 2);
}

const CONSENT_ACTION = { reject: "odrzucono", accept: "przyjęto", close: "zamknięto", none: "nie klikano" };
function consentText(consent) {
  if (!consent) return "brak danych";
  if (!consent.overlayBefore) return "nie było";
  const how = CONSENT_ACTION[consent.action] || consent.action || "kliknięto";
  return consent.overlayAfter ? `${how}, nadal widoczny na zrzucie` : `${how}, zniknął przed zrzutem`;
}

function PremiseRow({ r, narrow }) {
  const shots = shotsOf(r);
  const text = (
    <VStack gap={0.5}>
      <Text weight="semibold">{r.label}</Text>
      {narrow && <Text type="supporting" color="secondary">kryterium {r.id}</Text>}
    </VStack>
  );
  const proof = (
    <VStack gap={0.5}>
      {r.evidence && <Text maxLines={narrow ? 6 : 4}>{r.evidence}</Text>}
      {r.quote && <Text type="supporting" color="secondary" maxLines={2}>„{r.quote}”</Text>}
    </VStack>
  );
  return { key: r.id, text, proof, shots };
}

function PremisesTable({ rows, narrow, title }) {
  const data = rows.map((r) => PremiseRow({ r, narrow }));
  if (narrow) {
    return (
      <VStack gap={2.5}>
        {data.map((d) => (
          <VStack key={d.key} gap={1}>
            {d.text}
            {d.proof}
            <Shots shots={d.shots} title={title} />
          </VStack>
        ))}
      </VStack>
    );
  }
  return (
    <Table idKey="key" density="compact" verticalAlign="top" data={data} columns={[
      { key: "name", header: "Kryterium", width: proportional(2, { minWidth: 120 }), renderCell: (d) => d.text },
      { key: "proof", header: "Pomiar i cytat", width: proportional(4, { minWidth: 180 }), renderCell: (d) => d.proof },
      { key: "shots", header: "Zrzut strony", width: pixel(190), renderCell: (d) => <Shots shots={d.shots} title={title} /> },
    ]} />
  );
}

/** Kryteria ryzyka: przesłanki na wierzchu, pełna lista 19 kryteriów wg stanu pod rozwinięciem. */
export function RisksTile({ c, narrow }) {
  const checks = c.checks;
  const premises = checks.filter((x) => x.state === "przesłanka");
  const card = c.raw.m2Card;
  const groups = [...STATE_ORDER, ...new Set(checks.map((x) => x.state).filter((s) => !STATE_ORDER.includes(s)))]
    .map((state) => ({ state, rows: checks.filter((x) => x.state === state) }))
    .filter((g) => g.rows.length);
  const headline = checks.length ? `${premises.length} z ${checks.length} wymaga uwagi` : "Brak kart kryteriów";
  return (
    <Tile title="Kryteria ryzyka" id="sekcja-momenty" aside={<Token size="sm" color={premises.length ? "orange" : "green"} label={headline} />}>
      {card?.score != null && (
        <Text type="supporting" color="secondary">Wynik reguł {card.score} z 100 pkt · próg skierowania {card.threshold}. To przesłanki do sprawdzenia, nie ocena prawna.</Text>
      )}
      {premises.length === 0 ? <Text color="secondary">Żadne z kryteriów nie jest przesłanką.</Text> : <PremisesTable rows={premises} narrow={narrow} title={c.title} />}
      {checks.length > 0 && (
        <Collapsible defaultIsOpen={false} trigger={<Text weight="medium">Wszystkie {checks.length} kryteriów wg stanu</Text>}>
          <VStack gap={2} padding={1}>
            {groups.map((g) => (
              <VStack key={g.state} gap={1} role="group" aria-label={`Kryteria: ${g.state}`}>
                <HStack gap={1} vAlign="center"><StateToken state={g.state} /><Text type="supporting" color="secondary">{g.rows.length}</Text></HStack>
                <Table idKey="id" density="compact" verticalAlign="top" data={g.rows} columns={[
                  { key: "n", header: "Kryterium", width: proportional(2, { minWidth: 110 }), renderCell: (r) => <Text weight="medium">{r.label}</Text> },
                  { key: "e", header: "Wynik", width: proportional(4, { minWidth: 150 }), renderCell: (r) => <Text type="supporting" color="secondary" maxLines={3}>{r.evidence || "—"}</Text> },
                ]} />
              </VStack>
            ))}
          </VStack>
        </Collapsible>
      )}
    </Tile>
  );
}

/** Co zbadano: widoki z rozmiarem i banerem cookies, data odczytu, zakres. */
export function M2ScopeTile({ c }) {
  const market = c.raw.m2Market;
  const card = c.raw.m2Card;
  const views = Object.entries(market?.views || {}).map(([id, v]) => ({
    id,
    name: viewLabel(`${id} ${v.width}×${v.height}`),
    blocks: Array.isArray(v.blocks) ? v.blocks.length : v.blocks,
    cookies: consentText(v.consent),
  }));
  const gaps = (c.coverage?.gaps || []).map((g) => g.reason).filter(Boolean);
  return (
    <Tile title="Co zbadano">
      {c.coverage?.label && <Text weight="medium">{c.coverage.label}</Text>}
      <MetadataList>
        <MetadataListItem label="Odczytano">{fmtDateTime(card?.observedAt || c.observedAt)}</MetadataListItem>
        <MetadataListItem label="Strona">{c.url ? <ExternalLink url={market?.finalUrl || c.url}>{(market?.finalUrl || c.url).replace(/^https?:\/\//, "")}</ExternalLink> : "—"}</MetadataListItem>
      </MetadataList>
      {views.length > 0 && (
        <Table idKey="id" density="compact" verticalAlign="top" data={views} columns={[
          { key: "n", header: "Widok", width: proportional(2, { minWidth: 110 }), renderCell: (v) => <Text weight="medium">{v.name}</Text> },
          { key: "b", header: "Elementy", align: "end", width: pixel(84), renderCell: (v) => v.blocks ?? "—" },
          { key: "c", header: "Baner cookies", width: proportional(3, { minWidth: 120 }), renderCell: (v) => <Text type="supporting">{v.cookies}</Text> },
        ]} />
      )}
      {gaps.length > 0 && <Text type="supporting">Luki: {gaps.join("; ")}.</Text>}
    </Tile>
  );
}

/** Firma z wykazu KNF: nazwa, typ podmiotu, wykaz i numer wpisu. */
export function M2FirmTile({ c }) {
  const firm = c.raw.m2Card?.firm || c.raw.m2Market?.firm;
  const checked = c.raw.m2Market?.firm?.checkedAt;
  if (!firm) return <Tile title="Firma"><Text color="secondary">Nie ustalono firmy.</Text></Tile>;
  return (
    <Tile title="Firma">
      <MetadataList>
        <MetadataListItem label="Firma"><Text weight="semibold">{firm.name}</Text></MetadataListItem>
        <MetadataListItem label="Typ podmiotu">{firm.entityLabel || "—"}</MetadataListItem>
        <MetadataListItem label="Wykaz KNF">{(firm.category || "—").replace(/^Firmy inwestycyjne - /, "")}{checked ? `, stan z ${fmtDate(checked)}` : ""}</MetadataListItem>
        {firm.registryId != null && <MetadataListItem label="Numer w wykazie">{firm.registryId}</MetadataListItem>}
        {c.raw.m2Market?.firm?.home && <MetadataListItem label="Strona firmy"><ExternalLink url={c.raw.m2Market.firm.home}>{c.raw.m2Market.firm.home.replace(/^https?:\/\//, "")}</ExternalLink></MetadataListItem>}
      </MetadataList>
    </Tile>
  );
}

export const m2Subtitle = (c) => {
  const firm = c.raw.m2Card?.firm;
  return [firm?.name || c.creatorName, firm?.entityLabel].filter(Boolean).join(" · ");
};
