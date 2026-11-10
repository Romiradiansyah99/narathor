"""Backend API. The only door to the data."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.engine import Engine

from backend import chat, db, skills, soul, ui
from backend.config import Settings, get_settings
from backend.jobs import Job, Registry
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


def _as_channel_url(value: str) -> str:
    """Accept @handle or a bare handle where the brief contract wants a URL."""
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if cleaned.startswith("@"):
        return f"https://www.youtube.com/{cleaned}"
    if "." in cleaned:
        return f"https://{cleaned}"
    return f"https://www.youtube.com/@{cleaned}"


def _jobs(request: Request) -> Registry:
    """Job registry owned by the app."""
    return request.app.state.jobs


@router.get("/state", operation_id="state")
def state(request: Request) -> dict[str, Any]:
    """Everything the console needs to draw its first screen."""
    settings = _settings(request)
    engine = _engine(request)
    check = soul.verify(settings.soul_path, settings.soul_lock_path)
    channel = db.fetch_channel(engine)
    videos = db.fetch_videos(engine)
    transcripts = sum(1 for v in videos if db.fetch_transcript(engine, v.video_id) is not None)
    scripts = len(list(settings.output_dir.glob("*/*/scripts/*.json")))
    return {
        "soul": {"version": check.version, "ok": check.ok},
        "channel": channel.model_dump(mode="json") if channel else None,
        "videos": len(videos),
        "transcripts": transcripts,
        "briefs": len(briefs_load.list_ids(settings.briefs_dir)),
        "briefs_existing": briefs_load.list_ids(settings.briefs_dir),
        "scripts": scripts,
    }


@router.post("/channels", operation_id="discover_channel")
def discover_channel(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Read a channel's video tab into the library. Returns a job id to poll."""
    from ingest.channel import discover

    engine = _engine(request)
    url = str(payload.get("url") or "").strip()
    limit = int(payload.get("limit") or 25)
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    def work(log) -> dict[str, Any]:
        channel, videos = discover(url, limit=limit, log=log)
        log(f"saving {len(videos)} videos under channel {channel.channel_id}")
        counts = db.save_library(engine, channel, videos)
        log(f"library now {counts['videos']} new videos")
        return {
            "channel": channel.model_dump(mode="json"),
            "listed": len(videos),
            "saved": counts,
        }

    job: Job = _jobs(request).start("channel", f"channel {url}", work)
    return {"job_id": job.job_id, "status": job.status}


