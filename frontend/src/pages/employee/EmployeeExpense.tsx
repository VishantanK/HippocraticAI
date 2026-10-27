import { ArrowLeft, Pencil } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AnswerForm } from "../../components/AnswerForm";
import { ExpenseForm, toInput } from "../../components/ExpenseForm";
import { Stamp } from "../../components/Stamp";
import { ErrorState, Loading } from "../../components/States";
import { Timeline } from "../../components/Timeline";
import { useToast } from "../../components/Toast";
import { api } from "../../lib/api";
import { amountOf, day } from "../../lib/format";
import type { ExpenseDetail } from "../../lib/types";
import { clearDraft } from "../../lib/draft";
import { useData } from "../../lib/useData";

function headline(e: ExpenseDetail, hasQuestion: boolean) {
  switch (e.status) {
    case "approve": return ["Approved.", "Nothing else to do. It will be reimbursed."];
    case "reject": return ["Not approved.", "It's outside the expense policy for the reasons below. If a detail was wrong, edit it and it will be checked again."];
    case "flag": return hasQuestion
      ? ["Finance needs one thing from you.", "Answer below and it will be checked again straight away."]
      : ["With Finance for review.", "A person will look at it. You'll see the decision here."];
    case "error": return ["The check didn't finish.", "Finance has been told and will review it."];
    default: return ["Checking against policy…", "This usually takes a few seconds."];
  }
}

export default function EmployeeExpense() {
  const { id = "" } = useParams();
  const { data: e, error, loading, refresh } = useData(() => api.get(id), [id], (ev) => ev.expense_id === id);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  // Animate the stamp only when a new decision lands while the page is open.
  const seenRevision = useRef<number | null>(null);
  const revision = e?.decisions.at(-1)?.revision ?? null;
  const land = seenRevision.current !== null && revision !== seenRevision.current;
  useEffect(() => { if (revision !== null) seenRevision.current = revision; }, [revision]);

  if (loading && !e) return <Loading label="Loading expense" />;
  if (error || !e) return <ErrorState message={error ?? "Not found"} onRetry={refresh} />;

  const latest = e.decisions.at(-1)?.payload ?? null;
  const open = e.followups.find((f) => f.status === "open");
  const showQuestion = e.status === "flag" && !!open && latest?.decided_by === "system";
  const [title, sub] = headline(e, showQuestion);
  const canEdit = e.source === "portal" && e.status !== "checking";

  return (
    <div className="space-y-8">
      <Link to="/employee" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink"><ArrowLeft size={15} aria-hidden />My expenses</Link>

      <section className="rounded-lg border border-line bg-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <p className="text-sm text-muted">{e.raw.merchant || "Unnamed expense"}, {day(e.raw.date)}</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight">{amountOf(e.raw, latest)}</p>
            <h1 className="mt-5 text-xl font-semibold">{title}</h1>
            <p className="mt-1 max-w-prose text-ink-2">{sub}</p>
          </div>
          <Stamp status={e.status} land={land} />
        </div>

        {latest && e.status !== "checking" && e.status !== "approve" && (
          <ul className="mt-5 space-y-1.5 border-t border-line pt-4 text-sm">
            {latest.reasons.map((r, i) => <li key={i} className="flex gap-2"><span className="text-muted" aria-hidden>•</span>{r.detail}</li>)}
          </ul>
        )}

        {showQuestion && open && (
          <div className="mt-6 rounded-lg border border-flag/40 bg-flag-tint p-5">
            <p className="text-sm font-semibold text-flag">Question from Finance</p>
            <p className="mt-1 max-w-prose">{open.question}</p>
            <AnswerForm expenseId={e.id} reasons={latest?.reasons ?? []} onSent={refresh} />
          </div>
        )}
      </section>

      <section className="rounded-lg border border-line bg-panel p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="section-title">Details</h2>
          {canEdit && !editing && <button className="btn-quiet" onClick={() => setEditing(true)}><Pencil size={14} aria-hidden />Edit details</button>}
        </div>
        {editing ? (
          <>
            <ExpenseForm
              initial={toInput(e.raw, e.employee ?? "")}
              submitLabel="Save and check again"
              busy={busy}
              draftKey={`edit:${e.id}:${e.version}`}
              onSubmit={async (v) => {
                setBusy(true);
                try {
                  await api.update(e.id, { ...v, employee: e.employee });
                  clearDraft(`edit:${e.id}:${e.version}`);
                  toast("Saved. Checking again."); setEditing(false); refresh();
                }
                catch (err) { toast((err as Error).message, "error"); }
                finally { setBusy(false); }
              }}
            />
            <button className="btn-quiet mt-3" onClick={() => { clearDraft(`edit:${e.id}:${e.version}`); setEditing(false); }}>Cancel</button>
          </>
        ) : (
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
            {([["Category", e.raw.category || "None"], ["Merchant", e.raw.merchant || "None"], ["Amount as entered", String(e.raw.amount ?? "")],
               ["Receipt", e.raw.receipt ? "Yes" : "No"], ["Business purpose", e.raw.memo || "None"], ["Approval code", e.raw.approval_code || "None"]] as const)
              .map(([k, v]) => (
                <div key={k}><dt className="text-muted">{k}</dt><dd className="mt-0.5 break-words">{v}</dd></div>
              ))}
          </dl>
        )}
        {e.source === "batch" && <p className="mt-4 text-xs text-muted">Imported in a batch, so it can't be edited here.</p>}
      </section>

      {e.decisions.length > 0 && (
        <section>
          <h2 className="section-title mb-3">History</h2>
          <Timeline expense={e} />
        </section>
      )}
    </div>
  );
}
