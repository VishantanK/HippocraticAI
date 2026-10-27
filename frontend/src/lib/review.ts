import type { ExpenseSummary } from "./types";

/** Reasons only a person can resolve; the employee can't fix these by replying. */
const HUMAN_ONLY = new Set(["possible_duplicate", "high_amount_review", "edited_after_review", "check_failed",
  "llm_unavailable", "guard_unavailable", "possible_split", "possible_manipulation"]);

export function readyForDecision(e: ExpenseSummary) {
  if (e.status === "error") return true;
  if (e.status !== "flag") return false;
  return e.answers.length > 0 || (e.latest?.reasons ?? []).some((r) => HUMAN_ONLY.has(r.rule));
}

export function waitingOnEmployee(e: ExpenseSummary) {
  return e.status === "flag" && !readyForDecision(e);
}
