---
name: slice
description: "Build one feature as a single tested vertical slice, test first, then commit."
disable-model-invocation: true
---

Build this as one vertical slice: $ARGUMENTS

Follow AGENTS.md. Do these steps in order:
1. Acceptance bullets (from docs/REQUIREMENTS.md where possible).
2. Files and signatures. If it touches more than 3 files, stop and ask.
3. A failing test. Run pytest and show it fail.
4. The code: smallest change that makes it pass.
5. pytest output, all green.
6. 3 bullets: what changed, why, what could break. If an architectural decision was made,
   run /adr for it; if components or flow changed, run /arch.
7. Commit with a message that says why, not just what.
