# Stage 1 visual review and fresh-session handoff

Date: 2026-11-03. Branch: `experiment-2`. Issue: [#28](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/28).

## Review gate

**Awaiting the developer's visual review. Do not begin stage 2 or close #28.**
The developer approved the transport arrangement described below as a bounded visual
correction; this is not approval to start stage 2 or close #28. The screenshots below
remain the candidate for overall review. Other branches
and their Issues are independent alternatives and are not inputs to this work.

## Scope and decisions

Stage 1 establishes a live visual direction in the existing page. Warm surfaces, dark
text, blue selection and primary controls, yellow current Paragraph with a blue edge,
small tokens, 44 px control targets, and the specified platform-neutral system font
fallbacks form the candidate. No remote assets, font installation or UI build is needed.

Preparation uses a 300 px Library and a current Text surface within a 1440 px workspace.
Below 960 px the Library starts collapsed. The editor has a permanent label and an
explanation; the duplicate Paragraph list is hidden. Voice choice is disclosed while
selected Voice and Speed remain visible. The queue is a disclosure below the controls.
Row actions use a visible SVG disclosure; ready Narrations have readable labels and
named delete actions. Detailed Library/queue/dialog behavior remains for later stages.

Playback mode hides preparation, uses the current Core state for Pause/Continue, shows
readable Paragraph position, and exposes existing Paragraph commands. Return uses Stop.
The reading measure is 68ch; Text size remains the existing Core setting. Current
Paragraph scrolling accounts for the sticky transport and tall Paragraphs. Native
controls retain their keyboard input; readable Paragraphs support Enter/Space. Focus
moves between the primary transport actions and returns to the editor on Stop.

### Approved transport correction, 2026-11-03

The developer requested a more logical button order and a distinct exit from Playback
mode, then approved this proposal: previous Paragraph, Pause/Continue, next Paragraph
form one group; `Повторить абзац` follows with a gap. `К редактированию` is in the Text
header with an exit SVG, explanatory tooltip and a border below the header. On narrow
windows the exit remains on its own row above the transport. The Text size tools wrap
beside repeat below the navigation group. The specification now records this arrangement
for stage 5 (#32); stage 6 (#33) still completes keyboard/focus journeys.

Only HTML/CSS and documentation changed in this correction. Existing commands, primary
action state wiring and audio behavior are unchanged. Rechecked the actual page with
the isolated 20-Text fixture at 1280 × 720 and 390 × 844: the controls are visible in
the agreed order, no horizontal overflow, Pause/Continue works, and exit returns the
Text and editor focus. Updated `playback-1280.jpg` and `playback-390.jpg` accordingly.
Correction checks: pytest with `--basetemp=.cache/pytest-issue28-transport-20261103`
passed (109 tests, 6 slow tests deselected); mypy, ruff and `git diff --check` passed.

No Core/HTTP contract, synthesis, audio scheduling, Voice catalogue, queue semantics,
heartbeat or persistence protocol changed. Saving still happens through the existing
`set_text` before Play/enqueue. The page explains this and identifies a changed draft;
it does not claim a confirmed saved state. There is no autosave.

## Files and reproducible setup

- `ozvuchka/web/index.html`, `style.css`, `app.js`: visual structure, tokens and presentation wiring.
- `tools/ui_design_preview.py`: disposable real Core/HTTP fixture using the existing FakeVoiceProvider.
- `tests/test_server.py`: existing HTTP smoke check uses the Russian primary-action label.
- `docs/manual-checks.md`: hardware-only checks for this independent track.
- This directory: retained screenshot artifacts, verification and handoff.

Run from the repository root:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py
```

Open `http://127.0.0.1:8771`. The runner seeds 20 Texts, a long title, one skipped
Paragraph and six readable Paragraphs, and ready Alice/George Narrations for the
current Text. FakeVoiceProvider emits silent WAVs, so this checks the real player flow,
not speech quality. Use Play, Pause, navigation and Stop through the page. The runner
prints its unique `.cache/ui-design-preview/issue-28-*` Library, which is removed on
Ctrl+C. It never opens the teacher's `data/` folder. It needs the dev runtime and tests.

For separate empty/single-Text checks:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 0 --port 8772
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --port 8773
```

## Actual browser verification

Environment: Windows, Codex in-app browser. No Linux/macOS or native Edge app-window
claim is made. Browser interactions used the actual page against the servers above,
with screenshots and DOM geometry checks; no static mock or browser-test dependency.

| Check | Result |
| --- | --- |
| 1280 × 720, 20 Texts, long title, two ready Narrations | Editor and Play initially visible; editor height about 205 CSS px, seven lines; Play bottom about 583 px. No page horizontal overflow. |
| 1440 × 900 preparation | Bounded Library and current Text remain side by side; primary action visible. |
| 390 × 844 preparation and Playback mode | Controls wrap, Library disclosure starts closed, no horizontal page overflow. Vertical scrolling is allowed. |
| 640 × 360 CSS viewport | Reflow inspected, no horizontal overflow. This is not a genuine browser zoom test. |
| 0 and 1 saved Text | Actual page inspected at 1280 × 720; editor and primary action remain visible. |
| Play / Pause / Continue / return | Real Core commands change modes and labels; current readable Paragraph is yellow, skipped instruction remains labelled. Editor returns with its Text. |
| Previous Paragraph | Existing command moves playback back and updates readable position. |
| Voice disclosure and George sample | List expands; sample action leaves Alice selected (silent test sample). |
| Narrow Library disclosure with unsaved draft | Draft content and editor selection remain intact across disclosure changes. |
| Empty search result | Current Text/editor/title remain in place. Explicit empty-result copy is deferred to stage 3. |
| Reload during playback | Existing browser audio restriction pauses playback and shows the Russian Continue instruction; continuing works. |
| Primary control focus | Focus transfers from Continue to Pause and back; return focuses the editor. |
| Text size 80 px at 1280 × 720 | Panel remains accessible, no horizontal page overflow; current Paragraph starts below the sticky transport. Returned to 22 px through the existing buttons. |
| Browser warnings/errors | Captured browser warning/error log was empty during the checked flow. |

Screenshots are actual page captures, retained as project files:

- [Preparation, 1280 × 720](preparation-1280.jpg)
- [Playback mode paused, 1280 × 720](playback-1280.jpg)
- [Preparation, 390 × 844](preparation-390.jpg)
- [Playback mode paused, 390 × 844](playback-390.jpg)
- [Preparation, 1440 × 900](preparation-1440.jpg)
- [Preparation, 640 × 360 CSS viewport, full page](preparation-640.jpg)
- [Large Text, 1280 × 720, before the transport correction](playback-large-1280.jpg)

## Checks

`runtime/python.exe -m pytest --basetemp=.cache/pytest-issue28-final-20261103`: **109 passed,
6 slow tests deselected**. The plain required pytest command first failed during fixture
setup because sandbox denied access to its system temporary directory; the repository
base-temp run passed the same test selection without changing tests or production paths.
`runtime/python.exe -m mypy`: passed. `runtime/python.exe -m ruff check`: passed.
Provider/build behavior is unchanged, so slow/release checks do not apply.

## Remaining limits and next session

- Real browser zoom at 200% is unverified: the in-app browser's Ctrl-plus input did not
  change its zoom. The 640 × 360 check only covers a corresponding reduced CSS area.
- The full integration matrix (loading/unavailable/error states, queue cancellation,
  keyboard/presenter journeys, persistence races and all Text sizes at each viewport)
  belongs to the later bounded stages. Native rename/delete prompts are still present.
- Empty Library/search messages, detailed Library actions and Voice/queue refinements
  are unfinished. Core's filtered Library snapshot omits the current title when search
  excludes it; after F5 in that state, the heading falls back to the first content line.
  Do not add a new Core contract here to hide this limitation.
- Existing unsaved-edit transition/reload limitations remain. There is no automatic
  save, confirmed save acknowledgement, flush-on-navigation or page-hide guarantee.
- Projector readability, real presenter hardware and school-laptop performance are
  unticked in the single manual checklist. Cross-platform font stacks were implemented;
  actual fallback rendering on Linux/macOS remains unverified.

The implementation commit includes this handoff and its artifacts; resolve its hash
with `git log -1 --format=%H -- docs/design-reviews/issue-28/README.md` (also reported in
the session delivery). Read AGENTS.md, CODING_STANDARDS.md, GLOSSARY.md, ADR-0001/0003,
`docs/ui-design-spec.md`, #28 and this handoff. First obtain/record the developer's
visual review. Only after direction approval should a fresh bounded session read #29
and start stage 2. Do not close #28 before that confirmation.
