"""Durable job store (SQLite) and an asyncio worker pool.

Jobs survive restarts: on startup, anything left queued or running is put back
on the queue, and the step cache lets it resume without redoing finished work.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .domain import Job, JobRequest, JobStatus
from .orchestrator import Orchestrator

log = logging.getLogger("ugc.jobs")


class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT, created REAL, body TEXT)"
            )
            self._db.commit()

    def create(self, request: JobRequest) -> Job:
        now = time.time()
        job = Job(id=uuid.uuid4().hex, status=JobStatus.queued, request=request, created_at=now, updated_at=now)
        self.save(job)
        return job

    def save(self, job: Job) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO jobs (id, status, created, body) VALUES (?, ?, ?, ?)",
                (job.id, job.status.value, job.created_at, job.model_dump_json()),
            )
            self._db.commit()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._db.execute("SELECT body FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return Job.model_validate_json(row[0]) if row else None

    def list(self, limit: int = 50) -> list[Job]:
        with self._lock:
            rows = self._db.execute("SELECT body FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [Job.model_validate_json(r[0]) for r in rows]

    def unfinished(self) -> list[Job]:
        with self._lock:
            rows = self._db.execute(
                "SELECT body FROM jobs WHERE status IN ('queued', 'running') ORDER BY created"
            ).fetchall()
        return [Job.model_validate_json(r[0]) for r in rows]


class JobRunner:
    def __init__(self, store: JobStore, orchestrator: Orchestrator, workers: int = 1):
        self.store = store
        self.orchestrator = orchestrator
        self.orchestrator.on_update = store.save
        self.workers = max(1, workers)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        for job in self.store.unfinished():
            log.info("Recovering job %s", job.id)
            self.queue.put_nowait(job.id)
        self._tasks = [asyncio.create_task(self._worker(i)) for i in range(self.workers)]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def submit(self, request: JobRequest) -> Job:
        job = self.store.create(request)
        self.queue.put_nowait(job.id)
        return job

    async def _worker(self, n: int) -> None:
        while True:
            job_id = await self.queue.get()
            job = self.store.get(job_id)
            if job is None:
                continue
            job.status, job.error, job.trace = JobStatus.running, None, []
            self.store.save(job)
            try:
                await self.orchestrator.run_async(job)
                job.status = JobStatus.succeeded
            except Exception as e:
                log.exception("Job %s failed", job.id)
                job.status, job.error = JobStatus.failed, str(e)[:2000]
            job.updated_at = time.time()
            self.store.save(job)
            self.queue.task_done()
