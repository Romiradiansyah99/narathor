"""Phase 14: reading a channel's insides, not just its video count."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from backend import chat
from ingest import profile
from tests.test_phase11_chat import _fast_chat

# --------------------------------------------------------------------------- #
# The profile itself
# --------------------------------------------------------------------------- #


def _clip(title: str, seconds: int = 300, views: int = 1000) -> profile.Clip:
    return profile.Clip(video_id=title[:6], title=title, duration_s=seconds, views=views)


def _profile(**overrides: Any) -> profile.Profile:
    base: dict[str, Any] = {
        "channel_id": "CH-1",
        "name": "Warung Konten",
        "handle": "@warung",
        "url": "https://www.youtube.com/@warung/videos",
        "followers": 12_500,
        "description": "Channel soal uang dan kerja buat anak muda. " * 5,
        "tags": ["uang", "karier"],
        "clips": [
            _clip("Cara nabung buat anak muda", 240, 90_000),
            _clip("Kenapa gaji habis terus", 300, 120_000),
            _clip("Nabung vs investasi", 180, 40_000),
        ],
    }
    base.update(overrides)
    return profile.Profile(**base)


def test_human_counts_are_spoken_not_printed() -> None:
    assert profile.human(12_500) == "13 ribu"
    assert profile.human(1_200_000) == "1.2 juta"
    assert profile.human(28_000_000) == "28 juta"
    assert profile.human(950) == "950"


def test_duration_reads_like_a_clock() -> None:
    assert profile.duration(0) == "0:00"
    assert profile.duration(75) == "1:15"
    assert profile.duration(3725) == "1:02:05"


def test_overview_answers_what_is_inside() -> None:
    lines = profile.overview(_profile())
    text = " ".join(lines)
    assert "Warung Konten" in text
    assert "13 ribu subscriber" in text
    assert "format:" in text
    assert "paling laku" in text
    assert "Kenapa gaji habis terus" in text
    assert "deskripsi channel" in text


def test_overview_of_an_empty_channel_says_so() -> None:
    lines = profile.overview(_profile(clips=[]))
    assert "nggak ada video" in lines[0]


def test_keywords_need_to_repeat_to_count() -> None:
    """One video about bitcoin is not a theme; three about money are."""
    clips = [
        _clip("Uang dan kerja"),
        _clip("Uang dan waktu"),
        _clip("Uang dan pasar"),
        _clip("Bitcoin sekali doang"),
    ]
    words = profile.keywords(_profile(clips=clips), top=5)
    assert "uang" in words
    assert "bitcoin" not in words


def test_median_minutes_is_the_format() -> None:
    clips = [_clip("a", 60), _clip("b", 300), _clip("c", 900)]
    assert profile.median_minutes(_profile(clips=clips)) == 5.0


def test_profile_survives_a_round_trip_through_the_session() -> None:
    original = _profile()
    rebuilt = profile.Profile.from_dict(original.as_dict())
    assert rebuilt.name == original.name
    assert len(rebuilt.clips) == len(original.clips)
    assert rebuilt.clips[0].views == original.clips[0].views


def test_model_brief_is_compact_and_ranked_by_views() -> None:
    brief = profile.model_brief(_profile())
    assert "Warung Konten" in brief
    assert brief.index("Kenapa gaji habis terus") < brief.index("Nabung vs investasi")


# --------------------------------------------------------------------------- #
# Reading it from YouTube
# --------------------------------------------------------------------------- #


class _FakeYDL:
    """Just enough of yt-dlp to hand back a channel page."""

    payload: ClassVar[dict[str, Any]] = {}

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> _FakeYDL:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def extract_info(self, _target: str, download: bool = False) -> dict[str, Any]:
        return _FakeYDL.payload


def test_fetch_reads_views_durations_and_the_channel_blurb(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeYDL.payload = {
        "channel": "Warung Konten",
        "channel_id": "CH-1",
        "uploader_id": "@warung",
        "channel_follower_count": 12500,
        "description": "soal uang",
        "tags": ["uang"],
        "entries": [
            {"id": "v1", "title": "Cara nabung", "duration": 240, "view_count": 9000},
            {"id": "v2", "title": "Gaji habis", "duration": 300, "view_count": 12000},
            {"id": "v3", "title": "pendek", "duration": 10},
            {"id": None, "title": "rusak"},
        ],
    }
    monkeypatch.setattr("yt_dlp.YoutubeDL", _FakeYDL)
    result = profile.fetch("https://www.youtube.com/@warung")
    assert result.name == "Warung Konten"
    assert result.followers == 12500
    assert [clip.video_id for clip in result.clips] == ["v1", "v2"]
    assert result.clips[1].views == 12000


def test_fetch_turns_a_dead_youtube_into_a_channel_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken(_FakeYDL):
        def extract_info(self, _target: str, download: bool = False) -> dict[str, Any]:
            raise RuntimeError("HTTP Error 404")

    monkeypatch.setattr("yt_dlp.YoutubeDL", Broken)
    with pytest.raises(Exception, match="did not answer"):
        profile.fetch("https://www.youtube.com/@tidak-ada")


# --------------------------------------------------------------------------- #
# The console
# --------------------------------------------------------------------------- #


def _profile_slot() -> dict[str, Any]:
    return _profile().as_dict()


def test_a_finished_channel_job_stores_the_insides(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a fetch, the console knows what the channel contains, not just how many."""
    from tests.test_phase11_chat import FakeChannel, _video

    service, jobs, _calls = _fast_chat(
        settings,
        monkeypatch,
        channel=FakeChannel("https://www.youtube.com/@warung/videos"),
        videos=[_video("V1"), _video("V2"), _video("V3")],
    )
    job = jobs.start("channel", "channel @warung", lambda log: {})
    job.status = "done"
    job.result = {
        "channel": "Warung Konten",
        "channel_id": "CH-1",
        "videos": 3,
        "profile": _profile_slot(),
        "profile_lines": ["Warung Konten: 3 video kebaca, 13 ribu subscriber"],
        "profile_written": ["isinya soal uang", "formatnya pendek"],
    }
    service.store.save(
        chat.Session(
            sid="s",
            slots={"channel_url": "https://www.youtube.com/@warung/videos", "channel_id": "CH-1"},
            pending_job=job.job_id,
        )
    )

    reply = service.handle("s", advance=True)["reply"]
    text = " ".join(reply)
    assert "3 video masuk" in text
    assert "13 ribu subscriber" in text
    assert "isinya soal uang" in text

    slots = service.history("s")["slots"]
    assert slots["profile_lines"]
    assert slots["profile"]["name"] == "Warung Konten"


