---
name: arch
description: "Generate or refresh docs/ARCHITECTURE.md from the code, REQUIREMENTS.md and the ADRs."
---

Refresh docs/ARCHITECTURE.md. Optional focus: $ARGUMENTS

1. Read docs/REQUIREMENTS.md, docs/DECISIONS.md, docs/adr/ and the source tree. Summarise;
   never print large files.
2. Rewrite docs/ARCHITECTURE.md (80 lines or fewer), keeping its headings:
   - Overview: 3 sentences.
   - Components: module, responsibility, file.
   - Decision flow: a mermaid sequenceDiagram of one expense: guard -> normalize -> extract ->
     policy -> question (flags) -> store -> POST, plus the follow-up answer -> re-decide loop.
   - State & data: SQLite tables, what is POSTed, how revisions and follow-ups are tracked.
   - Safety boundaries: each AGENTS.md rule -> enforcing file:line and its test; mark GAP if missing.
   - LLM providers & fallback. Failure modes. Decisions: link each ADR.
3. Describe only what exists in code; put intended parts under "Planned".
4. Reply with `git diff --stat docs/ARCHITECTURE.md` and the 3 biggest changes. Don't commit.
