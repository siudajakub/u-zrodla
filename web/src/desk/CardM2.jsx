// Karta M2 (strona firmy z renderu): „Dowód” = trzy najważniejsze przesłanki ze zrzutami, reszta pod „+N przesłanek”,
// 19 kryteriów pod rozwinięciem; „Szczegóły” = firma, odczyt, widoki.
import React from "react";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Table, proportional } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { Shots, StateToken, Tile } from "./cardparts.jsx";
import { fmtDate, fmtDateTime } from "./labels.js";
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

/** Zdanie pomiaru po ludzku: widoki po polsku, liczby zaokrąglone, bez „y=”. Pole `summary` z API ma pierwszeństwo. */
export function plainEvidence(r) {
  const human = (r.measurements || []).map((m) => m.humanText).find(Boolean);
  return plainText(human || r.summary || r.evidence);
}

export function plainText(text) {
  return String(text || "")
    .replace(/\s*\(y=[^)]*\)/g, "").replace(/\s*\b(?:desktop|phone) \d+×\d+: kontrast[^.]*\./g, "")
    .replace(/\bdesktop\b/g, "komputer").replace(/\bphone\b/g, "telefon")
    .replace(/(\d+)\.(\d+) px/g, (_, a) => `${Number(a).toLocaleString("pl-PL").replace(/ /g, " ")} px`)
    .replace(/,?\s*y=[\d.]+( z [\d.]+)?( px)?/g, "")
    .replace(/\s*\(próg: [^)]*\)/g, "")
    .replace(/Takich twierdzeń: \d+\./, "")
    .replace(/FOG-PL [\d,]+/g, "indeks czytelności")
    .trim();
}

/** Trzy najważniejsze przesłanki: w kolejności punktów „Dlaczego tutaj” (reasons), pozostałe po nich. */
function rankPremises(c) {
  const premises = c.checks.filter((x) => x.state === "przesłanka");
  const pos = (r) => {
    const key = (r.quote || "").slice(0, 36);
    const i = c.reasons.findIndex((t) => (key && t.includes(key)) || t.toLowerCase().includes((r.label || "").toLowerCase().slice(0, 14)));
    return i < 0 ? 99 : i;
  };
  return [...premises].sort((a, b) => pos(a) - pos(b));
}

function PremiseRow({ r, title }) {
  const shots = shotsOf(r);
  const sentence = plainEvidence(r);
  const quoted = r.quote && sentence.includes(r.quote.slice(0, 40));
  return (
    <HStack gap={2} vAlign="start" hAlign="between" data-premise={r.id}>
      <VStack gap={0.5}>
        <Text weight="semibold">{r.label}</Text>
        {r.quote && !quoted && <Text type="supporting" maxLines={2}>„{r.quote}”</Text>}
        <Text type="supporting" color={quoted ? "primary" : "secondary"} maxLines={3}>{sentence}</Text>
      </VStack>
      {shots.length > 0 && <Shots shots={shots} title={title} />}
    </HStack>
  );
}

