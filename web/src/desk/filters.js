// Filtry widoku siedzą w adresie (#) i trafiają do GET /v1/queues/{name} (q, module, platform, band, dateField, since, until, section).
// Lista nie filtruje po stronie przeglądarki: stronicowanie wymaga, żeby filtr robił serwer.
// Wyjątek: `disc` (rejestr: jak ujawniono) zawęża już pobrany rejestr, bo API nie ma takiego parametru.
import { MODULE_NAME, STATES } from "./labels.js";

export const EMPTY_FILTERS = { state: "review", q: "", module: "all", source: "all", band: "all", from: "", to: "", dateField: "observedAt", section: "all", disc: "all" };
export const FILTER_KEYS = Object.keys(EMPTY_FILTERS);

export const activeCount = (f) => FILTER_KEYS.filter((k) => k !== "dateField" && k !== "state" && f[k] !== EMPTY_FILTERS[k]).length;

/** Kolejka API dla stanu i modułu: Do sprawdzenia → review, Niepełne → incomplete, Zamknięte → closed, Demo → demo, Wszystkie → offersM2/offersM3 przy module M2/M3, inaczej all. */
export function queueFor(state, module) {
  if (state === "all") return module === "M2" ? "offersM2" : module === "M3" ? "offersM3" : "all";
  return STATES.find((s) => s.value === state)?.queue || "review";
}

const BAND = { strong: "mocna", moderate: "średnia", weak: "słaba" };
export const PLATFORMS = [{ value: "youtube", label: "YouTube" }, { value: "tiktok", label: "TikTok" }, { value: "instagram", label: "Instagram" }, { value: "facebook", label: "Facebook" }, { value: "web", label: "WWW" }];
const SECTION = { confirmed: "potwierdzone", candidate: "do potwierdzenia" };
export const DISC = { in_description: "w opisie", in_speech: "w mowie", platform_flag: "flaga YouTube", pending: "czeka na mowę" };

export function describeFilters(f) {
  const out = [];
  if (f.q.trim()) out.push(`„${f.q.trim()}”`);
  if (f.state !== "review") out.push(`Stan: ${STATES.find((s) => s.value === f.state)?.label || f.state}`);
  if (f.module !== "all") out.push(MODULE_NAME[f.module] || f.module);
  if (f.source !== "all") out.push(`Źródło: ${PLATFORMS.find((p) => p.value === f.source)?.label || f.source}`);
  if (f.band !== "all") out.push(`Siła: ${BAND[f.band] || f.band}`);
  if (f.section !== "all") out.push(`Rejestr: ${SECTION[f.section] || f.section}`);
  if (f.disc !== "all") out.push(`Ujawnienie: ${DISC[f.disc] || f.disc}`);
  const when = f.dateField === "publishedAt" ? "opublikowano" : "odczytano";
  if (f.from) out.push(`${when} od ${f.from}`);
  if (f.to) out.push(`${when} do ${f.to}`);
  return out.join(", ");
}
