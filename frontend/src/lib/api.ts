import type { Delivery, ExpenseDetail, ExpenseInput, ExpenseSummary, Policy, Stats } from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`, res.status);
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
  /** One page of Finance's filtered list; `params` are the API's own query params (also the page URL's). */
  page: async (params: URLSearchParams) => {
    const res = await fetch(`/api/expenses?${params}`);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`, res.status);
    return { rows: body as ExpenseSummary[], total: Number(res.headers.get("X-Total-Count") ?? (body as unknown[]).length) };
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
  /** `expectedRevision` is the latest revision on screen; the server refuses (409) if it moved on. */
  override: (id: string, decision: "approve" | "reject", note: string, expectedRevision: number) =>
    request<ExpenseDetail>(`/api/expenses/${encodeURIComponent(id)}/override`,
      json("POST", { decision, note, expected_revision: expectedRevision })),
  stats: () => request<Stats>("/api/stats"),
  employees: () => request<string[]>("/api/employees"),
  policy: () => request<Policy>("/api/policy"),
  deliveries: () => request<Delivery[]>("/api/deliveries"),
  retryDelivery: (id: string, revision: number) =>
    request<{ post_status: string }>(`/api/deliveries/${encodeURIComponent(id)}/${revision}/retry`, { method: "POST" }),
  retryAllDeliveries: () => request<{ sent: number; failed: number }>("/api/deliveries/retry-all", { method: "POST" }),
};
