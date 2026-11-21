// Adres jest stanem widoku: #zakładka?case=ID&state=incomplete&module=M2&from=2026-11-01. Odświeżenie i „Wstecz” zachowują filtry.
// Cztery zakładki: Do sprawdzenia, Rejestr reklam, Źródła, Kalibracja. Stan i moduł to filtry listy „Do sprawdzenia”.
import { useCallback, useEffect, useState } from "react";
import { EMPTY_FILTERS, FILTER_KEYS } from "./filters.js";

export const TABS = [
  { id: "review", label: "Do sprawdzenia", mode: "split" },
  { id: "register", label: "Rejestr reklam", queue: "adRegister", mode: "table" },
  { id: "sources", label: "Źródła", queue: null, mode: "page" },
  { id: "calibration", label: "Kalibracja", queue: null, mode: "page" },
];
export const TAB_BY_ID = Object.fromEntries(TABS.map((t) => [t.id, t]));

/** Stare adresy zakładek → zakładka i filtry (przekierowanie, żeby nie psuć zapisanych linków). */
export const LEGACY = {
  m2: { tab: "review", filters: { state: "all", module: "M2" } },
  m3: { tab: "review", filters: { state: "all", module: "M3" } },
  incomplete: { tab: "review", filters: { state: "incomplete" } },
  niepelne: { tab: "review", filters: { state: "incomplete" } },
  closed: { tab: "review", filters: { state: "closed" } },
  zamkniete: { tab: "review", filters: { state: "closed" } },
  demo: { tab: "review", filters: { state: "demo" } },
  evidence: { tab: "sources", filters: {}, add: true },
  dodaj: { tab: "sources", filters: {}, add: true },
};

export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const legacy = LEGACY[path];
  const tab = legacy ? legacy.tab : TAB_BY_ID[path] ? path : "review";
  const params = new URLSearchParams(query);
  const filters = { ...EMPTY_FILTERS, ...(legacy?.filters || {}) };
  for (const key of FILTER_KEYS) if (params.has(key)) filters[key] = params.get(key) || EMPTY_FILTERS[key];
  return { tab, caseId: params.get("case") || null, filters, add: !!legacy?.add || params.get("add") === "1", legacy: !!legacy };
}

export function hashFor(tab, { caseId = null, filters = EMPTY_FILTERS, add = false } = {}) {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) if (filters[key] && filters[key] !== EMPTY_FILTERS[key]) params.set(key, filters[key]);
  if (caseId) params.set("case", caseId);
  if (add) params.set("add", "1");
  const query = params.toString();
  return `#${tab}${query ? `?${query}` : ""}`;
}

export function useRoute() {
  const [route, setRoute] = useState(() => {
    const first = parseHash();
    if (first.legacy) history.replaceState(null, "", hashFor(first.tab, first));
    return first;
  });
  useEffect(() => {
    const onChange = () => {
      const next = parseHash();
      if (next.legacy) history.replaceState(null, "", hashFor(next.tab, next));
      setRoute(next);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const go = useCallback((tab, next = {}, { replace = false } = {}) => {
    const hash = hashFor(tab, next);
    if (replace) history.replaceState(null, "", hash);
    else if (location.hash !== hash) location.hash = hash;
    setRoute(parseHash(hash));
  }, []);
  return [route, go];
}
