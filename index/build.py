"""Bangun kartu segmen siap dipakai Matcher."""

from __future__ import annotations

from contracts import Segment, SegmentCard, TranscriptDoc
from index import features as feat
from index.kinds import classify

MAX_DURATION_S = 70.0
MIN_WORDS = 4


def key_quote(text: str, max_words: int = 15) -> str:
    """Kalimat terpadat dalam segmen, dipotong pada batas kata."""
    sentences = [
        s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()
    ]
    if not sentences:
        return text[:120]
    best = max(sentences, key=lambda s: len(s.split()))
    words = best.split()
    return " ".join(words[:max_words])


def segment_id(video_id: str, t0: float) -> str:
    """Id segmen deterministik dari video dan waktu mulai."""
    return f"{video_id}:{round(t0 * 1000)}"


def build_cards(doc: TranscriptDoc, segments: list[Segment] | None = None) -> list[SegmentCard]:
    """Ubah transkrip menjadi kartu segmen. Segmen di luar batas dibuang."""
    items = (
        segments
        if segments is not None
        else [Segment(t0=s.t0, t1=s.t1, text=s.text, words=s.words) for s in doc.segments]
    )
    cards: list[SegmentCard] = []
    valid = [s for s in items if s.t1 > s.t0]
    for index, seg in enumerate(valid):
        if len(seg.text.split()) < MIN_WORDS:
            continue
        if seg.t1 - seg.t0 > MAX_DURATION_S:
            continue
        kind = classify(seg.text, is_last=index == len(valid) - 1)
        cards.append(
            SegmentCard(
                segment_id=segment_id(doc.video_id, seg.t0),
                video_id=doc.video_id,
                t0=seg.t0,
                t1=seg.t1,
                kind=kind,
                key_quote=key_quote(seg.text),
                features=feat.compute(seg.text, seg.t0, seg.t1),
            )
        )
    return cards


def attach_dead_air(cards: list[SegmentCard], spans: list[tuple[float, float]]) -> None:
    """Tempelkan jeda panjang ke kartu yang tepat mendahuluinya."""
    for card in cards:
        card.features.dead_air_spans = [
            span for span in spans if span[0] >= card.t0 and span[1] <= card.t1 + 30
        ]
