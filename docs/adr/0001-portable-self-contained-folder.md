# Portable, self-contained program folder

The program is expected to run from a flash drive on school laptops it has never seen, started by the teacher with a double click, with no installation, no setup scripts and no internet. So everything ships pre-built in one folder (embeddable Python, packages, Kokoro model, voices, spaCy model) with a single `.exe` launcher at the top, and all user data (the Library and its Narrations) is stored inside that same folder, never in `%APPDATA%`, the registry, or anywhere else on the computer. The folder is produced by a developer-only build script that runs in GitHub Actions (published as a release zip) and can also be run locally; nothing from the build tooling ends up in the shipped folder.

## Consequences

- Drive letters change between computers, so nothing may store absolute paths (this also rules out `.lnk` shortcuts as the launcher).
- Data is written to a flash drive: writes should be few and crash-tolerant (a pulled-out drive must not corrupt the Library).
- Model and package loading from a slow flash drive affects startup time; it must show progress rather than look frozen.
- Program-managed Library data, including WAV Narration pieces, remains exclusively under `data` and uses atomic writes. An explicitly requested browser download is user-owned output, not Library data: the browser may write it to its configured download folder or ask for a destination. MP3 export creates no intermediate WAV or persistent MP3 in the program folder and does not change Library paths or schema.
