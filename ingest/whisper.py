"""Transkrip fallback dengan faster-whisper. Opsional, lokal, tanpa API berbayar."""

from __future__ import annotations

from contracts import Segment, SourceKind, TranscriptDoc, Video

DEFAULT_MODEL = "small"


def transcribe(
    video: Video, audio_path: str, model_name: str = DEFAULT_MODEL
) -> TranscriptDoc | None:
    """Transkrip audio lokal. None bila dependensi tidak tersedia."""
    try:
        from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    raw_segments, info = model.transcribe(audio_path, vad_filter=True)
    segments = [
        Segment(t0=float(seg.start), t1=float(seg.end), text=str(seg.text).strip())
        for seg in raw_segments
        if str(seg.text).strip()
    ]
    if not segments:
        return None
    return TranscriptDoc(
        video_id=video.video_id,
        language=getattr(info, "language", None) or "id",
        source=SourceKind.WHISPER,
        segments=segments,
    )
