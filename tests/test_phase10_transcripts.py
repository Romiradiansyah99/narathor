"""Phase 10: transcripts from a machine YouTube does not trust.

The transcript API is refused from cloud IPs. Subtitles through yt-dlp, with a
cookies file, are not. These tests cover the parser, the option plumbing, and
the way a refusal is classified instead of being reported as a missing caption.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from contracts import Video
from ingest import captions, subtitles, ytdlp

VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.500 --> 00:00:04.000 align:start position:0%
so the money problem

00:00:04.000 --> 00:00:08.250
<v Speaker>is never about how much comes in

00:00:08.250 --> 00:00:12.000
it is about where it goes

00:00:12.000 --> 00:00:12.000
it is about where it goes
"""

VIDEO = Video(video_id="abc123", title="T", duration_s=600, url="https://youtu.be/abc123")


def test_parse_vtt_reads_cues() -> None:
    segments = subtitles.parse_vtt(VTT)
    assert len(segments) == 3
    assert segments[0].t0 == 0.5
    assert segments[0].t1 == 4.0
    assert segments[1].text == "is never about how much comes in"
    assert segments[2].t1 > segments[2].t0


def test_parse_vtt_drops_repeated_lines() -> None:
    doubled = VTT + "\n00:00:13.000 --> 00:00:14.000\nit is about where it goes\n"
    segments = subtitles.parse_vtt(doubled)
    texts = [s.text for s in segments]
    assert texts.count("it is about where it goes") == 1


def test_parse_vtt_ignores_empty_text() -> None:
    assert subtitles.parse_vtt("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n\n") == []


def test_base_options_reads_the_cookies_file(tmp_path: Path, monkeypatch) -> None:
    cookie = tmp_path / "cookies.txt"
    cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("YT_COOKIES_FILE", str(cookie))
    monkeypatch.setenv("YT_PROXY", "http://127.0.0.1:8888")
    options = ytdlp.base_options()
    assert options["cookiefile"] == str(cookie)
    assert options["proxy"] == "http://127.0.0.1:8888"
    assert ytdlp.cookies_present() is True


def test_base_options_ignores_a_missing_cookie_file(monkeypatch) -> None:
    monkeypatch.setenv("YT_COOKIES_FILE", "/nope/cookies.txt")
    monkeypatch.delenv("YT_PROXY", raising=False)
    assert "cookiefile" not in ytdlp.base_options()
    assert ytdlp.cookies_present() is False


class _WritingYDL:
    """Fake yt-dlp that writes a WEBVTT the way the real one does."""

    written: str = VTT

    def __init__(self, options: dict) -> None:
        self.options = options

    def __enter__(self) -> _WritingYDL:
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def download(self, urls: list[str]) -> None:
        outtmpl = self.options["outtmpl"]
        target = Path(outtmpl.replace("%(id)s", "abc123").replace("%(ext)s", "en.vtt"))
        target.write_text(self.written, encoding="utf-8")


class _Module:
    YoutubeDL = _WritingYDL


def test_fetch_returns_segments(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "yt_dlp", _Module())
    doc = subtitles.fetch(VIDEO, workdir=tmp_path)
    assert doc is not None
    assert doc.video_id == "abc123"
    assert len(doc.segments) == 3
    assert str(doc.source) == "captions"


def test_fetch_returns_none_when_no_track(monkeypatch, tmp_path: Path) -> None:
    class _Empty(_WritingYDL):
        def download(self, urls: list[str]) -> None:
            return None

    class _EmptyModule:
        YoutubeDL = _Empty

    monkeypatch.setitem(sys.modules, "yt_dlp", _EmptyModule())
    assert subtitles.fetch(VIDEO, workdir=tmp_path) is None


def test_fetch_raises_with_the_reason(monkeypatch, tmp_path: Path) -> None:
    class _Boom(_WritingYDL):
        def download(self, urls: list[str]) -> None:
            raise RuntimeError("Sign in to confirm you are not a bot")

    class _BoomModule:
        YoutubeDL = _Boom

    monkeypatch.setitem(sys.modules, "yt_dlp", _BoomModule())
    with pytest.raises(RuntimeError, match="not a bot"):
        subtitles.fetch(VIDEO, workdir=tmp_path)


def test_blocked_caption_is_classified(monkeypatch) -> None:
    class _Api:
        def fetch(self, *_a, **_k):
            raise type("RequestBlocked", (Exception,), {})("nope")

    class _Mod:
        YouTubeTranscriptApi = _Api

    monkeypatch.setitem(sys.modules, "youtube_transcript_api", _Mod())
    with pytest.raises(captions.TranscriptBlocked):
        captions.fetch(VIDEO)


def test_missing_caption_is_not_an_error(monkeypatch) -> None:
    class _Api:
        def fetch(self, *_a, **_k):
            return []

    class _Mod:
        YouTubeTranscriptApi = _Api

    monkeypatch.setitem(sys.modules, "youtube_transcript_api", _Mod())
    assert captions.fetch(VIDEO) is None


def test_ingest_report_carries_the_reason() -> None:
    from ingest.base import IngestReport

    report = IngestReport()
    report.skipped.append("abc123")
    report.errors["abc123"] = "TranscriptBlocked: RequestBlocked"
    payload = report.as_dict()
    assert payload["errors"]["abc123"].startswith("TranscriptBlocked")
