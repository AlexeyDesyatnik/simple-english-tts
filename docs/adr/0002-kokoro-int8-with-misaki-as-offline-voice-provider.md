# Kokoro int8 with misaki phonemes as the offline Voice provider

The only offline Voice provider is Kokoro-82M (int8 ONNX, 92 MB) fed with phonemes from misaki (with spaCy part-of-speech tagging), not with kokoro-onnx's default espeak-ng phonemes. This was chosen after benchmarking on the two target laptops (Celeron N4100 and i5-8250U) and listening tests in the `english-speaking-prototype` repo: int8 sounds identical to fp32 while loading much faster on the Celeron, and misaki fixes the homograph and intonation errors espeak produces (e.g. "Emma lives" read as /laɪvz/).

## Considered Options

- **Piper**: much faster (×3.9 real time on the Celeron versus ×0.44), but trained on espeak phonemes, so it keeps the homograph errors, and its British voices sounded worse. It is also GPL-3.0. Rejected despite the speed; the program instead lets the teacher wait for a Narration and keeps it in the Library.
- **Kokoro fp32**: no audible gain, 325 MB, 64 s warm-up on the Celeron.
- **Microsoft Edge "Read Aloud" voices (via `edge-tts`)**: good quality and a child voice (Maisie), but it is an unofficial, token-protected service that has broken before, and school internet may block it. It is reserved for a later, optional online Voice provider, never the default.
- **Windows natural voices, Azure/Google cloud APIs, Pocket TTS, MeloTTS**: too fragile, require a card-backed account, or require PyTorch with unknown speed on the Celeron.
