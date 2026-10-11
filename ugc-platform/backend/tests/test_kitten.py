import importlib.util
import os
from concurrent.futures.process import BrokenProcessPool

import pytest

from ugc_studio.plugins.voice import wav_duration
from ugc_studio.plugins.voice_kitten import KittenVoice

pytestmark = pytest.mark.skipif(importlib.util.find_spec("kittentts") is None, reason="kittentts not installed")


@pytest.fixture(scope="module")
def kitten():
    plugin = KittenVoice()
    yield plugin
    plugin.close()


def test_speaks_with_chosen_voice(kitten, tmp_path, brief_request):
    out = tmp_path / "a.wav"
    req = brief_request.model_copy(update={"voice": "Bella"})
    duration = kitten.synthesize("This mount snaps on in two seconds.", out, req)
    assert 1.0 < duration < 6.0
    assert abs(wav_duration(out) - duration) < 0.01


def test_recovers_after_worker_crash(kitten, tmp_path, brief_request):
    kitten._executor().submit(os._exit, 1)  # kill the worker the way a native espeak abort would
    with pytest.raises((RuntimeError, BrokenProcessPool)):
        for _ in range(3):  # the pool notices the dead worker on the next submit
            kitten.synthesize("Still there?", tmp_path / "b.wav", brief_request)
    assert kitten.synthesize("Back again.", tmp_path / "c.wav", brief_request) > 0.3


def test_non_english_is_rejected_for_fallback(kitten, tmp_path, brief_request):
    with pytest.raises(ValueError):
        kitten.synthesize("Hola", tmp_path / "d.wav", brief_request.model_copy(update={"language": "es"}))
