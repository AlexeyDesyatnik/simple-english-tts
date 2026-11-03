# UI/UX design review

Status: findings and proposals for the `experiment` branch, 2026-11-03. No design or implementation decision is approved yet. This is not an ADR.

Tracking issue: [#27](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/27).

The work on the `experiment` branch is a separate development approach. Existing Issues for the main branch are intentionally not linked, changed, or treated as dependencies.

## Purpose

Improve usability and give the application a more modern appearance while preserving the teacher's main workflows:

1. Paste or open a Text.
2. Choose a Voice and Speed.
3. Start playback without unnecessary waiting or scrolling.
4. Control individual Paragraphs during a lesson.
5. Read the Text clearly on a projector.

This document records a design review, not an implementation specification. Proposed changes must not bypass the existing core or turn the page into anything other than the view defined by ADR-0003.

## What was reviewed

- The HTML structure, CSS and browser-side behavior in `ozvuchka/web/`.
- The live workspace with a populated Library at 1280 × 800 and 1440 × 900.
- An open Text in the stopped state.
- Playback mode with the current Paragraph highlighted.

These were local browser checks, not checks on the school laptops or a projector.

## Confirmed findings

### 1. The primary workflow falls below the first screen

At 1280 × 800, the populated Library and the eight Voice rows occupy the first screen. The Text editor and Play require scrolling. The current order is Library → Voice settings → Text → controls, although entering or opening a Text and starting playback are the central actions.

### 2. Playback controls do not reflect the current state

Play, Pause, Stop and Enqueue are presented together with similar prominence. Play remains visible during playback, and controls remain available when their actions are not useful. Enqueue also remains in Playback mode even though it is not part of the lesson-time playback workflow.

Previous Paragraph, repeat and next Paragraph are available through keyboard commands but have no visible controls. Their discoverability is therefore low, especially for a new user.

### 3. The Library rows are visually noisy

Every Text repeats Rename and Delete buttons. These secondary actions compete with the Text title. The selected Text uses the same yellow as the currently spoken Paragraph, giving two different concepts the same visual signal. The Library byte count next to search has no explanatory label.

Ready Narrations are useful information, but their small text and deletion controls need a clearer, more consistent presentation.

### 4. Voice selection consumes too much vertical space

Eight radio rows, each with its own Listen button, push the editor and playback controls down. The selected Voice and Speed are not summarized as a compact setting after selection.

### 5. Editing and progress feedback need a clearer hierarchy

The Text editor has a placeholder but no persistent visible label. Synthesis and Start delay feedback is primarily textual, without a stable visual progress area. The current interface does not make the Text save state apparent.

Rename and deletion use native browser `prompt` and `confirm` dialogs, which are inconsistent with the rest of the interface and offer limited contextual presentation.

### 6. The visual system is functional but generic

Thin default-looking borders, a fieldset, repeated outlined buttons and small utility controls make the page feel like a collection of form elements rather than a deliberately organized workspace. Spacing and emphasis vary by element rather than following a clear surface and type hierarchy.

There is no design-specific `focus-visible` treatment. Some deletion and Listen targets are small. Clickable Paragraphs are list items and are not keyboard-focusable controls.

## What to preserve

- Playback mode hides the Library and settings and puts the Text first.
- The controls remain sticky while the Text scrolls.
- The Text can be made large enough for classroom use.
- The current Paragraph has a strong yellow highlight with an accent edge.
- Skipped Paragraphs remain visible and are identified.
- The interface remains calm, readable and free of decorative distractions.
- The application remains offline, with plain HTML/CSS/JavaScript, no framework and no build step.

In particular, do not weaken the current Paragraph highlight merely to obtain a more fashionable pastel palette. Any change to its contrast requires a projector check from the back rows.

## Recommendations

### 1. Put the Text and primary action first

On wide windows, use a two-column workspace:

- Left: a compact Library with search and New text.
- Right: the Text editor, Voice and Speed settings, and the primary playback action.

On narrow windows, collapse to one column with the Text and primary action before expanded secondary settings. Keep Playback mode as a separate, uncluttered layout rather than squeezing it into the workspace columns.

### 2. Make transport controls contextual

- Combine Play and Pause into one primary toggle whose label and icon reflect the current state.
- Disable Stop when nothing is playing, paused or waiting.
- Hide Enqueue in Playback mode.
- Use a Russian primary-action label such as «Слушать»; settle the exact wording before implementation.
- Add visible previous Paragraph, repeat and next Paragraph controls.
- Keep Text size controls visible but visually subordinate to playback.
- Group the controls as a deliberate transport bar with a compact status area.

### 3. Simplify the Library

- Make the Text title the main click target.
- Move Rename and Delete into a per-row overflow menu.
- Present ready Narrations as compact Voice/Speed chips with clear removal affordances.
- Use a blue or neutral selected-Text treatment; reserve yellow for the current Paragraph.
- Explain the storage figure as «На диске: …» or move it to a low-emphasis utility area.
- Keep destructive actions visually distinct and confirmed.

### 4. Make Voice selection compact

Evaluate either:

- a two-column grid of selectable Voice cards with preview actions; or
- a compact picker with one adjacent Listen action.

After selection, summarize the settings as, for example, «Alice · обычная скорость», and reveal the full list only when changing the Voice. Keep Speed next to Voice rather than in a separate workflow step.

### 5. Improve feedback and editing clarity

- Add a persistent visible label, «Текст для озвучки».
- Give synthesis progress and Start delay a stable status area, with a progress indicator where the underlying state supports it.
- Make the Text save state visible if the implementation retains the current command-driven saving behavior.
- Pair error color with an icon and a clear next action.
- Replace native rename and deletion dialogs with small application dialogs that manage focus and explain consequences.

### 6. Establish a restrained visual system

- Use white surfaces on the existing warm neutral background for the Library, editor and settings.
- Prefer approximately 12 px surface radii, subtle borders and only very light shadows where separation is needed.
- Standardize spacing around an 8 / 12 / 16 / 24 px scale.
- Clarify the type hierarchy for the application title, Text title, section headings, body text and secondary labels.
- Keep one prominent blue primary action; make secondary actions quieter and reserve red for destructive actions and errors.
- Use a consistent set of simple icons for playback, repeat, search and Voice samples.
- Provide deliberate hover, active, disabled and `focus-visible` states and comfortable pointer targets.

### 7. Treat accessibility as part of every stage

- Give the editor a programmatic as well as visible label.
- Preserve keyboard operation and visible focus for every new control and dialog.
- Do not rely on color alone for selection, playback, skipped or error states.
- Make clickable Paragraphs operable by keyboard if they remain interactive.
- Check responsive layouts with long Text titles and the complete Voice list.

## Proposed screen structure

Wide workspace:

```text
Озвучка
┌────────────────────┬──────────────────────────────────────┐
│ Библиотека         │ Текст для озвучки                    │
│ Поиск   Новый текст│ [editable Text]                      │
│ Text titles        │ Voice / Speed                        │
│ Narration chips    │ [Слушать] [В очередь] [Text size]    │
│                    │ Status / progress                    │
└────────────────────┴──────────────────────────────────────┘
```

Playback mode:

```text
[Previous] [Play/Pause] [Repeat] [Next] [Stop]     [Text size]
Status / progress

Skipped Paragraph
Current Paragraph, strongly highlighted
Next Paragraphs
```

These diagrams express hierarchy, not final dimensions or styling.

## Visual prototype awaiting review

The browser-checkable visual prototype was implemented in commit `ad35c09` on the `experiment` branch. It uses the existing plain HTML/CSS/JavaScript page and current state/commands; no parallel application, framework, build step or online dependency was introduced.

The prototype makes the layout, spacing, typography, icons and control states concrete. It does not implement every recommendation: native `prompt` and `confirm` dialogs remain for Rename and deletion. The open decisions below still require developer review.

## Screenshot record

The screenshots captured during the original review have session-local paths and are not durable project sources. The three canonical “before” images are stored in:

```text
docs/assets/ui-design-review/
├── workspace-1280-before.png
├── editor-before.png
└── playback-before.png
```

- [Workspace at 1280 × 800](assets/ui-design-review/workspace-1280-before.png): the first screen with a populated Library.
- [Text editor and controls](assets/ui-design-review/editor-before.png): the editor and controls reached by scrolling.
- [Playback mode](assets/ui-design-review/playback-before.png): the current Paragraph highlighted.

These baseline images were captured on 2026-11-03. Keep them stable. Put “after” and intermediate prototype screenshots in the relevant implementation Issue or pull request rather than accumulating every variant in the repository. Screenshots do not replace manual projector checks of contrast and readability from the back rows.

## Developer review checklist

Review the actual page, not only the code or baseline images:

1. Check out `experiment` and start the program with `runtime\python.exe -X utf8 -m ozvuchka`.
2. Open `http://127.0.0.1:8770` at 1280 × 800 with a populated Library.
3. In the Workspace, check that the Text editor, Voice, Speed and «Слушать» are visible without scrolling. Review the 340 px Library column, the fluid editor column and the proposed 900 px responsive breakpoint.
4. Review the compact Voice picker with its adjacent Listen action, the Narration chips, the per-Text overflow menu and the permanent Text save state.
5. Start playback. Review the «Слушать» / «Пауза» / «Продолжить» toggle, the visible Previous / Repeat / Next controls, disabled Stop and navigation states, hidden Enqueue and sticky transport bar.
6. Confirm that the blue selected Text and yellow current Paragraph are unmistakable, and that skipped Paragraphs remain clear. Check Text size controls and scrolling.
7. Check keyboard operation and visible focus, then a narrow layout around 390 px. Include long Text titles and the complete Voice list.
8. Decide whether each proposal under “Open decisions” is approved or needs adjustment.

Record the review outcome in Issue #27. If the direction is approved, split the implementation into the three stages below. If changes are requested, adjust the prototype first. Do not create implementation Issues before that decision. The projector check remains listed in `docs/manual-checks.md`.

## Implementation stages after prototype approval

Split Issue #27 into three substantial stages only after the prototype is reviewed:

1. **Workspace and playback hierarchy:** responsive layout, visible primary workflow, contextual transport controls and discoverable Paragraph navigation.
2. **Library and Voice density:** quieter Text rows, distinct selection, compact Narrations and Voice/Speed selection.
3. **Visual refinement and feedback:** surfaces, spacing, typography, icons, application dialogs and richer status presentation.

Do not create a separate Issue for every button: the UI is concentrated in a few shared files, and excessively fine-grained tasks would overlap. Accessibility and state correctness are acceptance requirements in every stage, not a separate final cleanup.

## Acceptance criteria for the direction

- At 1280 × 800 with a populated Library, the Text and primary playback action are visible without scrolling.
- Playback controls expose only actions relevant to the current state, and previous/repeat/next are discoverable.
- Selected Text and current Paragraph cannot be confused.
- The complete workflow remains keyboard-operable with visible focus.
- Narrow layouts remain usable without clipped controls or unreadable rows.
- Playback mode remains uncluttered and keeps its sticky controls.
- Current Paragraph, skipped and error states remain distinguishable on a projector.
- No online dependency, UI framework or build step is introduced.

## Open decisions

The prototype proposes the following answers; none is approved yet:

- **Columns and breakpoint:** a 340 px Library column, a fluid editor column and a 900 px single-column breakpoint.
- **Voice selection:** a compact picker with one adjacent Listen action rather than Voice cards.
- **Russian labels:** «Слушать», «Пауза» and «Продолжить»; «Предыдущий абзац», «Повторить абзац» and «Следующий абзац» for Paragraph navigation.
- **Status and save state:** a permanent Text save-state label, one stable status area and a progress indicator only while synthesis is active.
- **Visual tokens:** white surfaces on the warm neutral background, 12 px radii, subtle borders and very light shadows.

## Handoff to a fresh session

1. Read this document and Issue #27 on the `experiment` branch.
2. Inspect the current worktree and preserve any existing work; do not modify or link the main-branch Issues.
3. Run the actual page and use the developer review checklist above. The prototype and baseline screenshots already exist; keep the baseline stable.
4. Record the developer's decision in Issue #27. Do not create implementation Issues or start all three stages before approval.
5. After approval, create the three substantial implementation Issues and begin with Workspace and playback hierarchy.
