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

## experiment-2 visual direction (#28)

Use the `experiment-2` candidate after the developer has reviewed its visual direction;
do not substitute another branch's build. Browser verification is recorded in
`docs/design-reviews/issue-28/README.md`.

- [ ] **Projector/classroom, #28:** check UI labels, blue Library selection, and yellow current Paragraph with its blue edge from the back rows at the chosen Text size.
- [ ] **School laptops, #28:** check preparation and Playback mode responsiveness with 20 Texts and a long Text on the Celeron and i5.
- [ ] **Presenter remote, #28:** check pause/resume, previous/next Paragraph and repeat in Playback mode, including after using the native controls and disclosures.

## experiment-2 preparation workspace (#29)

- [ ] **School laptops, #29:** check narrow Library opening/scrolling/closing and switching back to the editor with 20 Texts on the Celeron and i5. Verify that controls stay responsive and typed input remains intact.

## experiment-2 Library (#30)

- [ ] **School laptops, #30:** with 20 Texts and several ready Narrations, check Library search and row menus on the Celeron and i5: opening a Text, keyboard navigation, and removing a disposable Narration stay responsive. Use a test Library for deletion.

## experiment-2 Voice choice and Narration queue (#31)

- [ ] **School laptops, #31:** check Voice chooser opening, independent Voice samples and selection, and queue progress/cancellation on the Celeron and i5 with a disposable Library. Check responsiveness while the real offline Voice provider loads and synthesizes; silent browser fixtures do not verify real Voice samples or device performance.
- [ ] **School laptops, #31 immediate cancellation (ADR-0004):** while real Alice is synthesizing a long Text and George is queued, cancel Alice and record the time until George starts. Repeat cancellation and re-enqueue; verify no old computation continues for minutes, no cancellation error appears, and previously completed Paragraphs remain usable. Use disposable data; browser/fake timings do not establish native cancellation latency on the Celeron/i5.
