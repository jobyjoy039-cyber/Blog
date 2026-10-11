"""KittenTTS (github.com/KittenML/KittenTTS, Apache-2.0) running in-process.

A small ONNX model (mini: ~80 MB) that runs in real time on CPU, so ads get a
voice with no GPU and no separate speech server. The model lives in a single
worker process: espeak can terminate its host process on a bad data path, and
isolating it means a crash costs one retry, not the API server.
"""
from __future__ import annotations

import importlib.util
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from ..domain import JobRequest
from .base import VoicePlugin
from .voice import KITTEN_VOICE_NAMES, trim_silence

VOICES = sorted(KITTEN_VOICE_NAMES)
SAMPLE_RATE = 24000

_model = None  # set inside the worker process


def _load(model_name: str) -> None:
    global _model
    from kittentts import KittenTTS

    _model = KittenTTS(model_name)


def _speak(text: str, out_path: str, voice: str, speed: float) -> None:
    import soundfile as sf

    audio = _model.generate(text, voice=voice, speed=speed)
    sf.write(out_path, audio, SAMPLE_RATE)


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
        self._pool: ProcessPoolExecutor | None = None
        self._lock = threading.Lock()

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("kittentts") is None:
            return False, "pip install 'ugc-studio[kitten]'"
        return True, ""

    def _executor(self) -> ProcessPoolExecutor:
        with self._lock:
            if self._pool is None:
                self._pool = ProcessPoolExecutor(
                    max_workers=1,
                    mp_context=multiprocessing.get_context("spawn"),
                    initializer=_load,
                    initargs=(self.model,),
                )
            return self._pool

    def _reset(self) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.shutdown(wait=False, cancel_futures=True)
                self._pool = None

    def synthesize(self, text: str, out_path: Path, request: JobRequest) -> float:
        if request.language not in ("en", "en-us", "en-gb"):
            raise ValueError("KittenTTS speaks English only")  # non-transient: orchestrator moves to the next voice
        voice = request.voice if request.voice in VOICES else self.default_voice
        try:
            self._executor().submit(_speak, text, str(out_path), voice, self.speed).result(timeout=self.timeout)
        except BrokenProcessPool:
            self._reset()  # worker died (e.g. native crash); next attempt starts a fresh one
            raise RuntimeError("KittenTTS worker crashed") from None
        except FutureTimeout:
            self._reset()  # a hung worker would block every later job
            raise RuntimeError(f"KittenTTS timed out after {self.timeout:.0f}s") from None
        return trim_silence(out_path)

    def close(self) -> None:
        self._reset()
