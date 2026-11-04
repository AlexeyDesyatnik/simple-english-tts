# AGENTS.md

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `AlexeyDesyatnik/simple-english-tts` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Manual checks

`docs/manual-checks.md` is the one list of what the developer checks by hand on the school laptops, the projector or in class. Work that leaves such a check (an acceptance criterion no test, CI run or browser check can cover) adds it there in the same commit; an item is deleted once it is ticked and its issue is closed. Read it before saying what is left to check.

After completing any work stage that needs developer manual verification or acceptance,
include the concrete checks in the final reply without waiting for the developer to ask.
Give the setup, actions and expected results, including an isolated test Library where
needed. Distinguish checks already performed by the agent from checks left for the
developer. A link to a handoff or checklist supplements these instructions; it does not
replace them. This applies to browser acceptance as well as hardware-only checks;
keep hardware-only items in `docs/manual-checks.md` as required above.

Keep implementation and manual acceptance proportional to this simple playback
application. Texts are normally copied from another source; rare loss of the latest
unconfirmed edits in an edge case is acceptable. Reliable ordinary autosave is enough;
do not expand this into a crash-proof editor or add recovery machinery without a
concrete need. Give the developer a short everyday-use check. Agent-run delay proxies,
fault injection and exhaustive lifecycle matrices are not routine developer acceptance.

### Coding standards

`CODING_STANDARDS.md` at the repo root: the checks to run (pytest, mypy, ruff) and the rules the tools don't check.
