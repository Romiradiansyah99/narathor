"""Akses database. SQLAlchemy Core, satu query untuk SQLite dan Postgres."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from backend.config import get_settings
from contracts import Channel, SourceKind, TranscriptDoc, Video

SCHEMA = "narathor"
metadata = MetaData(schema=SCHEMA)

channels_t = Table(
    "channels",
    metadata,
    Column("channel_id", String(64), primary_key=True),
    Column("name", String(256), nullable=False),
    Column("handle", String(128), nullable=False),
    Column("url", String(512), nullable=False),
)

videos_t = Table(
    "videos",
    metadata,
    Column("video_id", String(64), primary_key=True),
    Column("channel_id", String(64), ForeignKey(f"{SCHEMA}.channels.channel_id"), nullable=False),
    Column("title", String(512), nullable=False),
    Column("duration_s", Integer, nullable=False),
    Column("published_at", String(32), nullable=True),
    Column("url", String(512), nullable=True),
)

transcripts_t = Table(
    "transcripts",
    metadata,
    Column("video_id", String(64), ForeignKey(f"{SCHEMA}.videos.video_id"), primary_key=True),
    Column("language", String(16), nullable=False),
    Column("source", String(16), nullable=False),
    Column("segments", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

segments_t = Table(
    "segments",
    metadata,
    Column("segment_id", String(128), primary_key=True),
    Column("video_id", String(64), ForeignKey(f"{SCHEMA}.videos.video_id"), nullable=False),
    Column("t0", Float, nullable=False),
    Column("t1", Float, nullable=False),
    Column("text", Text, nullable=False),
    Column("kind", String(16), nullable=False),
    Column("key_quote", Text, nullable=False),
    Column("features", JSON, nullable=False),
    Column("brand_fit", Integer, nullable=False, default=0),
    Column("unit_key", String(256), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

combos_t = Table(
    "combos",
    metadata,
    Column("combo_id", String(128), primary_key=True),
    Column("brief_id", String(64), nullable=False),
    Column("thesis", Text, nullable=False),
    Column("segment_ids", JSON, nullable=False),
    Column("video_ids", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

scripts_t = Table(
    "scripts",
    metadata,
    Column("script_id", String(128), primary_key=True),
    Column("combo_id", String(128), nullable=False),
    Column("brief_id", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("status", String(16), nullable=False, default="pending"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

citations_t = Table(
    "citations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("script_id", String(128), nullable=False),
    Column("video_id", String(64), nullable=False),
    Column("t0", Float, nullable=False),
    Column("t1", Float, nullable=False),
    Column("quote", Text, nullable=False),
)

audits_t = Table(
    "audits",
    metadata,
    Column("script_id", String(128), primary_key=True),
    Column("verdict", String(16), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

runs_t = Table(
    "runs",
    metadata,
    Column("run_id", String(128), primary_key=True),
    Column("brief_id", String(64), nullable=False),
    Column("brief_hash", String(64), nullable=False),
    Column("soul_version", Integer, nullable=False),
    Column("prompt_version", String(32), nullable=False),
    Column("models", JSON, nullable=False),
    Column("status", String(16), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("est_cost_usd", Float, nullable=False, default=0.0),
    Column("payload", JSON, nullable=False, default=dict),
)

agent_calls_t = Table(
    "agent_calls",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(128), nullable=False),
    Column("role", String(32), nullable=False),
    Column("model", String(128), nullable=False),
    Column("prompt_tokens", Integer, nullable=False, default=0),
    Column("completion_tokens", Integer, nullable=False, default=0),
    Column("cost_usd", Float, nullable=False, default=0.0),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

cache_t = Table(
    "cache",
    metadata,
    Column("cache_key", String(128), primary_key=True),
    Column("value", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def build_engine(url: str) -> Engine:
    """Buat engine dengan schema_translate_map agar jalan di SQLite maupun Postgres."""
    translate = {"schema_translate_map": {SCHEMA: None}}
    if url.startswith("sqlite"):
        if ":memory:" in url or url.endswith(":memory:"):
            return create_engine(
                url,
                future=True,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                execution_options=translate,
            )
        return create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            execution_options=translate,
        )
    return create_engine(url, future=True, pool_size=4, max_overflow=0, execution_options=translate)


_engine: Engine | None = None


def get_engine() -> Engine:
    """Engine proses-tunggal, dibuat sekali."""
    global _engine
    if _engine is None:
        _engine = build_engine(get_settings().database_url)
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Ganti engine, dipakai test dan CLI."""
    global _engine
    _engine = engine


def create_schema(engine: Engine) -> None:
    """Buat seluruh tabel bila belum ada."""
    metadata.create_all(engine)


# --------------------------------------------------------------------------- #
# Seed dari data/ (read-only)
# --------------------------------------------------------------------------- #


