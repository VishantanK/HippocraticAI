/** Saved views for Finance's list: a name plus the page's query string. Kept per browser. */
export interface View { name: string; query: string }

const KEY = "expense-portal.views";

export const PRESETS: View[] = [
  { name: "Over $500", query: "amount_min=500" },
  { name: "Manipulation", query: "manipulation=true" },
  { name: "Delivery problems", query: "delivery=problem" },
  { name: "Waiting on a decision", query: "status=flag&sort=updated&dir=asc" },
];

export function loadViews(): View[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x?.name === "string" && typeof x?.query === "string") : [];
  } catch { return []; }
}

export function saveViews(views: View[]) {
  try { localStorage.setItem(KEY, JSON.stringify(views)); } catch { /* storage blocked: views last this session */ }
}
