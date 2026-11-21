import React from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Link } from "@astryxdesign/core/Link";
import { Skeleton } from "@astryxdesign/core/Skeleton";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { BANDS, DISCLOSURE, ORIGINS, clock, moduleName, describeDiscovery, fmtDateTime, fmtDayRoman, fmtNumber, safeUrl } from "./labels.js";

export const SCALE_NOTE = "Siła przesłanki to punkty 0–100 z jawnych składników reguł. To nie jest prawdopodobieństwo naruszenia ani ocena prawna.";

export const originLabel = (origin, at) => (origin === "replay" ? (at ? `odtworzenie skanu z ${fmtDayRoman(at)}` : "odtworzenie skanu") : ORIGINS[origin] || origin);

export function OriginToken({ origin, at }) {
  if (!origin || origin === "live") return null;
  const synthetic = origin === "synthetic" || origin === "upload";
  return <Token size="sm" color={synthetic ? "orange" : "gray"} label={originLabel(origin, at)} />;
}

const MODULE_COLOR = { M1: "blue", M2: "purple", M3: "green" };
/** Plakietka modułu: Finfluencer, Reklama firmy, Doradztwo. */
export function ModuleToken({ module }) {
  return module ? <Token size="sm" color={MODULE_COLOR[module] || "gray"} label={moduleName(module)} /> : null;
}

export function ImportToken({ c }) {
  return c.importLabel ? <Token size="sm" color="teal" label={c.importLabel} description="Realne dane wczytane z zapisanej strony, nie demonstracja." /> : null;
}

export function RecalcToken({ c }) {
  return c.needsRecalc && (c.module || "M1") === "M1" ? <Token size="sm" color="yellow" label="Do ponownego przeliczenia" description={c.needsRecalcReason || undefined} /> : null;
}

export function ReReviewToken({ c }) {
  return c.pendingReReview || c.reviewStale ? <Token size="sm" color="blue" label="Nowa wersja po decyzji" /> : null;
}

export function ExternalLink({ url, children }) {
  const href = safeUrl(url);
  return href ? <Link href={href} target="_blank">{children}</Link> : null;
}

/** Siła sygnału z opisem skali: punkty, nie prawdopodobieństwo. */
export function Strength({ c }) {
  if (!c.score) {
    return c.legacyScore != null && !c.isV2
      ? <VStack gap={0.5}><Text weight="semibold">—</Text><Text type="supporting" color="secondary">starsze reguły: {c.legacyScore} pkt</Text></VStack>
      : <Text color="secondary">—</Text>;
  }
  if (c.score.value == null) {
    return <VStack gap={0.5}><Text weight="semibold">—</Text><Text type="supporting" color="secondary" maxLines={2}>{c.score.notComputableReason || "nie do wyliczenia"}</Text></VStack>;
  }
  return (
    <VStack gap={0.5}>
      <Text weight="semibold">{BANDS[c.score.band] || "bez pasma"}</Text>
      <Text type="supporting" color="secondary" hasTabularNumbers>{c.score.value} z 100 pkt</Text>
    </VStack>
  );
}

/** Pierwszy dowód do pokazania. Wiersz kolejki ma tylko `firstMoment`; pełna sprawa wskazuje moment w mowie (z czasem), potem twierdzenie. */
export function proofOf(c) {
  if (c.isRow) {
    const m = c.firstMoment;
    if (!m) return null;
    return { url: safeUrl(m.deepLink) || safeUrl(c.url), start: m.start ?? null, quote: null, field: m.locator || null };
  }
  const byId = (id) => c.evidence.find((e) => e.id === id);
  const isFrame = (m) => String(m.evidenceId || "").startsWith("frame-");
  const timed = c.moments.find((m) => m.start != null && !isFrame(m));
  const moment = timed || c.moments[0];
  const claim = (c.claim && byId(c.claim.evidenceId)) || (moment && byId(moment.evidenceId)) || c.evidence.find((e) => e.role === "claim" && e.available) || c.evidence.find((e) => e.available);
  const start = moment?.start ?? claim?.start ?? null;
  const url = safeUrl(moment?.deepLink) || safeUrl(claim?.link) || safeUrl(c.url);
  if (!claim && !moment) return null;
  return { url, start, quote: claim?.text || c.claim?.text || null, field: moment?.locator || claim?.locator || null };
}

