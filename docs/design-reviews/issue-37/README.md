# Stage 10 — integrated acceptance (#37)

> **Historical record:** the stage and its Issue are complete. Branch rules, pending
> statuses, localhost servers and next-session instructions below describe the work at
> that time, not current guidance. See the [current UI design specification](../../ui-design-spec.md).

Date: 2026-11-04. Branch: `experiment-2`. Starting tree was clean at `b3b212c`,
five commits ahead of its upstream. Authenticated host GitHub CLI confirmed #36
closed and #37 open. Stages 1–9 were already accepted. At implementation handoff,
#37 remained open for developer acceptance; no push, CI inspection or Issue
mutation was performed. See the subsequent developer acceptance below.

Implementation commit: `e0403a0`.

## Scope and corrections

Integrated review of the existing design, with three bounded page corrections:

- Empty Play/prepare now explains in Russian that the teacher must paste a Text,
  instead of exposing `ValueError: no text to play` / `no text to queue`.
- Action/transport errors have their own alert and explicit dismissal. Routine
  snapshot rendering no longer erases them after half a second. The original
  action remains available for retry; dismissal returns focus to the editor or
  reading workspace. Save and synthesis errors retain their existing retry paths.
- Keyboard-help summary now has a 44 px target. For a current Paragraph taller
  than the viewport, visibility checks require its beginning below the sticky
  controls rather than considering every below-screen position visible. This
  fixes large-Text repositioning when the viewport narrows or tools change height.

Product changes: `ozvuchka/web/app.js`, `index.html`, `style.css` only. No Core,
HTTP command/snapshot, Library format, lifecycle, autosave ordering, provider,
audio scheduling, build or launcher contract changed. No framework, recovery
machinery, network dependency or other branch's implementation was introduced.
Hardware checks are consolidated in `docs/manual-checks.md` with original Issue
references retained; no outstanding check is marked passed or dropped.

## Reproducible setup

Windows; ChatGPT built-in Chromium browser controlled through Computer Use.
Real Core, HTTP server and page; disposable Libraries under
`.cache/ui-design-preview/`. The teacher's `data/` was not used. Run from the
repository root in a separate PowerShell terminal:

```powershell
New-Item -ItemType Directory -Force .cache/tmp | Out-Null
$env:TEMP = (Resolve-Path .cache/tmp).Path
$env:TMP = $env:TEMP
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 20 --long-title --port 18740 --real-voice
```

Open `http://127.0.0.1:18740`. Initial seeding prepares Alice and George with real
Kokoro before printing the URL, so allow time for startup. Ctrl+C stops the preview.
Use one editing/playback tab at a time. The preview omits the launcher's automatic
page-gone shutdown loop. All three review processes were stopped after checking.

Actual review Libraries:

| Port | Options | Disposable directory suffix | Purpose |
| --- | --- | --- | --- |
| 18740 | `--texts 20 --long-title --real-voice` | `issue-28-mf_tvg91` | Real speech, samples, two ready Narrations, layout, editing and reload. |
| 18741 | `--texts 0 --no-ready --unavailable` | `issue-28-frclnzj4` | Empty Library, unavailable Voice explanation, empty-action error/dismissal. |
| 18742 | `--texts 1 --no-ready --load-seconds 45 --piece-seconds 4 --fail-text owner` | `issue-28-9wgk1m9b` | Deterministic loading, waiting, progress, failure/retry and queue cancellation. |

The latter two use the existing paced FakeVoiceProvider seam, which emits silence;
they verify UI state, not speech quality or real-device cancellation latency.

## Browser results

The review covered 0, 1 and 20 Texts across these sessions, rather than duplicating
every interaction for every Library size. A temporary 21st Text was created,
autosaved, read and deleted through its confirmation dialog; final real Library
returned to 20 Texts. No substantial new defect requiring a separate Issue emerged.

| Area | Observed result |
| --- | --- |
| 1440 × 900 and 1280 × 720 | With 20 Texts, long current title and Alice/George ready labels, editor and Play remain initially visible. At 1280, editor bottom 628.75 and Play bottom 688.75 CSS px. Editor height 205.16 px accommodates six lines; Library growth remains in its scroll area. |
| 390 × 844 | Preparation, Voice/Speed, Library disclosure/scroll, long-title delete dialog, transport, help and reading tools remain usable without horizontal page overflow. Long preparation title and editor/actions may require vertical scrolling, as allowed. Library stays open after selection/New Text/dialog cancellation until explicit close or Escape. |
| 640 × 360 reflow proxy | Checked preparation, Voice disclosure and Playback layout at the CSS space corresponding to a 1280 × 720 window at 200%. Vertical scrolling is required; no horizontal page overflow. This is **not an actual browser zoom test**. |
| Browser zoom 200% | **Passed by developer report, 2026-11-04.** The developer explicitly confirmed actual 200% zoom works. The agent's earlier half-size proxy remains separate evidence: built-in-browser Ctrl+plus did not change `innerWidth` or `devicePixelRatio`. |
| Library/search | Empty Library and no-match search have distinct explanations; no-match search preserves current editor. Long row/title names remain fully accessible; two ready Narration labels remain readable. |
| Voice/sample | Real George sample reached browser's playing state while Alice remained selected. Arrows moved focus to Fable without selecting it; Escape restored Voice-summary focus. Confirming George with Enter closed the chooser and updated selection. Unavailable/loading states explain their meaning in text. Human listening quality is not claimed. |
| Editing/save/reload | New three-Paragraph Text showed unsaved then saved. F5 restored it. Appending `They smiled.` and immediately pressing Play saved/synthesized the exact latest Paragraph; disposable `library.json` independently confirmed it. Routine snapshots preserved the editable Text. No delay proxy or crash audit was repeated. |
| Playback | Real Kokoro reached natural completion with `Текст прочитан`, last readable Paragraph highlighted, and Play visible. Reload preserved completion. Return to editing stopped Playback mode. Space pause, PageDown and R paths, previous/next/repeat controls, Paragraph activation and skipped Russian instructions were exercised. Entry focuses the reading workspace. |
| Dialog/focus | Empty rename is rejected in Russian. Tab/Shift+Tab wrap in modal; Escape/cancel restore invoking focus. Long-title delete consequences fit the narrow scrollable dialog. A disposable Text was actually deleted; real teacher data was never touched. |
| Queue | George 1× active and George 0.8× waiting appeared together. Cancelling the active Narration started the waiting one; cancelling the remaining one left an empty queue and focused its summary. Existing completed pieces remain visible through existing Core behavior; no cancellation error was shown. |
| Failure/retry | The paced provider failed the Paragraph containing `owner`. Global and per-Paragraph Russian errors remained visible across polling. Activating the failed Paragraph retried it and returned to waiting; the configured fault predictably failed again. |
| Corrective errors | Empty Play and prepare now show a persistent Russian instruction, independent of routine status. Explicit dismissal hides it and restores editor focus. No new synthesis is requested for an empty Text. |
| Text size / sticky tools | Sizes 18–80 exercised. At 80 after desktop-to-390 resize, current Paragraph top was 341.34 px with sticky transport bottom 325 px. Very tall Paragraphs remain vertically scrollable; they cannot fit in one screen. No horizontal overflow. Help target is now at least 44 px. |

