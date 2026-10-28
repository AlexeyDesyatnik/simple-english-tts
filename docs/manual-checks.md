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

- [x] **#10** On the Celeron from a flash drive: a ready Narration plays before the model has loaded. — 2026-10-28, Celeron: yes.
- [ ] **#10** On the Celeron from a flash drive: the page opens at once, and a new Narration shows «Голоса загружаются…» until Kokoro has loaded. — 2026-10-28, Celeron: the window came about a minute after the start, then «Голоса загружаются…» for a couple of minutes (Kokoro loaded in 156 s cold, 15 s the second time). The log starts only about 45 s after the launch, so the time before it is not seen yet.
- [x] **#10** Starting Озвучка.exe again while it runs opens its page once more, with no error box and still one pythonw.exe in Task Manager; closing every page then ends the program. — 2026-10-28, Celeron: yes, in a tab of Yandex Browser (the default one), as the build then had no Edge window. Starting it right after closing the window gave a page with no server: #13.
- [ ] **#10** With another default browser (Yandex Browser on the Celeron), the program opens an Edge app window, with no address bar, both on the first start and on a second one.
