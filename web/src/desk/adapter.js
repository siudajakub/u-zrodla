// TYMCZASOWY ADAPTER DO USUNIĘCIA po wdrożeniu GET /v1/queues/{name} (kroki S6/S7 kontraktu v2).
// Buduje te same kolejki z GET /v1/state według reguł z docs/lanes/2026-11-21-fable-h-kontrakt.md §3.4.
// Gdy rekord niesie własne `queues[]` z API, adapter ich używa i niczego nie wylicza.
// Usunięcie: skasuj ten plik oraz użycie `buildFromState` w api.js (jedna funkcja `queueFromState`).

export const QUEUE_NAMES = ["review", "adRegister", "offersM2", "offersM3", "incomplete", "closed", "all", "demo"];
export const THRESHOLD = 60;

const real = (c) => c.origin === "live" || c.origin === "replay";
const inScope = (c) => !c.outOfScope && c.availability !== "removed";
const hasEvidence = (c) => c.evidence.some((e) => e.available);

function eligible(c, threshold) {
  if (c.queueEligible !== null) return c.queueEligible;
  return c.route === "refer" && c.score?.value != null && c.score.value >= threshold;
}

export function membership(c, threshold = THRESHOLD) {
  if (c.queues) return c.queues;
  const names = ["all"];
  if (c.origin === "synthetic" || c.origin === "upload") {
    names.push("demo");
    return names;
  }
  if (!real(c) || !inScope(c)) return names;
  if (c.module === "M1" && c.route === "refer" && eligible(c, threshold) && !c.needsRecalc && hasEvidence(c) && (c.status !== "closed" || c.pendingReReview || c.reviewStale)) names.push("review");
  if (c.registry === "included" || c.registry === "candidate") names.push("adRegister");
  if (c.module === "M2") names.push("offersM2");
  if (c.module === "M3") names.push("offersM3");
  if (c.route === "complete" || c.route === "insufficient" || c.needsRecalc || c.coverage?.blocksConclusion) names.push("incomplete");
  if (c.status === "closed") names.push("closed");
  return names;
}

const time = (v) => (v ? Date.parse(v) || 0 : 0);
const observed = (c) => c.checkCounts?.obserwacja ?? 0;
const SORT = {
  review: (a, b) => (b.score?.value ?? -1) - (a.score?.value ?? -1) || time(b.publishedAt) - time(a.publishedAt),
  adRegister: (a, b) => time(b.publishedAt) - time(a.publishedAt),
  offersM2: (a, b) => observed(b) - observed(a) || (b.legacyScore ?? 0) - (a.legacyScore ?? 0),
  offersM3: (a, b) => (b.legacyScore ?? 0) - (a.legacyScore ?? 0),
  incomplete: (a, b) => Number(b.needsRecalc) - Number(a.needsRecalc) || time(b.observedAt) - time(a.observedAt),
  closed: (a, b) => time(b.lastDecision?.at) - time(a.lastDecision?.at),
  all: (a, b) => time(b.observedAt) - time(a.observedAt),
  demo: (a, b) => time(b.observedAt) - time(a.observedAt),
};

export function queueFromState(name, cases, threshold = THRESHOLD) {
  const items = cases.filter((c) => membership(c, threshold).includes(name)).sort(SORT[name] || SORT.all);
  return items;
}

export function countsFromState(cases, threshold = THRESHOLD) {
  const counts = Object.fromEntries(QUEUE_NAMES.map((n) => [n, 0]));
  for (const c of cases) for (const n of membership(c, threshold)) if (n in counts) counts[n] += 1;
  return counts;
}
