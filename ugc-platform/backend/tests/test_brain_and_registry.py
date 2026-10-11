import pytest

from ugc_studio.domain import Framework, JobRequest, ManualBrief
from ugc_studio.plugins.base import Capability, NoPluginAvailable, Registry
from ugc_studio.plugins.brain_claude import ClaudeAnalyzer
from ugc_studio.plugins.brain_local import LocalAnalyzer, TemplateScriptWriter, claim_warnings, short_name
from ugc_studio.plugins.voice import ProportionalAligner, SilentVoice


def test_local_analysis_uses_real_data(product):
    a = LocalAnalyzer().analyze(product)
    assert "4.6 stars from 1,843 reviews" in a.proof_points
    assert a.pain_points[0].startswith("my old suction mount kept falling")
    assert short_name(product) == "GripMount"


@pytest.mark.parametrize("framework", list(Framework))
def test_every_framework_writes_hook_to_cta(product, framework):
    req = JobRequest(brief=ManualBrief(title="x"), framework=framework, target_seconds=30)
    script = TemplateScriptWriter().write(product, LocalAnalyzer().analyze(product), req)
    assert script.scenes[-1].kind == "cta"
    assert "$28.00" in script.scenes[-1].voice
    assert "#ad" in script.hashtags
    assert all(s.voice and "{" not in s.voice for s in script.scenes)


def test_short_target_trims_supporting_scenes(product):
    req = JobRequest(brief=ManualBrief(title="x"), framework=Framework.pas, target_seconds=8)
    kinds = [s.kind for s in TemplateScriptWriter().write(product, LocalAnalyzer().analyze(product), req).scenes]
    assert {"hook", "solution", "proof", "cta"} <= set(kinds)
    assert "agitate" not in kinds


def test_claim_warnings():
    w = claim_warnings("Clinically proven, 100% guaranteed and the best ever")
    assert len(w) == 4


def test_aligner_covers_clip():
    words = ProportionalAligner().align("one two three", None, 2.0)
    assert [w.text for w in words] == ["one", "two", "three"]
    assert words[0].start > 0 and words[-1].end <= 2.0
    assert all(a.end <= b.start + 1e-6 for a, b in zip(words, words[1:]))


def test_registry_order_preference_and_availability(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")
    reg = Registry()
    reg.register(LocalAnalyzer())
    reg.register(ClaudeAnalyzer("claude-opus-5-5"))
    assert [p.name for p in reg.chain(Capability.analyze)] == ["local"]  # claude unavailable, skipped

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    assert [p.name for p in reg.chain(Capability.analyze)] == ["claude", "local"]
    reg.set_preferred(Capability.analyze, "local")
    assert [p.name for p in reg.chain(Capability.analyze)] == ["local", "claude"]

    with pytest.raises(KeyError):
        reg.set_preferred(Capability.analyze, "nope")
    with pytest.raises(NoPluginAvailable):
        reg.chain(Capability.render)


def test_silent_voice_duration(tmp_path, brief_request):
    d = SilentVoice().synthesize("one two three four five six", tmp_path / "s.wav", brief_request)
    assert (tmp_path / "s.wav").stat().st_size > 1000
    assert 1.2 <= d < 4
