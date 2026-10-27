const CATEGORIES = ["Breakfast", "Lunch", "Dinner", "Hotel", "Office", "Software", "Uber", "Taxi", "Airfare", "Entertainment"];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

function badge(decision) {
  const d = decision || "pending";
  return `<span class="badge ${esc(d)}">${esc(d)}</span>`;
}

function latest(expense) {
  if (expense.latest) return expense.latest;
  const ds = expense.decisions || [];
  return ds.length ? ds[ds.length - 1].payload : null;
}

function money(p) {
  if (!p || p.amount == null) return "";
  return p.currency && p.currency !== "USD" ? `${p.amount.toFixed(2)} ${p.currency}` : `$${p.amount.toFixed(2)}`;
}

function subscribe(onEvent) {
  const es = new EventSource("/api/stream");
  es.onmessage = e => onEvent(JSON.parse(e.data));
  return es;
}
