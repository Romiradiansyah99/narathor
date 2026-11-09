"""Fitur heuristik per segmen. Tanpa LLM, tanpa jaringan."""

from __future__ import annotations

from itertools import pairwise

from contracts import Segment, SegmentFeatures

FILLERS = ("jadi gini", "apa ya", "gimana ya", "oke guys", "ya kan", "eee", "emm")
SETUP_PREAMBLES = (
    "sebelum itu",
    "di video kali ini",
    "sebelum kita mulai",
    "jadi sebelum",
    "oke sebelum",
)
PAYOFF_MARKERS = (
    "itu sebabnya",
    "makanya",
    "jadi intinya",
    "kesimpulannya",
    "akhirnya",
    "intinya",
)
REBUTTAL_MARKERS = ("tapi", "padahal", "bukan begitu", "salah", "keliru")
STORY_MARKERS = ("waktu", "dulu", "pernah", "suatu hari", "saya ingat")


def word_count(text: str) -> int:
    """Jumlah kata."""
    return len(text.split())


def wpm(text: str, t0: float, t1: float) -> float:
    """Kata per menit pada rentang segmen."""
    minutes = max((t1 - t0) / 60.0, 1e-6)
    return round(word_count(text) / minutes, 2)


def filler_positions(words: list[str]) -> list[int]:
    """Indeks kata tempat filler muncul."""
    hits: list[int] = []
    for filler in FILLERS:
        parts = filler.split()
        width = len(parts)
        for index in range(len(words) - width + 1):
            if [w.lower().strip(",.!?") for w in words[index : index + width]] == parts:
                hits.append(index)
    return sorted(set(hits))


def has_setup_preamble(text: str) -> bool:
    """True bila segmen dibuka dengan basa-basi administratif."""
    lowered = text.lower().strip()
    return any(lowered.startswith(marker) for marker in SETUP_PREAMBLES)


def payoff_present(text: str) -> bool:
    """True bila segmen memuat penanda pembayaran janji."""
    lowered = text.lower()
    return any(marker in lowered for marker in PAYOFF_MARKERS)


def hook_archetype(text: str) -> str:
    """Arketipe pembuka menurut bentuk kalimat pertama."""
    first = text.split(".")[0].strip()
    if "?" in first:
        return "question"
    if any(ch.isdigit() for ch in first):
        return "number"
    if any(first.lower().startswith(m) for m in STORY_MARKERS):
        return "story"
    return "claim"


def is_rebuttal(text: str) -> bool:
    """True bila segmen membantah sesuatu."""
    lowered = text.lower()
    return any(marker in lowered for marker in REBUTTAL_MARKERS)


def is_story(text: str) -> bool:
    """True bila segmen berbentuk cerita."""
    lowered = text.lower()
    return any(marker in lowered for marker in STORY_MARKERS)


def compute(text: str, t0: float, t1: float) -> SegmentFeatures:
    """Hitung seluruh fitur satu segmen."""
    words = text.split()
    return SegmentFeatures(
        word_count=word_count(text),
        wpm=wpm(text, t0, t1),
        filler_positions=filler_positions(words),
        dead_air_spans=[],
        has_setup_preamble=has_setup_preamble(text),
        payoff_present=payoff_present(text),
        niche_consistency_score=0.0,
        hook_archetype=hook_archetype(text),
    )


def dead_air(segments: list[Segment], threshold: float = 1.5) -> list[tuple[float, float]]:
    """Rentang jeda panjang antar segmen."""
    spans: list[tuple[float, float]] = []
    for prev, nxt in pairwise(segments):
        if nxt.t0 - prev.t1 >= threshold:
            spans.append((prev.t1, nxt.t0))
    return spans
