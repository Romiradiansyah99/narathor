"""Klasifikasi kind segmen. Heuristik tanpa model."""

from __future__ import annotations

from contracts import SegmentKind
from index.features import is_rebuttal, is_story, payoff_present

THESIS_MARKERS = ("sebenarnya", "intinya", "masalahnya", "yang penting", "harusnya")


def classify(text: str, is_last: bool) -> SegmentKind:
    """Tentukan kind satu segmen menurut bentuknya."""
    lowered = text.lower()
    if is_last and payoff_present(text):
        return "close"
    if any(marker in lowered for marker in THESIS_MARKERS):
        return "thesis"
    if (any(ch.isdigit() for ch in text) and "%" in text) or any(ch.isdigit() for ch in text):
        return "number"
    if is_rebuttal(text):
        return "rebuttal"
    if is_story(text):
        return "story"
    return "thesis" if payoff_present(text) else "story"
