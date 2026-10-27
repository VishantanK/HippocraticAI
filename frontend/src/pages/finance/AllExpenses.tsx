import { ArrowDown, ArrowUp, Search, ShieldAlert, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Empty, ErrorState, Loading } from "../../components/States";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api";
import { amountOf, day } from "../../lib/format";
import type { ExpenseSummary } from "../../lib/types";
import { useData } from "../../lib/useData";

const FILTERS = [
  { key: "", label: "All" },
  { key: "flag", label: "Needs info" },
  { key: "approve", label: "Approved" },
  { key: "reject", label: "Rejected" },
  { key: "checking", label: "Checking" },
  { key: "manipulation", label: "Manipulation" },
] as const;

type SortKey = "date" | "amount" | "employee" | "updated";

const sortValue = (e: ExpenseSummary, k: SortKey): string | number => {
  if (k === "amount") return e.latest?.amount ?? -1;
  if (k === "employee") return (e.employee ?? "").toLowerCase();
  if (k === "date") return e.raw.date ?? "";
  return e.updated_at;
};

export default function AllExpenses() {
  const [params, setParams] = useSearchParams();
  const filter = params.get("filter") ?? "";
  const source = params.get("source") ?? "";
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "updated", dir: -1 });
  const { data, error, loading, refresh } = useData(() => api.list(), []);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? [])
      .filter((e) => !filter || (filter === "manipulation" ? e.latest?.suspected_manipulation : (e.status ?? "checking") === filter))
      .filter((e) => !source || e.source === source)
      .filter((e) => !needle || [e.id, e.external_id, e.employee, e.raw.merchant, e.raw.category].join(" ").toLowerCase().includes(needle))
      .sort((a, b) => (sortValue(a, sort.key) > sortValue(b, sort.key) ? 1 : -1) * sort.dir);
  }, [data, filter, source, q, sort]);

  const setParam = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  const Th = ({ k, children, right = false }: { k: SortKey; children: string; right?: boolean }) => (
    <th className={`table-head ${right ? "text-right" : ""}`} aria-sort={sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button className="inline-flex items-center gap-1 hover:text-ink" onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? (-s.dir as 1 | -1) : -1 }))}>
        {children}
        {sort.key === k && (sort.dir === 1 ? <ArrowUp size={12} aria-hidden /> : <ArrowDown size={12} aria-hidden />)}
      </button>
    </th>
  );

  return (
    <div className="max-w-6xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">All expenses</h1>
        <p className="mt-1 text-ink-2">From the portal and batch imports, with the latest decision for each.</p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setParam("filter", f.key)}
              className={`rounded-full border px-3 py-1 text-sm ${filter === f.key ? "border-ink bg-ink text-paper" : "border-line bg-panel text-ink-2 hover:border-ink-2"}`}>
              {f.label}
            </button>
          ))}
        </div>
        <select className="field w-auto py-1.5 text-sm" value={source} onChange={(e) => setParam("source", e.target.value)} aria-label="Source">
          <option value="">Portal and batch</option><option value="portal">Portal only</option><option value="batch">Batch only</option>
        </select>
        <label className="relative ml-auto">
          <Search size={15} className="absolute left-2.5 top-2.5 text-muted" aria-hidden />
          <span className="sr-only">Search</span>
          <input className="field w-64 py-1.5 pl-8 text-sm" placeholder="Employee, merchant or ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
      </div>

      {loading && !data ? <Loading /> : error ? <ErrorState message={error} onRetry={refresh} /> : rows.length === 0 ? (
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
              {rows.map((e) => (
                <tr key={e.id} className="hover:bg-sunk/60">
                  <td className="table-cell whitespace-nowrap">
                    <Link to={`/finance/expenses/${e.id}`} className="font-medium hover:underline">{e.id}</Link>
                    {e.external_id && <div className="text-xs text-muted">{e.external_id}</div>}
                  </td>
                  <td className="table-cell">{e.employee}</td>
                  <td className="table-cell whitespace-nowrap text-ink-2">{day(e.raw.date)}</td>
                  <td className="table-cell">{e.raw.merchant}</td>
                  <td className="table-cell text-ink-2">
                    {e.latest?.category === "GroundTransport" ? "Ground transport" : e.latest?.category ?? e.raw.category ?? ""}
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
      <p className="text-xs text-muted">{rows.length} of {data?.length ?? 0} expenses</p>
    </div>
  );
}
