// Filtry widoku: data publikacji, źródło (platforma), siła przesłanki, moduł i tekst. Wszystkie siedzą w adresie (#).
import { BANDS } from "./labels.js";

export const EMPTY_FILTERS = { q: "", module: "all", source: "all", risk: "all", from: "", to: "" };
export const FILTER_KEYS = Object.keys(EMPTY_FILTERS);

export function bandOf(c) {
  if (c.score?.band) return c.score.band;
  if (c.score && c.score.value == null) return "none";
  if (c.legacyScore != null && !c.isV2) return c.legacyScore >= 60 ? "strong" : c.legacyScore >= 30 ? "moderate" : "weak";
  return "none";
}

export function applyFilters(items, f) {
  const q = f.q.trim().toLocaleLowerCase("pl-PL");
  return items.filter((c) => {
    const day = String(c.publishedAt || c.observedAt || "").slice(0, 10);
    const hay = [c.title, c.creatorName, c.reason, c.platform, c.relationship?.firmName].filter(Boolean).join(" ").toLocaleLowerCase("pl-PL");
    return (!q || hay.includes(q))
      && (f.module === "all" || c.module === f.module)
      && (f.source === "all" || c.platform === f.source)
      && (f.risk === "all" || bandOf(c) === f.risk)
      && (!f.from || (day && day >= f.from))
      && (!f.to || (day && day <= f.to));
  });
}

export const activeCount = (f) => FILTER_KEYS.filter((k) => f[k] !== EMPTY_FILTERS[k]).length;

export function describeFilters(f) {
  const out = [];
  if (f.q.trim()) out.push(`„${f.q.trim()}”`);
  if (f.module !== "all") out.push(`Moduł ${f.module}`);
  if (f.source !== "all") out.push(`Źródło ${f.source}`);
  if (f.risk !== "all") out.push(`Siła: ${BANDS[f.risk] || "bez oceny"}`);
  if (f.from) out.push(`od ${f.from}`);
  if (f.to) out.push(`do ${f.to}`);
  return out.join(", ");
}
