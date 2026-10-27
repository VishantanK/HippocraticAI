# Progress

## Current slice
v3 done: robustness + Finance/employee UX slices (below). Next: browser walkthrough of the new screens.

## Done
- v1: policy, guard, extraction, questions, pipeline, store, batch, eval, basic UI
- v2 backend: per-expense lock, backstop rules, POST outbox, async jobs, stats; review fixes
  (ordering, human-final, same-employee races, sticky duplicates, failure flag)
- Guard false-positive fix (found live): labelled replies, two-band thresholds, extractor flag removed
- React UI: /employee and /finance routes
- Verified live: eval 38/38; outbox recovery 18/18 delivered once; portal flag -> reply -> approve,
  manipulative replies rejected
- v3 (one commit each): stale-view override refused (409); live policy hints (GET /api/policy);
  server-side filters/paging/saved views; CSV export (formula-safe); delivery page + retry;
  SSE resync on reconnect/visibility, bounded queues, error boundaries; idempotency keys,
  atomic uploads, form drafts, override confirm + note to reverse; expense version history
  + "what changed" (ADR 0007). North stars moved to FutureWork.md (receipts, auth, scale).

## Next
- Visual check of the UI in a browser, incl. the v3 screens (filters, delivery, what changed, hints)
- Frontend tests: needs Vitest (new dependency, ask first); hint and diff logic were checked with node only
- Per-person caps and alcohol rule (open questions); see FutureWork.md for auth, receipts, scale

## Gotchas
- `.env` keys have a space before `=`; python-dotenv handles it.
- Tests stub LLMs; eval.py and batch.py call live APIs.
- Rebuild the UI (`cd frontend && npm run build`) after frontend changes; FastAPI serves dist/.

## Last test result
156 passed; eval not re-run in v3 (no policy or prompt changes; last: 38/38 + mock 99/100)