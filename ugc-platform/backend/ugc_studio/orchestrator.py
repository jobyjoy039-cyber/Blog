"""Master orchestrator: runs a job through ingest -> analyze -> script -> voice
-> align -> render. Each step walks its capability's plugin chain, retrying
and falling back to the next plugin; results are cached by content hash so a
re-run (or a retry after a crash) skips work that already succeeded.
"""
from __future__ import annotations

import asyncio
import hashlib
import zlib
import json
import logging
import time
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel

from . import timeline
from .domain import (
    Analysis, Job, ProductInfo, RenderInput, RenderOutput, SceneAudio, Script, StepTrace,
)
from .plugins.base import Capability, IngestPlugin, NoPluginAvailable, Plugin, Registry
from .plugins.brain_local import DROPPABLE
from .plugins.render_ffmpeg import END_HOLD, SCENE_PAD

log = logging.getLogger("ugc.orchestrator")
T = TypeVar("T")

# progress fraction reached when each step finishes
STEP_PROGRESS = {"ingest": 0.1, "analyze": 0.25, "script": 0.4, "voice": 0.7, "render": 1.0}


class StepFailed(RuntimeError):
    pass


class Cache:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts) -> str:
        blob = json.dumps(parts, sort_keys=True, default=lambda o: o.model_dump(mode="json") if isinstance(o, BaseModel) else str(o))
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def get(self, key: str, model: type[BaseModel]):
        p = self.root / f"{key}.json"
        if p.exists():
            try:
                return model.model_validate_json(p.read_text())
            except ValueError:
                p.unlink(missing_ok=True)
        return None

    def put(self, key: str, value: BaseModel) -> None:
        tmp = self.root / f"{key}.tmp"
        tmp.write_text(value.model_dump_json())
        tmp.replace(self.root / f"{key}.json")


