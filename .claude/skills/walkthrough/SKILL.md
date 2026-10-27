---
name: walkthrough
description: "Give a whole-repo tour for the demo and code review: architecture, one expense traced, where each safety rule is enforced. Read-only."
---

Walk through the whole repo. Optional focus: $ARGUMENTS

First read AGENTS.md, docs/REQUIREMENTS.md, docs/DECISIONS.md, docs/PROGRESS.md, `git log --oneline`
and the source tree. Summarise; never print large files.

Reply with, briefly:
1. The system in 3 sentences: problem, users, what the system does.
2. Architecture: each module in 1 line, plus an ASCII flow of one expense.
3. One expense traced end to end with file:line: input -> guard -> normalize -> LLM extract ->
   policy -> question -> store -> POST -> SSE, and the follow-up answer -> re-decide loop.
4. Each AGENTS.md design rule: where code enforces it (file:line) and the test that proves it.
   Flag any rule with no enforcement or no test as a GAP.
5. Slices built so far (git log) and key decisions with the alternative each rejected.
6. Known limits and what comes next.
7. A demo script: 3-5 expenses to submit in the portal, including one manipulation attempt.
8. 5 likely reviewer questions, each with a short answer.

Do not change any code.
