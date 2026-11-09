"""Pipeline ingest: caption dulu, Whisper bila perlu, cache selalu dihormati."""

from __future__ import annotations

import time

from backend.config import get_settings
from backend.db import fetch_transcript
from contracts import TranscriptDoc, Video
from ingest.base import Fetcher, IngestReport, TranscriptStore


class DbStore:
    """Store transkrip di database lewat backend. Satu-satunya jalur tulis."""

    def __init__(self, engine=None) -> None:
        from backend.db import get_engine

        self.engine = engine or get_engine()

    def get(self, video_id: str) -> TranscriptDoc | None:
        """Ambil transkrip dari database."""
        return fetch_transcript(self.engine, video_id)

    def put(self, doc: TranscriptDoc) -> None:
        """Simpan transkrip ke database."""
        from backend.store import save_transcript

        save_transcript(self.engine, doc)


class MemoryStore:
    """Store dalam memori, dipakai test."""

    def __init__(self) -> None:
        self.items: dict[str, TranscriptDoc] = {}

    def get(self, video_id: str) -> TranscriptDoc | None:
        """Ambil dari memori."""
        return self.items.get(video_id)

    def put(self, doc: TranscriptDoc) -> None:
        """Simpan ke memori."""
        self.items[doc.video_id] = doc


def run(
    videos: list[Video],
    store: TranscriptStore,
    captions: Fetcher,
    whisper: Fetcher | None = None,
    force: bool = False,
) -> IngestReport:
    """Jalankan ingest untuk semua video. Satu video gagal tidak menghentikan run."""
    report = IngestReport()
    started = time.perf_counter()
    for video in videos:
        if not force:
            existing = store.get(video.video_id)
            if existing is not None:
                report.cached.append(video.video_id)
                report.sources[video.video_id] = existing.source
                continue
        doc = None
        reason = ""
        try:
            doc = captions(video)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            doc = None
        if doc is None and whisper is not None:
            try:
                doc = whisper(video)
            except Exception as exc:
                reason = reason or f"{type(exc).__name__}: {exc}"
                doc = None
        if doc is None:
            report.skipped.append(video.video_id)
            report.errors[video.video_id] = reason or "no captions and no audio"
            continue
        store.put(doc)
        report.ingested.append(video.video_id)
        report.sources[video.video_id] = doc.source
    report.elapsed_s = time.perf_counter() - started
    return report


def default_fetchers() -> tuple[Fetcher, Fetcher]:
    """Fetcher produksi: caption YouTube, subtitle lewat yt-dlp, lalu Whisper."""
    from ingest import captions as captions_mod
    from ingest import subtitles as subtitles_mod
    from ingest import whisper as whisper_mod

    cache_dir = get_settings().output_dir / "_cache" / "audio"

    def captions_fetcher(video: Video) -> TranscriptDoc | None:
        blocked: Exception | None = None
        try:
            doc = captions_mod.fetch(video)
        except captions_mod.TranscriptBlocked as exc:
            doc = None
            blocked = exc
        if doc is not None:
            return doc
        try:
            doc = subtitles_mod.fetch(video)
        except Exception:
            if blocked is not None:
                raise blocked from None
            raise
        return doc

    def whisper_fetcher(video: Video) -> TranscriptDoc | None:
        path = captions_mod.fetch_audio(video, cache_dir)
        if path is None:
            return None
        return whisper_mod.transcribe(video, path)

    return captions_fetcher, whisper_fetcher
