# Expense Auto-Approver: solution

Decides **approve / reject / flag** for each expense, drafts a question to the employee for every
flag, POSTs every decision to `/decisions`, and serves an employee portal plus a Finance dashboard.
Batch and portal share one pipeline.

## Run
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # keys in .env
(cd frontend && npm install && npm run build)          # React UI -> frontend/dist
python mock_server.py                                  # :8000 decisions endpoint
.venv/bin/uvicorn app.server:app --port 8001           # UI: /employee and /finance
.venv/bin/python batch.py                              # process data/pending_expenses.json
.venv/bin/python eval.py                               # score vs labels (live LLMs)
.venv/bin/python -m pytest -q                          # offline tests
```

## How a decision is made (`app/pipeline.py`)
1. **Input guard** (`app/guard.py`): schema/length checks, unknown keys dropped, Unicode sanitised.
   A manipulation screen runs on every free-text field and follow-up answer. The **OpenAI Decisions
   API** predicate (`gpt-6-luna`) rejects at p >= 0.5, the Claude screen is the fallback, and a
   4-pattern regex is the backstop. Manipulation -> **reject**.
2. **Normalise** (`app/normalize.py`): amounts are always USD (any other currency symbol is flagged
   for the employee to give the dollar amount; nothing is converted), ISO or US dates, weekday.
3. **Extract** (`app/llm.py`, Claude, JSON schema): canonical category, named client, city.
   An exact category match overrides the model.
4. **Policy** (`app/policy.py`, pure code; see ASSUMPTIONS.md): caps, weekend meals, Tier-1 hotels,
   receipt over $25, software codes, split detection. Untrusted data flags before any cap is applied.
5. **Fail closed**: if the guard or extraction can't complete -> flag, never approve.
6. **Question** for flags (Claude, falls back to a template) -> stored -> POSTed -> pushed over SSE.

Guard thresholds: reject at p >= 0.85 with the text located to a field; 0.5-0.85 goes to a person.
Follow-up replies are labelled `reply_to_finance_N` so the screen knows they answer Finance.

## Robustness
- **Async:** portal writes return 202 `checking`; a worker pool decides (`app/jobs.py`) and the
  result arrives over SSE. Rapid edits coalesce; anything left `checking` is re-queued on startup;
  a crashed job records a fail-closed `check_failed` flag.
- **Concurrency:** per-expense lock plus atomic revision allocation; same-employee evaluations are
  serialised so duplicate/split checks always see each other.
- **Delivery:** an outbox (`app/outbox.py`) claims each row atomically, retries with backoff
  (8 attempts, then `dead`), sends `Idempotency-Key: {id}:{revision}`, and never delivers a
  superseded revision. Verified: endpoint down for a batch of 18, all delivered exactly once on recovery.
- **Backstop rules:** duplicates (a reply can't clear one), anything over $1,000, future dates.
- **Human decisions are final** for that version: queued re-checks don't replace them, and an edit
  made after review can only flag.

## UI (React + Vite + Tailwind, `frontend/`)
| Route | For |
|---|---|
| `/employee` | My expenses; questions from Finance on top |
| `/employee/new` | Form with validation, or JSON/CSV drag-and-drop with preview |
| `/employee/expenses/:id` | Decision stamp, reply form matched to the gap, edit, history |
| `/finance` | Decision mix, spend by category, manipulation and delivery alerts, recent decisions |
| `/finance/queue` | Ready for your decision vs waiting on the employee |
| `/finance/expenses` | Sortable, filterable table |
| `/finance/expenses/:id` | Submitted vs read-as, automated checks, history with delivery, approve/reject |

Dev mode: `cd frontend && npm run dev` (proxies `/api` to :8001).

The LLMs never output the decision. Prompts live in `app/prompts/`.

## Results
- `eval.py`: **20/20** past decisions, **18/18** pending (gold labels in `data/expected_pending.json`),
  zero false approves (a hard assertion).
- `pytest` (83, offline): policy boundaries, parsers, guard bands, attacks, portal HTTP round-trips,
  concurrency, outbox retry/ordering/claims, async jobs, and the races found in code review.

## POSTed decision
`{id, employee, decision, reasons:[{rule, detail}], question, amount (USD), category,
category_mapped_from, client, suspected_manipulation, revision, decision_key, source, decided_by,
policy_version, prompt_version, decided_at}`. Each re-decision (edit, answer, Finance override)
is a new `revision`; downstream should keep the latest.

## Storage (`app/store.py`, SQLite `expenses.db`)
- `expenses`: current raw + normalised fields, follow-up answers, version, latest status.
- `decisions`: append-only; the exact POSTed payload, audit signals (guard score, extraction),
  delivery state (pending/sending/sent/failed/dead/superseded, attempts, next retry, last error).
- `followups`: question, answer, status (open / answered / superseded).

Docs: `docs/` (requirements, ADRs, architecture), `ASSUMPTIONS.md`, `AGENTS.md`.

---

# Setup

## 1. Install

You may use **any major LLM** (Claude, GPT, Gemini, …) — bring your own API key, and make sure you can make API calls.

The mock server and the starter's I/O use only the Python standard library, so your LLM SDK is `the only dependency.`

## 2. Start the mock endpoint

In one terminal:

```bash
python mock_server.py
```

This listens on `http://localhost:8000` and accepts your decisions:

- `POST /decisions` — body is a single decision object **or** a JSON list of them. Appended to `received_decisions.jsonl`.
- `GET  /decisions` — returns everything received so far.
- `GET  /health` — liveness check.

There is no required schema for a decision — design a shape that makes sense for the customer and be ready to explain it. When you `flag` an expense, attach the clarifying question for the submitter to that same decision (e.g. a `"question"` field); it rides along to `/decisions` with everything else.

## 3. Build

`starter.py` has data loading and a `post_decision()` helper wired up, plus a stubbed LLM call. Use it as a starting point or start from scratch — your call.

```bash
python starter.py   # runs the (unfinished) scaffold end to end
```

## 4. Build a small portal

Add a minimal UI that lets an employee:

- upload an expense file or enter one expense manually,
- see the system classify it as `approve` / `reject` / `flag` as soon as it has enough information,
- see the generated follow-up question immediately when the result is `flag`,
- answer the follow-up question when one is generated,
- POST the resulting decision to the same mock endpoint as the batch flow,
- store portal-submitted expenses somewhere durable enough for a demo.

Use any UI/backend stack you like. It can be plain HTML, a small local web app, or whatever is fastest for you. For storage, a JSON file, SQLite table, in-memory store with an export, or another simple representation is fine. Be ready to explain what you store and why.

The important part is that the portal uses the same end-to-end path as your batch processor: classify with the same decision logic, POST the resulting decision, show a useful submitter-facing question for flags, and store all relevant portal-submission state consistently with what you POST.



## Data

- `data/past_decisions.json` — 20 past expenses, each with the decision Finance made (`approve` / `reject` / `flag`). No explanations are included.
- `data/pending_expenses.json` — the batch to process. No decisions.

The data is real-world-messy on purpose (mixed formats, free-text notes, the occasional oddball). Handle it as you see fit.