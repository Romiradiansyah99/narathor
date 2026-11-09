"""Fixture pustaka untuk test. Bukan data sungguhan."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_CHANNEL = {
    "channel_id": "CH-1",
    "name": "Channel Uji",
    "handle": "@channel-uji",
    "url": "https://www.youtube.com/@channel-uji",
}

FIXTURE_VIDEOS = [
    {
        "video_id": "VID-0001",
        "title": "Arah aliran uang, bukan jumlah",
        "duration_s": 640,
        "published_at": "2026-01-15",
        "url": "https://www.youtube.com/watch?v=VID-0001",
    },
    {
        "video_id": "VID-0002",
        "title": "Kenapa gaji naik tapi tetap habis",
        "duration_s": 812,
        "published_at": "2026-02-20",
        "url": "https://www.youtube.com/watch?v=VID-0002",
    },
    {
        "video_id": "VID-0003",
        "title": "Cicilan yang menutup cicilan",
        "duration_s": 455,
        "published_at": "2026-03-05",
        "url": "https://www.youtube.com/watch?v=VID-0003",
    },
]


def _segments_a() -> list[dict]:
    return [
        {"t0": 0.0, "t1": 4.5, "text": "Jadi gini, masalahnya bukan berapa yang masuk."},
        {"t0": 4.5, "t1": 12.0, "text": "Masalahnya ke mana yang masuk itu pergi."},
        {"t0": 12.0, "t1": 21.0, "text": "Tiga puluh persen bocor di hal yang tidak kamu ingat."},
    ]


def _segments_b() -> list[dict]:
    return [
        {"t0": 0.0, "t1": 5.0, "text": "Gaji naik dua kali lipat, tabungan tidak bergerak."},
        {
            "t0": 5.0,
            "t1": 14.0,
            "text": "Penyebabnya pengeluaran ikut naik dengan kecepatan yang sama.",
        },
        {
            "t0": 14.0,
            "t1": 24.0,
            "text": "Jadi masalah keuangan bukan soal jumlah, tapi ke mana aliran uang pergi.",
        },
    ]


FIXTURE_TRANSCRIPTS = {
    "VID-0001": {
        "video_id": "VID-0001",
        "language": "id",
        "source": "captions",
        "segments": _segments_a(),
    },
    "VID-0002": {
        "video_id": "VID-0002",
        "language": "id",
        "source": "whisper",
        "segments": _segments_b(),
    },
}


def write_fixture_library(data_dir: Path) -> Path:
    """Tulis pustaka fixture ke direktori sementara."""
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "channel.json").write_text(json.dumps(FIXTURE_CHANNEL), encoding="utf-8")
    (data_dir / "videos.json").write_text(json.dumps(FIXTURE_VIDEOS), encoding="utf-8")
    transcript_dir = data_dir / "transcripts"
    transcript_dir.mkdir(exist_ok=True)
    for video_id, doc in FIXTURE_TRANSCRIPTS.items():
        (transcript_dir / f"{video_id}.json").write_text(json.dumps(doc), encoding="utf-8")
    return data_dir
