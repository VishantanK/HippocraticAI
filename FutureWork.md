# Future work

North stars: out of scope for the demo, but the current design is meant to grow into them.
What stays the same throughout: code decides, the guard runs first, checks fail closed,
history is append-only, and the batch run and the portal share one `pipeline.process` path.

## Receipts end to end
Today a follow-up reply can attach a file. It is saved to `uploads/` and recorded as
`receipt_file`, but nothing serves it back.
- Serve receipts to Finance with a preview next to the "Submitted / Read as" table. Check
  the file name belongs to that expense and send `Content-Disposition` and `nosniff` headers.
- Validate uploads: reject anything over the size limit with a 413 (today it is cut off
  silently at 5 MB). Allow only pdf/png/jpg/heic, checked by magic bytes, and give the file
  a server-chosen extension.
- Mobile camera capture on New expense, not only in the follow-up reply.
- Object storage (S3/GCS) with presigned upload and download URLs, plus a virus scan.
- OCR to cross-check the amount, merchant and date against the submitted fields. A mismatch
  is flagged, never auto-approved.

## Auth and roles
Today (ASSUMPTIONS A4) there is no sign-in. Anyone can open `/finance` or call `/override`,
and any employee name shows that person's expenses.
- SSO (OIDC/SAML) with three roles: employee, finance-reviewer, finance-admin.
- The employee comes from the token, never from the request body or `localStorage`.
- Record the reviewer's identity on every override (`reviewer` is hard-coded to `"finance"` today).
- Scope reads and live events by role: employees see only their own expenses.

## Scaling to ~20k users
**Load estimate:** about 200k expenses a month, roughly 7k/day, peaking near 0.5 decisions/sec
after month-end. Throughput is small. What breaks first is fan-out, unbounded reads,
single-process state, and LLM rate limits.

### What breaks first
1. `GET /api/expenses` returns every row, and every SSE event makes every open page refetch it.
   Employee pages also refetch on other people's events, because `useData` defaults to
   "relevant = always".
2. SSE broadcasts every event to every client. That leaks other employees' expense ids and
   multiplies traffic.
3. In-process state assumes one process: `jobs._queued/_running`, `pipeline.expense_lock`,
   the SSE `_subscribers` set and the outbox thread. With two workers, expenses would be
   processed twice and SSE clients would only see half the events.
4. SQLite runs behind one global `RLock`. `stats()` scans every expense and parses every
   payload in Python on each Overview load.
5. Each expense needs 2-3 LLM calls, so provider rate limits and latency set the ceiling.
   A month-end spike queues behind 4 threads.

### Stage A: same box, ~2k users
- Scoped SSE (`?employee=X` or Finance). Events carry enough fields to patch the cached
  row in place, so clients don't refetch.
- Keep `stats` in a summary table updated on each decision, instead of a full scan.
- A client query cache (e.g. TanStack Query) for dedupe and stale-while-revalidate. This is
  a new dependency, so ask before adding it.

### Stage B: multiple instances, 20k users
- Postgres instead of SQLite. The append-only tables stay as they are. Row or advisory
  locks on the expense id replace `expense_lock`.
- A durable job queue (Postgres `SKIP LOCKED`, Redis or SQS) replaces the in-memory sets in
  `jobs.py`. Workers scale separately from the web tier. The outbox becomes a worker over
  the same table, which is already transactional-outbox shaped.
- Pub/sub for live updates (Postgres `LISTEN/NOTIFY` or Redis), keyed per employee and for
  Finance, so any web node can serve any SSE client.
- LLM layer: per-provider concurrency limits and token-bucket rate limiting, plus caching of
  guard and extract results by content hash. Fail-closed stays as it is.
- Ops: structured logs keyed by expense id; metrics for decision latency, queue depth, LLM
  error rate and outbox dead count; alerts on `dead > 0` and on queue age; the frontend
  served from a CDN.

### Stage C: only if needed
Read replicas for Finance analytics, partitioning by month, and a separate analytics store.
