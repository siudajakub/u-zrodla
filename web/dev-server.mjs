// Serwer deweloperski bez backendu: pliki z web/ oraz API schematu 2 (w tym GET /v1/overview i GET /v1/report) zbudowane z web/sample/export.json
// (eksport prawdziwego API, patrz web/sample/build_sample.py). Kolejki mają kursor i filtry jak GET /v1/queues/{name}.
// Uruchomienie:  node web/dev-server.mjs [--port 18790] [--legacy]
// --legacy: GET /v1/queues/{name} zwraca 404, żeby zobaczyć stan „starsze API”.
// Do prób ręcznych: GET /dev/alert?ref=<id sprawy> wysyła zdarzenie high_risk przez WebSocket do otwartych sesji.
import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { extname, join, normalize } from "node:path";

const args = process.argv.slice(2);
const port = Number(args[args.indexOf("--port") + 1]) || 18790;
const legacy = args.includes("--legacy");
const root = fileURLToPath(new URL(".", import.meta.url));
const exported = JSON.parse(await readFile(join(root, "sample/export.json"), "utf8"));
const { state, queues, cases } = exported;
state.scans = state.scans.map((s) => (s.status === "queued" ? { ...s, status: "done" } : s));
const resolutionStatus = { refer_to_control: "reviewing", complete_data: "reviewing", no_signal: "closed", close: "closed" };
let eventSeq = 1000;
const sockets = new Set();
const events = [];
let threshold = { ...state.threshold };
let thresholdHistory = [...exported.thresholdHistory.items];
let qualification = { ...state.qualification };
let qualificationHistory = [...exported.qualificationHistory.items];

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

const counts = () => Object.fromEntries(Object.entries(state.queues).map(([k, v]) => [k, queues[k] ? queues[k].length : v]));

/** Odpowiedź kolejki: filtry i kursor jak w API (q, module, platform, since, until, minScore, section, limit, cursor). */
function queuePage(name, params) {
  let items = [...queues[name]];
  const q = params.get("q")?.toLocaleLowerCase("pl-PL");
  const field = params.get("dateField") === "publishedAt" ? "publishedAt" : "observedAt";
  if (params.get("module")) items = items.filter((i) => i.module === params.get("module"));
  if (params.get("platform")) items = items.filter((i) => i.platform === params.get("platform"));
  if (params.get("band")) items = items.filter((i) => i.band === params.get("band"));
  if (params.get("since")) items = items.filter((i) => Date.parse(i[field]) >= Date.parse(params.get("since")));
  if (params.get("until")) items = items.filter((i) => Date.parse(i[field]) <= Date.parse(params.get("until")));
  if (params.get("minScore")) items = items.filter((i) => (i.reviewScore ?? -1) >= Number(params.get("minScore")));
  if (params.get("section") === "confirmed") items = items.filter((i) => i.adRegistry === "included");
  if (params.get("section") === "candidate") items = items.filter((i) => i.adRegistry === "candidate");
  if (q) items = items.filter((i) => `${i.title || ""} ${i.creatorName || ""}`.toLocaleLowerCase("pl-PL").includes(q));
  const limit = Math.min(500, Math.max(1, Number(params.get("limit")) || 50));
  const start = Number(params.get("cursor") || 0);
  const page = items.slice(start, start + limit);
  const last = state.scans[0];
  return { items: page, total: items.length, nextCursor: start + limit < items.length ? String(start + limit) : null, counts: counts(), threshold, asOf: new Date().toISOString(), lastScan: { id: last.id, status: last.status, updatedAt: last.updatedAt } };
}

function calibration(value) {
  const keys = Object.keys(exported.calibration).map(Number);
  const nearest = keys.reduce((a, b) => (Math.abs(b - value) < Math.abs(a - value) ? b : a));
  return { ...exported.calibration[String(nearest)], threshold: value };
}

