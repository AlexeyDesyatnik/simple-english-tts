# UI visual refresh — implementation and verification record

Date: 2026-11-06. Branch: `main`. The direction was approved on 2026-11-05 in the
[UI visual refresh plan](../../ui-visual-refresh-plan.md). The work changed presentation only;
the accepted interaction model and Core/HTTP contracts remain unchanged.

## Implementation commits

| Stage | Commit | Result |
| --- | --- | --- |
| Plan | `cac0fa9` | Visual direction, boundaries, six stages and acceptance criteria |
| 1. Foundation | `2bd32ae` | Refreshed tokens, Onest, controls, disclosure markers and reduced motion |
| 2. Library | `02f3806` | Coherent panel, full-row selection, search icon, quiet menus and readiness icons |
| 3. Preparation | `3877c9b` | Title/rename grouping, Voice/Speed surface, editor, save check and Play icon |
| 4. Playback mode | `a20c16f` | Compact sticky transport, transport icons, position hierarchy and reading layout |
| 5. Dialogs/feedback | `68746a5` | Dialogs, actionable errors, queue rows, loading states and narrow overlay polish |
| 6. Acceptance/docs | this record's commit | Final screenshots, current specification, README image and manual acceptance |

No framework, frontend build step, remote asset, new Python dependency or application-state
mechanism was added. Onest is bundled unmodified with its SIL OFL text and NOTICE entry.

## Reproducible UI setup

Windows; Kimi Code built-in Chromium browser; real Core and HTTP server with isolated
Libraries. The final capture Library used 20 Texts, a long title and two ready fake
Narrations. Fake audio is silent: these checks do not establish human listening quality.

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 20 --long-title --port 18761
```

Other stage checks used the same preview with `--texts 0` or `1`, `--no-ready`,
`--unavailable`, paced synthesis and deterministic failure. The teacher's `data/` Library was
never used. Preview processes were stopped after their checks.

## Visual and interaction evidence

| Area | Confirmed result |
| --- | --- |
| Desktop preparation | 1440 × 900 and 1280 × 720 captures reviewed. With 20 Texts and a long title, the editor and Play are initially visible; Library growth stays in its own scroll area. |
| Narrow preparation | 390 × 844 capture reviewed. Long title, rename, Voice/Speed and editor remain readable without horizontal clipping. |
| Library | Checked 0, 1 and 20 Texts, full-row selection, ready Narration labels, long titles, empty Library and empty search. Search preserved the open Text; narrow Library opened/closed with keyboard and retained the required disclosure state. |
| Voice/Speed and saving | Voice chooser opened with keyboard, arrows moved focus and Enter selected George. Speed changed through the real command. Edits reached confirmed `Сохранено`; the check icon appeared after correcting SVG `hidden` attribute handling. |
| Playback mode | Play, Pause/Continue, natural completion and return to editing were exercised. Current Paragraph, skipped instruction, position and quiet help are visible in the new treatment. Previous/Next/Repeat controls and accessible names were inspected, but this record does not claim a new exhaustive keyboard journey. |
| Narrow/large Playback | At 390 × 844 and Text size 80, the current Paragraph begins below the sticky transport. The initially clipped Play label was corrected by showing icon-only Previous/Next at up to 420 px while retaining their accessible names/tooltips; Play keeps its full label. |
| Dialogs/errors | Rename validation, narrow dialog layout, Escape/focus return, unavailable Voice text, empty-Play error and dismissal were checked. Library state survived dialog cancellation. A CSS specificity regression that exposed playback-only controls in preparation was found and corrected. |
| Narration queue | Active queue summary/details were reviewed with paced synthesis. A second Narration at another Speed was cancelled through its visible button and the queue became empty. No cancellation error appeared. |
| Reduced motion | The stylesheet disables nonessential transitions under `prefers-reduced-motion`; no separate assistive-technology or device audit is claimed. |

A late final interaction series showed a transient `Нет связи с программой` while the preview
HTTP endpoint still answered. It did not affect the saved screenshots and is not presented as
a resolved product defect or as a successful final keyboard journey. Existing public-seam
tests and the release smoke test provide the behavioural regression evidence below.

## Contrast and assets

Computed sRGB contrast against white: primary text 15.01:1, secondary text 4.97:1,
accent 5.77:1, error 6.76:1 and essential control border 3.66:1. Selection and current
Paragraph retain shape/text cues. Visible interactive targets retain the 44 px minimum.

The page references only local assets. `Onest-Variable.ttf` is served by the existing static
HTTP path and rendered correctly in Russian and English during browser checks.

## Release verification

```powershell
tools/build.bat release
runtime/python.exe tools/smoke_test.py dist/ozvuchka-0.3-15-g68746a5.zip
```

The release build produced `dist/ozvuchka-0.3-15-g68746a5.zip`. ZIP inspection confirmed
`ozvuchka/web/Onest-Variable.ttf`, `licenses/Onest-OFL.txt` and `licenses/NOTICE.txt`.
The release smoke test passed: the page was served, a second start reused the running
program, real Kokoro synthesized `Hello.` as 0.85 s of speech, the program ended after page
close and only `data/` received runtime writes. Launcher diagnostic checks also passed.

## Automated checks

Each implementation commit was preceded by:

```powershell
runtime/python.exe -m pytest
runtime/python.exe -m mypy
runtime/python.exe -m ruff check
git diff --check
```

Result at every stage: 213 passed, 8 slow deselected; mypy and ruff passed. No provider
algorithm changed. The release build and its real-Kokoro smoke test are recorded separately
above. No CSS/DOM assertion suite or new browser-test stack was introduced.

## Durable screenshots

- [Preparation, 1440 × 900](workspace-1440.png)
- [Preparation, 1280 × 720](workspace-1280.png)
- [Preparation, 390 × 844](workspace-390.png)
- [Playback mode, 1280 × 720](playback-1280.png)
- [Playback mode, 390 × 844](playback-390.png)

The built-in browser reports capture/display scaling metadata that should not be confused
with browser zoom. Images are retained as layout evidence, not as actual 200% zoom evidence.

## Developer acceptance — 2026-11-06

The developer reported that all requested manual checks passed: actual 200% browser zoom,
projector/back-row readability and offline Celeron/i5 visual checks with the release and a
disposable Library. The visual refresh is accepted; its completed checklist was removed from
`docs/manual-checks.md`. No per-device measurements were supplied, so none are invented here.
Existing #37 hardware checks are separate and are not marked passed by this acceptance.
