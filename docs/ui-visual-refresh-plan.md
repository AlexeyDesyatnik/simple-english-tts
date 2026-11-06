# UI visual refresh plan

Date: 2026-11-05. Status: complete. All six implementation stages were committed, browser
and release verification was recorded, and the developer confirmed all requested manual
acceptance checks on 2026-11-06.

## Authority and relationship to the accepted UI

This completed plan records the target visual language and delivery sequence for the UI
update. It supplements the [accepted UI design specification](ui-design-spec.md), which
remains authoritative for application behaviour, terminology, accessibility, responsive
disclosures, persistence and Playback mode. The plan describes design targets rather than
the current appearance; implementation and acceptance evidence is in the
[refresh browser/release record](design-reviews/ui-visual-refresh/README.md).

The refresh changes presentation, not the accepted interaction model. If a visual proposal
conflicts with an existing behavioural requirement, preserve the behaviour and resolve the
conflict explicitly rather than silently changing the product.

## Problem and intended outcome

The two-column preparation workspace and the focused Playback mode already work and their
usability is accepted. The dated appearance comes primarily from visual details: strong
outlines around most controls, native disclosure markers, similarly weighted rectangular
buttons, heavy titles and insufficient separation between primary and secondary information.

The target is a calm, contemporary teacher's tool described as **paper and ink**: a warm
light background, white working surfaces, an ink-blue accent and a soft amber current
Paragraph. It should look deliberate and modern without becoming a decorative dashboard or
competing with the Text during a lesson.

## Goals

- Make the accepted interface visually contemporary while preserving its layout logic and
  everyday workflows.
- Establish clearer hierarchy through typography, spacing and quiet surfaces rather than
  additional panels and borders.
- Give Library, preparation and Playback mode distinct but consistent visual treatment.
- Keep Text, the primary action, current Paragraph and actionable status visually dominant
  in their respective contexts.
- Retain readable contrast, 44 px interactive targets, visible keyboard focus and large
  Text on narrow screens and projectors.
- Keep every asset local and the page understandable without a framework or build step.

## Non-goals and boundaries

- Do not change Text/Voice/Speed selection, Narration preparation, the Narration queue,
  saving, Playback commands, Paragraph semantics, keyboard shortcuts or dialog behaviour.
- Do not change Core, HTTP contracts, persistence, audio scheduling, Voice providers or the
  launcher for visual reasons.
- Do not introduce a CSS/JavaScript framework, a component library, an icon font, remote
  assets or a frontend build step.
- Do not add dark mode, a separate mobile layout philosophy, new branding, import/export or
  other product features to this work.
- Do not use glassmorphism, decorative gradients, nested cards, heavy shadows, pill-shaped
  controls everywhere or icon-only principal actions.
- Do not reduce secondary text below 14 px, remove visible focus or use low contrast to make
  the interface appear lighter.

Most work should stay in `ozvuchka/web/style.css` and, for inline SVG or presentational
structure, `ozvuchka/web/index.html`. Change `app.js` only for state-independent presentation
that cannot be expressed cleanly in HTML/CSS. A locally bundled font additionally requires
packaging and licence updates. Any broader change must be called out and split rather than
hidden inside a visual stage.

## Visual language

### Colour and surfaces

Use the existing token approach, extended where necessary to distinguish decorative
dividers from essential control boundaries. These values are the starting design target;
measure contrast and adjust them before final acceptance if required.

| Role | Starting value | Use |
| --- | --- | --- |
| Background | `#F7F6F2` | Warm application background |
| Surface | `#FFFFFF` | Workspace, panels, editor and overlays |
| Primary text | `#202733` | Titles, controls and reading Text |
| Secondary text | `#667085` | Metadata and explanations |
| Accent | `#315FCC` | Primary action, focus and selected-state emphasis |
| Selected background | `#EAF0FC` | Current Library Text and selected Voice |
| Current Paragraph | `#FFF0B8` | Spoken Paragraph background |
| Divider | `#E3E5E8` | Nonessential separators |
| Error | existing `#AD2824` | Errors and destructive confirmation |

Keep one filled primary action per working context. Use thin separators, approximately
10–12 px radii and no routine shadows on controls. Shadows belong to floating Voice/Library
surfaces and dialogs, where they help establish layering. Selection, errors and the current
Paragraph must retain text or shape cues in addition to colour.

### Typography

Prefer a locally bundled **Onest** font with complete Russian and English glyph coverage,
subject to licence, file-size, rendering and layout checks. Package its licence and include
the font in offline/release assets; never fetch it from a font service. Retain the existing
platform-neutral system stack as fallback. If the bundled font causes clipping, poor
readability or disproportionate packaging cost, keep the system stack and record that
decision in the implementation handoff rather than adding another font dependency.

