# MP3 export specification

## Status and purpose

Proposed on 2026-11-06 against release tag `v0.4.1` (commit
`4dde53112bc5c48a081259c1222b2a9c1c580eb7`). This is the implementation contract for
adding MP3 export without changing synthesis, playback, or the Library format. It is
intended to be sufficient to resume the work in a new session without the original chat.

Project rules and terminology remain in `AGENTS.md`, `CODING_STANDARDS.md`, `GLOSSARY.md`,
`docs/development.md`, and `docs/ui-design-spec.md`. Teacher-facing wording is Russian;
code and project documentation are English.

## Goal

The teacher can download one fully prepared Narration of the current Text, using the
currently selected Voice and Speed, as an MP3 file that can be played outside the program.

The exported speech must follow the existing playback order and audible paragraph
spacing. Export uses audio already in the Library; it neither synthesizes missing audio
nor changes the saved Narration.

## Scope

The first version includes:

- one secondary `Скачать MP3` action in the preparation workspace;
- export of the current Text with the selected Voice and Speed;
- a complete, ready Narration only;
- on-demand MP3 encoding from the saved WAV pieces;
- a standard browser download;
- a useful filename derived from the Text title, Voice, and Speed;
- fixed mono MP3 output at 128 kbit/s;
- automated Core/HTTP coverage, browser acceptance, release packaging, and classroom
  hardware acceptance.

The first version excludes:

- exporting an incomplete Narration or implicitly enqueueing synthesis;
- exporting a non-current Text or a non-selected Voice/Speed from Library row menus;
- batch export and an export queue;
- bitrate, sample-rate, metadata, or destination settings in the application;
- persistent MP3 copies in the Library;
- changes to Voice providers, synthesis, the Narration queue, playback scheduling, WAV
  storage, or the Library JSON schema;
- a native Windows save dialog or a new UI framework.

These exclusions are deliberate scope boundaries, not missing acceptance criteria.

## Current architecture relevant to export

- Kokoro returns mono 16-bit WAV at 24 kHz through `wav_from_samples` in
  `ozvuchka/audio.py` and `ozvuchka/kokoro.py`.
- `LibraryFiles` stores each synthesis piece as `<audio id>.wav` under
  `data/narrations`; `Core.audio()` reads either a saved piece or an unsaved in-memory
  piece after a persistence failure.
- A Paragraph can contain several synthesis pieces. A Skipped paragraph has no pieces.
- The browser player concatenates pieces within a Paragraph without an added pause,
  applies a 0.005-second fade at piece edges, and inserts 0.7 seconds between readable
  Paragraphs. These values currently live in `ozvuchka/web/app.js`.
- The page is a view, Core owns application decisions, and the HTTP server only
  translates requests and responses. The server uses `ThreadingHTTPServer` on loopback.
- The existing `Audio` contract is deliberately WAV-only. MP3 export must not broaden
  the Voice provider or stored-Narration contract.
- There is currently no MP3 encoder dependency. Production packages must install from
  pinned wheels only.

## User experience

### Placement and availability

Put `Скачать MP3` beside `Подготовить озвучку` in the preparation transport, after the
existing preparation action. Keep `Воспроизвести` as the only filled primary action.
Do not show the export action in Playback mode or add it to Library rows.

The action is unavailable when there is no saved current Text, no readable Paragraph,
or the selected Narration is not completely ready. Expose the reason as visible,
accessible text such as `Сначала подготовьте озвучку целиком`; do not rely on a tooltip
alone. Existing preparation progress remains the source of readiness information.

A ready Narration remains exportable while Voice providers are loading or unavailable,
because export does not call a provider.

### Activation and feedback

On activation:

1. Flush the latest editor changes through the existing `saveTypedText()` transition.
   Do not export an older saved revision after a failed save.
2. Use the Text ID, Voice key, and Speed acknowledged by the refreshed snapshot.
3. Disable the action and show `Создаю MP3…` while the request is running. Keep polling
   and the rest of the page usable; do not display invented percentage progress.
4. Start a browser download when the response succeeds. Do not claim that the file was
   written to disk: the browser owns the destination and final download result.
5. On failure, leave a readable Russian error in the existing actionable-error area and
   allow retry with the same button.

The transient export busy state belongs to the page and need not survive F5. A repeated
click while the same page is exporting must not start a second request. No multi-window
export coordination is required.

### Downloaded file

