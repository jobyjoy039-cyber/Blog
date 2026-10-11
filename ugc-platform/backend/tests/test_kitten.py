import importlib.util

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
    kitten.synthesize("Warm up.", tmp_path / "w.wav", brief_request)
    kitten._proc.kill()  # the way a native espeak abort would end it
    kitten._proc.wait()
    # the dead worker is noticed and replaced on the next request
    assert kitten.synthesize("Back again.", tmp_path / "c.wav", brief_request) > 0.3


def test_worker_dying_mid_request_is_reported(kitten, tmp_path, brief_request, monkeypatch):
    kitten.synthesize("Warm up.", tmp_path / "w.wav", brief_request)
    real_write = kitten._proc.stdin.write

    def write_then_die(data):
        n = real_write(data)
        kitten._proc.kill()
        return n

    monkeypatch.setattr(kitten._proc.stdin, "write", write_then_die)
    with pytest.raises(RuntimeError, match="crashed"):
        kitten.synthesize("Gone.", tmp_path / "x.wav", brief_request)
    assert kitten.synthesize("Recovered.", tmp_path / "y.wav", brief_request) > 0.3


def test_non_english_is_rejected_for_fallback(kitten, tmp_path, brief_request):
    with pytest.raises(ValueError):
        kitten.synthesize("Hola", tmp_path / "d.wav", brief_request.model_copy(update={"language": "es"}))
