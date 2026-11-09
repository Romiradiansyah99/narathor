"""Matcher: rakit Combo dari kartu segmen lintas video."""

from __future__ import annotations

import json
import re

from agent.models import LanguageModel
from contracts import Combo, NarrativeBrief, SegmentCard

NEGATIONS = ("tidak", "bukan", "salah", "keliru", "mitos")


SUFFIXES = ("nya", "ku", "mu")


def _stem(word: str) -> str:
    """Buang akhiran yang paling umum agar 'masalahnya' cocok dengan 'masalah'."""
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _words(text: str) -> set[str]:
    """Kata bermakna setelah stemming ringan."""
    return {_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3}


def _overlap(a: str, b: str) -> float:
    """Irisan kata bermakna antara dua teks, dengan pencocokan awalan."""
    words_a = _words(a)
    words_b = _words(b)
    if not words_a or not words_b:
        return 0.0
    matched = 0
    for word in words_a:
        if word in words_b or any(
            len(word) >= 4
            and len(other) >= 4
            and (word.startswith(other) or other.startswith(word))
            for other in words_b
        ):
            matched += 1
    return matched / max(len(words_a | words_b), 1)


def contradicts(a: SegmentCard, b: SegmentCard) -> bool:
    """True bila dua segmen saling membantah secara dangkal."""
    if a.kind == "rebuttal" and b.kind == "rebuttal":
        return _overlap(a.key_quote, b.key_quote) > 0.4
    positive = not any(neg in a.key_quote.lower().split() for neg in NEGATIONS)
    negative = any(neg in b.key_quote.lower().split() for neg in NEGATIONS)
    return positive and negative and _overlap(a.key_quote, b.key_quote) >= 0.4


def score_card(card: SegmentCard, brief: NarrativeBrief) -> int:
    """brand_fit 0..5 menurut anchor docs/NARRATIVE.md §5."""
    text = card.key_quote.lower()
    blocked = [value.replace("_", " ") for value in brief.values_blocked]
    if any(token in text for token in blocked):
        return 0
    target = f"{brief.thesis} {brief.learning_outcome}"
    overlap = _overlap(card.key_quote, target)
    if overlap >= 0.12:
        return 5
    if overlap >= 0.05:
        return 3
    return 1


def rank(cards: list[SegmentCard], brief: NarrativeBrief) -> list[SegmentCard]:
    """Beri brand_fit dan urutkan; segmen skor 0 dibuang permanen."""
    kept: list[SegmentCard] = []
    for card in cards:
        card.brand_fit = score_card(card, brief)
        if card.brand_fit > 0:
            kept.append(card)
    return sorted(kept, key=lambda c: (-c.brand_fit, -c.t1, c.segment_id))


def build_combo(cards: list[SegmentCard], brief: NarrativeBrief, index: int) -> Combo | None:
    """Rakit satu combo: minimal dua video berbeda, tanpa kontradiksi."""
    ranked = rank(cards, brief)
    chosen: list[SegmentCard] = []
    for card in ranked:
        if card.brand_fit < 3:
            continue
        if len(chosen) >= 4:
            break
        if any(contradicts(card, other) for other in chosen):
            continue
        chosen.append(card)
    if len({c.video_id for c in chosen}) < 2:
        return None
    thesis = brief.thesis.strip().split(".")[0][:180]
    return Combo(
        combo_id=f"combo-{index:03d}",
        thesis=thesis,
        segment_ids=[c.segment_id for c in chosen],
        video_ids=sorted({c.video_id for c in chosen}),
        rationale=f"brand_fit {[c.brand_fit for c in chosen]}",
    )


def match(
    cards: list[SegmentCard], brief: NarrativeBrief, target: int, llm: LanguageModel | None = None
) -> list[Combo]:
    """Hasilkan hingga target combo. Tanpa llm, urutan deterministik dari brand_fit."""
    combos: list[Combo] = []
    pool = list(cards)
    for index in range(target):
        combo = build_combo(pool, brief, index)
        if combo is None:
            break
        combos.append(combo)
        used = set(combo.segment_ids)
        pool = [c for c in pool if c.segment_id not in used]
    if llm is not None and combos:
        try:
            refinement = llm.complete(
                "Pilih ulang urutan segmen agar alur klaim, bukti, konsekuensi, penutup. "
                f"Kandidat: {json.dumps([c.key_quote for c in cards[:20]])}"
            )
            _ = refinement
        except Exception:
            pass
    return combos