def test_isi_reads_the_stored_profile(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs, _calls = _fast_chat(settings, monkeypatch)
    session = chat.Session(sid="s", slots={"profile": _profile_slot()})
    service.store.save(session)
    reply = service.handle("s", "/isi")["reply"]
    text = " ".join(reply)
    assert "paling laku" in text
    assert "Warung Konten" in text


def test_isi_without_a_channel_says_so(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _jobs, _calls = _fast_chat(settings, monkeypatch)
    reply = service.handle("s", "/isi")["reply"]
    assert "belum ada" in reply[0]


def test_isi_still_works_when_no_model_is_available(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The facts are the point; the written read is a bonus, not the product."""
    monkeypatch.setenv("NARATHOR_PROFILE_MODEL", "off")
    service, _jobs, _calls = _fast_chat(settings, monkeypatch)
    service.store.save(chat.Session(sid="s", slots={"profile": _profile_slot()}))
    reply = service.handle("s", "/isi")["reply"]
    assert "paling laku" in " ".join(reply)


def test_the_menu_lists_cari_web_and_isi() -> None:
    from backend import skills

    names = {skill.name for skill in skills.SKILLS}
    assert {"cari", "web", "isi"} <= names


def test_a_known_channel_still_gets_its_insides_read(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The library already has the videos; this conversation still knows nothing about them."""
    from tests.test_phase11_chat import FakeChannel, _video

    service, _jobs, _calls = _fast_chat(
        settings, monkeypatch, channel=FakeChannel(), videos=[_video("V1")]
    )
    service.store.save(
        chat.Session(
            sid="s",
            slots={"channel_url": "https://www.youtube.com/@uji", "channel_id": "CH-1"},
        )
    )
    answer = service.handle("s", "gas")
    assert answer["job_kind"] == "profile"


def test_the_profile_is_read_once_per_conversation(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second message must not scrape the channel again."""
    from tests.test_phase11_chat import FakeChannel, _video

    service, jobs, _calls = _fast_chat(
        settings, monkeypatch, channel=FakeChannel(), videos=[_video("V1")]
    )
    session = chat.Session(
        sid="s",
        slots={
            "channel_url": "https://www.youtube.com/@uji",
            "channel_id": "CH-1",
            "profile": _profile_slot(),
            "profile_lines": ["Warung Konten: 3 video"],
        },
        profile_tried=True,
    )
    service.store.save(session)
    service.handle("s", "gas")
    assert "profile" not in [entry["kind"] for entry in jobs.started]


def test_an_early_poll_does_not_eat_the_job_result(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A poll that arrives before the job ends must wait, not throw the answer away."""
    service, jobs, _calls = _fast_chat(settings, monkeypatch)
    answer = service.handle("s", "https://youtube.com/@warung")
    early = service.handle("s", advance=True)
    assert early["pending"] is True
    assert early["reply"] == []
    assert early["job_id"] == answer["job_id"]

    job = jobs.jobs[answer["job_id"]]
    job.status = "done"
    job.result = {"channel": "Warung", "channel_id": "CH-1", "videos": 0}
    late = service.handle("s", advance=True)
    assert late.get("pending") is not True
    assert late["reply"]
