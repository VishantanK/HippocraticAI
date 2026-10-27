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