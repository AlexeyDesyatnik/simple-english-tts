"""Starts the program: runtime\\python.exe -m ozvuchka [--port N]"""

import argparse
import platform
import time
from pathlib import Path

from ozvuchka.core import Core
from ozvuchka.kokoro import DEFAULT_VOICE, KokoroProvider
from ozvuchka.server import make_server
from ozvuchka.voices import VoiceRegistry

ROOT = Path(__file__).resolve().parent.parent  # the program folder (ADR-0001)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ozvuchka")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    kokoro = KokoroProvider(ROOT / "models" / "kokoro")
    print("Loading Kokoro…", flush=True)
    kokoro.load()
    core = Core(
        VoiceRegistry([kokoro]),
        DEFAULT_VOICE,
        clock=time.monotonic,
        data_dir=ROOT / "data",
        computer=platform.node(),  # the Synthesis speed is remembered for each computer
    )
    server = make_server(core, args.port)
    print(f"Ozvuchka: http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        core.close()


if __name__ == "__main__":
    main()
