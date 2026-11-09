"""Orkestrasi satu run: brief -> agent -> artefak."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.graph import AgentDeps, run_agent
from agent.models import LanguageModel, for_role
from backend import db, soul, store
from backend.config import PROMPT_VERSION, Settings, get_settings
from briefs.load import brief_hash as compute_brief_hash
from briefs.load import load_or_raise
from contracts import NarrativeBrief, RunRecord, SourceRef
from report.render import write_artifacts


def select_videos(brief: NarrativeBrief, engine) -> list:
    """Saring pustaka menurut brief: durasi minimum dan preferensi kebaruan."""
    videos = db.fetch_videos(engine)
    kept = [v for v in videos if v.duration_s >= brief.sources.min_duration_s]
    if brief.sources.recency_preference == "recent":
        kept.sort(key=lambda v: v.published_at or datetime(1970, 1, 1).date(), reverse=True)
    elif brief.sources.recency_preference == "classic":
        kept.sort(key=lambda v: v.published_at or datetime(1970, 1, 1).date())
    return kept


def orchestrate(
    brief_id: str,
    settings: Settings | None = None,
    engine=None,
    count: int | None = None,
    concurrency: int | None = None,
    writer_llm: LanguageModel | None = None,
    matcher_llm: LanguageModel | None = None,
    use_models: bool = True,
) -> dict[str, Any]:
    """Jalankan satu narrative penuh dan tulis artefaknya."""
    settings = settings or get_settings()
    check = soul.verify(settings.soul_path, settings.soul_lock_path)
    if not check.ok:
        raise RuntimeError(f"soul tidak lolos verifikasi: {check.reason}")
    brief = load_or_raise(settings.briefs_dir, brief_id)
    engine = engine or db.build_engine(settings.database_url)
    db.create_schema(engine)
    db.seed(engine, settings.data_dir)

    videos = select_videos(brief, engine)
    transcripts = {
        video.video_id: doc
        for video in videos
        if (doc := db.fetch_transcript(engine, video.video_id)) is not None
    }
    if not videos:
        raise RuntimeError("pustaka kosong untuk brief ini; isi data/ lalu jalankan ingest")

    if use_models and writer_llm is None:
        writer_llm = for_role("writer")
    if use_models and matcher_llm is None:
        matcher_llm = for_role("matcher")

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    started = datetime.now(UTC)
    dep = AgentDeps(
        writer_llm=writer_llm,
        matcher_llm=matcher_llm,
        max_concurrency=concurrency or settings.max_concurrency,
        quote_checker=lambda citation: store.quote_present(engine, citation),
        target_combos=count or brief.output.scripts,
    )
    result = run_agent(
        brief,
        videos,
        transcripts,
        dep,
        thread_id=run_id,
    )

    cards = result.get("cards", [])
    store.save_segments(engine, cards, brief.id)
    for combo in result.get("combos", []):
        store.save_combo(engine, combo, brief.id)
    saved = 0
    for script in result.get("scripts", []):
        try:
            store.save_script(engine, script)
        except store.InvariantError:
            continue
        saved += 1
    for audit in result.get("audits", []):
        store.save_audit(engine, audit)

    channel = db.fetch_channel(engine)
    record = RunRecord(
        run_id=run_id,
        brief_id=brief.id,
        brief_hash=compute_brief_hash(brief),
        soul_version=check.version or 0,
        prompt_version=PROMPT_VERSION,
        models=dict(settings.models),
        sources=[
            SourceRef(video_id=video.video_id, source=transcripts[video.video_id].source)
            for video in videos
            if video.video_id in transcripts
        ],
        started_at=started,
        skipped=result.get("deferred", []),
    )
    store.save_run(engine, record)
    target = write_artifacts(
        settings.output_dir,
        brief.id,
        channel.name.replace(" ", "_") if channel else "channel",
        record,
        result.get("scripts", []),
        cards,
        result.get("audits", []),
    )
    summary = {
        "run_id": run_id,
        "brief": brief.id,
        "videos": len(videos),
        "cards": len(cards),
        "combos": len(result.get("combos", [])),
        "scripts": saved,
        "deferred": result.get("deferred", []),
        "max_concurrency": dep.tracker.max_seen,
        "output": str(target),
    }
    (Path(target) / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
