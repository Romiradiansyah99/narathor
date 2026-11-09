"""Tulis ke database lewat backend. Invarian ditegakkan di sini, bukan di prompt."""

from __future__ import annotations

import json
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from backend.db import (
    audits_t,
    citations_t,
    combos_t,
    runs_t,
    scripts_t,
    segments_t,
    transcripts_t,
)
from contracts import (
    Audit,
    Citation,
    Combo,
    RunRecord,
    SegmentCard,
    ShortScript,
    TranscriptDoc,
)


class InvariantError(RuntimeError):
    """Pelanggaran yang tidak boleh dilanjutkan dengan peringatan."""


def normalize(text: str) -> str:
    """Normalisasi longgar untuk pencocokan kutipan: huruf kecil, tanpa tanda baca."""
    lowered = unicodedata.normalize("NFKD", text.lower())
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return " ".join(cleaned.split())


def save_transcript(engine: Engine, doc: TranscriptDoc) -> None:
    """Simpan atau ganti transkrip satu video."""
    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(delete(transcripts_t).where(transcripts_t.c.video_id == doc.video_id))
        conn.execute(
            transcripts_t.insert().values(
                video_id=doc.video_id,
                language=doc.language,
                source=str(doc.source),
                segments=[seg.model_dump() for seg in doc.segments],
                created_at=now,
            )
        )


def save_segments(engine: Engine, cards: list[SegmentCard], brief_id: str) -> int:
    """Simpan kartu segmen. unit_key memuat brief agar dua brief tidak berbagi baris."""
    now = datetime.now(UTC)
    with engine.begin() as conn:
        for card in cards:
            unit_key = f"{card.segment_id}|{brief_id}"
            conn.execute(delete(segments_t).where(segments_t.c.segment_id == card.segment_id))
            conn.execute(
                segments_t.insert().values(
                    segment_id=card.segment_id,
                    video_id=card.video_id,
                    t0=card.t0,
                    t1=card.t1,
                    text=card.key_quote,
                    kind=card.kind,
                    key_quote=card.key_quote,
                    features=card.features.model_dump(),
                    brand_fit=card.brand_fit,
                    unit_key=unit_key,
                    created_at=now,
                )
            )
    return len(cards)


def save_combo(engine: Engine, combo: Combo, brief_id: str) -> None:
    """Simpan combo."""
    with engine.begin() as conn:
        conn.execute(delete(combos_t).where(combos_t.c.combo_id == combo.combo_id))
        conn.execute(
            combos_t.insert().values(
                combo_id=combo.combo_id,
                brief_id=brief_id,
                thesis=combo.thesis,
                segment_ids=combo.segment_ids,
                video_ids=combo.video_ids,
                created_at=datetime.now(UTC),
            )
        )


def quote_present(engine: Engine, citation: Citation) -> bool:
    """Cocokkan quote ke transkrip pada rentang t0..t1. Writer tidak dipercaya."""
    with engine.connect() as conn:
        row = (
            conn.execute(select(transcripts_t).where(transcripts_t.c.video_id == citation.video_id))
            .mappings()
            .first()
        )
    if row is None:
        return False
    segments = row["segments"]
    haystack = normalize(
        " ".join(
            str(seg.get("text", ""))
            for seg in segments
            if float(seg.get("t1", 0)) > citation.t0 and float(seg.get("t0", 0)) < citation.t1
        )
    )
    needle = normalize(citation.quote)
    return bool(needle) and needle in haystack


