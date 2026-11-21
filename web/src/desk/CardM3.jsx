// Karta M3 (oferta doradcza ze stron firmy): „Dowód” = cztery cechy rekomendacji po jednej linii; uprawnienia z wykazów KNF
// jako krok drogi dowodu; ostrzeżenie KNF i awaria rejestru jako banery; reszta w „Szczegółach”.
import React from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Text } from "@astryxdesign/core/Text";
import { StateToken, Tile } from "./cardparts.jsx";
import { ENTITY_ROW, IDENTITY_STATE, fmtDate, fmtDateTime, safeUrl } from "./labels.js";
import { ExternalLink } from "./parts.jsx";

export const pageName = (url) => {
  try {
    const u = new URL(url);
    return u.pathname === "/" ? "strona główna" : u.pathname.replace(/\/$/, "");
  } catch {
    return "podstrona";
  }
};

/** Jedna linia; komórki tabeli sklejone przez odczyt strony („usługiCo obejmuje”) dostają spację. */
const oneLine = (text) => String(text || "").replace(/([a-ząćęłńóśźż])([A-ZĄĆĘŁŃÓŚŹŻ])/g, "$1 $2").replace(/\s+/g, " ").trim();

/** Dowód M3: cztery cechy, każda w jednej linii: cecha, stan, cytat, odnośnik do podstrony. */
export function ProofM3({ c }) {
  const rows = c.checks;
  return (
    <Tile title="Dowód" id="sekcja-momenty">
      {rows.length === 0 ? <Text color="secondary">Brak oceny cech dla tej sprawy.</Text> : (
        <VStack gap={1.5}>
          {rows.map((r) => (
            <VStack key={r.id} gap={0.25} data-axis={r.id}>
              <HStack gap={1} vAlign="center" wrap="wrap"><Text weight="semibold">{r.label}</Text><StateToken state={r.state} />{safeUrl(r.url) && <ExternalLink url={r.url}>{pageName(r.url)} ↗</ExternalLink>}</HStack>
              {r.evidence ? <Text type="supporting" maxLines={1}>„{oneLine(r.evidence)}”</Text> : <Text type="supporting" color="secondary">brak cytatu</Text>}
            </VStack>
          ))}
        </VStack>
      )}
    </Tile>
  );
}

/** Banery krytyczne M3: ostrzeżenie publiczne KNF i awaria rejestru. */
export function M3Banners({ c }) {
  const id = c.raw.identity;
  const warn = id?.knfWarning;
  const failures = id?.registerFailures || [];
  return (
    <>
      {warn?.state === "found" && (
        <Banner status="error" title="Ostrzeżenie publiczne KNF" description="Nazwa, domena lub numer podmiotu występuje na liście ostrzeżeń publicznych KNF. To sygnał osobny; wymaga potwierdzenia tożsamości."
          endContent={<VStack gap={0.5}>{(warn.entries || []).filter((e) => safeUrl(e.url)).slice(0, 2).map((e) => <ExternalLink key={e.id} url={e.url}>Wpis KNF ↗</ExternalLink>)}</VStack>} />
      )}
      {failures.length > 0 && <Banner status="warning" title="Awaria rejestru" description={`Nie wczytano: ${failures.map((f) => f.name || f.file || f).join(", ")}. Wynik uprawnień jest niepełny.`} />}
    </>
  );
}

/** Nazwy podmiotu ze strony: `identity.operator.names`. */
export const operatorNames = (c) => (c.raw.identity?.operator?.names || []).filter(Boolean);

/** Wiersze „Szczegółów” M3: podmiot na stronie, wykazy, trafienia, podstrony, kontrargumenty. */
export function m3Details(c) {
  const id = c.raw.identity || {};
  const op = id.operator || {};
  const entity = Object.entries(ENTITY_ROW).flatMap(([k, label]) => (op[k] || []).slice(0, 2).map((v) => `${label}: ${v}`));
  const [, short] = IDENTITY_STATE[id.state] || ["gray", id.label || id.state || "nieustalone"];
  const regs = id.reviewedRegisters || [];
  const pages = c.raw.offer?.pages || [];
  const counters = c.checks.flatMap((x) => (Array.isArray(x.counter) ? x.counter.map((t) => `${x.label}: ${t}`) : []));
  return [
    ["Uprawnienia", `${short}${id.label && id.label !== short ? ` · ${id.label}` : ""}`],
    ["Dane podmiotu na stronie", entity.length ? entity.join("; ") : "brak nazwy, NIP i KRS"],
    (id.matches || []).length > 0 && ["Wpisy w wykazach", (id.matches || []).map((m) => `${m.name}${m.principal ? ` (w imieniu: ${m.principal})` : ""} · ${m.register}`).join("; ")],
    ["Przejrzane wykazy", `${regs.length}${id.checkedAt ? `, stan z ${fmtDate(id.checkedAt)}` : ""}: ${regs.join(", ")}. Brak wpisu nie dowodzi braku uprawnień.`],
    pages.length > 0 && ["Podstrony", <VStack key="p" gap={0.5}>{pages.map((p) => <HStack key={p.url} gap={1}><ExternalLink url={p.url}>{pageName(p.url)} ↗</ExternalLink><Text type="supporting" color="secondary">{fmtDateTime(p.observedAt)}</Text></HStack>)}</VStack>],
    counters.length > 0 && ["Kontrargumenty", <VStack key="c" gap={0.5}>{counters.slice(0, 6).map((t, i) => <Text key={i} type="supporting">{t}</Text>)}</VStack>],
  ].filter(Boolean);
}

export const m3Subtitle = (c) => {
  const id = c.raw.identity || {};
  const [, short] = IDENTITY_STATE[id.state] || ["gray", id.label || id.state || ""];
  return [c.raw.offer?.domain, operatorNames(c)[0], id.licensed && id.badge ? id.badge : short].filter(Boolean).join(" · ");
};
