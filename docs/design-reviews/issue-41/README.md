# Issue #41 — HTTP protection verification

Date: 2026-11-05. Status: HTTP implementation and release smoke verified;
browser acceptance remains incomplete. No teacher Library was used.

## Implemented policy

GET and command requests require exactly one Host matching `127.0.0.1:<port>`
or `localhost:<port>`, using the server's actual bound port. At port 80, the
authorities without a port are also supported. The server still binds only IPv4
loopback; IPv6, foreign names and different ports are not supported authorities.

Commands permit absent Origin for Python launcher/tools, or exactly one Origin
matching one of the supported HTTP application origins. Foreign, empty, `null`
and duplicate Origin headers are rejected with 403 before invoking Core. Origin
is compared against supported application origins, not an arbitrary Host value.

Commands require one `application/json` Content-Type (case-insensitive, with
parameters such as `charset=utf-8` accepted); unsupported/missing/duplicate
Content-Type is rejected with 415. No CORS permissions are added; foreign
preflight is not allowed. This does not authenticate a hostile local process.

The page's heartbeat helper now creates a JSON Blob, so fetch heartbeats and
the closing/frozen beacons supply the required MIME type. Ordinary commands and
keepalive saves already supplied JSON and retain their existing behaviour.

## Agent verification

- Tests written first: after fixing the test connection cleanup, 22 of the 26
  new HTTP cases reproduced missing rejection; four allowed combinations passed.
  All 28 HTTP tests pass after the fix. Tests use real Core/HTTP and disposable
  data, checking target state as well as status and absence of CORS permission.
- `mypy` and `ruff check` pass. Full suite results are recorded in the fix plan.
- Built `dist/ozvuchka-issue-41.zip` with the standard release script. The first
  build attempt hit a sandbox temporary-directory restriction; retrying with
  an isolated writable TEMP/TMP directory completed successfully.
- Release ZIP smoke passed: page served after 2.2 s, second launcher ended
  while the first kept running, real Kokoro synthesized "Hello." (0.85 s),
  closing ended the program, writes stayed in `data/`, and both startup
  diagnostic scenarios passed. This verifies Origin-less JSON tools including
  second-launch `page_opening`; it does not verify browser beacon dispatch.

## Browser evidence and limitations

- Installed Edge executable reports **156.0.4314.58**. Its update page also
  exposed that version in its URL. An existing ordinary profile was opened;
  no security settings or permissions were changed.
- The initial test server ran inside the sandbox. Browser navigation to
  `http://127.0.0.1:8781/` timed out, and the developer stopped Computer Use
  because the visible page was unresponsive. This was an environment failure,
  not an observed application security rejection.
- Restarted the existing paced preview outside the sandbox with `--texts 0`.
  An independent HTTP probe of `/api/state` returned 200. On resuming UI
  verification, Computer Use stopped because it could not reliably determine
  the current Windows browser URL. No further UI actions were attempted.
- Application autosave/reload/close/freeze in a real browser is **not yet
  verified**. No foreign-origin browser request was exercised. Target state
  and request arrival for those scenarios therefore have no browser result.
- Different-loopback-port requests, a controlled public HTTPS source, actual
  Edge policy/permission state, and explicitly allowed LNA in a disposable
  profile are **untested**. Raw HTTP tests establish server rejection, not
  browser exploitability. Do not infer that arbitrary internet pages can
  currently reach the application.

## Resume agent browser acceptance

Use `tools/ui_design_preview.py --port 8781 --texts 0` outside network isolation
with its disposable Library. Probe `/api/state` before opening the UI. Exercise
ordinary typing/confirmed save, reload, Play and close/reopen in the real page;
observe server requests and state, including JSON heartbeat/closing beacons.
Use a separately unpacked release with the actual launcher for lifecycle checks.

`foreign-origin.html` is a static acceptance fixture, not an automated page
test. Serve this directory from a separate loopback port, for example:

```powershell
runtime\python.exe -m http.server 8782 --bind 127.0.0.1 --directory docs/design-reviews/issue-41
```

Open `http://127.0.0.1:8782/foreign-origin.html`, verify the target field points
only to the isolated preview, and send the two harmless marker requests. Record
the browser/version, source and target origins, observed LNA permission and
policies, console/network result and target server log. Independently inspect
the target `/api/state` and Library bytes: neither marker may appear. A simple
request may reach the server and receive 403 while its response remains opaque;
a JSON request may stop at preflight. Record what actually happened.

Repeat from a controlled public HTTPS source only when one is available, with
normal permissions and, where practical, explicitly allowed LNA in a disposable
profile. Do not disable ordinary user protections. Keep the distinction between
public HTTPS and loopback results in the evidence.

## Short developer acceptance

Unpack `dist/ozvuchka-issue-41.zip` into a fresh folder with a disposable Library.
Start `Озвучка.exe`, save two short English Texts and prepare speech. Reload and
play one, delete the unwanted Text, close and wait about 10 seconds, then reopen.
Expect confirmed content and ready speech to remain, the deleted Text to stay
absent, and normal opening/closing. Also start the launcher again while the
window is open: it should reopen the running program with the same Library.
The detailed foreign-origin matrix remains an agent check, not routine
developer acceptance. Existing hardware checks in `docs/manual-checks.md` are
unchanged.
