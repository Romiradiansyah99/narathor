"""Phase 11: the chat. Reading a message, asking one question, starting work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend import chat
from briefs import load as briefs_load


class FakeJobs:
    """Registry that records a job instead of running it."""

    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.jobs: dict[str, Any] = {}

    def start(self, kind: str, label: str, work) -> Any:
        job_id = f"job-{kind}-{len(self.started)}"
        job = type(
            "FakeJob",
            (),
            {
                "job_id": job_id,
                "kind": kind,
                "label": label,
                "work": work,
                "status": "running",
                "result": {},
                "error": None,
            },
        )()
        self.jobs[job_id] = job
        self.started.append({"kind": kind, "label": label, "job": job})
        return job

    def get(self, job_id: str) -> Any:
        return self.jobs.get(job_id)


class FakeChannel:
    """Only the fields chat reads."""

    def __init__(self, url: str = "https://www.youtube.com/@uji") -> None:
        self.url = url
        self.name = "Channel_Uji"


def _patch_db(
    monkeypatch: pytest.MonkeyPatch,
    channel: Any = None,
    videos: list[Any] | None = None,
    transcripts: int = 0,
) -> None:
    rows = videos or []
    monkeypatch.setattr(chat.db, "fetch_channel", lambda _engine: channel)
    monkeypatch.setattr(chat.db, "fetch_videos", lambda _engine: rows)
    monkeypatch.setattr(
        chat.db,
        "fetch_transcript",
        lambda _engine, video_id: object() if video_id in {v.video_id for v in rows} else None,
    )
    if transcripts == 0:
        monkeypatch.setattr(chat.db, "fetch_transcript", lambda _engine, _vid: None)
    elif transcripts < len(rows):
        keep = {v.video_id for v in rows[:transcripts]}
        monkeypatch.setattr(
            chat.db,
            "fetch_transcript",
            lambda _engine, video_id: object() if video_id in keep else None,
        )


def _video(video_id: str) -> Any:
    return type("V", (), {"video_id": video_id, "duration_s": 600})()


# --------------------------------------------------------------------------- #
# Reading a message
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "key", "expected"),
    [
        ("https://www.youtube.com/@frugal", "channel_url", "https://www.youtube.com/@frugal"),
        ("youtube.com/@frugal", "channel_url", "https://youtube.com/@frugal"),
        ("coba @frugal aja", "channel_url", "https://www.youtube.com/@frugal"),
        ("bikin 12 naskah", "count", 12),
        ("durasi 20 detik", "duration", 20),
    ],
)
def test_extract_rules_reads_the_obvious(text: str, key: str, expected: Any) -> None:
    assert chat.extract_rules(text)[key] == expected


def test_extract_rules_takes_topic_and_audience() -> None:
    found = chat.extract_rules("bikin naskah soal burnout kerja buat anak magang, tone santai")
    assert found["topic"].startswith("burnout kerja")
    assert found["audience"].startswith("anak magang")
    assert found["tone"] == "santai"


def test_understand_prefers_rules_over_the_model() -> None:
    def llm(_prompt: str) -> str:
        return '{"channel_url": "https://youtube.com/@salah", "topic": "dari model"}'

    found = chat.understand("soal uang buat mahasiswa https://youtube.com/@benar", llm)
    assert found["channel_url"] == "https://youtube.com/@benar"
    assert found["topic"] in {"uang buat mahasiswa", "uang"}


def test_understand_survives_a_dead_model() -> None:
    def llm(_prompt: str) -> str:
        raise RuntimeError("model down")

    assert chat.understand("soal uang", llm)["topic"] == "uang"


def test_understand_ignores_model_noise() -> None:
    assert chat.understand("halo", lambda _prompt: "bukan json") == {}


# --------------------------------------------------------------------------- #
# Slots into a brief
# --------------------------------------------------------------------------- #


def test_compose_brief_passes_the_validator() -> None:
    slots = {
        "channel_url": "https://www.youtube.com/@uji",
        "topic": "kenapa gaji muda habis",
        "message": "bukan soal jumlah, tapi ke mana uang pergi",
        "audience": "pekerja muda",
        "tone": "santai",
        "count": 4,
        "duration": 15,
    }
    brief_id, payload = chat.compose_brief(slots)
    report = briefs_load.validate(brief_id, payload)
    assert report.ok, report.render()
    assert report.brief is not None
    assert report.brief.output.scripts == 4


def test_compose_brief_clamps_impossible_numbers() -> None:
    payload = chat.compose_brief(
        {"channel_url": "https://www.youtube.com/@uji", "topic": "x", "count": 99, "duration": 30}
    )[1]
    assert payload["output"]["scripts"] == 20
    assert payload["output"]["target_duration_s"] == 15


def test_compose_brief_keeps_sixty_seconds() -> None:
    payload = chat.compose_brief(
        {"channel_url": "https://www.youtube.com/@uji", "topic": "x", "duration": 60}
    )[1]
    assert payload["output"]["target_duration_s"] == 60


# --------------------------------------------------------------------------- #
# The conversation
# --------------------------------------------------------------------------- #


def _chat(settings, monkeypatch: pytest.MonkeyPatch, **state: Any) -> tuple[chat.Chat, FakeJobs]:
    _patch_db(
        monkeypatch,
        channel=state.get("channel"),
        videos=state.get("videos"),
        transcripts=state.get("transcripts", 0),
    )
    jobs = FakeJobs()
    return chat.Chat(settings=settings, engine=object(), jobs=jobs, llm=lambda _p: "{}"), jobs


def _fast_chat(
    settings, monkeypatch: pytest.MonkeyPatch, **state: Any
) -> tuple[chat.Chat, FakeJobs, list[str]]:
    """A chat whose model records every call, so the fast path can be proven silent."""
    _patch_db(
        monkeypatch,
        channel=state.get("channel"),
        videos=state.get("videos"),
        transcripts=state.get("transcripts", 0),
    )
    calls: list[str] = []

    def llm(prompt: str) -> str:
        calls.append(prompt)
        return "{}"

    jobs = FakeJobs()
    return (
        chat.Chat(settings=settings, engine=object(), jobs=jobs, llm=llm),
        jobs,
        calls,
    )


def test_a_url_never_waits_for_the_model(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs, calls = _fast_chat(settings, monkeypatch, channel=FakeChannel("@lama"))
    answer = service.handle("abc", "coba https://www.youtube.com/@baru")
    assert answer["job_kind"] == "channel"
    assert calls == []
    assert jobs.started[0]["kind"] == "channel"


def test_a_greeting_is_answered_from_the_library(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs, calls = _fast_chat(
        settings,
        monkeypatch,
        channel=FakeChannel(),
        videos=[_video("VID-0001")],
        transcripts=1,
    )
    answer = service.handle("abc", "halo")
    assert "transkrip" in answer["reply"][0]
    assert calls == []


def test_a_spelled_out_brief_never_waits_for_the_model(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, jobs, calls = _fast_chat(
        settings,
        monkeypatch,
        channel=FakeChannel(),
        videos=[_video("VID-0001")],
        transcripts=1,
    )
    answer = service.handle("abc", "bikin 2 naskah soal uang buat pekerja muda, tone santai")
    assert answer["job_kind"] == "run"
    assert calls == []
    assert jobs.started[0]["kind"] == "run"


def test_a_product_question_is_answered_without_the_model(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _jobs, calls = _fast_chat(settings, monkeypatch, channel=FakeChannel())
    answer = service.handle("abc", "ini bisa dipake buat apa?")
    assert "naskah" in answer["reply"][0]
    assert calls == []


def test_an_open_question_still_reaches_the_model(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _jobs, calls = _fast_chat(settings, monkeypatch, channel=FakeChannel())
    service.handle("abc", "menurut kamu kenapa orang susah nabung?")
    assert calls


def test_first_message_asks_for_a_channel(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _chat(settings, monkeypatch)
    answer = service.handle("abc", "halo")
    assert any("channel" in line for line in answer["reply"])
    assert jobs.started == []


def test_existing_channel_means_it_asks_for_a_topic(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, jobs = _chat(
        settings,
        monkeypatch,
        channel=FakeChannel(),
        videos=[_video("VID-0001")],
        transcripts=1,
    )
    answer = service.handle("abc", "halo")
    assert any("soal apa" in line for line in answer["reply"])
    assert jobs.started == []


def test_a_new_url_starts_a_channel_job(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _chat(settings, monkeypatch, channel=FakeChannel("@lama"))
    answer = service.handle("abc", "coba https://www.youtube.com/@baru")
    assert answer["job_kind"] == "channel"
    assert jobs.started[0]["kind"] == "channel"


def test_missing_transcripts_start_an_ingest_job(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _chat(
        settings,
        monkeypatch,
        channel=FakeChannel(),
        videos=[_video("VID-0001"), _video("VID-0002")],
        transcripts=0,
    )
    service.handle("abc", "bikin naskah soal uang")
    assert jobs.started[0]["kind"] == "ingest"


def test_ready_library_starts_a_run_job(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _chat(
        settings,
        monkeypatch,
        channel=FakeChannel(),
        videos=[_video("VID-0001")],
        transcripts=1,
    )
    answer = service.handle("abc", "bikin 2 naskah soal uang buat pekerja muda")
    assert answer["job_kind"] == "run"
    assert jobs.started[0]["kind"] == "run"
    session = service.store.load("abc")
    assert session.brief_id and (settings.briefs_dir / f"{session.brief_id}.yaml").exists()


def test_advance_after_a_run_does_not_start_it_again(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, jobs = _chat(
        settings, monkeypatch, channel=FakeChannel(), videos=[_video("VID-0001")], transcripts=1
    )
    service.handle("abc", "bikin 2 naskah soal uang")
    assert job_kinds(jobs) == ["run"]
    answer = service.handle("abc", advance=True)
    assert answer["job_id"] is None
    assert job_kinds(jobs) == ["run"]


def test_a_second_ingest_is_not_started_twice(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, jobs = _chat(settings, monkeypatch, channel=FakeChannel(), videos=[_video("VID-0001")])
    service.handle("abc", "bikin naskah soal uang")
    assert job_kinds(jobs) == ["ingest"]
    answer = service.handle("abc", advance=True)
    assert answer["job_id"] is None
    assert any("youtube nolak mesin ini" in line for line in answer["reply"])


def job_kinds(jobs: FakeJobs) -> list[str]:
    """Kinds of the jobs that were started, in order."""
    return [entry["kind"] for entry in jobs.started]


def test_reset_forgets_everything(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _chat(settings, monkeypatch)
    service.handle("abc", "soal uang")
    answer = service.handle("abc", "reset")
    assert "lupa" in answer["reply"][0]
    assert service.store.load("abc").slots == {}


def test_history_returns_what_was_said(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _chat(settings, monkeypatch)
    service.handle("abc", "halo")
    history = service.history("abc")
    assert history["messages"][0] == {"role": "user", "text": "halo"}


# --------------------------------------------------------------------------- #
# Printing
# --------------------------------------------------------------------------- #


def test_format_scripts_renders_timecodes_and_citations(tmp_path: Path) -> None:
    doc = {
        "title": "Bukan Jumlah",
        "target_duration_s": 15,
        "beats": [
            {
                "at_s": 0,
                "text": "Masalahnya bukan berapa yang masuk.",
                "citation": {"video_id": "VID-0001", "t0": 0.0, "t1": 4.5},
            },
            {"at_s": 75, "text": "Tutup.", "citation": None},
        ],
    }
    path = tmp_path / "script.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    text = chat.format_scripts([path])
    assert "naskah 1 — Bukan Jumlah" in text
    assert "00:00  Masalahnya" in text
    assert "VID-0001 0.0-4.5s" in text
    assert "01:15" in text


def test_library_hints_name_what_the_transcripts_talk_about(client) -> None:
    hints = chat.library_hints(client.app.state.engine)
    assert isinstance(hints, list)
    assert hints


# --------------------------------------------------------------------------- #
# The agent loop
# --------------------------------------------------------------------------- #


class ScriptedModel:
    """A model that answers with a fixed list of replies, in order."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else "{}"


