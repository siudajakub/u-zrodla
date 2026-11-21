// „Droga dowodu”: kroki weryfikacji sprawy w kolejności, każdy ze stanem. Czyta `proofPath[]` z API (id, label, state, detail, at, deepLink).
// Gdy API jeszcze nie podaje pola, kroki powstają z coverage, adRelationship i discovery wyłącznie jako mapowanie etykiet (bez własnej oceny).
// Stan: ok (zbadano, bez zarzutu), suspect (wspiera przesłankę), refuted (obala przesłankę), gap (nie zbadano), skipped (nie dotyczy).
import React from "react";
import { Card } from "@astryxdesign/core/Card";
import { Grid } from "@astryxdesign/core/Grid";
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Link } from "@astryxdesign/core/Link";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { Tooltip } from "@astryxdesign/core/Tooltip";
import { DISCOVERY_METHOD, ROUTES, clock, safeUrl, strengthLabel, timeLink } from "./labels.js";
import { shotsOf } from "./CardM2.jsx";

const SHORT = {
  discovery: "Odkrycie", description: "Opis", platformFlag: "Flaga YouTube", speech: "Mowa", frames: "Kadry", firm: "Firma", model: "Typ materiału",
  secondOpinion: "Model", decision: "Wynik", read: "Render", claim: "Twierdzenie", warning: "Ostrzeżenie", action: "Czynność", personalisation: "Personalizacja",
  identity: "Uprawnienia", instrument: "Instrument", market: "Rynek",
};

const step = (id, state, detail, extra = {}) => ({ id, label: SHORT[id] || id, state, detail, at: null, deepLink: null, ...extra });

const discoveryDetail = (c) => {
  const d = c.discovery[0];
  if (!d) return null;
  const how = DISCOVERY_METHOD[d.method] || d.reason || "droga odkrycia";
  return `${how}${d.query ? `: „${d.query}”` : ""}${d.position != null || d.rank != null ? `, pozycja ${d.position ?? d.rank}` : ""}`;
};