Use one font family for UI, editor and Playback text. The initial hierarchy is:

- UI body: 16 px, line height 1.5;
- metadata and explanations: 14 px or larger;
- workspace title: 24–26 px, weight 600, line height about 1.25–1.3;
- section titles: 20 px, weight 600;
- editor: about 17 px with comfortable line height;
- Playback text: controlled only by the existing independent Text size setting.

Use weight, size and spacing to establish hierarchy; avoid all-uppercase labels and excessive
letter spacing. Long-title limits and accessible full names remain as specified for the
current UI.

### Controls and icons

- Primary buttons use the accent fill and a readable text label.
- Secondary actions prefer quiet tonal or ghost treatment; use a persistent outline only
  where it helps identify the control. Hover, pressed, selected, disabled and focus-visible
  states must remain explicit.
- Inputs retain recognizable boundaries and receive a clear accent focus ring. Do not apply
  the low-contrast decorative divider token to an essential control boundary without meeting
  the 3:1 requirement.
- Use consistent inline SVG icons, normally 20 px with a consistent stroke, for Play/Pause,
  previous/next, rename, search, readiness and disclosure arrows. Principal actions retain
  text labels and every icon-only action retains an accessible name and tooltip.
- Replace the visual mixture of native disclosure triangles and boxed ellipsis controls with
  a coherent disclosure/icon style without changing native keyboard semantics.

### Motion and feedback

Use only restrained 120–160 ms transitions for hover, pressed and disclosed visual states.
Honour `prefers-reduced-motion`. Do not animate layout in a way that moves the editor or
primary action during routine status updates.

Saving, ready, waiting and failure states may gain small supporting icons, but their existing
Russian text remains authoritative. Errors stay visible with their current retry/dismissal
paths; do not replace them with disappearing toast notifications. Do not invent determinate
Narration progress.

## Screen direction

### Library

Treat Library as one coherent side panel rather than a stack of unrelated outlined controls.

- Give search a quiet field treatment and a small search icon.
- Make `Новый текст` a tonal action that does not compete with `Воспроизвести`.
- Give the selected Text a rounded, full-row selected background and readable title.
- Present ready Narrations as subdued metadata with a small readiness cue, not bright badges.
- Make the row menu a quiet ghost action while retaining its 44 px target and always-visible
  discovery.
- Keep Library size visually tertiary. Its DOM position may remain unchanged if the visual
  hierarchy is clear.
- Preserve bounded scrolling, three-line row titles, empty/search-empty distinctions and all
  row-menu keyboard/focus behaviour.

### Preparation workspace

Use one white working surface with a subtle boundary. Remove visual nesting where a spacing
or divider already provides structure.

- Keep the preparation eyebrow and long title, but reduce their visual weight.
- Present rename as a small pencil action associated with the title rather than a competing
  outlined block below it; keep its accessible name and dialog.
- Group Voice and Speed visually in a quiet settings area without changing their controls or
  disclosure behaviour.
- Pair confirmed save text with a small check; keep failure and retry unmistakable.
- Lighten the editor's resting visual treatment while preserving a clear boundary and strong
  focus state. The Text remains the main content.
- Keep `Воспроизвести` dominant and `Подготовить озвучку` secondary.
- Preserve initial editor/Play visibility at 1280 × 720 and stable layout during status and
  Narration queue updates.

### Playback mode

Make Playback mode feel like a dedicated reading screen, not merely the preparation form
with fields hidden.

- Retain the current header and sticky transport order, presented as a compact, calm toolbar.
- Use familiar transport icons together with the existing accessible names; keep the primary
  Pause/Continue/Play action filled.
- Separate readable-Paragraph position visually from technical Narration status.
- Make reading and keyboard hints quieter without removing access to them.
- Keep reading Text centred with a measure around 65–70 characters at ordinary Text size.
- Retain a soft amber current Paragraph with an ink-blue leading edge, comfortable padding
  and no competing decoration on other Paragraphs.
- Preserve skipped/failed Paragraph cues, large Text, natural-completion state, sticky-control
  clearance and all keyboard/presenter behaviour.

## Implementation sequence

Implement the stages in order, in separately reviewable commits. Each stage uses the real
page and Core with an isolated Library, not a static mock. Do not reopen or repurpose the
completed #28–#37 design stages; if GitHub tracking is wanted, create distinct Issues for
this refresh.

### Stage 1 — Visual foundation

**Change:** define the refreshed colour/surface/type/control tokens; decide and, if accepted,
bundle Onest with its licence and offline packaging; establish global typography, button
variants, input focus, disclosure/icon basics and reduced-motion rules.

