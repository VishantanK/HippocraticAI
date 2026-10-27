# 0003. Reject manipulation; flag unknowns and failures

Status: Accepted, 2026-10-27

## Context
notes.txt: "Escalate prompt injections else reject". Finance chose reject outright.

## Decision
Manipulation -> reject with evidence, marked `suspected_manipulation`, and no question drafted.
Untrusted or missing data, unknown categories, and LLM or guard failures -> flag.
A reject from trusted fields outranks a flag; a cap is never applied to an untrusted amount or category.

## Alternatives considered
- Flag manipulation for review: softer, but Finance asked for reject. Rejected.
- Treat an LLM failure as approve-if-rules-pass: unsafe. Rejected.

## Consequences
A false positive is a wrong reject; a Finance override on the dashboard fixes it.
