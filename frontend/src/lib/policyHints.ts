import { money } from "./format";
import type { ExpenseInput, Policy } from "./types";

/**
 * Advisory hints shown while the employee fills in the form. They mirror the policy numbers
 * from /api/policy but never decide anything: the server's check is the only decision, and
 * things the LLM reads (is a client named? which city?) are only guessed at here.
 */
export interface Hint { key: string; tone: "reject" | "flag"; text: string }

const MEALS = ["Breakfast", "Lunch", "Dinner"];

/** "$1,250.00", "USD 40", "40" -> number; another currency symbol or no digits -> null. */
export function usdAmount(amount: ExpenseInput["amount"]): number | null {
  if (typeof amount === "number") return amount;
  const s = (amount ?? "").trim();
  if (!s || /[^\s\d.,$a-z-]/i.test(s.replace(/US\$|USD/gi, ""))) return null;
  const n = Number(s.replace(/US\$|USD|\$|,|\s/gi, ""));
  return Number.isFinite(n) ? n : null;
}

/** True when the amount carries a currency symbol other than the dollar sign (€, £, ¥, ₹…). */
export function looksForeign(amount: ExpenseInput["amount"]): boolean {
  return typeof amount === "string" && /\p{Sc}/u.test(amount.replace(/\$/g, ""));
}

function monthsBefore(iso: string, months: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1 - months, 1));
  const last = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0)).getUTCDate();
  t.setUTCDate(Math.min(d, last));
  return t.toISOString().slice(0, 10);
}

export function hintsFor(v: ExpenseInput, p: Policy): Hint[] {
  const out: Hint[] = [];
  const category = p.categories.find((c) => c.toLowerCase() === (v.category ?? "").trim().toLowerCase());
  const amount = usdAmount(v.amount);
  const memo = (v.memo ?? "").trim();
  const mealCap = category && MEALS.includes(category) ? p.meal_caps[category] : null;
  const date = /^\d{4}-\d{2}-\d{2}$/.test(v.date ?? "") ? v.date! : null;

  if (looksForeign(v.amount)) {
    out.push({ key: "non_usd", tone: "flag", text: "That amount isn't in US dollars. Enter the dollar amount from your card statement, or Finance will ask for it." });
  }
  if (date && date > p.today) out.push({ key: "future_date", tone: "flag", text: "The date is in the future. Finance will ask about it." });
  else if (date && date < monthsBefore(p.today, p.stale_months)) {
    out.push({ key: "stale_date", tone: "flag", text: `The date is more than ${p.stale_months} months ago, so a person will review it.` });
  }

  const nameClient = memo ? "Make sure the business purpose names the client company." : "Name the client company in the business purpose.";
  if (mealCap != null && date) {
    const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
    if (weekday === 0 || weekday === 6) {
      out.push({ key: "weekend_meal", tone: "reject", text: `Weekend meals are only paid for a client. ${nameClient}` });
    }
  }
  if (mealCap != null && amount != null && amount > mealCap) {
    out.push({ key: "meal_over_cap", tone: "reject", text: `${category} is capped at ${money(mealCap)} unless it's with a client. ${nameClient}` });
  }
  if (category === "Entertainment") {
    out.push({ key: "entertainment_not_client", tone: "reject", text: `Entertainment is only paid when it's with a client. ${nameClient}` });
  }
  if (category === "Hotel" && amount != null) {
    if (amount > p.hotel_cap_tier1) {
      out.push({ key: "hotel_over_cap", tone: "reject", text: `Hotels are capped at ${money(p.hotel_cap_tier1)} a night, even in the most expensive cities. If this covers several nights, say so in the purpose.` });
    } else if (amount > p.hotel_cap && !namesTier1City(`${v.merchant ?? ""} ${memo}`, p)) {
      out.push({ key: "hotel_over_cap", tone: "reject", text: `Hotels are capped at ${money(p.hotel_cap)} a night, or ${money(p.hotel_cap_tier1)} in ${p.tier1_cities.map(title).join(", ")}. Put the city in the merchant or purpose.` });
    }
  }
  if (amount != null && amount > p.receipt_threshold && !v.receipt) {
    out.push({ key: "missing_receipt", tone: "flag", text: `Anything over ${money(p.receipt_threshold)} needs a receipt. Without one, Finance will ask for it.` });
  }
  if (category === "Software" && !(v.approval_code ?? "").trim()) {
    out.push({ key: "missing_approval_code", tone: "flag", text: "Software needs an approval code from your manager. Without one, Finance will ask for it." });
  }
  if (amount != null && amount > p.high_amount_review) {
    out.push({ key: "high_amount_review", tone: "flag", text: `Anything over ${money(p.high_amount_review)} is always looked at by a person.` });
  }
  return out;
}

function namesTier1City(text: string, p: Policy) {
  const t = text.toLowerCase();
  return p.tier1_cities.some((c) => t.includes(c));
}

const title = (s: string) => s.replace(/\b[a-z]/g, (c) => c.toUpperCase()).replace(/\bDc\b/, "DC");
