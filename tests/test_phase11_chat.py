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

    def start(self, kind: str, label: str, work) -> Any:
        job = type(
            "FakeJob",
            (),
            {"job_id": f"job-{kind}", "kind": kind, "label": label, "work": work},
        )()
        self.started.append({"kind": kind, "label": label, "job": job})
        return job


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
