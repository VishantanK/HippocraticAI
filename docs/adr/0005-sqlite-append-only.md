# 0005. SQLite with append-only history

Status: Accepted, 2026-10-27

## Context
The portal must persist submissions, decisions and follow-up state consistently with what was POSTed.

## Decision
`app/store.py` keeps three tables. `expenses` holds the current raw and normalised view plus the
answers, with a version. `decisions` gets one row per revision (exact POST payload, signals,
post_status). `followups` holds question, answer and status (open/answered/superseded).

## Alternatives considered
- A JSON file: no concurrency or queries. Rejected.
- In-memory: lost on restart. Rejected.

## Consequences
A full audit trail, and the latest revision is the truth. A POST failure is recorded (post_status)
but not yet retried.
