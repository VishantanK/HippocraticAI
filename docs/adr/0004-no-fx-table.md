# 0004. No hardcoded FX conversion

Status: Accepted, 2026-10-27

## Context
EXP-2015 is €65. Notes say "Non dollar amounts (convert)".

## Decision
Any non-USD amount is flagged and the question asks for the USD amount as charged. An amount
with no currency marker is treated as USD. The answer's USD amount re-runs the full policy.

## Alternatives considered
- Static FX table: stale, and it would silently drive approvals. Rejected.
- Live FX API: new dependency, still not the card-statement amount. Rejected.

## Consequences
Every foreign expense needs one employee reply.