/** Dowód M2: 3 przesłanki, pod „+N przesłanek” pozostałe, pod „Wszystkie 19 kryteriów” pełna lista wg stanu. */
export function ProofM2({ c }) {
  const checks = c.checks;
  const ranked = rankPremises(c);
  const lead = ranked.slice(0, 3);
  const rest = ranked.slice(3);
  const groups = [...STATE_ORDER, ...new Set(checks.map((x) => x.state).filter((s) => !STATE_ORDER.includes(s)))]
    .map((state) => ({ state, rows: checks.filter((x) => x.state === state) }))
    .filter((g) => g.rows.length);
  return (
    <Tile title="Dlaczego tutaj i dowód" id="sekcja-momenty">
      {lead.length === 0 ? <Text color="secondary">Żadne z kryteriów nie jest przesłanką.</Text> : (
        <VStack gap={2}>{lead.map((r) => <PremiseRow key={r.id} r={r} title={c.title} />)}</VStack>
      )}
      {rest.length > 0 && (
        <Collapsible defaultIsOpen={false} trigger={<Text type="supporting" weight="medium">+ {rest.length} {rest.length === 1 ? "przesłanka" : rest.length < 5 ? "przesłanki" : "przesłanek"}</Text>}>
          <VStack gap={2} padding={1}>{rest.map((r) => <PremiseRow key={r.id} r={r} title={c.title} />)}</VStack>
        </Collapsible>
      )}
      {checks.length > 0 && (
        <Collapsible defaultIsOpen={false} trigger={<Text type="supporting" weight="medium">Wszystkie {checks.length} kryteriów wg stanu</Text>}>
          <VStack gap={2} padding={1}>
            {groups.map((g) => (
              <VStack key={g.state} gap={1} role="group" aria-label={`Kryteria: ${g.state}`}>
                <HStack gap={1} vAlign="center"><StateToken state={g.state} /><Text type="supporting" color="secondary">{g.rows.length}</Text></HStack>
                <Table idKey="id" density="compact" verticalAlign="top" data={g.rows} columns={[
                  { key: "n", header: "Kryterium", width: proportional(2, { minWidth: 110 }), renderCell: (r) => <Text weight="medium">{r.label}</Text> },
                  { key: "e", header: "Wynik", width: proportional(4, { minWidth: 150 }), renderCell: (r) => <Text type="supporting" color="secondary" maxLines={3}>{plainEvidence(r) || "—"}</Text> },
                ]} />
              </VStack>
            ))}
          </VStack>
        </Collapsible>
      )}
    </Tile>
  );
}

const CONSENT_ACTION = { reject: "odrzucono", accept: "przyjęto", close: "zamknięto", none: "nie klikano" };
function consentText(consent) {
  if (!consent) return "brak danych";
  if (!consent.overlayBefore) return "nie było";
  const how = CONSENT_ACTION[consent.action] || consent.action || "kliknięto";
  return consent.overlayAfter ? `${how}, nadal widoczny na zrzucie` : `${how}, zniknął przed zrzutem`;
}
const VIEW = { desktop: "komputer", phone: "telefon", tablet: "tablet" };

/** Wiersze „Szczegółów” M2: firma i wpis KNF, strona, odczyt, baner cookies w widokach. */
export function m2Details(c) {
  const card = c.raw.m2Card;
  const market = c.raw.m2Market;
  const firm = card?.firm || market?.firm;
  const checked = market?.firm?.checkedAt;
  const views = Object.entries(market?.views || {}).map(([id, v]) => `${VIEW[id] || id}: baner cookies ${consentText(v.consent)}`);
  return [
    firm && ["Firma", `${firm.name}${firm.entityLabel ? ` · ${firm.entityLabel}` : ""}`],
    firm && ["Wykaz KNF", `${(firm.category || "—").replace(/^Firmy inwestycyjne - /, "")}${checked ? `, stan z ${fmtDate(checked)}` : ""}${firm.registryId != null ? `, nr ${firm.registryId}` : ""}`],
    market?.firm?.home && ["Strona firmy", <ExternalLink key="h" url={market.firm.home}>{market.firm.home.replace(/^https?:\/\//, "")}</ExternalLink>],
    c.url && ["Strona", <ExternalLink key="u" url={market?.finalUrl || c.url}>{(market?.finalUrl || c.url).replace(/^https?:\/\//, "")}</ExternalLink>],
    ["Odczytano", fmtDateTime(card?.observedAt || c.observedAt)],
    views.length > 0 && ["Widoki", views.join("; ")],
  ].filter(Boolean);
}

export const m2Subtitle = (c) => {
  const firm = c.raw.m2Card?.firm;
  const when = c.raw.m2Card?.observedAt || c.observedAt;
  return [firm?.name || c.creatorName, firm?.entityLabel, firm?.registryId != null ? "w wykazie KNF" : null, when ? `odczyt ${fmtDateTime(when)}` : null].filter(Boolean).join(" · ");
};
