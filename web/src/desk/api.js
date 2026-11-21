// Jedyny moduł klienta API pulpitu (schemat 2). Wszystkie widoki czytają i zapisują przez niego.
// Lista kolejki to GET /v1/queues/{name} z kursorem; brak trasy (404) pokazuje stan „starsze API”, bez udawania danych.
import { normalizeCase, normalizeRow, normalizeState } from "./model.js";

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

const base = () => (globalThis.INVESTWATCH_API_BASE || "");
const enc = (id) => String(id).split("/").map(encodeURIComponent).join("/");
const SCHEMA = { "X-InvestWatch-Schema": "2" };

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(base() + path, { ...options, headers: { Accept: "application/json", ...SCHEMA, ...(options.headers || {}) } });
  } catch {
    throw new ApiError(0, "Brak połączenia z serwerem.");
  }
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map((d) => d.msg).join("; ") : null;
    throw new ApiError(response.status, detail || `Serwer odpowiedział ${response.status}.`, body);
  }
  return body;
}

const json = (method, payload) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

/** Parametry zapytania kolejki z filtrów widoku (adres #). Platforma, moduł, pasmo, kanał (q) i data filtrują serwer. */
export function queueQuery(filters = {}, { limit = 50, cursor = null, queue = null, report = false } = {}) {
  const p = new URLSearchParams();
  if (!report) p.set("limit", String(limit));
  if (cursor) p.set("cursor", cursor);
  if (filters.q?.trim()) p.set("q", filters.q.trim());
  if (filters.module && filters.module !== "all") p.set("module", filters.module);
  if (filters.source && filters.source !== "all") {
    // API ma jedną platformę kanoniczną „web” (WWW i Studio to aliasy przy odczycie).
    p.set("platform", filters.source);
  }
  if (filters.band && filters.band !== "all") p.set("band", filters.band);
  if (filters.from || filters.to) p.set("dateField", filters.dateField === "publishedAt" ? "publishedAt" : "observedAt");
  if (filters.from) p.set("since", `${filters.from}T00:00:00+00:00`);
  if (filters.to) p.set("until", `${filters.to}T23:59:59+00:00`);
  if (filters.section && filters.section !== "all") p.set("section", filters.section);
  return p.toString();
}

/** Adres raportu CSV/JSON z aktualnymi filtrami: GET /v1/report?module=…&format=… */
export function reportUrl({ module, format = "csv", filters = {}, queue = null }) {
  const query = queueQuery(filters, { report: true, queue });
  const p = new URLSearchParams(query);
  p.delete("module");
  p.set("module", module);
  if (queue) p.set("queue", queue);
  p.set("format", format);
  return `${base()}/v1/report?${p.toString()}`;
}

/** Adres zasobu serwowanego przez API (np. zrzuty dowodów /evidence/…) z prefiksem bazy. */
export const assetUrl = (path) => (typeof path === "string" && path.startsWith("/") ? base() + path : path || null);

const caseCache = new Map();

