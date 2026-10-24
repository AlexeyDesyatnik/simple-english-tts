# Manual checks on the school computers

Everything the developer has to check by hand on the school laptops, the projector or in class: what no test, CI run or browser check can show. One list for all the work, whichever chat it was done in.

- **Adding**: work that leaves such a check adds it here in the same commit, under where it is done, with its issue.
- **Checking**: tick the box and write the date and what you saw after it (`— 2026-11-03, Celeron: estimate 1:20, real 1:31`). Numbers an issue asks for go in a comment on that issue as well, and the issue's own checkbox is ticked there.
- **Removing**: an item is deleted once it is ticked and its issue is closed; an unticked one stays even if the issue was closed without it. Git keeps the history.

## Getting the program onto a laptop

Take the zip from the latest green build of `main` in GitHub Actions (the run's artifacts) or from GitHub Releases, unblock it before unpacking and copy it to the flash drive: see README, "Unblocking the zip" and "Copying to a flash drive". The program writes only into its `data\` folder; its log is `data\ozvuchka.log`, worth bringing back when something goes wrong.

The laptops: **Celeron** (N4100, no AVX, 3.8 GB, synthesizes slower than speech, about ×0.44) and **i5** (about ×1.85).

## From a flash drive, on both laptops

- [ ] **#11** Celeron: a double-click on `Озвучка.exe` opens the window with no console; a phrase plays in the Alice voice; no DLL errors.
- [ ] **#11** i5: the same.
- [ ] **#11** Measured for both laptops and written in a comment on #11: time until the window appears, time until the model is ready, peak memory (Task Manager), the folder's size.
- [ ] **#11** About 10 s after the window is closed, nothing of the program is left in Task Manager (no `pythonw.exe`, no extra `msedge.exe`). If it takes about two minutes instead, Edge did not tell the program that the window was closing: write that down.
- [ ] **#11** The program folder put inside a folder with a Russian name on the flash drive (e.g. `E:\Уроки\Озвучка`): it starts and speaks all the same (eSpeak NG used to fail on such paths).
- [ ] **#11** F5 in the window: the page comes back and the program keeps running.
- [ ] **#11** The window minimized for half an hour, then restored: the program is still running and plays.
- [ ] **#11** After a lesson with the program, nothing of it is left on the laptop outside the program folder: no log, no Library (phonemizer's temporary copy of `espeak-ng.dll` in `%TEMP%` is expected while it runs and may stay behind).

## On the Celeron

- [ ] **#5** A Text of about 150 words that is not ready: the Start delay shown after Play is within about ±20% of the real wait, and once playback starts it never stops to wait for synthesis.
- [ ] **#6** A ready Narration plays without stuttering while another one is synthesized in the Narration queue.

## In class, with the projector

- [ ] **#9** The Text can be read from the back of the room. Write down the smallest Text size (A− / A+) that is enough.
- [ ] **#9** If the school has a presenter remote: its buttons move to the next and previous Paragraph. If a button does nothing, note which one; it may send a key the program does not listen to yet.

## Waiting for the work

Checks the issues ask for, to be done once the work is in a release:

- **#10** On the Celeron from a flash drive: a ready Narration plays before the model has loaded.
