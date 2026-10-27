---
name: checkpoint
description: "Save progress to docs/PROGRESS.md and commit so the session can be cleared safely."
disable-model-invocation: true
---

1. Run `.venv/bin/python -m pytest -q` and note the result line.
2. Rewrite docs/PROGRESS.md in 30 lines or fewer with these headings:
   Current slice, Done, Next, Gotchas, Last test result.
3. Commit with `git add -A && git commit -m "docs: checkpoint progress"`.
4. Reply exactly: "Safe to /clear".
