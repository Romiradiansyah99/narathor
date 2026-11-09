"""Ambil caption YouTube. Jalur cepat, tanpa unduh audio."""

from __future__ import annotations

from contracts import Segment, SourceKind, TranscriptDoc, Video
from ingest import ytdlp

LANGUAGES = ("id", "en")


class TranscriptBlocked(RuntimeError):
    """YouTube refused the request: datacenter IP, bot check, or rate limit."""


def fetch(video: Video) -> TranscriptDoc | None:
    """Ambil caption video. None bila caption tidak tersedia.

    Raises TranscriptBlocked when the refusal is about the caller, not the
    video, so the console can say why instead of reporting a missing caption.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        fetched = YouTubeTranscriptApi().fetch(video.video_id, languages=list(LANGUAGES))
    except Exception as exc:
        name = type(exc).__name__
        if "Blocked" in name or "IpBlocked" in name or "TooManyRequests" in name:
            raise TranscriptBlocked(f"{video.video_id}: {name}") from exc
        return None
    segments = [
        Segment(t0=float(item.start), t1=float(item.start + item.duration), text=str(item.text))
        for item in fetched
        if str(item.text).strip()
    ]
    if not segments:
        return None
    return TranscriptDoc(
        video_id=video.video_id,
        language=getattr(fetched, "language_code", None) or "id",
        source=SourceKind.CAPTIONS,
        segments=segments,
    )


def fetch_audio(video: Video, target_dir) -> str | None:
    """Unduh audio terbaik ke target_dir. None bila gagal."""
    import yt_dlp

    target_dir.mkdir(parents=True, exist_ok=True)
    template = str(target_dir / f"{video.video_id}.%(ext)s")
    options: dict[str, object] = ytdlp.base_options()
    options.update(
        {
            "format": "bestaudio/best",
            "outtmpl": template,
            "skip_download": False,
            "noprogress": True,
            "noplaylist": True,
        }
    )
    try:
        with yt_dlp.YoutubeDL(options) as ydl:  # pyright: ignore[reportArgumentType]
            info = ydl.extract_info(
                video.url or f"https://www.youtube.com/watch?v={video.video_id}",
                download=True,
            )
    except Exception:
        return None
    if not info:
        return None
    return info.get("requested_downloads", [{}])[0].get("filepath")