const plural = (n, one, few, many) => (n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

function firmStep(c) {
  const firm = c.relationship?.firm;
  const names = (firm?.candidates || []).length;
  const name = c.raw.firmShort || firm?.mention || firm?.candidates?.[0]?.name || c.raw.firmRelation?.label || c.raw.m2Card?.firm?.brand || c.raw.m2Card?.firm?.name;
  const extra = (c.raw.relationships?.length || 0) > 1 ? ` · +${c.raw.relationships.length - 1} ${plural(c.raw.relationships.length - 1, "firma", "firmy", "firm")}` : "";
  if (!name) return step("firm", "gap", "nie ustalono firmy");
  return step("firm", "ok", `${name}${names ? ` · ${names} ${plural(names, "wpis", "wpisy", "wpisów")} KNF` : c.raw.m2Card ? " · w wykazie KNF" : ""}${extra}`);
}

function decisionStep(c) {
  const route = c.route;
  const strength = c.score?.value > 0 ? ` · ${strengthLabel(c.score.band, c.score.value)}` : "";
  const reg = c.registry ? ` · rejestr: ${c.registry === "candidate" ? "do potwierdzenia" : "potwierdzona"}` : "";
  const label = route ? ROUTES[route] || route : "brak oceny reguł";
  return step("decision", route === "refer" ? "suspect" : route === "no_signal" ? "refuted" : route ? "ok" : "gap", `${label}${strength}${reg}`);
}

function modelSteps(c) {
  const out = [];
  const m = c.raw.model && typeof c.raw.model === "object" ? c.raw.model : null;
  if (m?.status === "ready" && m.label) out.push(step("model", "ok", `${m.label} (opis, nie zmienia decyzji)`));
  const so = c.raw.secondOpinion;
  if (so?.status === "ready") out.push(step("secondOpinion", so.needsReview ? "suspect" : "ok", so.needsReview ? "rozbieżność — do przeglądu" : `zgodny z regułami${so.quote ? `: „${so.quote}”` : ""}`));
  return out;
}

function m1Fallback(c) {
  const rel = c.relationship;
  const disc = rel?.disclosure;
  const mod = c.coverage?.modalities || {};
  const steps = [];
  const dd = discoveryDetail(c);
  steps.push(step("discovery", dd ? "ok" : "gap", dd || "nie ustalono"));
  const hasRel = ["declared", "documented", "probable"].includes(rel?.status);
  if (hasRel) {
    steps.push(disc?.state === "in_description"
      ? step("description", "refuted", `oznaczenie w opisie${disc.text ? `: „${disc.text}”` : ""}`)
      : step("description", "suspect", `${rel.basis || "relacja z firmą"}; bez oznaczenia`));
  } else steps.push(step("description", mod.description ? "ok" : "gap", mod.description ? "bez śladu relacji" : "nie zbadano"));
  const flag = mod.platformFlags;
  if (flag) {
    steps.push(flag.state === "observed" && flag.paidPromotion === true ? step("platformFlag", "refuted", "płatna promocja")
      : flag.state === "observed" ? step("platformFlag", "ok", "brak") : step("platformFlag", "gap", "nie sprawdzono"));
  } else if (c.platform === "youtube" || c.platform === "tiktok") steps.push(step("platformFlag", "gap", "nie sprawdzono"));
  const tr = mod.transcript;
  const ev = disc?.evidenceId ? c.evidence.find((e) => e.id === disc.evidenceId) : null;
  if (disc?.state === "in_speech") {
    steps.push(step("speech", "refuted", `oznaczenie ${clock(ev?.start ?? 0)}${disc.text ? `: „${disc.text}”` : ""}`, { at: ev?.start ?? null, deepLink: ev?.link || null }));
  } else if (tr?.state === "full") {
    const span = tr.windows?.length ? `${clock(tr.windows[0].start)}–${clock(tr.windows[tr.windows.length - 1].end)}` : "cała";
    steps.push(step("speech", hasRel ? "suspect" : "ok", `${span}, brak oznaczenia`));
  } else if (tr) steps.push(step("speech", "gap", tr.state === "pending" ? "czeka na transkrypcję" : c.platform === "tiktok" ? "niedostępna (TikTok)" : "niedostępna"));
  else if (c.platform === "youtube" || c.platform === "tiktok") steps.push(step("speech", "gap", c.platform === "tiktok" ? "niedostępna (TikTok)" : "nie zbadano"));
  const fr = mod.frames;
  const moments = fr?.moments || [];
  if (disc?.state === "in_frame") steps.push(step("frames", "refuted", "oznaczenie widoczne w kadrze", { at: ev?.start ?? null, deepLink: ev?.link || null }));
  else if (moments.length) steps.push(step("frames", "ok", `${moments.length} ${plural(moments.length, "kadr", "kadry", "kadrów")}, bez OCR`, { at: moments[0], deepLink: timeLink(c.url, moments[0]) }));
  else if (c.platform === "youtube" || c.platform === "tiktok") steps.push(step("frames", "gap", "nie pobrano"));
  steps.push(firmStep(c), ...modelSteps(c), decisionStep(c));
  return steps;
}

function adFallback(c) {
  const r = c.raw;
  return [
    step("read", r.adBody ? "ok" : "gap", r.adBody ? "tekst reklamy" : "brak tekstu"),
    { ...step("media", "gap", "obraz i wideo nie badane"), label: "Obraz i wideo" },
    { ...step("delivery", r.adDeliveryStartDate ? "ok" : "gap", r.adDeliveryStartDate ? "emisja z biblioteki reklam" : "brak dat emisji"), label: "Emisja" },
    firmStep(c),
    decisionStep(c),
  ];
}

function m2Fallback(c) {
  const checks = c.checks;
  const premises = checks.filter((x) => x.state === "przesłanka").length;
  const met = checks.filter((x) => x.state === "spełnione").length;
  const na = checks.filter((x) => x.state === "nie dotyczy").length;
  const views = Object.keys(c.raw.m2Market?.views || {});
  const shots = checks.reduce((n, x) => n + shotsOf(x).length, 0);
  return [
    step("read", views.length ? "ok" : "gap", views.length ? `${views.map((v) => (v === "phone" ? "telefon" : v === "desktop" ? "komputer" : v)).sort().join(" + ")}` : "nie zbadano"),
    { ...step("criteria", premises ? "suspect" : "ok", `${premises} ${plural(premises, "przesłanka", "przesłanki", "przesłanek")} · ${met} spełnionych · ${na} nie dotyczy`), label: "Kryteria" },
    { ...step("shots", shots ? "ok" : "gap", shots ? `${shots} ${plural(shots, "zrzut", "zrzuty", "zrzutów")}` : "brak zrzutów"), label: "Zrzuty" },
    firmStep(c),
    decisionStep(c),
  ];
}

function m3Fallback(c) {
  const id = c.raw.identity || {};
  const pages = c.raw.offer?.pages?.length || 0;
  const present = c.checks.filter((x) => x.state === "przesłanka").length;
  const names = id.operator?.names || [];
  const warn = id.knfWarning?.state === "found";
  return [
    { ...step("read", pages ? "ok" : "gap", pages ? `${pages} ${plural(pages, "podstrona", "podstrony", "podstron")}` : "nie zbadano"), label: "Tekst" },
    { ...step("axes", present ? "suspect" : "ok", `${present} z ${c.checks.length || 4} cech`), label: "Cechy" },
    { ...step("operator", names.length ? "ok" : "gap", names.length ? names.slice(0, 2).join(", ") : "brak nazwy, NIP i KRS"), label: "Podmiot na stronie" },
    { ...step("identity", id.licensed ? "refuted" : "suspect", `${id.licensed ? id.badge || "uprawniony" : "brak wpisu"} · ${(id.reviewedRegisters || []).length} wykazów`), label: "Wykazy KNF" },
    { ...step("warning", warn ? "suspect" : "ok", warn ? "jest wpis" : "brak wpisu"), label: "Ostrzeżenia KNF" },
    ...modelSteps(c),
    decisionStep(c),
  ];
}

const LONG = 64;

function fallbackSteps(c) {
  if (c.raw.adBody) return adFallback(c);
  if (c.module === "M2" && c.checks.length) return m2Fallback(c);
  if (c.module === "M3" && c.checks.length) return m3Fallback(c);
  return m1Fallback(c);
}

/** Kroki z API (`proofPath`); za długie zdania zastępuje krótsze z tego samego kroku, gdy da się je zbudować z karty. */
export function buildProofPath(c) {
  const api = Array.isArray(c.raw.proofPath) ? c.raw.proofPath.filter((s) => s && s.id) : [];
  const fallback = fallbackSteps(c);
  if (!api.length) return fallback;
  const byId = new Map(fallback.map((s) => [s.id, s]));
  return api.map((s) => {
    const own = byId.get(s.id);
    const detail = s.detail && (s.detail.length <= LONG || !own?.detail) ? s.detail : own.detail;
    return { ...s, label: s.id === "decision" ? "Wynik" : SHORT[s.id] || s.label, detail: s.id === "decision" && own ? own.detail : detail || "", deepLink: safeUrl(s.deepLink) };
  });
}

const MARK = { ok: "✓", suspect: "✓", refuted: "✓", gap: "○", skipped: "–" };
const STATE_NAME = { ok: "zbadano, bez zarzutu", suspect: "wspiera przesłankę", refuted: "obala przesłankę", gap: "nie zbadano", skipped: "nie dotyczy" };

function StepText({ s, lines }) {
  const text = s.detail || "—";
  return (
    <Tooltip content={text}>
      <Text type="supporting" color={s.state === "gap" ? "secondary" : "primary"} maxLines={lines}>{text}</Text>
    </Tooltip>
  );
}

function StepHead({ s }) {
  const head = (
    <HStack gap={0.5} vAlign="center" wrap="wrap">
      <Text type="supporting" color={s.state === "gap" ? "secondary" : "primary"} aria-hidden="true">{MARK[s.state] || "○"}</Text>
      <Text weight="semibold" color={s.state === "gap" ? "secondary" : "primary"}>{s.label}</Text>
      {s.at != null && <Text type="supporting" hasTabularNumbers>{clock(s.at)}</Text>}
    </HStack>
  );
  return (
    <HStack gap={1} vAlign="center" wrap="wrap">
      {s.deepLink ? <Link href={s.deepLink} target="_blank" tooltip="Otwórz film w tej sekundzie" label={`${s.label} ${s.at != null ? clock(s.at) : ""}: otwórz źródło`}>{head}</Link> : head}
      {s.state === "refuted" && <Token size="sm" color="green" label="obaliło" description="Ten krok przeczy przesłance z opisu" />}
    </HStack>
  );
}

/** Pasek kroków (1440): siatka z krokami, krok obalający wyróżniony zielonym tłem. Telefon: lista pionowa. */
export function EvidencePath({ c, narrow }) {
  const steps = buildProofPath(c);
  if (!steps.length) return null;
  if (narrow) {
    return (
      <VStack gap={1} role="list" aria-label="Droga dowodu" data-testid="proof-path">
        {steps.map((s) => {
          const head = <Text weight="semibold" color={s.state === "gap" ? "secondary" : "primary"}>{MARK[s.state] || "○"} {s.label}{s.at != null ? ` ${clock(s.at)}` : ""}</Text>;
          return (
            <Text key={s.id} type="supporting" role="listitem" data-step={s.id} data-state={s.state} aria-label={`${s.label}: ${STATE_NAME[s.state] || s.state}`}>
              {s.deepLink ? <Link href={s.deepLink} target="_blank" tooltip="Otwórz film w tej sekundzie">{head}</Link> : head}
              {s.state === "refuted" && <> <Token size="sm" color="green" label="obaliło" /></>}
              {s.detail ? <Text type="supporting" color="secondary"> {s.detail}</Text> : null}
            </Text>
          );
        })}
      </VStack>
    );
  }
  return (
    <Grid columns={{ minWidth: 168, max: 4 }} gap={1.5} role="list" aria-label="Droga dowodu" data-testid="proof-path">
      {steps.map((s) => (
        <Card key={s.id} padding={1.5} variant={s.state === "refuted" ? "green" : s.state === "suspect" ? "yellow" : s.state === "gap" ? "muted" : "default"} role="listitem" data-step={s.id} data-state={s.state} aria-label={`${s.label}: ${STATE_NAME[s.state] || s.state}`}>
          <VStack gap={0.5}>
            <StepHead s={s} />
            <StepText s={s} lines={2} />
          </VStack>
        </Card>
      ))}
    </Grid>
  );
}