def save_script(engine: Engine, script: ShortScript) -> None:
    """Simpan naskah. Klaim tanpa sitasi valid -> InvariantError, tidak ada yang ditulis."""
    for beat in script.beats:
        if beat.is_claim:
            if beat.citation is None:
                raise InvariantError(f"beat pada {beat.at_s}s mengaku klaim tanpa citation")
            if not quote_present(engine, beat.citation):
                raise InvariantError(
                    f"kutipan tidak ditemukan di transkrip {beat.citation.video_id} "
                    f"pada {beat.citation.t0}..{beat.citation.t1}"
                )
    with engine.begin() as conn:
        conn.execute(delete(scripts_t).where(scripts_t.c.script_id == script.script_id))
        conn.execute(delete(citations_t).where(citations_t.c.script_id == script.script_id))
        conn.execute(
            scripts_t.insert().values(
                script_id=script.script_id,
                combo_id=script.combo_id,
                brief_id=script.brief_id,
                payload=json.loads(script.model_dump_json()),
                status="pending",
                attempts=0,
                created_at=datetime.now(UTC),
            )
        )
        for beat in script.beats:
            if beat.citation is None:
                continue
            conn.execute(
                citations_t.insert().values(
                    script_id=script.script_id,
                    video_id=beat.citation.video_id,
                    t0=beat.citation.t0,
                    t1=beat.citation.t1,
                    quote=beat.citation.quote,
                )
            )


def save_audit(engine: Engine, audit: Audit) -> None:
    """Simpan audit tujuh gate."""
    with engine.begin() as conn:
        conn.execute(delete(audits_t).where(audits_t.c.script_id == audit.script_id))
        conn.execute(
            audits_t.insert().values(
                script_id=audit.script_id,
                verdict=audit.verdict,
                payload=json.loads(audit.model_dump_json()),
                created_at=datetime.now(UTC),
            )
        )
        conn.execute(
            scripts_t.update()
            .where(scripts_t.c.script_id == audit.script_id)
            .values(status="done" if audit.verdict == "pass" else audit.verdict)
        )


def save_run(engine: Engine, record: RunRecord) -> None:
    """Simpan catatan run. Tanpa ini artefak tidak boleh ditulis."""
    with engine.begin() as conn:
        conn.execute(delete(runs_t).where(runs_t.c.run_id == record.run_id))
        conn.execute(
            runs_t.insert().values(
                run_id=record.run_id,
                brief_id=record.brief_id,
                brief_hash=record.brief_hash,
                soul_version=record.soul_version,
                prompt_version=record.prompt_version,
                models=record.models,
                status=record.status,
                started_at=record.started_at,
                finished_at=record.finished_at,
                est_cost_usd=record.est_cost_usd,
                payload=json.loads(record.model_dump_json()),
            )
        )


def finish_run(engine: Engine, run_id: str, status: str, cost_usd: float = 0.0) -> None:
    """Tandai run selesai atau gagal."""
    with engine.begin() as conn:
        conn.execute(
            runs_t.update()
            .where(runs_t.c.run_id == run_id)
            .values(status=status, finished_at=datetime.now(UTC), est_cost_usd=cost_usd)
        )


def load_cards(engine: Engine, brief_id: str) -> list[SegmentCard]:
    """Baca kartu segmen yang tersimpan untuk satu brief."""
    with engine.connect() as conn:
        rows = (
            conn.execute(select(segments_t).where(segments_t.c.unit_key.like(f"%|{brief_id}")))
            .mappings()
            .all()
        )
    cards: list[SegmentCard] = []
    for row in rows:
        cards.append(
            SegmentCard(
                segment_id=row["segment_id"],
                video_id=row["video_id"],
                t0=row["t0"],
                t1=row["t1"],
                kind=row["kind"],
                key_quote=row["key_quote"],
                features=row["features"],
                brand_fit=row["brand_fit"],
            )
        )
    return sorted(cards, key=lambda c: c.segment_id)


def load_scripts(engine: Engine, brief_id: str) -> list[ShortScript]:
    """Baca naskah yang tersimpan untuk satu brief."""
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(scripts_t)
                .where(scripts_t.c.brief_id == brief_id)
                .order_by(scripts_t.c.script_id)
            )
            .mappings()
            .all()
        )
    return [ShortScript.model_validate(row["payload"]) for row in rows]


def load_audits(engine: Engine, limit: int = 500) -> list[Audit]:
    """Baca audit terakhir."""
    with engine.connect() as conn:
        rows = (
            conn.execute(select(audits_t).order_by(audits_t.c.created_at.desc()).limit(limit))
            .mappings()
            .all()
        )
    return [Audit.model_validate(row["payload"]) for row in rows]
