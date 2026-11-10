"""Background jobs: the bridge between a button in the browser and the pipeline.

Ingest and assemble take minutes, so they cannot run inside a request. Each job
is a thread with a log the UI polls, and the log is mirrored to disk so a
restart does not erase the history of what was run.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

JobKind = Literal["channel", "profile", "ingest", "run"]
JobStatus = Literal["queued", "running", "done", "failed"]

MAX_LOG_LINES = 400


@dataclass
class Job:
    """One unit of background work."""

    job_id: str
    kind: JobKind
    label: str
    status: JobStatus = "queued"
    created_at: str = ""
    finished_at: str | None = None
    log: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Shape the UI reads."""
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "log": self.log,
            "result": self.result,
            "error": self.error,
        }


class Registry:
    """Every job this process knows about, newest first."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._log_dir = log_dir

    def _persist(self, job: Job) -> None:
        """Mirror the job to disk. Failure to write must not kill the job."""
        if self._log_dir is None:
            return
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            (self._log_dir / f"{job.job_id}.json").write_text(
                json.dumps(job.as_dict(), indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def get(self, job_id: str) -> Job | None:
        """One job by id."""
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 20) -> list[Job]:
        """Recent jobs, newest first."""
        with self._lock:
            return list(reversed(list(self._jobs.values())))[:limit]

    def start(
        self,
        kind: JobKind,
        label: str,
        work: Callable[[Callable[[str], None]], dict[str, Any]],
    ) -> Job:
        """Run `work` in a thread. It receives a logger and returns the result."""
        job = Job(
            job_id=f"job-{uuid.uuid4().hex[:10]}",
            kind=kind,
            label=label,
            status="running",
            created_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._persist(job)

        def log(line: str) -> None:
            with self._lock:
                job.log.append(str(line))
                if len(job.log) > MAX_LOG_LINES:
                    del job.log[: len(job.log) - MAX_LOG_LINES]
            self._persist(job)

        def target() -> None:
            try:
                job.result = work(log) or {}
                job.status = "done"
            except Exception as exc:
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "failed"
                log(job.error)
            finally:
                job.finished_at = datetime.now(UTC).isoformat()
                self._persist(job)

        thread = threading.Thread(target=target, name=job.job_id, daemon=True)
        thread.start()
        return job
