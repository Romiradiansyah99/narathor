"""Phase 12: the slash menu and the conversation's own library."""

from __future__ import annotations

from typing import Any

import pytest

from backend import chat, db, skills


class FakeJobs:
    """Registry that records a job instead of running it."""

    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.jobs: dict[str, Any] = {}

    def start(self, kind: str, label: str, work) -> Any:
        job = type(
            "FakeJob",
            (),
            {
                "job_id": f"job-{kind}-{len(self.started)}",
                "kind": kind,
                "status": "running",
                "result": {},
                "error": None,
            },
        )()
        self.jobs[job.job_id] = job
        self.started.append({"kind": kind, "job": job})
        return job

    def get(self, job_id: str) -> Any:
        return self.jobs.get(job_id)


class FakeChannel:
    """Only the fields chat reads."""

    channel_id = "CH-1"
    name = "Channel_Uji"
    handle = "@uji"
    url = "https://www.youtube.com/@uji"


def _video(video_id: str) -> Any:
    return type("V", (), {"video_id": video_id, "duration_s": 600})()


def _service(
    settings,
    monkeypatch: pytest.MonkeyPatch,
    videos: list[Any] | None = None,
    transcripts: int = 0,
) -> tuple[chat.Chat, FakeJobs]:
    rows = videos or []
    monkeypatch.setattr(chat.db, "fetch_channel_by_id", lambda _e, _c: FakeChannel())
    monkeypatch.setattr(chat.db, "fetch_channel_by_url", lambda _e, _u: FakeChannel())
    monkeypatch.setattr(chat.db, "fetch_channels", lambda _e: [FakeChannel()])
    monkeypatch.setattr(chat.db, "fetch_videos_for_channel", lambda _e, _c: rows)
    monkeypatch.setattr(
        chat.db,
        "fetch_transcript",
        lambda _e, vid: object() if vid in {v.video_id for v in rows[:transcripts]} else None,
    )
    jobs = FakeJobs()
    return (
        chat.Chat(settings=settings, engine=object(), jobs=jobs, llm=lambda _p: "{}"),
        jobs,
    )


def test_catalogue_is_unique_and_ordered() -> None:
    entries = skills.catalogue()
    names = [entry["name"] for entry in entries]
    assert len(names) == len(set(names))
    assert names[0] == "/channel"
    assert all(entry["about"] for entry in entries)


def test_every_skill_has_a_handler() -> None:
    for skill in skills.SKILLS:
        assert hasattr(chat.Chat, f"_cmd_{skill.name}"), skill.name


def test_help_lists_the_catalogue(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch)
    answer = service.handle("abc", "/help")
    assert any("/channel" in line for line in answer["reply"])
    assert answer["job_id"] is None


def test_unknown_skill_says_so(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch)
    answer = service.handle("abc", "/terbang ke bulan")
    assert "nggak ada" in answer["reply"][0]
    assert any("/status" in line for line in answer["reply"])


def test_status_before_a_channel_claims_nothing(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch, videos=[_video("V1")], transcripts=1)
    answer = service.handle("abc", "/status")
    assert "belum ada channel" in answer["reply"][0]


