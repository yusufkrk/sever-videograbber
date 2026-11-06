"""Arayüz için indirme kuyruğu: her link ayrı bir iş, sınırlı sayıda paralel çalışır."""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core import ProgressEvent, VideoGrabber
from ..options import DownloadOptions
from ..platforms import detect_platform

ACTIVE = ("queued", "extracting", "downloading", "processing")


@dataclass
class Job:
    id: str
    url: str
    options: DownloadOptions
    status: str = "queued"
    title: str | None = None
    thumbnail: str | None = None
    uploader: str | None = None
    duration: float | None = None
    downloaded: int | None = None
    total: int | None = None
    speed: float | None = None
    eta: int | None = None
    phase: str | None = None
    item_index: int | None = None
    item_count: int | None = None
    files: list[Path] = field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    item_errors: int = 0
    batch: int = 0
    created: float = field(default_factory=time.time)
    finished: float | None = None
    grabber: VideoGrabber | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        platform = detect_platform(self.url)
        frac = self.downloaded / self.total if self.downloaded is not None and self.total else None
        size = sum(p.stat().st_size for p in self.files if p.exists()) if self.files else None
        return {
            "id": self.id,
            "url": self.url,
            "status": self.status,
            "platform": {"key": platform.key, "name": platform.name},
            "title": self.title,
            "thumbnail": self.thumbnail,
            "uploader": self.uploader,
            "duration": self.duration,
            "audio_only": self.options.audio_only,
            "fraction": min(frac, 1.0) if frac is not None else None,
            "downloaded": self.downloaded,
            "total": self.total,
            "speed": self.speed,
            "eta": self.eta,
            "phase": self.phase,
            "item_index": self.item_index,
            "item_count": self.item_count,
            "files": [str(p) for p in self.files],
            "file_name": self.files[0].name if len(self.files) == 1 else None,
            "file_count": len(self.files),
            "size": size,
            "error": self.error,
            "error_code": self.error_code,
            "item_errors": self.item_errors,
        }


class JobManager:
    def __init__(self, max_parallel: int = 2) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(max(1, max_parallel))
        self._ids = itertools.count(1)
        self._batches = itertools.count(1)
        self.version = 0  # her değişiklikte artar; arayüz gereksiz çizimi atlayabilir

    # ------------------------------------------------------------------ sorgular

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            # En yeni grup en üstte; grup içinde yapıştırılma sırası korunur.
            ordered = sorted(self._jobs.values(), key=lambda j: (-j.batch, int(j.id)))
            return [job.to_dict() for job in ordered]

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ACTIVE)

    # ------------------------------------------------------------------ işlemler

    def add(self, urls: list[str], options: DownloadOptions) -> list[str]:
        ids = []
        batch = next(self._batches)
        for url in urls:
            job = Job(id=str(next(self._ids)), url=url, options=options, batch=batch)
            with self._lock:
                self._jobs[job.id] = job
                self.version += 1
            threading.Thread(target=self._run, args=(job,), name=f"job-{job.id}", daemon=True).start()
            ids.append(job.id)
        return ids

    def retry(self, job_id: str) -> str | None:
        job = self.get(job_id)
        if not job or job.status in ACTIVE:
            return None
        self.remove(job_id)
        return self.add([job.url], job.options)[0]

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.status not in ACTIVE:
            return False
        with self._lock:
            if job.grabber:
                job.grabber.cancel()
            self._finish(job, "cancelled")  # arayüz hemen tepki versin
        return True

    def cancel_all(self) -> None:
        for job_id in [j.id for j in list(self._jobs.values())]:
            self.cancel(job_id)

    def remove(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status not in ACTIVE:
                del self._jobs[job_id]
                self.version += 1

    def clear_finished(self) -> None:
        with self._lock:
            for job_id in [j.id for j in self._jobs.values() if j.status not in ACTIVE]:
                del self._jobs[job_id]
            self.version += 1

    # ------------------------------------------------------------------ iç işleyiş

    def _finish(self, job: Job, status: str) -> None:
        job.status = status
        job.speed = job.eta = None
        job.finished = time.time()
        self.version += 1

    def _on_event(self, job: Job, ev: ProgressEvent) -> None:
        with self._lock:
            if job.status == "cancelled":
                return
            if ev.status in ACTIVE:
                job.status = ev.status
            for key in ("title", "thumbnail", "uploader", "duration", "item_index", "item_count"):
                value = getattr(ev, key)
                if value is not None:
                    setattr(job, key, value)
            if ev.status == "downloading":
                job.downloaded, job.total = ev.downloaded, ev.total
                job.speed, job.eta, job.phase = ev.speed, ev.eta, ev.phase
            elif ev.status == "processing":
                job.speed = job.eta = None
            self.version += 1

    def _run(self, job: Job) -> None:
        with self._slots:
            with self._lock:
                if job.status != "queued":  # sırada beklerken iptal edildi
                    return
                job.grabber = VideoGrabber(job.options, on_progress=lambda ev: self._on_event(job, ev))
            try:
                result = job.grabber.download(job.url)
            except Exception as exc:  # pragma: no cover - download() normalde fırlatmaz
                with self._lock:
                    job.error, job.error_code = str(exc), "generic"
                    self._finish(job, "error")
                return
            with self._lock:
                if job.status == "cancelled":
                    return
                job.files = list(result.files)
                job.title = job.title or result.title
                job.item_errors = len(result.item_errors)
                if result.ok:
                    if job.total:
                        job.downloaded = job.total
                    self._finish(job, "skipped" if result.skipped else "finished")
                elif result.error and result.error.code == "cancelled":
                    self._finish(job, "cancelled")
                else:
                    job.error = str(result.error) if result.error else None
                    job.error_code = result.error.code if result.error else "generic"
                    self._finish(job, "error")