def read_library(data_dir: Path) -> tuple[Channel | None, list[Video], dict[str, TranscriptDoc]]:
    """Baca pustaka dari data/ tanpa menulis apa pun ke sana."""
    channel: Channel | None = None
    channel_file = data_dir / "channel.json"
    if channel_file.exists():
        channel = Channel.model_validate(json.loads(channel_file.read_text(encoding="utf-8")))

    videos: list[Video] = []
    videos_file = data_dir / "videos.json"
    if videos_file.exists():
        payload = json.loads(videos_file.read_text(encoding="utf-8"))
        videos = [Video.model_validate(item) for item in payload]

    transcripts: dict[str, TranscriptDoc] = {}
    transcript_dir = data_dir / "transcripts"
    if transcript_dir.exists():
        for doc_path in sorted(transcript_dir.glob("*.json")):
            doc = TranscriptDoc.model_validate(json.loads(doc_path.read_text(encoding="utf-8")))
            transcripts[doc.video_id] = doc
    return channel, videos, transcripts


def seed(engine: Engine, data_dir: Path | None = None) -> dict[str, int]:
    """Isi tabel dari data/ bila kosong. Idempoten."""
    data_dir = data_dir or get_settings().data_dir
    channel, videos, transcripts = read_library(data_dir)
    now = datetime.now(UTC)
    counts = {"channels": 0, "videos": 0, "transcripts": 0}
    with engine.begin() as conn:
        existing_channels = conn.execute(select(channels_t.c.channel_id)).all()
        if not existing_channels and channel is not None:
            conn.execute(
                channels_t.insert().values(
                    channel_id=channel.channel_id,
                    name=channel.name,
                    handle=channel.handle,
                    url=channel.url,
                )
            )
            counts["channels"] = 1
        elif existing_channels and channel is not None:
            pass
        else:
            pass

        known_videos = {row[0] for row in conn.execute(select(videos_t.c.video_id)).all()}
        channel_id = channel.channel_id if channel else "unknown"
        for video in videos:
            if video.video_id in known_videos:
                continue
            conn.execute(
                videos_t.insert().values(
                    video_id=video.video_id,
                    channel_id=channel_id,
                    title=video.title,
                    duration_s=video.duration_s,
                    published_at=video.published_at.isoformat() if video.published_at else None,
                    url=video.url,
                )
            )
            counts["videos"] += 1

        known_transcripts = {row[0] for row in conn.execute(select(transcripts_t.c.video_id)).all()}
        known_videos = {row[0] for row in conn.execute(select(videos_t.c.video_id)).all()}
        for video_id, doc in transcripts.items():
            if video_id in known_transcripts or video_id not in known_videos:
                continue
            conn.execute(
                transcripts_t.insert().values(
                    video_id=video_id,
                    language=doc.language,
                    source=str(doc.source),
                    segments=[seg.model_dump() for seg in doc.segments],
                    created_at=now,
                )
            )
            counts["transcripts"] += 1
    return counts


def ensure_ready(engine: Engine | None = None, data_dir: Path | None = None) -> dict[str, int]:
    """Buat schema lalu seed. Aman dipanggil berulang."""
    eng = engine or get_engine()
    create_schema(eng)
    return seed(eng, data_dir)


# --------------------------------------------------------------------------- #
# Query baca
# --------------------------------------------------------------------------- #


def fetch_channel(engine: Engine) -> Channel | None:
    """Ambil channel pertama."""
    with engine.connect() as conn:
        row = conn.execute(select(channels_t)).mappings().first()
    if row is None:
        return None
    return Channel(
        channel_id=row["channel_id"],
        name=row["name"],
        handle=row["handle"],
        url=row["url"],
    )


def fetch_videos(engine: Engine) -> list[Video]:
    """Seluruh video dalam pustaka, urut video_id."""
    with engine.connect() as conn:
        rows = conn.execute(select(videos_t).order_by(videos_t.c.video_id)).mappings().all()
    return [
        Video(
            video_id=row["video_id"],
            title=row["title"],
            duration_s=row["duration_s"],
            published_at=row["published_at"],
            url=row["url"],
        )
        for row in rows
    ]


def fetch_video(engine: Engine, video_id: str) -> Video | None:
    """Satu video, None bila tidak ada."""
    with engine.connect() as conn:
        row = (
            conn.execute(select(videos_t).where(videos_t.c.video_id == video_id)).mappings().first()
        )
    if row is None:
        return None
    return Video(
        video_id=row["video_id"],
        title=row["title"],
        duration_s=row["duration_s"],
        published_at=row["published_at"],
        url=row["url"],
    )


def fetch_transcript(engine: Engine, video_id: str) -> TranscriptDoc | None:
    """Transkrip satu video, None bila belum di-ingest."""
    with engine.connect() as conn:
        row = (
            conn.execute(select(transcripts_t).where(transcripts_t.c.video_id == video_id))
            .mappings()
            .first()
        )
    if row is None:
        return None
    return TranscriptDoc(
        video_id=row["video_id"],
        language=row["language"],
        source=SourceKind(row["source"]),
        segments=row["segments"],
    )
