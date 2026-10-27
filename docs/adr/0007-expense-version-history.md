# 0007. Keep every submitted version of an expense

Status: Accepted, 2026-10-27

## Context
When an employee edits an expense, `expenses.raw_json` is overwritten. Decisions record which
`expense_version` they judged, but the fields of earlier versions were lost. So Finance couldn't
see why a decision flipped (for example, reject to approve after a client name was added).

## Decision
A new append-only table, `expense_versions (expense_id, version, raw_json, created_at)`, gets
one row per distinct submitted version. It is written in the same transaction that bumps
`expenses.version`, and for single and batch inserts. On connect, existing databases are
backfilled with each expense's current version. `GET /api/expenses/{id}` returns `versions`,
and Finance's expense page shows "What changed since the previous decision": field diffs
between the versions the last two decisions used, plus replies in between.

## Alternatives considered
- Diffing `signals`/`normalized` from decision rows: those hold the extracted view, not what
  the employee typed. Rejected.
- Storing a diff per edit: harder to read back, and the full rows are small. Rejected.

## Consequences
A complete audit trail of what was submitted, alongside the decisions table (ADR 0005).
Expenses edited before this change show only their current version; the UI says so.
`expenses.raw_json` remains the current version for every reader, so nothing else changes.
