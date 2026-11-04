# Stage 9 — reload and page-hide safety (#36)

Date: 2026-11-04. Branch: `experiment-2`. Starting tree was clean at `510566e`.
Stages 1–8 are accepted. The current open #36 was read in the built-in browser:
`gh issue view` returned 401 and unauthenticated REST was rate-limited.
No Issue was modified. Keep #36 open for developer acceptance.

Implementation commit: the commit introducing this handoff; resolve its SHA with
`git log -1 -- docs/design-reviews/issue-36/README.md`. No push or CI inspection
is part of this delivery.

## Implementation and contract

Product changes are confined to `ozvuchka/web/app.js`. The existing `save_text`
command, editing context, positive increasing sequence and `saved`/`failed`/`stale`
results remain unchanged. Core owns the current Text, ordering, failed content,
disk-write status and lifecycle deadlines. No Core, HTTP, Library format, audio
scheduling, synthesis, Voice provider or launcher change was necessary. There is
no localStorage, extra persistence store, unload prompt or stage 10 work.

On `visibilitychange` to hidden, `pagehide`, and `freeze`, send the latest dirty
editor value through `fetch(..., keepalive: true)`. This bypasses the ordinary
serial request queue and debounce, including when an older save is pending.
The request uses the same context/sequence as ordinary autosave. Pending lifecycle
submissions for the same context/sequence are coalesced; a newer edit can be sent
independently. Lifecycle dispatch never means `Сохранено`: only a matching confirmed
write does. A late old success cannot mark newer input saved or clear its error;
an old failure cannot undo a newer confirmed write. Visible failure retains retry.

If the reloaded page's initial snapshot predates the departing page's delivery,
polling adopts a higher Core revision while the new editor is still clean. It does
not replace locally edited content, caret or selection with routine snapshots.
The existing explicit conflict error remains applicable to rejected saves.

Heartbeat dispatch remains independent of ordinary commands. `page_closing` still
starts the ten-second reload window, `page_alive` retains its five-second cadence
and two-minute timeout, `page_frozen` suspends expiry, and `resume` sends alive.
No save completion is awaited before sending these lifecycle events.

This directory also holds screenshots and an optional standard-library
[delay proxy](network_proxy.py) for repeatable acceptance. It forwards the real
page, HTTP commands, snapshots and audio; it does not replace the app or provide
a new browser-test framework.

## Guarantees and limits

- Once Core accepts a newer sequence, an older request in that context cannot
  overwrite it, even if requests arrive in reverse order. Failed writes also
  reserve their sequence. This is a Core guarantee, independent of response order.
- `saved` follows the existing atomic write: temporary file, flush/fsync, then
  replacement. Confirmed content survives F5, reopening and normal process restart.
  Dispatch, HTTP 200 alone, and a queued keepalive are not confirmations.
- Ordinary immediate reload/navigation was observed to deliver the last input in
  this browser, including with a pending old request/response. Lifecycle delivery
  itself is best effort, not a universal durability guarantee. Browsers may omit
  events, reject requests or terminate the page before delivery. Keepalive bodies
  share a roughly 64 KiB outstanding quota, including other keepalives/beacons;
  a large Text or exhausted quota can fail. Use confirmed ordinary autosave for
  large Texts. No synchronous unload request or browser-close blocking is added.
- A write failure preserves the accepted Text and error in the running Core.
  Reloading/reopening that same process exposes it and retry. Disk retains the
  previous successful version. If the process exits before retry succeeds, those
  memory-only edits are lost. If the request never reached Core, it cannot recover
  that input at all. A departed page cannot display a later transport failure.
- Closing longer than the existing ten-second grace period can end the real
  application. A fresh process loads only the successful Library writes. The
  isolated preview does not run the launcher's automatic page-gone shutdown loop.
- A killed browser/process, power loss, removed drive or OS/storage failure is not
  covered by an unsent-edit guarantee. Atomic replacement limits partial-file
  exposure; no new guarantee about hardware durability or recovery of corruption
  is made. There is no recovery journal or merge across editing windows.
- One current editing workspace is assumed. If a newly reloaded page is edited
  before a delayed departing request reaches Core, conflicting sequences may be
  rejected rather than merged. Local input is retained with the error; copy it
  before another reload. Clean-page reconciliation is not concurrent-editor merge.

## Verification record

Windows, ChatGPT built-in Chromium browser; actual Python Core/HTTP/page with a
fresh `tools/ui_design_preview.py --real-voice` process. Disposable Library:
`.cache/ui-design-preview/issue-28-6om46pud`. User `data/` was not changed.
Port 8791 already served another instance, so it was only read; all edit/failure
checks used the new preview on 18736 through a local proxy on 18737.
The initial duplicate-port preview was stopped without editing its data.

Setup from the repository root, in separate terminals:

