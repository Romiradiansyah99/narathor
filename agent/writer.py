"""Writer: naskah penuh dengan sitasi. Backend tetap yang memverifikasi."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent.models import LanguageModel
from backend.config import ROOT
from contracts import (
    Beat,
    Citation,
    Combo,
    NarrativeBrief,
    SegmentCard,
    ShortScript,
    TranscriptDoc,
)


class WriterError(RuntimeError):
    """Keluaran model tidak dapat dipakai sebagai naskah."""


def prompt_path() -> Path:
    """Jalur template prompt Writer."""
    return ROOT / "prompts" / "writer.md"


def build_prompt(
    brief: NarrativeBrief,
    combo: Combo,
    cards: list[SegmentCard],
    transcripts: dict[str, TranscriptDoc],
) -> str:
    """Rakit prompt Writer dari brief, combo, dan transkrip."""
    template = prompt_path().read_text(encoding="utf-8")
    blocks: list[str] = []
    by_id = {card.segment_id: card for card in cards}
    for segment_id in combo.segment_ids:
        card = by_id.get(segment_id)
        if card is None:
            continue
        doc = transcripts.get(card.video_id)
        text = doc.text_between(card.t0, card.t1) if doc else card.key_quote
        blocks.append(f"[{card.video_id} {card.t0:.1f}-{card.t1:.1f}] {text}")
    body = template.split("---", 2)[-1].strip()
    return body.format(
        learning_outcome=brief.learning_outcome.strip(),
        thesis=brief.thesis.strip(),
        tone=brief.tone.target,
        register_level=brief.register_level,
        target_duration_s=brief.output.target_duration_s,
        audience=brief.audience.primary,
        segments="\n".join(blocks),
    )


def parse(raw: str, combo: Combo, brief: NarrativeBrief, script_id: str) -> ShortScript:
    """Ubah jawaban model menjadi ShortScript yang tervalidasi."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        raise WriterError("jawaban model tidak memuat JSON")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise WriterError(f"JSON tidak valid: {exc}") from exc
    beats = [
        Beat(
            at_s=float(item.get("at_s", 0)),
            text=str(item.get("text", "")).strip(),
            is_claim=bool(item.get("is_claim", False)),
            citation=Citation(**item["citation"]) if item.get("citation") else None,
            overlay=item.get("overlay"),
        )
        for item in payload.get("beats", [])
    ]
    if not beats:
        raise WriterError("naskah tanpa beat")
    return ShortScript(
        script_id=script_id,
        combo_id=combo.combo_id,
        brief_id=brief.id,
        hook=str(payload.get("hook", "")).strip(),
        beats=beats,
        payoff_at_s=float(payload.get("payoff_at_s", 0)),
        payoff_pays_off=bool(payload.get("payoff_pays_off", False)),
        single_minded_proposition=str(payload.get("single_minded_proposition", "")).strip(),
        title=str(payload.get("title", "")).strip(),
        caption=str(payload.get("caption", "")).strip(),
        target_duration_s=brief.output.target_duration_s,
        discarded=[str(x) for x in payload.get("discarded", [])],
    )


def write(
    combo: Combo,
    brief: NarrativeBrief,
    cards: list[SegmentCard],
    transcripts: dict[str, TranscriptDoc],
    llm: LanguageModel,
    script_id: str,
) -> ShortScript:
    """Tulis satu naskah. Lempar WriterError bila keluaran tidak layak."""
    prompt = build_prompt(brief, combo, cards, transcripts)
    raw = llm.complete(prompt, system="Kamu penulis naskah short yang setia pada ucapan sumber.")
    return parse(raw, combo, brief, script_id)
