// Serwer deweloperski bez backendu: pliki z web/ oraz API zbudowane z web/sample/state.json.
// Uruchomienie:  node web/dev-server.mjs [--port 18790] [--queues]
// Domyślnie GET /v1/queues/{name} zwraca 404, więc pulpit używa tymczasowego adaptera (jak przy dzisiejszym API).
// Z flagą --queues serwer udaje docelową trasę i liczy kolejki tym samym kodem adaptera.
// Do prób ręcznych: GET /dev/alert?ref=<id sprawy> wysyła zdarzenie high_risk przez WebSocket do otwartych sesji.
import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { extname, join, normalize } from "node:path";
import { normalizeState } from "./src/desk/model.js";
import { QUEUE_NAMES, queueFromState } from "./src/desk/adapter.js";

const args = process.argv.slice(2);
const port = Number(args[args.indexOf("--port") + 1]) || 18790;
const withQueues = args.includes("--queues");
const root = fileURLToPath(new URL(".", import.meta.url));
const state = JSON.parse(await readFile(join(root, "sample/state.json"), "utf8"));
const calibrationExamples = state.calibration.examples || [];
let eventSeq = 1000;
const sockets = new Set();
const events = [];

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".jpg": "image/jpeg", ".png": "image/png", ".woff2": "font/woff2", ".txt": "text/plain" };
const send = (res, status, body, type = "application/json") => {
  res.writeHead(status, { "Content-Type": type, "X-Content-Type-Options": "nosniff" });
  res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
};

function frame(text) {
  const data = Buffer.from(text);
  const head = data.length < 126 ? Buffer.from([0x81, data.length]) : Buffer.from([0x81, 126, data.length >> 8, data.length & 255]);
  return Buffer.concat([head, data]);
}
function emit(kind, ref, message) {
  const event = { id: ++eventSeq, at: new Date().toISOString(), kind, ref, message };
  events.unshift(event);
  for (const socket of sockets) socket.write(frame(JSON.stringify(event)));
  return event;
}

function calibration(threshold) {
  const rows = calibrationExamples.map((e) => ({ ...e, referred: e.score >= threshold }));
  const tp = rows.filter((e) => e.referred && e.expected).length;
  const fp = rows.filter((e) => e.referred && !e.expected).length;
  const tn = rows.filter((e) => !e.referred && !e.expected).length;
  const fn = rows.filter((e) => !e.referred && e.expected).length;
  return { ...state.calibration, threshold, tp, fp, tn, fn, cost: 2 * fn + fp, errors: rows.filter((e) => (e.referred && !e.expected) || (!e.referred && e.expected)).map((e) => ({ ...e, outcome: e.referred ? "fp" : "fn" })) };
}

function caseById(id) {
  return state.findings.find((f) => f.id === id);
}

