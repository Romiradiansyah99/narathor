"""CLI Narathor. Tipis: memvalidasi, memanggil backend, mencetak progres."""

from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Annotated

import typer

from agent.matcher import match, score_card
from backend import db, soul
from backend.config import get_settings
from backend.store import load_audits, load_cards, load_scripts, save_combo, save_segments
from briefs import load as briefs_load
from contracts import NarrativeBrief
from eval.metrics import evaluate
from index.build import build_cards
from index.segmenter import segment_transcript
from ingest import ytdlp
from ingest.pipeline import DbStore, default_fetchers
from ingest.pipeline import run as run_ingest
from narathor.run import orchestrate

app = typer.Typer(add_completion=False, help="Mesin perangkai naskah short.")
soul_app = typer.Typer(help="Konstitusi: verifikasi dan bump.")
narrative_app = typer.Typer(help="Narrative Brief: buat dan periksa.")
app.add_typer(soul_app, name="soul")
app.add_typer(narrative_app, name="narrative")


def _fail(message: str, code: int = 1) -> None:
    """Cetak ke stderr lalu keluar non-zero."""
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


def _require_soul() -> int:
    """Verifikasi soul atau hentikan seluruh command."""
    settings = get_settings()
    check = soul.verify(settings.soul_path, settings.soul_lock_path)
    if not check.ok:
        _fail(f"Soul tidak lolos verifikasi.\n\n{check.reason}")
    assert check.version is not None
    return check.version


@app.callback()
def main(ctx: typer.Context) -> None:
    """Every command verifies the soul first, except the ceremony itself.

    `soul bump` and `soul verify` must stay reachable while the hash is mismatched,
    otherwise a deliberate change could never be ratified.
    """
    if ctx.invoked_subcommand == "soul":
        return
    _require_soul()


# --------------------------------------------------------------------------- #
# soul
# --------------------------------------------------------------------------- #


@soul_app.command("verify")
def soul_verify() -> None:
    """Periksa SOUL.md terhadap soul.lock."""
    settings = get_settings()
    check = soul.verify(settings.soul_path, settings.soul_lock_path)
    typer.echo(json.dumps(check.model_dump(mode="json"), indent=2))
    if not check.ok:
        raise typer.Exit(code=1)


@soul_app.command("bump")
def soul_bump(
    reason: Annotated[str, typer.Option("--reason", help="Alasan perubahan pasal.")],
) -> None:
    """Naikkan versi soul setelah SOUL.md diubah secara sengaja."""
    settings = get_settings()
    try:
        updated = soul.bump(settings.soul_path, settings.soul_lock_path, reason)
    except soul.SoulLockError as exc:
        _fail(str(exc))
        return
    typer.echo(json.dumps(updated, indent=2))
    typer.echo("\nWajib: jalankan ulang `narathor eval` untuk seluruh narrative yang terdampak.")


# --------------------------------------------------------------------------- #
# narrative
# --------------------------------------------------------------------------- #


@narrative_app.command("check")
def narrative_check(brief_id: str) -> None:
    """Validasi satu brief tanpa menyentuh model."""
    settings = get_settings()
    report = briefs_load.load(settings.briefs_dir, brief_id)
    if not report.ok:
        _fail(report.render())
    assert report.brief is not None
    typer.echo(f'Brief "{brief_id}" lolos. hash {briefs_load.brief_hash(report.brief)[:16]}')


@narrative_app.command("new")
def narrative_new(brief_id: str) -> None:
    """Buat brief baru dari template."""
    settings = get_settings()
    target = briefs_load.brief_path(settings.briefs_dir, brief_id)
    if target.exists():
        _fail(f"brief {target.name} sudah ada; tidak ditimpa")
    template = settings.briefs_dir / "_template.yaml"
    if not template.exists():
        _fail("briefs/_template.yaml tidak ada")
    shutil.copyfile(template, target)
    typer.echo(
        f"dibuat: {target}\nisi field WAJIB, lalu jalankan `narathor narrative check {brief_id}`"
    )


@narrative_app.command("list")
def narrative_list() -> None:
    """Daftar brief dan status validasinya."""
    settings = get_settings()
    for brief_id in briefs_load.list_ids(settings.briefs_dir):
        report = briefs_load.load(settings.briefs_dir, brief_id)
        mark = "ok" if report.ok else f"ditolak ({len(report.rejections)})"
        title = report.brief.title if report.brief else "-"
        typer.echo(f"{brief_id:28} {mark:16} {title}")


# --------------------------------------------------------------------------- #
# doctor dan status
# --------------------------------------------------------------------------- #


@app.command("doctor")
def doctor() -> None:
    """Lima pemeriksaan: API key, database, soul, pustaka, model."""
    settings = get_settings()
    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    channel = db.fetch_channel(engine)
    videos = db.fetch_videos(engine)
    checks = [
        (
            "api_key",
            bool(settings.api_key),
            "COMMAND_CODE_API_KEY terisi" if settings.api_key else "kosong di .env",
        ),
        ("database", True, "sqlite" if settings.is_sqlite else "postgres"),
        (
            "soul",
            soul.verify(settings.soul_path, settings.soul_lock_path).ok,
            f"v{_require_soul()}",
        ),
        (
            "library",
            len(videos) > 0,
            f"{len(videos)} video, channel {channel.name if channel else '-'}",
        ),
        ("models", True, ", ".join(f"{k}={v}" for k, v in settings.models.items())),
        (
            "cookies",
            ytdlp.cookies_present(),
            os.environ.get("YT_COOKIES_FILE", "").strip()
            or "belum ada; youtube akan menolak transkrip dari IP server",
        ),
    ]
    for name, ok, detail in checks:
        typer.echo(f"[{'ok  ' if ok else 'gagal'}] {name:10} {detail}")
    if not all(ok for _, ok, _ in checks):
        raise typer.Exit(code=1)


