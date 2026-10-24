"""Synthesizes a Voice sample for every Kokoro Voice into <model folder>\\samples\\<voice>.wav.

The samples ship in the program folder, so the teacher hears them at once even on the Celeron.
Samples already made are kept; delete the samples folder to make them again.
Usage: python make_voice_samples.py <Kokoro model folder>
"""

import sys
from pathlib import Path

from ozvuchka.kokoro import VOICES, KokoroProvider
from ozvuchka.library import write_atomically

# 5 to 7 seconds at Speed 1.0 for every Voice
PHRASE = "Hello! My name is {name}. Today we are going to read an English story together, one sentence at a time."


def main() -> int:
    model_dir = Path(sys.argv[1])
    samples = model_dir / "samples"
    samples.mkdir(exist_ok=True)
    missing = [(voice, name) for voice, name, _ in VOICES if not (samples / f"{voice}.wav").exists()]
    if not missing:
        print(f"  all {len(VOICES)} samples present")
        return 0
    provider = KokoroProvider(model_dir)
    provider.load()
    for voice, name in missing:
        audio = provider.synthesize(PHRASE.format(name=name), voice, 1.0)
        if not 5.0 <= audio.duration <= 7.0:
            print(f"  {voice}: the sample lasts {audio.duration:.1f} s, not 5 to 7 s; change the phrase")
            return 1
        write_atomically(samples / f"{voice}.wav", audio.data)
        print(f"  {voice}.wav: {audio.duration:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
