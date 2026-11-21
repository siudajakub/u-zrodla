// Karta M3 (oferta doradcza ze stron firmy): cztery cechy rekomendacji z cytatem i kontrargumentem, uprawnienia z wykazów KNF, braki.
import React from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Item } from "@astryxdesign/core/Item";
import { List } from "@astryxdesign/core/List";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { Table, pixel, proportional } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { StateToken, Tile } from "./cardparts.jsx";
import { ENTITY_ROW, IDENTITY_STATE, fmtDate, fmtDateTime, safeUrl } from "./labels.js";
import { ExternalLink } from "./parts.jsx";

const pageName = (url) => {
  try {
    const u = new URL(url);
    return u.pathname === "/" ? "strona główna" : u.pathname.replace(/\/$/, "");
  } catch {
    return "podstrona";
  }
};

/** Cztery cechy rekomendacji: czynność, personalizacja, instrument, rynek. */
export function AxesTile({ c, narrow }) {
  const rows = c.checks.map((x) => ({ ...x, counter: Array.isArray(x.counter) ? x.counter : [] }));
  const cite = (r) => (
    <VStack gap={0.5}>
      {r.evidence ? <Text maxLines={narrow ? 6 : 4}>„{r.evidence}”</Text> : <Text color="secondary">brak cytatu</Text>}
      {safeUrl(r.url) && <ExternalLink url={r.url}>{pageName(r.url)} ↗</ExternalLink>}
    </VStack>
  );
  const counter = (r) => (r.counter.length ? (
    <VStack gap={0.5}>
      <Text type="supporting" maxLines={3}>{r.counter[0]}</Text>
      {r.counter.length > 1 && <Text type="supporting" color="secondary">+ {r.counter.length - 1} {r.counter.length - 1 === 1 ? "kolejny" : "kolejne"}</Text>}
    </VStack>
  ) : <Text type="supporting" color="secondary">brak</Text>);
  return (
    <Tile title="Cztery cechy rekomendacji" id="sekcja-momenty">
      {rows.length === 0 ? <Text color="secondary">Brak oceny cech dla tej sprawy.</Text> : narrow ? (
        <VStack gap={2.5}>
          {rows.map((r) => (
            <VStack key={r.id} gap={1}>
              <HStack gap={1} vAlign="center"><Text weight="semibold">{r.label}</Text><StateToken state={r.state} /></HStack>
              {cite(r)}
              <VStack gap={0.5}><Text type="supporting" color="secondary">Kontrargument</Text>{counter(r)}</VStack>
            </VStack>
          ))}
        </VStack>
      ) : (
        <Table idKey="id" density="compact" verticalAlign="top" data={rows} columns={[
          { key: "label", header: "Cecha", width: proportional(2, { minWidth: 90 }), renderCell: (r) => <Text weight="semibold">{r.label}</Text> },
          { key: "state", header: "Stan", width: pixel(120), renderCell: (r) => <StateToken state={r.state} /> },
          { key: "cite", header: "Cytat ze strony", width: proportional(5, { minWidth: 200 }), renderCell: cite },
          { key: "counter", header: "Kontrargument", width: proportional(3, { minWidth: 140 }), renderCell: counter },
        ]} />
      )}
    </Tile>
  );
}

