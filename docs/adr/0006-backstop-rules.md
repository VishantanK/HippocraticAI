# 0006. Backstop rules: duplicates, high amounts, future dates

Status: Accepted, 2026-10-27

## Context
In v1 the same receipt submitted twice was approved twice, and uncapped categories (client meals,
Airfare, Office) could auto-approve any amount. A future-dated expense was also accepted.

## Decision
Three flag rules in `app/policy.py`:
- `possible_duplicate`: same employee, merchant, date and amount as a non-rejected expense.
- `high_amount_review`: a would-be approve over `HIGH_AMOUNT_REVIEW` (default $1,000).
- `future_date`: the date is after today.
They flag rather than reject, because each has a legitimate explanation that a human can confirm.
Duplicate takes precedence over split, and rejected expenses are ignored by both.

## Alternatives considered
- Reject duplicates: two identical coffees on one day can be real. Rejected.
- No amount ceiling: one bad extraction (is_client) could approve thousands of dollars. Rejected.

## Consequences
More flags on high-value trips. Watch the $1,000 threshold with Finance. Eval unchanged (38/38).
