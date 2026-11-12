# Interrupt active Narration synthesis on cancellation

Date: 2026-11-04. Branch: `experiment-2`.

## Context

During stage 4 (#31) acceptance the developer rejected the previous cancellation
contract: removing a Narration but finishing its active piece can block the next one
for minutes on a slow computer. They explicitly requested cancellation of the computation
itself. This authorizes a bounded exception to the UI track's original exclusion of
provider/queue changes; no later UI stages or audio algorithm redesign are included.

## Decision

Core associates the claimed piece with its owning Narration and a fresh `threading.Event`.
Cancelling that Narration removes it, stops its playback as before, and sets only that
call's signal. Cancelling a waiting Narration does not interrupt the active one. A repeated
old cancellation cannot affect the next call, including re-enqueue of the same Narration.

`VoiceProvider.synthesize` accepts an optional per-call `cancel` Event and raises
`SynthesisCancelled` on interruption. The default remains usable for sample generation
and direct synthesis callers. Providers must stop their work when signalled; merely
returning control while continuing the same expensive inference elsewhere is insufficient.

The pinned Kokoro wrapper retains its loaded model/session and unchanged phoneme/audio
pipeline. Its session adapter supplies a distinct ONNX `RunOptions` per native run. A
short-lived monitor checks the cancellation Event every 10 ms and sets `terminate`;
it never calls Core or acquires Core's lock. The documented runtime mechanism terminates
active calls using those options and returns an error status, translated to cancellation:
[ONNX Runtime Python RunOptions](https://onnxruntime.ai/docs/api/python/api_summary.html#onnxruntime.RunOptions).
The monitor is joined before another run starts; no second synthesis/model copy is launched.

Core discards an interrupted result, records no synthesis failure, and excludes it from
Synthesis speed measurement. It also removes a late file if cancellation races an atomic
write. Already completed pieces remain in the Library. The next Narration is claimed by
the same worker after the interrupted call unwinds. HTTP commands and snapshots are unchanged.

## Bounds and consequences

Cancellation is prompt interruption, not a hard real-time deadline or unsafe Python
thread termination. Native inference exits at ONNX Runtime's cancellation checkpoints;
phonemization and WAV conversion are checked before/after their synchronous calls.
Initial shared provider loading is not cancelled when a waiting Narration is removed.
Developer acceptance on the school Celeron and i5 was completed in #24 on 2026-11-12.
Cancellation and re-enqueue behaved correctly, but numerical latency measurements were not
preserved. Do not claim a fixed millisecond guarantee from the fake, development PC or this
acceptance record.

FakeVoiceProvider and the paced preview respect the same Event, so a deliberately
60-second test wait is interruptible. Tests cover active/waiting cancellation, already
completed pieces, repeated/renewed requests, late results, and real native interruption
followed by another Voice on the same loaded provider. Slow provider tests are required.
Build, launcher, Voice catalogue, queue priority, other scheduling, Speed values, audio
joining and Start delay calculation are unchanged.