/** Uprawnienia: stan z wykazów KNF, przejrzane wykazy z datą, ostrzeżenie publiczne KNF. */
export function PermissionsTile({ c }) {
  const id = c.raw.identity;
  const [color, short] = IDENTITY_STATE[id.state] || ["gray", id.label || id.state || "nieustalone"];
  const regs = id.reviewedRegisters || [];
  const warn = id.knfWarning;
  const found = warn?.state === "found";
  const op = id.operator || {};
  const mentioned = Object.entries(ENTITY_ROW).flatMap(([k, label]) => (op[k] || []).slice(0, 2).map((v) => `${label}: ${v}`));
  const failures = id.registerFailures || [];
  return (
    <Tile title="Uprawnienia" aside={id.licensed && id.badge ? <Token size="sm" color="green" label={`kontrola: ${id.badge}`} /> : undefined}>
      <HStack gap={1.5} vAlign="center" wrap="wrap">
        <Token color={color} label={short} />
        {id.label && id.label !== short && <Text type="supporting" color="secondary">{id.label}</Text>}
      </HStack>
      {found && (
        <Banner status="error" title="Ostrzeżenie publiczne KNF" description="Nazwa, domena lub numer podmiotu występuje na liście ostrzeżeń publicznych KNF. To sygnał osobny; wymaga potwierdzenia tożsamości."
          endContent={<VStack gap={0.5}>{(warn.entries || []).filter((e) => safeUrl(e.url)).slice(0, 2).map((e) => <ExternalLink key={e.id} url={e.url}>Wpis KNF ↗</ExternalLink>)}</VStack>} />
      )}
      {failures.length > 0 && <Banner status="warning" title="Awaria rejestru" description={`Nie wczytano: ${failures.map((f) => f.name || f.file || f).join(", ")}. Wynik uprawnień jest niepełny.`} />}
      {id.matches?.length > 0 && (
        <Table idKey="id" density="compact" verticalAlign="top" data={id.matches} columns={[
          { key: "n", header: "Wpis w wykazie", width: proportional(3, { minWidth: 130 }), renderCell: (m) => <VStack gap={0.5}><Text weight="medium">{m.name}</Text>{m.principal && <Text type="supporting" color="secondary">w imieniu: {m.principal}</Text>}</VStack> },
          { key: "r", header: "Wykaz", width: proportional(3, { minWidth: 120 }), renderCell: (m) => <Text type="supporting">{m.register}</Text> },
        ]} />
      )}
      <MetadataList>
        <MetadataListItem label="Dane podmiotu na stronie">{mentioned.length ? mentioned.join("; ") : "brak nazwy, NIP i KRS"}</MetadataListItem>
        <MetadataListItem label="Ostrzeżenia KNF">
          <HStack gap={1} vAlign="center" wrap="wrap"><StatusDot variant={found ? "error" : "success"} label={found ? "jest wpis" : "brak wpisu"} /><Text>{found ? "jest wpis" : "brak wpisu"}{warn?.checkedAt ? ` (${fmtDate(warn.checkedAt)})` : ""}</Text></HStack>
        </MetadataListItem>
      </MetadataList>
      <Collapsible defaultIsOpen={false} trigger={<Text type="supporting">Przejrzane wykazy ({regs.length}{id.checkedAt ? `, stan z ${fmtDate(id.checkedAt)}` : ""})</Text>}>
        <List density="compact" hasDividers>
          {regs.map((name) => <Item key={name} label={name} endContent={<Text type="supporting" color="secondary">{fmtDate(id.checkedAt)}</Text>} />)}
        </List>
      </Collapsible>
      <Text type="supporting" color="secondary">Brak wpisu nie dowodzi braku uprawnień: sprawdzono tylko wymienione wykazy, w podanym dniu.</Text>
    </Tile>
  );
}

export function MissingTile({ c }) {
  if (!c.missing.length) return null;
  return (
    <Tile title="Czego brakuje">
      <VStack gap={1.5} role="list">
        {c.missing.map((m, i) => <HStack key={i} gap={1.5} vAlign="start" role="listitem"><Text color="secondary">•</Text><Text>{m}</Text></HStack>)}
      </VStack>
      <Text type="supporting" color="secondary">Brak tych danych na stronie nie jest wnioskiem.</Text>
    </Tile>
  );
}

/** Co zbadano: odczytane podstrony i luki (render i obrazy nie były badane). */
export function M3ScopeTile({ c }) {
  const pages = c.raw.offer?.pages || [];
  const gaps = (c.coverage?.gaps || []).map((g) => g.reason).filter(Boolean);
  return (
    <Tile title="Co zbadano">
      {c.coverage?.label && <Text weight="medium">{c.coverage.label}</Text>}
      {pages.length > 0 && (
        <Table idKey="url" density="compact" verticalAlign="top" data={pages} columns={[
          { key: "u", header: "Podstrona", width: proportional(3, { minWidth: 140 }), renderCell: (p) => <ExternalLink url={p.url}>{pageName(p.url)} ↗</ExternalLink> },
          { key: "t", header: "Odczytano", width: proportional(2, { minWidth: 120 }), renderCell: (p) => <Text type="supporting">{fmtDateTime(p.observedAt)}</Text> },
        ]} />
      )}
      {gaps.length > 0 && <Text type="supporting">Luki: {gaps.join("; ")}.</Text>}
    </Tile>
  );
}

export const m3Subtitle = (c) => [c.raw.offer?.domain, c.raw.identity?.licensed ? c.raw.identity.badge : null].filter(Boolean).join(" · ");
