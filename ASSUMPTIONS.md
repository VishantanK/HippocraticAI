# Assumptions

Every assumption made while building, with its source. **Confirmed** = the user/customer agreed.
**Inferred** = derived from the data or notes and not explicitly confirmed. Update this file whenever
a new assumption is made, and move items to Confirmed when the customer answers.

## Policy
| # | Assumption | Status | Source |
|---|---|---|---|
| P1 | Meal caps: Breakfast $20, Lunch $30, Dinner $60; over the cap with no client = **reject** | Inferred | notes.txt #2; EXP-1003/1005/1007 rejected |
| P2 | "No weekend meals except clients" = Sat/Sun meal with no client is **rejected** | Inferred | notes #1; EXP-1020 (Sat) rejected |
| P3 | A client meal or client Entertainment needs a **named external org/person** in the memo; "team dinner" is not a client | Inferred | EXP-1017 vs 1018 |
| P4 | Entertainment with no client = reject | Inferred | notes #7 "ONLY Client" |
| P5 | Hotel cap is per night ($200, or $350 in Tier-1 cities); the location comes from merchant/memo/LLM city. A stay that mentions more than one night ("3 nights", "2-night", "nights") is **flagged** `multi_night_hotel`, never divided by code; one night or unstated = the total is capped | Confirmed (multi-night) | notes #5; EXP-1012/1013/1014; user chose "Flag multi-night" |
| P6 | Receipt is needed when amount **> $25** (exactly $25 is fine); missing = **flag** | Inferred | notes #8; EXP-1006/1008 approve, 1009 flag |
| P7 | Software with no approval code = **flag** (not reject); codes are checked against `data/approval_codes.json` | Inferred | notes #9; EXP-1010 flagged |
| P8 | Airfare is uncapped (not in notes) | Inferred | EXP-1016 approved |
| P9 | Office, Software, Uber/ground transport are uncapped | Inferred | notes #6 |
| P10 | A reject from trusted fields outranks a flag (e.g. over-cap dinner with no receipt -> reject) | Inferred | safety: rejecting pays nothing |
| P11 | Split expense = same employee + merchant + meal category within 1 day, each under the cap but combined over it, no client -> **flag** | Confirmed | asked; user chose "detect cap-dodging splits" |
| P12 | Unknown categories are mapped by the LLM to the nearest policy category (e.g. Taxi -> GroundTransport); low confidence or no fit -> flag | Confirmed | user chose "LLM maps to nearest" |
| P13 | Empty category is never filled in by the LLM -> flag | Inferred | notes "Missing category --> Ask" |
| P14 | Alcohol is not separately restricted; EXP-2006 is rejected on the cap only | Inferred | open question |
| P15 | Duplicate = same employee + merchant (letters only, so "Chipotle #12" = "CHIPOTLE") + date + amount within 1% as another expense that isn't rejected -> **flag**. A follow-up answer can't clear it; only Finance can | Inferred | robustness review |
| P16 | Any would-be approve over **$1,000** goes to a human (`HIGH_AMOUNT_REVIEW`); a reject stays a reject | Inferred | backstop for uncapped categories; past max approved was $410 |
| P17 | A future-dated expense -> flag | Inferred | data validity |
| P18 | Rejected expenses are ignored for split and duplicate checks (they aren't paid) | Inferred | design |
| P19 | A Finance decision is final for that version: queued automatic re-checks don't replace it, and an edit made after review can't auto-approve (it's flagged `edited_after_review`) | Inferred | review finding |
| P20 | If a decision job crashes, the expense is flagged `check_failed` (stored and POSTed) | Inferred | fail closed |
| P21 | A Finance override applies only to the revision the reviewer saw: if the expense was re-decided since, or is being re-checked, it is refused (409) and the page reloads | Inferred | robustness review (stale approve) |
| P21 | An expense dated more than **6 calendar months** before today is flagged `stale_date` (late claim or a year typo); a reject stays a reject | Confirmed | user |
| P22 | A placeholder merchant (no letters/digits, or N/A, none, unknown, TBD, misc, various...) counts as `missing_merchant` | Confirmed | user chose "Flag both" |
| P23 | A blank employee is flagged `missing_employee` (duplicate and split checks can't run without one) | Confirmed | user chose "Flag both" |

## Data
| # | Assumption | Status | Source |
|---|---|---|---|
| D1 | All amounts are USD: plain numbers and `$`/`US$`/`USD` amounts. No currency identification or conversion anywhere | Confirmed | user |
| D2 | An amount with any other currency symbol (€ £ ¥ ₹ ₩…, detected generically) -> flag `non_usd`, asking for the USD amount charged. Text like "65 EUR" is unreadable -> flag `invalid_amount` | Confirmed | user |
| D3 | Dates are ISO or US MM/DD/YYYY | Inferred | data |
| D4 | `receipt` counts only when it is literal `true`; anything else = no receipt | Inferred | safety |
| D5 | Unknown input fields (e.g. a `decision` key in an upload) are dropped | Inferred | safety |
| D6 | Zero or negative amounts -> flag | Inferred | safety |
| D7 | Amounts must be plain dollars and cents: ASCII digits, commas only as thousands groups, at most 2 decimals, finite. "12,50", "1.234,56", "1,0000", "1e1", "nan", "15.999" are **flagged** `invalid_amount`, never guessed | Confirmed | user ("should be flagged as a typo"); MOCK-065; NaN used to approve |
| D8 | "Today" for date rules is the real date unless `EXPENSE_TODAY` pins it (tests and eval pin 2026-10-27 so fixed-date data doesn't age) | Inferred | design |

## Security
| # | Assumption | Status | Source |
|---|---|---|---|
| S1 | A manipulation attempt (text addressed to the reviewer) -> **reject** outright | Confirmed | user chose "Reject outright" |
| S2 | Guard: OpenAI Decisions API primary, Claude fallback, small regex backstop. **Reject** at p >= 0.85 with the text located to a field; 0.5-0.85 (or unlocated) -> a person reviews it (`possible_manipulation`), never auto-approved | Confirmed (thresholds inferred) | user; calibration in ADR 0002 |
| S3 | Follow-up answers are untrusted and guarded too; an answer can't set the decision directly | Inferred | safety |
| S4 | If any LLM/guard check can't complete -> flag (fail closed) | Inferred | safety |
| S5 | Only the guard judges manipulation. The extractor no longer has an injection flag: it produced false positives on benign replies ("Code from my manager") and duplicated the guard, which already scans every field incl. replies | Inferred | found live: a benign follow-up reply was rejected |
| S6 | Follow-up replies are passed to the guard as `reply_to_finance_N` and to the extractor as `followup_answers` (not merged into the memo), so both know they answer Finance's question | Inferred | same finding |

## Product / system
| # | Assumption | Status | Source |
|---|---|---|---|
| A1 | Stack: FastAPI + SQLite + vanilla JS, SSE for live updates | Confirmed | user |
| A2 | Every re-evaluation POSTs a new decision with an increasing `revision`; downstream uses the latest | Inferred | design |
| A3 | Portal submissions get server ids `WEB-####`; an uploaded id is kept as `external_id` | Inferred | avoids overwriting other expenses |
| A4 | No auth: Employee and Finance are separate routes; the employee picks their identity in the UI | Confirmed | user chose "route split only, no auth" |
| A5 | Failed POSTs are retried with backoff (8 attempts, then `dead`); only the latest revision of an expense is delivered, and older undelivered ones become `superseded` | Inferred | downstream keeps the latest revision |
| A6 | Models: Claude `claude-haiku-5-5` for extraction/questions; `gpt-6-luna` for the guard | Confirmed | user set Haiku in config |
| A7 | The form's policy hints are guidance only: built from the same constants as `policy.py` via `GET /api/policy`, they never block a submit and the server's check is the only decision. Client and city are only guessed at client-side (the LLM reads them). Approval codes are never sent to the browser | Inferred | slice 2 (user liked inline hints) |
| A8 | Finance's list filters on the latest decision (amount, category, rules) and is paged at 50; saved views live in the reviewer's browser only (no accounts yet) | Inferred | slice 3 |
| A9 | CSV export has the same filters as the list but every page, with the latest decision per expense (not the full history). String cells starting with = + - @ tab or CR are prefixed with ' so a spreadsheet won't run them | Inferred | slice 4; memos are untrusted |