class Orchestrator:
    def __init__(self, registry: Registry, data_dir: Path, retries: int = 2,
                 on_update: Callable[[Job], None] | None = None):
        self.registry = registry
        self.data_dir = data_dir
        self.cache = Cache(data_dir / "cache")
        self.retries = max(1, retries)
        self.on_update = on_update or (lambda job: None)

    # -- helpers -------------------------------------------------------------
    def _run_chain(self, job: Job, step: str, capability: Capability, fn: Callable[[Plugin], T],
                   cache_parts: tuple | None = None, model: type[BaseModel] | None = None,
                   filter_: Callable[[Plugin], bool] = lambda p: True) -> T:
        failures: list[str] = []
        for plugin in [p for p in self.registry.chain(capability) if filter_(p)]:
            key = self.cache.key(step, plugin.name, plugin.version, *cache_parts) if cache_parts else None
            if key and model:
                hit = self.cache.get(key, model)
                if hit is not None:
                    job.trace.append(StepTrace(step=step, plugin=plugin.name, cached=True, fallbacks=failures))
                    return hit
            for attempt in range(1, self.retries + 1):
                t0 = time.monotonic()
                try:
                    result = fn(plugin)
                except Exception as e:  # plugins wrap third-party code; any failure means "try next"
                    log.warning("%s/%s attempt %d failed: %s", step, plugin.name, attempt, e)
                    last = f"{plugin.name}: {type(e).__name__}: {e}"
                    if isinstance(e, (PermissionError, FileNotFoundError, ValueError)):
                        break  # not transient, don't retry this plugin
                    time.sleep(min(4.0, 0.5 * 2 ** (attempt - 1)))
                    continue
                job.trace.append(StepTrace(step=step, plugin=plugin.name, seconds=round(time.monotonic() - t0, 2), fallbacks=failures))
                if key and isinstance(result, BaseModel):
                    self.cache.put(key, result)
                return result
            failures.append(last)
        raise StepFailed(f"{step} failed in every plugin: " + " | ".join(failures) if failures else f"No plugin could handle {step}")

    def _advance(self, job: Job, step: str, done: bool = False) -> None:
        job.step = step
        if done:
            job.progress = STEP_PROGRESS.get(step, job.progress)
        job.updated_at = time.time()
        self.on_update(job)

    # -- pipeline ------------------------------------------------------------
    def run(self, job: Job) -> Job:
        req = job.request
        workdir = self.data_dir / "jobs" / job.id
        workdir.mkdir(parents=True, exist_ok=True)

        self._advance(job, "ingest")
        job.product = self._run_chain(
            job, "ingest", Capability.ingest,
            lambda p: p.ingest(req, workdir),  # type: ignore[attr-defined]
            filter_=lambda p: isinstance(p, IngestPlugin) and p.can_handle(req),
        )
        self._advance(job, "ingest", done=True)

        if req.script_override:
            job.script = req.script_override
        else:
            self._advance(job, "analyze")
            job.analysis = self._run_chain(
                job, "analyze", Capability.analyze, lambda p: p.analyze(job.product),  # type: ignore[attr-defined]
                cache_parts=(job.product,), model=Analysis,
            )
            self._advance(job, "analyze", done=True)
            self._advance(job, "script")
            job.script = self._run_chain(
                job, "script", Capability.script,
                lambda p: p.write(job.product, job.analysis, req),  # type: ignore[attr-defined]
                cache_parts=(job.product, job.analysis, req.framework, req.target_seconds, req.platform, req.language),
                model=Script,
            )
        self._advance(job, "script", done=True)

        self._advance(job, "voice")
        audio_dir = workdir / "audio"
        audio_dir.mkdir(exist_ok=True)
        scene_audio: list[SceneAudio] = []
        for i, scene in enumerate(job.script.scenes):
            path = audio_dir / f"scene_{i}.wav"

            def speak(p, text=scene.voice, path=path):
                return SceneAudio(path=str(path), duration=p.synthesize(text, path, req))  # type: ignore[attr-defined]

            sa = self._run_chain(job, f"voice[{i}]", Capability.voice, speak)
            sa.words = self._run_chain(
                job, f"align[{i}]", Capability.align,
                lambda p, sa=sa, text=scene.voice: p.align(text, Path(sa.path), sa.duration),  # type: ignore[attr-defined]
            )
            scene_audio.append(sa)
            job.progress = 0.4 + 0.3 * (i + 1) / len(job.script.scenes)
            self.on_update(job)
        if not req.script_override:
            self._fit_to_target(job, scene_audio, req.target_seconds)
        self._advance(job, "voice", done=True)

        self._advance(job, "render")
        music = None
        if req.music_upload_id:
            music = str(self.data_dir / "uploads" / req.music_upload_id)
        elif req.music != "none":
            total = timeline.plan([a.duration for a in scene_audio]).total
            seed = zlib.crc32(job.id.encode()) % 10_000
            try:  # music is polish: an ad without it beats no ad
                music = str(self._run_chain(
                    job, "music", Capability.music,
                    lambda p: p.compose(req.music, total, workdir / "music.wav", seed),  # type: ignore[attr-defined]
                ))
            except (StepFailed, NoPluginAvailable) as e:
                log.warning("Continuing without music: %s", e)
        w, h = req.frame()
        data = RenderInput(product=job.product, script=job.script, scene_audio=scene_audio,
                           width=w, height=h, music_path=music)
        job.output = self._run_chain(
            job, "render", Capability.render,
            lambda p: p.render(data, workdir / "render"),  # type: ignore[attr-defined]
        )
        self._advance(job, "render", done=True)
        return job

    @staticmethod
    def _fit_to_target(job: Job, scene_audio: list[SceneAudio], target: int, tolerance: float = 1.1) -> None:
        """Voices speak at different speeds, so length is checked on the real audio.
        Supporting scenes are dropped (hook, solution, proof and CTA always stay)."""
        def total():
            return sum(a.duration + SCENE_PAD for a in scene_audio) + END_HOLD
        scenes = job.script.scenes
        for kind in DROPPABLE:
            if total() <= target * tolerance or len(scenes) <= 3:
                break
            keep = [i for i, s in enumerate(scenes) if s.kind != kind]
            if len(keep) < len(scenes) and len(keep) >= 3:
                scenes[:] = [scenes[i] for i in keep]
                scene_audio[:] = [scene_audio[i] for i in keep]

    async def run_async(self, job: Job) -> Job:
        return await asyncio.to_thread(self.run, job)
