import { useState, type FormEvent } from "react";
import { CATEGORIES } from "../lib/format";
import type { ExpenseInput, RawExpense } from "../lib/types";

type Errors = Partial<Record<keyof ExpenseInput, string>>;

function validate(v: ExpenseInput): Errors {
  const e: Errors = {};
  if (!v.date) e.date = "Add the date on the receipt.";
  if (v.amount === null || v.amount === "") e.amount = "Add the amount.";
  else if (typeof v.amount === "string" && !/\d/.test(v.amount)) e.amount = "Use a number, like 42.50.";
  if (!v.merchant) e.merchant = "Add where you paid.";
  if (!v.category) e.category = "Pick a category.";
  return e;
}

export function toInput(raw: RawExpense | null, employee: string): ExpenseInput {
  return {
    employee,
    date: raw?.date && /^\d{4}-\d{2}-\d{2}$/.test(raw.date) ? raw.date : raw?.date ?? "",
    category: raw?.category ?? "",
    merchant: raw?.merchant ?? "",
    amount: raw?.amount ?? "",
    memo: raw?.memo ?? "",
    receipt: raw?.receipt === true,
    approval_code: raw?.approval_code ?? "",
  };
}

/** Plain numbers are sent as numbers; anything else (e.g. "€65") is sent as typed for the server to judge. */
function clean(v: ExpenseInput): ExpenseInput {
  const amt = typeof v.amount === "string" ? v.amount.trim() : v.amount;
  return {
    ...v,
    amount: typeof amt === "string" && /^-?\d+(\.\d+)?$/.test(amt) ? Number(amt) : amt,
    approval_code: v.approval_code?.trim() || null,
    memo: v.memo?.trim() ?? "",
  };
}

export function ExpenseForm({
  initial, submitLabel, busy, onSubmit,
}: { initial: ExpenseInput; submitLabel: string; busy?: boolean; onSubmit: (v: ExpenseInput) => void }) {
  const [v, setV] = useState(initial);
  const [errors, setErrors] = useState<Errors>({});
  const set = <K extends keyof ExpenseInput>(k: K, val: ExpenseInput[K]) => setV((p) => ({ ...p, [k]: val }));
  const isSoftware = (v.category ?? "").toLowerCase() === "software";

  function submit(e: FormEvent) {
    e.preventDefault();
    const errs = validate(v);
    setErrors(errs);
    if (Object.keys(errs).length === 0) onSubmit(clean(v));
  }

  const err = (k: keyof ExpenseInput) => errors[k] && <p className="mt-1 text-sm text-reject">{errors[k]}</p>;

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="f-date">Date</label>
          <input id="f-date" type="date" className="field" value={v.date ?? ""} onChange={(e) => set("date", e.target.value)} />
          {err("date")}
        </div>
        <div>
          <label className="field-label" htmlFor="f-amount">Amount</label>
          <input id="f-amount" inputMode="decimal" className="field" placeholder="42.50" value={v.amount ?? ""} onChange={(e) => set("amount", e.target.value)} />
          <p className="mt-1 text-xs text-muted">In US dollars. Paid in another currency? Enter the dollar amount from your card statement.</p>
          {err("amount")}
        </div>
        <div>
          <label className="field-label" htmlFor="f-merchant">Merchant</label>
          <input id="f-merchant" className="field" placeholder="Where you paid" value={v.merchant ?? ""} onChange={(e) => set("merchant", e.target.value)} />
          {err("merchant")}
        </div>
        <div>
          <label className="field-label" htmlFor="f-category">Category</label>
          <input id="f-category" list="categories" className="field" placeholder="Lunch, Hotel, Software…" value={v.category ?? ""} onChange={(e) => set("category", e.target.value)} />
          <datalist id="categories">{CATEGORIES.map((c) => <option key={c} value={c} />)}</datalist>
          {err("category")}
        </div>
      </div>
      <div>
        <label className="field-label" htmlFor="f-memo">Business purpose</label>
        <textarea id="f-memo" rows={2} className="field" placeholder="Dinner with Acme Corp about the renewal" value={v.memo ?? ""} onChange={(e) => set("memo", e.target.value)} />
        <p className="mt-1 text-xs text-muted">Meals with a client have no limit. Name the client company so we can tell.</p>
      </div>
      {isSoftware && (
        <div>
          <label className="field-label" htmlFor="f-code">Software approval code</label>
          <input id="f-code" className="field sm:w-60" placeholder="SW-1234" value={v.approval_code ?? ""} onChange={(e) => set("approval_code", e.target.value)} />
        </div>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--ink))]" checked={v.receipt} onChange={(e) => set("receipt", e.target.checked)} />
        I have the receipt <span className="text-muted">(needed for anything over $25)</span>
      </label>
      <button className="btn-primary" type="submit" disabled={busy}>{busy ? "Sending…" : submitLabel}</button>
    </form>
  );
}
