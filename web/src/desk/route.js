// Adres jest stanem widoku: #zakładka?case=ID&module=M1&from=2026-11-01. Odświeżenie i „Wstecz” zachowują filtry.
import { useCallback, useEffect, useState } from "react";
import { EMPTY_FILTERS, FILTER_KEYS } from "./filters.js";

export const TABS = [
  { id: "review", label: "Co wymaga sprawdzenia", queue: "review", mode: "split" },
  { id: "register", label: "Rejestr reklam M1", queue: "adRegister", mode: "table" },
  { id: "m2", label: "Oferty WWW M2", queue: "offersM2", mode: "table" },
  { id: "m3", label: "Oferty M3", queue: "offersM3", mode: "table" },
  { id: "incomplete", label: "Niepełne dane", queue: "incomplete", mode: "split" },
  { id: "closed", label: "Zamknięte", queue: "closed", mode: "split" },
  { id: "sources", label: "Źródła", queue: null, mode: "page" },
  { id: "calibration", label: "Kalibracja", queue: null, mode: "page" },
  { id: "demo", label: "Demo i własne pliki", queue: "demo", mode: "split" },
  { id: "evidence", label: "Dodaj dowód", queue: null, mode: "page" },
];
export const TAB_BY_ID = Object.fromEntries(TABS.map((t) => [t.id, t]));

export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const tab = TAB_BY_ID[path] ? path : "review";
  const params = new URLSearchParams(query);
  const filters = { ...EMPTY_FILTERS };
  for (const key of FILTER_KEYS) if (params.has(key)) filters[key] = params.get(key) || EMPTY_FILTERS[key];
  return { tab, caseId: params.get("case") || null, filters };
}

export function hashFor(tab, { caseId = null, filters = EMPTY_FILTERS } = {}) {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) if (filters[key] && filters[key] !== EMPTY_FILTERS[key]) params.set(key, filters[key]);
  if (caseId) params.set("case", caseId);
  const query = params.toString();
  return `#${tab}${query ? `?${query}` : ""}`;
}

export function useRoute() {
  const [route, setRoute] = useState(() => parseHash());
  useEffect(() => {
    const onChange = () => setRoute(parseHash());
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
