# Narrow-window workflow browser checks

Checked on 2026-11-02 in the built-in Chromium browser against the real HTTP
server, Core and Kokoro provider, with a separate Library in `.cache/issue20-data/`.

At 390 x 844:

- Created a three-Paragraph Text, observed unsaved and saved states, found it by
  Library search, opened it, renamed it inline and edited its content.
- Opened the Library and Voice disclosures using Space. Opening a Text collapsed
  the Library and focused the editor. Selected George and Speed 0.8, listened to
  his sample and closed the Voice panel with Escape.
- Enqueued and synthesized a real Narration, played it, paused using Space,
  continued, navigated and repeated Paragraphs, then stopped using Space and
  returned to preparation. Enter on a Paragraph also started playback.
- Playback controls were at least 44 pixels high, with no horizontal overflow.
  All eight Voice rows fitted the panel; sample buttons were 44 pixels high.
- Opened the Library menu with ArrowDown, navigated with End and activated its
  deletion action with Enter. Escape closed only the menu and restored its trigger.
- Checked deletion cancellation, initial Cancel focus and Tab/Shift+Tab containment.
  A long unbroken Text title wrapped inside the Library and deletion dialog;
  the dialog was 343 pixels wide inside the 375-pixel page content area.
- Resized with a deletion dialog open, then cancelled it: focus returned to the
  collapsed Library summary. Submitted a blank title and checked the Russian
  error remained visible; cancelled the edit afterwards.
- Checked an active 16-Paragraph Narration queue: its title, progress and Cancel
  action fitted without clipping. Cancel was 44 pixels high.

Compared Core snapshots before and after 390 -> 1440 -> 390 while paused:
Text, content, Voice, Speed, Text size, queue and playback position were identical.
Repeated resizing through 1280 with an active queue: its Narration ID, Text
content, settings and playback state were unchanged while synthesis progressed.
No resize handler sends a Core command.

At both 1440 x 900 and 1280 x 720, the editor ended at y=393 and the primary
action at y=497, within the first screen. Library and Voice selection retained
their behavior. Page scroll width equalled its client width at all three sizes.
Routine save messages use a fixed 48-pixel slot; errors can expand and wrap.

Validation: 112 pytest tests passed (6 slow tests deselected), mypy, ruff,
`node --check ozvuchka/web/app.js` and `git diff --check` passed. The HTTP test
needed loopback access outside the socket-restricted sandbox. No page test
framework or internal test seam was added. Independent Standards and Spec
reviews found one Escape propagation issue, fixed and verified in the browser.

School-laptop responsiveness, projector readability and presenter-remote
acceptance remain in `docs/manual-checks.md` under #20.
