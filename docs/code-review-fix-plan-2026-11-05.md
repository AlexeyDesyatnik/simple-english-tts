# Code review fix plan — 2026-11-05

Status: finding 1 / Issue #39 accepted by the developer, and finding 3 / Issue #40 implemented and verified through Core on 2026-11-05. Finding 2 / Issue #41 has HTTP implementation, automated verification, a passing release ZIP smoke test, developer everyday browser acceptance and passing in-app Chromium foreign-loopback-origin checks; The developer accepted these checks as sufficient and requested closure on 2026-11-05; additional Edge/public HTTPS/LNA checks are waived, not recorded as passed. Verification and acceptance are recorded below. Other findings remain planned. The developer requested that this plan be recorded in project documentation and GitHub Issues.

## Start here in a new session

1. Read AGENTS.md, CODING_STANDARDS.md, GLOSSARY.md, docs/agents/issue-tracker.md, docs/agents/domain.md, docs/development.md and docs/manual-checks.md, then the relevant ADRs.
2. Read this plan and [the original review](code-review-2026-11-05.md). The review's priorities are preliminary; this plan records the subsequent revalidation and chosen scope.
3. Findings 1 / #39, 3 / #40 and 2 / #41 are complete; the developer accepted the available #41 checks as sufficient on 2026-11-05 and requested closure. Next is finding 6 / #42. Read the Issue's latest comments before implementation. Work through one bounded fix at a time; do not resume retired UI design tracks.
4. Write behaviour tests through the existing public seams before changing behaviour. Keep Core independent of HTTP and the page. Record verification and remaining limitations in the Issue.
5. Before each implementation commit run `runtime\python.exe -m pytest`, `runtime\python.exe -m mypy`, and `runtime\python.exe -m ruff check`. Run relevant slow tests for provider/contract/cancellation-test changes; follow the coding standards for provider/build changes. HTTP protection also needs launcher/reopen and release ZIP smoke verification.

Recommended order: **1 → 3 → 2 → 6 → 4 → 5**. Findings 1 and 3 share unreadable-Library acceptance; implement 1 first. Finding 6 should precede the slow verification for 4. Other fixes are independent. The order does not imply a dependency on hardware acceptance.

