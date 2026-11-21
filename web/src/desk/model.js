// Jeden kształt sprawy dla widoków. Czyta pola kontraktu v2 (reviewDecision, reviewScore, adRelationship,
// adRegistry, coverage, evidence z rolą) i nazwy przejściowe z cienia kwalifikacji (evidenceV2, coverageV2).
// Rekord w kształcie v1 (bez reviewDecision) trafia do stanu „do ponownego przeliczenia”.
import { bandOfValue, timeLink } from "./labels.js";

const arr = (v) => (Array.isArray(v) ? v : []);
const num = (v) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? null : Number(v));
const obj = (v) => (v && typeof v === "object" && !Array.isArray(v) ? v : null);

const MODALITY_OF_KIND = { description: "description", title: "title", audio: "transcript", transcript: "transcript", subtitle: "transcript", frame: "frame", screenshot: "page", page: "page", registry: "registry" };

export function normalizeEvidence(e, caseUrl) {
  const url = e.url || caseUrl || null;
  const start = num(e.start ?? e.t);
  return {
    id: e.id ?? null,
    role: e.role ?? null,
    kind: e.kind || "description",
    modality: e.modality || MODALITY_OF_KIND[e.kind] || "description",
    text: e.text ?? "",
    url,
    start,
    end: num(e.end),
    link: e.sourceUrlAtTime || timeLink(url, start),
    locator: obj(e.locator),
    available: e.available !== false && !!url,
    unavailableReason: e.unavailableReason || (url ? null : "brak odsyłacza do źródła"),
    thumbnailUrl: e.thumbnailUrl || e.thumbnail || null,
    caveat: e.caveat || null,
    effect: e.effect || null,
    counterKind: e.counterKind || null,
    method: e.method || null,
    observedAt: e.observedAt || null,
    sourceVersion: e.sourceVersion ?? null,
    observation: e.observation || null,
  };
}

export function normalizeReach(r, platform) {
  if (!r) return null;
  if (r.metrics) {
    const key = ["viewCount", "euTotalReach", "subscriberCount"].find((k) => r.metrics[k] && num(r.metrics[k].value) != null) || ["viewCount", "euTotalReach", "subscriberCount"].find((k) => r.metrics[k]) || Object.keys(r.metrics)[0];
    const m = r.metrics[key];
    if (!m) return null;
    const metric = key === "euTotalReach" ? "eu_reach" : key === "subscriberCount" ? "subscribers" : platform === "tiktok" ? "plays" : "views";
    return { metric, value: num(m.value), hidden: m.state === "hidden", observedAt: m.observedAt || r.asOf || null, source: m.source || r.source || null };
  }
  return { metric: r.metric || "views", value: num(r.value), hidden: !!r.hidden, observedAt: r.observedAt || null, source: r.source || null };
}

export function normalizeDiscovery(list, legacy) {
  const entries = arr(list).map((d) => ({ ...d, at: d.at || d.observedAt || null }));
  if (entries.length) return entries;
  const o = obj(legacy);
  if (o && (o.query || o.sourceUrl || o.observedAt)) return [{ method: o.method || "apple_search", query: o.query, position: o.rank ?? o.position, at: o.observedAt, sourceUrl: o.sourceUrl }];
  return [];
}

export function originOf(raw) {
  if (raw.origin) return raw.origin;
  if (raw.synthetic || raw.contractDemo) return "synthetic";
  if (raw.mode === "upload" || String(raw.id || "").startsWith("upload-")) return "upload";
  return raw.mode === "replay" ? "replay" : "live";
}

function normalizeCoverage(raw) {
  const c = obj(raw.coverage) && (raw.coverage.modalities || raw.coverage.state) ? raw.coverage : obj(raw.coverageV2);
  if (c) {
    return {
      state: c.state || null,
      label: c.label || null,
      blocksConclusion: !!c.blocksConclusion,
      modalities: obj(c.modalities) || {},
      gaps: arr(c.gaps),
    };
  }
  if (typeof raw.coverage === "string" && raw.coverage) return { legacyText: raw.coverage, state: null, modalities: {}, gaps: [], blocksConclusion: false };
  return null;
}

