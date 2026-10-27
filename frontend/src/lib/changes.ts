import type { Answer, DecisionRow, ExpenseDetail, RawExpense } from "./types";

export interface FieldChange { field: string; from: string; to: string }

export interface Changes {
  before: DecisionRow;
  after: DecisionRow;
  fields: FieldChange[];
  answers: Answer[];
  missingHistory: boolean; // the earlier version predates version history
}

const FIELDS: [keyof RawExpense, string][] = [
  ["date", "Date"], ["category", "Category"], ["merchant", "Merchant"], ["amount", "Amount"],
  ["memo", "Business purpose"], ["receipt", "Receipt"], ["approval_code", "Approval code"],
];

const show = (v: unknown) =>
  v === null || v === undefined || v === "" ? "None" : v === true ? "Yes" : v === false ? "No" : String(v);

/** What changed between the last two decisions: edited fields and replies in between. Null if nothing did. */
export function changesSincePrevious(e: ExpenseDetail): Changes | null {
  if (e.decisions.length < 2) return null;
  const before = e.decisions.at(-2)!;
  const after = e.decisions.at(-1)!;
  const raw = (v: number) => e.versions?.find((x) => x.version === v)?.raw;
  const from = raw(before.expense_version);
  const to = raw(after.expense_version);
  const fields = from && to
    ? FIELDS.filter(([k]) => show(from[k]) !== show(to[k])).map(([k, label]) => ({ field: label, from: show(from[k]), to: show(to[k]) }))
    : [];
  const answers = e.answers.filter((a) => a.at > before.decided_at && a.at <= after.decided_at);
  const missingHistory = before.expense_version !== after.expense_version && (!from || !to);
  if (!fields.length && !answers.length && !missingHistory) return null;
  return { before, after, fields, answers, missingHistory };
}
