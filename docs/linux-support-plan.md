# Linux support plan

Status: all six stages (#57-#62) are complete. Desktop acceptance was completed on 2026-11-12 and umbrella #56 is closed.

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

The following code remains platform-independent:

- `ozvuchka/core.py`, `library.py`, `settings.py`, `scheduling.py` and `text.py`;
- `ozvuchka/audio.py` and `export.py`, including the explicit little-endian MP3 PCM handling;
- `ozvuchka/kokoro.py` and the pinned ONNX model/Voice data, subject to native dependency checks;
- `ozvuchka/server.py` and `ozvuchka/web/`, with the browser responsible for audio output;
- `ozvuchka/log.py` and atomic Library persistence.

Platform integration is separated into small startup modules:

- `ozvuchka/__main__.py` delegates the per-port single-instance protocol to `ozvuchka/instance.py`.
  That module selects `WindowsPortLock` from `instance_windows.py` on Windows or `PosixPortLock`
  from `instance_posix.py` on Linux, importing only the selected implementation.
- `ozvuchka/window.py` opens the local page and owns the shared window interface. Windows native
  discovery and placement are loaded from `window_windows.py` only when `WindowMonitor` is created;
  Linux uses the default browser without a placement monitor.
- Windows retains its .NET launcher and `tools/build.ps1`; Linux has `Озвучка.sh` and
  `tools/build_linux.py` with the baseline standalone runtime.
- `tools/smoke_test.py`, platform tests and `.github/workflows/build.yml` explicitly cover both
  release archives and their platform-specific lifecycle and diagnostics.

Keep platform checks out of Core and the page, and load Windows-only imports only on Windows.

## Implemented design

### Application startup and window behavior

The common per-port protocol preserves the running-page handshake and timeout behavior. Windows
uses a named mutex; Linux uses a process-lifetime `fcntl.flock`. Process exit releases either lock,
and a second start opens the existing loopback page and exits without loading Kokoro or creating
another server.

Windows retains Edge discovery and `WindowMonitor`. On Linux, Python's standard browser mechanism
opens the URL, heartbeat shutdown/reload grace behavior remains unchanged, and no native placement
monitor or `data/window.json` is created.

This made ADR-0003 platform-specific while preserving its local web-page decision. Stage 2 amended
that ADR and the affected module documentation.

### Development and release builds

Development uses isolated CPython 3.12 runtimes and wheel-only pinned dependencies. The Linux
release uses a pinned **baseline x86-64** standalone CPython distribution, not an `x86_64_v2/v3`
build, plus manylinux wheels and the same checked Kokoro/spaCy assets as Windows.

The Linux launcher starts the bundled interpreter with `-X utf8 -m ozvuchka --app`, forwards
arguments and preserves current-startup diagnostics without Zenity/KDialog dependencies. The tar
archive preserves executable permissions and contains no user `data/`, build host paths or
build-only tooling.

Shared dependency/model versions and checksums live in `tools/build-assets.json` and the pinned
requirements. Stage 4 extended ADR-0001 from a single Windows portable folder to per-platform
portable folders, including the Linux license/notice differences.

### CI and publication

Windows and Linux ordinary tests, real Kokoro slow tests, strict mypy and ruff run on every push.
Only genuinely platform-specific tests are marked, and the minimum-glibc 2.29 job prevents a newer
runner from silently raising the supported floor.

CI smoke-tests the exact uploaded archives: real synthesis, MP3 export, second launch, heartbeat
shutdown, diagnostics and writes only under `data/`. Both artifacts are uploaded on every successful
build. On a version tag, one downstream release job waits for all three build/test jobs and publishes
both files to one GitHub Release; it checks out the repository so `gh` can generate release notes.

## Completed stages

The stages were completed and evidenced in order. The linked Issues contain their full work lists,
out-of-scope boundaries and acceptance criteria. The subsections below preserve the original work
contracts as an implementation record, not as pending instructions.

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

The stage originally proposed at least one Debian/Ubuntu-family and one non-Debian-family desktop,
covering Firefox and a Chromium-family browser. On 2026-11-12 the developer explicitly accepted
**M.OS 12** (ROSA-based) and **Альт Образование 10** as the sufficient final matrix, replacing the
Debian/Ubuntu requirement. The developer confirmed the required offline launch, audible Narration
and Voice samples, Playback controls, MP3, reload/close, second launch and persistence checks, as
well as disposable Windows/Linux Library transfer and the executable-removable-mount workflow.

The Russian README, English development documentation and ADRs are complete. Agent-performed checks
remain distinguished from the developer's audible/desktop acceptance. Completed manual-check entries
were removed after acceptance.

## Validated environments and acceptance boundary

The exact Linux archive has passed headless real-provider and lifecycle checks on Debian 12 (glibc 2.36) and
offline Fedora 30 (glibc 2.29), including paths with spaces/Cyrillic, second launch, MP3 and diagnostics.
A built-in-browser run against the archive in WSL also confirmed Text autosave, two ready Paragraphs, Playback
completion, a downloaded MPEG and F5 persistence. These automated and agent-run results are not the source
of the audible desktop acceptance.

Final desktop/browser acceptance was completed by the developer on M.OS 12 and Альт Образование 10 on
2026-11-12, with no reported defects. Both desktops used **X11 and Chromium**; exact browser versions and
the installed glibc versions were not recorded. No distribution or browser coverage beyond the recorded
environments is implied: the accepted matrix establishes neither separate Debian/Ubuntu nor Firefox
desktop evidence.

## Verification policy

- Follow `CODING_STANDARDS.md`: tests first for behavior changes, and pytest, mypy and ruff before
  every commit. Run slow real Kokoro tests after provider or build changes.
- Preserve the full Windows checks alongside Linux checks; Linux success is not evidence that
  Windows still works.
- Development-venv success is not release success. Release verification must test the unpacked shipped artifact.
- Headless WAV generation is not audible browser Playback acceptance. Record real browser/desktop
  evidence separately in the owning Issue.
- Use fresh disposable Libraries for manual acceptance and destructive checks.
- Do not claim musl, ARM, old CPUs, other desktop sessions or `noexec` mounts from inference alone.

## Fresh-session handoff

1. Read `AGENTS.md`, `CODING_STANDARDS.md`, this plan, umbrella #56 and the relevant closed stage's
   final evidence. Read ADR-0001/0003 and ADR-0002 when touching the provider.
2. Inspect `git status` and recent history. Do not redo closed stages or overwrite unrelated work.
3. The six implementation stages are complete. The listed non-goals require a new explicit decision
   and Issue rather than becoming implicit follow-up work.
4. Use `Part of #N` for partial commits and `Closes #N` only for a commit that completes an Issue.
   Update affected ADRs/docstrings and `docs/manual-checks.md` in the same commit as the behavior.
5. Post tested environments, commands, results and artifact details in the owning Issue. Close it
   only when its acceptance criteria are met, then update the stage status here.

No manual acceptance remains for this track.
