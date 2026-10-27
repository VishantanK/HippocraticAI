import { CheckCircle2, RotateCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState, Loading } from "../../components/States";
import { StatusPill } from "../../components/StatusPill";
import { useToast } from "../../components/Toast";
import { api } from "../../lib/api";
import type { Delivery } from "../../lib/types";
import { useData } from "../../lib/useData";

/** Decisions that haven't reached the payments system, with a way to push them again. */
export default function DeliveryPage() {
  const { data, error, loading, refresh } = useData(api.deliveries, [],
    (e) => e.type === "decision" || e.type === "delivery");
  const [busy, setBusy] = useState<string | null>(null);
  const toast = useToast();

  async function run(key: string, fn: () => Promise<string>) {
    setBusy(key);
    try { toast(await fn()); } catch (err) { toast((err as Error).message, "error"); }
    finally { setBusy(null); refresh(); }
  }

  const retryOne = (d: Delivery) => run(`${d.expense_id}:${d.revision}`, async () => {
    const r = await api.retryDelivery(d.expense_id, d.revision);
    return r.post_status === "sent" ? `${d.expense_id} delivered.` : `${d.expense_id} still couldn't be delivered.`;
  });
  const retryAll = () => run("all", async () => {
    const r = await api.retryAllDeliveries();
    return r.failed ? `${r.sent} delivered, ${r.failed} still failing.` : `${r.sent} delivered.`;
  });

  if (loading && !data) return <Loading label="Loading deliveries" />;
  if (error || !data) return <ErrorState message={error ?? "No data"} onRetry={refresh} />;
  const dead = data.filter((d) => d.post_status === "dead").length;

  return (
    <div className="max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Delivery to payments</h1>
          <p className="mt-1 text-ink-2">
            Decisions the payments system hasn't received yet. Failed ones retry on their own;
            ones that gave up after 8 attempts wait for you.
          </p>
        </div>
        {data.length > 0 && (
          <button className="btn-primary" disabled={!!busy} onClick={retryAll}>
            <RotateCw size={15} className={busy === "all" ? "animate-spin" : ""} aria-hidden />
            {busy === "all" ? "Retrying…" : "Retry all now"}
          </button>
        )}
      </header>

      {data.length === 0 ? (
        <div className="flex items-center gap-3 rounded-lg border border-line bg-panel px-5 py-6">
          <CheckCircle2 className="text-approve" aria-hidden />
          <p>Every decision has been delivered. Nothing to do.</p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted">{data.length} undelivered{dead ? `, ${dead} gave up` : ""}.</p>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="table-head">Expense</th><th className="table-head">Decision</th>
                  <th className="table-head">State</th><th className="table-head">Last error</th>
                  <th className="table-head text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d) => {
                  const key = `${d.expense_id}:${d.revision}`;
                  return (
                    <tr key={key}>
                      <td className="table-cell whitespace-nowrap">
                        <Link to={`/finance/expenses/${d.expense_id}`} className="font-medium hover:underline">{d.expense_id}</Link>
                        <div className="text-xs text-muted">{d.employee ?? "Unknown"}, revision {d.revision}</div>
                      </td>
                      <td className="table-cell"><StatusPill status={d.decision} /></td>
                      <td className="table-cell whitespace-nowrap">
                        <span className={d.post_status === "dead" ? "font-semibold text-reject" : "text-flag"}>
                          {d.post_status === "dead" ? "Gave up" : "Retrying"}
                        </span>
                        <div className="text-xs text-muted">
                          {d.post_attempts} attempt{d.post_attempts === 1 ? "" : "s"}
                          {d.post_status === "failed" && d.next_attempt_at ? `, next try at ${new Date(d.next_attempt_at).toLocaleTimeString()}` : ""}
                        </div>
                      </td>
                      <td className="table-cell max-w-xs break-words text-ink-2">{d.last_error ?? "None recorded"}</td>
                      <td className="table-cell text-right">
                        <button className="btn-quiet py-1" disabled={!!busy} onClick={() => retryOne(d)}>
                          {busy === key ? "Retrying…" : "Retry now"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
