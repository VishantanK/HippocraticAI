import type { Decision, Payload, RawExpense, Status } from "./types";

const USD = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

/** All amounts in the system are USD. */
export function money(amount: number | null | undefined) {
  return amount == null ? "" : USD.format(amount);
}

/** Prefer the parsed USD amount from the decision; fall back to what was typed (e.g. "€65.00"). */
export function amountOf(raw: RawExpense, p?: Payload | null) {
  if (p && p.amount != null) return money(p.amount);
  return raw.amount == null ? "" : String(raw.amount);
}

export function day(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function ago(iso: string | null | undefined) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export const STATUS_LABEL: Record<string, string> = {
  approve: "Approved", reject: "Rejected", flag: "Needs info", checking: "Checking", error: "Check failed",
};

export const DECISIONS: Decision[] = ["approve", "flag", "reject"];

export function statusLabel(s: Status) {
  return STATUS_LABEL[s ?? "checking"] ?? "Pending";
}

/** Plain-language names for policy rule codes (Finance sees the code too). */
export const RULE_LABEL: Record<string, string> = {
  within_policy: "Within policy",
  suspected_manipulation: "Manipulation attempt",
  missing_category: "Missing category",
  unknown_category: "Unrecognised category",
  missing_merchant: "Missing merchant",
  invalid_amount: "Unreadable amount",
  non_usd: "Not in USD",
  non_positive_amount: "Zero or negative amount",
  invalid_date: "Unreadable date",
  future_date: "Future date",
  stale_date: "Over 6 months old",
  missing_employee: "Missing employee",
  multi_night_hotel: "Multi-night hotel",
  weekend_meal: "Weekend meal",
  meal_over_cap: "Over meal limit",
  hotel_over_cap: "Over hotel limit",
  entertainment_not_client: "Entertainment without client",
  missing_receipt: "Receipt needed",
  missing_approval_code: "Approval code needed",
  unknown_approval_code: "Approval code not on file",
  possible_split: "Possible split bill",
  possible_duplicate: "Possible duplicate",
  high_amount_review: "Over auto-approval limit",
  llm_unavailable: "Automated check unavailable",
  guard_unavailable: "Safety check unavailable",
  human_review: "Finance decision",
  edited_after_review: "Edited after review",
  check_failed: "Automated check failed",
  possible_manipulation: "Wording needs a look",
};

/** The policy's own categories (what the system maps everything to). */
export const POLICY_CATEGORIES = ["Breakfast", "Lunch", "Dinner", "Hotel", "Office", "Software", "GroundTransport", "Airfare", "Entertainment"];

export const categoryLabel = (c: string) => (c === "GroundTransport" ? "Ground transport" : c);

export const CATEGORIES = ["Breakfast", "Lunch", "Dinner", "Hotel", "Office", "Software", "Uber", "Taxi", "Airfare", "Entertainment"];

/** Which structured answer fields a flag needs, from its reason codes. */
export function answerFieldsFor(rules: string[]) {
  const has = (...r: string[]) => r.some((x) => rules.includes(x));
  return {
    receipt: has("missing_receipt", "high_amount_review"),
    approvalCode: has("missing_approval_code", "unknown_approval_code"),
    category: has("missing_category", "unknown_category"),
    amount: has("non_usd", "invalid_amount", "non_positive_amount"),
    merchant: has("missing_merchant"),
  };
}
