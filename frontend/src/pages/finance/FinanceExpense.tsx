import { ArrowLeft, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Stamp } from "../../components/Stamp";
import { ErrorState, Loading } from "../../components/States";
import { Timeline } from "../../components/Timeline";
import { useToast } from "../../components/Toast";
import { api, ApiError } from "../../lib/api";
import { amountOf, day, money, RULE_LABEL } from "../../lib/format";
import type { ExpenseDetail } from "../../lib/types";
import { useData } from "../../lib/useData";

export default function FinanceExpense() {
  const { id = "" } = useParams();
  const { data: e, error, loading, refresh } = useData(() => api.get(id), [id], (ev) => ev.expense_id === id);
  if (loading && !e) return <Loading label="Loading expense" />;
  if (error || !e) return <ErrorState message={error ?? "Not found"} onRetry={refresh} />;

  const last = e.decisions.at(-1);
  const p = last?.payload;

  return (
    <div className="max-w-6xl space-y-6">
      <Link to="/finance/expenses" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink"><ArrowLeft size={15} aria-hidden />All expenses</Link>

      <header className="flex flex-wrap items-start justify-between gap-6 rounded-lg border border-line bg-panel p-6">
        <div>
          <p className="text-sm text-muted">{e.id}{e.external_id ? ` (${e.external_id})` : ""}, {e.source === "batch" ? "batch import" : "portal"}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{e.employee ?? "Unknown employee"}</h1>
          <p className="mt-1 text-lg text-ink-2">{e.raw.merchant || "No merchant"}, {day(e.raw.date)}, <span className="font-semibold tabular-nums text-ink">{amountOf(e.raw, p)}</span></p>
        </div>
        <Stamp status={e.status} />
      </header>

      {p?.suspected_manipulation && (
        <div className="flex items-start gap-3 rounded-lg border border-reject/40 bg-reject-tint px-4 py-3 text-sm">
          <ShieldAlert size={18} className="mt-0.5 shrink-0 text-reject" aria-hidden />
          <p>Text in this expense tried to instruct the reviewer, so it was rejected without applying policy. The evidence is below.</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          {p && (
            <section className="rounded-lg border border-line bg-panel p-5">
              <h2 className="section-title mb-3">Why</h2>
              <ul className="space-y-3">
                {p.reasons.map((r, i) => (
                  <li key={i} className="text-sm">
                    <p className="font-semibold">{RULE_LABEL[r.rule] ?? r.rule} <code className="ml-1 rounded bg-sunk px-1 text-xs font-normal text-muted">{r.rule}</code></p>
                    <p className="mt-0.5 text-ink-2">{r.detail}</p>
                  </li>
                ))}
              </ul>
              {p.question && e.status === "flag" && (
                <div className="mt-4 rounded bg-flag-tint px-3 py-2 text-sm">
                  <p className="font-semibold text-flag">Question sent to the employee</p>
                  <p className="mt-0.5">{p.question}</p>
                </div>
              )}
            </section>
          )}
          <ReadAs e={e} />
          <Checks e={e} />
        </div>

        <div className="space-y-6">
          <Decide e={e} onDone={refresh} />
          <section className="rounded-lg border border-line bg-panel p-5">
            <h2 className="section-title mb-4">History</h2>
            {e.decisions.length ? <Timeline expense={e} showDelivery /> : <p className="text-sm text-muted">Not decided yet.</p>}
          </section>
          {p && (
            <details className="rounded-lg border border-line bg-panel p-5 text-sm">
              <summary className="cursor-pointer font-semibold">Last decision sent to payments</summary>
              <pre className="mt-3 overflow-x-auto rounded bg-sunk p-3 text-xs">{JSON.stringify(p, null, 2)}</pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function ReadAs({ e }: { e: ExpenseDetail }) {
  const n = (e.normalized ?? {}) as Record<string, unknown>;
  const s = (v: unknown) => (v === null || v === undefined || v === "" ? "None" : String(v));
  const rows: [string, unknown, string][] = [
    ["Amount", e.raw.amount, n.amount != null ? money(n.amount as number) : n.foreign_symbol ? "Not in US dollars" : "Unreadable"],
    ["Date", e.raw.date, n.date ? `${day(n.date as string)} (${n.weekday})` : "Unreadable"],
    ["Category", e.raw.category, s(n.category ?? "Unknown")],
    ["Merchant", e.raw.merchant, s(n.merchant)],
    ["Purpose", e.raw.memo, n.is_client ? `Client: ${n.client_name}` : "No client named"],
    ["Receipt", e.raw.receipt, n.receipt ? "Yes" : "No"],
    ["Approval code", e.raw.approval_code, s(n.approval_code)],
  ];
  return (
    <section className="rounded-lg border border-line bg-panel p-5">
      <h2 className="section-title">What was submitted, and how it was read</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><th className="table-head w-32">Field</th><th className="table-head">Submitted</th><th className="table-head">Read as</th></tr></thead>
          <tbody>
            {rows.map(([k, raw, read]) => (
              <tr key={k}><td className="table-cell text-muted">{k}</td><td className="table-cell break-words">{s(raw)}</td><td className="table-cell">{read}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {e.answers.length > 0 && (
        <p className="mt-3 text-xs text-muted">Includes {e.answers.length} follow-up repl{e.answers.length === 1 ? "y" : "ies"} from the employee.</p>
      )}
    </section>
  );
}

function Checks({ e }: { e: ExpenseDetail }) {
  const sig = e.decisions.filter((d) => d.decided_by === "system").at(-1)?.signals;
  if (!sig) return null;
  const screen = sig.guard?.screen;
  const hits = sig.guard?.manipulation ?? [];
  const ex = sig.extract;
  return (
    <section className="rounded-lg border border-line bg-panel p-5 text-sm">
      <h2 className="section-title mb-3">Automated checks</h2>
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <div>
          <dt className="text-muted">Manipulation screen</dt>
          <dd>{screen ? `${screen.detector === "openai_decisions" ? "Decisions API" : screen.detector}, probability ${(screen.probability ?? 0).toFixed(2)}` : "Not run"}</dd>
        </div>
        {ex && <div><dt className="text-muted">Category read</dt><dd>{ex.category} ({Math.round(ex.category_confidence * 100)}% confident)</dd></div>}
        {ex && <div><dt className="text-muted">Client</dt><dd>{ex.is_client && ex.client_name ? ex.client_name : "None named"}</dd></div>}
        {ex?.city && <div><dt className="text-muted">City</dt><dd>{ex.city}</dd></div>}
      </dl>
      {hits.map((h, i) => (
        <p key={i} className="mt-3 rounded bg-reject-tint px-3 py-2"><strong>Flagged text in {h.field}:</strong> "{h.evidence}" <span className="text-muted">({h.detector})</span></p>
      ))}
      {(sig.llm_error || sig.guard?.guard_error) && (
        <p className="mt-3 rounded bg-reject-tint px-3 py-2">A check didn't complete: {sig.llm_error ?? sig.guard?.guard_error}. The expense was flagged instead of approved.</p>
      )}
      {!!sig.guard?.schema_issues?.length && <p className="mt-3 text-muted">Input issues: {sig.guard.schema_issues.join("; ")}</p>}
    </section>
  );
}

function Decide({ e, onDone }: { e: ExpenseDetail; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<"approve" | "reject" | null>(null);
  const [noteError, setNoteError] = useState(false);
  const toast = useToast();
  if (e.status === "checking") {
    return <section className="rounded-lg border border-line bg-panel p-5 text-sm text-muted">Being checked. You can decide once it finishes.</section>;
  }
  const isFlag = e.status === "flag" || e.status === "error";
  const amount = amountOf(e.raw, e.decisions.at(-1)?.payload) || "this expense";
  // Reversing an approve or a reject goes on the record with a reason (the server enforces this too).
  const noteRequired = !isFlag;

  function ask(d: "approve" | "reject") {
    if (noteRequired && !note.trim()) { setNoteError(true); return; }
    setNoteError(false);
    setConfirming(d);
  }

  async function decide(d: "approve" | "reject") {
    setBusy(true);
    try {
      await api.override(e.id, d, note.trim(), e.decisions.at(-1)?.revision ?? 0);
      toast(d === "approve" ? "Approved and sent to payments." : "Rejected and sent to payments.");
      setNote("");
      onDone();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Someone changed it after this page loaded: show the latest and keep the note.
        toast("It changed while you were looking. The latest is shown now; check it and decide again.", "error");
        onDone();
      } else {
        toast((err as Error).message, "error");
      }
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  return (
    <section className={`rounded-lg border p-5 ${isFlag ? "border-flag/50 bg-flag-tint" : "border-line bg-panel"}`}>
      <h2 className="section-title">{isFlag ? "Your decision" : "Change the decision"}</h2>
      <p className="mt-1 text-sm text-ink-2">
        {isFlag ? "This one needs a person. Your decision is final for this version and is sent to payments." : "Overrides the current decision and is sent to payments."}
      </p>
      <label htmlFor="note" className="field-label mt-4">Note for the record{noteRequired ? " (required)" : ""}</label>
      <textarea id="note" rows={2} className="field" placeholder="Why you decided this" value={note}
        aria-invalid={noteError} aria-describedby={noteError ? "note-error" : undefined}
        onChange={(ev) => { setNote(ev.target.value); if (ev.target.value.trim()) setNoteError(false); }} />
      {noteError && <p id="note-error" className="mt-1 text-sm text-reject">Say why you're reversing the automatic decision.</p>}

      {confirming ? (
        <div className="mt-3 rounded border border-line bg-panel p-3 text-sm" role="alertdialog" aria-labelledby="confirm-title">
          <p id="confirm-title" className="font-semibold">
            {confirming === "approve" ? "Approve" : "Reject"} {amount} for {e.employee ?? "this employee"}?
          </p>
          <p className="mt-0.5 text-ink-2">It's sent to payments straight away.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button autoFocus className={confirming === "approve" ? "btn-approve" : "btn-reject"} disabled={busy} onClick={() => decide(confirming)}>
              {busy ? "Sending…" : `Yes, ${confirming}`}
            </button>
            <button className="btn-quiet" disabled={busy} onClick={() => setConfirming(null)}>Back</button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {(isFlag || e.status === "reject") && <button className="btn-approve" onClick={() => ask("approve")}>Approve</button>}
          {(isFlag || e.status === "approve") && <button className="btn-reject" onClick={() => ask("reject")}>Reject</button>}
        </div>
      )}
    </section>
  );
}
