"""Phase 9: the console. Jobs, channel discovery, and the write endpoints."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from backend import ui
from backend.jobs import Registry
from ingest import channel as channel_mod
from tests.test_phase2_soul_briefs import VALID_BRIEF

BRIEF = {
    "id": "uang-arah",
    "title": "Uang bukan soal jumlah",
    "learning_outcome": "Bisa menunjuk satu kebocoran pengeluaran sendiri.",
    "thesis": "Masalah keuangan bukan soal jumlah pemasukan, tapi ke mana uang pergi.",
    "audience": {
        "primary": "pekerja muda jakarta",
        "literacy_level": "menengah",
        "pain_points": [],
    },
    "values_allowed": ["transparansi"],
    "values_blocked": ["fomo"],
    "register_level": 2,
    "tone": {"target": "tenang dan langsung", "avoid": ["menggurui"]},
    "seasonal_context": {"as_of": "2026-11-09", "period": None, "moments": [], "trend_notes": ""},
    "sources": {
        "channels": ["https://www.youtube.com/@uji"],
        "recency_preference": "any",
        "min_duration_s": 180,
    },
    "output": {"scripts": 1, "target_duration_s": 15, "language": "id", "montages": 0},
}


def _wait(client: TestClient, job_id: str, timeout: float = 3.0) -> dict:
    """Poll a job until it leaves the running state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["status"] in {"done", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


# --------------------------------------------------------------------------- #
# Job registry
# --------------------------------------------------------------------------- #


def test_job_runs_and_records_its_log(tmp_path: Path) -> None:
    registry = Registry(log_dir=tmp_path / "jobs")

    def work(log):
        log("first")
        log("second")
        return {"ok": True}

    job = registry.start("run", "demo", work)
    finished = _wait_on(registry, job.job_id)
    assert finished.status == "done"
    assert finished.log == ["first", "second"]
    assert finished.result == {"ok": True}
    assert (tmp_path / "jobs" / f"{job.job_id}.json").exists()


def test_job_failure_is_captured_not_raised(tmp_path: Path) -> None:
    registry = Registry(log_dir=tmp_path)

    def work(log):
        log("about to fail")
        raise RuntimeError("model said no")

    job = registry.start("ingest", "demo", work)
    finished = _wait_on(registry, job.job_id)
    assert finished.status == "failed"
    assert "model said no" in (finished.error or "")
    assert finished.log[-1].startswith("RuntimeError")


def test_registry_lists_newest_first(tmp_path: Path) -> None:
    registry = Registry(log_dir=tmp_path)
    first = registry.start("run", "one", lambda log: {"n": 1})
    _wait_on(registry, first.job_id)
    second = registry.start("run", "two", lambda log: {"n": 2})
    _wait_on(registry, second.job_id)
    assert [job.label for job in registry.list()] == ["two", "one"]
    assert registry.get("missing") is None


def _wait_on(registry: Registry, job_id: str, timeout: float = 3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = registry.get(job_id)
        if job and job.status in {"done", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


# --------------------------------------------------------------------------- #
# Channel discovery
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://www.youtube.com/@romi/videos", "https://www.youtube.com/@romi/videos"),
        ("youtube.com/@romi", "https://www.youtube.com/@romi/videos"),
        (
            "https://youtube.com/channel/UC123/featured",
            "https://www.youtube.com/channel/UC123/videos",
        ),
        ("https://www.youtube.com/c/NamaChannel", "https://www.youtube.com/c/NamaChannel/videos"),
    ],
)
def test_normalize_channel_url(given: str, expected: str) -> None:
    assert channel_mod.normalize(given) == expected


@pytest.mark.parametrize("bad", ["", "https://vimeo.com/x", "not a url at all"])
def test_normalize_rejects_non_channels(bad: str) -> None:
    with pytest.raises(channel_mod.ChannelError):
        channel_mod.normalize(bad)


class _FakeYDL:
    """Stand-in for yt_dlp.YoutubeDL, no network."""

    ENTRIES: ClassVar[list[dict]] = [
        {"id": "abc123", "title": "Video satu", "duration": 420, "upload_date": "20260901"},
        {"id": "def456", "title": "Video dua", "duration": 90, "upload_date": None},
        {"id": None, "title": "broken entry"},
    ]

    def __init__(self, options: dict) -> None:
        self.options = options

    def __enter__(self) -> _FakeYDL:
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def extract_info(self, url: str, download: bool = False) -> dict:
        assert download is False
        return {
            "channel_id": "UC-test",
            "channel": "Channel Uji",
            "uploader_id": "@uji",
            "entries": self.ENTRIES,
        }


class _FakeModule:
    """A yt_dlp module with just the one attribute discover() uses."""

    YoutubeDL = _FakeYDL


def test_discover_reads_the_video_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", _FakeModule())
    lines: list[str] = []
    channel, videos = channel_mod.discover("@uji", limit=5, log=lines.append)
    assert channel.channel_id == "UC-test"
    assert channel.handle == "@uji"
    assert [v.video_id for v in videos] == ["abc123", "def456"]
    assert videos[0].published_at is not None
    assert "2 videos listed" in lines[-1]


def test_discover_respects_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", _FakeModule())
    _channel, videos = channel_mod.discover("@uji", limit=1)
    assert len(videos) == 1


def test_discover_fails_loudly_when_youtube_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom(_FakeYDL):
        def extract_info(self, url: str, download: bool = False) -> dict:
            raise RuntimeError("sign in to confirm you are not a bot")

    class _BoomModule:
        YoutubeDL = _Boom

    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", _BoomModule())
    with pytest.raises(channel_mod.ChannelError, match="did not answer"):
        channel_mod.discover("@uji")


# --------------------------------------------------------------------------- #
# Console page
# --------------------------------------------------------------------------- #


def test_page_carries_the_boot_state() -> None:
    html = ui.page({"videos": 3, "channel": None, "soul": {"version": 2, "ok": True}})
    assert '"videos": 3' in html
    assert "Courier Prime" in html
    assert 'id="btn-run"' in html
    assert 'id="console"' in html


def test_page_escapes_dangerous_strings() -> None:
    html = ui.page({"channel": {"name": "</script><b>x"}})
    assert "</script><b>x" not in html
    assert "\\u003c" in html.lower() or "&lt;" in html.lower()


# --------------------------------------------------------------------------- #
# Write endpoints
# --------------------------------------------------------------------------- #


def test_console_page_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Assembly console" in response.text


def test_state_endpoint_reports_the_library(client: TestClient) -> None:
    payload = client.get("/api/state").json()
    assert payload["soul"]["ok"] is True
    assert payload["videos"] >= 1
    assert isinstance(payload["briefs_existing"], list)


def test_save_brief_writes_yaml(client: TestClient, settings) -> None:
    response = client.post("/api/briefs", json=BRIEF)
    assert response.status_code == 200
    assert len(response.json()["brief_hash"]) == 64
    written = settings.briefs_dir / "uang-arah.yaml"
    assert written.exists()
    assert "Masalah keuangan" in written.read_text(encoding="utf-8")


def test_save_brief_reports_a_rejection(client: TestClient) -> None:
    bad = dict(BRIEF, tone={"target": "bikin penasaran sampai akhir", "avoid": []})
    response = client.post("/api/briefs", json=bad)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["rejections"]
    assert "reject" in json.dumps(detail).lower() or detail["message"]


def test_save_brief_needs_an_id(client: TestClient) -> None:
    response = client.post("/api/briefs", json={"title": "no id"})
    assert response.status_code == 400


def test_channel_job_writes_the_library(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contracts import Channel, Video

    def fake_discover(url: str, limit: int = 25, log=None):
        if log:
            log("fake discovery")
        return (
            Channel(channel_id="UC-fake", name="Fake", handle="@fake", url=url),
            [
                Video(video_id="vid-1", title="One", duration_s=300, url=None),
                Video(video_id="vid-2", title="Two", duration_s=400, url=None),
            ],
        )

    monkeypatch.setattr("ingest.channel.discover", fake_discover)
    started = client.post("/api/channels", json={"url": "@fake", "limit": 5}).json()
    finished = _wait(client, started["job_id"])
    assert finished["status"] == "done", finished
    assert finished["result"]["listed"] == 2
    assert finished["log"][0] == "fake discovery"


def test_channel_endpoint_needs_a_url(client: TestClient) -> None:
    assert client.post("/api/channels", json={}).status_code == 400


def test_ingest_and_run_need_a_known_brief(client: TestClient, settings) -> None:
    (settings.briefs_dir / "uang-arah.yaml").write_text(VALID_BRIEF, encoding="utf-8")
    missing = client.post("/api/runs", json={"brief_id": "tidak-ada"})
    assert missing.status_code == 400
    assert client.post("/api/runs", json={}).status_code == 400
    assert client.post("/api/ingest", json={}).status_code == 400


def test_job_lookup_404(client: TestClient) -> None:
    assert client.get("/api/jobs/tidak-ada").status_code == 404
    assert client.get("/api/jobs").json() == []


def test_token_gate_blocks_without_the_token(
    settings, engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.main import create_app

    monkeypatch.setenv("NARATHOR_UI_TOKEN", "rahasia")
    app = create_app(settings=settings, engine=engine, data_dir=settings.data_dir)
    with TestClient(app) as gated:
        assert gated.get("/").status_code == 401
        with_token = gated.get("/?t=rahasia")
        assert with_token.status_code == 200
        assert with_token.cookies.get("nt") == "rahasia"
