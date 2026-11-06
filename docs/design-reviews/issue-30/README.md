# Stage 3 Library — verification and handoff

> **Historical record:** the stage and its Issue are complete. Branch rules, pending
> statuses, localhost servers and next-session instructions below describe the work at
> that time, not current guidance. See the [current UI design specification](../../ui-design-spec.md).

Date: 2026-11-04. Branch: `experiment-2`.
Issue: [#30](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/30).
Baseline: `88b56ea`, with a clean working tree and no difference from the tracking branch.
Implementation and browser evidence commit: `3f9d1d0`; handoff identifier record:
`eeaf410`. The developer accepted stage 3 on 2026-11-04 after the requested manual
browser checks, reporting that everything was OK. Publication and Build verification
follow this acceptance; the final Build result is recorded on #30.

## Result and scope

Library rows retain the accepted warm surfaces, blue selection and persistent ellipsis
action. Titles take at most three visible lines, with the complete name in the DOM,
accessible button name and title tooltip. Ready Narrations are readable 14 px labels.
Their destructive actions now live in the row disclosure, alongside rename and Text
deletion, instead of competing with every ready label. Each removal names its Voice,
Speed and Text accessibly; its target is at least 44 CSS pixels high.

Only one row action disclosure stays open. Enter/Space open it, native Tab visits its
actions, Escape closes it and restores summary focus, and Tab leaving or an outside
click dismisses it. Closing on click rather than pointerdown is intentional: collapsing
a previous row before mouseup moves the next row out from under the pointer. Library
rebuilds preserve the open row and return focused row controls to the corresponding
title/summary, or to the first remaining Text/search after deletion.

An empty Library explains how to create a Text. An empty search result suggests changing
or clearing the query. Search does not replace the current editor or title while the
page stays open. Total storage is secondary and explicitly labelled as Library size.

No Core, HTTP or storage contract changed. Existing commands and native confirmations
remain. No autosave, audio, provider, queue, lifecycle or later-stage work was added.
No other branch or its Issues supplied code or requirements. Only #30 is updated
for stage 3 completion, after publication and a successful Build.

Changed files: `ozvuchka/web/app.js`, `style.css`, `index.html`, the Library paragraph
of `docs/ui-design-spec.md`, the #30 hardware entry in `docs/manual-checks.md`, and this
review directory. The preview tool and fixture provider are unchanged.

## Reproduction

From the repository root, in three terminals:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --long-title
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 0 --port 8772
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --long-title --port 8773
```

Open `http://127.0.0.1:8771`, `:8772`, or `:8773`. These run the real Core/HTTP/page
with FakeVoiceProvider (silent WAVs), 20/0/1 Texts, and two ready Narrations on the long
Text. Each Library lives in a unique `.cache/ui-design-preview/issue-28-*` directory;
the historical prefix does not denote another branch. The teacher's `data/` was never
opened or modified. Ctrl+C stops a runner and removes its disposable Library.

## Actual browser checks

Windows, Codex in-app browser, actual visible controls and read-only DOM measurements.
No static mock, external browser or browser-test dependency was used.

| Check | Observed result |
| --- | --- |
| 1280 × 720, 20 Texts, long title, two Narrations | Page 1280 × 720, Play bottom about 617 CSS px; editor and Play visible, no horizontal overflow. Three-line Library title and full accessible name. |
| 1440 × 900 | DOM measurements: page 1440 × 900, 20 rows, two ready labels, no overflow. No dedicated final screenshot retained at this size. |
| 1280 × 720, 0 and 1 Texts | Distinct empty guidance or single selected long-title row; editor/Play remain visible. |
| Empty search (`zzzz`) | Zero rows, explicit no-results message. Current Text content and full working title remain unchanged. Clearing search restores 20 rows. |
| Menu Enter/Space, Tab, Escape | Native disclosure opens; focus visits rename/deletion; Escape returns to summary. Tab past the last action closes the menu and reaches the next Text. |
| Switching row menus by pointer | The second menu opens and the first closes. An initial pointerdown collapse displaced the target; corrected and rechecked through actual clicks. |
| 390 × 844 | No horizontal page overflow. Menu, title and two ready labels fit inside the bounded single-scroll Library panel. First Escape closes row actions; second closes Library and focuses its summary. |
| Outside click and typed draft | Both panels close; unsaved editor value remains intact. |
| Narrow Text selection | Selected row gets `aria-current`, Library closes, editor receives focus and shows the chosen Text. |
| 640 × 360 CSS viewport | No horizontal overflow. Tab scrolls the deletion action into the panel; measured action height 44 px, bounds top 206/bottom 250. This is not actual 200% zoom. |
| Remove one Narration | Alice disappears, George remains, storage falls from 3.9 to 2.0 MB, menu stays open and focus returns to its summary. Enqueue recreates Alice through the existing command. |
| Delete sole Text (`:8773`) | Empty Library appears, working title becomes New Text, search receives focus. Only disposable data was deleted. |
| Playback regression | Play hides Library/editor and shows the existing transport and Paragraphs; return restores editor focus and the selected Text. |

Native-confirm removal commands did complete in the in-app browser. One pointer call
timed out, so success was established from the resulting row, ready labels, size and
focus, not from that tool response. No controllable native confirm dialog was exposed;
its cancel path was not verified. Rename reaches the existing handler, but this browser
reports `prompt() is not supported`; end-to-end title editing is not claimed. Application
dialogs remain stage 6 (#33), as explicitly allowed by #30 and the specification.
The developer subsequently completed the requested browser acceptance, including
rename, cancellation/removal and the new menus at 200% zoom, and reported no issues.
Browser version and window dimensions were not restated in this stage 3 report;
Chrome at 1280 × 720 and 200% was the requested setup. This user acceptance is separate
from the in-app browser evidence above.

Artifacts (browser capture raster sizes can differ from the measured CSS viewport):

- [20 Texts, 1280 baseline](library-1280.jpg)
- [Row actions, 1280 baseline](menu-1280.jpg)
- [Row actions, narrow viewport](menu-390.jpg)
- [Focused action, compact viewport](menu-640.jpg)
- [Empty Library](empty-1280.jpg)
- [Single long-title Text](one-text-1280.jpg)
- [Empty search with current Text retained](search-empty-1280.jpg)
- [One Narration removed](narration-removed-1280.jpg)
- [Sole Text removed](text-removed-1280.jpg)

## Checks and remaining limits

- `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue30-final`: **109 passed, 6 slow tests deselected**.
- `runtime/python.exe -m mypy`: passed (23 source files).
- `runtime/python.exe -m ruff check`: passed.
- `git diff --check`: passed.

These checks are rerun before the implementation commit. Slow tests and ZIP smoke do
not apply because provider/build/launcher code is unchanged. No CSS/DOM assertion
tests were introduced.

Stage 3 browser acceptance, including genuine 200% zoom, is satisfied by the developer's
2026-11-04 report above. School-laptop responsiveness remains open under #30 in the
single manual checklist; no hardware results are claimed. This deferred hardware check
does not block completion of the bounded Library stage.

Inherited transition/reload limitations remain: switching Texts does not flush unsaved
edits; after F5 with a query hiding the current Text, the working title falls back to
the first content line until that Text is visible in search again. Deleting the current
Text leaves its editor content as an unsaved draft. These existing behaviours were
observed, not changed into a new persistence protocol. Stages 6–9 own dialogs and save
guarantees; do not add autosave or audio changes as follow-up to this Library stage.

## Next session

Read AGENTS.md, CODING_STANDARDS.md, GLOSSARY.md, ADR-0001/0003,
`docs/ui-design-spec.md`, this handoff and the live next-stage Issue. Stage 3 is accepted;
check #30 for the publication/Build result. Do not start stage 4 automatically. Stage 4
is #31 (Voice choice and Narration queue); it remains untouched.