@app.command("status")
def status() -> None:
    """Ringkas keadaan pustaka dan brief."""
    settings = get_settings()
    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    videos = db.fetch_videos(engine)
    with_transcript = sum(1 for v in videos if db.fetch_transcript(engine, v.video_id) is not None)
    typer.echo(f"video        : {len(videos)}")
    typer.echo(f"transkrip    : {with_transcript}")
    typer.echo(f"brief        : {len(briefs_load.list_ids(settings.briefs_dir))}")
    typer.echo(f"soul         : v{_require_soul()}")


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #


@app.command("ingest")
def ingest(
    narrative: Annotated[str, typer.Option("--narrative", help="id brief")],
    force: Annotated[bool, typer.Option("--force", help="abaikan cache")] = False,
    limit: Annotated[int, typer.Option("--limit", help="batas video")] = 0,
) -> None:
    """Ambil transkrip pustaka: caption dulu, Whisper bila perlu."""
    settings = get_settings()
    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    brief = briefs_load.load_or_raise(settings.briefs_dir, narrative)
    videos = [v for v in db.fetch_videos(engine) if v.duration_s >= brief.sources.min_duration_s]
    if limit:
        videos = videos[:limit]
    captions_fetcher, whisper_fetcher = default_fetchers()
    report_data = run_ingest(
        videos, DbStore(engine), captions_fetcher, whisper_fetcher, force=force
    )
    typer.echo(json.dumps(report_data.as_dict(), indent=2))


@app.command("index")
def index_cmd(narrative: Annotated[str, typer.Option("--narrative", help="id brief")]) -> None:
    """Segmentasi dan fitur, tanpa LLM."""
    settings = get_settings()
    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    brief = briefs_load.load_or_raise(settings.briefs_dir, narrative)
    cards = []
    for video in db.fetch_videos(engine):
        doc = db.fetch_transcript(engine, video.video_id)
        if doc is None:
            continue
        cards.extend(build_cards(doc, segment_transcript(doc.segments)))
    for card in cards:
        card.brand_fit = score_card(card, brief)
    saved = save_segments(engine, cards, brief.id)
    typer.echo(f"segmen: {saved} kartu tersimpan")


@app.command("mine")
def mine(
    narrative: Annotated[str, typer.Option("--narrative", help="id brief")],
    top: Annotated[int, typer.Option("--top", help="jumlah combo")] = 50,
) -> None:
    """Rakit combo lintas video dari segmen tersimpan."""
    settings = get_settings()
    engine = db.build_engine(settings.database_url)
    brief = briefs_load.load_or_raise(settings.briefs_dir, narrative)
    cards = load_cards(engine, brief.id)
    combos = match(cards, brief, top)
    for combo in combos:
        save_combo(engine, combo, brief.id)
    typer.echo(f"combo: {len(combos)} tersimpan dari {len(cards)} kartu")


@app.command("script")
def script_cmd(
    narrative: Annotated[str, typer.Option("--narrative", help="id brief")],
    count: Annotated[int, typer.Option("--count", help="jumlah naskah")] = 0,
    concurrency: Annotated[int, typer.Option("--concurrency", help="batas unit paralel")] = 0,
) -> None:
    """Tulis naskah penuh dengan sitasi."""
    summary = orchestrate(
        narrative,
        count=count or None,
        concurrency=concurrency or None,
    )
    typer.echo(json.dumps(summary, indent=2))


@app.command("report")
def report_cmd(narrative: Annotated[str, typer.Option("--narrative", help="id brief")]) -> None:
    """Tampilkan ringkasan artefak terakhir."""
    settings = get_settings()
    base = settings.output_dir / narrative
    if not base.exists():
        _fail(f"belum ada artefak untuk {narrative}; jalankan `narathor script` dulu")
    for run_file in sorted(base.glob("*/summary.json")):
        typer.echo(f"{run_file.parent.name}: {run_file.read_text(encoding='utf-8')}")


@app.command("eval")
def eval_cmd(narrative: Annotated[str, typer.Option("--narrative", help="id brief")]) -> None:
    """Hitung lima metrik. Golden set hanya dibaca di sini."""
    settings = get_settings()
    engine = db.build_engine(settings.database_url)
    scripts = load_scripts(engine, narrative)
    audits = load_audits(engine)
    golden = settings.data_dir / "eval" / f"{narrative}.json"
    result = evaluate(scripts, audits, golden)
    typer.echo(json.dumps(result.as_dict(), indent=2))


@app.command("check")
def check_cmd() -> None:
    """ruff, pyright, dan pytest sekaligus."""
    import subprocess

    commands = [
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "pyright"],
        ["uv", "run", "pytest", "-q"],
    ]
    failed = False
    for command in commands:
        proc = subprocess.run(command, cwd=str(settings_root()), capture_output=True, text=True)
        label = " ".join(command[2:])
        typer.echo(f"[{'ok  ' if proc.returncode == 0 else 'gagal'}] {label}")
        if proc.returncode != 0:
            failed = True
            typer.echo(proc.stdout[-2000:] + proc.stderr[-2000:], err=True)
    if failed:
        raise typer.Exit(code=1)


def settings_root():
    """Akar repo untuk subprocess."""
    return get_settings().root


def _print_brief(brief: NarrativeBrief) -> None:
    """Cetak ringkas satu brief."""
    typer.echo(f"{brief.id}: {brief.title}")
    typer.echo(f"  learning_outcome: {brief.learning_outcome.strip()[:80]}")


if __name__ == "__main__":
    sys.exit(app())
