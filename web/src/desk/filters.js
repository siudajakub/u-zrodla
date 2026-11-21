// Filtry widoku siedzą w adresie (#) i trafiają do GET /v1/queues/{name} (q, module, platform, band, dateField, since, until, section).
// Lista nie filtruje po stronie przeglądarki: stronicowanie wymaga, żeby filtr robił serwer.
export const EMPTY_FILTERS = { q: "", module: "all", source: "all", band: "all", from: "", to: "", dateField: "observedAt", section: "all" };
export const FILTER_KEYS = Object.keys(EMPTY_FILTERS);

export const activeCount = (f) => FILTER_KEYS.filter((k) => k !== "dateField" && f[k] !== EMPTY_FILTERS[k]).length;

const BAND = { strong: "mocna", moderate: "średnia", weak: "słaba" };
export const PLATFORMS = [{ value: "youtube", label: "YouTube" }, { value: "tiktok", label: "TikTok" }, { value: "instagram", label: "Instagram" }, { value: "facebook", label: "Facebook" }, { value: "web", label: "WWW" }];
const SECTION = { confirmed: "potwierdzone", candidate: "do potwierdzenia" };

export function describeFilters(f) {
  const out = [];
  if (f.q.trim()) out.push(`„${f.q.trim()}”`);
  if (f.module !== "all") out.push(`Moduł ${f.module}`);
  if (f.source !== "all") out.push(`Platforma ${PLATFORMS.find((p) => p.value === f.source)?.label || f.source}`);
  if (f.band !== "all") out.push(`Siła: ${BAND[f.band] || f.band}`);
  if (f.section !== "all") out.push(`Rejestr: ${SECTION[f.section] || f.section}`);
  const when = f.dateField === "publishedAt" ? "opublikowano" : "odczytano";
  if (f.from) out.push(`${when} od ${f.from}`);
  if (f.to) out.push(`${when} do ${f.to}`);
  return out.join(", ");
}
