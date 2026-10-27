# 0001. Deterministic policy, LLM at the edges

Status: Accepted, 2026-10-27

## Context
Expense rules (caps, receipts, codes, weekends) are crisp, but the inputs are messy free text.
A wrong auto-approval pays out company money.

## Decision
`app/policy.py` is a pure function that decides. LLMs only extract typed facts (canonical
category, client named, city) under a JSON schema, and draft follow-up questions.
An exact category match overrides the LLM.

## Alternatives considered
- LLM decides directly: not auditable, open to prompt injection, nondeterministic. Rejected.
- Pure rules, no LLM: can't tell "w/ Acme" (client) from "team dinner", or map "Taxi". Rejected.

## Consequences
Good: 38/38 on labelled data, unit-testable boundaries. Bad: extraction errors still matter
(e.g. a wrong is_client). Watch: the eval after any prompt change.
