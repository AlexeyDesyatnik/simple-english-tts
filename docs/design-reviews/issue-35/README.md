# Stage 8 — visible autosave and safe Text transitions (#35)

Date: 2026-11-04. Independent branch: `experiment-2`. Starting tree: clean,
HEAD `87edb98` (accepted stage 7, still local). Stages 1–7 are accepted and #34
is closed according to the developer's handoff. The current open #35 was read
through GitHub REST because `gh issue view` returned HTTP 401. No Issue was
modified or closed; no push or CI inspection was performed.

Implementation commit: the commit introducing this handoff; resolve its exact SHA
with `git log -1 -- docs/design-reviews/issue-35/README.md` (also in the delivery).
Stage 8 awaits developer acceptance; keep #35 open.

## Scope and implementation

Changed `ozvuchka/web/app.js`, `index.html`, and `style.css`. This directory contains
the handoff and real-page screenshots. No Core/HTTP contract, storage schema,
Voice provider, synthesis, audio scheduling, heartbeat or other branch changed.
No new hardware-only acceptance criterion was introduced; the existing
`docs/manual-checks.md` items remain applicable and unchanged.

The editor now submits `save_text` with the snapshot's editing context and an
increasing local edit sequence. Every input event advances the sequence, including
input that has not yet been sent. A 600 ms pause coalesces ordinary typing; unfinished
IME composition is not autosaved. There is at most one save request awaiting an
acknowledgement; callers waiting for it recheck whether another save has started.
Newer typing during a request is flushed afterwards. No idle/unchanged draft write
is made merely by opening the page or pressing New Text.

The permanent editor feedback distinguishes `Изменения не сохранены`,
`Сохранение…`, `Сохранено`, and a persistent save error with
`Повторить сохранение`. Success requires a `saved` result with matching context
and sequence, not an HTTP success or snapshot/content equality. An older success
only confirms its older sequence: it cannot mark newer input saved. Failure keeps
its error through polling and further typing until a later acknowledged save
resolves it. Retry resends the same sequence/content if unchanged, or the latest
higher sequence after further input. Transport failures and stale/rejected results
also leave an error and block the attempted transition. A stale context is never
silently replaced with a newly invented context for retry.

Open Text, New Text, Play and enqueue share a guarded transition: make the editor
read-only, flush the latest visible revision, and only then send the action and
refresh. Further transition clicks are ignored until completion. On save failure,
the action is not dispatched and the editor becomes editable again. Another
attempt at the action retries the save first; the dedicated retry button saves
without resuming the failed action. This avoids a delayed retry unexpectedly
switching Texts or starting playback.

Snapshots replace the textarea only when the editing context changes, never when
the first save assigns a Library Text ID or when polling reports older content.
Within a context the textarea value, caret, selection and scroll position remain
browser-owned. A reopened existing Text whose fresh context is `idle` shows the
neutral autosave hint, making no new disk-write acknowledgement claim. Empty
content is saved through the same contract; untitled whitespace Texts have a
readable `Текст без названия` label. Confirmed deletion remains an explicit discard
operation; deleting another Text does not cancel the current editor's debounce.

## Required checks

```powershell
runtime/python.exe -m pytest --basetemp=.cache/pytest-issue35-final
runtime/python.exe -m mypy
runtime/python.exe -m ruff check
git diff --check
```

Results: **133 passed, 8 slow deselected**; mypy passed for 23 source files; ruff
and whitespace checks passed. There are no automated page tests, as required by
`CODING_STANDARDS.md`; the existing public Core/HTTP tests cover the stage 7
contract. Slow/provider/build checks do not apply because those areas are unchanged.

## Real-page browser verification

Used the ChatGPT in-app browser against a fresh isolated real Core/HTTP/page:

```powershell
New-Item -ItemType Directory -Force .cache/issue35-temp | Out-Null
$env:TMP = (Resolve-Path .cache/issue35-temp).Path
$env:TEMP = $env:TMP
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --no-ready --port 8791 --real-voice
```

Disposable Library for the successful run:
`.cache/ui-design-preview/issue-28-e6amkoxd`. User `data/` was untouched.
The initial process could not copy the temporary eSpeak DLL in the sandbox's
system temporary directory; it was stopped and a fresh process using the writable
workspace temporary directory loaded real Kokoro successfully. No provider fix or
silent fake substitution was made.

For response-delay checks, a temporary, uncommitted Python standard-library proxy
on port 8792 forwarded to that same server. Only responses to `save_text` were
held, after the real server had handled the request. A file in `.cache/` selected
the delay; all other requests and assets passed through. The final delay scenario
used 12 seconds per save response. This was development instrumentation, not a
product endpoint or a new test framework.

Observed with visible controls and read-only DOM measurements:

- Ordinary typing: unsaved feedback immediately, then confirmed saved feedback;
  reopening and F5 after confirmation retained the exact content.
- Delayed first save of a new draft: entered `First saved draft with a delayed
  acknowledgement.`, waited for saving feedback, then entered `New input must
  survive the first Library identity.` while the old response was pending.
  The old acknowledgement did not replace the new input or show it as saved.
  During its own pending save, the newer revision showed saving. Proxy logging
  showed exactly sequences 1 and 2 in this final scenario, with no duplicate save.
- Selected the first character (`selectionStart=0`, `selectionEnd=1`) during that
  delay. Both offsets and the exact newer value remained unchanged after the old
  response, after the new acknowledgement, and after subsequent snapshot polling.
