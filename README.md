# Озвучка (Simple English TTS)

An offline program that reads English texts aloud during English lessons. See `GLOSSARY.md` for the terms and `docs/adr/` for the decisions.

## Development

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

- `Озвучка.exe` — the launcher. It starts `runtime\pythonw.exe -m ozvuchka --app` from its own folder, with no console window; the program opens its page `http://127.0.0.1:8770` in the default browser at once and loads Kokoro in the background (ADR-0003): a ready Narration plays meanwhile, a new one waits for the Voices. Starting `Озвучка.exe` again opens the page of the program already running instead of starting a second one. If the program stops with an error, the launcher says so in a message box.
- `runtime\`, `ozvuchka\`, `models\` — Python with the packages, the program, the Kokoro model and the Voice samples. Python code is compiled ahead, so nothing is written there at start.
- `licenses\` — third-party licenses; `licenses\NOTICE.txt` lists the components.
- `data\` — not in the zip: the program makes it on the first start and keeps the Library, the settings and its log `ozvuchka.log` there (rotated: at most three parts of 1 MB), and nothing anywhere else on the computer.

When the page's window or tab is closed, the page stops sending its heartbeat and the program ends by itself, about 10 seconds later (it waits that long in case the page is only being reloaded with F5). A page that has not been heard from for two minutes counts as closed too.

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
