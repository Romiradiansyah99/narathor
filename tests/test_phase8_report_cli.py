"""Test Fase 8: laporan, metrik, orkestrasi, dan CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent.models import StubModel
from backend import db, store
from backend.config import Settings
from contracts import Audit, Beat, Citation, GateResult, RunRecord, SegmentCard, ShortScript
from eval.metrics import Metrics, evaluate, precision_at_k, rates, read_golden
from narathor.cli import app as cli_app
from narathor.run import orchestrate, select_videos
from report.render import blocked_markdown, index_markdown, script_markdown, write_artifacts
from tests.fixtures import FIXTURE_VIDEOS

REPLY = {
    "hook": "Uang bocor di tempat salah",
    "beats": [
        {
            "at_s": 0,
            "text": "Masalah keuangan bukan jumlah tapi arah aliran uang",
            "is_claim": True,
            "citation": {
                "video_id": "VID-0001",
                "t0": 0,
                "t1": 12,
                "quote": "masalahnya bukan berapa yang masuk",
            },
        },
        {
            "at_s": 8,
            "text": "Gaji naik tabungan tidak bergerak karena pengeluaran ikut naik",
            "is_claim": True,
            "citation": {
                "video_id": "VID-0002",
                "t0": 0,
                "t1": 5,
                "quote": "Gaji naik dua kali lipat",
            },
        },
    ],
    "payoff_at_s": 8,
    "payoff_pays_off": True,
    "single_minded_proposition": "Arah aliran uang lebih menentukan daripada jumlah",
    "title": "Arah aliran",
    "caption": "caption uji",
    "discarded": ["statistik"],
}

BRIEF_YAML = """id: uji
title: "Uji"
learning_outcome: >
  Penonton memahami arah aliran uang bukan jumlahnya
thesis: >
  Masalah keuangan pribadi lebih sering soal arah aliran daripada jumlah
audience:
  primary: "Indonesia 18-35"
  literacy_level: menengah
values_allowed: [kejujuran_intelektual]
values_blocked: [janji_kaya_instan]
register_level: 2
tone:
  target: "tegas, jernih"
seasonal_context:
  as_of: 2026-11-09
sources:
  channels: ["https://youtube.com/@uji"]
  recency_preference: any
  min_duration_s: 100
output:
  scripts: 2
  target_duration_s: 15
  language: id
