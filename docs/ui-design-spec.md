# UI design specification — experiment-2

## Authority and scope

This specification defines the independent UI design implementation on `experiment-2`.
The developer treats the work on this branch and the two other implementation tracks as
three alternatives. Existing Issues and implementations on other branches are not
dependencies, acceptance criteria, or sources of implementation work for this track.
Do not close, modify, or reuse their Issues. The stage Issues linked below belong only
to this specification and branch.

This document is the design source of truth; GitHub Issues hold the implementation
stages. The developer explicitly requested the specification in project documentation.
Project documentation is in English; all teacher-facing text is in Russian.

## Goals

- Keep the current Text and primary playback action visible on the first laptop screen.
- Prevent the Library from pushing the working area below the fold as it grows.
- Reduce competition between content, settings, and Library maintenance actions.
- Make playback, Narration preparation, saving, and failure states understandable.
- Preserve large Text, strong current-Paragraph highlighting, keyboard control, and
  presenter-remote mappings.
- Support narrow windows and browser zoom without clipped controls.
- Avoid new Windows-specific UI dependencies in preparation for future portability.

## Architecture and exclusions

Keep the plain HTML/CSS/JavaScript page, with no framework, build step, online assets,
or new browser-test stack. Core owns application decisions and state that must survive
page reload; HTTP only translates commands, events, snapshots, and assets. Do not use
localStorage as a second source of application state. Preserve atomic Library writes
and storage within the portable application's data folder.

The scope excludes porting the launcher to Linux/macOS, changing the Voice provider,
Voice catalogue, synthesis algorithm, audio scheduling, Speed values, queue semantics,
or Start delay calculation. It also excludes dark mode, import/export, cloud features,
new branding, and a separate mobile application. Platform-neutral UI is not a claim
that the whole application already runs on every OS. ADR-0003's current Windows launch
mechanism remains in place; no ADR change is needed for the font and layout changes.

## Preparation workspace

On a wide window, use a two-column workspace: Library navigation on the left and the
current Text on the right. Start with a Library width of 280–320 CSS pixels and a
workspace maximum width around 1440 pixels; refine in the browser.

The Library contains search, New Text, Text rows, and ready Narration information.
The working area contains the Text title, save state, compact Voice/Speed settings,
labelled editor, and actions. A compact status area presents preparation and queue
information without shifting the editor or primary control during routine updates.

Below approximately 960 pixels, expose the Library through a disclosure and keep the
current Text central. Opening or closing it must preserve edits and work position.
The exact breakpoint is adjustable to fit real content and font metrics.
The narrow Library disclosure opens above the working area without moving the editor.
Bound its height and scroll its contents as one panel; close it on Escape, outside
pointer input, focus leaving the panel, or choosing/creating a Text. It is a non-modal
disclosure, so preserve the native Tab order and return focus appropriately.
On desktop, constrain the working title to two lines with its full title accessible,
so an unusually long title does not displace the editor and primary action.

Give the editor a permanent `Текст` label and a separate short explanation that each
line is a Paragraph. Remove the duplicate rendered Paragraph list from preparation;
use it in Playback mode. The primary action is `Воспроизвести`; the secondary action
is `Подготовить озвучку`, using the existing enqueue command. Do not show irrelevant
Pause/Stop actions in the stopped preparation state.

At 1280 × 720 and 100% browser zoom, with 20 saved Texts, the editor and primary action
must be visible without scrolling the page. Aim for at least six visible editor lines.
Library growth must not move these controls down. Prefer bounded Library scrolling on
desktop and avoid adding unnecessary nested scrolling to the editor/workspace.

## Library

The main part of a Text row opens it. Use a restrained blue selected state; reserve
yellow for the current spoken Paragraph. Long titles must wrap or truncate cleanly,
with the complete title accessible when needed.

Move rename/delete into an always-discoverable row menu available to pointer and
keyboard users, never hover-only. Show ready Narrations as readable labels such as
`Готово · Alice · 1×`. Replace tiny inline deletion crosses with an accessible action.
Keep total storage size secondary. Distinguish an empty Library from an empty search
result. Searching must not remove the current Text from the working area.

Stage 3 bounds row titles to three visible lines, retaining the full accessible name
and title tooltip. Ready Narration labels stay in the row; their removal actions live
in the row's always-visible ellipsis disclosure alongside rename and Text deletion.
Only one row disclosure is open at a time. Escape closes it and focuses its summary;
Tab leaving it or a click outside closes it. Actions remain in document flow inside
the bounded Library scroll area, with targets at least 44 CSS pixels high.

## Voice, Speed, and Narration queue

