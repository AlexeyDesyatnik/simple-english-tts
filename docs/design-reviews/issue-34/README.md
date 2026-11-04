# Stage 7 — save acknowledgement and ordering (#34)

Date: 2026-11-04. Independent branch: `experiment-2`. Starting tree: clean,
`11433bc`. The final acceptance section of the #33 handoff supersedes its earlier
pending statements: stages 1–6 are accepted. #33 and all other Issues were untouched.
The live #34 body was read through the public GitHub REST API because `gh` returned
401. No push or CI inspection was performed.

Implementation commit: the commit introducing this handoff and the Core/HTTP changes
(exact SHA in the delivery message; `git log -1 -- docs/design-reviews/issue-34/README.md`).

## Scope and changed files

`ozvuchka/core.py` owns the new save contract and editing-context lifetime.
`ozvuchka/server.py` adds one thin command mapping. `tests/test_core.py` and the
existing `tests/test_server.py` exercise the public commands and snapshots with
FakeVoiceProvider, FakeClock and temporary data. This directory holds the handoff
and browser evidence.

No web files, Library schema, storage implementation, synthesis, audio scheduling,
Voice provider, heartbeat or other branch implementation was changed. The existing
page still saves through legacy `set_text` at its existing action boundaries.
Autosave, visible save-state/retry controls, transition guards and immediate reload/
page-hide flushing belong to stages 8–9. No new hardware-only criterion is introduced;
the outstanding checks in `docs/manual-checks.md` remain unchanged.

## Public contract

The snapshot has an additive top-level `save` object, available even before a Text
exists:

```json
{"context":"opaque-token","sequence":0,"text_id":null,"status":"idle","error":null}
```

Call `Core.save_text(text, context=token, sequence=n)`, or send this JSON to
`POST /api/command`:

```json
{"command":"save_text","text":"Hello, class.","context":"opaque-token","sequence":1}
```

The HTTP response wraps the Core result as usual:

```json
{"result":{"context":"opaque-token","sequence":1,"text_id":"assigned-text-id","status":"saved","error":null}}
```

- `context` identifies one current Text editing interval, including its initially
  unsaved draft. It is not the Library Text ID. Obtain it from the snapshot; do not
  invent it or substitute an old Text ID. Its association survives the first save
  assigning a Library ID. No token is persisted to disk.
- `sequence` is a positive JSON integer (booleans/fractions/strings are rejected).
  Allocate increasing numbers for edits within that context, above the snapshot's
  latest accepted sequence after reconnecting. Gaps are allowed. Ordering compares
  the pair `(context, sequence)`, never unrelated Texts or wall-clock timestamps.
- `saved` acknowledges that **this requested content** completed the existing
  atomic Library write: temporary-file write, flush, file fsync, then replacement.
  The result identifies its context, sequence and Library Text ID. HTTP 200 alone
  is not confirmation. A repeated identical request attempts the write again,
  including when its content is already in memory; equality is not proof of saving.
- `failed` means the edit was accepted in memory but persistence was not confirmed.
  It reserves its sequence and Text ID, retains its content and a Russian error in
  `snapshot.save`, and remains observable through polling. Fix the filesystem cause
  and retry the exact same context/sequence/content, or submit a newer edit with a
  higher sequence. An unreadable Library remains protected against overwrite and
  always returns failure; repairing it requires restarting Core, as before.
- `stale` rejects an expired context, a lower sequence, or the reuse of the latest
  sequence with different content. Its result echoes the **rejected request's**
  context/sequence, has `text_id: null`, and includes a Russian explanation. It
  changes no Text, save snapshot or Library ordering and does not erase a failure.
  Refresh the snapshot and reconcile edits; do not blindly resend with a new token.
- Empty/whitespace content is saved verbatim by the new command, preserving an
  existing Text's identity and explicit title. A first empty save also creates a
  Library Text; its generated title is empty under the existing title rules. The
  later UI integration must account for this when presenting an empty draft.

Core processes validation, edit acceptance, disk write and result construction
under the same lock as Text transitions. A save that acquires the lock before a
switch belongs to that previous Text; one arriving after the switch is rejected.
`new_text` (even on an empty workspace), opening a different Text, deleting the
selected Text, and a content-changing legacy `set_text` expire the context. Returning
to an earlier Text gets a fresh token, so a late old request cannot follow it back.
Opening the same current Text or unchanged legacy `set_text` does not expire it.
Rename, search and Voice/Speed changes do not start another editing interval.

All pre-existing command signatures and results remain compatible, including
`set_text(...) -> None` / HTTP `result: null`. They do not acquire ordering guarantees
for requests without a token. Changed legacy writes invalidate guarded requests,
but a late unguarded writer can still apply to the current Text. Stages 8–9 must
move **all editor save paths**, including lifecycle requests, to the guarded command.

