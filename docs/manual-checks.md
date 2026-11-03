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

- [ ] #26 — On Windows 10 Home 22H2 x64, AMD Athlon II X2 250, 8 GB RAM, unpack the experimental `codex/v0.2-numpy-legacy` build into a fresh folder (not the build from `main`). Follow README's "Experimental v0.2 build for older CPUs": confirm NumPy 2.3.5 imports with exit code 0, start the launcher, synthesize and play a new Narration, close and reopen the program, and check `data\ozvuchka.log`. Record the build version, outcome and any errors in #26.
