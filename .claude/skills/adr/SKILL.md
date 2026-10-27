---
name: adr
description: "Record an architecture decision as docs/adr/NNNN-slug.md and add a row to docs/DECISIONS.md."
---

Record this decision: $ARGUMENTS

1. Number = highest in docs/adr/ + 1, 4 digits (start at 0001). Slug from the title.
2. Write docs/adr/NNNN-slug.md, 30 lines or fewer, with these sections:
   `# NNNN. Title`, Status (Accepted, today's date), Context, Decision,
   Alternatives considered (each with why it was rejected), Consequences (good, bad, what to watch).
3. Only facts from the conversation or the code; label guesses as Assumption.
4. Add a row to docs/DECISIONS.md: decision (linking the ADR), why, rejected alternative.
5. If it replaces an earlier ADR, set that one's Status to "Superseded by NNNN".
6. Reply with the path and a 1-line summary. Don't commit; the slice commit includes it.
