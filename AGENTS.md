# AGENTS.md

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `AlexeyDesyatnik/simple-english-tts` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Manual checks

`docs/manual-checks.md` is the one list of what the developer checks by hand on the school laptops, the projector or in class. Work that leaves such a check (an acceptance criterion no test, CI run or browser check can cover) adds it there in the same commit; an item is deleted once it is ticked and its issue is closed. Read it before saying what is left to check.

### Coding standards

`CODING_STANDARDS.md` at the repo root: the checks to run (pytest, mypy, ruff) and the rules the tools don't check.

### Publishing completed work

After implementing a task, commit the changes, then obtain the user's permission
to push and check CI. Once permission is granted, push the current branch and
wait for GitHub Actions for the pushed commit to finish. Inspect any failures,
fix issues caused by the changes, and verify CI again. Report the final result
with a link to the run. If the user has already authorized push and CI checks
for the current task, proceed without asking again.
