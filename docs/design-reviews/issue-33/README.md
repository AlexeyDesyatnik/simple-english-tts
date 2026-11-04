# Stage 6 application dialogs and keyboard — verification and handoff

Date: 2026-11-04. Branch: `experiment-2`.
Issue: [#33](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/33).
Baseline: `c84d1a5`, clean tree, tracking `origin/experiment-2` with no divergence.
Status: implementation ready for developer acceptance; #33 remains open.
Implementation and browser evidence: `bc5a4a4` (local, not pushed).

## Changes and boundaries

- `ozvuchka/web/index.html`, `app.js`, `style.css`: replace native prompt/confirm with
  one labelled HTML `dialog`, shown with `showModal()`. Rename selects the existing
  title initially; destructive confirmation initially focuses Cancel. Background is
  inert and explicit Tab/Shift+Tab wrap keeps keyboard focus among visible enabled
  dialog controls. Escape and Cancel dismiss without dispatching a command.
- The workspace exposes `Изменить название` for a saved Text in preparation. An empty
  or whitespace-only title shows a Russian inline alert, marks the input invalid,
  and preserves the exact input. Server errors keep the dialog/input available.
  During a submitted command controls temporarily disable to prevent duplicate
  submission; Escape cannot retract an already submitted operation.
- Deletion names the Text or the Voice/Speed Narration, explains Library/queue/playback
  consequences and whether the Text stays. Text deletion explains irreversibility.
  The existing Core commands are used. After successful deletion of the open Text,
  the editor clears together with the selection rather than retaining deleted content.
- Closing returns to the workspace title button or the row's action summary. If a row
  disappears after deletion/filtering, use the first remaining Text, then search if
  none remain. If the narrow Library closed when the modal opened, return to its
  summary. Normal focus scrolling keeps the destination visible.
- Queue disclosure now also closes with Escape to its summary. Global shortcuts
  respect prevented/composing events, modal state, native controls, interactive ARIA
  widgets and editable/tabbable content. Existing physical `event.code` mappings for
  Space, left/right, PageUp/PageDown and KeyR remain. Native button/summary Space,
  select arrows and editor keys retain their own behaviour. Paragraph Enter/Space
  still invokes the existing play-from command.
- `ozvuchka/core.py`: additive `text.title` snapshot field, read under the existing
  lock from the unfiltered Library. Workspace title must remain correct when a rename
  removes the Text from the search results, including after F5. No command or save
  acknowledgement contract changes. `tests/test_core.py` adds the public-seam
  regression (first failed with missing `title`, then passed).
- `docs/manual-checks.md`: #33 school laptop and presenter checks in the single list.

No other branch was used as an implementation source. No changes to audio planning,
player events, provider/synthesis, ADR-0004 interruption, queue ordering or Start delay.
The accepted completion screen and `playback.ended_at` remain. Stages 7–9 (save
acknowledgement, autosave, safe transitions and reload protection) are not implemented.
No framework, dependencies or browser test stack were added.

## Isolated preview and real speech

Use the **fresh final Core** at [127.0.0.1:8788](http://127.0.0.1:8788/).
It has a new disposable Library below `.cache/ui-design-preview/issue-28-ggpr_yjy`,
20 Texts, a long title, and ready **real Kokoro Alice/George** Narrations. The final
page is in preparation, modal closed, with Play ready. The user Library was untouched.
Earlier :8785 is an older Core without `text.title`; do not use it for acceptance.

Reproduce from the repository root, choosing an unused port and a fresh process:

```powershell
New-Item -ItemType Directory -Force .cache/real-preview-temp | Out-Null
$env:TEMP = (Resolve-Path .cache/real-preview-temp).Path
$env:TMP = $env:TEMP
runtime/python.exe -X utf8 tools/ui_design_preview.py --real-voice --long-title --port 8788
```

The existing preview seam also served separate disposable fake Libraries:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --long-title --port 8786
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --no-ready --piece-seconds 60 --port 8787
```

The fake generates silence. Its waiting and destructive checks establish command/UI
behaviour only. Real-provider pages establish actual speech assets and playback
interaction; no agent listening-quality or output-device judgment is claimed.
Temporary Library changes disappear when the corresponding process exits.

## Actual browser verification

Windows, ChatGPT in-app browser, real page/Core/HTTP, visible controls and keyboard
input; DOM observations and retained screenshots. No static mock.

- Rename from workspace and row menu: prefilled/selected input; whitespace submission
  preserves three spaces and shows the Russian error; Tab/Shift+Tab wraps through
  input/Cancel/Save. Cancel and Escape restore the origin. Enter saves the title.
  Name-field arrows/PageDown and R/К text input do not start playback.
- Delete confirmation starts on Cancel; Tab/Shift+Tab cycles Cancel/Delete. Cancel and
  Escape preserve data. Disposable Text deletion reduced 20 rows to 19 and focused a
  remaining Text. Deleting the selected Text clears the editor and title selection.
- Disposable Alice Narration deletion left George ready and the Text intact; focus
  returned to its row summary. Deleting the only Text while preparation was queued
  left an empty Library/queue, empty editor and focus in search. Existing shared-piece
  retention and cancellation implementation are not redesigned here.
- A rename that removed a row from the active search returned focus to search.
  On final Core, workspace rename with search `Saturday` changed the title to
  `Проверка переименования при поиске`; the Library became empty, and F5 retained
  the correct workspace title. Cleared search and restored the long title afterwards.
- Row summaries open with Enter; rename activates with Enter; Escape returns from
  dialog to row summary and closes a row disclosure. Narrow Library opens with Enter
  and closes on focus leaving into a modal; Escape/cancel returns to Library summary.
- Voice summary Enter, arrows among Voice choices without selecting, Space confirming
  Alice, Escape cancelling: selection/summary focus behaved correctly. Speed select
  ArrowDown and editor End/R/Backspace/PageDown kept native behaviour without Play.
  Queue and keyboard-help Enter/Escape close to their own summaries.
- Real Kokoro: Play/Pause/Continue; Space on the native transport activates that button.
  With background focused, ArrowRight moved from paused 1/6 to 2/6 and started speech;
  Space paused. PageDown moved to 3/6, PageUp to 2/6, ArrowLeft to 1/6; KeyR repeated.
  ArrowRight/PageDown on the focused Continue button and R on help summary did not
  invoke global playback commands. Paragraph Enter/Space started that Paragraph.
- Fake waiting: help opened/closed, background Space paused, KeyR restarted waiting;
  right/PageDown/PageUp/left moved 1→2→3→2→1 while waiting. No silent check is claimed
  as audible acceptance. Real physical Russian-layout R and presenter mappings still
  need the developer/hardware check; browser KeyR simulation verifies the physical-code
  path, not a real keyboard-layout switch.
- On the **fresh final real Core**, Space on the final readable Paragraph started it;
  natural completion retained reading, Play, `Текст прочитан`, 6/6; F5 retained that
  screen. Return explicitly restored preparation/editor focus.
- 1440×900 and 1280×720: long title, 20 Texts, editor and primary action fit initially
  (Play bottom about 669 CSS px); no page horizontal overflow. 390×844: long-title
  rename/delete dialogs wrap, controls remain reachable, no horizontal page overflow.
  At 640×360 the invalid rename dialog and both actions fit (bottom about 337px).
- **Genuine 200% zoom is not verified in IAB.** Browser Ctrl+Plus left viewport/DPR/
  visual scale unchanged; the other attempted zoom key forms were unsupported. The
  640×360 view is reduced available space, not browser zoom. Stage 5's accepted zoom
  does not substitute for this stage's new dialogs. Developer acceptance at real 200%
  remains explicitly required.

## Retained evidence

| View | Screenshot |
| --- | --- |
| Final fresh Core, invalid rename and visible focus | [1280×720](rename-error-1280.jpg) |
| Preparation, long title and 20 Texts | [1440×900](preparation-1440.jpg), [1280×720](preparation-1280.jpg) |
| Destructive Text confirmation | [1280×720](delete-text-1280.jpg) |
| Narration confirmation with Cancel focus | [390×844](delete-narration-390.jpg) |
| Final fresh Core, long-title deletion, cancelled | [390×844](delete-long-390.jpg) |
| Rename on narrow screen | [390×844](rename-390.jpg) |
| Invalid rename at reduced height, not 200% zoom | [640×360](compact-640.jpg) |
| Real Kokoro paused reading | [1440×900](playback-real-1440.jpg) |
| Fake waiting, silent | [waiting screenshot](waiting-1280.jpg) |
| Final fresh Core, completion retained after F5 | [1280×720](completed-fresh-1280.jpg) |

Some IAB captures are visibly soft. Earlier screenshots precede the additive title
snapshot field; the final error, long-title deletion and completion screenshots use
:8788. These interactions/layouts are unchanged by the additive field.

## Checks and developer acceptance

- `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue33-final`: **116 passed,
  8 slow tests deselected**.
- `runtime/python.exe -m mypy`: passed, 23 source files.
- `runtime/python.exe -m ruff check`: passed.
- `git diff --check`: passed.
- No slow/provider/build suite required: those implementations were not changed.
  No push or CI inspection has been performed.

Developer acceptance on :8788:

1. Rename from workspace and Library. Submit an empty/whitespace title; inspect the
   Russian error and retained input. Tab/Shift+Tab, Cancel and Escape should keep/return
   focus predictably. Save a new title, also with a Library search hiding that Text.
2. On disposable preview data only, cancel and confirm Narration/Text deletion; inspect
   exact names/consequences and returned focus, including deletion of the last result.
3. Open/close Library, row actions, Voice chooser, queue and reading help by keyboard.
   Start real speech; use native controls while focused, then click the reading
   background for Space/arrows/PageUp/PageDown and physical R in Russian layout.
   Verify heard Paragraph, highlight and pause/resume/repeat. After natural end,
   reading should stay open through F5 until `К редактированию`.
4. In a normal browser with **actual 200% zoom**, inspect both dialog types, long titles,
   error text, focus outline and access to both buttons. Narrow layout may scroll
   vertically; controls must not clip or cause horizontal page overflow.

Hardware-only checks remain in `docs/manual-checks.md`; none were marked complete.
Do not close #33 or start stage 7 before developer acceptance. Ask separately before
push and CI. After acceptance and an authorized successful push/CI, close #33.