Keep selected Voice and Speed visible near the editor; disclose the full Voice list
on request. Selecting a Voice and listening to its Voice sample are separate actions:
auditioning must not change selection. Explain loading and unavailable Voices in text.
Confirming a Voice by pointer, Enter or Space closes the chooser and restores focus
to its summary. While open, arrow keys move focus between Voice choices without
changing the selected Voice; Enter or Space confirms it. Escape closes without choosing.
Use a single-column Voice list when space is limited; retain the clearly named normal
Speed. No options may be clipped.

Show a compact Narration queue summary with expandable details. Keep existing estimates,
ready Paragraph counts, and cancellation. The queue's appearance must not displace the
primary action or editor. Do not invent progress precision or new timing calculations.

## Playback mode

Hide Library, editor, and Voice settings. Retain Text, compact transport, and status.
Use a primary state-dependent action: `Пауза` while playing or waiting,
`Продолжить` while paused, and `Воспроизвести` when ready to start.
Expose previous Paragraph, repeat, and next Paragraph through existing Core commands.
Show position such as `Абзац 2 из 8`, counting readable Paragraphs.

Provide `К редактированию`, which stops through the existing command and returns to
the prepared Text. Place it beside the Text title in a separate header row, with an
exit SVG and a tooltip explaining that it stops playback and returns to editing.
Separate that row from the transport with spacing and a border; in narrow windows
keep the exit on its own row above the transport.

Group the transport in the order previous Paragraph, primary Pause/Continue action,
next Paragraph. Put `Повторить абзац` beside that group with a small gap, retaining
one filled primary action. Keep the navigation group together in narrow windows
where it fits, with repeat and Text size tools wrapping below it.
This arrangement was approved during the stage 1 visual review on 2026-11-03;
stage 5 completes its behavior and integrated verification.

Do not show enqueue here. Keep Text size controls near the reading
tools and provide compact keyboard help and a hint about starting from a Paragraph.

Centre reading Text and constrain line length relative to Text size, initially around
60–75 characters at ordinary size. Large Text must retain useful margins and accessible
controls. Preserve yellow highlighting with a blue edge, distinguish skipped and failed
Paragraphs, and keep the current Paragraph visible without hiding it behind the sticky
transport. Do not introduce new end-of-playback semantics as a styling change.

## Saving and feedback

Autosave after a short pause in typing, coalescing writes. Distinguish unsaved changes,
saving, confirmed saved state, and failure. `Сохранено` means a confirmed disk write,
not merely dispatching a request or receiving a generic HTTP success.

Flush latest edits before opening another Text, creating a Text, playback, or enqueue.
Do not complete a transition that could lose edits when saving fails. Older requests
or responses must neither overwrite newer edits nor mark newer unsaved content saved.
Snapshot updates must preserve typing, cursor, and selection.

Confirmed saves survive F5 and reopening. Handle ordinary immediate reload/page hide
separately from idle autosave, including an older in-flight request. Document the exact
guarantees: unsent edits cannot be guaranteed after process termination or a crash.
Keep required state in Core and preserve the existing heartbeat lifecycle.

Errors must remain readable until resolved or dismissed, with a retry path where
applicable. Routine polling must not erase an actionable error. Reserve room for normal
status updates; longer error text may expand accessibly rather than being clipped.

## Visual language and platform-neutral typography

Keep a warm light background, dark readable text, and a blue accent. Use blue tint for
selection, yellow for the current Paragraph, and red for errors/destructive actions.
Define a small CSS token set for colours, surfaces, borders, spacing, radii, and controls.

Initial guidelines:

- UI text 16–18 px; secondary text at least 14 px; Text size remains independent.
- Spacing steps 4, 8, 12, 16, 24, and 32 px.
- Interactive targets approximately 44 × 44 px or larger, especially small menu actions.
- Moderate 8–10 px radii, thin borders, minimal shadows.
- One filled primary action per working context; quieter secondary actions.
- Explicit hover, pressed, focus-visible, selected, disabled, and loading states.
- Information must not rely on colour alone; target 4.5:1 contrast for ordinary text
  and 3:1 for essential control boundaries/focus indicators against adjacent colours.

Use `system-ui, "Noto Sans", "Liberation Sans", sans-serif`. These are fallbacks, not
installation requirements. Do not privilege Segoe UI or require a Windows-only font.
No network font loading. Small OS-dependent typographic differences are acceptable;
the layout must tolerate different metrics. A bundled font, if later needed for exact
consistency, is a separate decision including licensing and packaging.

Use consistent inline SVG icons, not an icon font or platform-dependent emoji. Keep
text labels on principal actions. Avoid decorative animation and honour reduced-motion
preferences for nonessential scrolling/transitions.

## Accessibility and application dialogs