| Order | Finding | Implementation Issue | Dependency |
| --- | --- | --- | --- |
| 1 | 1 — Preserve audio on persistence failure | [#39](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/39) | Accepted 2026-11-05 |
| 2 | 3 — Validate Library records | [#40](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/40) | Verified 2026-11-05 |
| 3 | 2 — Reject foreign-origin commands | [#41](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/41) | Accepted 2026-11-05; additional browser matrix waived |
| 4 | 6 — Bound cancellation test | [#42](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/42) | Before #43 slow verification |
| 5 | 4 — Explicit WAV contract | [#43](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/43) | Prefer #42 first |
| 6 | 5 — Consistent queue titles | [#44](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/44) | Independent |

Suggested next-session instruction: “Continue with Issue #42 following docs/code-review-fix-plan-2026-11-05.md. Issue #41 was accepted with the completed HTTP, release and browser checks; do not resume its optional browser matrix.”

## Evidence and limits

Revalidation used the current local code and disposable temporary Libraries outside the repository, with FakeVoiceProvider and direct Core/HTTP calls. User data was not used.

| Finding | Revalidated evidence | Limit |
| --- | --- | --- |
| 1 | Failed Library save leaves the old Text on disk but deletes its WAV. An unreadable Library followed by creation/deletion of a temporary Text also deletes old WAV files. | No physical flash-drive failure was induced. |
| 2 | A raw HTTP POST carrying a foreign Origin and text/plain JSON returned 200 and changed the Text. | This does not establish that a real browser sends the request under its current local-network policies. |
| 3 | A Library containing content: 42 raises AttributeError from snapshot. | Other malformed fields need regression cases. |
| 4 | A fake provider returning Audio with format mp3 terminates the synthesis thread with AssertionError. | Current Kokoro returns WAV; this is an extension-contract defect. |
| 5 | Core returns the content-derived queue title instead of the custom Library title. Code inspection separately confirms unchanged queue IDs prevent DOM title/aria-label refresh. | No browser reproduction was performed in this planning session. |
| 6 | A finite executor experiment confirms result(timeout) does not bound context exit. | Native Kokoro hanging was not reproduced. |

The planning session did not rerun full pytest/mypy/ruff, the slow suite, real-browser attack checks or hardware acceptance. The original review's 140 passing tests, 8 deselected slow tests and successful static checks belong to that earlier review, not this revalidation.

All 37 existing Issues were checked for overlap. Only #24 was open. Relevant closed work: #4/#12/#34 (Library and persistence), #36 (page lifecycle), #31 (queue and cancellation), and #1 (future provider contract). These are context, not open duplicate fixes. #24 remains the hardware-validation task; do not reopen the retired design work or close #24 on the strength of these fixes.

## Finding 1 — Preserve audio when Library persistence fails

Priority: high. This can destroy already prepared Narrations.

Scope: `ozvuchka/core.py`, narrowly necessary storage changes, and tests through Core. Related Issues: #4, #12, #34. No prerequisite.

Prepare and save the prospective Library without the deleted Text before committing destructive in-memory changes and audio cleanup. On failure retain the Text for retry and expose the existing Library error. Do not delete audio based on incomplete references when the Library is unreadable. Audit both Text and Narration deletion, including shared pieces and a preceding failed edit whose in-memory references differ from disk. Prefer conservatively retained files over lost ready Narrations. Preserve the current ability to work temporarily without overwriting an unreadable Library.

Acceptance:

- [x] A failed deletion save preserves the persisted Text and its playable Narration after restart; the Text remains available for retry in the current session.
- [x] Retrying after the write obstruction is removed deletes the intended Text and only safely unreferenced pieces.
- [x] Creating/deleting temporary Texts or deleting a Narration after an unreadable Library does not destroy old audio or overwrite the original Library.
- [x] Shared pieces and audio referenced by the last persisted Library remain protected, including after a prior failed edit.
- [x] Existing deletion-during-synthesis behaviour remains covered.
- [x] Regression tests use Core commands/snapshot/audio and temporary data, not a new storage-unit-test layer.

Bounds: no journal, backup generations, automatic repair, background garbage collection or crash-proof editor. Ordinary autosave guarantees remain unchanged. No new hardware-only acceptance is needed.

Implementation record (2026-11-05, #39):

- Text deletion saves the prospective Library first. A write failure leaves the Text, editing context and Narration queue intact for retry and exposes the existing Library error.
- Core remembers the last successfully persisted Text records. Narration deletion protects references from persisted versions hidden by failed edits, while ordinary deletion still removes unshared pieces.
- An unreadable Library can still be used for temporary work, including Text deletion, without overwriting its original bytes. Audio deletion is suppressed because its complete references are unknown; conservatively retained files are intentional.
- Six new Core-seam regression cases cover failed deletion and retry, restart Playback without synthesis, shared pieces, unreadable-Library Text/Narration deletion and failed edits followed by Text/Narration deletion. Existing deletion-during-synthesis coverage passes.
- Agent verification: `pytest` **146 passed, 8 slow tests deselected**; `mypy` and `ruff check` passed; `git diff --check` passed. Tests used disposable temporary Libraries. The new failure scenarios were reproduced before the production fix. Provider/build code was unchanged; slow tests, release build and browser acceptance were not run for this Core-only fix.
- Developer acceptance passed on 2026-11-05: the developer confirmed that the supplied everyday-use check worked. The instructions used an isolated copy of the current `runtime`, `models` and `ozvuchka` folders under `dist/acceptance-39-<id>`, a fresh disposable Library and port 8771. The check covered saving two Texts, preparing both Narrations, F5 and Playback, deleting one Text, closing and reopening, and verifying the retained Text and ready Narration. This was a source-copy check, not a release ZIP/launcher smoke test. Write-failure simulation remains covered by agent tests. Existing hardware checks remain outstanding in `docs/manual-checks.md`.

## Finding 3 — Validate Library records before exposing state

Priority: medium. Malformed but valid JSON can prevent every state snapshot.

Scope: `ozvuchka/library.py` validation and Core-seam tests. Related Issues: #4, #34. Start after finding 1 so unreadable-Library handling has safe deletion semantics.

Validate the version and complete structure before returning records: texts is a list, entries are objects, id/content are strings, title is absent/null/string, and IDs are unambiguous (reject duplicate or empty IDs). Report malformed input through the existing unreadable-Library path. Do not silently coerce field values, partially load and overwrite the file, or introduce a schema migration. Preserve valid older records without title.

Acceptance:

- [x] Parameterized malformed structure/field cases produce a usable snapshot with a Library error instead of an exception.
- [x] Invalid Library bytes stay unchanged; temporary editing still follows existing unreadable-Library behaviour.
- [x] Existing valid version-1 records, including missing/null title, remain compatible.
- [x] Combined regression coverage with finding 1 verifies old audio is preserved.

Verification is automated through Core; no hardware-specific check is required.

Implementation record (2026-11-05, #40):

- The complete version-1 Library is validated before returning any records. The version must be integer 1 (not a boolean or float), `texts` must be a list, each record an object, and IDs nonempty unique strings. Content must be a string; title may be absent, null or a string. Values are not coerced and no partial Library is exposed.
- Malformed records use Core's existing unreadable-Library path. Temporary editing, synthesis and deletion remain usable without replacing the original bytes. The #39 protection also keeps old Narration audio when a valid saved record is followed by an invalid record.
- Tests were written first: 15 of the 38 selected cases failed before the fix. Added coverage consists of 31 malformed structures/field cases, three compatible optional-title cases (also preserving record order and empty content), and two combined audio-preservation cases extending #39.
- Agent verification: full `pytest` **182 passed, 8 slow tests deselected**; `mypy`, `ruff check` and `git diff --check` passed. All data was disposable. No provider, build, HTTP or page changes; slow tests, release ZIP and browser checks were not run. All #40 criteria are covered through Core; no additional developer fault-injection or hardware acceptance is required. Existing hardware checks in `docs/manual-checks.md` remain outstanding.

## Finding 2 — Reject foreign-origin local commands

Priority: high for preventive protection; browser exploitability remains conditional.

Scope: `ozvuchka/server.py`, request construction in `ozvuchka/web/app.js`, HTTP tests and compatibility checks of launcher/tools. Related Issue: #36 and ADR-0003. Independent of storage fixes.

Use a bounded HTTP-layer policy:

- Validate Host against explicit supported loopback authorities and the server's actual port, not an arbitrary supplied Host.
- Reject a foreign Origin and Origin: null. Compare against explicitly supported application origins, including the port.
- Require application/json for commands, accepting valid charset parameters.
- Preserve Origin-less Python launcher/tool requests subject to Host and Content-Type checks. `_page_opening` already sends application/json.
- Do not add permissive CORS. Keep HTTP checks outside Core.
- Update heartbeat fetches and page_closing/page_frozen sendBeacon bodies together: they currently send string JSON without application/json. A JSON Blob can supply the beacon content type. Keep existing keepalive autosave behaviour.

Acceptance:

- [x] HTTP tests cover allowed and rejected Origin/Host/Content-Type combinations, including null/missing Origin and non-default ports; rejected requests have no command side effects.
- [x] Ordinary commands, heartbeat, autosave, reload, close/reopen and second-launch page_opening work. Developer everyday acceptance passed on 2026-11-05; individual beacon dispatch and freeze were not separately observed.
- [ ] Browser evidence records actual Edge version, permissions/policies, source origin and whether a request reached the server or was blocked before it.
- [x] From a separate origin, exercise a no-cors text/plain JSON POST and an application/json request requiring preflight, using harmless marker Texts in isolated data. Inspect target state rather than treating a CORS console error as proof of no mutation. Passed in the in-app Chromium browser between loopback ports on 2026-11-05; installed Edge remains untested.
- [ ] Distinguish another-loopback-port checks from a controlled public HTTPS-origin check. Record untested cases honestly; do not claim that all internet pages can currently exploit Edge.
- [ ] After protection, foreign requests leave state unchanged even where the browser permits local-network access. Test both normal permission settings and an explicitly allowed setting in a disposable browser profile where practical.
- [x] Launcher/reopen and release ZIP smoke checks pass; no broad lifecycle redesign is introduced.

Bounds: no login, random-port redesign or token infrastructure without evidence it is needed. This protects against foreign web pages, not a hostile local process capable of forging headers.

Background: [Fetch Standard](https://fetch.spec.whatwg.org/) distinguishes simple request sending from CORS response access. [Microsoft's Edge LNA documentation](https://learn.microsoft.com/en-us/deployedge/ms-edge-local-network-access) describes local-network/localhost permission restrictions; actual installed-browser behaviour must be measured. Do not disable a user's normal browser protections to perform acceptance.

Implementation record (2026-11-05, #41; accepted for closure):

- HTTP validates one supported Host using the bound port, permits absent Origin for local tools or one explicit supported application Origin, and requires one JSON Content-Type. Foreign/null/duplicate headers are rejected before Core commands execute. GET also validates Host. No CORS permission was added.
- The shared heartbeat body is now a JSON Blob for fetch, page-closing and page-frozen beacons. Ordinary commands and keepalive autosave retain their JSON headers and existing behaviour.
- Tests written first: 22 of 26 new HTTP cases reproduced missing rejection (four allowed cases already passed). Full suite after the fix: **208 passed, 8 slow tests deselected**; `mypy`, `ruff check` and `git diff --check` passed.
- Standard release build produced `dist/ozvuchka-issue-41.zip`. Its smoke test passed, including real Kokoro, second-launch `page_opening`, automatic exit after the closing event, data-only writes and startup diagnostics. Provider/build source was unchanged; the separate slow suite was not run.
- Browser acceptance could not be completed: the sandboxed preview initially timed out; an outside-sandbox restart then returned HTTP 200 to an independent probe. On UI resumption, Computer Use stopped because it could not reliably determine the Windows browser URL. Edge executable version is 156.0.4314.58. No foreign-origin browser request, LNA permission/policy check, public HTTPS-source check or allowed-permission profile check is claimed. The Issue stays open.
- Developer everyday browser acceptance passed on 2026-11-05 with the ZIP rebuilt on the current computer: saving two Texts, preparing speech, F5/Playback, deleting one Text, close/wait/reopen and a second launcher start. The developer confirmed the supplied check worked. The rebuilt 177 MB ZIP also passed the agent smoke test (page after 1.2 s, real Kokoro speech 0.85 s, second launch, closing, data-only writes and both startup diagnostics). This does not separately verify the freeze event or individual beacon dispatch.
- Agent foreign-loopback-origin browser check passed on 2026-11-05 in the in-app Chromium browser (reported Chrome/156.0.0.0): source `http://127.0.0.1:8782`, target `http://127.0.0.1:8781`. Permission query reported `prompt`; no permission interaction or security-setting change occurred. The simple POST reached the server and returned 403 (opaque response to the page); JSON preflight returned 501 with no subsequent JSON POST logged. Before/after state snapshots were identical and `library.json` remained absent; neither marker appeared. This establishes protection when the browser lets the simple request reach the target. It does not establish Edge policy state or public HTTPS behaviour.
- The developer explicitly accepted the completed checks as sufficient on 2026-11-05 and requested closure. Installed Edge foreign-origin, public HTTPS-origin, explicitly allowed LNA and separate freeze/beacon observations remain unperformed, not failed; they are waived for this accepted scope. Unchecked matrix criteria above retain that evidence distinction. Existing hardware acceptance is unchanged. [Detailed evidence and screenshot](design-reviews/issue-41/README.md).

## Finding 6 — Bound the real cancellation test by a process deadline

Priority: low for the product, useful before subsequent slow checks.

Scope: `tests/test_voice_provider_contract.py` and a small test helper if needed. Related Issue: #31; ADR-0004. Recommended before finding 4 verification.

Run the specific real cancellation scenario in a child process with a parent-enforced deadline and cleanup. Keep cancellation and the next synthesis on the same loaded provider within that child. Allow a separate adequate model-loading budget; measure cancellation from its signal after active inference starts. Retain useful failure output.

Acceptance:

- [ ] The real test still proves active cancellation and successful subsequent synthesis on the same loaded provider.
- [ ] A deliberately blocked child demonstrates bounded failure and cleanup without consuming the CI job's 60-minute timeout.
- [ ] Parent timeout handling terminates/reaps the child and returns a diagnostic failure on Windows.
- [ ] Relevant slow tests pass; no production cancellation algorithm change is made.

Do not substitute shutdown(wait=False): [Python 3.12 documents](https://docs.python.org/3.12/library/concurrent.futures.html) that interpreter exit still waits for executor threads. Do not build a general test framework. School-device cancellation latency remains covered by #24, not established by this test change.

## Finding 4 — Make WAV the explicit current provider contract

Priority: medium contract defect; current Kokoro users are not affected by MP3 output.

Scope: Audio/VoiceProvider contract, validation at the handled provider-result boundary, existing Core/contract tests and narrowly relevant developer documentation. Related Issue: #1. Prefer completing finding 6 before running real-provider verification.

Decision: support WAV now; defer MP3 storage until a concrete provider requires it. WAV is already assumed by persistence, discovery, duration loading, deletion, size accounting and the existing provider contract test. Narrow the format type and document the contract, but also reject unsupported runtime output inside an error-handled synthesis boundary. Report a teacher-readable Narration error and keep the worker usable for subsequent valid work. Replacing assert with another uncaught exception or adding only a type annotation is insufficient.

Acceptance:

- [ ] Provider and Audio contracts explicitly describe supported WAV output; relevant Voice sample expectations are consistent.
- [ ] Invalid-format output gives an observable Narration failure without terminating the worker; a subsequent valid Narration completes.
- [ ] Existing fake/real provider contract tests verify WAV output and duration; required slow checks pass.
- [ ] Documentation explicitly records the narrower current promise: a WAV provider is one new module; an MP3 provider must normalize internally or require a separate storage extension.
- [ ] Document that this qualifies the original #1 promise of an Edge/MP3 provider added with one module. Do not silently present WAV-only as fulfilling that promise.

Bounds: no MP3 decoder dependency, sidecar-duration format, storage migration or new online provider. If MP3 is later implemented, plan persistence/discovery/readback/deletion/size and browser playback-after-restart together. ADR-0002 continues to defer the online provider; this work does not reverse it.

## Finding 5 — Keep queue titles consistent with the Library

Priority: low; a bounded user-visible consistency fix.

Scope: Core queue snapshot, app.js renderQueue and Core tests. Related Issues: #12, #31. Independent of other fixes.

Use the Text's chosen title with the usual content-derived fallback in queue snapshots. Refresh the existing row's title and cancel button aria-label when the snapshot changes without replacing its focused button. Preserve queue IDs, ordering, progress and cancellation semantics.

Acceptance:

- [ ] Core tests cover a custom title before/after enqueue and an updated automatic title with stable Narration ID.
- [ ] In the real page, rename a waiting Text and observe the new queue title and accessible cancel name without re-enqueueing.
- [ ] A focused cancel button stays focused through title/progress updates; ordering and cancellation still work.
- [ ] Verify with the real Core/HTTP/page and an existing paced provider seam if needed, not a static mock or new JS test framework.

## Shared developer acceptance and non-goals

After implementation use a separately unpacked program with a fresh disposable Library, not the teacher's data. Paste two Texts, wait for confirmed saving, prepare a Narration, rename a waiting Text and check its queue title. Reload, play ready speech, delete the unwanted Text, close and reopen. Expect preserved confirmed content/audio, consistent names and normal lifecycle behaviour. For a quick queue, use the existing paced preview for agent browser verification; do not require fault injection in everyday developer acceptance.

Agent automation owns write failures, invalid JSON and controlled test hangs. Agent browser checks own the detailed foreign-origin and DOM/focus cases, with limitations recorded. The developer's everyday check supplements rather than repeats those matrices.

No new projector/presenter-remote/hardware-only checks are introduced by this plan. Existing Celeron/i5, Athlon, classroom and cancellation timing checks remain in [docs/manual-checks.md](manual-checks.md) and [Issue #24](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/24). If implementation introduces a genuinely new hardware acceptance criterion, add it there in the same implementation commit. Do not mark existing hardware checks complete based on automation or browser evidence.

Keep this proportional to a simple playback application: no crash-proof editor, recovery system, UI redesign, dependency upgrades or broad test-framework changes.
