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
| P5 | Hotel cap is per night ($200, or $350 in Tier-1 cities); the location comes from merchant/memo/LLM city | Inferred | notes #5; EXP-1012/1013/1014 |
| P6 | Receipt is needed when amount **> $25** (exactly $25 is fine); missing = **flag** | Inferred | notes #8; EXP-1006/1008 approve, 1009 flag |
| P7 | Software with no approval code = **flag** (not reject); codes are checked against `data/approval_codes.json` | Inferred | notes #9; EXP-1010 flagged |
| P8 | Airfare is uncapped (not in notes) | Inferred | EXP-1016 approved |
| P9 | Office, Software, Uber/ground transport are uncapped | Inferred | notes #6 |
| P10 | A reject from trusted fields outranks a flag (e.g. over-cap dinner with no receipt -> reject) | Inferred | safety: rejecting pays nothing |
| P11 | Split expense = same employee + merchant + meal category within 1 day, each under the cap but combined over it, no client -> **flag** | Confirmed | asked; user chose "detect cap-dodging splits" |
| P12 | Unknown categories are mapped by the LLM to the nearest policy category (e.g. Taxi -> GroundTransport); low confidence or no fit -> flag | Confirmed | user chose "LLM maps to nearest" |
| P13 | Empty category is never filled in by the LLM -> flag | Inferred | notes "Missing category --> Ask" |
| P14 | Alcohol is not separately restricted; EXP-2006 is rejected on the cap only | Inferred | open question |

## Data
| # | Assumption | Status | Source |
|---|---|---|---|
| D1 | An amount with no currency marker is USD | Confirmed | user |
| D2 | Any non-USD amount -> flag and ask for the USD amount charged; no FX table | Confirmed | user |
| D3 | Dates are ISO or US MM/DD/YYYY | Inferred | data |
| D4 | `receipt` counts only when it is literal `true`; anything else = no receipt | Inferred | safety |
| D5 | Unknown input fields (e.g. a `decision` key in an upload) are dropped | Inferred | safety |
| D6 | Zero or negative amounts -> flag | Inferred | safety |

## Security
| # | Assumption | Status | Source |
|---|---|---|---|
| S1 | A manipulation attempt (text addressed to the reviewer) -> **reject** outright | Confirmed | user chose "Reject outright" |
| S2 | Guard: OpenAI Decisions API primary, Claude fallback, small regex backstop; reject at p >= 0.5 | Confirmed (threshold inferred) | user; calibration in ADR 0002 |
| S3 | Follow-up answers are untrusted and guarded too; an answer can't set the decision directly | Inferred | safety |
| S4 | If any LLM/guard check can't complete -> flag (fail closed) | Inferred | safety |

## Product / system
| # | Assumption | Status | Source |
|---|---|---|---|
| A1 | Stack: FastAPI + SQLite + vanilla JS, SSE for live updates | Confirmed | user |
| A2 | Every re-evaluation POSTs a new decision with an increasing `revision`; downstream uses the latest | Inferred | design |
| A3 | Portal submissions get server ids `WEB-####`; an uploaded id is kept as `external_id` | Inferred | avoids overwriting other expenses |
| A4 | No auth in the demo; the employee/finance views are separate pages | Inferred | 2h scope |
| A5 | A failed POST is recorded (`post_status=failed`) but not retried | Inferred | 2h scope |
| A6 | Models: Claude `claude-haiku-5-5` for extraction/questions; `gpt-6-luna` for the guard | Confirmed | user set Haiku in config |
