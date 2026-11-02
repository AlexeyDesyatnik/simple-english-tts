# Playback shortcuts after disclosures

Checked on 2026-11-02 in the built-in Chromium browser against the real HTTP
server, Core and Kokoro provider, using a disposable Library under `.cache/`.
A second server used the same page and Core with a Voice provider held in
synthesis, to keep the waiting state deterministic. The teacher's `data/`
was not used.

Before the fix, opening and closing playback help with the pointer left focus
on its summary. Space reopened help instead of pausing playback.

- Opened and closed each of the Library, Voice and playback-help disclosures
  with the pointer, Enter then Space, and Enter then Escape. With a playable
  Text, closing returned focus to Play without an extra click or Tab.
- After each of these nine journeys, used Space, both horizontal arrows,
  PageUp/PageDown and R. Observed the actual Core snapshots around the commands:
  next moved Paragraph 0 to 1, previous moved 1 to 0, repeat kept Paragraph 0,
  and Space paused playback. Paragraph numbers here are zero-based.
- Opened and closed help by all three methods during playing and paused states.
  Checked Space pause/continue in both directions; separately paused before
  each navigation/repeat key and verified it resumed at the requested Paragraph.
- Repeated help open/close journeys while waiting. Space changed waiting to
  paused and back; arrows and PageUp/PageDown moved 0 -> 1 -> 0, and R kept 0,
  with Core remaining waiting for synthesis. These observations came from the
  server's command journal, rather than button labels alone.
- Typed Space and R and used arrows and PageUp/PageDown in Library search,
  the title input and the editor. Radio arrows selected the next Voice, and
  select arrows changed Speed. On an open disclosure summary, Space opened the
  panel, while R and PageDown did not send playback commands.
- Opened the Library menu with ArrowDown and ArrowUp, moved to Delete using
  ArrowDown, and used Space to open its dialog. R, arrows and PageDown did not
  control playback inside the menu/dialog. Escape restored the menu trigger;
  dialog Tab/Shift+Tab stayed inside, Space cancelled and restored its trigger.
  Closing the Library afterwards returned focus to Play.
- The server recorded no playback commands during the field, disclosure,
  Voice, menu and dialog interaction checks.
- Creating a new Text in the narrow Library left focus in the editor after
  the Library collapsed. With an empty Text and Play disabled, closing the
  Library kept its summary focused instead of moving to a disabled control.

Library and Voice panels are hidden in Playback mode, so their close-then-control
journeys start in preparation; help can be exercised during playing, paused and
waiting states. The existing physical `KeyR` mapping is unchanged. The browser
input tool cannot send a Russian-layout physical key, so that hardware check
and the actual presenter remote remain in `docs/manual-checks.md` under #21.

Validation: 112 pytest tests passed (6 slow tests deselected), mypy, ruff,
`node --check ozvuchka/web/app.js` and `git diff --check` passed. No page test
framework or internal test seam was added.
Independent Standards and Spec reviews found no implementation findings;
the physical Russian-layout and presenter checks remain pending.