let fakeScan = null;
function startScan(mode) {
  const id = createHash("sha1").update(String(Date.now())).digest("hex").slice(0, 32);
  const names = state.sources.slice(0, 8).map((s) => s.name);
  fakeScan = { id, scanId: id, mode, status: "running", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), attempts: 1, steps: names.map((name, i) => ({ id: `s${i}`, name, status: "queued" })), startedMs: Date.now() };
  state.scans.unshift({ ...fakeScan, steps: undefined, captures: null, progress: { done: 0, total: names.length } });
  emit("scan", id, "Dodano skan do kolejki");
  const tick = setInterval(() => {
    const done = Math.min(names.length, Math.floor((Date.now() - fakeScan.startedMs) / 900));
    fakeScan.steps.forEach((s, i) => { s.status = i < done ? "done" : i === done ? "running" : "queued"; });
    state.scans[0].progress = { done, total: names.length };
    if (done >= names.length) {
      clearInterval(tick);
      state.scans[0] = { ...state.scans[0], status: "done", updatedAt: new Date().toISOString(), captures: 78, progress: null };
      fakeScan.status = "done";
      emit("scan", id, "Skan zakończony");
    }
  }, 500);
  return state.scans[0];
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const path = decodeURIComponent(url.pathname);
  try {
    if (path === "/v1/health") return send(res, 200, { status: "ok", schema: 5 });
    if (path === "/v1/state") return send(res, 200, { ...state, events: events.concat(state.events).slice(0, 50) });
    if (path.startsWith("/v1/queues/")) {
      if (!withQueues) return send(res, 404, { detail: "Not Found" });
      const name = path.slice(11);
      if (!QUEUE_NAMES.includes(name)) return send(res, 404, { detail: "Nieznana kolejka." });
      const normalized = normalizeState(state);
      const items = queueFromState(name, normalized.cases).map((c) => ({ id: c.id, title: c.title, module: c.module }));
      return send(res, 200, { items, total: items.length, nextCursor: null, asOf: state.asOf, lastScan: state.scans[0] });
    }
    if (path === "/v1/calibration") return send(res, 200, calibration(Number(url.searchParams.get("threshold") ?? 60)));
    if (path === "/v1/threshold/history") return send(res, 404, { detail: "Not Found" });
    if (path === "/v1/scans" && req.method === "POST") {
      const body = JSON.parse(await readBody(req));
      if (fakeScan?.status === "running") return send(res, 409, { detail: "Skan jest już w toku." });
      return send(res, 202, startScan(body.mode));
    }
    if (path.startsWith("/v1/scans/")) {
      return fakeScan && path.endsWith(fakeScan.id) ? send(res, 200, { ...fakeScan, progress: state.scans[0].progress }) : send(res, 404, { detail: "Nie znaleziono skanu." });
    }
    if (path === "/v1/media" && req.method === "POST") {
      await readBody(req);
      const title = url.searchParams.get("title") || "plik";
      const id = `upload-${Date.now().toString(16)}`;
      state.findings.push({ id, title, module: "M1", platform: "upload", origin: "upload", mode: "upload", status: "new", revision: 1, version: 1, observedAt: new Date().toISOString(), description: url.searchParams.get("description") || "", score: 0, history: [], evidence: [], needsRecalc: false });
      emit("finding", id, title);
      return send(res, 202, { scanId: id });
    }
    const m = path.match(/^\/v1\/cases\/(.+?)(\/versions)?$/);
    if (m) {
      const f = caseById(m[1]);
      if (!f) return send(res, 404, { detail: "Nie znaleziono sprawy." });
      if (m[2]) return send(res, 200, { versions: f.versions || [] });
      if (req.method === "PATCH") {
        const body = JSON.parse(await readBody(req));
        if (body.expectedRevision !== f.revision) return send(res, 409, { detail: "Sprawa została zmieniona. Odśwież ją przed zapisem.", current: { revision: f.revision, status: f.status, version: f.version } });
        if (!String(body.note || "").trim()) return send(res, 422, { detail: "Wpisz uzasadnienie decyzji." });
        f.status = body.status;
        f.revision += 1;
        f.lastDecision = { status: body.status, at: new Date().toISOString(), note: body.note, version: f.version, revision: f.revision, route: f.reviewDecision?.route ?? null };
        f.history = [...(f.history || []), { seq: (f.history?.length || 0) + 1, at: f.lastDecision.at, action: "decision", changeKind: "decision", note: body.note, details: { status: body.status, version: f.version } }];
        emit("case", f.id, "Zapisano decyzję analityka");
        return send(res, 200, f);
      }
      return send(res, 200, f);
    }
    if (path === "/dev/alert") {
      const ref = url.searchParams.get("ref") || state.findings[0].id;
      return send(res, 200, emit("high_risk", ref, caseById(ref)?.title || ref));
    }
    if (path === "/dev/bump") {
      const f = caseById(url.searchParams.get("id"));
      if (f) f.revision += 1;
      return send(res, 200, { revision: f?.revision });
    }
    // pliki statyczne
    let file = normalize(join(root, path === "/" ? "index.html" : path));
    if (!file.startsWith(root)) return send(res, 403, "Zabronione", "text/plain");
    const info = await stat(file).catch(() => null);
    if (info?.isDirectory()) file = join(file, "index.html");
    const data = await readFile(file).catch(() => null);
    if (!data) return send(res, 404, "Nie znaleziono", "text/plain");
    return send(res, 200, data, TYPES[extname(file)] || "application/octet-stream");
  } catch (e) {
    return send(res, 500, { detail: String(e.message || e) });
  }
});

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

server.on("upgrade", (req, socket) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname !== "/v1/events") return socket.destroy();
  const key = req.headers["sec-websocket-key"];
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${createHash("sha1").update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest("base64")}\r\n\r\n`);
  socket.write(frame(JSON.stringify({ kind: "ready", id: eventSeq })));
  sockets.add(socket);
  socket.on("data", () => {});
  socket.on("close", () => sockets.delete(socket));
  socket.on("error", () => sockets.delete(socket));
});

server.listen(port, "127.0.0.1", () => console.log(`InvestWatch dev: http://127.0.0.1:${port}/ (kolejki API: ${withQueues ? "tak" : "nie, adapter"})`));
