# Озвучка (Simple English TTS)

An offline program that reads English texts aloud during English lessons. See `GLOSSARY.md` for the terms and `docs/adr/` for the decisions.

## Development

Build the local runtime (embeddable Python 3.12, packages, Kokoro model, spaCy model, pytest, mypy, ruff) into `runtime\` and `models\`. Needs internet; run it again after a failure, finished steps are skipped:

```bat
tools\build.bat dev
```

Run the tests (the real Kokoro tests are marked `slow` and skipped by default):

```bat
runtime\python.exe -m pytest
runtime\python.exe -m pytest -m slow
```

Check types and lint (settings in `pyproject.toml`; the rules the tools don't check are in `CODING_STANDARDS.md`):

```bat
runtime\python.exe -m mypy
runtime\python.exe -m ruff check
```

Start the program and open http://127.0.0.1:8770:

```bat
runtime\python.exe -X utf8 -m ozvuchka
```