def test_status_counts_only_this_conversation(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(
        settings, monkeypatch, videos=[_video("V1"), _video("V2")], transcripts=1
    )
    service.handle("abc", "/channel https://www.youtube.com/@uji")
    answer = service.handle("abc", "/status")
    assert "2 video" in answer["reply"][0]
    assert "1 transkrip" in answer["reply"][0]


def test_channel_skill_starts_the_job(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _service(settings, monkeypatch)
    answer = service.handle("abc", "/channel @uji")
    assert answer["job_kind"] == "channel"
    assert jobs.started[0]["kind"] == "channel"


def test_channel_skill_without_argument_shows_the_shape(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, jobs = _service(settings, monkeypatch)
    answer = service.handle("abc", "/channel")
    assert "pakai" in answer["reply"][0]
    assert jobs.started == []


def test_topic_and_audience_are_slots(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch)
    service.handle("abc", "/topik uang masuk dan pergi")
    service.handle("abc", "/audiens pekerja muda")
    brief = service.handle("abc", "/brief")
    joined = " ".join(brief["reply"])
    assert "uang masuk dan pergi" in joined
    assert "pekerja muda" in joined


def test_naskah_without_transcripts_refuses(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _service(settings, monkeypatch, videos=[_video("V1")])
    service.handle("abc", "/channel @uji")
    answer = service.handle("abc", "/naskah")
    assert any("transkrip" in line for line in answer["reply"])
    assert jobs.started[0]["kind"] == "channel"


def test_naskah_without_topic_asks_for_one(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch, videos=[_video("V1")], transcripts=1)
    service.handle("abc", "/channel @uji")
    answer = service.handle("abc", "/naskah")
    assert any("/topik" in line for line in answer["reply"])


def test_cookies_skill_explains_the_paste(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch)
    answer = service.handle("abc", "/cookies")
    assert any("tempel" in line for line in answer["reply"])


def test_reset_clears_the_conversation(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch)
    service.handle("abc", "/topik uang")
    service.handle("abc", "/reset")
    assert service.store.load("abc").slots == {}


def test_doctor_reports_the_checks(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _service(settings, monkeypatch)
    answer = service.handle("abc", "/doctor")
    joined = " ".join(answer["reply"])
    assert "api key" in joined
    assert "soul" in joined


def test_advance_after_a_channel_command_continues_to_ingest(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that starts a job must be resumable, like any other work."""
    service, jobs = _service(settings, monkeypatch, videos=[_video("V1")])
    first = service.handle("abc", "/channel @uji")
    job = jobs.jobs[first["job_id"]]
    job.status = "done"
    job.result = {"channel": "Channel_Uji", "channel_id": "CH-1", "videos": 1}

    second = service.handle("abc", advance=True)
    assert second["job_kind"] == "ingest"
    assert any("video masuk" in line for line in second["reply"])


def test_the_chain_stops_when_the_ingest_is_finished(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two advances must not start the same ingest twice."""
    service, jobs = _service(settings, monkeypatch, videos=[_video("V1")])
    first = service.handle("abc", "/channel @uji")
    channel_job = jobs.jobs[first["job_id"]]
    channel_job.status = "done"
    channel_job.result = {"channel": "Channel_Uji", "channel_id": "CH-1", "videos": 1}

    second = service.handle("abc", advance=True)
    ingest_job = jobs.jobs[second["job_id"]]
    ingest_job.status = "done"
    ingest_job.result = {"ingested": [], "cached": [], "skipped": ["V1"], "blocked": 1}

    third = service.handle("abc", advance=True)
    assert third["job_id"] is None
    assert any("cookies" in line for line in third["reply"])
    assert len(jobs.started) == 2


def test_skills_endpoint_matches_the_registry(client) -> None:
    payload = client.get("/api/skills").json()
    assert [item["name"] for item in payload["skills"]] == [
        entry["name"] for entry in skills.catalogue()
    ]
    assert payload["skills"][0]["takes_args"] is True


def test_the_page_has_no_placeholder_and_keeps_the_line_in_the_corner(client) -> None:
    page = client.get("/").text
    assert "tulis apa aja" not in page
    assert "<header>attention is all you need</header>" in page
    assert "api/skills" in page


# --------------------------------------------------------------------------- #
# Finding a channel from whatever was typed
# --------------------------------------------------------------------------- #


def test_fetch_channel_by_url_matches_the_shapes_people_paste(engine) -> None:
    db.create_schema(engine)
    db.ensure_ready(engine)
    channel = db.fetch_channel(engine)
    assert channel is not None
    handle = channel.handle.lstrip("@")
    for typed in (
        channel.url,
        f"{channel.url}/videos",
        channel.handle,
        f"@{handle.upper()}",
        f"youtube.com/@{handle}",
    ):
        found = db.fetch_channel_by_url(engine, typed)
        assert found is not None, typed
        assert found.channel_id == channel.channel_id


def test_fetch_videos_for_channel_ignores_other_channels(engine) -> None:
    db.create_schema(engine)
    db.ensure_ready(engine)
    channel = db.fetch_channel(engine)
    assert channel is not None
    mine = db.fetch_videos_for_channel(engine, channel.channel_id)
    assert mine
    assert db.fetch_videos_for_channel(engine, "CH-TIDAK-ADA") == []


# --------------------------------------------------------------------------- #
# Which model answers the chat
# --------------------------------------------------------------------------- #


def test_the_chat_runs_on_the_router_role(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The conversational brain must be the router, not the writer."""
    from agent import models as agent_models

    asked: list[str] = []
    monkeypatch.setattr(
        agent_models, "for_role", lambda role: asked.append(role) or agent_models.StubModel("{}")
    )
    _service(settings, monkeypatch)
    bare = chat.Chat(settings=settings, engine=object(), jobs=FakeJobs(), llm=None)
    bare.model()
    assert asked == ["router"]


def test_the_router_gets_a_smaller_budget_than_the_writer() -> None:
    from agent.models import ROLE_LIMITS

    assert ROLE_LIMITS["router"]["max_completion_tokens"] <= 200
    assert ROLE_LIMITS["router"]["timeout"] <= 8.0


def test_the_router_is_the_fast_variant() -> None:
    from backend.config import DEFAULT_MODELS

    assert "ultrafast" in DEFAULT_MODELS["router"] or "fast" in DEFAULT_MODELS["router"]


def test_an_empty_router_answer_is_asked_again(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider sometimes returns an empty body. One retry saves the reply."""
    answers = ["", '{"say": "jawaban kedua", "tool": null, "args": {}}']

    def llm(_prompt: str) -> str:
        return answers.pop(0) if answers else ""

    _service(settings, monkeypatch)
    service = chat.Chat(settings=settings, engine=object(), jobs=FakeJobs(), llm=llm)
    plan = service._think(chat.Session(sid="abc"), llm)
    assert plan is not None
    assert plan["say"] == "jawaban kedua"
