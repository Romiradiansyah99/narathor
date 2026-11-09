"""Test Fase 2: penegakan soul dan validasi brief."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import soul
from briefs import load as briefs_load

VALID_BRIEF = """
id: cerdaskan-bangsa
title: "Mencerdaskan bangsa lewat atensi yang berguna"
learning_outcome: >
  Penonton memahami bahwa masalah keuangan pribadi lebih sering soal arah
  aliran daripada soal jumlah penghasilan.
thesis: >
  Atensi adalah aset terbatas; konten yang layak ditonton meninggalkan satu
  gagasan utuh.
audience:
  primary: "Indonesia, 18-35, terbiasa short, belum punya dasar"
  literacy_level: menengah
  pain_points:
    - "merasa sudah tahu tapi hasilnya tidak berubah"
values_allowed:
  - kejujuran_intelektual
  - tanggung_jawab_personal
values_blocked:
  - janji_kaya_instan
  - pseudosains
register_level: 2
tone:
  target: "tegas, jernih, tidak menggurui"
  avoid:
    - "menggurui"
seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: []
  trend_notes: ""
  trend_expiry: null
sources:
  channels:
    - "https://www.youtube.com/@channel-uji"
  recency_preference: any
  min_duration_s: 180
output:
  scripts: 30
  target_duration_s: 15
  language: id
  montages: 0
"""


def _write(briefs_dir: Path, brief_id: str, body: str, keep_id: bool = False) -> None:
    if not keep_id:
        body = body.replace("id: cerdaskan-bangsa", f"id: {brief_id}")
    (briefs_dir / f"{brief_id}.yaml").write_text(body, encoding="utf-8")


def test_valid_brief_passes(settings) -> None:
    _write(settings.briefs_dir, "cerdaskan-bangsa", VALID_BRIEF)
    report = briefs_load.load(settings.briefs_dir, "cerdaskan-bangsa")
    assert report.ok, report.render()
    assert report.brief is not None
    assert report.brief.audience.literacy_level == "menengah"


def test_valid_brief_via_api(settings, client: TestClient) -> None:
    _write(settings.briefs_dir, "cerdaskan-bangsa", VALID_BRIEF)
    response = client.get("/api/briefs/cerdaskan-bangsa")
    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"]["id"] == "cerdaskan-bangsa"
    assert len(payload["brief_hash"]) == 64


@pytest.mark.parametrize(
    ("needle", "code", "expected_word"),
    [
        ("learning_outcome", 1, "learning_outcome"),
        ("seasonal_context", 3, "as_of"),
    ],
)
def test_missing_required_field_rejected(
    settings, needle: str, code: int, expected_word: str
) -> None:
    body = VALID_BRIEF
    if needle == "learning_outcome":
        body = body.replace(
            "learning_outcome: >\n  Penonton memahami bahwa masalah keuangan pribadi lebih sering soal arah\n  aliran daripada soal jumlah penghasilan.\n",
            'learning_outcome: ""\n',
        )
    else:
        body = body.replace("  as_of: 2026-11-09\n", "")
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == code for r in report.rejections), report.render()
    assert expected_word in report.render()


def test_values_overlap_rejected(settings) -> None:
    body = VALID_BRIEF.replace("- pseudosains", "- pseudosains\n  - tanggung_jawab_personal")
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 4 for r in report.rejections), report.render()


def test_ambiguous_blocked_value_rejected(settings) -> None:
    body = VALID_BRIEF.replace("- pseudosains", "- konten yang terlalu berhati-hati")
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 12 for r in report.rejections), report.render()
    assert "ambiguity" in report.render().lower()


def test_tone_asking_payoff_delay_rejected(settings) -> None:
    body = VALID_BRIEF.replace('"tegas, jernih, tidak menggurui"', '"bikin penasaran sampai akhir"')
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 7 for r in report.rejections), report.render()
    assert "Article 4" in report.render()


def test_tone_asking_to_loosen_citation_rejected(settings) -> None:
    body = VALID_BRIEF.replace(
        '  trend_notes: ""', '  trend_notes: "boleh tanpa sitasi supaya ringkas"'
    )
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 6 for r in report.rejections), report.render()
    assert "Article 5" in report.render()


def test_soul_mandated_value_cannot_be_blocked(settings) -> None:
    body = VALID_BRIEF.replace("- pseudosains", "- keterlacakan")
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 5 for r in report.rejections), report.render()


def test_experimental_duration_rejected(settings) -> None:
    body = VALID_BRIEF.replace("target_duration_s: 15", "target_duration_s: 30")
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 8 for r in report.rejections), report.render()


def test_scoring_override_beyond_bound_rejected(settings) -> None:
    body = VALID_BRIEF + "\nscoring_overrides:\n  hook_weight: 0.45\n"
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 11 for r in report.rejections), report.render()


def test_hook_weight_ratio_guard(settings) -> None:
    body = VALID_BRIEF + "\nscoring_overrides:\n  hook_weight: 0.30\n  satisfaction_weight: 0.12\n"
    _write(settings.briefs_dir, "uji", body)
    report = briefs_load.load(settings.briefs_dir, "uji")
    assert not report.ok
    assert any(r.code == 11 for r in report.rejections), report.render()


def test_rejected_brief_writes_no_artifact(settings, client: TestClient) -> None:
    body = VALID_BRIEF.replace(
        "learning_outcome: >\n  Penonton memahami bahwa masalah keuangan pribadi lebih sering soal arah\n  aliran daripada soal jumlah penghasilan.\n",
        'learning_outcome: ""\n',
    )
    _write(settings.briefs_dir, "uji", body)
    response = client.get("/api/briefs/uji")
    assert response.status_code == 400
    assert not settings.output_dir.exists() or not any(settings.output_dir.iterdir())


def test_missing_file_rejected(settings) -> None:
    report = briefs_load.load(settings.briefs_dir, "tidak-ada")
    assert not report.ok
    assert any(r.code == 12 for r in report.rejections)


def test_id_must_match_filename(settings) -> None:
    _write(settings.briefs_dir, "lain", VALID_BRIEF, keep_id=True)
    report = briefs_load.load(settings.briefs_dir, "lain")
    assert not report.ok
    assert any(r.code == 12 for r in report.rejections)


def test_soul_bump_moves_hash_and_raises_version(settings) -> None:
    before = json.loads(settings.soul_lock_path.read_text())
    settings.soul_path.write_bytes(settings.soul_path.read_bytes() + b"\n")
    updated = soul.bump(settings.soul_path, settings.soul_lock_path, "uji: pasal tambahan")
    assert updated["version"] == before["version"] + 1
    assert updated["previous_versions"][-1]["sha256"] == before["sha256"]
    assert soul.verify(settings.soul_path, settings.soul_lock_path).ok is True


def test_soul_bump_without_reason_refused(settings) -> None:
    with pytest.raises(soul.SoulLockError):
        soul.bump(settings.soul_path, settings.soul_lock_path, "   ")
