# 0004. No currency handling: everything is USD

Status: Accepted, 2026-10-27 (revised: currency identification removed)

## Context
EXP-2015 is €65. Notes say "Non dollar amounts (convert)". v1 mapped symbols and ISO codes to a
currency field and carried it through the system.

## Decision
There is no currency handling. Plain numbers and `$`/`US$`/`USD` amounts are USD. Any other
currency symbol (any Unicode currency character, not a fixed list) means the amount is not
read; the expense is flagged `non_usd` and the question asks for the USD amount as charged.
Other unreadable text (e.g. "65 EUR") is flagged `invalid_amount`. Decisions carry only a USD
`amount`; there is no `currency` field.

## Alternatives considered
- Static FX table: stale, and it would silently drive approvals. Rejected.
- Identify currencies (symbol/ISO table) and carry a currency field: more code, and nothing
  downstream used it except to say "not USD". Rejected (user).

## Consequences
Every foreign expense needs one employee reply. Simpler data: amounts are always dollars.
