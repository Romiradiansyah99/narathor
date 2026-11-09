"""Segmentasi transkrip. Heuristik, tanpa LLM."""

from __future__ import annotations

from contracts import Segment

PAUSE_S = 0.8
MIN_WORDS = 4
MAX_DURATION_S = 70.0
SENTENCE_END = (".", "!", "?", ";", ":")


def _words(seg: Segment) -> list[str]:
    """Kata dalam segmen, dari words[] bila ada."""
    if seg.words:
        return [w.text for w in seg.words]
    return seg.text.split()


def _ends_sentence(text: str) -> bool:
    """True bila teks berakhir dengan penanda kalimat."""
    return text.strip().endswith(SENTENCE_END)


def _slice_times(seg: Segment, words: list[str]) -> list[tuple[float, float, str]]:
    """Pecah satu segmen menjadi kalimat dengan waktu proporsional per kata."""
    total = max(len(words), 1)
    span = max(seg.t1 - seg.t0, 0.001)
    per_word = span / total
    out: list[tuple[float, float, str]] = []
    buf: list[str] = []
    start_index = 0
    for index, word in enumerate(words):
        buf.append(word)
        if word.endswith(SENTENCE_END):
            t0 = seg.t0 + start_index * per_word
            t1 = seg.t0 + (index + 1) * per_word
            out.append((round(t0, 3), round(t1, 3), " ".join(buf)))
            buf = []
            start_index = index + 1
    if buf:
        t0 = seg.t0 + start_index * per_word
        out.append((round(t0, 3), round(seg.t1, 3), " ".join(buf)))
    return out


def segment_transcript(segments: list[Segment]) -> list[Segment]:
    """Pecah transkrip pada jeda lebih dari 0.8 detik dan penanda kalimat."""
    sentences: list[tuple[float, float, str]] = []
    for seg in segments:
        if seg.text.strip():
            sentences.extend(_slice_times(seg, _words(seg)))

    merged: list[Segment] = []
    for t0, t1, text in sentences:
        if merged:
            prev = merged[-1]
            gap = t0 - prev.t1
            same_block = gap <= PAUSE_S and not _ends_sentence(prev.text)
            if same_block and (t1 - prev.t0) <= MAX_DURATION_S:
                merged[-1] = Segment(
                    t0=prev.t0,
                    t1=t1,
                    text=(prev.text + " " + text).strip(),
                    words=[*prev.words],
                )
                continue
        merged.append(Segment(t0=t0, t1=t1, text=text.strip()))

    tidy: list[Segment] = []
    for seg in merged:
        if len(seg.text.split()) < MIN_WORDS and tidy:
            prev = tidy[-1]
            tidy[-1] = Segment(
                t0=prev.t0,
                t1=seg.t1,
                text=(prev.text + " " + seg.text).strip(),
                words=[*prev.words],
            )
            continue
        tidy.append(seg)
    return tidy