Every control needs an accessible name and visible focus. Clickable Paragraphs must
be keyboard operable. Do not let playback shortcuts capture normal input in fields,
native controls, menus, or dialogs. Preserve Space, arrows, PageUp/PageDown, and R,
including physical-key R in Russian layout, when playback shortcuts apply.

Replace native rename/delete prompts with application dialogs with labelled input or
clear Russian consequences. Support cancel/Escape, focus containment where modal, and
focus restoration. Keyboard control must still work after opening/closing disclosures,
menus, help, and dialogs. Destructive confirmation must identify the affected Text or
Narration and describe the Narration queue using glossary terminology.

## Verification and completion

Check the actual page through its visible controls against Core/HTTP with an isolated
Library. Existing FakeVoiceProvider/FakeClock may provide deterministic readiness,
loading, waiting, and failures; do not replace the application with a static mock.
Do not use the teacher's Library for destructive checks.

Check 1440 × 900, 1280 × 720, 390 × 844, and browser zoom at 200%. At desktop baseline
sizes the editor and primary action are initially visible; narrow/zoomed views may
scroll vertically but must not clip controls or overflow the page horizontally.
Exercise 0, 1, and 20 Texts, long titles, several Narrations per Text, empty search,
Voice loading/unavailability, preparation, pause, errors, and large Text.

Check keyboard journeys, focus restoration, Voice samples, queue cancellation, skipped
Paragraphs, Text transitions, reloads, and persistence as relevant to each stage.
Record browser/OS and what was actually checked; do not claim untested platforms.
Retain final screenshot artifacts and a concise browser-check record with reproducible
setup. Do not treat temporary screenshots from this chat as durable project inputs.

Run pytest, mypy, and ruff before each commit as CODING_STANDARDS.md requires. Add
behaviour tests through public seams when Core behaviour changes; do not add tests
that merely assert CSS/DOM structure. Slow tests apply if provider/build code changes.

Hardware-only acceptance belongs in `docs/manual-checks.md` in the same implementation
commit that creates the need, with its stage Issue: projector/back-row readability,
presenter remote, and school-laptop responsiveness. Browser checks do not establish
these outcomes. This planning document does not mark any of them complete.

## Delivery stages and fresh-session handoff

Implement the ten stages sequentially, each in a fresh bounded session if useful.
They are sized for GPT-6.1 Sol with room for inspection, implementation, browser checks,
and fixes; this is a scope discipline, not an exact model context-capacity guarantee.
Keep most UI stages in the three web files. Split unexpected cross-layer work rather
than combining a player rewrite, persistence change, and layout revision in one stage.

1. Visual direction: tokens and browser-checkable workspace/Playback mode prototype.
2. Workspace layout: wide/narrow structure and visible editor/primary action.
3. Library: rows, selection, ready Narrations, search/empty states, action menus.
4. Voices and queue: compact choice, samples, availability, stable queue summary/details.
5. Playback mode: transport, Paragraph navigation/progress, reading layout, return.
6. Dialogs and keyboard: application dialogs, title editing, focus and shortcut journeys.
7. Save acknowledgement: minimal Core/HTTP contract and ordering guarantees.
8. UI autosave: debounce, save states, flush-before-action, typing stability, retry.
9. Reload/page-hide safety: pending edits, request races, lifecycle and documented limits.
10. Integrated acceptance: complete visual/interaction matrix and small corrective fixes.

Stage 1 presents both screens for design review before detailed implementation.
Stage 6 completes dialogs that stages 3–4 may temporarily implement with existing
confirmations. Accessibility is required throughout, not deferred to stage 6 or 10.
Stages 7–9 are deliberately separate: do not hide persistence work in styling changes.
Stage 10 must not become an unbounded redesign; split substantial discoveries into
new Issues for this track.

Each handoff records the stage goal/exclusions, changed files and public contracts,
acceptance checks, resulting commit, screenshot/check record, and remaining limitations.
Read this document, AGENTS.md, relevant glossary/ADR entries, CODING_STANDARDS.md, the
current stage Issue, and the preceding handoff. Do not require the full chat history.

### Issue index

1. [Establish the visual direction](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/28)
2. [Build the preparation workspace layout](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/29)
3. [Refine Library rows and actions](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/30)
4. [Compact Voice selection and Narration queue](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/31)
5. [Improve Playback mode and reading layout](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/32)
6. [Finish application dialogs and keyboard journeys](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/33)
7. [Define reliable save acknowledgement and ordering](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/34)
8. [Add visible autosave and safe Text transitions](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/35)
9. [Protect edits across reload and page hide](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/36)
10. [Complete integrated visual and interaction acceptance](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/37)
