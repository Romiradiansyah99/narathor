"""Test Fase 1: backend sisi baca."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.main import create_app
from tests.fixtures import FIXTURE_VIDEOS


def test_health_reports_library(client: TestClient) -> None:
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["videos"] == len(FIXTURE_VIDEOS)


def test_videos_returns_entire_library(client: TestClient) -> None:
    payload = client.get("/api/videos").json()
    assert len(payload) == len(FIXTURE_VIDEOS)
    for item in payload:
        assert {"video_id", "title", "duration_s"} <= set(item)


def test_missing_video_returns_404_naming_id(client: TestClient) -> None:
    response = client.get("/api/videos/VID-9999")
    assert response.status_code == 404
    assert "VID-9999" in response.json()["detail"]


def test_soul_endpoint_reports_hash(client: TestClient) -> None:
    payload = client.get("/api/soul").json()
    assert payload["ok"] is True
    assert payload["version"] == 1
    assert len(payload["sha256"]) == 64


def test_tampered_soul_blocks_every_endpoint(client: TestClient, settings) -> None:
    soul_path: Path = settings.soul_path
    original = soul_path.read_bytes()
    soul_path.write_bytes(original + b"\n")
    for path in ("/api/health", "/api/videos", "/api/soul", "/api/briefs"):
        response = client.get(path)
        assert response.status_code == 409, path
        assert response.json()["detail"]["ok"] is False
    soul_path.write_bytes(original)


def test_seed_is_idempotent_and_survives_reset(settings) -> None:
    eng = db.build_engine(settings.database_url)
    first = db.ensure_ready(eng, settings.data_dir)
    second = db.ensure_ready(eng, settings.data_dir)
    assert first["videos"] == len(FIXTURE_VIDEOS)
    assert second["videos"] == 0
    assert len(db.fetch_videos(eng)) == len(FIXTURE_VIDEOS)
    eng.dispose()


def test_transcript_seeded_with_source(settings) -> None:
    eng = db.build_engine(settings.database_url)
    db.ensure_ready(eng, settings.data_dir)
    doc = db.fetch_transcript(eng, "VID-0002")
    assert doc is not None
    assert doc.source == "whisper"
    assert doc.segments[0].text.startswith("Gaji naik")
    eng.dispose()


def test_video_detail_reports_transcript(settings) -> None:
    app = create_app(settings=settings, data_dir=settings.data_dir)
    with TestClient(app) as test_client:
        payload = test_client.get("/api/videos/VID-0001").json()
    assert payload["has_transcript"] is True
    assert payload["transcript_source"] == "captions"


@pytest.mark.parametrize("bad", ["VID-", "vid-0001"])
def test_video_lookup_is_exact(client: TestClient, bad: str) -> None:
    assert client.get(f"/api/videos/{bad}").status_code == 404
