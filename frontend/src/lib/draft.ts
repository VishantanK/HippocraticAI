import { useEffect } from "react";

/** Unsent form drafts, kept for this tab only (sessionStorage) so a reload or a wrong click doesn't lose them. */
const PREFIX = "expense-portal.draft.";

export function loadDraft<T>(key: string): T | null {
  try { const v = sessionStorage.getItem(PREFIX + key); return v ? (JSON.parse(v) as T) : null; } catch { return null; }
}

export function saveDraft(key: string, value: unknown) {
  try { sessionStorage.setItem(PREFIX + key, JSON.stringify(value)); } catch { /* storage blocked: no drafts */ }
}

export function clearDraft(key: string) {
  try { sessionStorage.removeItem(PREFIX + key); } catch { /* ignore */ }
}

/** Ask before closing or reloading the tab while there is unsent input. */
export function useUnsavedWarning(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
}

/** One key per user action, so a retried request is recognised by the server (Idempotency-Key). */
export function newActionKey() {
  try { return crypto.randomUUID(); } catch { return `${Date.now()}-${Math.random().toString(36).slice(2)}`; }
}
