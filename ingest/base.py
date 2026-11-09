"""Kontrak ingest: fetcher, store, dan laporan run."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from contracts import SourceKind, TranscriptDoc, Video


class TranscriptStore(Protocol):
    """Penyimpanan transkrip. Cache dan database memakai antarmuka yang sama."""

    def get(self, video_id: str) -> TranscriptDoc | None:
        """Ambil transkrip bila sudah ada."""
        ...

    def put(self, doc: TranscriptDoc) -> None:
        """Simpan transkrip."""
        ...


Fetcher = Callable[[Video], TranscriptDoc | None]


@dataclass
class IngestReport:
    """Hasil satu run ingest."""

    ingested: list[str] = field(default_factory=list)
    cached: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    sources: dict[str, SourceKind] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    elapsed_s: float = 0.0

    def as_dict(self) -> dict:
        """Bentuk siap tulis ke run.json."""
        return {
            "ingested": self.ingested,
            "cached": self.cached,
            "skipped": self.skipped,
            "sources": {k: str(v) for k, v in self.sources.items()},
            "errors": self.errors,
            "elapsed_s": round(self.elapsed_s, 3),
        }
