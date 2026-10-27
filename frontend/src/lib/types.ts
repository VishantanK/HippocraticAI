export type Decision = "approve" | "reject" | "flag";
export type Status = Decision | "checking" | "error" | null;

export interface Reason { rule: string; detail: string }

/** Exactly what is POSTed to /decisions. */
export interface Payload {
  id: string;
  employee: string | null;
  decision: Decision;
  reasons: Reason[];
  question: string | null;
  amount?: number | null; // always USD; null when unreadable or not in dollars
  category?: string | null;
  category_mapped_from?: string | null;
  client?: string | null;
  suspected_manipulation?: boolean;
  revision: number;
  decision_key: string;
  source: "batch" | "portal";
  decided_by: "system" | "human";
  reviewer?: string;
  policy_version: string;
  decided_at: string;
}

export interface RawExpense {
  employee: string | null;
  date: string | null;
  category: string | null;
  merchant: string | null;
  amount: number | string | null;
  memo: string | null;
  receipt: boolean | null;
  approval_code: string | null;
}

export interface Answer { text: string; fields: Record<string, unknown>; at: string }

export interface Signals {
  guard?: {
    schema_issues: string[];
    manipulation: { field: string; evidence: string; detector: string; probability?: number }[];
    guard_error: string | null;
    screen: { detector?: string; probability?: number; field?: string; primary_error?: string } | null;
  };
  extract?: { category: string; category_confidence: number; is_client: boolean; client_name: string; city: string };
  llm_error?: string;
  question_source?: string | null;
}

export interface DecisionRow {
  revision: number;
  expense_version: number;
  decision: Decision;
  decided_by: "system" | "human";
  payload: Payload;
  signals: Signals;
  post_status: "pending" | "sent" | "failed" | "dead";
  post_attempts: number;
  last_error: string | null;
  next_attempt_at: string | null;
  decided_at: string;
}

export interface Followup {
  rowid: number;
  decision_revision: number;
  question: string;
  answer: string | null;
  status: "open" | "answered" | "superseded";
  asked_at: string;
  answered_at: string | null;
}

export interface ExpenseSummary {
  id: string;
  employee: string | null;
  source: "batch" | "portal";
  external_id: string | null;
  raw: RawExpense;
  normalized: Record<string, unknown> | null;
  answers: Answer[];
  version: number;
  status: Status;
  created_at: string;
  updated_at: string;
  latest?: Payload | null;
  post_status?: string | null;
  decided_by?: string | null;
}

export interface ExpenseDetail extends ExpenseSummary {
  decisions: DecisionRow[];
  followups: Followup[];
}

export interface Stats {
  total: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
  manipulation: number;
  open_questions: number;
  answered_awaiting_review: number;
  post: { pending: number; sent: number; failed: number; dead: number };
  by_category: { category: string; approve: number; reject: number; flag: number }[];
  recent: { expense_id: string; revision: number; decision: Decision; decided_by: string; decided_at: string; employee: string | null }[];
}

export type ExpenseInput = Omit<RawExpense, "receipt"> & { receipt: boolean };

/** GET /api/policy: the numbers behind the form's hints (guidance; the server decides). */
export interface Policy {
  version: string;
  today: string;
  categories: string[];
  meal_caps: Record<string, number>;
  hotel_cap: number;
  hotel_cap_tier1: number;
  tier1_cities: string[];
  receipt_threshold: number;
  high_amount_review: number;
  stale_months: number;
}
