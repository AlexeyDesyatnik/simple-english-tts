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
opens a bounded, scrolling panel over the editor without changing its layout. Native
radio labels choose a Voice; separate, named buttons play Voice samples without changing
selection. Rows show loading, available or unavailable states in text. Samples remain
usable during loading/unavailability, as the existing Voice provider contract allows.
Sample loading, playing, completion and retry guidance have their own status, independent
of polled synthesis feedback. Late sample promises cannot overwrite a newer sample's status.

Escape closes the Voice panel and focuses its summary. Tab leaving it and outside clicks
close it. Availability updates keep the same radio/button elements rather than rebuilding
them. Narrow rows wrap into a single column, with 44 px selection and sample targets.

The queue summary is always present, including `пуста`, below the primary action. Details
show existing order, Voice/Speed, synthesizing or queued state, and existing time estimates;
an unknown estimate is explicitly labelled. Existing current-Text ready Paragraph counts
and ready Narration feedback remain in the status area. No new per-queue Paragraph counts
or estimates are inferred. Cancellation buttons name the Text and Narration. Routine
progress updates retain the buttons; membership changes restore focus to the corresponding
cancellation button or the queue summary if that Narration has gone. Expanded details
scroll within their existing bound and retain their open state after cancellation/completion.

Changed files: `ozvuchka/web/app.js`, `index.html`, `style.css`,
`tools/ui_design_preview.py`, `docs/manual-checks.md`, and this review directory.
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
| Independent sample | George sample reports playing/completion while Alice remains the only checked radio. No `set_voice` action is sent by sample controls. |
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

- `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue31-final`: **109 passed, 6 slow tests deselected**.
- `runtime/python.exe -m mypy`: passed (23 source files).
- `runtime/python.exe -m ruff check`: passed.
- `git diff --check`: passed.

Production provider/build/launcher behaviour is unchanged; slow tests and ZIP smoke are
not required for this stage. The preview tool wraps the test fake only. No CSS/DOM
assertion tests were introduced and no Core behaviour required new tests.

Genuine browser zoom at 200% remains for developer acceptance: the in-app browser's
documented capability controls viewport size but does not expose browser zoom. Please
check Voice selection, independent samples, the Speed options and queue cancellation
at 200% in the developer's browser. The compact viewport evidence above is not a claim
to have completed that check. Sample-failure retry text is implemented but an actual
missing/corrupt sample failure was not injected in this session.

School-laptop responsiveness and real offline samples remain under #31 in the single
manual checklist. Existing projector/remote checks remain there as well; no hardware
results are claimed.

Inherited stage 3 limitations remain: native `prompt()` does not work in the in-app
browser; application dialogs belong to stage 6. Text transitions do not flush unsaved
edits; reload/search title fallback and deleted-Text draft behaviour are unchanged.
No autosave, audio redesign or later-stage work was added.

## Next session

Read AGENTS.md, CODING_STANDARDS.md, GLOSSARY.md, ADR-0001/0002/0003,
`docs/ui-design-spec.md`, this handoff and live #31. Present stage 4 for acceptance;
keep #31 open until accepted. Stage 5 (#32) is not started. Publication and CI need the
developer's permission; neither is implied by this local handoff.
