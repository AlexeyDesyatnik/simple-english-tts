# Manual checks on the school computers

Everything the developer has to check by hand on the school laptops, the projector or in class: what no test, CI run or browser check can show. One list for all the work, whichever chat it was done in.

- **Adding**: work that leaves such a check adds it here in the same commit, under where it is done, with its issue.
- **Checking**: tick the box and write the date and what you saw after it (`— 2026-11-03, Celeron: estimate 1:20, real 1:31`). Numbers an issue asks for go in a comment on that issue as well, and the issue's own checkbox is ticked there.
- **Removing**: an item is deleted once it is ticked and its issue is closed; an unticked one stays even if the issue was closed without it. Git keeps the history.

## Getting the program onto a laptop

Take the zip from the latest green build of `main` in GitHub Actions (the run's artifacts) or from GitHub Releases, unblock it before unpacking and copy it to the flash drive: see [development instructions](development.md#unblocking-the-zip) and [copying to a flash drive](development.md#copying-to-a-flash-drive). The program writes only into its `data\` folder; its log is `data\ozvuchka.log`, worth bringing back when something goes wrong.

The laptops: **Celeron** (N4100, no AVX, 3.8 GB, synthesizes slower than speech, about ×0.44) and **i5** (about ×1.85).

## Outstanding hardware checks (#24)

[Issue #24](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/24) owns the
remaining classroom-hardware validation. Use a published release or the archive from
the latest green build of `main`, with a fresh disposable Library. The Issue references
below record where each check originated; #24 is their current owning Issue.

## Adopted main with NumPy 2.3.5 (#24; from #26 and #37)

The older NumPy was previously accepted on Athlon II X2 250 and an 11th-generation
Core i5 with the isolated v0.2 build (#26). The adopted main combines that pin
with the accepted experiment-2 UI. Local/CI checks on a modern CPU do not verify
the new combined archive on the old computer.

- [ ] **Older CPU, #24 (from #26 / #37):** unpack the adopted main archive into a fresh folder on the Athlon II X2 250 (or the target old computer). Start the launcher, paste a short English Text, prepare and play a new Narration, then close/reopen and check that the Text remains and `data/ozvuchka.log` exists. Expect no NumPy import/startup error and correct speech. Use a disposable Library; no speed benchmark is required.

## Adopted UI integrated acceptance (#24; from #37 and stages #28-33)

Stage 10 consolidated the outstanding stage checks below without marking any of
those checks passed. Use the adopted `main` (the accepted `experiment-2` design)
and a disposable Library with 20 Texts, a long title and several ready
Narrations. Browser evidence and the short everyday-use acceptance are in
`docs/design-reviews/issue-37/README.md`. The developer accepted stage 10 on
2026-11-04, explicitly confirming actual 200% browser zoom. The visual refresh
acceptance on 2026-11-06 also confirmed actual 200% zoom and projector/Celeron/i5
visual checks. That acceptance did not supply the device interaction and
performance results or cancellation timings required below.
Record device, date and observations when checking these items.

- [ ] **Projector/classroom, #24 (from #37; preserves #28 and #32):** from the back rows, check UI labels, blue Library selection, centred reading Text and yellow current Paragraph with its blue edge. Try Text sizes 18-80, readable-Paragraph position, skipped instructions and expanded keyboard help; the current Paragraph must start below sticky controls.
- [ ] **Presenter remote, #24 (from #37; preserves #28, #32 and #33):** immediately after Play, without an extra pointer action, check pause/resume, previous/next (arrows and PageUp/PageDown) and repeat (physical R in the Russian layout). Repeat after natural completion and after Library/Voice/help/dialog/native-control use. Native controls retain their own keys while focused; returning to editing stops speech. Compare heard real Kokoro speech with the highlighted Paragraph.
- [ ] **School laptops, #24 (from #37; preserves #28-33):** on both Celeron and i5, check preparation and Playback responsiveness with 20 Texts, a long Text, waiting synthesis, large Text and 200% browser zoom. Scroll/open/close narrow Library, switch Texts, search and use row menus. Open rename/delete dialogs with long titles, check Tab/Shift+Tab containment, Escape and return focus. Narrow Library stays open across actions and cancelled dialogs until explicitly closed. Typed edits remain intact. Delete only disposable Texts/Narrations.
- [ ] **Real Voice and queue responsiveness, #24 (from #37; preserves #31):** on Celeron/i5, open Voice chooser, listen to independent samples, select Voice/Speed and observe queue progress/cancellation while the real offline provider loads and synthesizes. Silent fixtures cannot establish responsiveness or sound on these devices.
- [ ] **Immediate real cancellation, #24 (from #37; preserves #31 / ADR-0004):** while Alice synthesizes a long Text and George waits, cancel Alice and record time until George starts. Repeat cancellation/re-enqueue. No old computation should continue for minutes, no cancellation error should appear, and completed Paragraphs must remain usable. Use disposable data; development-PC/fake timings do not establish native cancellation latency on Celeron/i5.
