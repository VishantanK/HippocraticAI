import { useCallback, useEffect, useRef, useState } from "react";
import { useLiveEvents, type LiveEvent } from "./live";

/**
 * Load data and keep it fresh: refetches when a server event matches `relevant`.
 * Bursts (a batch run) are coalesced into one refetch. After a reconnect or when the tab
 * becomes visible again, every mounted hook refetches, since events may have been missed.
 */
export function useData<T>(load: () => Promise<T>, deps: unknown[], relevant: (e: LiveEvent) => boolean = () => true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef<number>();
  const loadRef = useRef(load);
  loadRef.current = load;

  const refresh = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useLiveEvents((e) => {
    if (e.type !== "resync" && !relevant(e)) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(refresh, 250);
  });

  return { data, error, loading, refresh, setData };
}