def _agent(settings, monkeypatch: pytest.MonkeyPatch, model: ScriptedModel, **state: Any):
    _patch_db(
        monkeypatch,
        channel=state.get("channel"),
        videos=state.get("videos"),
        transcripts=state.get("transcripts", 0),
    )
    jobs = FakeJobs()
    return chat.Chat(settings=settings, engine=object(), jobs=jobs, llm=model), jobs


def test_parse_plan_reads_a_tool_call() -> None:
    plan = chat.parse_plan('{"say": "gas", "tool": "ingest", "args": {"limit": 5}}')
    assert plan == {"say": "gas", "tool": "ingest", "args": {"limit": 5}}


def test_parse_plan_treats_none_as_talk_only() -> None:
    plan = chat.parse_plan('{"say": "halo", "tool": "none", "args": {}}')
    assert plan is not None
    assert plan["tool"] is None


def test_parse_plan_rejects_prose() -> None:
    assert chat.parse_plan("tentu, saya akan membantu") is None


def test_agent_says_what_the_model_said(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel('{"say": "channel mana nih?", "tool": null, "args": {}}')
    service, jobs = _agent(settings, monkeypatch, model)
    answer = service.handle("abc", "menurut kamu channel ini cocok buat topik apa?")
    assert answer["reply"] == ["channel mana nih?"]
    assert jobs.started == []


def test_agent_starts_the_tool_it_asked_for(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(
        '{"say": "siap, gue baca.", "tool": "fetch_channel", '
        '"args": {"url": "https://www.youtube.com/@baru"}}'
    )
    service, jobs = _agent(settings, monkeypatch, model)
    answer = service.handle("abc", "coba @baru")
    assert answer["job_kind"] == "channel"
    assert jobs.started[0]["kind"] == "channel"


def test_agent_sees_the_job_result_and_answers_again(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedModel(
        '{"say": "gue ambil transkripnya dulu.", "tool": "ingest", "args": {}}',
        '{"say": "transkripnya kosong, youtube nolak mesin ini.", "tool": null, "args": {}}',
    )
    service, jobs = _agent(
        settings,
        monkeypatch,
        model,
        channel=FakeChannel(),
        videos=[_video("VID-0001")],
    )
    first = service.handle("abc", "bikin naskah soal uang")
    assert first["job_kind"] == "ingest"
    job = jobs.jobs[first["job_id"]]
    job.status = "done"
    job.result = {"ingested": [], "cached": [], "skipped": ["VID-0001"], "blocked": 1}

    second = service.handle("abc", advance=True)
    assert second["reply"] == ["transkripnya kosong, youtube nolak mesin ini."]
    assert "diblokir youtube 1" in model.prompts[-1]


def test_agent_falls_back_when_the_model_talks_prose(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedModel("maaf, saya tidak bisa")
    service, _jobs = _agent(settings, monkeypatch, model)
    answer = service.handle("abc", "halo")
    assert any("channel" in line for line in answer["reply"])


def test_agent_does_not_restart_a_finished_assemble(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedModel(
        '{"say": "gue rangkai.", "tool": "assemble", "args": {"topic": "uang"}}',
        '{"say": "siap", "tool": "assemble", "args": {"topic": "uang"}}',
    )
    service, jobs = _agent(
        settings,
        monkeypatch,
        model,
        channel=FakeChannel(),
        videos=[_video("VID-0001")],
        transcripts=1,
    )
    first = service.handle("abc", "bikin naskah soal uang")
    assert first["job_kind"] == "run"
    jobs.jobs[first["job_id"]].status = "done"
    jobs.jobs[first["job_id"]].result = {"scripts": 1, "block": "naskah 1"}

    second = service.handle("abc", advance=True)
    assert second["job_id"] is None
    assert len(jobs.started) == 1


def test_agent_stops_after_three_tool_calls(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    call = '{"say": "lagi", "tool": "ingest", "args": {}}'
    model = ScriptedModel(call, call, call, call, call)
    service, jobs = _agent(
        settings, monkeypatch, model, channel=FakeChannel(), videos=[_video("V1")]
    )
    service.handle("abc", "tolong ambil transkripnya sekarang")
    for _ in range(4):
        last = service.handle("abc", advance=True)
        if last["job_id"] is None:
            break
        jobs.jobs[last["job_id"]].status = "done"
    assert len(jobs.started) == 3


COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc123\n"
    ".youtube.com\tTRUE\t/\tTRUE\t0\tHSID\tdef456\n"
)


def test_looks_like_cookies_separates_a_paste_from_a_sentence() -> None:
    assert chat.looks_like_cookies(COOKIES)
    assert not chat.looks_like_cookies("bikin naskah soal uang")


def test_a_pasted_cookie_file_is_saved_and_used(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs = _chat(
        settings, monkeypatch, channel=FakeChannel(), videos=[_video("VID-0001")], transcripts=1
    )
    answer = service.handle("abc", COOKIES)
    saved = settings.root / "cookies.txt"
    assert saved.exists()
    assert saved.read_text(encoding="utf-8").startswith("# Netscape")
    assert any("cookies" in line for line in answer["reply"])
    session = service.store.load("abc")
    assert session.messages[0]["text"] == "(cookies youtube ditempel)"


def test_session_store_roundtrips(tmp_path: Path) -> None:
    store = chat.SessionStore(tmp_path)
    session = chat.Session(sid="abc", slots={"topic": "uang"})
    session.messages.append({"role": "user", "text": "halo"})
    store.save(session)
    loaded = store.load("abc")
    assert loaded.slots == {"topic": "uang"}
    assert loaded.messages[0]["text"] == "halo"


def test_session_ids_are_sanitised(tmp_path: Path) -> None:
    store = chat.SessionStore(tmp_path)
    assert store.path("../../etc/passwd").parent == tmp_path


# --------------------------------------------------------------------------- #
# The endpoint
# --------------------------------------------------------------------------- #


def test_chat_endpoint_answers_and_sets_a_session_cookie(client) -> None:
    response = client.post("/api/chat", json={"message": "halo"})
    assert response.status_code == 200
    body = response.json()
    assert body["reply"]
    assert response.cookies.get("nsid")


def test_chat_history_is_empty_for_a_new_session(client) -> None:
    response = client.get("/api/chat/history")
    assert response.status_code == 200
    assert response.json()["messages"] == []
