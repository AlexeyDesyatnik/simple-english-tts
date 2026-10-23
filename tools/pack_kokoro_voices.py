"""Packs Kokoro voices (*.bin from onnx-community) into one voices.npz for kokoro-onnx.

Each .bin is a float32 array 510 x 1 x 256 (a voice style per phrase length).
Usage: python pack_kokoro_voices.py <folder with .bin> <output .npz>
"""

import sys
from pathlib import Path
from typing import Any

import numpy as np


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    voices: dict[str, Any] = {}  # Any: numpy's stubs reject **arrays next to savez's own keyword arguments
    for f in sorted(src.glob("*.bin")):
        arr = np.fromfile(f, dtype=np.float32)
        if arr.size % 256:
            print(f"skipping {f.name}: unexpected size")
            return 1
        voices[f.stem] = arr.reshape(-1, 1, 256)
    if not voices:
        print("no voices found")
        return 1
    np.savez(dst, **voices)
    print(f"  {dst.name}: {', '.join(voices)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