The snapshot describes the latest accepted guarded attempt in the current interval.
`idle` makes no persistence claim; it also follows legacy edits and Text transitions.
Other Library writes may persist an earlier failed edit, but do not promote its
save status: retry explicitly to obtain a fresh acknowledgement. This conservative
state is separate from the existing general `library_error` field.

## Client duties and limits for stages 8–9

Match each response against the current context **and the latest local edit
sequence**, not just the latest sent request. A response for an earlier edit cannot
mark newer unsent input saved. After reload, the snapshot provides the latest Core
attempt and sequence; it cannot know input that was never sent. Tokens expire on
process restart. This contract assumes one current editing workspace; it is not a
multi-client merge protocol.

This stage does not stop a user transition after failure. Switching explicitly
ends the interval; pending UI edits must be flushed and transitions gated by later
stages. `saved` is not a guarantee against OS/device power loss after replacement,
external file modification, a later write, or loss of unsent input on process death.
No directory-fsync or filesystem durability guarantee beyond existing ADR-0001
storage is added.

## Tests and results

Tests preceded implementation: the initial nine selected cases failed because
`save`/`save_text` did not exist; all nine passed after implementation. Additional
cases cover unreadable storage, invalid sequences and fresh sequences after return.
Filesystem failures use a directory at the temporary Library-file path, not storage
method mocks. Persistence is checked by opening the Text through a fresh Core.

Coverage includes confirmed/retried writes, polling after failure, previous disk
content on failure, older edits after a newer accepted (including failed) edit,
duplicate sequence conflicts, blank content, new/open/delete/legacy invalidation,
same sequence on a different Text, and late saves before/after return. HTTP verifies
the same success/failure/stale results through the existing adapter.

Required checks:

```powershell
runtime/python.exe -m pytest --basetemp=.cache/pytest-issue34-final
runtime/python.exe -m mypy
runtime/python.exe -m ruff check
git diff --check
```

Results: **133 passed, 8 slow deselected**; mypy passed (23 source files); ruff and
diff whitespace checks passed. Slow/provider/build checks do not apply to these
changes. No CI run was inspected and no Issue was modified or closed.

## Actual browser verification

Windows, ChatGPT in-app browser, real page/Core/HTTP with a fresh isolated process:

```powershell
runtime/python.exe -X utf8 tools/ui_design_preview.py --texts 1 --no-ready --port 8790
```

The preview printed its disposable Library path under `.cache/ui-design-preview/`.
The user Library was untouched. No playback, sample or synthesis check was performed;
the silent fake was sufficient for this save-only check. For any later playback
acceptance use a fresh preview with `--real-voice` instead.

Using visible controls: opened the page, created New Text, selected another Library
Text and returned. Sent the new contract through PowerShell HTTP requests against
this same preview: obstructed its `library.json.tmp` with an empty directory, sent
sequence 2, observed `failed` and the existing Russian Library error on the page.
Removed only that empty obstruction and retried sequence 2: `saved`. Sequence 1
returned `stale`; reload retained `Stage seven confirmed text.` and the error cleared.
Selected the other Text visibly, sent old-context sequence 100: `stale`; the selected
Text remained intact. Returned visibly to the saved Text and confirmed its content.
These are sequential request-order checks, not a network stress or power-loss test.

Evidence: [observable failure](save-failed.jpg),
[confirmed content after switching](confirmed-after-switch.jpg). No layout changes
were made; the previous stages' full responsive/zoom matrix was not repeated.

## Developer acceptance

1. Start the isolated preview above and use its printed disposable directory only.
   Keep playback stopped. Verify New Text and Library selection still work and that
   no autosave badge or new transition dialog has appeared.
2. In another PowerShell window, get the context and submit an edit:

   ```powershell
   $state34 = Invoke-RestMethod http://127.0.0.1:8790/api/state
   $body34 = @{command='save_text'; text='Hello, class.';
       context=$state34.save.context; sequence=($state34.save.sequence + 1)}
   Invoke-RestMethod http://127.0.0.1:8790/api/command -Method Post `
       -ContentType application/json -Body ($body34 | ConvertTo-Json)
   ```

   Require `result.status = saved` with matching context/sequence and a Text ID.
   Reload the page, switch away and back: the saved content must remain.
3. Repeat with a fresh context after switching. Before sending, create an empty
   `library.json.tmp` directory inside **the printed preview Library only**. Require
   `failed`; poll `/api/state` twice and inspect `save.error`. Remove that empty
   directory and resend exactly the same body: require `saved`.
4. Send a smaller sequence with different content, then reuse the accepted sequence
   with different content: both must return `stale`. Select another Text, then resend
   the old context with a much larger sequence: still `stale`, with neither Text
   replaced. Returning to the original Text must not revive its old context.
5. Run the public-seam tests above for restart persistence, unreadable Library,
   empty content and compatibility. Review the client duties before starting #35;
   unsent typing and immediate F5 protection are deliberately not acceptance for #34.

Stage 7 awaits developer acceptance. Ask separately before push or CI inspection;
do not close #33 in this session. No work on stages 8–9 was started.
