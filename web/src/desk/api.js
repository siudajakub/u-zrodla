// Jedyny moduł klienta API pulpitu. Wszystkie widoki czytają i zapisują przez niego.
// Kolejki: GET /v1/queues/{name}; gdy trasa nie istnieje (404), tymczasowy adapter (adapter.js) buduje je ze stanu.
import { normalizeCase, normalizeState } from "./model.js";
import { QUEUE_NAMES, countsFromState, queueFromState } from "./adapter.js";

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

const base = () => (globalThis.INVESTWATCH_API_BASE || "");
const enc = (id) => String(id).split("/").map(encodeURIComponent).join("/");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(base() + path, { headers: { Accept: "application/json", ...(options.headers || {}) }, ...options });
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

let queueRoute = null; // "api" | "adapter" | null (jeszcze nie sprawdzono)

export const api = {
  /** Tryb źródła kolejek, do pokazania w stopce i w testach. */
  get queueRoute() {
    return queueRoute;
  },

  async state() {
    const raw = await request("/v1/state");
    return normalizeState(raw);
  },

  /** Liczniki zakładek: z /v1/state (`queues`), a gdy ich brak, liczy adapter. */
  counts(state) {
    if (state?.queues && typeof state.queues === "object") return { ...Object.fromEntries(QUEUE_NAMES.map((n) => [n, 0])), ...state.queues };
    return countsFromState(state?.cases || [], state?.threshold?.value);
  },

  /** Kolejka jako lista znormalizowanych spraw. Zwraca także źródło danych. */
  async queue(name, state) {
    if (queueRoute !== "adapter") {
      try {
        const body = await request(`/v1/queues/${encodeURIComponent(name)}?limit=500`);
        queueRoute = "api";
        const ids = new Map((state?.cases || []).map((c) => [c.id, c]));
        const items = (body.items || []).map((i) => ids.get(i.id) || null).filter(Boolean);
        // Podsumowanie z API bez pełnego rekordu w stanie: dociągnij sprawę.
        const missing = (body.items || []).filter((i) => !ids.has(i.id));
        const fetched = await Promise.all(missing.map((i) => api.case(i.id, state).catch(() => null)));
        return { items: [...items, ...fetched.filter(Boolean)], total: body.total ?? (body.items || []).length, route: "api", asOf: body.asOf || null, lastScan: body.lastScan || null };
      } catch (e) {
        if (e.status !== 404) throw e;
        queueRoute = "adapter";
      }
    }
    return { items: queueFromState(name, state?.cases || [], state?.threshold?.value), total: null, route: "adapter", asOf: state?.asOf || null, lastScan: null };
  },

  async case(id, state) {
    const raw = await request(`/v1/cases/${enc(id)}`);
    return normalizeCase(raw, state?.creatorMap);
  },

  versions: (id) => request(`/v1/cases/${enc(id)}/versions`),
  version: (id, n) => request(`/v1/cases/${enc(id)}/versions/${n}`),

  /** Zapis decyzji z kontrolą rewizji. 409 → ApiError z `current` w body. */
  decide(c, { status, note }) {
    return request(`/v1/cases/${enc(c.id)}`, json("PATCH", { status, note, expectedRevision: c.revision, reviewedVersion: c.version }));
  },

  startScan(mode) {
    return request("/v1/scans", json("POST", { mode, requestId: globalThis.crypto?.randomUUID?.() || String(Date.now()) }));
  },
  scan: (id) => request(`/v1/scans/${encodeURIComponent(id)}`),
  async thresholdHistory() {
    try {
      return (await request("/v1/threshold/history")).items || [];
    } catch (e) {
      if (e.status === 404) return null; // trasa jeszcze nie istnieje (S7)
      throw e;
    }
  },
  calibration: (threshold) => request(`/v1/calibration?threshold=${encodeURIComponent(threshold)}`),

  uploadEvidence(file, title, description) {
    const params = new URLSearchParams({ title: title || file.name, description: description || "", filename: file.name });
    return request(`/v1/media?${params}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
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