Use a filename such as `Название текста — Alice — 1×.mp3`. Remove or replace characters
not valid in Windows filenames, control length, and provide a fallback for an empty or
excessively long title. The HTTP response must carry a standards-compliant UTF-8
`Content-Disposition` filename and an ASCII fallback.

The browser downloads the file to its configured download folder or asks for a location,
according to browser settings. Deleting the Text or Narration later does not delete an
already downloaded MP3.

## Audio semantics

For the requested Text/Voice/Speed revision:

1. Parse the saved Text with the existing `ozvuchka/text.py` rules.
2. Visit Paragraphs in reading order and omit Skipped paragraphs.
3. Read every synthesis piece through Core's existing audio seam, including pieces held
   only in memory after a Library write failure.
4. Concatenate pieces within each readable Paragraph with the existing 0.005-second edge
   fades and no additional silence.
5. Insert exactly 0.7 seconds of digital silence between adjacent readable Paragraphs.
   Do not add this pause before the first or after the last Paragraph.
6. Encode the assembled mono PCM stream as MP3 at 128 kbit/s, preserving the source
   24 kHz sample rate when supported by the selected encoder.

Move the pause and fade values to one Python-owned definition exposed to the page in the
snapshot, so browser playback and export cannot silently acquire different values. This
is a sharing change only; audible playback behavior and scheduling must stay unchanged.

Prefer streaming PCM chunks into the encoder rather than constructing one large float
array. Do not compare exact encoded bytes in tests: encoder metadata and valid padding
are implementation details.

## Backend design

### Encoder module

Add an internal `ozvuchka/export.py` responsible only for WAV/PCM assembly, silence,
fades, MP3 encoding, and filename-safe formatting where appropriate. It must not own
Core state or read arbitrary paths supplied by HTTP.

The preferred encoder is `lameenc`, using a pinned CPython 3.12 Windows x64 wheel. Its
use is a dependency gate, not an assumption: stage 1 must verify the wheel, mono 24 kHz
encoding, offline packaging, licenses, and basic runtime behavior. If it fails that gate,
stop and revise this specification before selecting another encoder. Do not silently add
FFmpeg, pydub, a decoder stack, or a system installation requirement.

Keep `Audio(format="wav")` unchanged. If a return value is needed, define a separate
immutable export result containing MP3 bytes and filename rather than treating export as
provider Audio.

### Core operation

Add a Core operation equivalent to:

```python
export_narration(text_id: str, voice_key: str, speed: float) -> ExportResult
```

Its responsibilities are to:

- validate the Text ID, Voice key, and allowed Speed;
- resolve the saved Text revision and its ordered audio IDs;
- reject an empty or incomplete Narration with a Russian user-facing error;
- snapshot the title and audio IDs under the Core lock;
- read audio and encode outside the Core lock;
- return MP3 bytes and the download filename without changing application state.

A deletion or read failure racing an export may fail that export with a retryable
Russian error; it must not crash the server, resurrect deleted audio, or expose a partial
MP3. Export does not lock out synthesis or playback while encoding.

Do not add export progress to the Core snapshot or start a second long-running background
worker for this version.

### HTTP response

Add a loopback-protected GET route equivalent to:

```text
/api/export/<text_id>?voice=kokoro%3Abf_alice&speed=1.0
```

Core, not the handler, validates the identifiers and decides whether export is allowed.
The handler only parses and translates the request and returned export result.

Success response:

- status 200;
- `Content-Type: audio/mpeg`;
- `Content-Disposition: attachment` with ASCII fallback and UTF-8 filename;
- `Cache-Control: no-store`;
- the MP3 bytes as the body, not Base64 JSON.

Expected request/state failures return a JSON Russian error with an appropriate 4xx
status. Unexpected encoding/read failures return a readable JSON error rather than an
empty successful download. Preserve the existing Host policy and never accept a file
path from the client.

The page uses `fetch`, checks the response, creates a temporary Blob URL, clicks a
temporary download link, and revokes the URL. A failed response must not replace or
navigate away from the application page.

## Storage, portability, and licensing

Do not write intermediate WAV or MP3 files into the program folder. Export produces an
in-memory response and adds no files to `data/narrations`, no Library size accounting,
and no deletion/migration behavior.

Library-owned data remains exclusively under `data`. An explicitly requested browser
download is a user-owned output and may be written to the browser-selected destination.
Update ADR-0001 wording to distinguish those two categories without weakening atomic
Library writes or portable paths.

