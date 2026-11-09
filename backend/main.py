"""Backend API. The only door to the data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from backend import db, soul
from backend.config import Settings, get_settings
from briefs import load as briefs_load
from contracts import NarrativeBrief, SoulCheck

router = APIRouter(prefix="/api")


def _settings(request: Request) -> Settings:
    """Settings attached to the app, not global, so tests stay isolated."""
    return request.app.state.settings


def _engine(request: Request) -> Engine:
    """Engine milik app."""
    return request.app.state.engine


def require_soul(request: Request) -> SoulCheck:
    """Check the constitution at the start of every request. Mismatch -> 409."""
    settings = _settings(request)
    check = soul.verify(settings.soul_path, settings.soul_lock_path)
    if not check.ok:
        raise HTTPException(status_code=409, detail=check.model_dump(mode="json"))
    return check


@router.get("/soul", operation_id="get_soul_status")
def get_soul_status(request: Request) -> dict[str, Any]:
    """Constitution status: version, hash, and check result."""
    settings = _settings(request)
    check = soul.verify(settings.soul_path, settings.soul_lock_path)
    return {
        "version": check.version,
        "sha256": check.actual_hash,
        "expected_sha256": check.expected_hash,
        "ok": check.ok,
        "checked_at": check.checked_at.isoformat(),
        "reason": check.reason,
    }


@router.get("/health", operation_id="health")
def health(request: Request) -> dict[str, Any]:
    """Backend, database, and library status."""
    settings = _settings(request)
    engine = _engine(request)
    videos = db.fetch_videos(engine)
    channel = db.fetch_channel(engine)
    return {
        "status": "ok",
        "database": "sqlite" if settings.is_sqlite else "postgres",
        "channel": channel.name if channel else None,
        "videos": len(videos),
        "briefs": len(briefs_load.list_ids(settings.briefs_dir)),
        "api_key_present": bool(settings.api_key),
    }


@router.get("/briefs", operation_id="list_briefs")
def list_briefs(request: Request) -> list[dict[str, Any]]:
    """List briefs with their validation status."""
    settings = _settings(request)
    items: list[dict[str, Any]] = []
    for brief_id in briefs_load.list_ids(settings.briefs_dir):
        report = briefs_load.load(settings.briefs_dir, brief_id)
        items.append(
            {
                "id": brief_id,
                "title": report.brief.title if report.brief else None,
                "ok": report.ok,
                "rejections": [r.__dict__ for r in report.rejections],
            }
        )
    return items


@router.get("/briefs/{brief_id}", operation_id="get_brief")
def get_brief(brief_id: str, request: Request) -> dict[str, Any]:
    """One validated brief. A rejected brief -> 400 with the reason."""
    settings = _settings(request)
    report = briefs_load.load(settings.briefs_dir, brief_id)
    if report.brief is None:
        raise HTTPException(
            status_code=400,
            detail={
                "brief_id": brief_id,
                "message": report.render(),
                "rejections": [{"code": r.code, "message": r.message} for r in report.rejections],
            },
        )
    brief: NarrativeBrief = report.brief
    return {
        "brief": brief.model_dump(mode="json"),
        "brief_hash": briefs_load.brief_hash(brief),
    }


@router.get("/videos", operation_id="list_videos")
def list_videos(request: Request) -> list[dict[str, Any]]:
    """Every video in the library, with id, title, and duration."""
    videos = db.fetch_videos(_engine(request))
    return [
        {
            "video_id": v.video_id,
            "title": v.title,
            "duration_s": v.duration_s,
            "published_at": v.published_at.isoformat() if v.published_at else None,
            "url": v.url,
        }
        for v in videos
    ]


@router.get("/videos/{video_id}", operation_id="get_video")
def get_video(video_id: str, request: Request) -> dict[str, Any]:
    """One video. Missing -> 404 naming the id requested."""
    video = db.fetch_video(_engine(request), video_id)
    if video is None:
        raise HTTPException(
            status_code=404,
            detail=f"video {video_id} not found in the library",
        )
    transcript = db.fetch_transcript(_engine(request), video_id)
    return {
        "video_id": video.video_id,
        "title": video.title,
        "duration_s": video.duration_s,
        "published_at": video.published_at.isoformat() if video.published_at else None,
        "url": video.url,
        "has_transcript": transcript is not None,
        "transcript_source": str(transcript.source) if transcript else None,
        "segments": len(transcript.segments) if transcript else 0,
    }


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    data_dir: Path | None = None,
) -> FastAPI:
    """Build the app. Explicit parameters are for tests."""
    resolved = settings or get_settings()
    eng = engine or db.build_engine(resolved.database_url)
    db.create_schema(eng)
    db.seed(eng, data_dir or resolved.data_dir)

    app = FastAPI(
        title="Narathor",
        version="0.1.0",
        description="Mesin perangkai naskah short dari pustaka video sebuah channel YouTube.",
        dependencies=[Depends(require_soul)],
    )
    app.state.settings = resolved
    app.state.engine = eng
    app.include_router(router)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        """Reply with errors in a consistent shape."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.get("/healthz", include_in_schema=False, dependencies=[])
    def plain_health(_request: Request) -> JSONResponse:
        """Liveness check that does not touch the soul."""
        return JSONResponse({"status": "ok"})

    return app
