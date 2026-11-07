# Development

An offline program that reads English texts aloud during English lessons. See [GLOSSARY.md](../GLOSSARY.md) for the terms, [ADRs](adr/) for the decisions,
and [CODING_STANDARDS.md](../CODING_STANDARDS.md) for coding rules.
Teacher-facing instructions are in the [Russian README](../README.md).
Run the commands below from the repository root.

## Planned Linux support

Linux support is planned, not currently shipped. The support target, technical decisions, ordered
stage Issues and fresh-session handoff are in the [Linux support plan](linux-support-plan.md).
[Issue #56](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/56) is the umbrella;
start with its first open stage and do not begin a later stage before its predecessor's acceptance
evidence is recorded.

NumPy is pinned to 2.3.5 to keep the program usable on older CPUs such as the
Athlon II X2 250. NumPy 2.4 raised its default CPU baseline to x86-64-v2
([release notes](https://numpy.org/doc/stable/release/2.4.0-notes.html#modulate-dispatched-x86-cpu-features)).
The isolated v0.2 build with 2.3.5 was tested successfully on the Athlon and an
11th-generation Core i5 laptop. The developer accepted these checks as sufficient;
the perceived speed difference was minimal, without timed measurements
([#26](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/26)).
Review older-CPU support before upgrading this dependency.

## UI design

The [UI design specification](ui-design-spec.md) is the source of truth for the current
UI on `main`. It includes the accepted `experiment-2` interaction model and the visual
refresh accepted on 2026-11-06.

## Voice provider audio contract

The current `Audio` and `VoiceProvider` contracts support **WAV only**, including
Voice samples. Providers return WAV bytes and duration in seconds; Core rejects
other runtime format values as a visible Narration failure before persistence,
then continues the Narration queue. This format check does not decode arbitrary
bytes or establish that a provider's declared WAV bytes are valid; that remains
part of the provider contract, checked by the fake/real contract suite.

A new WAV Voice provider is one module. A provider producing MP3 or another
source format must normalize its output to WAV internally, or require a separate
storage extension. This narrows the original [Issue #1](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/1)
promise that an Edge/MP3 provider could be added as one module returning MP3;
that broader promise is not implemented. Any future MP3 storage design must
cover persistence, duration discovery, readback, deletion, size accounting and
browser Playback after restart together. No decoder or storage migration is
introduced now; ADR-0002 still defers the online provider.

MP3 export does not broaden this WAV contract. `lameenc==1.9.0` encodes ready mono
16-bit 24 kHz WAV pieces in memory at 128 kbit/s, with the same piece fades and 0.7-second
Paragraph pauses as browser playback. It neither synthesizes missing pieces nor stores MP3
or intermediate WAV files in the Library. The pinned CPython 3.12 Windows x64 wheel is
self-contained; no compiler, system LAME/FFmpeg, decoder stack, or network is needed at
runtime. Its LGPL/GPL license texts, notices, and source references ship in `licenses\`.

## Local environment

Build the local runtime (embeddable Python 3.12, packages, Kokoro model, spaCy model, pytest, mypy, ruff) into `runtime\` and `models\`. Needs internet; run it again after a failure, finished steps are skipped:

```bat
tools\build.bat dev
```

Run the tests (the real Kokoro tests are marked `slow` and skipped by default):

```bat
runtime\python.exe -m pytest
runtime\python.exe -m pytest -m slow
```

Check types and lint (settings in `pyproject.toml`; the rules the tools don't check are in `CODING_STANDARDS.md`):

```bat
runtime\python.exe -m mypy
runtime\python.exe -m ruff check
```

Start the program and open http://127.0.0.1:8770:

```bat
runtime\python.exe -X utf8 -m ozvuchka
```

Started this way the program keeps running until Ctrl+C. Its log is `data\ozvuchka.log`.

### Linux development runtime

Linux application startup and a local portable-archive build are implemented; CI publication remains a later
stage. On Linux x86-64 with CPython 3.12 and its `venv` module already installed, run from the repository root:

```bash
python3.12 tools/setup_linux.py
```

The setup needs internet access. It creates `runtime-linux/`, installs the existing direct and transitive
pins with `--only-binary=:all:`, and installs the checked spaCy/Kokoro assets into the shared `models/`
folder. Downloads are cached in `.cache/`; finished setup steps can be rerun. No compiler, system eSpeak,
LAME or FFmpeg is used.

Start the program and open the loopback page in the default browser:

```bash
runtime-linux/bin/python -X utf8 -m ozvuchka --app
```

A second start opens the running page and exits. The per-port `data/instance-<port>.lock` file may remain,
but its flock is released when the owning process ends. Linux has no placement monitor and does not create
`data/window.json`; page heartbeat and reload grace work as on Windows.

Run the checks, including the real provider and cancellation tests:

```bash
runtime-linux/bin/python -m pytest
runtime-linux/bin/python -m pytest -m slow
runtime-linux/bin/python -m mypy
runtime-linux/bin/python -m ruff check
```

Every push runs those same four commands in two Linux jobs: current Ubuntu and a pinned Fedora 30 container
with the minimum glibc 2.29. The minimum job first runs `python tools/download_linux_python.py`, then the
same `tools/setup_linux.py` and checks in the container; its final checks run with Docker networking disabled.
The same downloaded baseline CPython is used by CI and the portable release build. Both jobs log the
environment, cache `.cache/` downloads (including pip wheels), and rebuild `runtime-linux/` from the current
pins on every run.
The Fedora setup passes `SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt` so the standalone interpreter uses
the system CA bundle; certificate verification is never disabled.

The validated dependency target is glibc 2.29 or newer and baseline x86-64 (the bundled eSpeak library
requires `GLIBC_2.29`); this development setup does not claim musl, ARM or older-glibc support. Shared model
versions and checksums live in `tools/build-assets.json`, used by the Windows, Linux and CI setup entry points.

## The program the teacher gets

The release zip `ozvuchka-<version>.zip` holds one folder, `Озвучка\` (ADR-0001):

- `Озвучка.exe` — the launcher. It starts `runtime\python.exe -m ozvuchka --app` from its own folder, with no console window; the program opens its window with `msedge --app=http://127.0.0.1:8770` at once, or the default browser on a computer without Edge (ADR-0003), and loads Kokoro in the background: a ready Narration plays meanwhile, a new one waits for the Voices. The Edge window restores its normal bounds and maximized state from `data\window.json`. Starting `Озвучка.exe` again opens the window of the program already running instead of starting a second one. If the program stops with an error, the launcher shows Python's exit code and saves its available error output in a separate `data\startup-<id>.log` for that launch. The message identifies that file, or explains that Python produced no output or that saving failed. Earlier `ozvuchka.log` entries are never presented as evidence of the current failure.
- `runtime\`, `ozvuchka\`, `models\` — Python with the packages, the program, the Kokoro model and the Voice samples. Python code is compiled ahead, so nothing is written there at start.
- `licenses\` — third-party licenses; `licenses\NOTICE.txt` lists the components.
- `data\` — not in the zip: the program makes it on the first start and keeps the Library, the settings and its log `ozvuchka.log` there (rotated: at most three parts of 1 MB). All program-managed writes stay there; explicitly requested browser downloads are user-owned outputs in browser-selected destinations.

When the window is closed, the page stops sending its heartbeat and the program ends by itself, about 10 seconds later (it waits that long in case the page is only being reloaded with F5). A page that has not been heard from for two minutes counts as closed too.

## Building a release

GitHub Actions (`.github/workflows/build.yml`) builds both releases on every push. Windows runs its ordinary/slow/type/lint checks, zip build and smoke test. The normal Linux job runs the same checks, builds the tar.gz and smoke-tests that exact archive; the minimum-glibc job downloads the uploaded archive and repeats its smoke test offline on glibc 2.29. Both artifacts are retained for 14 days. On a version tag, one downstream release job waits for all three build/test jobs and places both artifacts in one GitHub Release.

The shared smoke test unpacks into a fresh path with spaces/Cyrillic, starts the actual launcher with `--no-window`, gets the page, synthesizes "Hello." with real Kokoro, exports MP3, checks second launch, heartbeat shutdown, data-only writes, and deliberate application-import and interpreter-initialization failures. Windows retains its `.exe`, `_pth` and process-tree checks; Linux checks the executable tar launcher and uses POSIX process cleanup and the standalone runtime layout.

To build and smoke-test the Windows release locally (needs internet; the result is `dist\Озвучка\` and `dist\ozvuchka-<version>.zip`):

```bat
tools\build.bat release
runtime\python.exe tools\smoke_test.py dist\ozvuchka-<version>.zip
```

To build and smoke-test the Linux release on Linux x86-64 with CPython 3.12 (needs internet for the build only):

```bash
python3.12 tools/build_linux.py
runtime-linux/bin/python -X utf8 tools/smoke_test.py dist/ozvuchka-<version>-linux-x86_64.tar.gz
```

The result is `dist/ozvuchka-<version>-linux-x86_64.tar.gz`, containing one `Озвучка/` folder. It includes the
pinned baseline standalone CPython, application packages, model, Voice samples and actual Linux licenses.
`Озвучка.sh` starts the bundled interpreter with `-X utf8 -m ozvuchka --app`, forwards arguments and preserves
the child exit status. On failure it saves and identifies current output in `data/startup-<pid>.log` on the
terminal; it never uses an old `ozvuchka.log` as current-launch evidence. No desktop message-box dependency
is introduced. The launcher and native executables retain their permissions in the tar archive.

Both release modes build their folders from scratch and cache downloads in `.cache/`. The version defaults to
`git describe --tags`; use `-Version 1.0` for Windows or `--version 1.0` for Linux to override it.

## Releasing a version

1. Make sure the last build of `main` in GitHub Actions is green.
2. Tag the commit and push the tag:

   ```bat
   git tag v1.0
   git push origin v1.0
   ```

3. After Windows and both Linux jobs pass, one release job publishes `ozvuchka-1.0.zip` and `ozvuchka-1.0-linux-x86_64.tar.gz` in the same GitHub Release, under the tag's name, with notes made from the commits. If the release already exists, it uploads/replaces both assets instead. Edit the notes there if needed.

## Unblocking the zip

A zip downloaded from GitHub carries the "downloaded from the internet" mark, and Windows passes it on to every file unpacked from it, so SmartScreen warns about `Озвучка.exe` and may refuse to run it. Remove the mark from the zip **before** unpacking it:

- right-click the zip → Properties → tick **Unblock** at the bottom → OK; or
- in PowerShell: `Unblock-File .\ozvuchka-1.0.zip`

If the folder was already unpacked from a blocked zip, unblock everything in it: `Get-ChildItem -Recurse .\Озвучка | Unblock-File`.

## Copying to a flash drive

1. Unblock the zip (above) and unpack it on the computer first: unpacking straight onto a flash drive is much slower.
2. Copy the whole `Озвучка` folder to the flash drive, anywhere (the drive letter and the path may be different on each laptop; names in Russian are fine). The folder is about 400 MB of many small files, so the copy takes a few minutes; the flash drive may be FAT32, exFAT or NTFS.
3. On the laptop, open the folder on the flash drive and double-click `Озвучка.exe`. The first start on a laptop is slower while Windows reads the files from the flash drive.

To update, replace the folder's `runtime\`, `ozvuchka\`, `models\`, `licenses\`, `Озвучка.exe` and `version.txt` with the new ones, and keep `data\`: it holds the teacher's Library.

## Keeping the welcome page current

When publishing a release, check the Russian README against the shipped interface,
update button names and the screenshot, and remove any obsolete next-version note.
The teacher download link must lead to a published release, not an Actions artifact.
