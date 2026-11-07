# Linux support plan

Status: stages 1-2 (#57, #58) and stage 4 (#60) complete; stages 3 and 5 (#59, #61) await pushed green CI runs.

Umbrella: [GitHub Issue #56](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/56).
The stage Issues are the detailed work contracts. This document is the durable technical plan and
fresh-session entry point; update it when validated evidence changes a decision.

## Context and outcome

The Windows application already separates its portable Library, Narration queue, Voice provider,
WAV/MP3 code, loopback HTTP server and plain web page from most operating-system facilities. Linux
support should extend that architecture rather than introduce another application or UI stack.

The intended outcome is a second release artifact for **Linux x86-64 with glibc 2.29 or newer**.
It must run offline from an unpacked self-contained folder without a system Python, compiler,
distribution eSpeak/LAME/FFmpeg packages, or a particular distribution's package manager. The
existing Windows ZIP and its behavior must remain supported.

The initial Linux version uses an installed modern Firefox- or Chromium-family browser. It opens
the default browser rather than promising an Edge app window or native window-placement restore.
The Library remains in the program folder's `data/` directory and keeps the current format.

## Support contract for the first release

- Linux x86-64, baseline x86-64 CPU instructions, glibc 2.29 or newer.
- CPython 3.12 and the existing pinned application dependencies, subject to the stage-1 gate.
- A modern installed browser; no browser is bundled.
- One portable `ozvuchka-<version>-linux-x86_64.tar.gz` containing `Озвучка/` and an executable
  relative-path launcher.
- No runtime network access, installation, system Python, compiler, system eSpeak, LAME or FFmpeg.
- A normally executable filesystem. A removable volume mounted `noexec` is not a supported target.
- No guarantee that Linux restores browser-window bounds or maximized state.

The original glibc 2.28 estimate came from the pinned `onnxruntime==1.31.0` CPython 3.12
`manylinux_2_28_x86_64` wheel. Stage 1 confirmed its `GLIBC_2.28` requirement, but also found that the
bundled `espeakng-loader==0.2.4` library requires `GLIBC_2.29` despite its manylinux_2_17 wheel tag. The
validated floor is therefore glibc 2.29. A successful test on a current Ubuntu runner alone still does not
establish the minimum supported environment.

### Explicit non-goals

- Alpine/musl, ARM, 32-bit Linux and macOS artifacts.
- Flatpak, Snap, AppImage, DEB/RPM or distribution-specific installation.
- A bundled browser, a Qt/GTK UI, a new JavaScript framework or an online dependency.
- X11- and Wayland-independent window placement or desktop-environment-specific integrations.
- Replacing, weakening or delaying the existing Windows release pipeline.

These can be considered later through new decisions and Issues; they are not implicit follow-up
work for this track.

## Current platform boundaries

The following existing code is expected to remain platform-independent:

- `ozvuchka/core.py`, `library.py`, `settings.py`, `scheduling.py` and `text.py`;
- `ozvuchka/audio.py` and `export.py`, including the explicit little-endian MP3 PCM handling;
- `ozvuchka/kokoro.py` and the pinned ONNX model/Voice data, subject to native dependency checks;
- `ozvuchka/server.py` and `ozvuchka/web/`, with the browser responsible for audio output;
- `ozvuchka/log.py` and atomic `data/` persistence.

The required platform work is concentrated elsewhere:

- `ozvuchka/__main__.py` uses a Win32 named mutex for the per-port single-instance protocol.
- `ozvuchka/window.py` imports `winreg` and Win32 `ctypes` APIs at module import, discovers Edge and
  monitors native window placement. It cannot currently be imported on Linux.
- `tools/launcher/Ozvuchka.cs` is a Windows .NET Framework launcher.
- `tools/build.ps1` acquires Windows embeddable Python and VC++ DLLs and builds the Windows ZIP.
- `tools/smoke_test.py`, `tests/test_launcher.py` and `.github/workflows/build.yml` contain
  Windows-specific release and test behavior.

Do not scatter platform checks through Core or the page. Use small startup/platform modules and
load Windows-only imports only on Windows.

## Target design

### Application startup and window behavior

Keep the current per-port protocol and its race/timeout behavior. Preserve the Windows named mutex;
use a process-lifetime POSIX lock on Linux, such as `fcntl.flock`. A process exit must release the
lock, and a second start must open the existing loopback page and exit without loading Kokoro or
creating another server.

Keep Windows Edge discovery and `WindowMonitor` in a Windows implementation. On Linux, open the
URL through Python's standard browser mechanism, retain heartbeat shutdown/reload grace behavior,
and do not start a native placement monitor. Linux need not create `data/window.json`.

This deliberately makes ADR-0003 platform-specific while preserving its local web-page decision.
Stage 2 must amend that ADR and affected docstrings when implementing the behavior.

### Development and release builds

Use an isolated CPython 3.12 development runtime and wheel-only pinned dependencies for stages 1-3.
For the release, use a pinned **baseline x86-64** standalone CPython distribution, not an
`x86_64_v2/v3` build, plus manylinux wheels and the same checked Kokoro/spaCy assets.

The Linux launcher starts the bundled interpreter with `-X utf8 -m ozvuchka --app`, forwards
arguments and preserves current-startup diagnostics without Zenity/KDialog dependencies. The tar
archive must preserve executable permissions and contain no user `data/`, build host paths or
build-only tooling.

Reuse shared dependency/model versions and checksums where practical rather than allowing Windows
and Linux builds to drift. Do not rewrite the working Windows build merely for stylistic sharing.

This deliberately extends ADR-0001 from a single Windows portable folder to per-platform portable
folders. Stage 4 must amend the ADR, including the Linux license/notice differences.

### CI and publication

Keep Windows checks and add Linux ordinary tests, real Kokoro slow tests, strict mypy and ruff.
Narrowly mark only genuinely platform-specific tests; do not skip broad modules to obtain green CI.
Include a validated glibc 2.29 environment so newer-runner builds cannot silently raise the floor.

After the archive exists, smoke-test that exact artifact in a clean environment: real synthesis,
MP3 export, second launch, heartbeat shutdown, diagnostics and writes only under `data/`. Upload
both artifacts on every successful build. On a version tag, one downstream release job must wait
for both platform builds and publish both files to one GitHub Release; parallel jobs must not race
to create separate or partial releases.

## Ordered stages

Each stage should be completed and evidenced before the next begins. The linked Issue contains the
full work list, out-of-scope boundaries and acceptance criteria.

| Stage | Issue | Deliverable | Depends on |
| --- | --- | --- | --- |
| 1 | [#57](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/57) | Validated native dependency gate and reproducible Linux development runtime | None |
| 2 | [#58](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/58) | Linux application startup, POSIX single instance and platform-separated window integration | #57 |
| 3 | [#59](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/59) | Linux ordinary/slow/type/lint checks in CI, including minimum glibc | #58 |
| 4 | [#60](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/60) | Self-contained offline Linux tar.gz, bundled runtime and launcher | #59 |
| 5 | [#61](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/61) | Exact-artifact smoke tests, Actions artifacts and coordinated GitHub Release publication | #60 |
| 6 | [#62](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/62) | Real desktop/browser acceptance and final teacher/developer documentation | #61 |

### Stage 1: native dependency gate and development runtime

Prove real Kokoro/misaki/eSpeak WAV synthesis and `lameenc` MP3 encoding with CPython 3.12 on
Linux x86-64. Establish the pinned development setup, check paths containing spaces/Cyrillic,
record actual wheel/glibc/CPU requirements and collect Linux license differences. Do not start
startup refactoring or release packaging here. If the gate fails, record it and revise this plan
before stage 2 rather than hiding it behind unreviewed dependency upgrades.

The stage-4 license inventory starts from the existing package, model, Voice and font notices. Linux uses
the same eSpeak NG, LAME and ONNX Runtime projects and source references, but their native files are Linux
shared libraries rather than Windows DLL/PYD files. The archive has no Microsoft Visual C++ runtime or
.NET launcher; it carries the selected standalone CPython distribution's license instead of the Windows
embeddable-Python file. Stage 4 must also preserve license files shipped inside the actual manylinux wheels,
including notices for bundled libraries in `.libs` directories, rather than copying only the Windows license
folder. In particular, the validated NumPy 2.3.5 manylinux wheel bundles OpenBLAS/LAPACK, libgfortran and
libquadmath in `numpy.libs/`; its `dist-info/LICENSE.txt` carries their BSD and GCC-runtime-exception notices.

### Stage 2: cross-platform application startup

Separate Windows-only imports and implementations, add the POSIX per-port lock and default-browser
launch, and preserve heartbeat lifecycle. Write public-seam behavior tests first. Prove Linux real
provider operation and second-instance behavior while keeping Windows mutex, Edge and placement
behavior unchanged. No X11/Wayland placement implementation.

### Stage 3: continuous Linux checks

Run ordinary and real Kokoro slow tests, mypy and ruff on Linux on every push, with explicit
minimum-glibc coverage. Keep the existing Windows test and release jobs green. Document commands
that match the actual development setup and workflow.

### Stage 4: portable release archive

Build the baseline standalone runtime, pinned Linux packages, model, Voice samples, licenses and
relative launcher into the named tar.gz. Preserve startup diagnostics and the `data/` write
boundary. Perform a basic clean-environment synthesis/export check, leaving full smoke automation
to stage 5. Amend ADR-0001 and development build instructions.

### Stage 5: exact-artifact verification and publication

Extend platform-specific smoke coverage without weakening Windows assertions. Test executable
permissions, real synthesis/MP3, single instance, shutdown, early failures and no writes outside
`data/` from the unpacked archive. Run on minimum glibc and the normal Linux CI environment, with
an offline clean-environment check. Upload both artifacts and coordinate tag publication after both
platforms pass.

### Stage 6: desktop acceptance and documentation

Check the release artifact in a small representative matrix: at least one Debian/Ubuntu-family and
one non-Debian-family desktop, Firefox and a Chromium-family browser. Verify audible Narration and
Voice samples, Playback controls, MP3, reload/close, second launch and persistence. Check disposable
Library transfer between Windows and Linux in at least one direction rather than assuming it.

Update Russian README and English development documentation, finish ADR consistency and record
remaining manual checks in `docs/manual-checks.md` with #62. Distinguish agent-performed checks
from the developer's audible/desktop acceptance. Do not close #62 or #56 with required acceptance
silently unchecked.

## Verification policy

- Follow `CODING_STANDARDS.md`: tests first for behavior changes, and pytest, mypy and ruff before
  every commit. Run slow real Kokoro tests after provider or build changes.
- Preserve the full Windows checks in every relevant stage; Linux success is not evidence that
  Windows still works.
- Development-venv success is not release success. Stage 5 must test the unpacked shipped artifact.
- Headless WAV generation is not audible browser Playback acceptance. Record real browser/desktop
  evidence separately in #62.
- Use fresh disposable Libraries for manual acceptance and destructive checks.
- Do not claim musl, ARM, old CPUs, other desktop sessions or `noexec` mounts from inference alone.

## Fresh-session handoff

1. Read `AGENTS.md`, `CODING_STANDARDS.md`, this plan, umbrella #56 and the first open stage in the
   table. Read ADR-0001/0003 and ADR-0002 when touching the provider.
2. Inspect `git status`, recent history and the predecessor Issue's final evidence comment. Do not
   redo closed stages, overwrite unrelated work or assume an open stage's result.
3. Work only within the selected stage. If evidence invalidates the support contract or sequencing,
   record it in the Issue and update this plan before proceeding.
4. Use `Part of #N` for partial commits and `Closes #N` only for a commit that completes the stage.
   Update affected ADRs/docstrings and `docs/manual-checks.md` in the same commit as the behavior.
5. Post tested environments, commands, results, artifact details and remaining checks in the stage
   Issue. Close it only when its acceptance criteria are met, then update the stage status here.

No manual acceptance is required for this planning-only document itself. All implementation and
acceptance work remains in the open Issues above.
