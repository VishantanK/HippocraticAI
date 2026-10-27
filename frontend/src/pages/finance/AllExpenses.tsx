import { ArrowDown, ArrowUp, Bookmark, Search, ShieldAlert, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Empty, ErrorState, Loading } from "../../components/States";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api";
import { amountOf, categoryLabel, day, POLICY_CATEGORIES, RULE_LABEL } from "../../lib/format";
import { useData } from "../../lib/useData";
import { loadViews, PRESETS, saveViews, type View } from "../../lib/views";

const PAGE = 50;

const STATUS = [
  { key: "", label: "All" },
  { key: "flag", label: "Needs info" },
  { key: "approve", label: "Approved" },
  { key: "reject", label: "Rejected" },
  { key: "checking", label: "Checking" },
  { key: "manipulation", label: "Manipulation" },
] as const;

// Query params that are filters (everything except sort, dir and page). They are also the API's params.
const FILTER_KEYS = ["status", "manipulation", "source", "employee", "category", "date_from", "date_to",
  "amount_min", "amount_max", "rule", "delivery", "q"];

type SortKey = "date" | "amount" | "employee" | "updated";

/** Old links used ?filter=flag / ?filter=manipulation; read them as the new params. */
function normalise(params: URLSearchParams) {
  const p = new URLSearchParams(params);
  const legacy = p.get("filter");
  if (legacy) {
    p.delete("filter");
    p.set(legacy === "manipulation" ? "manipulation" : "status", legacy === "manipulation" ? "true" : legacy);
  }
  return p;
}

/** The API request for this page: filters, sort and the page window. */
export function apiParams(p: URLSearchParams, paged = true) {
  const out = new URLSearchParams();
  FILTER_KEYS.forEach((k) => { const v = p.get(k); if (v) out.set(k, v); });
  out.set("sort", p.get("sort") ?? "updated");
  out.set("dir", p.get("dir") ?? "desc");
  if (paged) {
    out.set("limit", String(PAGE));
    out.set("offset", String((Math.max(1, Number(p.get("page")) || 1) - 1) * PAGE));
  }
  return out;
}

