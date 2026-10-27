import type { ExpenseDetail, ExpenseInput, ExpenseSummary, Stats } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  return body as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const api = {
  list: (q: { source?: string; employee?: string } = {}) => {
    const params = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
    return request<ExpenseSummary[]>(`/api/expenses${params.size ? `?${params}` : ""}`);
  },
  get: (id: string) => request<ExpenseDetail>(`/api/expenses/${encodeURIComponent(id)}`),
  create: (e: ExpenseInput) => request<ExpenseDetail>("/api/expenses", json("POST", e)),
  update: (id: string, e: ExpenseInput) => request<ExpenseDetail>(`/api/expenses/${encodeURIComponent(id)}`, json("PUT", e)),
  upload: (file: File, employee: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("employee", employee);
    return request<ExpenseDetail[]>("/api/expenses/upload", { method: "POST", body: fd });
  },
  answer: (id: string, form: FormData) =>
    request<ExpenseDetail>(`/api/expenses/${encodeURIComponent(id)}/answer`, { method: "POST", body: form }),
  override: (id: string, decision: "approve" | "reject", note: string) =>
    request<ExpenseDetail>(`/api/expenses/${encodeURIComponent(id)}/override`, json("POST", { decision, note })),
  stats: () => request<Stats>("/api/stats"),
  employees: () => request<string[]>("/api/employees"),
};