export function normalizeCase(raw, creators = new Map()) {
  const decision = obj(raw.reviewDecision);
  const score = obj(raw.reviewScore);
  const rel = obj(raw.adRelationship);
  const registry = obj(raw.adRegistry);
  const v2 = arr(raw.evidenceV2).length ? raw.evidenceV2 : arr(raw.evidence).filter((e) => e && e.role);
  const legacyEvidence = arr(raw.evidence).filter((e) => e && !e.role);
  const evidence = (v2.length ? v2 : legacyEvidence).map((e) => normalizeEvidence(e, raw.url));
  const creator = creators.get(raw.creatorId) || null;
  const module = raw.module || "M1";
  const route = decision?.route || null;
  const isV2 = !!decision;
  // M2 i M3 nie mają trasy kwalifikacji M1; ich przeliczenie wskazuje wyłącznie API (needsRecalc).
  const needsRecalc = raw.needsRecalc ?? (module === "M1" ? !isV2 : false);
  const sc = score
    ? { value: num(score.value), band: score.band || null, state: score.state || (score.value == null ? "withheld" : "computed"), meaning: score.meaning || null, notComputableReason: score.notComputableReason || null, components: arr(score.components), rules: score.rulesVersion || null }
    : null;
  const disclosure = obj(rel?.disclosure);
  const firm = obj(rel?.firm);
  const candidates = arr(firm?.candidates);
  const status = raw.status || "new";
  const out = {
    raw,
    id: raw.id,
    title: raw.title || raw.id,
    url: raw.url || null,
    platform: raw.platform || "",
    module,
    origin: originOf(raw),
    status,
    revision: raw.revision ?? 1,
    version: raw.version ?? 1,
    creatorId: raw.creatorId || null,
    creator,
    creatorName: raw.creatorName || creator?.name || raw.author || raw.brand || raw.publisher || "",
    publishedAt: raw.publishedAt || null,
    publishedAtDerived: obj(raw.publishedAtDerived),
    observedAt: raw.observedAt || null,
    isV2,
    route,
    reason: decision?.reason || null,
    reasons: arr(decision?.reasons),
    moments: arr(decision?.moments),
    completeReason: decision?.completeReason || null,
    requirement: obj(decision?.requirement),
    claim: obj(decision?.claim),
    alternative: decision?.alternative ?? null,
    missing: arr(decision?.missing),
    decidedBy: decision?.decidedBy || null,
    ruleVersion: decision?.version || sc?.rules || raw.rulesVersion || null,
    queueEligible: decision && "queueEligible" in decision ? !!decision.queueEligible : null,
    score: sc,
    legacyScore: num(raw.score),
    relationship: rel && {
      status: rel.status || "unknown",
      basis: rel.basis || null,
      firmName: firm?.mention || candidates[0]?.name || null,
      firm: firm && { ...firm, candidates },
      disclosure: disclosure && { state: disclosure.state || "not_checked", where: disclosure.where || null, text: disclosure.text || null, summary: disclosure.summary || null, kind: disclosure.kind || null, evidenceId: disclosure.evidenceId || null, checked: arr(disclosure.checked), notChecked: arr(disclosure.notChecked) },
    },
    registry: registry?.state || null,
    registryCampaign: registry?.campaignKey || null,
    registrySummary: registry?.summary || null,
    registryKind: registry?.disclosureKind || null,
    speechBasis: decision?.speechBasis || null,
    gatedFrom: decision?.gatedFrom || null,
    activeVariant: raw.activeVariant || null,
    provenance: obj(raw.provenance),
    durationSec: num(raw.youtube?.durationSec),
    paidPromotionFlag: raw.youtube?.paidPromotionFlag ?? null,
    premises: arr(raw.premises),
    evidence,
    counter: arr(raw.counterEvidence).map((e) => normalizeEvidence(e, raw.url)),
    coverage: normalizeCoverage(raw),
    frames: arr(raw.frames),
    needsRecalc: !!needsRecalc,
    needsRecalcReason: raw.needsRecalcReason || null,
    pendingReReview: !!raw.pendingReReview,
    reviewStale: !!raw.reviewStale,
    lastDecision: obj(raw.lastDecision) || deriveLastDecision(raw),
    history: arr(raw.history).map((h) => ({ ...h, details: parseDetails(h.details) })),
    versions: arr(raw.versions),
    discovery: normalizeDiscovery(raw.discovery),
    reach: normalizeReach(raw.reach, raw.platform),
    firstScanId: raw.firstScanId || null,
    lastScanId: raw.lastScanId || null,
    summary: raw.summary || null,
    checks: arr(raw.checks),
    checkCounts: obj(raw.checkCounts),
    semantic: obj(raw.semantic),
    analysisVersion: obj(raw.analysisVersion),
    outOfScope: raw.outOfScope || null,
    availability: obj(raw.availability)?.state || null,
    queues: Array.isArray(raw.queues) ? raw.queues : null,
  };
  return out;
}

