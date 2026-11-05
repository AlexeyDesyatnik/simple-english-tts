# Code review findings — 2026-11-05

This is a handoff for planning fixes, not an implementation plan. The findings below
were inferred from reading the current code; the individual failure scenarios were
not reproduced separately. Revalidate them against the current code and distinguish
confirmed behavior from assumptions when planning. Priorities describe the review's
assessment, not an agreed implementation order.

## Findings

### 1. Audio can be deleted when the Library cannot be saved — high

[`Core.delete_text`](../ozvuchka/core.py#L195) changes the in-memory Library, calls
`_save_library()` without checking its result, and then removes unreferenced audio
pieces. [`_save_library`](../ozvuchka/core.py#L526) returns `False` on a write error,
while [`_remove_unreferenced_pieces`](../ozvuchka/core.py#L625) can delete files.

If a Library write fails but audio deletion succeeds, the old `library.json` can
still reference the deleted Text after a restart, while its Narration pieces are
gone. A broader case is an unreadable Library: its contents are not loaded, but its
audio files are still discovered. Creating and then deleting another Text can cause
the old audio files to be treated as unreferenced. Check this scenario against the
intended unreadable-Library behavior before choosing a fix.

### 2. Local command endpoint does not validate request origin — high, conditional

[`do_POST`](../ozvuchka/server.py#L71) accepts JSON commands without checking
`Origin`, a request token, or `Content-Type`. The default port is fixed in
[`__main__.py`](../ozvuchka/__main__.py#L37). If a browser permits a third-party
page to send a request to localhost, that page could issue a command that changes
data, such as `set_text`. Cross-origin restrictions on reading a response alone do
not necessarily prevent a request from being sent.

The browser scenario was **not tested** in the Edge version used by this project;
browser and local-network restrictions may affect exploitability. Assess the
actual threat and deployment environment before choosing a mitigation.

### 3. A Library with invalid field types can prevent snapshots — medium

[`LibraryFiles.texts`](../ozvuchka/library.py#L30) validates the outer object and
format version but does not validate each field's type. For example,
`{"version": 1, "texts": [{"id": "1", "content": 42}]}` passes loading but
can raise an exception when [`Core.snapshot`](../ozvuchka/core.py#L451) derives a
title with `_title`. Instead of reporting an unreadable Library, the state request
fails. The existing [damaged-Library test](../tests/test_core.py#L935) covers
invalid JSON and an unknown version, not valid JSON with incorrect field types.

### 4. A provider returning MP3 can terminate the synthesis worker — medium

The [`Audio` type](../ozvuchka/audio.py#L13) and provider interface do not restrict
the audio format to WAV, but [`LibraryFiles.save_piece`](../ozvuchka/library.py#L58)
asserts that the format is WAV. The call in the [synthesis worker](../ozvuchka/core.py#L771)
only catches `OSError`, so an MP3 result would raise `AssertionError` and end the
worker. This concerns a prospective provider; the current Kokoro provider returns
WAV. Consider the project's stated goal that a new Voice provider requires one new
module when deciding whether to expand the contract or explicitly constrain it.

### 5. Queue titles can differ from Library titles — low

The [queue snapshot](../ozvuchka/core.py#L705) derives the title from the Text's
content instead of using its user-selected Library title. In addition, the
[queue renderer](../ozvuchka/web/app.js#L575) rebuilds rows only when queue IDs
change, so an existing row's title is not refreshed merely because the title
changes. These are separate contributing behaviors to verify when planning a fix.

### 6. Cancellation test timeout does not bound the test — low

The [real-Kokoro cancellation test](../tests/test_voice_provider_contract.py#L112)
uses `future.result(timeout=5)` inside a `ThreadPoolExecutor` context. If the native
call hangs, exiting the context still waits for its worker, so the test can hang
until the [CI job timeout](../.github/workflows/build.yml#L14). The test exercises
meaningful behavior; its timeout mechanism is the concern. The hanging case was
not separately reproduced.

## Review scope and checks

- The review found no convincingly demonstrated dead code or tests that check
  nothing. Absence of a finding is not proof that none exists.
- The ordinary test suite passed: **140 passed, 8 slow tests deselected**. The
  `mypy` and `ruff` checks also passed. The slow suite, real-browser attack scenario,
  and individual failure reproductions were not run as part of this review.
- The first test attempt could not create its default temporary directory in the
  sandbox. A second run using a separate temporary directory outside the repository
  passed. The review made no changes to project files.
- Follow [AGENTS.md](../AGENTS.md), [coding standards](../CODING_STANDARDS.md), the
  [domain guidance](agents/domain.md), and [manual checks](manual-checks.md) while
  planning. Keep proposed implementation and acceptance proportional to the
  application; do not add recovery machinery without a concrete need.