Screenshots are browser content captures; the capture backend may omit scrollbar
space or capture a few fewer pixels than the requested viewport. Viewport dimensions
above were checked independently from DOM `innerWidth`/`innerHeight`. Some state
evidence is scrolled to the relevant control or Paragraph rather than page top.

## Visual/platform checks

Source audit: page assets, scripts, stylesheet, samples and speech are local;
no remote font, `@import`, external asset URL, localStorage, Windows-only font
dependency or new package. Font stack remains
`system-ui, "Noto Sans", "Liberation Sans", sans-serif`; SVG icons are inline.
This is a source/layout portability check, not a claim of Linux/macOS runtime
support. Those OSes, Edge app-window zoom, physical Russian layout and presenter
remote were not tested in this session.

Computed sRGB contrast from current CSS tokens against `#fffefa`: ordinary text
14.14:1, muted text 5.95:1, blue 6.71:1, red 6.70:1, control border 3.23:1.
Current yellow Paragraph: text 11.43:1 and blue edge 5.43:1. Selection, errors and
current Paragraph also have text/shape cues. Visible buttons/selects/summaries
were checked for 44 px minimum height after correcting keyboard help; row-menu
summaries and Text size buttons retain their 44 px targets. Visible keyboard
focus and modal containment were observed, not a full assistive-technology audit.

## Durable evidence

- [Final workspace, 1440](workspace-1440.jpg), [1280](workspace-1280.jpg),
  [390](workspace-390.jpg), [narrow Library](library-390.jpg).
- [Final Playback, 1440](playback-1440.jpg), [390](playback-390.jpg),
  [half-size reflow proxy](playback-half-viewport.jpg),
  [preparation reflow proxy](preparation-half-viewport.jpg).
- [Large Text, 1280](large-text-1280.jpg), [large Text, 390](large-text-390.jpg).
- [Long delete dialog](dialog-390.jpg), [persistent empty-action error](empty-error-1280.jpg),
  [loading/waiting](loading-waiting.jpg), [queue](queue.jpg),
  [synthesis failure](synthesis-failure.jpg), [real completion](real-completed.jpg).

## Required checks and remaining acceptance

```powershell
runtime/python.exe -m pytest --basetemp=.cache/pytest-issue37-final
runtime/python.exe -m mypy
runtime/python.exe -m ruff check
git diff --check
```

Result: 133 passed, 8 slow deselected; mypy passed (23 source files); ruff and
diff check passed. Provider/build code is unchanged, so slow/build smoke checks
are not required. No page test framework or CSS/DOM assertion tests were added.

Developer's short everyday-use acceptance, using the fresh real preview above:

1. New Text: paste two English lines, edit a few words, wait for `Сохранено`,
   then F5. Expect the exact saved Text.
2. Listen to a different Voice sample without changing selection, choose Voice
   and Speed, then Play. Check heard speech, yellow Paragraph, Space pause/resume,
   next/repeat, natural completion and return to editing.
3. Narrow the window: open/scroll Library, open rename or delete and cancel.
   Expect Library to remain open, no clipped controls and visible returned focus.
4. In the normal Edge/Chrome browser set **actual 200% zoom**. Check editor/Play,
   Library, Voice chooser, dialog and reading tools: vertical scroll is allowed,
   horizontal clipping is not. The developer has now confirmed this criterion.

School hardware acceptance is the consolidated checklist in `docs/manual-checks.md`:
projector/back-row readability, real presenter remote and Celeron/i5 performance
(including real cancellation latency). No browser simulation marks those passed.
## Developer acceptance — 2026-11-04

The developer confirmed that all requested acceptance checks work, explicitly
including actual 200% browser zoom. Stage 10 is accepted; the ten-stage UI track
is complete. Close #37 on that basis. No further everyday-use or zoom check is
required for this delivery.

The confirmation does not provide device-specific results or cancellation
timings for the projector, presenter remote or Celeron/i5 checklist. Keep those
entries as unrecorded hardware checks rather than inventing measurements or
claiming particular devices were tested. No push or CI inspection is authorized.
