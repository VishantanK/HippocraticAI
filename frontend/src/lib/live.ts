import { useEffect, useRef, useState } from "react";

/** "resync" is local, not from the server: events may have been missed, so reload everything shown. */
export interface LiveEvent { type: "queued" | "processing" | "decision" | "error" | "delivery" | "resync"; expense_id: string; payload?: unknown }

type Listener = (e: LiveEvent) => void;
const listeners = new Set<Listener>();
const statusListeners = new Set<(up: boolean) => void>();
let source: EventSource | null = null;
let connected = false;

let opened = false;

const emit = (event: LiveEvent) => listeners.forEach((fn) => fn(event));
const resync = () => emit({ type: "resync", expense_id: "*" });

function ensure() {
  if (source) return;
  source = new EventSource("/api/stream");
  source.onopen = () => {
    setConnected(true);
    if (opened) resync(); // a reconnect: anything sent while we were away was missed
    opened = true;
  };
  source.onerror = () => setConnected(false); // EventSource reconnects on its own
  source.onmessage = (m) => {
    let event: LiveEvent;
    try { event = JSON.parse(m.data) as LiveEvent; } catch { return; } // skip a malformed message
    emit(event);
  };
  // Background tabs can be throttled or put to sleep; catch up when the tab is looked at again.
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") resync(); });
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
