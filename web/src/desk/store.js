// Stan pulpitu: dane ze /v1/state, odświeżanie w tle, zdarzenia WebSocket i alerty wysokiego ryzyka.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

export function useDeskData() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [refreshError, setRefreshError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loadedAt, setLoadedAt] = useState(null);
  const [live, setLive] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const inFlight = useRef(false);
  const again = useRef(false);
  const timer = useRef(null);

  const refresh = useCallback(async () => {
    if (inFlight.current) {
      again.current = true;
      return;
    }
    inFlight.current = true;
    setRefreshing(true);
    try {
      const next = await api.state();
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
        again.current = false;
        clearTimeout(timer.current);
        timer.current = setTimeout(refresh, 400);
      }
    }
  }, []);

  const schedule = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(refresh, 400);
  }, [refresh]);

  useEffect(() => {
    refresh();
    const stop = api.events({
      onStatus: (up, resumed) => {
        setLive(up);
        if (up && resumed) schedule();
      },
      onEvent: (event) => {
        if (event.kind === "high_risk") {
          setAlerts((list) => [{ id: event.id, ref: event.ref, message: event.message, at: event.at }, ...list.filter((a) => a.id !== event.id)].slice(0, 3));
        }
        schedule();
      },
    });
    return () => {
      stop();
      clearTimeout(timer.current);
    };
  }, [refresh, schedule]);

  const dismissAlert = useCallback((id) => setAlerts((list) => list.filter((a) => a.id !== id)), []);
  return { data, error, refreshError, refreshing, loadedAt, live, alerts, dismissAlert, refresh, schedule };
}

export function useQueue(name, data, loadedAt) {
  const [state, setState] = useState({ status: "loading", items: [], error: null, route: null });
  useEffect(() => {
    if (!name || !data) return undefined;
    let cancelled = false;
    setState((s) => ({ ...s, status: s.items.length ? "refreshing" : "loading", error: null }));
    api.queue(name, data).then(
      (result) => !cancelled && setState({ status: "ready", items: result.items, error: null, route: result.route }),
      (e) => !cancelled && setState((s) => ({ ...s, status: "error", error: e.message })),
    );
    return () => {
      cancelled = true;
    };
  }, [name, data, loadedAt]);
  return state;
}
