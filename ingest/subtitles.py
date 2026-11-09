"""Subtitles through yt-dlp: the path that survives a datacenter IP.

The transcript API is refused from cloud ranges. yt-dlp with a cookies file is
not. This module writes no audio: it asks YouTube for the subtitle track and
parses the WEBVTT it gets back.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from contracts import Segment, SourceKind, TranscriptDoc, Video
from ingest import ytdlp

TIMING = re.compile(
    r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<ms>\d{3})\s*-->\s*"
    r"(?P<h2>\d{2}):(?P<m2>\d{2}):(?P<s2>\d{2})[.,](?P<ms2>\d{3})"
)
TAG = re.compile(r"<[^>]+>")
LANGUAGES = ("id", "en")


def _seconds(h: str, m: str, s: str, ms: str) -> float:
    """WEBVTT timestamp to seconds."""
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_vtt(text: str) -> list[Segment]:
    """Parse WEBVTT into segments, dropping the rolling duplicate lines YouTube emits."""
    segments: list[Segment] = []
    start = end = 0.0
    buffer: list[str] = []
    seen_cue = False

    def flush() -> None:
        if not buffer:
            return
        joined = " ".join(buffer).strip()
        if not joined:
            return
        if segments and segments[-1].text == joined:
            return
        segments.append(Segment(t0=start, t1=max(end, start + 0.1), text=joined))

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("WEBVTT") or line.startswith("NOTE") or line.startswith("Kind:"):
            continue
        match = TIMING.match(line)
        if match:
            flush()
            buffer = []
            seen_cue = True
            start = _seconds(match["h"], match["m"], match["s"], match["ms"])
            end = _seconds(match["h2"], match["m2"], match["s2"], match["ms2"])
            continue
        if not line:
            flush()
            buffer = []
            continue
        if not seen_cue or line.startswith(("Kind:", "Language:")):
            continue
        cleaned = TAG.sub("", line).replace("&amp;", "&").replace("&nbsp;", " ").strip()
        if cleaned and not cleaned.isdigit():
            buffer.append(cleaned)
    flush()
    return segments


def fetch(video: Video, workdir: Path | None = None) -> TranscriptDoc | None:
    """Download the subtitle track and parse it. None when there is no track."""
    import yt_dlp

    options: Any = ytdlp.base_options()
    options.update(
        {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(LANGUAGES),
            "subtitlesformat": "vtt",
            "outtmpl": "%(id)s.%(ext)s",
        }
    )
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        options["outtmpl"] = str(Path(tmp) / "%(id)s.%(ext)s")
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([video.url or f"https://www.youtube.com/watch?v={video.video_id}"])
        except Exception as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
        candidates = sorted(Path(tmp).glob("*.vtt"))
        if not candidates:
            return None
        chosen = candidates[0]
        for candidate in candidates:
            if candidate.stem.endswith(".id"):
                chosen = candidate
                break
        segments = parse_vtt(chosen.read_text(encoding="utf-8", errors="replace"))
    if not segments:
        return None
    language = "id" if chosen.stem.endswith(".id") else "en"
    return TranscriptDoc(
        video_id=video.video_id,
        language=language,
        source=SourceKind.CAPTIONS,
        segments=segments,
    )