let fakeScan = null;
function startScan(mode) {
  const id = createHash("sha1").update(String(Date.now())).digest("hex").slice(0, 32);
  const names = state.sources.slice(0, 6).map((s) => s.name);
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

function moveCase(c, status) {
  const row = (name) => queues[name]?.find((i) => i.id === c.id);
  if (status === "closed") {
    for (const name of ["review", "incomplete"]) queues[name] = queues[name].filter((i) => i.id !== c.id);
    if (!row("closed")) queues.closed.unshift({ ...(queues.review.find((i) => i.id === c.id) || summaryOf(c)), status, lastDecision: c.lastDecision });
  }
  for (const name of Object.keys(queues)) for (const i of queues[name]) if (i.id === c.id) { i.status = status; i.revision = c.revision; i.lastDecision = c.lastDecision; }
}
const summaryOf = (c) => ({ id: c.id, title: c.title, module: c.module, platform: c.platform, creatorId: c.creatorId, creatorName: null, publishedAt: c.publishedAt, observedAt: c.observedAt, status: c.status, revision: c.revision, version: c.version, origin: c.origin, route: c.route, reviewScore: c.reviewScore?.value ?? null, queueEligible: c.queueEligible, adRegistry: c.adRegistry?.state ?? null, queues: ["closed", "all"], needsRecalc: false, pendingReReview: false, reviewStale: false, reason: c.reviewDecision?.reason ?? null, firstMoment: null, lastDecision: c.lastDecision, url: c.url });

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const path = decodeURIComponent(url.pathname);
  try {
    if (path === "/v1/health") return send(res, 200, { status: "ok", schema: 7 });
    if (path === "/v1/report") {
      const module = url.searchParams.get("module") || "M1";
      const names = { M1: ["review", "adRegister"], M2: ["offersM2"], M3: ["offersM3"] }[module] || ["all"];
      const seen = new Set();
      const params = new URLSearchParams([...url.searchParams].filter(([k]) => k !== "limit" && k !== "cursor" && k !== "module"));
      params.set("limit", "500");
      const rows = names.flatMap((n) => queuePage(n, params).items).filter((i) => !seen.has(i.id) && seen.add(i.id));
      const cell = (v) => `"${String(v ?? "").replace(/"/g, '""').replace(/^([=+\-@\t\r])/, "'$1")}"`;
      const head = ["firma", "tresc", "url", "platforma", "dataPublikacji", "dataOdczytu", "trasa", "silaSygnalu", "statusDecyzji", "id"];
      const lines = rows.map((i) => [i.creatorName, i.title, i.url, i.platform, i.publishedAt, i.observedAt, i.route, i.reviewScore, i.status, i.id].map(cell).join(","));
      if (url.searchParams.get("format") === "json") return send(res, 200, { items: rows, total: rows.length });
      res.writeHead(200, { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": `attachment; filename="investwatch-raport-${module}.csv"`, "X-Total-Count": String(rows.length) });
      return res.end(`\uFEFF${[head.join(","), ...lines].join("\r\n")}\r\n`);
    }
    if (path === "/v1/overview" || path === "/v1/state") return send(res, 200, { ...state, queues: counts(), findings: [], threshold, qualification, events: events.concat(state.events).slice(0, 50) });
    if (path.startsWith("/v1/queues/")) {
      if (legacy) return send(res, 404, { detail: "Not Found" });
      const name = path.slice(11);
      if (!queues[name]) return send(res, 404, { detail: "Nie ma takiej kolejki." });
      return send(res, 200, queuePage(name, url.searchParams));
    }
    if (path === "/v1/trend") return send(res, 200, exported.trend);
    if (path === "/v1/calibration") return send(res, 200, calibration(Number(url.searchParams.get("threshold") ?? 60)));
    if (path === "/v1/threshold") {
      if (req.method === "PUT") {
        const body = JSON.parse(await readBody(req));
        if (body.expectedId !== threshold.id) return send(res, 409, { detail: "Próg zmieniono w międzyczasie." });
        threshold = { ...threshold, id: threshold.id + 1, value: body.value, note: body.note, setAt: new Date().toISOString(), restoredFrom: null };
        thresholdHistory.push(threshold);
        emit("threshold", String(threshold.id), "Zmieniono próg");
      }
      return send(res, 200, threshold);
    }
    if (path === "/v1/threshold/history") return send(res, 200, { items: thresholdHistory });
    if (path === "/v1/threshold/restore" && req.method === "POST") {
      const body = JSON.parse(await readBody(req));
      const old = thresholdHistory.find((h) => h.id === body.id);
      if (!old || body.expectedId !== threshold.id) return send(res, 409, { detail: "Nie można przywrócić." });
      threshold = { ...old, id: threshold.id + 1, setAt: new Date().toISOString(), restoredFrom: old.id, note: body.note };
      thresholdHistory.push(threshold);
      return send(res, 200, threshold);
    }
    if (path === "/v1/qualification") return send(res, 200, qualification);
    if (path === "/v1/qualification/history") return send(res, 200, { items: qualificationHistory });
    if (path === "/v1/qualification/restore" && req.method === "POST") {
      const body = JSON.parse(await readBody(req));
      const old = qualificationHistory.find((h) => h.id === body.id);
      if (!old || body.expectedId !== qualification.id) return send(res, 409, { detail: "Nie można przywrócić." });
      qualification = { ...old, id: qualification.id + 1, setAt: new Date().toISOString(), restoredFrom: old.id, note: body.note };
      qualificationHistory.push(qualification);
      return send(res, 200, qualification);
    }
    if (path === "/v1/scans" && req.method === "POST") {
      const body = JSON.parse(await readBody(req));
      if (fakeScan?.status === "running") return send(res, 409, { detail: "Skan jest już w toku." });
      return send(res, 202, startScan(body.mode));
    }
    if (path.startsWith("/v1/scans/")) {
      const id = path.slice(10);
      if (fakeScan && id === fakeScan.id) return send(res, 200, { ...fakeScan, progress: state.scans[0].progress });
      return exported.scans[id] ? send(res, 200, exported.scans[id]) : send(res, 404, { detail: "Nie znaleziono skanu." });
    }
    if (path.startsWith("/v1/frames/")) {
      const data = await readFile(join(root, "sample/frames", path.slice(11))).catch(() => null);
      return data ? send(res, 200, data, "image/jpeg") : send(res, 404, { detail: "Nie ma takiego kadru." });
    }
    if (path === "/v1/media" && req.method === "POST") {
      await readBody(req);
      return send(res, 202, { scanId: `upload-${Date.now().toString(16)}` });
    }
    const m = path.match(/^\/v1\/cases\/(.+?)(\/versions)?$/);
    if (m) {
      const f = cases[m[1]];
      if (!f) return send(res, 404, { detail: "Nie znaleziono sprawy." });
      if (m[2]) return send(res, 200, { versions: f.versions || [] });
      if (req.method === "PATCH") {
        const body = JSON.parse(await readBody(req));
        if (body.expectedRevision !== f.revision) return send(res, 409, { detail: "Sprawa została zmieniona. Odśwież ją przed zapisem.", current: { revision: f.revision, status: f.status, version: f.version } });
        if (!String(body.note || "").trim()) return send(res, 422, { detail: "Wpisz uzasadnienie decyzji." });
        const status = body.status || resolutionStatus[body.resolution];
        if (!status) return send(res, 422, { detail: "Podaj status lub rodzaj decyzji (resolution)." });
        f.status = status;
        f.revision += 1;
        f.lastDecision = { status, resolution: body.resolution || null, at: new Date().toISOString(), note: body.note, version: f.version, revision: f.revision, route: f.route ?? null };
        f.history = [...(f.history || []), { seq: (f.history?.length || 0) + 1, at: f.lastDecision.at, action: "decision", changeKind: "decision", note: body.note, details: JSON.stringify({ status, resolution: body.resolution, version: f.version }) }];
        moveCase(f, status);
        emit("case", f.id, "Zapisano decyzję analityka");
        return send(res, 200, f);
      }
      return send(res, 200, f);
    }
    if (path === "/dev/alert") {
      const ref = url.searchParams.get("ref") || Object.keys(cases)[0];
      return send(res, 200, emit("high_risk", ref, cases[ref]?.title || ref));
    }
    if (path === "/dev/bump") {
      const f = cases[url.searchParams.get("id")];
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

server.listen(port, "127.0.0.1", () => console.log(`InvestWatch dev: http://127.0.0.1:${port}/ (kolejki API: ${legacy ? "nie, tryb starszego API" : "tak"})`));
