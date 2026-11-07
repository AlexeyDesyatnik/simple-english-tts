# Portable, self-contained program folders

The program is expected to run from a flash drive on school computers it has never seen, started by the teacher without installation, setup scripts or internet. Each supported platform has its own pre-built `Озвучка/` folder containing the application, Python runtime, packages, Kokoro model, Voices and spaCy model. Windows uses the embeddable CPython runtime and a single `.exe` launcher; Linux x86-64 uses a baseline standalone CPython runtime, an executable `Озвучка.sh` and a `.tar.gz` that preserves its permission. All program-managed data (the Library and its Narrations) is stored inside that same folder, never in a user profile, registry or platform data directory. Developer-only build scripts produce the folders; no build tooling is shipped.

## Consequences

- Drive letters and mount points change between computers, so nothing may store absolute build-time paths. Launchers locate the runtime relative to their own folder (this also rules out Windows `.lnk` shortcuts).
- Data is written to a flash drive: writes should be few and crash-tolerant (a pulled-out drive must not corrupt the Library).
- Model and package loading from a slow flash drive affects startup time; it must show progress rather than look frozen.
- Program-managed Library data, including WAV Narration pieces, remains exclusively under `data` and uses atomic writes. An explicitly requested browser download is user-owned output, not Library data: the browser may write it to its configured download folder or ask for a destination. MP3 export creates no intermediate WAV or persistent MP3 in the program folder and does not change Library paths or schema.
- Windows and Linux ship the license texts and notices from their actual runtimes and native wheels. Linux omits the Visual C++ runtime and .NET launcher notices and includes standalone CPython's bundled-library notices and Linux-specific bundled libraries such as NumPy's OpenBLAS/GCC runtime components.
- The Linux archive needs a normally executable filesystem; a `noexec` mount is not supported. Its default-browser and diagnostic behavior differs intentionally from the Windows Edge window and message boxes (ADR-0003).