"""


@pytest.fixture
def brief_file(settings: Settings) -> Path:
    path = settings.briefs_dir / "uji.yaml"
    path.write_text(BRIEF_YAML, encoding="utf-8")
    return path


def _script(script_id: str = "s1") -> ShortScript:
    return ShortScript(
        script_id=script_id,
        combo_id="c1",
        brief_id="uji",
        hook="Uang bocor di tempat salah",
        beats=[
            Beat(
                at_s=0,
                text="klaim",
                is_claim=True,
                citation=Citation(
                    video_id="VID-0001", t0=0, t1=12, quote="masalahnya bukan berapa yang masuk"
                ),
            ),
            Beat(at_s=8, text="penutup"),
        ],
        payoff_at_s=8,
        payoff_pays_off=True,
        single_minded_proposition="p",
        title="t",
        caption="c",
        target_duration_s=15,
    )


def _audit(script_id: str = "s1", pressed: list[str] | None = None) -> Audit:
    pressed = pressed or []
    gates = [
        GateResult(name=name, passed=name not in pressed)
        for name in (
            "soul_compliance",
            "citation_integrity",
            "hook_payoff",
            "craft_distinctiveness",
            "brief_alignment",
            "values_clean",
            "traceability",
        )
    ]
    return Audit(
        script_id=script_id,
        gates=gates,
        cites_ok="citation_integrity" not in pressed,
        verdict="pass" if not pressed else "return",
        pressed=pressed,
    )


def test_script_markdown_lists_citations() -> None:
    text = script_markdown(_script())
    assert "Arah aliran" in text or "t" in text
    assert "VID-0001" in text
    assert "0.0-12.0" in text


def test_index_markdown_counts_cards() -> None:
    card = SegmentCard(
        segment_id="VID-0001:0", video_id="VID-0001", t0=0, t1=10, kind="thesis", key_quote="q"
    )
    text = index_markdown([card], {"s1": _audit()})
    assert "Segmen: 1" in text
    assert "s1: pass" in text


def test_blocked_markdown_empty() -> None:
    assert "(tidak ada)" in blocked_markdown([])


def test_write_artifacts_creates_files(settings: Settings) -> None:
    from datetime import UTC, datetime

    record = RunRecord(
        run_id="run-1",
        brief_id="uji",
        brief_hash="a" * 64,
        soul_version=1,
        prompt_version="v1",
        started_at=datetime.now(UTC),
    )
    target = write_artifacts(
        settings.output_dir, "uji", "Channel_Uji", record, [_script()], [], [_audit()]
    )
    assert (target / "run.json").exists()
    assert (target / "scripts" / "s1.md").exists()
    assert (target / "index.md").exists()
    assert (target / "blocked.md").exists()


def test_write_artifacts_rejects_untraceable(settings: Settings) -> None:
    from datetime import UTC, datetime

    record = RunRecord.model_construct(
        run_id="r",
        brief_id="uji",
        brief_hash="",
        soul_version=0,
        prompt_version="",
        models={},
        sources=[],
        started_at=datetime.now(UTC),
        finished_at=None,
        status="running",
        est_cost_usd=0.0,
        skipped=[],
    )
    with pytest.raises(RuntimeError):
        write_artifacts(settings.output_dir, "uji", "c", record, [], [], [])


def test_precision_at_k() -> None:
    assert precision_at_k(["a", "b"], ["a", "x", "b"], 3) == pytest.approx(2 / 3)
    assert precision_at_k([], ["a"]) == 0.0


def test_rates_compute_violations() -> None:
    metrics = rates([_script("s1"), _script("s2")], [_audit("s1"), _audit("s2", ["hook_payoff"])])
    assert metrics.citation_violation_rate == 0.0
    assert metrics.hook_payoff_violation_rate == 0.5
    assert metrics.craft_pass_rate == 1.0


def test_evaluate_reads_golden(settings: Settings) -> None:
    golden = settings.data_dir / "eval" / "uji.json"
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(json.dumps(["VID-0001"]), encoding="utf-8")
    metrics = evaluate([_script()], [_audit()], golden)
    assert metrics.precision_at_10 > 0
    assert isinstance(metrics, Metrics)


def test_read_golden_missing() -> None:
    assert read_golden(Path("/tmp/tidak-ada-golden.json")) == []


def test_select_videos_filters_by_duration(settings: Settings, brief_file: Path) -> None:
    from briefs.load import load_or_raise

    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    brief = load_or_raise(settings.briefs_dir, "uji")
    videos = select_videos(brief, engine)
    assert all(v.duration_s >= brief.sources.min_duration_s for v in videos)
    engine.dispose()


def test_orchestrate_writes_output(settings: Settings, brief_file: Path, monkeypatch) -> None:
    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    summary = orchestrate(
        "uji",
        settings=settings,
        engine=engine,
        count=2,
        concurrency=2,
        writer_llm=StubModel(REPLY),
        use_models=True,
    )
    assert summary["videos"] == len(FIXTURE_VIDEOS)
    assert Path(summary["output"]).exists()
    assert (Path(summary["output"]) / "run.json").exists()
    engine.dispose()


def test_store_roundtrip(settings: Settings, brief_file: Path) -> None:
    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    card = SegmentCard(
        segment_id="VID-0001:0", video_id="VID-0001", t0=0, t1=10, kind="thesis", key_quote="q"
    )
    store.save_segments(engine, [card], "uji")
    cards = store.load_cards(engine, "uji")
    assert len(cards) == 1
    store.save_script(engine, _script())
    store.save_audit(engine, _audit())
    assert len(store.load_scripts(engine, "uji")) == 1
    assert len(store.load_audits(engine)) == 1
    engine.dispose()


def test_cli_status_runs(settings: Settings, brief_file: Path, monkeypatch) -> None:
    monkeypatch.setattr("narathor.cli.get_settings", lambda: settings)
    monkeypatch.setattr("backend.config.get_settings", lambda: settings)
    result = CliRunner().invoke(cli_app, ["narrative", "list"])
    assert result.exit_code == 0
    assert "uji" in result.stdout


def test_cli_rejects_missing_brief(settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("narathor.cli.get_settings", lambda: settings)
    result = CliRunner().invoke(cli_app, ["narrative", "check", "tidak-ada"])
    assert result.exit_code != 0
