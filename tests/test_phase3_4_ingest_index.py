"""Test Fase 3 dan 4: ingest dan indexer. Tidak menyentuh jaringan."""

from __future__ import annotations

from contracts import Segment, SourceKind, TranscriptDoc, Video
from index import features as feat
from index.build import build_cards, key_quote
from index.segmenter import segment_transcript
from ingest.base import IngestReport
from ingest.pipeline import MemoryStore, run

VIDEOS = [
    Video(video_id="VID-0001", title="A", duration_s=100),
    Video(video_id="VID-0002", title="B", duration_s=100),
    Video(video_id="VID-0003", title="C", duration_s=100),
]


def _doc(video_id: str, text: str, source: SourceKind = SourceKind.CAPTIONS) -> TranscriptDoc:
    return TranscriptDoc(
        video_id=video_id,
        language="id",
        source=source,
        segments=[Segment(t0=0.0, t1=5.0, text=text)],
    )


def test_caption_used_when_available() -> None:
    store = MemoryStore()
    report = run(VIDEOS[:1], store, captions=lambda v: _doc(v.video_id, "caption ada"))
    assert report.ingested == ["VID-0001"]
    assert report.sources["VID-0001"] == SourceKind.CAPTIONS
    assert store.get("VID-0001") is not None


def test_whisper_fallback_when_caption_missing() -> None:
    store = MemoryStore()
    report = run(
        VIDEOS[:1],
        store,
        captions=lambda v: None,
        whisper=lambda v: _doc(v.video_id, "hasil whisper", SourceKind.WHISPER),
    )
    assert report.ingested == ["VID-0001"]
    assert report.sources["VID-0001"] == SourceKind.WHISPER


def test_rerun_hits_cache_without_download() -> None:
    store = MemoryStore()
    calls: list[str] = []

    def captions(video: Video) -> TranscriptDoc:
        calls.append(video.video_id)
        return _doc(video.video_id, "isi")

    run(VIDEOS[:1], store, captions=captions)
    second = run(VIDEOS[:1], store, captions=captions)
    assert calls == ["VID-0001"]
    assert second.cached == ["VID-0001"]
    assert second.ingested == []


def test_video_without_audio_is_skipped_and_run_continues() -> None:
    store = MemoryStore()

    def captions(video: Video) -> TranscriptDoc | None:
        return None if video.video_id == "VID-0002" else _doc(video.video_id, "isi")

    report = run(VIDEOS, store, captions=captions, whisper=lambda v: None)
    assert report.skipped == ["VID-0002"]
    assert len(report.ingested) == 2


def test_report_records_source_per_video() -> None:
    store = MemoryStore()
    report = run(VIDEOS[:2], store, captions=lambda v: _doc(v.video_id, "isi"))
    payload = report.as_dict()
    assert payload["sources"] == {"VID-0001": "captions", "VID-0002": "captions"}
    assert isinstance(report, IngestReport)


def test_force_ignores_cache() -> None:
    store = MemoryStore()
    run(VIDEOS[:1], store, captions=lambda v: _doc(v.video_id, "isi"))
    report = run(VIDEOS[:1], store, captions=lambda v: _doc(v.video_id, "isi baru"), force=True)
    assert report.ingested == ["VID-0001"]


def test_segmenter_splits_on_pause() -> None:
    segs = [
        Segment(t0=0.0, t1=3.0, text="Ini kalimat pertama tanpa titik"),
        Segment(t0=5.5, t1=8.0, text="Ini kalimat setelah jeda panjang"),
    ]
    out = segment_transcript(segs)
    assert len(out) == 2
    assert out[0].t0 == 0.0


def test_segmenter_merges_short_fragments() -> None:
    segs = [
        Segment(t0=0.0, t1=3.0, text="Kalimat yang cukup panjang di sini"),
        Segment(t0=3.1, t1=3.6, text="pendek"),
    ]
    out = segment_transcript(segs)
    assert len(out) == 1
    assert "pendek" in out[0].text


def test_filler_detected() -> None:
    positions = feat.filler_positions(["jadi", "gini", "bro", "apa", "ya", "maksudnya"])
    assert 0 in positions


def test_setup_preamble_detected() -> None:
    assert feat.has_setup_preamble("Sebelum itu, saya mau cerita dulu") is True
    assert feat.has_setup_preamble("Masalahnya ada di aliran") is False


def test_wpm_computed() -> None:
    assert feat.wpm("satu dua tiga empat lima enam", 0.0, 6.0) == 60.0


def test_dead_air_spans() -> None:
    segs = [Segment(t0=0.0, t1=2.0, text="a"), Segment(t0=6.0, t1=8.0, text="b")]
    assert feat.dead_air(segs) == [(2.0, 6.0)]


def test_cards_drop_short_and_long_segments() -> None:
    doc = TranscriptDoc(
        video_id="VID-0001",
        language="id",
        source=SourceKind.CAPTIONS,
        segments=[
            Segment(t0=0.0, t1=1.0, text="dua kata"),
            Segment(t0=2.0, t1=90.0, text="kalimat ini sangat panjang " * 8),
            Segment(t0=100.0, t1=110.0, text="Masalahnya ada di arah aliran uang kamu"),
        ],
    )
    cards = build_cards(doc)
    assert len(cards) == 1
    assert cards[0].video_id == "VID-0001"


def test_card_size_bounded() -> None:
    doc = TranscriptDoc(
        video_id="VID-0001",
        language="id",
        source=SourceKind.CAPTIONS,
        segments=[Segment(t0=0.0, t1=20.0, text="kata " * 400)],
    )
    card = build_cards(doc)[0]
    assert len(card.key_quote.split()) <= 15


def test_key_quote_picks_longest_sentence() -> None:
    quote = key_quote("Pendek. Ini kalimat yang jauh lebih panjang dari yang lain.")
    assert quote.startswith("Ini kalimat")


def test_kind_classification() -> None:
    from index.kinds import classify

    assert classify("Sebenarnya masalahnya ada di arah", False) == "thesis"
    assert classify("Angkanya 30 persen dari total", False) == "number"
    assert classify("Tapi itu keliru menurut data", False) == "rebuttal"
