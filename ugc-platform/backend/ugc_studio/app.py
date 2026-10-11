"""REST API consumed by the Android app."""
from __future__ import annotations

import hmac
import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import __version__
from .config import Settings, get_settings
from .domain import Framework, Job, JobRequest, Platform
from .jobs import JobRunner, JobStore
from .orchestrator import Orchestrator
from .plugins import Capability, Registry, build_registry

MAX_UPLOAD = 50 * 1024 * 1024
UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac"}


class SwapRequest(BaseModel):
    name: str


class Created(BaseModel):
    id: str


def create_app(settings: Settings | None = None, registry: Registry | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    uploads = settings.data_dir / "uploads"
    uploads.mkdir(exist_ok=True)
    registry = registry or build_registry(settings)
    store = JobStore(settings.data_dir / "jobs.db")
    runner = JobRunner(store, Orchestrator(registry, settings.data_dir, settings.step_retries), settings.workers)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runner.start()
        yield
        await runner.stop()
        for plugin in registry.all():  # stop model worker processes
            close = getattr(plugin, "close", None)
            if callable(close):
                close()

    app = FastAPI(title="UGC Ad Studio API", version=__version__, lifespan=lifespan)
    app.state.registry, app.state.store, app.state.runner = registry, store, runner

    def auth(x_api_key: str | None = Header(default=None)) -> None:
        if settings.api_key and not (x_api_key and hmac.compare_digest(x_api_key, settings.api_key)):
            raise HTTPException(401, "Missing or wrong X-API-Key")

    def job_or_404(job_id: str) -> Job:
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    def job_file(job: Job, path: str | None) -> Path:
        if not path:
            raise HTTPException(409, f"Job is {job.status.value}; output not ready")
        p = Path(path).resolve()
        if settings.data_dir.resolve() not in p.parents or not p.exists():
            raise HTTPException(404, "File missing")
        return p

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/options", dependencies=[Depends(auth)])
    def options():
        return {
            "platforms": [p.value for p in Platform],
            "frameworks": [f.value for f in Framework],
            "resolutions": ["720p", "1080p", "4k"],
        }

    @app.get("/plugins", dependencies=[Depends(auth)])
    def plugins():
        out = []
        for p in registry.all():
            info = p.info()
            info["preferred"] = registry.preferred(p.capability) == p.name
            out.append(info)
        return out

    @app.put("/plugins/{capability}", dependencies=[Depends(auth)])
    def swap_plugin(capability: Capability, body: SwapRequest):
        try:
            registry.set_preferred(capability, body.name)
        except KeyError as e:
            raise HTTPException(404, str(e)) from None
        return {"capability": capability.value, "preferred": body.name}

    @app.post("/uploads", dependencies=[Depends(auth)], response_model=Created)
    async def upload(file: UploadFile = File(...)):
        if file.content_type not in UPLOAD_TYPES:
            raise HTTPException(415, f"Unsupported type {file.content_type}")
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File too large (max 50 MB)")
        uid = uuid.uuid4().hex
        (uploads / uid).write_bytes(data)
        return Created(id=uid)

    @app.post("/jobs", dependencies=[Depends(auth)], status_code=202, response_model=Job)
    def create_job(req: JobRequest):
        if req.music_upload_id and not (re.fullmatch(r"[a-f0-9]{32}", req.music_upload_id)
                                        and (uploads / req.music_upload_id).exists()):
            raise HTTPException(400, "Unknown music_upload_id")
        return runner.submit(req)

    @app.get("/jobs", dependencies=[Depends(auth)], response_model=list[Job])
    def list_jobs(limit: int = 50):
        return store.list(min(max(1, limit), 200))

    @app.get("/jobs/{job_id}", dependencies=[Depends(auth)], response_model=Job)
    def get_job(job_id: str):
        return job_or_404(job_id)

    @app.post("/jobs/{job_id}/retry", dependencies=[Depends(auth)], status_code=202, response_model=Job)
    def retry_job(job_id: str):
        job = job_or_404(job_id)
        if job.status.value in ("queued", "running"):
            raise HTTPException(409, "Job is still in progress")
        return runner.submit(job.request)  # cached steps make this cheap

    @app.get("/jobs/{job_id}/video", dependencies=[Depends(auth)])
    def video(job_id: str):
        job = job_or_404(job_id)
        return FileResponse(job_file(job, job.output and job.output.video), media_type="video/mp4",
                            filename=f"ugc-ad-{job_id[:8]}.mp4")

    @app.get("/jobs/{job_id}/thumbnail", dependencies=[Depends(auth)])
    def thumbnail(job_id: str):
        job = job_or_404(job_id)
        return FileResponse(job_file(job, job.output and job.output.thumbnail), media_type="image/jpeg")

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8080)
