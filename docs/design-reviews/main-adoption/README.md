# Adopt the accepted UI as main

Date: 2026-11-04. The developer selected the complete, accepted `experiment-2`
implementation as the new main, retiring the alternatives on `main` and
`experiment`. The one retained change from the former main is NumPy 2.3.5
compatibility for older processors (#26).

## Source states and history

| Source | Commit | Archive tag |
| --- | --- | --- |
| Previous main | `4b3ede308d0a30a277ea2ecf86ccaab0850c5a03` | `archive-main-before-adoption-20261104` |
| Retired experiment | `765db6d` | `archive-experiment-before-adoption-20261104` |
| Accepted experiment-2 | `cf29c0d52a4b17b2185bf9483f3b3556cc669540` | `archive-experiment-2-before-adoption-20261104` |

Preparation branch: `codex/adopt-experiment-2`, based on accepted `experiment-2`.
Copy only the three-file change from `4b3ede3`: NumPy pins in
`tools/requirements.txt` and `tools/constraints.txt`, plus its README explanation.
The README overlap was resolved by retaining that explanation and describing the
accepted UI as the main implementation. The specification receives a historical
adoption note; completed stage records remain intact. No application, provider,
test, launcher, build script or workflow code differs from `cf29c0d`.

The main adoption uses a merge commit with previous main as first parent and the
prepared candidate as second parent, but with its complete tree taken from the
candidate. This preserves ancestry and permits a normal fast-forward push of
main without carrying the rejected implementation into the resulting files.
No force push or release tag is needed. Archive tags are retained before retiring
local/remote experiment branches. They do not start with `v`, so they do not
publish a GitHub Release.

## Verification

The existing developer runtime was rebuilt with `tools/build.bat dev`. All
constraint versions were checked against installed package metadata: only NumPy
changes, from 2.5.4 to 2.3.5. No other dependency upgrade was introduced.
`pip check` reports only the known, deliberately omitted `docopt` dependency of
the unused num2words CLI (`tools/requirements-nodeps.txt`); application synthesis
uses the existing supported library path.

Local checks on Windows:

- pytest: 133 passed, 8 slow deselected.
- Real Kokoro slow tests: 8 passed, 133 deselected.
- mypy: 23 source files, no issues; ruff and diff check passed.
- `tools/build.bat release -Version ui-adoption-numpy235`: passed; archive 177 MB.
  ZIP inspection confirmed NumPy 2.3.5 and exact candidate application sources.
- Launcher smoke test: passed. Page served after 1.2 s, second launch reused the
  running instance, real `Hello.` speech was 0.85 s, page-close ended the program,
  and the log/data stayed inside `data/`.

Set `TEMP` and `TMP` to the repository's `.cache/tmp` before build, slow tests and
smoke testing. Initial sandbox-default temporary directories denied DLL/metadata
writes; repeating with this writable temporary directory passed. This was an
execution environment problem, not a change to the provider or NumPy contract.

Actual page check: ChatGPT built-in Chromium on Windows, real Core/HTTP/Kokoro
with NumPy 2.3.5, `tools/ui_design_preview.py --texts 1 --no-ready --port 18743
--real-voice`. Disposable Library suffix `issue-28-9qwwir0l`; teacher data untouched.
Replaced the Text with two English Paragraphs and immediately pressed Play.
The browser reached `Текст прочитан`, highlighted Paragraph 2 of 2, returned to
editing, and restored the exact saved Text on reload. The test server was stopped.
[Playback evidence](numpy235-playback.jpg). The UI itself is unchanged, so the
previous accepted layout/keyboard/200% checks are not repeated as a new design
acceptance matrix.

## Hardware handoff

The earlier v0.2 + NumPy 2.3.5 experiment was accepted on Athlon II X2 250 and an
11th-generation Core i5 (#26). This is prior evidence, not a claim that this new
combined archive has already run on the old CPU. The integrated old-CPU check is
in `docs/manual-checks.md` alongside the existing school hardware checklist.

Use a fresh disposable copy of the new main archive on the old computer: start
the launcher, paste a short English Text, synthesize/play it, close/reopen, and
confirm the Text remains and `data/ozvuchka.log` exists. Expect no NumPy startup
failure. No benchmark or exhaustive UI reacceptance is required.