```powershell
New-Item -ItemType Directory -Force .cache/tmp | Out-Null
$env:TEMP = (Resolve-Path .cache/tmp).Path
$env:TMP = $env:TEMP
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --no-ready --port 18736 --real-voice
```

```powershell
runtime/python.exe -X utf8 docs/design-reviews/issue-36/network_proxy.py
```

During the recorded run, a temporary `.cache/issue36_proxy.py` with the same
request/response delay mechanism was used. The maintained review copy above makes
that setup reproducible. All application files were forwarded fresh after edits.

Observed through page controls, immediate `tab.reload()` (F5 lifecycle) and actual
navigation away/back; Core snapshots and the disposable `library.json` were read
separately to distinguish acceptance from disk persistence:

| Scenario | Observed result |
| --- | --- |
| Type then immediate reload, before 600 ms debounce | Exact input restored, matching `saved` Core state and disk content. |
| Hold sequence 2 **before** forwarding for 12 s; type sequence 3 then reload | Sequence 3 reached Core/disk first; delayed sequence 2 returned `stale`. Latest Text remained. |
| Hold sequence 4 **response** for 12 s; type sequence 5 then navigate to blank and reopen | Exact sequence 5 Text restored and saved; old acknowledgement did not replace it. |
| Immediate navigation away/reopen, no older save | Latest Text reached Core/disk and was restored. |
| New draft, immediate F5; existing Text cleared to empty, immediate F5 | Exact draft/empty value restored with `saved`; the draft received its Library identity. |
| Close tab after confirmed autosave, reopen | Exact confirmed content restored. |
| Tool-driven immediate tab destruction before debounce | Last input was not delivered (no corresponding proxy save); reopening showed the preceding confirmed version. This is an observed lifecycle limitation, not a successful graceful-close check. |
| Hold departing sequence 10 request for 4 s; reload before it reaches Core | First page showed the preceding version; polling then adopted the exact later Text with `Сохранено`, without another reload. |
| Obstruct disposable `library.json.tmp`, type then immediate reload | Latest input survived in Core, failure/retry persisted across polls; disk retained the preceding Text. Removing only the empty obstruction and retrying confirmed the write. |
| Hold successful sequence 11 response for 12 s, obstruct writes, type sequence 12 then reload | New failed Text/error/retry restored; disk retained sequence 11. An old success did not turn the failed revision into `Сохранено`. |
| Type short Text then immediately Play | Real Alice Kokoro synthesized the exact latest Paragraph; browser playback reached natural completion, `Текст прочитан`, Core `ended_at=0`, empty queue. |

Evidence: [restored later revision](reload-saved.jpg),
[write failure after reload](reload-write-failed.jpg),
[real playback completion](real-playback.jpg),
[confirmed close/reopen](confirmed-reopen.jpg). Successful final page screenshot
is 1280 × 720; the initial failure screenshot uses the browser's default narrow
viewport. The stage 10 visual/zoom/platform matrix was not repeated. Built-in
browser tabs reported `visible` even when the browser panel was hidden, so a
standalone background-tab/freeze transition is not claimed as physically tested;
navigation/page-hide paths were exercised. Timed heartbeat/close/reopen behavior
is also covered by the existing public Core tests.

Required checks (after the final implementation):

```powershell
runtime/python.exe -m pytest --basetemp=.cache/pytest-issue36-final
runtime/python.exe -m mypy
runtime/python.exe -m ruff check
git diff --check
```

Results: 133 passed, 8 slow deselected; mypy: 23 source files, no issues; ruff and
diff check passed. Slow tests are not required: provider/build behavior is unchanged.
No new hardware-only criterion was introduced; the existing items in
`docs/manual-checks.md` remain applicable. Test servers were stopped after review.

## Developer acceptance

Developer scope correction, 2026-11-04: ordinary autosave is sufficient for this
application. Texts are normally copied from another source; rare loss of the latest
unconfirmed edits in edge cases is acceptable. Do not pursue editor-grade recovery
or require the developer to repeat fault injection and delayed-request scenarios.
The detailed record above remains evidence of checks already performed by the agent,
not a required developer acceptance matrix. No further product changes follow from
this correction.

For a fresh disposable preview, use the preview command above and open
`http://127.0.0.1:18736` directly. No proxy or extra network setup is needed.

1. Paste a short Text, change a few words, pause and check that `Сохранено` appears.
2. Press F5 and check that the Text remains. Optionally try F5 immediately after
   typing a few more characters; this is a quick smoke check, not a durability audit.
3. Press Play and check that the edited Text is read. Return to editing and check
   that it remains available.

The developer reports that autosave generally works. No additional exhaustive
manual verification is requested. Stop a disposable preview with Ctrl+C when done.

Do not close #36 before acceptance and do not begin stage 10 / #37 here.
