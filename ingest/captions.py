"""Ambil caption YouTube. Jalur cepat, tanpa unduh audio."""

from __future__ import annotations

from contracts import Segment, SourceKind, TranscriptDoc, Video

LANGUAGES = ("id", "en")


def fetch(video: Video) -> TranscriptDoc | None:
    """Ambil caption video. None bila caption tidak tersedia."""
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        fetched = YouTubeTranscriptApi().fetch(video.video_id, languages=list(LANGUAGES))
    except Exception:
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
    options: dict[str, object] = {
        "format": "bestaudio/best",
        "outtmpl": template,
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
    }
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
