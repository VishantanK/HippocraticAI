import { useEffect, useRef, useState } from "react";

export interface LiveEvent { type: "queued" | "processing" | "decision" | "error"; expense_id: string; payload?: unknown }

type Listener = (e: LiveEvent) => void;
const listeners = new Set<Listener>();
const statusListeners = new Set<(up: boolean) => void>();
let source: EventSource | null = null;
let connected = false;

function ensure() {
  if (source) return;
  source = new EventSource("/api/stream");
  source.onopen = () => setConnected(true);
  source.onerror = () => setConnected(false); // EventSource reconnects on its own
  source.onmessage = (m) => {
    const event = JSON.parse(m.data) as LiveEvent;
    listeners.forEach((fn) => fn(event));
  };
}

function setConnected(up: boolean) {
  connected = up;
  statusListeners.forEach((fn) => fn(up));
}

/** Subscribe to server events. The handler can change between renders without resubscribing. */
export function useLiveEvents(handler: Listener) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    ensure();
    const fn: Listener = (e) => ref.current(e);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);
}

export function useLiveStatus() {
  const [up, setUp] = useState(connected);
  useEffect(() => {
    ensure();
    statusListeners.add(setUp);
    return () => { statusListeners.delete(setUp); };
  }, []);
  return up;
}
