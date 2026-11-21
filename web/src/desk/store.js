// Stan pulpitu: odczyt /v1/overview, lekkie odświeżanie w tle, zdarzenia WebSocket i alerty.
// Listy i karty spraw czytają kolejki i /v1/cases; tutaj są tylko liczniki, skany, źródła, próg i wariant.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";

export function useDeskData() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [refreshError, setRefreshError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loadedAt, setLoadedAt] = useState(null);
  const [live, setLive] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [rev, setRev] = useState(0);
  const inFlight = useRef(false);
  const again = useRef(null);
  const timer = useRef(null);
  const sig = useRef("");
  const dataRef = useRef(null);

  const refresh = useCallback(async ({ heavy = false } = {}) => {
    if (inFlight.current) {
      again.current = { heavy: heavy || again.current?.heavy };
      return;
    }
    inFlight.current = true;
    setRefreshing(true);
    try {
      let next;
      const current = dataRef.current;
      if (heavy || !current) {
        next = await api.state();
      } else {
        const light = await api.light();
        next = { ...current, counts: light.counts || current.counts, threshold: light.threshold || current.threshold, lastScan: light.lastScan, asOf: light.asOf };
      }
      const fingerprint = JSON.stringify([next.counts, next.threshold?.id, next.threshold?.value, next.lastScan?.id, next.lastScan?.updatedAt, next.qualification?.id]);
      if (fingerprint !== sig.current) {
        sig.current = fingerprint;
        api.clearCases();
        setRev((n) => n + 1);
      }
      dataRef.current = next;
      setData(next);
      setError(null);
      setRefreshError(null);
      setLoadedAt(new Date().toISOString());
    } catch (e) {
      setRefreshError(e.message);
      setData((current) => {
        if (!current) setError(e.message);
        return current;
      });
    } finally {
      inFlight.current = false;
      setRefreshing(false);
      if (again.current) {
        const next = again.current;
        again.current = null;
        clearTimeout(timer.current);
        timer.current = setTimeout(() => refresh(next), 400);
      }
    }
  }, []);

  const schedule = useCallback((options) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => refresh(options), 400);
  }, [refresh]);

  useEffect(() => {
    refresh({ heavy: true });
    const stop = api.events({
      onStatus: (up, resumed) => {
        setLive(up);
        if (up && resumed) schedule();
      },
      onEvent: (event) => {
        if (event.kind === "high_risk") {
          setAlerts((list) => [{ id: event.id, ref: event.ref, message: event.message, at: event.at }, ...list.filter((a) => a.id !== event.id)].slice(0, 3));
        }
        schedule({ heavy: event.kind === "scan" || event.kind === "qualification" || event.kind === "threshold" });
      },
    });
    return () => {
      stop();
      clearTimeout(timer.current);
    };
  }, [refresh, schedule]);

  const dismissAlert = useCallback((id) => setAlerts((list) => list.filter((a) => a.id !== id)), []);
  return { data, error, refreshError, refreshing, loadedAt, live, alerts, dismissAlert, refresh, schedule, rev };
}

/** Kolejka ze stronicowaniem: pierwsza strona po zmianie kolejki, filtrów lub wersji danych, kolejne przez `more()`. */
export function useQueue(name, filters, data, rev) {
  const [state, setState] = useState({ status: "loading", items: [], total: 0, nextCursor: null, error: null, legacy: false, loadingMore: false });
  const key = useMemo(() => JSON.stringify([name, filters]), [name, filters]);
  const creators = data?.creatorMap;
  const gen = useRef(0);
  useEffect(() => {
    if (!name || !data) return undefined;
    const mine = ++gen.current;
    setState((s) => ({ ...s, status: s.items.length ? "refreshing" : "loading", error: null, legacy: false }));
    const wait = filters?.q ? 250 : 0;
    const t = setTimeout(() => {
      api.queue(name, filters, { creators }).then(
        (r) => mine === gen.current && setState({ status: "ready", items: r.items, total: r.total, nextCursor: r.nextCursor, error: null, legacy: false, loadingMore: false }),
        (e) => mine === gen.current && setState((s) => ({ ...s, status: "error", error: e.message, legacy: e.status === 404, loadingMore: false })),
      );
    }, wait);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, rev, !!data]);
  const more = useCallback(() => {
    setState((s) => {
      if (!s.nextCursor || s.loadingMore) return s;
      const mine = gen.current;
      api.queue(name, filters, { cursor: s.nextCursor, creators }).then(
        (r) => mine === gen.current && setState((cur) => ({ ...cur, items: [...cur.items, ...r.items.filter((i) => !cur.items.some((x) => x.id === i.id))], total: r.total, nextCursor: r.nextCursor, loadingMore: false })),
        (e) => mine === gen.current && setState((cur) => ({ ...cur, loadingMore: false, error: e.message })),
      );
      return { ...s, loadingMore: true };
    });
  }, [name, filters, creators]);
  return { ...state, more };
}

/** Pełna sprawa z /v1/cases/{id} (z pamięcią podręczną do następnej zmiany danych). */
export function useCase(id, data, rev, reload = 0) {
  const [state, setState] = useState({ status: id ? "loading" : "idle", c: null, error: null });
  const creators = data?.creatorMap;
  useEffect(() => {
    if (!id || !data) {
      setState({ status: "idle", c: null, error: null });
      return undefined;
    }
    let cancelled = false;
    setState((s) => ({ status: s.c?.id === id ? "refreshing" : "loading", c: s.c?.id === id ? s.c : null, error: null }));
    api.case(id, creators, { fresh: reload > 0 }).then(
      (c) => !cancelled && setState({ status: "ready", c, error: null }),
      (e) => !cancelled && setState({ status: "error", c: null, error: e.message, notFound: e.status === 404 }),
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, rev, reload, !!data]);
  return state;
}
