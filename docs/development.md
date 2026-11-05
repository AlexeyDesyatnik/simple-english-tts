# Development

An offline program that reads English texts aloud during English lessons. See [GLOSSARY.md](../GLOSSARY.md) for the terms, [ADRs](adr/) for the decisions,
and [CODING_STANDARDS.md](../CODING_STANDARDS.md) for coding rules.
Teacher-facing instructions are in the [Russian README](../README.md).
Run the commands below from the repository root.

NumPy is pinned to 2.3.5 to keep the program usable on older CPUs such as the
Athlon II X2 250. NumPy 2.4 raised its default CPU baseline to x86-64-v2
([release notes](https://numpy.org/doc/stable/release/2.4.0-notes.html#modulate-dispatched-x86-cpu-features)).
The isolated v0.2 build with 2.3.5 was tested successfully on the Athlon and an
11th-generation Core i5 laptop. The developer accepted these checks as sufficient;
the perceived speed difference was minimal, without timed measurements
([#26](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/26)).
Review older-CPU support before upgrading this dependency.

## UI design

The accepted ten-stage `experiment-2` implementation is now the basis of `main`.
Its [UI design specification](ui-design-spec.md) and
[integrated acceptance record](design-reviews/issue-37/README.md) describe
the current design. The other design alternatives are retired; only the NumPy
compatibility change from the previous `main` was retained. See the
[adoption record](design-reviews/main-adoption/README.md) for source commits
and archived branch states.

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

## Local environment

The [2026-11-05 code review fix plan](code-review-fix-plan-2026-11-05.md)
records revalidated findings, implementation Issues, dependencies and acceptance.
Follow the plan's current task and implementation order;
the original review is [here](code-review-2026-11-05.md).

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

## The program the teacher gets

The release zip `ozvuchka-<version>.zip` holds one folder, `Озвучка\` (ADR-0001):

- `Озвучка.exe` — the launcher. It starts `runtime\python.exe -m ozvuchka --app` from its own folder, with no console window; the program opens its window with `msedge --app=http://127.0.0.1:8770` at once, or the default browser on a computer without Edge (ADR-0003), and loads Kokoro in the background: a ready Narration plays meanwhile, a new one waits for the Voices. Starting `Озвучка.exe` again opens the window of the program already running instead of starting a second one. If the program stops with an error, the launcher shows Python's exit code and saves its available error output in a separate `data\startup-<id>.log` for that launch. The message identifies that file, or explains that Python produced no output or that saving failed. Earlier `ozvuchka.log` entries are never presented as evidence of the current failure.
- `runtime\`, `ozvuchka\`, `models\` — Python with the packages, the program, the Kokoro model and the Voice samples. Python code is compiled ahead, so nothing is written there at start.
- `licenses\` — third-party licenses; `licenses\NOTICE.txt` lists the components.
- `data\` — not in the zip: the program makes it on the first start and keeps the Library, the settings and its log `ozvuchka.log` there (rotated: at most three parts of 1 MB), and nothing anywhere else on the computer.

When the window is closed, the page stops sending its heartbeat and the program ends by itself, about 10 seconds later (it waits that long in case the page is only being reloaded with F5). A page that has not been heard from for two minutes counts as closed too.

## Building a release

GitHub Actions (`.github/workflows/build.yml`) does it on every push: it builds the dev runtime, runs pytest (with the `slow` tests), mypy and ruff, builds the release zip and runs its smoke test (`tools\smoke_test.py`: unpack, start `Озвучка.exe`, get the page, synthesize "Hello." with the real Kokoro, close the page and check that the program ends and wrote only into `data\`). The zip of every run is kept for 14 days among the run's artifacts.

To build it locally (needs internet; the result is `dist\Озвучка\` and `dist\ozvuchka-<version>.zip`):

```bat
tools\build.bat release
runtime\python.exe tools\smoke_test.py dist\ozvuchka-<version>.zip
```

The release mode builds the folder from scratch every time; downloads are cached in `.cache\`. The version is `git describe --tags`, or `-Version 1.0` to name it.

## Releasing a version

1. Make sure the last build of `main` in GitHub Actions is green.
2. Tag the commit and push the tag:

   ```bat
   git tag v1.0
   git push origin v1.0
   ```

3. The tag's build publishes `ozvuchka-1.0.zip` in GitHub Releases, under the tag's name, with notes made from the commits. Edit the notes there if needed.

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