export const api = {
  /** Odczyt stanu: GET /v1/overview (lekki, bez spraw; starsze API bez tej trasy: /v1/state?compact=1). Listy i karty idą przez kolejki i /v1/cases. */
  async state() {
    try {
      return normalizeState(await request("/v1/overview"));
    } catch (e) {
      if (e.status !== 404) throw e;
      return normalizeState(await request("/v1/state?compact=1"));
    }
  },

  /** Lekki odczyt do odświeżania w tle: liczniki, próg i ostatni skan z nagłówka najkrótszej kolejki. */
  async light() {
    const body = await request("/v1/queues/review?limit=1");
    return { counts: body.counts, threshold: body.threshold, lastScan: body.lastScan, asOf: body.asOf };
  },

  /** Jedna strona kolejki. Zwraca wiersze (podsumowania), łączną liczbę i kursor następnej strony. */
  async queue(name, filters, { cursor = null, limit = 50, creators } = {}) {
    try {
      const body = await request(`/v1/queues/${encodeURIComponent(name)}?${queueQuery(filters, { limit, cursor, queue: name })}`);
      return { items: (body.items || []).map((i) => normalizeRow(i, creators)), total: body.total ?? 0, nextCursor: body.nextCursor || null, counts: body.counts || null, threshold: body.threshold || null, lastScan: body.lastScan || null, asOf: body.asOf || null };
    } catch (e) {
      if (e.status === 404) throw new ApiError(404, "Ten serwer nie ma jeszcze kolejek (GET /v1/queues). Pulpit wymaga nowszego API.", e.body);
      throw e;
    }
  },

  async case(id, creators, { fresh = false } = {}) {
    if (!fresh && caseCache.has(id)) return caseCache.get(id);
    const promise = request(`/v1/cases/${enc(id)}`).then((raw) => normalizeCase(raw, creators));
    caseCache.set(id, promise);
    promise.catch(() => caseCache.delete(id));
    return promise;
  },
  clearCases() {
    caseCache.clear();
  },

  versions: (id) => request(`/v1/cases/${enc(id)}/versions`),

  /** Zapis decyzji: rodzaj (resolution), uzasadnienie, kontrola rewizji i wersji. 409 → ApiError z `current` w body. */
  decide(c, { resolution, note }) {
    return request(`/v1/cases/${enc(c.id)}`, json("PATCH", { resolution, note, expectedRevision: c.revision, reviewedVersion: c.version }));
  },

  startScan(mode) {
    return request("/v1/scans", json("POST", { mode, requestId: globalThis.crypto?.randomUUID?.() || String(Date.now()) }));
  },
  scan: (id) => request(`/v1/scans/${encodeURIComponent(id)}`),
  trend: (days = 30) => request(`/v1/trend?days=${days}`),

  threshold: () => request("/v1/threshold"),
  async thresholdHistory() {
    return (await request("/v1/threshold/history")).items || [];
  },
  setThreshold: ({ value, expectedId, note, variant }) => request("/v1/threshold", json("PUT", { value, expectedId, note: note || "", variant })),
  restoreThreshold: ({ id, expectedId, note }) => request("/v1/threshold/restore", json("POST", { id, expectedId, note: note || "" })),

  qualification: () => request("/v1/qualification"),
  async qualificationHistory() {
    return (await request("/v1/qualification/history")).items || [];
  },
  restoreQualification: ({ id, expectedId, note }) => request("/v1/qualification/restore", json("POST", { id, expectedId, note: note || "" })),

  /** Kalibracja progu. `module` (M1 domyślnie): serwer, który nie zna modułu, zwraca M1; widok porównuje pole `module` odpowiedzi. */
  calibration: (threshold, variant, module = "M1") => request(`/v1/calibration?threshold=${encodeURIComponent(threshold)}${variant ? `&variant=${encodeURIComponent(variant)}` : ""}${module && module !== "M1" ? `&module=${encodeURIComponent(module)}` : ""}`),

  uploadEvidence(file, title, description) {
    const params = new URLSearchParams({ title: title || file.name, description: description || "", filename: file.name });
    return request(`/v1/media?${params}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
  },

  /** Import ręczny strony Biblioteki Reklam Meta lub profilu Instagram: surowy plik, nazwa w zapytaniu. */
  importMeta(file) {
    return request(`/v1/import/meta?filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
  },

  /** WebSocket zdarzeń z ponownym łączeniem i dociąganiem od ostatniego ID. Zwraca funkcję zamykającą. */
  events({ onEvent, onStatus }) {
    let ws;
    let timer;
    let closed = false;
    let delay = 1000;
    let cursor = null;
    const connect = () => {
      if (closed) return;
      const origin = base() ? new URL(base(), location.href) : location;
      const scheme = origin.protocol === "https:" ? "wss" : "ws";
      const after = cursor != null ? `?after=${cursor}` : "";
      try {
        ws = new WebSocket(`${scheme}://${origin.host}/v1/events${after}`);
      } catch {
        onStatus?.(false);
        timer = setTimeout(connect, delay);
        return;
      }
      ws.onopen = () => {
        delay = 1000;
        onStatus?.(true, cursor != null);
      };
      ws.onmessage = (message) => {
        let item;
        try {
          item = JSON.parse(message.data);
        } catch {
          return;
        }
        if (item.kind === "ready") {
          if (cursor == null) cursor = item.id;
          return;
        }
        if (item.id != null) cursor = item.id;
        onEvent?.(item);
      };
      ws.onclose = () => {
        onStatus?.(false);
        if (!closed) {
          timer = setTimeout(connect, delay);
          delay = Math.min(delay * 2, 15000);
        }
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  },
};
