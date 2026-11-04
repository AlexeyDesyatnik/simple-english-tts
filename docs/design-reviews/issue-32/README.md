# Stage 5 Playback mode — verification and handoff

Date: 2026-11-04. Branch: `experiment-2`.
Issue: [#32](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/32).
Baseline: `d3d0e35`, clean working tree on the existing branch.
Implementation and browser evidence: `d0d4fab` (local, not pushed).
Status: audible transport and genuine 200% accepted by the developer; the requested
completion-view correction below is ready for review. #32 remains open.
No push or CI inspection has been performed. Both require separate permission.

## Changes and boundaries

- `ozvuchka/web/index.html`, `app.js`, `style.css`: one persistent primary button
  displays Pause while playing/waiting, Continue while paused, Play when stopped.
  It retains focus rather than swapping two DOM buttons. Previous/next have explicit
  accessible Paragraph names; the navigation group stays together at narrow widths.
- Position counts readable Paragraphs only and follows the highlighted Paragraph
  during the existing inter-Paragraph pause. Current Paragraphs expose `aria-current`.
  Skipped Paragraphs retain their textual explanation. Failed Paragraphs now show their
  error and a retry hint in the reading Text, rather than only a hover tooltip.
- Text size tools are a named group with the current size and the existing limits.
  Compact help explains native-control focus and closes with Escape to its summary.
  A separate hint exposes starting from a Paragraph by pointer or Enter/Space.
- Reading Text retains centred 68ch line length, yellow highlight and blue edge.
  Scrolling centres short Paragraphs in the space below the sticky panel and aligns
  the beginning of a tall Paragraph below it. ResizeObserver handles wrapped tools,
  help expansion and viewport changes. All Paragraphs get the measured scroll margin,
  so browser scrolling for a click/focus cannot place them behind the panel.
- Return uses the existing stop command, clears the page schedule and focuses the
  editor with normal focus scrolling, including in a narrow window.
- `tools/ui_design_preview.py`: optional `--fail-text` injects a deterministic synthesis
  error through the existing FakeVoiceProvider seam. Use it with `--no-ready`.
- `docs/manual-checks.md`: #32 projector, remote and school-laptop checks added.

Core, HTTP/snapshot contracts, audio scheduling/player events, the natural end,
Voice choice, Library, queue order and ADR-0004 cancellation are unchanged. No code
or decisions were copied from other branches. Dialog replacement and autosave remain
later stages. There are no new dependencies or browser test frameworks.

## Reproducible isolated setup

Fresh processes were started for this session; no previous-session Core was reused.
Both use temporary Libraries below `.cache/ui-design-preview/`, never user `data/`.
Fake speech is silent and does not establish real audio quality or hardware timing.

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --long-title --port 8781
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --no-ready --piece-seconds 10 --fail-text owner --port 8782
```

The first seeds 20 Texts, a long title and Alice/George Narrations. The second starts
without ready Narrations; Play the seeded Text to see a failed second readable
Paragraph. For a clean waiting case, create a New Text containing two fresh English
lines without `owner`, then Play. Pause is available during the Start delay.
Temporary Library changes disappear when that preview process exits.

The :8781 page is left paused at the first readable Paragraph, Text size 22, for review.
The second preview contains disposable browser-created data; restart it to reproduce
its initial state. A ready combination will not be synthesized again merely by enqueue.

## Actual browser verification

Windows, ChatGPT in-app browser, real page/Core/HTTP. Browser controls and keyboard
were used, with DOM/accessibility reads and screenshots; no static mock.

- Playing and waiting expose Pause; pausing exposes Continue on the same focused
  button; Continue resumes. Stopped/ready preparation exposes Play and no Pause.
  Waiting was observed as `Начнётся через ~7 с`, then paused before readiness.
- Previous/next move among readable Paragraphs, excluding the Russian instruction;
  repeat restarts through the existing command. Pointer and Enter start a Paragraph.
  The compact-window pointer check initially hit the sticky help after browser scroll;
  measured scroll margins fixed this, and an actual click then selected Paragraph 3/6.
- Natural completion of the final Paragraph returns to preparation, as before. Physical
  R after that end restarts Paragraph 6/6 through Core's existing repeat semantics.
  Return stops and focuses the unchanged prepared editor. Replaying starts at 1/6.
- Seven displayed lines give six readable Paragraphs. The Russian line remains visibly
  skipped; injected failure has a red message directly beneath its English Paragraph.
- 1440×900 and 1280×720: long title, centred reading Text, navigation, return, and
  preparation with 20 Texts. 390×844: navigation stays together, other tools wrap,
  compact help expands/Escape closes with summary focus, no horizontal page overflow.
- Existing seven Text sizes were exercised from 18 to 80 and back. At the limits the
  appropriate size button disables. At 390×844/80 the tall current Paragraph began at
  y≈329 below the panel ending at y≈313. The rest remains available by normal scrolling.
- 640×360 compact viewport: current Paragraph remained below the panel and the page
  had no horizontal overflow. This is **not genuine 200% browser zoom**. Ctrl+Plus did
  not change IAB's viewport/DPR; genuine 200% still needs developer browser acceptance.
  Stage 4's accepted zoom result is not claimed as stage 5 verification.

Retained screenshots (some native browser captures are visibly soft):

| View | Evidence |
| --- | --- |
| Main paused view, focused Continue | [1280×720](paused-1280.jpg) |
| Playing view | [1280×720](playing-1280.jpg) |
| Reading Text with long title | [1440×900](playback-1440.jpg) |
| Preparation retained with 20 Texts | [1440×900](preparation-1440.jpg) |
| Narrow reading tools | [390×844](narrow-390.jpg) |
| Expanded help | [390×844](help-390.jpg) |
| Maximum Text size 80 | [390×844](large-390.jpg) |
| Reduced available height | [640×360](compact-640.jpg) |
| Waiting with Pause available | [1280×720](waiting-1280.jpg) |
| Failed and skipped Paragraphs | [1280×720](failed-1280.jpg) |

## Checks and acceptance

- `runtime/python.exe -m pytest --basetemp=.cache/pytest-issue32-final`: **114 passed,
  8 slow tests deselected**. Default pytest initially failed at temporary-directory
  fixture setup under the sandbox; a writable repository basetemp resolved it.
- `runtime/python.exe -m mypy`: passed, 23 source files.
- `runtime/python.exe -m ruff check`: passed.
- `git diff --check`: passed.
- Slow/provider/build checks are not required: production provider/build behaviour
  was not changed. The page has no automated tests, per CODING_STANDARDS.md.

Developer acceptance remains: review transport and reading layout, repeat the 200%
zoom check, and confirm stage 5. Hardware checks stay exclusively in
`docs/manual-checks.md`; none are marked complete here. Existing native prompt()
limitations, application dialogs and save/transition guarantees are outside #32.
Do not close #32 or start stage 6 before acceptance. Ask separately before push and
CI inspection. Preserve the immediate synthesis interruption in ADR-0004/f2d2109.

## Audible acceptance correction

The developer correctly noted that silent fake speech cannot establish that heard
speech actually pauses, resumes or starts/repeats at the correct Paragraph. Earlier
fake/browser checks establish UI/command behaviour only; full stage acceptance is
still pending audible review.

A fresh real-provider preview is now running at http://127.0.0.1:8783 with its own
new disposable Library, 20 Texts and ready Alice/George Narrations. It was stopped
back in preparation for the developer to press Play. The user Library is untouched.
Reproduce from the repository root:

```powershell
New-Item -ItemType Directory -Force .cache/real-preview-temp | Out-Null
$env:TEMP = (Resolve-Path .cache/real-preview-temp).Path
$env:TMP = $env:TEMP
runtime/python.exe -X utf8 tools/ui_design_preview.py --real-voice --long-title --port 8783
```

`--real-voice` selects the unmodified installed KokoroProvider and its real Voice
identifiers; no fake delays, failures or availability overrides can be combined with
it. Initial seeding waits up to 300 seconds per Narration. All data still goes into
the preview's TemporaryDirectory; production launch/data handling is unchanged.

The real provider loaded and synthesized both Narrations successfully. An HTTP read
of the first Alice piece confirmed 4.523 seconds of PCM speech, peak 30890 and
107725 nonzero samples (not a silent fake WAV). In-app browser Play entered playing
and advanced among Paragraphs; Return stopped and focused the editor. This does not
claim an agent listening judgment or that the user's output device is working.
[Ready real-provider page](real-voice-ready.jpg).

Audible developer acceptance: pause stops sound; Continue resumes the same position;
Previous/Next switch to the corresponding spoken Paragraph; Repeat starts it again;
clicking a Paragraph starts that Paragraph; Return immediately stops sound; natural
completion has no extra speech or overlap and replay starts at the first readable
Paragraph. Verify the highlight/position against what is actually heard. The Russian
instruction remains unspoken. Genuine 200% zoom and hardware checks remain pending.

## Developer acceptance: keep Playback mode after completion

On 2026-11-04 the developer confirmed real speech behaviour and acceptable genuine
200% zoom. They requested one correction: finishing the Text must not automatically
return to editing; the teacher chooses when to leave Playback mode. This explicit
request supersedes earlier natural-end UI expectations in this handoff and the
original styling-only end boundary in the specification.

Core's existing last-heard `_ended_at` is now exposed as nullable
`playback.ended_at` in the snapshot. No command, audio scheduling, event processing
or stopped/playing state transition changed. The UI retains Playback mode when that
position exists, keeps the last readable Paragraph highlighted and counted, shows
`Текст прочитан`, and offers `Воспроизвести`. Explicit stop clears that position and
returns to editing. Play still restarts from the first readable Paragraph; repeat
and previous retain their existing semantics after the end. Since Core owns the
position, F5 retains the completed reading screen without page-only mode state.
GLOSSARY.md and the Playback mode specification now describe this accepted direction.

The new public-seam test first failed with a missing snapshot field, then passed.
Existing exact playback snapshot assertions include the additive field. Latest
checks: **115 passed, 8 slow tests deselected**, mypy and ruff passed; diff check passed.
No production provider/build change; no additional slow suite is required.

A fresh real-Kokoro process serves the correction on http://127.0.0.1:8784 using a
new disposable Library. Earlier ports contain older Core instances; use :8784.
Reproduce the real-provider command above with `--port 8784`.

Actual IAB verification: let the last spoken Paragraph finish naturally; observe
Playback mode, Play, `Абзац 6 из 6` and `Текст прочитан`; reload and retain that view;
Repeat starts 6/6; Return explicitly exposes/focuses the editor; Play starts 1/6.
The page is left on the completed reading screen for developer review.
[Completed reading screen](completed-1280.jpg).

The developer's sound and 200% acceptance is recorded here, not as a hardware result.
All school/projector/remote items in the single manual checklist remain outstanding.
The new completion-view correction awaits review; #32 is not closed, stage 6 has not
started, and push/CI inspection still require separate permission.
