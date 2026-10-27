import { MessageSquareReply, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { IdentityPicker } from "../../components/IdentityPicker";
import { Empty, ErrorState, Loading } from "../../components/States";
import { StatusPill } from "../../components/StatusPill";
import { api } from "../../lib/api";
import { amountOf, day } from "../../lib/format";
import { useIdentity } from "../../lib/identity";
import type { ExpenseSummary } from "../../lib/types";
import { useData } from "../../lib/useData";

const waitingOnMe = (e: ExpenseSummary) => e.status === "flag" && !!e.latest?.question && e.latest.decided_by === "system";

export default function EmployeeHome() {
  const [me] = useIdentity();
  if (!me) {
    return (
      <section className="max-w-lg">
        <h1 className="text-2xl font-semibold tracking-tight">Who's submitting?</h1>
        <p className="mb-6 mt-2 text-ink-2">Enter your name to see your expenses. There's no sign-in in this demo.</p>
        <IdentityPicker />
      </section>
    );
  }
  return <Mine me={me} />;
}

function Mine({ me }: { me: string }) {
  const { data, error, loading, refresh } = useData(() => api.list({ employee: me }), [me]);
  if (loading && !data) return <Loading label="Loading your expenses" />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  const rows = data ?? [];
  const action = rows.filter(waitingOnMe);
  const counts = { approve: 0, flag: 0, reject: 0, checking: 0 } as Record<string, number>;
  rows.forEach((r) => { counts[r.status ?? "checking"] = (counts[r.status ?? "checking"] ?? 0) + 1; });

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{me.split(" ")[0]}'s expenses</h1>
          <p className="mt-1 text-ink-2">
            {rows.length === 0 ? "Nothing submitted yet." :
              `${counts.approve} approved, ${counts.flag} need info, ${counts.reject} rejected${counts.checking ? `, ${counts.checking} being checked` : ""}.`}
          </p>
        </div>
        <Link to="/employee/new" className="btn-primary"><Plus size={16} aria-hidden />New expense</Link>
      </div>

      {action.length > 0 && (
        <section aria-labelledby="action-title">
          <h2 id="action-title" className="section-title mb-3">Finance has a question</h2>
          <ul className="divide-y divide-line overflow-hidden rounded-lg border border-flag/40 bg-flag-tint">
            {action.map((e) => (
              <li key={e.id}>
                <Link to={`/employee/expenses/${e.id}`} className="flex items-start gap-3 px-4 py-3 hover:bg-flag/10">
                  <MessageSquareReply size={18} className="mt-0.5 shrink-0 text-flag" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{e.raw.merchant || "Unnamed expense"}, {amountOf(e.raw, e.latest)} on {day(e.raw.date)}</p>
                    <p className="line-clamp-2 text-sm text-ink-2">{e.latest?.question}</p>
                  </div>
                  <span className="shrink-0 text-sm font-semibold text-flag">Reply</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="all-title">
        <h2 id="all-title" className="section-title mb-3">All expenses</h2>
        {rows.length === 0 ? (
          <Empty title="No expenses yet">
            <Link to="/employee/new" className="font-semibold text-flag underline">Submit your first expense</Link> or upload a file.
          </Empty>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-sm">
              <thead>
                <tr><th className="table-head">Date</th><th className="table-head">Merchant</th><th className="table-head">Category</th><th className="table-head text-right">Amount</th><th className="table-head">Status</th></tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id} className="hover:bg-sunk/60">
                    <td className="table-cell whitespace-nowrap text-ink-2">{day(e.raw.date)}</td>
                    <td className="table-cell"><Link to={`/employee/expenses/${e.id}`} className="font-medium hover:underline">{e.raw.merchant || "Unnamed"}</Link></td>
                    <td className="table-cell text-ink-2">{e.raw.category || "None"}</td>
                    <td className="table-cell text-right tabular-nums">{amountOf(e.raw, e.latest)}</td>
                    <td className="table-cell"><StatusPill status={e.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
