# Decisions

| Decision | Why | Rejected alternative |
|----------|-----|----------------------|
| [0001](adr/0001-deterministic-policy-llm-at-edges.md) Code decides; LLM only extracts and writes questions | Auditable, testable, and can't be talked into approving | LLM outputs the decision |
| [0002](adr/0002-input-guard-decisions-api.md) Input guard first; OpenAI Decisions API primary, Claude fallback, regex backstop | Calibrated probability, cheap and fast; layered defence | Hardcoded regex only; OpenAI Moderation API (doesn't target injection) |
| [0003](adr/0003-reject-manipulation-flag-unknowns.md) Manipulation is rejected; unknowns and failures are flagged | Finance's call; a wrong approval costs more than a human look | Flagging manipulation for review |
| [0004](adr/0004-no-fx-table.md) Everything is USD; any other currency symbol is flagged for the USD amount | No conversion or currency tracking to get wrong | Static FX table; currency field |
| [0005](adr/0005-sqlite-append-only.md) SQLite with append-only decision/follow-up history | One file, full audit trail, matches what was POSTed | JSON file; in-memory store |
| [0006](adr/0006-backstop-rules.md) Flag duplicates, amounts over $1,000 and future dates | Stop double payment and runaway uncapped approvals | Reject duplicates; no ceiling |
