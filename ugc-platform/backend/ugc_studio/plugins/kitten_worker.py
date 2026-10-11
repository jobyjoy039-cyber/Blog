"""Standalone KittenTTS worker: `python -m ugc_studio.plugins.kitten_worker MODEL`.

Reads one JSON request per line on stdin and answers one JSON line on the
original stdout. Runs as its own program (not a multiprocessing child), so it
works however the API was launched, and a native crash only kills this process.
"""
from __future__ import annotations

import json
import os
import sys


def main() -> None:
    reply = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)  # anything else (Python prints, native espeak output) goes to stderr
    sys.stdout = sys.stderr
    model_name = sys.argv[1]
    try:
        import soundfile as sf
        from kittentts import KittenTTS

        model = KittenTTS(model_name)
    except Exception as e:  # report load failures instead of dying silently
        reply.write(json.dumps({"ready": False, "error": f"{type(e).__name__}: {e}"}) + "\n")
        return
    reply.write(json.dumps({"ready": True}) + "\n")
    for line in sys.stdin:
        try:
            req = json.loads(line)
            audio = model.generate(req["text"], voice=req["voice"], speed=req["speed"])
            sf.write(req["out"], audio, 24000)
            reply.write(json.dumps({"ok": True}) + "\n")
        except Exception as e:
            reply.write(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}) + "\n")


if __name__ == "__main__":
    main()