@router.post("/briefs", operation_id="save_brief")
def save_brief(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Validate a brief from the console and write it. Rejections are the answer."""
    settings = _settings(request)
    raw = dict(payload)
    brief_id = str(raw.get("id") or "").strip()
    if not brief_id:
        raise HTTPException(status_code=400, detail={"message": "id is required"})
    sources = raw.get("sources")
    if isinstance(sources, dict):
        channels = sources.get("channels")
        if isinstance(channels, list):
            sources["channels"] = [_as_channel_url(str(c)) for c in channels]
    report = briefs_load.validate(brief_id, raw)
    if report.brief is None:
        raise HTTPException(
            status_code=400,
            detail={
                "brief_id": brief_id,
                "message": report.render(),
                "rejections": [{"code": r.code, "message": r.message} for r in report.rejections],
            },
        )
    path = briefs_load.brief_path(settings.briefs_dir, brief_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {
        "brief_id": brief_id,
        "brief_hash": briefs_load.brief_hash(report.brief),
        "rejections": [],
    }


@router.post("/ingest", operation_id="start_ingest")
def start_ingest(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Fetch transcripts for the brief's library. Captions first, Whisper second."""
    from ingest.pipeline import DbStore, default_fetchers
    from ingest.pipeline import run as run_ingest

    settings = _settings(request)
    engine = _engine(request)
    brief_id = str(payload.get("brief_id") or "").strip()
    limit = int(payload.get("limit") or 0)
    force = bool(payload.get("force"))
    if not brief_id:
        raise HTTPException(status_code=400, detail="brief_id is required")
    brief = briefs_load.load_or_raise(settings.briefs_dir, brief_id)

    def work(log) -> dict[str, Any]:
        class LoggingStore(DbStore):
            """DbStore that reports every transcript it writes."""

            def put(self, doc) -> None:
                super().put(doc)
                log(f"{doc.video_id}: {doc.source} / {len(doc.segments)} segments")

        videos = [
            v for v in db.fetch_videos(engine) if v.duration_s >= brief.sources.min_duration_s
        ]
        if limit:
            videos = videos[:limit]
        if not videos:
            raise RuntimeError("library is empty for this brief: fetch a channel first")
        log(f"{len(videos)} videos to fetch, minimum {brief.sources.min_duration_s}s")
        captions_fetcher, whisper_fetcher = default_fetchers()
        store = LoggingStore(engine)
        report = run_ingest(videos, store, captions_fetcher, whisper_fetcher, force=force)
        data = report.as_dict()
        for video_id in report.cached:
            log(f"{video_id}: cache hit")
        for video_id in report.skipped:
            log(f"{video_id}: skipped, {report.errors.get(video_id, 'no transcript')}")
        blocked = sum(1 for e in report.errors.values() if "Blocked" in e)
        if blocked:
            log("")
            log("youtube refused this machine, not the videos.")
            log("the fix: a cookies file from a logged in browser, a residential proxy,")
            log("or run ingest from a normal connection.")
        log(
            f"ingested {len(report.ingested)} / cached {len(report.cached)} / skipped {len(report.skipped)}"
        )
        return data

    job = _jobs(request).start("ingest", f"ingest {brief_id}", work)
    return {"job_id": job.job_id, "status": job.status}


@router.post("/runs", operation_id="start_run")
def start_run(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Assemble scripts from the indexed library. This is the long one."""
    from narathor.run import orchestrate

    settings = _settings(request)
    engine = _engine(request)
    brief_id = str(payload.get("brief_id") or "").strip()
    count = int(payload.get("count") or 0) or None
    if not brief_id:
        raise HTTPException(status_code=400, detail="brief_id is required")
    briefs_load.load_or_raise(settings.briefs_dir, brief_id)

    def work(log) -> dict[str, Any]:
        log(f"brief {brief_id}, {count or 'brief default'} scripts")
        summary = orchestrate(brief_id, settings=settings, engine=engine, count=count)
        log(f"run {summary['run_id']}: {summary['scripts']} scripts from {summary['cards']} cards")
        log(f"artefacts in {summary['output']}")
        for video_id in summary.get("deferred", []):
            log(f"{video_id}: deferred")
        return summary

    job = _jobs(request).start("run", f"run {brief_id}", work)
    return {"job_id": job.job_id, "status": job.status}


@router.get("/jobs", operation_id="list_jobs")
def list_jobs(request: Request) -> list[dict[str, Any]]:
    """Recent jobs, newest first."""
    return [job.as_dict() for job in _jobs(request).list()]


@router.get("/jobs/{job_id}", operation_id="get_job")
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """One job with its log."""
    job = _jobs(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return job.as_dict()


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
    app.state.jobs = Registry(log_dir=resolved.output_dir / "_jobs")
    app.state.chat = chat.Chat(resolved, eng, app.state.jobs)
    app.include_router(router)

    def warm() -> None:
        """Pay the provider's connection setup once, off the request path."""
        import sys

        if os.environ.get("NARATHOR_CHAT_MODEL", "").strip().lower() in {"off", "0", "no"}:
            return
        if "pytest" in sys.modules:
            return
        try:
            app.state.chat.model()
            from agent.models import for_role

            for_role("router").complete("ok", system="balas: ok")
        except Exception:
            pass

    threading.Thread(target=warm, daemon=True, name="warm-model").start()

    token = os.environ.get("NARATHOR_UI_TOKEN", "").strip()

    @app.middleware("http")
    async def gate(request: Request, call_next):
        """One shared token keeps the tunnel private without an account system."""
        if not token or request.url.path == "/healthz":
            return await call_next(request)
        supplied = request.query_params.get("t") or request.cookies.get("nt")
        if supplied != token:
            return HTMLResponse(
                '<body style="background:#000;color:#fff;font:14px ui-monospace;padding:40px">'
                "401 unauthorised. open the console with ?t=&lt;token&gt;</body>",
                status_code=401,
            )
        response = await call_next(request)
        if request.query_params.get("t") == token:
            response.set_cookie(
                "nt", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
            )
        return response

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def console() -> HTMLResponse:
        """The console page: a prompt, and whatever it has said so far."""
        return HTMLResponse(ui.page())

    @app.get("/api/skills", operation_id="list_skills")
    def list_skills() -> dict[str, Any]:
        """The slash menu. Same list the chat answers with, so they cannot drift."""
        return {"skills": skills.catalogue()}

    @app.post("/api/chat", operation_id="chat_turn")
    def chat_turn(payload: dict[str, Any], request: Request, response: Response) -> dict[str, Any]:
        """One message in, one answer out, plus the job it started if any."""
        service: chat.Chat = request.app.state.chat
        sid = request.cookies.get("nsid") or uuid.uuid4().hex[:20]
        data = service.handle(
            sid,
            message=payload.get("message"),
            advance=bool(payload.get("advance")),
        )
        response.set_cookie("nsid", sid, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
        return data

    @app.get("/api/chat/history", operation_id="chat_history")
    def chat_history(request: Request, response: Response) -> dict[str, Any]:
        """Everything said in this session, for a page that just opened."""
        service: chat.Chat = request.app.state.chat
        sid = request.cookies.get("nsid") or uuid.uuid4().hex[:20]
        response.set_cookie("nsid", sid, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
        return service.history(sid)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        """Reply with errors in a consistent shape."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(briefs_load.BriefRejected)
    async def brief_error(_request: Request, exc: briefs_load.BriefRejected) -> JSONResponse:
        """A rejected brief is a client error with the reasons attached."""
        return JSONResponse(
            status_code=400,
            content={
                "detail": {
                    "message": exc.report.render(),
                    "rejections": [
                        {"code": r.code, "message": r.message} for r in exc.report.rejections
                    ],
                }
            },
        )

    @app.get("/healthz", include_in_schema=False, dependencies=[])
    def plain_health(_request: Request) -> JSONResponse:
        """Liveness check that does not touch the soul."""
        return JSONResponse({"status": "ok"})

    return app
