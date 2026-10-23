# Coding standards

What the tools check is configured in `pyproject.toml`; this file holds the rest. The decisions behind it are in `docs/adr/`, the words in `GLOSSARY.md`.

## Checks before every commit

```bat
runtime\python.exe -m pytest
runtime\python.exe -m mypy
runtime\python.exe -m ruff check
```

All three must pass. Run `runtime\python.exe -m pytest -m slow` as well after touching the Kokoro provider or the build. mypy is strict for `ozvuchka/` and `tools/`; tests may leave functions unannotated, but their bodies are still checked. Silence a check (`# type: ignore[code]`, `# noqa: CODE`) only with the error code and a comment saying why.

## Language

- Code, comments, docs and commit messages are in English; everything the teacher sees is in Russian.
- Domain concepts are named as in `GLOSSARY.md`, capitalized in prose (Text, Paragraph, Voice, Narration), never with the synonyms it lists under _Avoid_. A concept the glossary lacks is a gap to settle with `/domain-modeling`, not a word to invent.

## Shape

- **The core** (`ozvuchka/core.py`) holds all program state and decides what happens, including what plays. It knows nothing about HTTP or the page. It is driven by commands and the page player's events and read through one snapshot.
- **The HTTP layer** (`ozvuchka/server.py`) only translates: a command or event per JSON body, the snapshot, audio, static files. No logic.
- **The page** (`ozvuchka/web/`) is a view (ADR-0003): plain HTML, CSS and JS, no framework, no build step. It renders the snapshot, plays what the core says and reports events. It keeps no state that must survive F5, and settings go through the core, not `localStorage`.
- **A Voice provider** is anything with the `VoiceProvider` shape (`ozvuchka/voices.py`); a new provider is one new module.
- **Data** lives in the program folder's `data/` (ADR-0001): no absolute paths, and every write goes to a temporary file followed by a rename.

## Threads

- Core state is read and changed only under the core's lock; the snapshot is copied out under it.
- One background thread synthesizes, one piece at a time. A Voice provider is never called while the core's lock is held.
- Commands return at once; progress is seen through the snapshot.

## Tests

- Tests check behaviour through public seams only:
  - the core: commands, events and the snapshot, built with `FakeVoiceProvider`, `FakeClock` and a temporary data folder;
  - the `VoiceProvider` contract, run against the fake and the real providers;
  - one HTTP smoke test.
- Internal modules (`ozvuchka/text.py`, storage, scheduling) have no tests of their own, so they can be reworked freely.
- Write tests first (`/tdd`). A test name reads as a sentence of the spec; expected values are literals from the spec or a worked example, never recomputed the way the code does it.
- Tests that use the real Kokoro are marked `slow`.
- The page has no automated tests: check it in the built-in browser against the real program.

## Python

- Annotate every function. Use `X | None`, built-in generics and `collections.abc`.
- Small immutable values are `@dataclass(frozen=True)`; module-internal names start with `_`.
- Every module starts with a docstring saying what it is for. Comments explain why, not what, and are rare.
- Errors the teacher may meet are shown in Russian (in the snapshot, on the page); the program does not crash on them.

## Dependencies

- Direct dependencies are pinned in `tools/requirements*.txt`; transitive ones are pinned in `tools/constraints.txt`, which is `pip freeze` of a working dev runtime (regenerate it after changing requirements).
- Packages are installed from wheels only. Comments in the requirements files stay ASCII.

## Commits

- An imperative summary line, then what changed and why.
- A commit that completes an issue says `Closes #N`; one that is part of it says `Part of #N`.
