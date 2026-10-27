import { Link } from "react-router-dom";
import { Empty, ErrorState, Loading } from "../../components/States";
import { api } from "../../lib/api";
import { ago, amountOf, day, RULE_LABEL } from "../../lib/format";
import { readyForDecision, waitingOnEmployee } from "../../lib/review";
import type { ExpenseSummary } from "../../lib/types";
import { useData } from "../../lib/useData";

export default function Queue() {
  const { data, error, loading, refresh } = useData(() => api.list(), []);
  if (loading && !data) return <Loading label="Loading queue" />;
  if (error || !data) return <ErrorState message={error ?? "No data"} onRetry={refresh} />;
  const ready = data.filter(readyForDecision);
  const waiting = data.filter(waitingOnEmployee);

  return (
    <div className="max-w-5xl space-y-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Review queue</h1>
        <p className="mt-1 text-ink-2">Expenses the system couldn't decide on its own.</p>
      </header>
      <QueueSection title="Ready for your decision" note="The employee has replied, or only a person can resolve it." rows={ready}
        empty="Nothing needs a decision right now." />
      <QueueSection title="Waiting on the employee" note="A question has been sent. These move up when they reply." rows={waiting}
        empty="No open questions." muted />
    </div>
  );
}

function QueueSection({ title, note, rows, empty, muted = false }: { title: string; note: string; rows: ExpenseSummary[]; empty: string; muted?: boolean }) {
  return (
    <section>
      <div className="mb-3 flex items-baseline gap-3">
        <h2 className="section-title">{title}</h2>
        <span className="text-sm tabular-nums text-muted">{rows.length}</span>
      </div>
      <p className="-mt-2 mb-3 text-sm text-muted">{note}</p>
      {rows.length === 0 ? <Empty title={empty} /> : (
        <ul className={`divide-y divide-line overflow-hidden rounded-lg border border-line bg-panel ${muted ? "opacity-90" : ""}`}>
          {rows.map((e) => (
            <li key={e.id}>
              <Link to={`/finance/expenses/${e.id}`} className="grid gap-2 px-4 py-3 hover:bg-sunk/60 sm:grid-cols-[1fr_auto] sm:items-center">
                <div className="min-w-0">
                  <p className="font-medium">
                    {e.employee ?? "Unknown"} <span className="font-normal text-ink-2">at {e.raw.merchant || "unknown merchant"}, {day(e.raw.date)}</span>
                  </p>
                  <p className="mt-0.5 flex flex-wrap gap-1.5">
                    {(e.latest?.reasons ?? []).map((r, i) => (
                      <span key={i} className="rounded bg-flag-tint px-1.5 py-0.5 text-xs font-medium text-flag">{RULE_LABEL[r.rule] ?? r.rule}</span>
                    ))}
                    {e.answers.length > 0 && <span className="rounded bg-sunk px-1.5 py-0.5 text-xs text-ink-2">Replied {ago(e.answers.at(-1)?.at)}</span>}
                  </p>
                </div>
                <div className="flex items-center gap-4 text-sm sm:justify-end">
                  <span className="font-semibold tabular-nums">{amountOf(e.raw, e.latest)}</span>
                  <span className="w-20 text-right text-xs text-muted">{ago(e.updated_at)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
