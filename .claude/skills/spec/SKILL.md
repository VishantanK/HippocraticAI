---
name: spec
description: "Turn the user's discovery notes into docs/REQUIREMENTS.md, sized for a 2-hour build."
disable-model-invocation: true
---

Turn these discovery notes into docs/REQUIREMENTS.md: $ARGUMENTS

Rules:
- Fill the existing headings. Only facts the user stated; anything inferred goes under an
  "Assumptions" heading.
- At most 3 core flows, so it fits a 2-hour build. Move the rest to "Scope: later".
- 5-8 acceptance scenarios in the table (#, expense/input, system must, must not), including at
  least one safety case (manipulation attempt, missing data, or escalation to a human).
- Do not write code.

Reply with:
1. A 5-line read-back the user can say to the customer to confirm understanding.
2. The top 3 open questions, most important first.
