@AGENTS.md
@docs/DECISIONS.md
@docs/PROGRESS.md
@ASSUMPTIONS.md

## Skills and agents
- `/spec <notes>`: discovery notes -> docs/REQUIREMENTS.md
- `/slice <feature>`: one vertical slice, test first, commit; `/checkpoint`: save PROGRESS.md, then /clear
- `/explain <file|function|diff>` and `/walkthrough [focus]` (whole repo): read-only interview prep
- `/adr <decision>`: docs/adr/NNNN-*.md + DECISIONS.md row; `/arch`: refresh docs/ARCHITECTURE.md
- `reviewer` agent: fresh-eyes review of `git diff HEAD` (correctness and safety only)

## Rules
- Record every new assumption in ASSUMPTIONS.md (Inferred vs Confirmed, with the source) as you make it.
- Never print large files; use head, a short summary script, or a subagent.
- When compacting, keep: files changed, the last test result, open decisions, the current slice.
