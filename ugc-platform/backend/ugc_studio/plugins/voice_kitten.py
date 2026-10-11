"""KittenTTS (github.com/KittenML/KittenTTS, Apache-2.0) as the built-in voice.

A small ONNX model (mini: ~80 MB) that runs in real time on CPU, so ads get a
voice with no GPU and no separate speech server. The model runs in a separate
worker program (kitten_worker.py) that stays loaded between requests: espeak
can terminate its host process, and isolating it means a crash costs one
retry, not the API server.
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from ..domain import JobRequest
from .base import VoicePlugin
from .voice import KITTEN_VOICE_NAMES, trim_silence

VOICES = sorted(KITTEN_VOICE_NAMES)


class KittenVoice(VoicePlugin):
    name = "kittentts"
    priority = 5  # local, commercial-friendly, no extra server: first choice
    license = "Apache-2.0 (code and weights)"
    commercial_ok = True
    description = "KittenTTS on CPU, 8 English voices (Bella, Jasper, Luna, Bruno, Rosie, Hugo, Kiki, Leo)."

    def __init__(self, model: str = "KittenML/kitten-tts-mini-0.8", voice: str = "Jasper",
                 speed: float = 1.2, timeout: float = 180):
        self.model = model
        self.default_voice = voice if voice in VOICES else "Jasper"
        self.speed = speed
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._replies: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("kittentts") is None:
            return False, "pip install 'ugc-studio[kitten]'"
        return True, ""

    def _read(self, timeout: float) -> dict:
        try:
            line = self._replies.get(timeout=timeout)
        except queue.Empty:
            self._stop()
            raise RuntimeError(f"KittenTTS timed out after {timeout:.0f}s") from None
        if line is None:  # stdout closed: the worker died
            self._stop()
            raise RuntimeError("KittenTTS worker crashed")
        return json.loads(line)

    def _start(self) -> None:
        # Make the package importable in the worker however the server was installed or launched.
        pkg_root = str(Path(__file__).resolve().parents[2])
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [pkg_root, os.environ.get("PYTHONPATH")]))}
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "ugc_studio.plugins.kitten_worker", self.model],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env,
        )
        self._replies = queue.Queue()
        proc, replies = self._proc, self._replies

        def pump() -> None:  # reader thread so every wait can time out
            for line in proc.stdout:
                replies.put(line)
            replies.put(None)

        threading.Thread(target=pump, daemon=True).start()
        hello = self._read(self.timeout)  # first start may download the model
        if not hello.get("ready"):
            self._stop()
            raise RuntimeError(f"KittenTTS failed to load: {hello.get('error')}")

    def _stop(self) -> None:
        if self._proc is not None:
            if self._proc.poll() is None:
                self._proc.kill()
            self._proc = None

    def synthesize(self, text: str, out_path: Path, request: JobRequest) -> float:
        if request.language not in ("en", "en-us", "en-gb"):
            raise ValueError("KittenTTS speaks English only")  # non-transient: orchestrator moves to the next voice
        voice = request.voice if request.voice in VOICES else self.default_voice
        with self._lock:  # one model, one request at a time
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            try:
                self._proc.stdin.write(json.dumps({"text": text, "out": str(out_path), "voice": voice, "speed": self.speed}) + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError):
                self._stop()
                raise RuntimeError("KittenTTS worker crashed") from None
            reply = self._read(self.timeout)
        if not reply.get("ok"):
            raise RuntimeError(f"KittenTTS: {reply.get('error')}")
        return trim_silence(out_path)

    def close(self) -> None:
        with self._lock:
            self._stop()