export function ProofLink({ c }) {
  const proof = proofOf(c);
  if (!proof?.url) return <Text type="supporting" color="secondary">brak wskazanego fragmentu</Text>;
  const label = proof.start != null ? `od ${clock(proof.start)} ↗` : c.module && c.module !== "M1" ? "strona ↗" : "opis ↗";
  return <Link href={proof.url} target="_blank" hasUnderline>{label}</Link>;
}

export function locatorText(locator) {
  if (!locator) return null;
  return locator.field === "description" ? "w opisie" : locator.field === "title" ? "w tytule" : `w polu ${locator.field}`;
}

const CHECKED = { description: "opis", transcript: "mowa", frames: "kadry", platformFlags: "flaga płatnej promocji" };

/** Typ ujawnienia współpracy: opis / mowa m:ss / flaga płatnej promocji YouTube / kadr, albo brak oznaczenia w zbadanym zakresie. */
export function disclosureText(c) {
  const d = c.relationship?.disclosure;
  if (!d) return "Oznaczenie nieustalone";
  if (d.state === "in_speech" || d.state === "in_frame") {
    const ev = c.evidence.find((e) => e.id === d.evidenceId);
    return `${DISCLOSURE[d.state]}${ev?.start != null ? `, ${clock(ev.start)}` : ""}`;
  }
  if (d.state === "not_found_in_scope") {
    const checked = d.checked.length ? ` (zbadano: ${d.checked.map((m) => CHECKED[m] || m).join(", ")})` : "";
    return `nie znaleziono w zbadanym zakresie${checked}`;
  }
  return DISCLOSURE[d.state] || d.state;
}

export function DisclosureProof({ c }) {
  const d = c.relationship?.disclosure;
  if (!d) return null;
  const ev = c.evidence.find((e) => e.id === d.evidenceId);
  const sentence = c.registrySummary || d.summary;
  return (
    <VStack gap={0.5}>
      <Text weight="medium">{disclosureText(c)}</Text>
      {sentence ? <Text type="supporting" color="secondary" maxLines={3}>{sentence}</Text> : (d.text || ev?.text) && <Text type="supporting" color="secondary" maxLines={2}>„{d.text || ev.text}”</Text>}
      {ev?.start != null && ev.link && <ExternalLink url={ev.link}>Otwórz od {clock(ev.start)}</ExternalLink>}
    </VStack>
  );
}

export function reachText(reach) {
  if (!reach) return "Zasięg nieznany";
  if (reach.hidden) return `Statystyka ukryta przez autora${reach.observedAt ? ` (sprawdzono ${fmtDateTime(reach.observedAt)})` : ""}`;
  const n = fmtNumber(reach.value);
  if (n == null) return "Zasięg nieznany";
  const unit = reach.metric === "subscribers" ? "obserwujących kanał" : reach.metric === "plays" ? "odtworzeń" : reach.metric === "eu_reach" ? "osób w UE (zasięg reklamy)" : "wyświetleń";
  return `${n} ${unit}${reach.observedAt ? `, stan z ${fmtDateTime(reach.observedAt)}` : ""}${reach.source ? ` (${reach.source})` : ""}`;
}

export function discoveryLines(list) {
  return list.map(describeDiscovery);
}

export function Loading({ rows = 5, label = "Pobieranie danych…" }) {
  return (
    <VStack gap={3} padding={4}>
      <Text as="p" type="supporting" color="secondary" role="status">{label}</Text>
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} height={48} index={i} />)}
    </VStack>
  );
}

export function ErrorBlock({ message, retry, title = "Nie można pobrać danych" }) {
  return (
    <VStack padding={4}>
      <Banner status="error" title={title} description={`${message} Brak danych nie oznacza braku spraw.`}
        endContent={retry && <Button label="Spróbuj ponownie" onClick={retry} />} />
    </VStack>
  );
}

export function NoResults({ filterText, hint, clear }) {
  return (
    <EmptyState isCompact title="Brak materiałów dla wybranych filtrów"
      description={`${filterText ? `Filtry: ${filterText}. ` : ""}${hint || ""}`.trim()}
      actions={clear && <Button label="Wyczyść filtry" onClick={clear} />} />
  );
}

export function Meta({ children }) {
  return <HStack gap={2} wrap="wrap" vAlign="center">{children}</HStack>;
}

export function Lines({ lines }) {
  return (
    <VStack gap={0.5}>
      {lines.filter(Boolean).map((line, i) => <Text key={i} type="supporting" color="secondary" maxLines={i === lines.length - 1 ? 3 : 1}>{line}</Text>)}
    </VStack>
  );
}
