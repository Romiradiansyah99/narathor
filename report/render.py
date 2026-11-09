"""Laporan artefak: naskah, index.md, blocked.md, run.json."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from contracts import Audit, RunRecord, SegmentCard, ShortScript

SCRIPT_TEMPLATE = """# {title}

- brief: {brief_id}
- combo: {combo_id}
- durasi target: {duration}s
- payoff di detik: {payoff}

## Hook
{hook}

## Naskah
{beats}

## Sitasi
{citations}

## Yang tidak dipakai
{discarded}
"""


def script_markdown(script: ShortScript) -> str:
    """Render satu naskah sebagai markdown dengan sitasi per klaim."""
    beats = "\n".join(
        f"{index + 1}. [{beat.at_s:.1f}s] {beat.text}"
        + (f"\n   overlay: {beat.overlay}" if beat.overlay else "")
        for index, beat in enumerate(script.beats)
    )
    citations = "\n".join(
        f'- {beat.citation.video_id} {beat.citation.t0:.1f}-{beat.citation.t1:.1f}: "{beat.citation.quote}"'
        for beat in script.beats
        if beat.citation
    )
    discarded = "\n".join(f"- {item}" for item in script.discarded) or "- (tidak ada)"
    return SCRIPT_TEMPLATE.format(
        title=script.title,
        brief_id=script.brief_id,
        combo_id=script.combo_id,
        duration=script.target_duration_s,
        payoff=script.payoff_at_s,
        hook=script.hook,
        beats=beats,
        citations=citations or "- (tidak ada klaim)",
        discarded=discarded,
    )


def index_markdown(cards: list[SegmentCard], audit_by_script: dict[str, Audit]) -> str:
    """Render index.md: daftar segmen dan keputusannya."""
    lines = ["# Index", "", f"Segmen: {len(cards)}", ""]
    for card in sorted(cards, key=lambda c: (-c.brand_fit, c.segment_id)):
        lines.append(
            f"- {card.segment_id} | {card.kind} | brand_fit {card.brand_fit} | "
            f"{card.t0:.1f}-{card.t1:.1f} | {card.key_quote[:90]}"
        )
    if audit_by_script:
        lines.extend(["", "## Gate", ""])
        for script_id, audit in audit_by_script.items():
            lines.append(
                f"- {script_id}: {audit.verdict} ({', '.join(audit.pressed) or 'semua gate lulus'})"
            )
    return "\n".join(lines) + "\n"


def blocked_markdown(blocked: list[tuple[str, str]]) -> str:
    """Render blocked.md: segmen yang dibuang beserta pasalnya."""
    lines = ["# Blocked", ""]
    if not blocked:
        lines.append("- (tidak ada)")
    for segment_id, reason in blocked:
        lines.append(f"- {segment_id}: {reason}")
    return "\n".join(lines) + "\n"


def write_artifacts(
    output_dir: Path,
    brief_id: str,
    channel: str,
    run: RunRecord,
    scripts: list[ShortScript],
    cards: list[SegmentCard],
    audits: list[Audit],
    blocked: list[tuple[str, str]] | None = None,
) -> Path:
    """Tulis seluruh artefak satu run. Tanpa run.json tidak ada yang ditulis."""
    if not run.brief_hash or not run.prompt_version or not run.soul_version:
        raise RuntimeError("artefak tanpa jejak tidak boleh ditulis")
    target = output_dir / brief_id / channel
    scripts_dir = target / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for script in scripts:
        (scripts_dir / f"{script.script_id}.md").write_text(
            script_markdown(script), encoding="utf-8"
        )
        (scripts_dir / f"{script.script_id}.json").write_text(
            script.model_dump_json(indent=2), encoding="utf-8"
        )
    audit_map = {audit.script_id: audit for audit in audits}
    (target / "index.md").write_text(index_markdown(cards, audit_map), encoding="utf-8")
    (target / "blocked.md").write_text(blocked_markdown(blocked or []), encoding="utf-8")
    record = run.model_copy(update={"finished_at": datetime.now(UTC), "status": "done"})
    (target / "run.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return target