Pin direct and transitive dependencies as required by `CODING_STANDARDS.md`. Ship the
encoder and all required license/notice texts in the offline release. Confirm that the
release works without a compiler, system LAME/FFmpeg, network access, or development
packages.

## Verification

### Stage-local automated checks

Write behavior tests before implementation and check that they fail first. Use public
Core and HTTP seams, FakeVoiceProvider, FakeClock, and temporary data folders.

Cover at least:

- incomplete, empty, unknown, and disallowed export requests are rejected without state
  changes or provider calls;
- the requested saved Text revision, Voice, and Speed determine the exported audio IDs;
- ready in-memory pieces can be exported after a simulated Library persistence failure;
- a deleted/missing piece produces a controlled error;
- HTTP success has MP3 content, attachment disposition, UTF-8 filename, and no-store;
- malformed requests and foreign Hosts cannot export or cause side effects;
- playback pause/fade values remain unchanged after sharing their definitions;
- ordinary synthesis, playback, and deletion tests remain green.

Run `runtime\python.exe -m pytest`, `runtime\python.exe -m mypy`, and
`runtime\python.exe -m ruff check` for every implementation stage. Run slow tests after
build or Kokoro-related changes as required by the project rules.

### Browser acceptance

Use the real application with an isolated, disposable Library. Include a Text with two
English Paragraphs, one Russian-only Skipped paragraph, and a Paragraph long enough to
contain multiple synthesis pieces where practical.

Check that:

- the action explains and enforces full readiness without enqueueing synthesis;
- the latest edits are saved before export and a failed save blocks export;
- the busy state prevents duplicate clicks without freezing polling or navigation;
- the downloaded file has the expected filename and opens in an ordinary media player;
- Voice, Speed, Paragraph order, omitted Russian instruction, piece joins, and 0.7-second
  Paragraph pauses match playback;
- no MP3/intermediate files appear in `data/narrations`;
- a failed request remains readable and can be retried;
- F5 preserves the underlying Text/Narration state;
- 1280x720, 390x844, and 200% zoom retain visible, unclipped controls and keyboard focus;
- export is not offered in Playback mode.

### Release and hardware acceptance

Extend the release smoke test to synthesize a short real Narration, export it, and check
a plausible non-empty MPEG response from the unpacked offline release. Keep the existing
check that the program writes only to `data` internally.

On the school Celeron and i5, using a release archive and disposable Library, prepare and
export a short multi-Paragraph Narration. Confirm responsive preparation/playback during
export, successful browser download, correct audible speech and pauses in an external
player, and no encoder startup/runtime error. Add the hardware-only check to
`docs/manual-checks.md` in the implementation commit that creates the need.

## Documentation updates

As the corresponding stages land:

- add the MP3-export domain term if needed by `GLOSSARY.md`;
- update `docs/ui-design-spec.md`, whose current exclusions otherwise reject export;
- document the dependency and unchanged WAV provider contract in `docs/development.md`;
- distinguish managed Library data from explicit downloads in ADR-0001;
- add teacher-facing download instructions and refresh the README screenshot when the
  visible action ships;
- update third-party notices and the release smoke test;
- record only checks actually performed, leaving hardware acceptance explicitly open
  until the developer completes it.

## Implementation stages and issues

1. **Validate the MP3 encoder dependency.** Gate `lameenc` on wheel availability,
   CPython 3.12 x64 compatibility, mono 24 kHz/128 kbit/s encoding, licenses, offline
   packaging, and a small runtime sample. Record evidence; do not build the application
   feature in this stage. Issue: [#45](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/45).
2. **Implement Core and HTTP export.** Add shared playback timing definitions, audio
   assembly/encoding, the Core operation, the download endpoint, and public-seam behavior
   tests. Depends on stage 1. Issue: [#46](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/46).
3. **Add the preparation-page download action.** Implement save-first behavior, readiness,
   busy/error states, Blob download, accessibility, responsive layout, and real-browser
   acceptance. Depends on stage 2. Issue: [#47](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/47).
4. **Package, document, and accept the release.** Finish dependency/license packaging,
   release smoke coverage, project/teacher documentation, and school-laptop acceptance.
   Depends on stages 1-3. Issue: [#48](https://github.com/AlexeyDesyatnik/simple-english-tts/issues/48).

No stage authorizes changing the excluded scope without revising this specification and
the relevant issue first.
