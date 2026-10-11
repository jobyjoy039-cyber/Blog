import subprocess
import time

import pytest

from ugc_studio.domain import (
    Analysis, Job, JobRequest, JobStatus, Platform, Scene, SceneAudio, Script,
)
from ugc_studio.orchestrator import Orchestrator, StepFailed
from ugc_studio.plugins.base import AnalyzePlugin, Registry
from ugc_studio.plugins.brain_local import LocalAnalyzer, TemplateScriptWriter
from ugc_studio.plugins.ingest import ManualIngest
from ugc_studio.plugins.render_ffmpeg import FFmpegRenderer
from ugc_studio.plugins.voice import ProportionalAligner

from .conftest import FakeRender, FakeVoice, needs_ffmpeg


class FlakyAnalyzer(AnalyzePlugin):
    name = "flaky"
    priority = 1

    def __init__(self):
        self.calls = 0

    def analyze(self, product) -> Analysis:
        self.calls += 1
        raise ConnectionError("model server down")


def make_registry(tmp_path, *extra, render=None):
    reg = Registry()
    for p in (ManualIngest(tmp_path / "uploads"), LocalAnalyzer(), TemplateScriptWriter(),
              FakeVoice(), ProportionalAligner(), render or FakeRender(), *extra):
        reg.register(p)
    return reg


def new_job(req: JobRequest, id_: str = "j1") -> Job:
    now = time.time()
    return Job(id=id_, status=JobStatus.running, request=req, created_at=now, updated_at=now)


def test_pipeline_with_fallback_and_cache(tmp_path, brief_request, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    flaky = FlakyAnalyzer()
    orch = Orchestrator(make_registry(tmp_path, flaky), tmp_path, retries=2)
    job = orch.run(new_job(brief_request))

    assert flaky.calls == 2  # retried, then fell back
    analyze = next(t for t in job.trace if t.step == "analyze")
    assert analyze.plugin == "local" and "flaky" in analyze.fallbacks[0]
    assert job.output and job.progress == 1.0
    assert len(job.script.scenes) >= 3

    job2 = orch.run(new_job(brief_request, "j2"))
    assert next(t for t in job2.trace if t.step == "script").cached


def test_every_plugin_failing_raises(tmp_path, brief_request, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    reg = Registry()
    for p in (ManualIngest(tmp_path / "uploads"), FlakyAnalyzer()):
        reg.register(p)
    with pytest.raises(StepFailed, match="analyze failed"):
        Orchestrator(reg, tmp_path).run(new_job(brief_request))


def test_fit_to_target_drops_supporting_scenes():
    kinds = ["hook", "problem", "agitate", "solution", "proof", "cta"]
    job = new_job(JobRequest(url="https://x.example/p"))
    job.script = Script(framework="PAS", title="t", scenes=[Scene(kind=k, voice=k) for k in kinds])
    audio = [SceneAudio(path=f"{k}.wav", duration=6.0) for k in kinds]
    Orchestrator._fit_to_target(job, audio, target=20)
    assert [s.kind for s in job.script.scenes] == ["hook", "solution", "proof", "cta"]
    assert len(audio) == 4


@needs_ffmpeg
def test_real_ffmpeg_render(tmp_path, brief_request):
    req = brief_request.model_copy(update={"platform": Platform.facebook, "resolution": "720p"})
    req.script_override = Script(framework="PAS", title="t", scenes=[
        Scene(kind="hook", voice="Okay this actually works.", on_screen="Wait for it"),
        Scene(kind="cta", voice="Tap the link.", on_screen="Link below"),
    ])
    reg = make_registry(tmp_path, render=FFmpegRenderer())
    job = Orchestrator(reg, tmp_path).run(new_job(req))
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "csv=p=0", job.output.video],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "video,720,900" in out and "audio" in out  # facebook 4:5 at 720p
    assert 2 < job.output.duration < 8
    assert (tmp_path / "jobs" / "j1" / "render" / "captions.ass").read_text().count("Dialogue:") > 4


@needs_ffmpeg
def test_studio_render_with_music_and_sfx(tmp_path, brief_request):
    from ugc_studio.plugins.music import ProceduralMusic
    from ugc_studio.plugins.render_studio import StudioRenderer

    req = brief_request.model_copy(update={"platform": Platform.tiktok, "resolution": "720p", "music": "chill"})
    req.script_override = Script(framework="PAS", title="t", scenes=[
        Scene(kind="hook", voice="Okay this actually works.", on_screen="Wait for it"),
        Scene(kind="proof", voice="Two seconds, every time."),
        Scene(kind="cta", voice="Tap the link."),
    ])
    reg = make_registry(tmp_path, ProceduralMusic(), render=StudioRenderer())
    job = Orchestrator(reg, tmp_path).run(new_job(req))
    assert next(t for t in job.trace if t.step == "render").plugin == "studio"
    assert any(t.step == "music" for t in job.trace)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,channels", "-of", "csv=p=0", job.output.video],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "video,720,1280" in probe and "audio,2" in probe
    loud = subprocess.run(["ffmpeg", "-i", job.output.video, "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    integrated = float(loud.rsplit("I:", 1)[1].split("LUFS")[0])
    assert -15.5 < integrated < -12.5  # mastered to about -14 LUFS