**Acceptance:** all existing screens remain usable; one primary action remains per context;
ordinary text contrast is at least 4.5:1 and essential boundaries/focus at least 3:1;
44 px targets and visible focus survive; no remote asset request, framework or build step is
introduced. Capture preparation and Playback at 1440 × 900 and 1280 × 720 for visual review
before refining individual screens.

### Stage 2 — Library visual refinement

**Change:** implement the coherent panel, search/New Text treatment, selected Text rows,
ready Narration metadata, quiet row actions and refined scrolling/dividers.

**Acceptance:** check 0, 1 and 20 Texts, long titles and several ready Narrations. Selection
is clear without relying only on colour; search-empty and Library-empty remain distinct;
menus, rename/delete disclosures, focus return and narrow-Library persistence behave exactly
as before. Library growth does not move the editor or primary action.

### Stage 3 — Preparation workspace visual refinement

**Change:** refine the workspace surface, title/rename relationship, Voice/Speed area, editor,
save feedback, primary/secondary actions and Narration queue presentation.

**Acceptance:** at 1280 × 720 with 20 Texts and a long title, the editor and Play remain
initially visible with at least six editor lines. Voice loading/unavailability, independent
Voice samples, Speed, queue details/cancellation, saving and errors remain readable and do
not shift routine controls. Check narrow layout and actual 200% zoom for clipping.

### Stage 4 — Playback mode visual refinement

**Change:** implement the compact header/transport, icon treatment, position/status hierarchy,
quiet help and refined reading Text/current Paragraph presentation.

**Acceptance:** exercise Play, Pause/Continue, previous/next, repeat, Paragraph activation,
skipped/failed Paragraphs, natural completion, reload and return to editing. Check Text sizes
18–80, long/tall Paragraphs and sticky-control clearance at desktop and narrow sizes. Entering
Playback mode still focuses the reading workspace; shortcuts and focus restoration are
unchanged.

### Stage 5 — Overlays, feedback and responsive polish

**Change:** bring Voice chooser, narrow Library surface, application dialogs, queue, errors,
save states and disabled/loading treatments into the same visual system; add only the approved
subtle transitions; correct remaining narrow/zoom visual inconsistencies.

**Acceptance:** check 1440 × 900, 1280 × 720, 390 × 844 and actual 200% browser zoom. There
is no horizontal page overflow or clipped option/action. Dialog containment, Escape/cancel,
focus restoration, persistent errors and retry/dismissal remain intact. Reduced-motion mode
removes nonessential transitions.

### Stage 6 — Integrated visual acceptance and documentation

**Change:** perform the complete browser review on the real application with disposable
Libraries; fix small visual regressions; retain final screenshots and a concise reproducible
check record under `docs/design-reviews/ui-visual-refresh/`; update the accepted UI
specification/current-design references and the Russian README screenshot to match the shipped
interface.

Add the resulting projector/back-row visual acceptance to `docs/manual-checks.md` in the same
implementation commit, including readability of the new hierarchy, selection, control states
and amber current Paragraph. Keep existing unticked hardware checks until their own removal
rules are met. Give the developer a short everyday-use acceptance covering preparation,
Playback, a narrow window and actual 200% zoom; browser automation does not mark hardware
checks passed.

## Verification required for every implementation stage

Run from the repository root before each commit:

```bat
runtime\python.exe -m pytest
runtime\python.exe -m mypy
runtime\python.exe -m ruff check
git diff --check
```

Run the slow suite as well if provider/build code changes, and the release smoke test if the
build or launcher changes. Do not add CSS/DOM assertion tests or a new browser-test stack.
Browser verification belongs against the real page through its visible controls, using an
isolated Library and the existing preview/fake seams where deterministic states are useful.

At minimum, the integrated review covers 0, 1 and 20 Texts; long titles; multiple Narrations;
Voice loading/unavailability; save states; waiting/progress/cancellation; empty actions;
synthesis failure/retry; Playback completion; dialogs; keyboard journeys; large Text; narrow
layout and actual 200% zoom. Record what was actually checked and do not claim untested
platforms, devices, sound quality or assistive-technology coverage.

## Definition of done

The refresh is complete only when all six stages are implemented and reviewed, the accepted
behaviour is unchanged, all required automated checks pass, the browser matrix has no visual
or interaction regression, assets work offline in the release package, contrast/target/focus
requirements are met and documentation/screenshots describe the resulting interface rather
than this target plan. Outstanding projector, presenter-remote and school-laptop checks must
be reported explicitly rather than inferred from desktop browser evidence.