- Created an empty directory at the **disposable** `library.json.tmp` path to
  force real atomic-write failure. The error and retry button survived polling.
  Tried a different Text, New Text, Play and enqueue separately: all retained
  `Latest failed edit remains on screen.`, kept the selected Text, stayed in
  preparation, and did not add a Narration to the queue.
- Removed only that empty obstruction, clicked retry, and observed `Сохранено`
  with no remaining error. Then switched to another Text successfully.
- Entered `Immediate switch must save this edit.` and clicked another Text before
  the debounce. Returning showed that exact content. Entered
  `Saved before creating another Text.` and immediately created a Text; reopening
  the previous Text retained those latest edits.
- Entered `Hello, class. This is the latest playback text.` and immediately pressed
  Play. Playback mode displayed that exact Paragraph; real Kokoro synthesis and
  browser playback reached natural completion (`Текст прочитан`, `ended_at=0`).
  Returned to editing, entered `Preparation uses the very latest edit.` and
  immediately enqueued: the queue prepared that revision and exposed a ready
  Alice Narration. This checks real playback flow, not subjective audible quality.
- Saved whitespace in a new Text: a readable untitled Library row appeared and
  no empty accessible row title was left behind.
- At 1280 × 720, the editor and Play were visible (editor bottom about 578 CSS px,
  Play bottom about 638). At 760 × 720, the save feedback and actions remained
  readable, with no horizontal page overflow. Library disclosure remained open
  until explicitly closed. Temporary viewport override was reset afterwards.

An initial browser pass exposed duplicate waiter submissions during overlapping
save calls. The wait was changed to recheck the in-flight promise in a loop;
the final delayed-draft scenario above was repeated after reloading the final
JavaScript and showed one request per revision.

Evidence: [confirmed desktop autosave](autosave-desktop.png),
[narrow autosave](autosave-narrow.png), [save failure and retry](save-failed.png),
[newer input during delayed acknowledgement](delayed-newer-input.png),
[latest Text after real playback](playback-latest.png).

The full stage 10 visual/zoom/hardware matrix was not repeated. Preview/proxy
processes were stopped after verification; their temporary Library is disposable.

## Developer acceptance

1. Start the isolated preview above and open its printed localhost address.
   Use only its printed disposable Library for the following checks. Never create
   a failure obstruction in the user's `data/` directory.
2. Type several characters without pausing, then pause. Expect unsaved/saving/saved
   feedback and no jump in cursor or selection. Select part of the Text, wait for
   several polls, then continue typing: the selection and insertion point must
   behave normally. After `Сохранено`, F5 and switching away/back retain the Text.
3. Immediately after an edit, try each of: another Text, New Text, Play, enqueue.
   The outgoing Text is saved first; Play/queue must use the last visible revision.
   A fresh untouched draft should not create an extra empty Library entry merely
   because you click New Text. Editing a Text to blank does save that blank value.
4. While idle, create an empty `library.json.tmp` directory inside the printed
   disposable Library. Edit the Text and wait. Verify the persistent error and
   retry button. Try all four actions separately: none may discard the edit or
   start its action. Remove only the empty obstruction and click retry: require
   `Сохранено`. The previously blocked action should need another explicit click.
5. For a delayed-response check, use browser development network throttling or a
   local response-delay proxy forwarding to the isolated preview. Hold a save
   response for several seconds, type a newer revision, and select part of it.
   The old response must not erase the revision or label it saved; only its own
   matching confirmation may show `Сохранено`. Repeat on a fresh draft so the
   first assigned Library ID is also exercised. Inspect cursor/selection after
   polling resumes. Restore ordinary network settings after the test.
6. Check normal feedback at laptop width and with a narrow window. Long save errors
   may expand the layout but must remain readable and keep retry accessible.
   Review the screenshots and scope limits before accepting #35.

## Limits and next stage

Immediate reload, page-hide, older in-flight lifecycle races, and protection of
unsent input during those events remain **stage 9 / #36**. No unload prompt,
lifecycle save, beacon save or localStorage was added. The existing heartbeat is
unchanged. F5 above was tested only after confirmed saving. Unsent edits cannot
be guaranteed after process termination or a crash. One current editing workspace
is assumed; concurrent-window merge/conflict recovery is not implemented.

Do not push or inspect CI in this stage. Do not close #35 until developer acceptance.

## Developer verification update — 2026-11-04

The developer confirmed that all four checks in the chat's short acceptance list
work: ordinary autosave with stable cursor/selection; saving before opening or
creating a Text and retaining edits on return; Play/enqueue using the latest
visible edits; and F5 retaining content after confirmed saving.

This confirmation refers to the four-item chat list, not items 1–4 of the longer
acceptance procedure above. Developer verification of write failure, blocked
transitions and retry has not yet been reported. Delayed-response and failure
scenarios have the agent browser evidence recorded above. Full stage 8 acceptance
has not yet been declared; #35 remains open. Push and CI remain deferred.

### Developer failure/retry check — 2026-11-04

The developer also confirmed that the write-failure scenario works: an empty
`library.json.tmp` directory in the current disposable preview Library produces
a save error, a Text switch retains the visible edits, and removing the obstruction
then retrying saves successfully. Together with the earlier four chat checks,
the developer has now confirmed the ordinary and failure/retry scenarios.
No Issue state, push or CI operation was performed as part of recording this result.