function parseDetails(d) {
  if (d && typeof d === "object") return d;
  try {
    return typeof d === "string" && d ? JSON.parse(d) : {};
  } catch {
    return {};
  }
}

function deriveLastDecision(raw) {
  const last = arr(raw.history).filter((h) => h.action === "decision").pop();
  return last ? { status: last.details?.status || raw.status, at: last.at, note: last.note, version: last.details?.version ?? null, revision: raw.revision } : null;
}

export function normalizeCreator(raw) {
  const list = Array.isArray(raw.discovery) ? raw.discovery : null;
  return {
    ...raw,
    discoveries: normalizeDiscovery(raw.discoveries || list, list ? null : raw.discovery),
    reach: normalizeReach(raw.reach, raw.platform),
    isNewInScan: raw.isNew === true,
  };
}

/** Stan z GET /v1/overview (to samo co /v1/state?findings=0): twórcy, źródła, skany, liczniki, próg, wariant i trend. Sprawy czytają kolejki. */
export function normalizeState(state) {
  const creators = new Map(arr(state?.creators).map((c) => [c.id, normalizeCreator(c)]));
  const { findings, ...rest } = state || {};
  return { ...rest, creatorMap: creators, counts: obj(state?.queues) || {}, creators: undefined };
}

/** Wiersz kolejki z podsumowania API (bez dowodów). Szczegół sprawy to osobny odczyt /v1/cases/{id}. */
export function normalizeRow(item, creators = new Map()) {
  const value = num(item.reviewScore);
  const creator = creators.get?.(item.creatorId) || null;
  return {
    isRow: true,
    id: item.id,
    title: item.title || item.id,
    module: item.module || "M1",
    platform: item.platform || "",
    creatorId: item.creatorId || null,
    creatorName: item.creatorName || creator?.name || "",
    publishedAt: item.publishedAt || null,
    observedAt: item.observedAt || null,
    origin: item.origin || "live",
    status: item.status || "new",
    revision: item.revision ?? 1,
    version: item.version ?? 1,
    route: item.route || null,
    score: value == null ? null : { value, band: item.band || bandOfValue(value), state: "computed" },
    band: item.band || null,
    queueEligible: item.queueEligible ?? null,
    registry: item.adRegistry || null,
    registryInfo: obj(item.adRegistryInfo),
    disclosure: obj(item.disclosure),
    firstReason: item.firstReason || null,
    completeReason: item.completeReason || null,
    transcriptState: item.transcriptState || null,
    reason: item.reason || null,
    firstMoment: obj(item.firstMoment),
    lastDecision: obj(item.lastDecision),
    needsRecalc: !!item.needsRecalc,
    pendingReReview: !!item.pendingReReview,
    reviewStale: !!item.reviewStale,
    url: item.url || null,
    queues: arr(item.queues),
  };
}

/** Tekst „powód” w wierszu: `firstReason` z API, potem skrót `reason`. */
export function rowReason(c) {
  if (c.firstReason) return c.firstReason;
  if (c.reasons?.length) return c.reasons[0];
  if (c.reason) return c.reason;
  if (c.needsRecalc) return c.needsRecalcReason;
  return "Powód nieopisany";
}

export function scanOf(state, id) {
  return arr(state?.scans).find((s) => s.id === id || s.scanId === id) || null;
}

export function lastScanOf(state) {
  return arr(state?.scans)[0] || null;
}

/** Skan, z którego pochodzą materiały: ostatni skan odkrywania (na żywo lub odtworzony), nie przeliczenie. */
export function dataScanOf(state) {
  return arr(state?.scans).find((s) => (s.mode === "live" || s.mode === "replay") && s.status !== "queued") || null;
}
