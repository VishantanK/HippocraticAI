# AGENTS.md

Purpose: an expense auto-approver for Finance Ops. It decides approve / reject / flag for each
expense, drafts a follow-up question for flags, POSTs every decision, and serves an employee
portal plus a Finance dashboard. Built live, demoed and code-reviewed.

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Test (offline, no LLM): `.venv/bin/python -m pytest -q`
- Eval (live LLMs, labelled data): `.venv/bin/python eval.py`
  (`--suite mock` runs only the 100 synthetic failure-mode cases in `data/mock_cases.json`)
- Mock endpoint: `python mock_server.py` (localhost:8000)
- Batch: `.venv/bin/python batch.py [file]`
- Portal: `.venv/bin/uvicorn app.server:app --port 8001`

## Design rules
- Code makes every decision. LLMs only screen for manipulation, extract facts and write
  questions; `app/policy.py` is pure and has no LLM or I/O.
- The input guard (`app/guard.py`) runs first on every expense and every follow-up answer.
  A manipulation attempt is rejected. The OpenAI Decisions API is primary, the Claude screen is
  the fallback, and a small regex list is the backstop.
- Fail closed: if any check can't complete (LLM down, guard error), the result is `flag`, never `approve`.
- Untrusted text goes into prompts only inside tags, and every LLM call uses structured output.
- The batch run and the portal share one path (`pipeline.process`). What is stored matches what is POSTed.
- Decisions and follow-ups are append-only (revisions). A follow-up answer adds data and
  triggers a full re-evaluation; it never sets the decision.
- No keys in logs or code; `.env` is never committed.
- Ask before adding a dependency.

## Workflow
- Plan multi-file changes before coding.
- One vertical slice at a time.
- Write the test first for any guarantee.
- Show pytest output (and the eval result for policy/prompt changes) before saying something is done.
- Keep diffs small and commit after each green slice, with messages that say why.
- Never edit a test to make it pass.
- After each change, give 3 bullets: what changed, why, what could break.
- Record architectural decisions as an ADR in docs/adr/ plus a row in docs/DECISIONS.md.
- Keep README.md and docs/ARCHITECTURE.md true to the code; update the README before each push.
