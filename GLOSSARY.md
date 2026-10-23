# Simple English TTS

An offline program that reads English texts aloud during English lessons, run by the teacher on school laptops without relying on internet access.

## Language

### Content

**Library**:
The collection of Texts the teacher has saved in the program, together with their Narrations.
_Avoid_: History, recent files, cache

**Text**:
A piece of English writing the teacher has pasted or opened and saved in the Library to be read aloud.
_Avoid_: Document, file, lesson

**Paragraph**:
One non-empty line of a Text; the unit the teacher highlights, repeats, or starts playback from.
_Avoid_: Block, chunk, section

**Skipped paragraph**:
A Paragraph with no English in it (e.g. a Russian task instruction), shown to the teacher but never read aloud.
_Avoid_: Hidden paragraph, comment, ignored line

### Speech

**Voice**:
A named speaker the teacher picks to read a Text (e.g. Alice, George); every Voice comes from exactly one Voice provider.
_Avoid_: Speaker, model, engine

**Voice provider**:
A source of Voices: offline (built into the program, always available) or online (available only while there is internet access).
_Avoid_: Engine, backend, TTS service

**Voice sample**:
A short ready-made clip of a Voice that the teacher can listen to instantly when choosing one.
_Avoid_: Preview, demo, test phrase

**Speed**:
How fast a Voice reads, as a multiple of its normal pace (1.0 = normal, 0.8 = slower for younger pupils).
_Avoid_: Rate, tempo

**Narration**:
The synthesized speech of one Text in one Voice at one Speed, kept in the Library so it can be played again without waiting.
_Avoid_: Recording, audio, cache, voiceover

**Narration queue**:
The Narrations waiting to be synthesized, one at a time, in the order the teacher asked for them.
_Avoid_: Jobs, tasks, backlog

**Start delay**:
How long the teacher must wait after pressing Play before a Narration that is still being synthesized can play through without stopping.
_Avoid_: ETA, loading time, latency
