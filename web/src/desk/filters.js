// Filtry widoku siedzą w adresie (#) i trafiają do GET /v1/queues/{name} (q, module, platform, minScore, since, until, section).
// Lista nie filtruje po stronie przeglądarki: stronicowanie wymaga, żeby filtr robił serwer.
export const EMPTY_FILTERS = { q: "", module: "all", source: "all", risk: "all", from: "", to: "", section: "all" };
export const FILTER_KEYS = Object.keys(EMPTY_FILTERS);

export const activeCount = (f) => FILTER_KEYS.filter((k) => f[k] !== EMPTY_FILTERS[k]).length;

const RISK = { strong: "co najmniej mocna (75 pkt)", moderate: "co najmniej średnia (60 pkt)" };
const SECTION = { confirmed: "potwierdzone", candidate: "do potwierdzenia" };

export function describeFilters(f) {
  const out = [];
  if (f.q.trim()) out.push(`„${f.q.trim()}”`);
  if (f.module !== "all") out.push(`Moduł ${f.module}`);
  if (f.source !== "all") out.push(`Źródło ${f.source}`);
  if (f.risk !== "all") out.push(`Siła: ${RISK[f.risk] || f.risk}`);
  if (f.section !== "all") out.push(`Rejestr: ${SECTION[f.section] || f.section}`);
  if (f.from) out.push(`odczytano od ${f.from}`);
  if (f.to) out.push(`odczytano do ${f.to}`);
  return out.join(", ");
}
