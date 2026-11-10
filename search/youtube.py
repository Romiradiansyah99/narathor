"""Search inside YouTube, not the open web.

When the question is "what does this space already look like", the answer lives on
YouTube: the videos, the channels that make them, how long they run and how many
people watched. A general web search returns blog posts about those videos.

This module reads yt-dlp's search results, which carry views, duration and channel.
No transcript is involved, so it keeps working on a datacenter IP where the
transcript endpoints are blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingest import ytdlp
from ingest.profile import duration, human

WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class Hit:
    """One video, with the numbers a person uses to judge it."""

    video_id: str
    title: str
    channel: str = ""
    duration_s: int = 0
    views: int = 0
    description: str = ""

    @property
    def url(self) -> str:
        """Where the video lives."""
        return WATCH_URL.format(video_id=self.video_id)

    def line(self) -> str:
        """One row for the console: what it is, who made it, how it did."""
        bits = [duration(self.duration_s)]
        if self.views:
            bits.append(f"{human(self.views)} tonton")
        if self.channel:
            bits.append(self.channel)
        return f"{self.title[:80]} ({', '.join(bits)})"

    def as_dict(self) -> dict[str, Any]:
        """Shape kept in the session."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel": self.channel,
            "url": self.url,
            "duration_s": self.duration_s,
            "views": self.views,
        }


def find_videos(query: str, limit: int = 6) -> list[Hit]:
    """Search YouTube and return what it found, best match first."""
    import yt_dlp

    cleaned = " ".join(query.split())
    if not cleaned:
        return []
    options: Any = ytdlp.base_options()
    options.update({"extract_flat": "in_playlist", "playlistend": max(limit, 1)})
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{cleaned}", download=False)
    hits: list[Hit] = []
    for entry in (info or {}).get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        hits.append(
            Hit(
                video_id=str(entry.get("id")),
                title=str(entry.get("title") or entry.get("id")),
                channel=str(entry.get("channel") or entry.get("uploader") or ""),
                duration_s=int(entry.get("duration") or 0),
                views=int(entry.get("view_count") or 0),
                description=str(entry.get("description") or ""),
            )
        )
        if len(hits) >= limit:
            break
    return hits


def as_results(hits: list[Hit]) -> list[tuple[str, str, str]]:
    """(title, url, detail) rows, the shape the console already prints."""
    return [(hit.title, hit.url, hit.line()) for hit in hits]
