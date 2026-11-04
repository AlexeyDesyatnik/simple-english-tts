# Manual checks on the school computers

Everything the developer has to check by hand on the school laptops, the projector or in class: what no test, CI run or browser check can show. One list for all the work, whichever chat it was done in.

- **Adding**: work that leaves such a check adds it here in the same commit, under where it is done, with its issue.
- **Checking**: tick the box and write the date and what you saw after it (`— 2026-11-03, Celeron: estimate 1:20, real 1:31`). Numbers an issue asks for go in a comment on that issue as well, and the issue's own checkbox is ticked there.
- **Removing**: an item is deleted once it is ticked and its issue is closed; an unticked one stays even if the issue was closed without it. Git keeps the history.

## Getting the program onto a laptop

Take the zip from the latest green build of `main` in GitHub Actions (the run's artifacts) or from GitHub Releases, unblock it before unpacking and copy it to the flash drive: see README, "Unblocking the zip" and "Copying to a flash drive". The program writes only into its `data\` folder; its log is `data\ozvuchka.log`, worth bringing back when something goes wrong.

The laptops: **Celeron** (N4100, no AVX, 3.8 GB, synthesizes slower than speech, about ×0.44) and **i5** (about ×1.85).

## Waiting for the work

Checks the issues ask for, to be done once the work is in a release:

## Startup failure messages (#25)

- [ ] **Launcher failure messages, #25:** on a Windows PC (a school laptop is best), with a disposable unzipped copy of the adopted main zip: (1) start Озвучка.exe normally: the window opens and `data\ozvuchka.log` appears. (2) Close it, then rename the `data` folder to `data-old` and create a plain empty *file* named `data` in its place; start Озвучка.exe again. Expect a Russian message with the exit code saying that the `data\` folder cannot be created or written, and that no log was written. It must not mention `data\ozvuchka.log`. Then delete the file `data` and rename `data-old` back. Record the Windows version and the message text.
- [ ] **Early startup output, #25:** on the same kind of disposable unzipped copy: rename its `ozvuchka` folder (the program package) to `ozvuchka-off`, delete `data` if present, then start Озвучка.exe. Expect the Russian message saying the program closed before its log started and that the output is in `data\startup-output.txt`, and that file to contain `No module named ozvuchka` (the exact text may differ). Then rename `ozvuchka-off` back. Record the Windows version and the message text.

## Adopted main with NumPy 2.3.5 (#26, #37)

The older NumPy was previously accepted on Athlon II X2 250 and an 11th-generation
Core i5 with the isolated v0.2 build (#26). The adopted main combines that pin
with the accepted experiment-2 UI. Local/CI checks on a modern CPU do not verify
the new combined archive on the old computer.

- [ ] **Older CPU, #26 / #37 integration:** unpack the adopted main archive into a fresh folder on the Athlon II X2 250 (or the target old computer). Start the launcher, paste a short English Text, prepare and play a new Narration, then close/reopen and check that the Text remains and `data/ozvuchka.log` exists. Expect no NumPy import/startup error and correct speech. Use a disposable Library; no speed benchmark is required.

## Adopted UI integrated acceptance (#37; stages #28-33)

Stage 10 consolidates the outstanding stage checks below without marking any of
those checks passed. Use the adopted `main` (the accepted `experiment-2` design)
and a disposable Library with 20 Texts, a long title and several ready
Narrations. Browser evidence and the short everyday-use acceptance are in
`docs/design-reviews/issue-37/README.md`. The developer accepted stage 10 on
2026-11-04, explicitly confirming actual 200% browser zoom. Device-specific
results and cancellation timings below have not been recorded; browser acceptance
does not supply those measurements.
Record device, date and observations when checking these items.

- [ ] **Projector/classroom, #37 (preserves #28 and #32):** from the back rows, check UI labels, blue Library selection, centred reading Text and yellow current Paragraph with its blue edge. Try Text sizes 18-80, readable-Paragraph position, skipped instructions and expanded keyboard help; the current Paragraph must start below sticky controls.
- [ ] **Presenter remote, #37 (preserves #28, #32 and #33):** immediately after Play, without an extra pointer action, check pause/resume, previous/next (arrows and PageUp/PageDown) and repeat (physical R in the Russian layout). Repeat after natural completion and after Library/Voice/help/dialog/native-control use. Native controls retain their own keys while focused; returning to editing stops speech. Compare heard real Kokoro speech with the highlighted Paragraph.
- [ ] **School laptops, #37 (preserves #28-33):** on both Celeron and i5, check preparation and Playback responsiveness with 20 Texts, a long Text, waiting synthesis, large Text and 200% browser zoom. Scroll/open/close narrow Library, switch Texts, search and use row menus. Open rename/delete dialogs with long titles, check Tab/Shift+Tab containment, Escape and return focus. Narrow Library stays open across actions and cancelled dialogs until explicitly closed. Typed edits remain intact. Delete only disposable Texts/Narrations.
- [ ] **Real Voice and queue responsiveness, #37 (preserves #31):** on Celeron/i5, open Voice chooser, listen to independent samples, select Voice/Speed and observe queue progress/cancellation while the real offline provider loads and synthesizes. Silent fixtures cannot establish responsiveness or sound on these devices.
- [ ] **Immediate real cancellation, #37 (preserves #31 / ADR-0004):** while Alice synthesizes a long Text and George waits, cancel Alice and record time until George starts. Repeat cancellation/re-enqueue. No old computation should continue for minutes, no cancellation error should appear, and completed Paragraphs must remain usable. Use disposable data; development-PC/fake timings do not establish native cancellation latency on Celeron/i5.
