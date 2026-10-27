# Progress

## Current slice
v2 done: robustness + React UI. Next: polish from user review.

## Done
- v1: policy, guard, extraction, questions, pipeline, store, batch, eval, basic UI
- v2 backend: per-expense lock, backstop rules, POST outbox, async jobs, stats; review fixes
  (ordering, human-final, same-employee races, sticky duplicates, failure flag)
- Guard false-positive fix (found live): labelled replies, two-band thresholds, extractor flag removed
- React UI: /employee and /finance routes
- Verified live: eval 38/38; outbox recovery 18/18 delivered once; portal flag -> reply -> approve,
  manipulative replies rejected

## Next
- Visual check of the UI in a browser (Chrome automation can't reach the local server here)
- Auth/roles; receipt OCR; per-person caps and alcohol rule (open questions)

## Gotchas
- `.env` keys have a space before `=`; python-dotenv handles it.
- Tests stub LLMs; eval.py and batch.py call live APIs.
- Rebuild the UI (`cd frontend && npm run build`) after frontend changes; FastAPI serves dist/.

## Last test result
128 passed; eval 38/38 + mock 99/100, zero false approves
