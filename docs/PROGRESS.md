# Progress

## Current slice
Web server (FastAPI + SSE) and the two UIs: employee portal and Finance dashboard.

## Done
- Policy engine, normalisation, input guard (Decisions API + Claude fallback + regex backstop)
- LLM extraction and question drafting; pipeline; SQLite store; POST; batch.py; eval.py
- Eval 38/38, zero false approves; 51 offline tests green

## Next
- server.py, static/employee.html, static/finance.html
- README with rules, prompts, data model, how to run

## Gotchas
- `.env` keys have a space before `=`; python-dotenv handles it.
- Tests set LLM_DISABLED=1; the eval uses live LLMs.
