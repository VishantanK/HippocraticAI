import { FileUp } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ExpenseForm, toInput } from "../../components/ExpenseForm";
import { IdentityPicker } from "../../components/IdentityPicker";
import { useToast } from "../../components/Toast";
import { api } from "../../lib/api";
import { parseCsv } from "../../lib/csv";
import { clearDraft, newActionKey } from "../../lib/draft";
import { useIdentity } from "../../lib/identity";

type Tab = "form" | "file";
const COLS = ["date", "merchant", "category", "amount", "memo", "receipt"] as const;

export default function NewExpense() {
  const [me] = useIdentity();
  const [tab, setTab] = useState<Tab>("form");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const toast = useToast();
  // One key per visit to this page: if a send times out and the user presses it again, the
  // server returns the first result instead of creating a second expense.
  const actionKey = useRef(newActionKey());

  if (!me) {
    return (
      <section className="max-w-lg">
        <h1 className="text-2xl font-semibold tracking-tight">Who's submitting?</h1>
        <p className="mb-6 mt-2 text-ink-2">Enter your name before adding an expense.</p>
        <IdentityPicker />
      </section>
    );
  }

  const tabCls = (t: Tab) => `rounded px-3 py-1.5 text-sm font-medium ${tab === t ? "bg-ink text-paper" : "text-ink-2 hover:bg-sunk"}`;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">New expense</h1>
      <p className="mt-1 text-ink-2">It's checked against the expense policy as soon as you send it, usually in a few seconds.</p>
      <div className="mt-6 inline-flex gap-1 rounded-lg border border-line bg-panel p-1" role="tablist">
        <button role="tab" aria-selected={tab === "form"} className={tabCls("form")} onClick={() => setTab("form")}>Enter details</button>
        <button role="tab" aria-selected={tab === "file"} className={tabCls("file")} onClick={() => setTab("file")}>Upload a file</button>
      </div>
      <div className="mt-6 rounded-lg border border-line bg-panel p-6">
        {error && <p className="mb-4 rounded bg-reject-tint px-3 py-2 text-sm text-reject">{error}</p>}
        {tab === "form" ? (
          <ExpenseForm
            initial={toInput(null, me)}
            submitLabel="Send for approval"
            busy={busy}
            draftKey={`new:${me}`}
            onSubmit={async (v) => {
              setBusy(true); setError(null);
              try {
                const e = await api.create({ ...v, employee: me }, actionKey.current);
                clearDraft(`new:${me}`);
                navigate(`/employee/expenses/${e.id}`);
              } catch (err) { setError((err as Error).message); setBusy(false); }
            }}
          />
        ) : (
          <Upload me={me} busy={busy} onUpload={async (file) => {
            setBusy(true); setError(null);
            try {
              const res = await api.upload(file, me, actionKey.current);
              toast(`${res.length} expense${res.length === 1 ? "" : "s"} sent. Decisions will appear as they're checked.`);
              navigate("/employee");
            } catch (err) { setError((err as Error).message); setBusy(false); }
          }} />
        )}
      </div>
    </div>
  );
}

function Upload({ me, busy, onUpload }: { me: string; busy: boolean; onUpload: (f: File) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  async function pick(f: File | undefined) {
    if (!f) return;
    setFile(f); setProblem(null); setRows(null);
    try {
      const text = await f.text();
      const parsed = f.name.toLowerCase().endsWith(".csv") ? parseCsv(text) : [JSON.parse(text)].flat();
      if (!parsed.length) throw new Error("The file has no expenses in it.");
      setRows(parsed as Record<string, unknown>[]);
    } catch (e) {
      setProblem(e instanceof SyntaxError ? "That file isn't valid JSON." : (e as Error).message);
    }
  }

  const others = rows?.filter((r) => r.employee && r.employee !== me).length ?? 0;

  return (
    <div>
      <label
        onDragOver={(e: DragEvent) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e: DragEvent) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center ${over ? "border-flag bg-flag-tint" : "border-line hover:border-ink-2"}`}
      >
        <FileUp className="text-muted" aria-hidden />
        <span className="font-medium">{file ? file.name : "Drop a JSON or CSV file, or click to choose"}</span>
        <span className="text-sm text-muted">CSV columns: date, category, merchant, amount, memo, receipt, approval_code</span>
        <input type="file" accept=".json,.csv" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
      </label>
      {problem && <p className="mt-3 text-sm text-reject">{problem}</p>}
      {rows && (
        <div className="mt-5">
          <p className="mb-2 text-sm text-ink-2">
            {rows.length} expense{rows.length === 1 ? "" : "s"} found. Each one is checked on its own.
            {others > 0 && ` ${others} belong to someone other than ${me}.`}
          </p>
          <div className="max-h-72 overflow-auto rounded border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-panel"><tr>{COLS.map((c) => <th key={c} className="table-head capitalize">{c}</th>)}</tr></thead>
              <tbody>
                {rows.slice(0, 200).map((r, i) => (
                  <tr key={i}>{COLS.map((c) => <td key={c} className="table-cell max-w-[14rem] truncate">{String(r[c] ?? "")}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="btn-primary mt-4" disabled={busy || !file} onClick={() => file && onUpload(file)}>
            {busy ? "Sending…" : `Send ${rows.length} for approval`}
          </button>
        </div>
      )}
    </div>
  );
}
