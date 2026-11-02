# Library and Text management browser checks

Checked on 2026-11-02 in the built-in Chromium browser against the real HTTP server,
Core and Kokoro provider, using a separate disposable Library under `.cache/`.
The teacher's `data/` was not used.

- Created two Texts and checked autosave before opening another Text.
- Saved an inline title, submitted whitespace and saw the Russian validation error
  while the input remained in place, then corrected and saved it.
- Opened another Text through its row's rename menu and verified focus moved to
  the inline title field. Reopened the previous Text and verified its pending
  content edits had been saved.
- Opened menus with pointer, ArrowDown and ArrowUp; checked Home, End, Enter and
  Escape, including focus returning to the trigger. An autosave completed with a
  menu open: the menu and focused item survived the Library update.
- Checked Text deletion cancellation by button and Escape, then confirmed deletion
  of a disposable Text and observed its row disappear.
- Synthesized a Narration, checked its compact Voice/Speed label and Russian
  removal name, cancelled removal by button and Escape, then confirmed removal.
  The Narration disappeared and its Text remained.
- Checked that each deletion dialog starts on Cancel, describes the consequences
  and returns focus when closed. Shift+Tab from Cancel and Tab from Delete stayed
  within the dialog after the explicit focus containment was added.
- Filtered the Library, reloaded with the current Text excluded from the search
  results and verified its title was still shown. Cleared the search and verified
  the selected Text used blue (`rgb(230, 239, 252)`).
- Played a ready Narration and verified its current Paragraph used yellow
  (`rgb(255, 229, 138)`). Checked the storage size was in the Library footer and
  the destructive menu item was separated from rename.

Standard validation: 112 tests passed (6 slow tests deselected), mypy and ruff
passed, and `node --check ozvuchka/web/app.js` and `git diff --check` passed.
The HTTP test needed a run outside the socket-restricted sandbox. Independent
Standards and Spec reviews found no outstanding findings after fixes.

No new school-hardware acceptance check is introduced by this issue; the existing
projector check for #16 remains in `docs/manual-checks.md`.
