# Stage 4 Voice choice and Narration queue — verification and handoff

Date: 2026-11-04. Branch: `experiment-2`.
Issue: [#31](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/31).
Baseline: `b3b7b50`, clean working tree, identical to `origin/experiment-2`.
Implementation and browser evidence commit: `afae5e2`. This follow-up records its
identifier only; the implementation has not been published and CI has not been queried.
Stage 3 was accepted; its Library implementation and visual direction are preserved.
Stage 4 is awaiting developer acceptance. Do not close #31 or start stage 5 yet.

## Result and scope

Selected Voice, its availability and the native Speed picker remain visible beside the
editor. Normal Speed remains explicitly named `1× — обычная`. The Voice disclosure
opens a bounded, scrolling panel over the editor without changing its layout. Explicit
choice buttons choose a Voice; separate, named buttons play Voice samples without changing
selection. Rows show loading, available or unavailable states in text. Samples remain
usable during loading/unavailability, as the existing Voice provider contract allows.
Sample loading, playing, completion and retry guidance have their own status, independent
of polled synthesis feedback. Late sample promises cannot overwrite a newer sample's status.

Voice choice buttons expose the committed selection through `aria-pressed` and visible
`Выбран` text. Arrow keys move focus without selecting; Enter/Space or a click confirms,
closes the panel and focuses its summary. Escape closes without changing the Voice.
Tab leaving it and outside clicks close it. Availability updates keep the same buttons
rather than rebuilding them. Narrow rows wrap into a single column, with 44 px selection
and sample targets. This interaction was revised after the developer review below.

The queue summary is always present, including `пуста`, below the primary action. Details
show existing order, Voice/Speed, synthesizing or queued state, and existing time estimates;
an unknown estimate is explicitly labelled. Existing current-Text ready Paragraph counts
and ready Narration feedback remain in the status area. No new per-queue Paragraph counts
or estimates are inferred. Cancellation buttons name the Text and Narration. Routine
progress updates retain the buttons; membership changes restore focus to the corresponding
cancellation button or the queue summary if that Narration has gone. Expanded details
scroll within their existing bound and retain their open state after cancellation/completion.

Changed files: `ozvuchka/web/app.js`, `index.html`, `style.css`,
`tools/ui_design_preview.py`, `tests/test_core.py`, `docs/ui-design-spec.md`,
`docs/manual-checks.md`, and this review directory.
No Core, HTTP, storage, production provider, audio scheduling, queue semantics, estimate
calculation, Speed values or public contracts changed. No code or decisions were copied
from another branch. No other Issues were changed.

## Reproduction

Run any of these from the repository root in separate terminals:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --long-title --port 8774
runtime/python.exe -X utf8 tools/ui_design_preview.py --long-title --no-ready --piece-seconds 15 --port 8775
runtime/python.exe -X utf8 tools/ui_design_preview.py --no-ready --unavailable --texts 1 --port 8776
runtime/python.exe -X utf8 tools/ui_design_preview.py --no-ready --load-seconds 40 --texts 0 --port 8777
```

Open the corresponding localhost port. These serve the actual Core/HTTP/page with the
existing FakeVoiceProvider, wrapped only to pace loading/synthesis for visible checks.
Samples and Narrations are silent WAVs. This verifies browser playback, not audible quality.
Use `--no-ready` with delayed or unavailable fixtures to avoid the ordinary ready-seeding
timeout. Default invocation retains stage 3's two ready Narrations. Each runner uses its
own disposable `.cache/ui-design-preview/issue-28-*` Library; the historical prefix is
only a fixture directory name. The user's `data/` was not opened or modified. Ctrl+C
stops a runner and removes its disposable Library.

On :8775 enqueue Alice, choose George and enqueue again before Alice finishes. Open
queue details, inspect changing estimates, and cancel George then Alice. On :8777 open
the Voice panel immediately, audition George, enter a short Text and enqueue while
loading. After loading, the existing worker completes the Narration and the queue empties.

## Actual browser verification

Windows, Codex in-app browser, actual visible controls with read-only DOM measurements.
No static mock or new browser-test framework. Browser version was not exposed/recorded.

| Check | Observed result |
| --- | --- |
| 1280 × 720; 20 Texts, long title, two ready Narrations | Editor y=351.59, height=205.16; Play y=572.75, bottom=616.75. Both initially visible. Voice panel does not change those document coordinates. |
| 1440 × 900 | No horizontal overflow; Play bottom=616.75. Full Voice panel and editor fit. |
| 390 × 844 | No horizontal overflow (document width=375, viewport=390 including scrollbar). Single-column Voice choices and samples fit. Panel has its own bounded scroll. Native Speed control fits. |
| 640 × 360 CSS viewport | No horizontal overflow (document width=625). Tab reaches the George sample in the scrolling panel; Space plays it. This is a compact viewport check, **not genuine 200% browser zoom**. |
| Independent sample | George sample reports playing/completion while Alice remains selected. No `set_voice` action is sent by sample controls. |
| Voice selection / Escape | Choosing George changes the visible summary. Escape closes the panel and focuses its summary. |
| Tab / outside click | Tab after the last sample reaches Speed and closes the panel. Clicking Speed outside also closes it. |
| Speed and reload | Changing to 0.8 survives reload alongside selected George; returning to the labelled normal Speed works. |
| Loading / empty Library | Alice stays named with `загрузка…`; rows say `Загрузка…`. George sample plays while loading. Enqueue shows `В очереди · время пока неизвестно` and the existing loading feedback. |
| Loading completion | The queued short Text becomes ready, summary becomes `пуста`; normal ready Paragraph feedback remains. |
| Unavailable / one Text | Summary and rows say `недоступен`. Samples remain available. Enqueue produces the existing Russian unavailable-Voice failure without losing the Text. |
| Active plus waiting Narration | Alice says `Готовится`, George says `В очереди`; existing estimates appear after the first completed piece and count down. No fabricated percentage or timer. |
| Queue layout stability | Editor document y=351.59 and Play document y=572.75 remain unchanged after queue appearance, progress and cancellation. Browser may scroll to focused details; that does not change document layout. |
| Cancel queued / active | George disappears first; Alice remains active. Cancelling Alice leaves the empty queue and focuses its summary. Narrow cancellation target measured 44 px high and wholly accessible after native scrolling. |
| Playback regression | Play hides preparation/queue and shows existing Paragraphs/transport; pause and return to editing work, with editor focus restored. |

Retained screenshots (captures can differ in raster size from measured CSS viewports;
keyboard focus may have scrolled the page):

- [Voice panel, 1280](voices-1280.jpg)
- [Voice panel, 1440](voices-1440.jpg)
- [Voice panel, narrow](voices-390.jpg)
- [Keyboard sample, compact](voices-640.jpg)
- [Two Narrations in queue](queue-1280.jpg)
- [Narrow active Narration cancellation](queue-390.jpg)
- [Loading Voices and independent sample](loading-1280.jpg)
- [Unavailable Voices](unavailable-1280.jpg)

## Checks and remaining limits

- Initial checks: `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue31-final`: **109 passed, 6 slow tests deselected**.
- Cancellation clarification: `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue31-cancel-final`: **110 passed, 6 slow tests deselected**.
- `runtime/python.exe -m mypy`: passed (23 source files).
- `runtime/python.exe -m ruff check`: passed.
- `git diff --check`: passed.

Production provider/build/launcher behaviour is unchanged; slow tests and ZIP smoke are
not required for this stage. The preview tool wraps the test fake only. No CSS/DOM
assertion tests were introduced. A public-seam cancellation regression test was added
after the developer's report, confirming existing behaviour without changing Core.

The developer reported that genuine 200% zoom was fine on 2026-11-04. This covers the
initial candidate; the subsequent Voice-button revision was browser-checked at 1280
and 390 CSS px, and still awaits the developer's interaction acceptance. In-app compact
viewport evidence is not genuine browser zoom. Sample-failure retry text is implemented but an actual
missing/corrupt sample failure was not injected in this session.

School-laptop responsiveness and real offline samples remain under #31 in the single
manual checklist. Existing projector/remote checks remain there as well; no hardware
results are claimed.

Inherited stage 3 limitations remain: native `prompt()` does not work in the in-app
browser; application dialogs belong to stage 6. Text transitions do not flush unsaved
edits; reload/search title fallback and deleted-Text draft behaviour are unchanged.
No autosave, audio redesign or later-stage work was added.

## Developer review and revision (2026-11-04)

The developer confirmed workspace stability, independent samples, Tab navigation,
Speed persistence, and genuine 200% zoom. They requested closing the chooser on Voice
selection and arrow-key navigation with explicit Enter/Space confirmation. Queue and
cancellation acceptance could not be completed because their test Narrations finished
before the second Voice could be enqueued. This is not full stage acceptance.

The revision replaces native radios (whose arrows select immediately) with named native
buttons. Pointer click and native Enter/Space activation confirm; arrows only focus a
Voice, wrapping at either end. From the open summary an arrow focuses the currently
selected Voice. Confirmation closes the disclosure and returns summary focus after
the command/refresh; clicking the already selected Voice closes without another command.
Sample buttons remain separate, and availability/progress do not alter pending focus.

Actual in-app browser rechecks: arrow to Alice while George remains selected; Escape
preserves George; Enter selects George from Alice and closes; Space selects Alice and
closes; pointer selection closes; sample playback leaves the panel open with selection
unchanged. At 390 CSS px the revised panel has no horizontal overflow. Retained updated
evidence: [focused Alice, selected George](keyboard-choice-1280.jpg),
[revised narrow panel](choice-revised-390.jpg). Earlier Voice screenshots show the
pre-review radio layout and are retained as historical evidence.

A fresh, unprepared disposable Library is served for repeat acceptance at :8778:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --long-title --no-ready --piece-seconds 60 --port 8778
```

It delays every synthesis piece by 60 seconds and seeds no ready Narrations, leaving
several minutes to enqueue Alice and George and cancel them. The initial page was
visually checked but no Narrations were enqueued there by the agent, preserving it
for the developer. If a combination later becomes ready, create a New Text or change
Speed before retesting: enqueue deliberately does not regenerate a ready Narration.
This only changes fixture invocation; production timing/queue semantics are unchanged.

## Cancellation follow-up (2026-11-04)

The developer accepted revised Voice keyboard/pointer selection and successfully
created active Alice plus queued George. They reported that cancelling Alice left
George queued rather than immediately synthesizing. Full stage acceptance is still
pending this clarification.

Inspection of `Core.cancel` confirmed its existing contract: cancellation removes the
Narration but finishes the provider call already under way, keeping its result. Only
then can the single synthesis worker claim George. With :8778's deliberately slow
fixture that means up to 60 seconds of waiting after Alice is removed. Do not change
this into interruptible synthesis or mark George synthesizing before it actually starts.

Added a deterministic test using the existing manual FakeVoiceProvider: cancel Alice,
assert George is still queued, release just the Alice piece, assert George becomes
synthesizing, then finish and check that Alice's later Paragraph was never requested.
It passed before any implementation changes. Core, production provider and queue
semantics remain unchanged.

Actual browser reproduction used another disposable Library on :8779 with
`--texts 1 --no-ready --piece-seconds 15`. Through visible controls enqueue Alice and
George, cancel Alice, observe only George with `В очереди`, then observe George become
`Готовится` after the outstanding Alice piece finishes. No re-enqueue or reload was
needed. [Retained transition evidence](cancel-next-started-1280.jpg).

The UI now explains the cancellation boundary in expanded nonempty queue details;
cancel buttons refer to that explanation with `aria-describedby`. This is explanatory
text, not an inferred worker state or a new timing calculation. For repeat developer
acceptance, refresh :8778 and cancel Alice while George waits, then allow up to 60 seconds
for George to start. If a Voice/Speed combination is already ready, use a New Text or
another Speed so that the existing enqueue command has work to do.

Review correction commit: `550a641` (Voice confirmation/keyboard). The cancellation
clarification and evidence are in the commit introducing this section; use
`git log -1 --format=%h -- tests/test_core.py` to identify it.

## Next session

Read AGENTS.md, CODING_STANDARDS.md, GLOSSARY.md, ADR-0001/0002/0003,
`docs/ui-design-spec.md`, this handoff and live #31. Present stage 4 for acceptance;
keep #31 open until accepted. Stage 5 (#32) is not started. Publication and CI need the
developer's permission; neither is implied by this local handoff.