export default function AllExpenses() {
  const [raw, setRaw] = useSearchParams();
  const params = normalise(raw);
  const key = params.toString();
  const { data, error, loading, refresh } = useData(() => api.page(apiParams(params)), [key]);
  const { data: employees } = useData(api.employees, [], (e) => e.type === "queued");

  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    if (!("page" in changes)) next.delete("page"); // any filter change starts again at page 1
    setRaw(next, { replace: true });
  };

  // Search box: typed locally, written to the URL after a pause so each keystroke isn't a request.
  const [q, setQ] = useState(params.get("q") ?? "");
  useEffect(() => { setQ(params.get("q") ?? ""); }, [params.get("q")]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const t = window.setTimeout(() => { if (q !== (params.get("q") ?? "")) set({ q }); }, 300);
    return () => window.clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const sort = (params.get("sort") ?? "updated") as SortKey;
  const dir = params.get("dir") ?? "desc";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const status = params.get("manipulation") ? "manipulation" : params.get("status") ?? "";
  const activeFilters = FILTER_KEYS.filter((k) => params.get(k));
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  const Th = ({ k, children, right = false }: { k: SortKey; children: string; right?: boolean }) => (
    <th className={`table-head ${right ? "text-right" : ""}`} aria-sort={sort === k ? (dir === "asc" ? "ascending" : "descending") : "none"}>
      <button className="inline-flex items-center gap-1 hover:text-ink"
        onClick={() => set({ sort: k, dir: sort === k && dir === "desc" ? "asc" : "desc" })}>
        {children}
        {sort === k && (dir === "asc" ? <ArrowUp size={12} aria-hidden /> : <ArrowDown size={12} aria-hidden />)}
      </button>
    </th>
  );

  return (
    <div className="max-w-6xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">All expenses</h1>
        <p className="mt-1 text-ink-2">From the portal and batch imports, with the latest decision for each.</p>
      </header>

      <Views current={key} onPick={(query) => setRaw(new URLSearchParams(query), { replace: true })} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by status">
          {STATUS.map((f) => (
            <button key={f.key}
              onClick={() => set(f.key === "manipulation" ? { manipulation: "true", status: "" } : { status: f.key, manipulation: "" })}
              aria-pressed={status === f.key}
              className={`rounded-full border px-3 py-1 text-sm ${status === f.key ? "border-ink bg-ink text-paper" : "border-line bg-panel text-ink-2 hover:border-ink-2"}`}>
              {f.label}
            </button>
          ))}
        </div>
        <label className="relative ml-auto">
          <Search size={15} className="absolute left-2.5 top-2.5 text-muted" aria-hidden />
          <span className="sr-only">Search</span>
          <input className="field w-64 py-1.5 pl-8 text-sm" placeholder="Employee, merchant or ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
      </div>

      <div className="grid gap-3 rounded-lg border border-line bg-panel p-4 text-sm sm:grid-cols-3 lg:grid-cols-6">
        <Select label="Employee" value={params.get("employee")} onChange={(v) => set({ employee: v })}
          options={(employees ?? []).map((e) => [e, e])} />
        <Select label="Category" value={params.get("category")} onChange={(v) => set({ category: v })}
          options={POLICY_CATEGORIES.map((c) => [c, categoryLabel(c)])} />
        <Select label="Rule" value={params.get("rule")} onChange={(v) => set({ rule: v })}
          options={Object.entries(RULE_LABEL).sort((a, b) => a[1].localeCompare(b[1]))} />
        <Select label="Source" value={params.get("source")} onChange={(v) => set({ source: v })}
          options={[["portal", "Portal"], ["batch", "Batch"]]} />
        <div>
          <span className="field-label">Date</span>
          <div className="flex gap-1">
            <input type="date" aria-label="From date" className="field px-2 py-1.5 text-sm" value={params.get("date_from") ?? ""} onChange={(e) => set({ date_from: e.target.value })} />
            <input type="date" aria-label="To date" className="field px-2 py-1.5 text-sm" value={params.get("date_to") ?? ""} onChange={(e) => set({ date_to: e.target.value })} />
          </div>
        </div>
        <div>
          <span className="field-label">Amount (USD)</span>
          <div className="flex gap-1">
            <AmountInput label="Minimum amount" value={params.get("amount_min")} onChange={(v) => set({ amount_min: v })} placeholder="Min" />
            <AmountInput label="Maximum amount" value={params.get("amount_max")} onChange={(v) => set({ amount_max: v })} placeholder="Max" />
          </div>
        </div>
      </div>

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {activeFilters.map((k) => (
            <button key={k} onClick={() => set({ [k]: "" })} className="inline-flex items-center gap-1 rounded-full bg-sunk px-2.5 py-0.5 text-ink-2 hover:text-ink">
              {chipLabel(k, params.get(k)!)} <X size={12} aria-label="Remove filter" />
            </button>
          ))}
          <button className="text-muted underline hover:text-ink" onClick={() => setRaw(new URLSearchParams(), { replace: true })}>Clear all</button>
        </div>
      )}

      {loading && !data ? <Loading /> : error ? <ErrorState message={error} onRetry={refresh} /> : !data || data.rows.length === 0 ? (
        <Empty title="No expenses match">Try another filter or clear the search.</Empty>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="table-head">ID</th><Th k="employee">Employee</Th><Th k="date">Date</Th>
                <th className="table-head">Merchant</th><th className="table-head">Category</th>
                <Th k="amount" right>Amount</Th><th className="table-head">Decision</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((e) => (
                <tr key={e.id} className="hover:bg-sunk/60">
                  <td className="table-cell whitespace-nowrap">
                    <Link to={`/finance/expenses/${e.id}`} className="font-medium hover:underline">{e.id}</Link>
                    {e.external_id && <div className="text-xs text-muted">{e.external_id}</div>}
                  </td>
                  <td className="table-cell">{e.employee}</td>
                  <td className="table-cell whitespace-nowrap text-ink-2">{day(e.raw.date)}</td>
                  <td className="table-cell">{e.raw.merchant}</td>
                  <td className="table-cell text-ink-2">
                    {e.latest?.category ? categoryLabel(e.latest.category) : e.raw.category ?? ""}
                    {e.latest?.category_mapped_from && <div className="text-xs text-muted">entered as "{e.latest.category_mapped_from}"</div>}
                  </td>
                  <td className="table-cell text-right tabular-nums">{amountOf(e.raw, e.latest)}</td>
                  <td className="table-cell">
                    <div className="flex items-center gap-1.5">
                      <StatusPill status={e.status} />
                      {e.latest?.suspected_manipulation && <ShieldAlert size={15} className="text-reject" aria-label="Manipulation attempt" />}
                      {e.decided_by === "human" && <span className="text-xs text-muted">by Finance</span>}
                      {e.post_status && !["sent", "superseded"].includes(e.post_status) && (
                        <TriangleAlert size={14} className="text-reject" aria-label={`Delivery ${e.post_status}`} />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="text-muted">
          {total === 0 ? "No expenses" : `${(page - 1) * PAGE + 1}–${Math.min(page * PAGE, total)} of ${total} expenses`}
        </p>
        {pages > 1 && (
          <div className="flex items-center gap-2">
            <button className="btn-quiet py-1" disabled={page <= 1} onClick={() => set({ page: String(page - 1) })}>Previous</button>
            <span className="tabular-nums text-ink-2">Page {page} of {pages}</span>
            <button className="btn-quiet py-1" disabled={page >= pages} onClick={() => set({ page: String(page + 1) })}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}

function chipLabel(k: string, v: string) {
  switch (k) {
    case "status": return `Status: ${STATUS.find((s) => s.key === v)?.label ?? v}`;
    case "manipulation": return "Manipulation";
    case "delivery": return "Delivery problems";
    case "rule": return `Rule: ${RULE_LABEL[v] ?? v}`;
    case "amount_min": return `Over $${v}`;
    case "amount_max": return `Under $${v}`;
    case "date_from": return `From ${day(v)}`;
    case "date_to": return `To ${day(v)}`;
    case "category": return categoryLabel(v);
    case "q": return `"${v}"`;
    default: return v;
  }
}

function Select({ label, value, onChange, options }: { label: string; value: string | null; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label>
      <span className="field-label">{label}</span>
      <select className="field py-1.5 text-sm" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">Any</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

/** Applies on blur or Enter, so typing "500" isn't three requests; ignores anything that isn't a number. */
function AmountInput({ label, value, onChange, placeholder }: { label: string; value: string | null; onChange: (v: string) => void; placeholder: string }) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => setV(value ?? ""), [value]);
  const apply = () => { const t = v.trim(); if (t === "" || Number.isFinite(Number(t))) onChange(t); else setV(value ?? ""); };
  return (
    <input aria-label={label} inputMode="decimal" className="field px-2 py-1.5 text-sm" placeholder={placeholder} value={v}
      onChange={(e) => setV(e.target.value)} onBlur={apply} onKeyDown={(e) => e.key === "Enter" && apply()} />
  );
}

function Views({ current, onPick }: { current: string; onPick: (query: string) => void }) {
  const [mine, setMine] = useState<View[]>(loadViews);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const comparable = (q: string) => { const p = new URLSearchParams(q); p.delete("page"); p.sort(); return p.toString(); };
  const isCurrent = (v: View) => comparable(v.query) === comparable(current);

  const save = () => {
    const n = name.trim();
    if (!n) return;
    const next = [...mine.filter((v) => v.name !== n), { name: n, query: comparable(current) }];
    setMine(next); saveViews(next); setNaming(false); setName("");
  };
  const remove = (n: string) => { const next = mine.filter((v) => v.name !== n); setMine(next); saveViews(next); };
  const chip = (on: boolean) => `rounded px-2.5 py-1 text-sm ${on ? "bg-ink text-paper" : "bg-sunk text-ink-2 hover:text-ink"}`;

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Saved views">
      <Bookmark size={15} className="text-muted" aria-hidden />
      {PRESETS.map((v) => <button key={v.name} className={chip(isCurrent(v))} onClick={() => onPick(v.query)}>{v.name}</button>)}
      {mine.map((v) => (
        <span key={v.name} className={`inline-flex items-center gap-1 ${chip(isCurrent(v))}`}>
          <button onClick={() => onPick(v.query)}>{v.name}</button>
          <button onClick={() => remove(v.name)} aria-label={`Delete view ${v.name}`}><X size={12} aria-hidden /></button>
        </span>
      ))}
      {naming ? (
        <form className="flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <input autoFocus className="field w-40 py-1 text-sm" placeholder="Name this view" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn-quiet py-1 text-sm" type="submit">Save</button>
          <button className="text-sm text-muted hover:text-ink" type="button" onClick={() => setNaming(false)}>Cancel</button>
        </form>
      ) : (
        comparable(current) !== comparable("") && !PRESETS.concat(mine).some(isCurrent) && (
          <button className="text-sm text-muted underline hover:text-ink" onClick={() => setNaming(true)}>Save this view</button>
        )
      )}
    </div>
  );
}
