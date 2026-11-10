"""Fixture test. Tidak pernah menyentuh jaringan dan tidak pernah memanggil model."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.config import DEFAULT_MODELS, Settings
from backend.main import create_app
from tests.fixtures import write_fixture_library

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings terisolasi: soul disalin, data fixture, database SQLite sementara."""
    soul_src = ROOT / "SOUL.md"
    lock_src = ROOT / "soul.lock"
    soul_dst = tmp_path / "SOUL.md"
    lock_dst = tmp_path / "soul.lock"
    shutil.copyfile(soul_src, soul_dst)
    shutil.copyfile(lock_src, lock_dst)
    data_dir = write_fixture_library(tmp_path / "data")
    briefs_dir = tmp_path / "briefs"
    briefs_dir.mkdir()
    shutil.copyfile(ROOT / "briefs" / "_template.yaml", briefs_dir / "_template.yaml")
    return Settings(
        root=tmp_path,
        data_dir=data_dir,
        output_dir=tmp_path / "output",
        briefs_dir=briefs_dir,
        prompts_dir=tmp_path / "prompts",
        soul_path=soul_dst,
        soul_lock_path=lock_dst,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.sqlite3'}",
        api_key="test-key",
        max_concurrency=3,
        models=dict(DEFAULT_MODELS),
    )


@pytest.fixture
def engine(settings: Settings) -> Iterator:
    """Engine baru untuk setiap test."""
    eng = db.build_engine(settings.database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def client(settings: Settings, engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Test client di atas app yang dibangun dengan settings terisolasi."""
    monkeypatch.setenv("NARATHOR_CHAT_MODEL", "off")
    app = create_app(settings=settings, engine=engine, data_dir=settings.data_dir)
    with TestClient(app) as test_client:
        yield test_client
