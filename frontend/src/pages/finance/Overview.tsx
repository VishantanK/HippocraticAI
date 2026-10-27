import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { DecisionMix, SpendByCategory } from "../../components/Charts";
import { ErrorState, Loading } from "../../components/States";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api";
import { ago } from "../../lib/format";
import { useData } from "../../lib/useData";

export default function Overview() {
  const { data: s, error, loading, refresh } = useData(api.stats, [], (e) => e.type === "decision");
  if (loading && !s) return <Loading label="Loading overview" />;
  if (error || !s) return <ErrorState message={error ?? "No data"} onRetry={refresh} />;

  const auto = s.total ? Math.round(((s.by_status.approve ?? 0) + (s.by_status.reject ?? 0)) / s.total * 100) : 0;
  const undelivered = s.post.failed + s.post.dead + s.post.pending;
  const kpis = [
    { label: "Expenses", value: s.total, to: "/finance/expenses" },
    { label: "Decided without a person", value: `${auto}%`, to: "/finance/expenses" },
    { label: "In the review queue", value: (s.by_status.flag ?? 0) + (s.by_status.error ?? 0), to: "/finance/queue" },
    { label: "Waiting on employees", value: s.open_questions, to: "/finance/queue" },
  ];

  return (
    <div className="max-w-6xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-ink-2">Every expense is checked on arrival. Only the review queue needs you.</p>
      </header>

      <dl className="grid grid-cols-2 divide-line overflow-hidden rounded-lg border border-line bg-panel sm:grid-cols-4 sm:divide-x">
        {kpis.map((k) => (
          <Link key={k.label} to={k.to} className="px-5 py-4 hover:bg-sunk/60">
            <dt className="text-sm text-ink-2">{k.label}</dt>
            <dd className="mt-1 text-3xl font-semibold tabular-nums tracking-tight">{k.value}</dd>
          </Link>
        ))}
      </dl>

      {(s.manipulation > 0 || s.post.dead > 0 || s.post.failed > 0) && (
        <div className="space-y-2">
          {s.manipulation > 0 && (
            <Link to="/finance/expenses?manipulation=true" className="flex items-center gap-3 rounded-lg border border-reject/40 bg-reject-tint px-4 py-3 text-sm hover:border-reject">
              <ShieldAlert size={18} className="text-reject" aria-hidden />
              <span><strong>{s.manipulation} expense{s.manipulation === 1 ? "" : "s"}</strong> tried to instruct the reviewer and {s.manipulation === 1 ? "was" : "were"} rejected automatically.</span>
              <span className="ml-auto font-semibold text-reject">Review</span>
            </Link>
          )}
          {(s.post.dead > 0 || s.post.failed > 0) && (
            <div className="flex items-center gap-3 rounded-lg border border-line bg-panel px-4 py-3 text-sm">
              <AlertTriangle size={18} className="text-reject" aria-hidden />
              <span>
                {s.post.failed > 0 && <>{s.post.failed} decision{s.post.failed === 1 ? " is" : "s are"} being retried to the payments system. </>}
                {s.post.dead > 0 && <strong>{s.post.dead} could not be delivered after 8 attempts.</strong>}
              </span>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <section className="rounded-lg border border-line bg-panel p-5">
            <h2 className="section-title">Current decisions</h2>
            <p className="mb-5 text-sm text-muted">Latest decision for each of {s.total} expenses.</p>
            <DecisionMix counts={s.by_status} />
          </section>
          <section className="rounded-lg border border-line bg-panel p-5">
            <h2 className="section-title">Spend by category</h2>
            <p className="mb-5 text-sm text-muted">USD claimed, by current decision. Claims not in dollars appear once the employee gives the USD amount.</p>
            <SpendByCategory rows={s.by_category} />
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-lg border border-line bg-panel p-5">
            <h2 className="section-title mb-3">Recent decisions</h2>
            <ol className="space-y-3">
              {s.recent.map((r) => (
                <li key={`${r.expense_id}:${r.revision}`} className="flex items-start gap-3 text-sm">
                  <StatusPill status={r.decision} />
                  <Link to={`/finance/expenses/${r.expense_id}`} className="min-w-0 flex-1 hover:underline">
                    <span className="font-medium">{r.employee ?? "Unknown"}</span>
                    <span className="text-muted"> {r.expense_id}{r.revision > 1 ? `, revision ${r.revision}` : ""}{r.decided_by === "human" ? ", by Finance" : ""}</span>
                  </Link>
                  <span className="shrink-0 text-xs text-muted">{ago(r.decided_at)}</span>
                </li>
              ))}
            </ol>
          </section>
          <section className="rounded-lg border border-line bg-panel p-5 text-sm">
            <h2 className="section-title mb-3">Delivery to payments</h2>
            <p className="text-ink-2">
              {s.post.sent} delivered{undelivered ? `, ${undelivered} not yet` : ", none outstanding"}.
              {s.post.dead === 0 && s.post.failed === 0 && " Everything is up to date."}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
