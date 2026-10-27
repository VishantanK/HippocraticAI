import { Paperclip } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { clearDraft, loadDraft, newActionKey, saveDraft, useUnsavedWarning } from "../lib/draft";
import { answerFieldsFor, CATEGORIES } from "../lib/format";
import type { Reason } from "../lib/types";
import { useToast } from "./Toast";

/** Reply to Finance's question. Shows only the fields the open gaps need, plus a note. */
export function AnswerForm({ expenseId, reasons, onSent }: { expenseId: string; reasons: Reason[]; onSent: () => void }) {
  const need = answerFieldsFor(reasons.map((r) => r.rule));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const toast = useToast();
  const draftKey = `answer:${expenseId}`;
  const [draft] = useState(() => loadDraft<Record<string, string>>(draftKey) ?? {});
  const [dirty, setDirty] = useState(Object.values(draft).some(Boolean));
  const actionKey = useRef(newActionKey()); // same key if the user presses Send again after a timeout
  useUnsavedWarning(dirty && !busy);

  function remember(e: FormEvent<HTMLFormElement>) {
    const values: Record<string, string> = {};
    new FormData(e.currentTarget).forEach((v, k) => { if (typeof v === "string") values[k] = v; });
    saveDraft(draftKey, values);
    setDirty(Object.values(values).some((v) => v.trim()) || !!fileName);
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const hasContent = [...form.entries()].some(([, v]) => (typeof v === "string" ? v.trim() : (v as File).size > 0));
    if (!hasContent) return setError("Add a reply or fill in one of the fields.");
    setBusy(true);
    setError(null);
    try {
      await api.answer(expenseId, form, actionKey.current);
      clearDraft(draftKey);
      setDirty(false);
      actionKey.current = newActionKey();
      toast("Reply sent. Checking again.");
      onSent();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} onInput={remember} className="mt-4 space-y-4">
      {need.receipt && (
        <div>
          <span className="field-label">Receipt</span>
          <label className="btn-quiet cursor-pointer">
            <Paperclip size={15} aria-hidden /> {fileName || "Attach receipt"}
            <input type="file" name="receipt_file" accept="image/*,.pdf" className="sr-only" onChange={(e) => setFileName(e.target.files?.[0]?.name ?? "")} />
          </label>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {need.approvalCode && (
          <div>
            <label className="field-label" htmlFor="a-code">Approval code</label>
            <input id="a-code" name="approval_code" defaultValue={draft.approval_code} className="field" placeholder="SW-1234" />
          </div>
        )}
        {need.category && (
          <div>
            <label className="field-label" htmlFor="a-cat">Category</label>
            <select id="a-cat" name="category" className="field" defaultValue={draft.category ?? ""}>
              <option value="">Choose…</option>
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
        )}
        {need.amount && (
          <div>
            <label className="field-label" htmlFor="a-amount">Amount in USD, as charged</label>
            <input id="a-amount" name="amount" defaultValue={draft.amount} inputMode="decimal" className="field" placeholder="70.20" />
          </div>
        )}
        {need.merchant && (
          <div>
            <label className="field-label" htmlFor="a-merchant">Merchant</label>
            <input id="a-merchant" name="merchant" defaultValue={draft.merchant} className="field" />
          </div>
        )}
      </div>
      <div>
        <label className="field-label" htmlFor="a-text">Reply to Finance</label>
        <textarea id="a-text" name="text" rows={3} defaultValue={draft.text} className="field" placeholder="Anything that answers the question" />
      </div>
      {error && <p className="text-sm text-reject">{error}</p>}
      <button className="btn-primary" disabled={busy}>{busy ? "Sending…" : "Send reply"}</button>
    </form>
  );
}
