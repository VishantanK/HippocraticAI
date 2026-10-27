# Progress

## Current slice
Done: end-to-end system. Next: polish and review.

## Done
- Policy engine, normalisation, input guard (Decisions API + Claude fallback + regex backstop)
- LLM extraction and question drafting; pipeline; SQLite store; POST; batch.py; eval.py
- FastAPI server with SSE; employee portal (submit/upload/edit/answer); Finance dashboard (filters, history, override)
- Live batch: 18 decisions POSTed, 4 flags with questions; eval 38/38, zero false approves

## Next
- Retry failed POSTs (outbox); auth/roles; receipt OCR; alcohol and per-person rules (open questions)
- Browser smoke test of the UI (Chrome automation couldn't reach the local server)

## Gotchas
- `.env` keys have a space before `=`; python-dotenv handles it.
- Tests set LLM_DISABLED=1 and stub the LLMs; eval.py and batch.py use live LLMs.
- uvicorn binds IPv4 localhost only.

## Last test result
59 passed
