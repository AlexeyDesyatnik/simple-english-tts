# Stage 2 preparation workspace — verification and handoff

Date: 2026-11-04. Branch: `experiment-2`. Issue: [#29](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/29).
Baseline: `aca9918`, following `289ea5b`. Stage 1's visual direction was explicitly
accepted by the developer on 2026-11-03; that approval is recorded in the #28 handoff.

## Result and boundary

The preparation workspace implementation (`aa66901`) has passed its browser layout
acceptance, including genuine 200% zoom reported by the developer on 2026-11-04:
Chrome 150, window 1280 × 720, all controls accessible and no horizontal scrolling.
The in-app browser checks below remain separate evidence; their smaller viewport
was not a substitute for the developer's genuine zoom check. GitHub Issue state has
not been changed by this acceptance record. School-laptop checks remain pending.
Do not automatically begin stage 3. This stage changed no Core/HTTP contracts, saving
behavior, audio scheduling, Voice provider, queue semantics or application lifecycle.

The inherited wide workspace keeps the Library at 300 CSS px and bounds its content
against viewport height, with the Text central in the right column. The list alone
scrolls on desktop; Library growth does not push down the editor or actions. The
desktop working title is constrained to two lines; its complete text is in the DOM,
accessible heading name and title tooltip. The editor keeps its permanent Text label,
Paragraph hint, Voice/Speed summary and the two existing preparation actions.

Below 960 CSS px the Library starts closed. Its contents open as a non-modal disclosure
above the workspace, so the editor's document position remains unchanged. The panel
has one bounded scroll area including its tools and Text rows. This avoids a tiny
independently scrolling list in short windows. Escape closes it and focuses the
disclosure summary; outside pointer input and focus moving outside also close it.
Choosing a Text or New Text closes it and restores editor focus. Opening/closing the
disclosure leaves typed content, selection and editor scroll intact. These are view
interactions only; no localStorage or new save protocol was introduced.

## Changed files

- `ozvuchka/web/index.html`: wrapper for the disclosed Library contents.
- `ozvuchka/web/style.css`: bounded sidebar, narrow overlay disclosure with one scroll area, desktop title limit.
- `ozvuchka/web/app.js`: disclosure dismissal/focus, narrow Text navigation, full-title tooltip.
- `tools/ui_design_preview.py`: optional `--long-title` fixture flag, still isolated from the teacher's Library.
- `docs/ui-design-spec.md`: concrete stage 2 layout decisions.
- `docs/design-reviews/issue-28/README.md`: recorded stage 1 acceptance.
- `docs/manual-checks.md`: school-laptop check for #29.
- This directory: retained screenshots and handoff.

## Reproduction

From the repository root, run:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py
```

Open `http://127.0.0.1:8771`. This is the actual page against Core/HTTP, seeded with
20 Texts, a skipped Paragraph and two ready Narrations for the current Text. The
existing FakeVoiceProvider produces silent WAVs. The unique disposable Library lives
under `.cache/ui-design-preview/issue-28-*`, never `data/`; the runner prints its path
and cleans it on Ctrl+C. Its historical `issue-28-` prefix is only a fixture name.

Additional fixtures used:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 0 --port 8772
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --long-title --port 8773
```

## Actual browser checks

Windows, Codex in-app browser; no native Chrome interaction was used in the resumed
verification. No static mock or browser-test dependency was added. Initial exploration
was on 2026-11-03, with final checks and screenshots on 2026-11-04.

| Check | Observed result |
| --- | --- |
| 1280 × 720, 20 Texts | Page dimensions exactly 1280 × 720; no initial page scrolling. Editor outer height about 205 px, seven text lines at line-height 25.6 px; Play bottom about 583 px. |
| 1280 × 720, empty Library | Same editor height and Play position, no page overflow. |
| 1280 × 720, one Text with a very long title | Title takes two lines, complete title available; Play bottom about 617 px, page remains 1280 × 720. |
| 1440 × 900, long title | Two columns, editor and Play visible; page remains 1440 × 900. |
| 390 × 844 preparation | Library initially closed; controls wrap, vertical scrolling allowed, no horizontal overflow. |
| 390 × 844, disclosure with an unsaved draft | Content and selection (510, 510) unchanged; editor scroll stays 0 and document-top position stays about 525 px. Native focus may scroll the page to a requested control; disclosure itself does not change layout. |
| Escape | Library closes and focus returns to its summary. |
| Tab from final Library row | Focus reaches the Voice disclosure and the Library closes. |
| Outside pointer input | Clicking the app heading closes the Library. |
| 640 × 360 CSS viewport | No horizontal page overflow. Found and fixed a 29 px list area in the initial implementation; the panel now has one scroll area, and a Text can be chosen through its visible row. This is not a genuine 200% zoom test. |
| Genuine 200% browser zoom, developer check, 2026-11-04 | Chrome 150, window 1280 × 720: developer reports that everything is accessible and there is no horizontal scrolling anywhere. OS was not specified in the report. |
| Narrow Text selection | Library closes, selected Text appears, editor receives focus. |
| Playback regression | Preparation has Play/enqueue only and no duplicate Paragraph list. Play/Pause enters Playback mode, hiding Library/editor; return restores the Text and editor focus. |

The native rename prompt could not be used in the in-app browser (`prompt() is not
supported`); the long-title check therefore uses the deterministic fixture flag.
Replacing native dialogs belongs to stage 6, not this layout stage. No unrelated
dialog or persistence work was folded into this implementation.

Artifacts:

- [Preparation, 1280 × 720, 20 Texts](preparation-1280.jpg)
- [Preparation, 390 × 844](preparation-390.jpg)
- [Open Library, 390 × 844](library-390.jpg)
- [Preparation, 640 × 360 CSS viewport, full page](preparation-640.jpg)
- [Empty Library, 1280 × 720](empty-1280.jpg)
- [Long title, 1280 × 720](long-title-1280.jpg)
- [Long title, 1440 × 900](preparation-1440.jpg)

## Required checks and remaining acceptance

- `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue29-20261104`: **109 passed, 6 slow tests deselected**.
- `runtime/python.exe -m mypy`: passed.
- `runtime/python.exe -m ruff check`: passed.
- `git diff --check`: passed.

The repository-local pytest base directory avoids the system-temp sandbox restriction
already encountered in stage 1. Production paths are unchanged. Slow/provider/build
checks do not apply to this change. No CSS/DOM assertion tests were introduced.

Genuine 200% zoom acceptance is satisfied by the developer's report above; it no longer
blocks browser layout acceptance. School-laptop responsiveness remains unticked in `docs/manual-checks.md`.
The #28 projector/presenter checks also remain pending. Actual Linux/macOS font
rendering is unverified.

Unsaved edits still have the inherited transition/reload limitations: Library opening
preserves the editor, but selecting a different Text is not a flush-before-navigation
guarantee. Autosave and reliable save acknowledgement remain stages 7–9. Detailed
Library empty/search states and actions remain stage 3; Voice/queue refinements stage 4;
full Playback mode behavior stage 5; dialogs and integrated keyboard journeys stage 6.

## Next session

Implementation commit: `aa66901`; this handoff also contains the subsequent developer
acceptance record for 200% zoom.
Read AGENTS.md, CODING_STANDARDS.md, GLOSSARY.md, ADR-0001/0003, the UI specification,
#29 and this handoff. The 200% browser acceptance is complete. Hardware checks remain
in the manual checklist. Stage 3 is #30 and should be a separate bounded task.
Other branches and their Issues remain unrelated; no code or requirements were copied
from them. This session did not post comments or change Issue states on GitHub.
