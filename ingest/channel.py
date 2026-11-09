"""Channel discovery: from a YouTube channel URL to a list of videos.

The pipeline downstream assumes the library already exists. This module is the
step that creates it, so a channel URL typed into the UI becomes real rows
instead of a promise.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from contracts import Channel, Video
from ingest import ytdlp

VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

# A channel URL may point at the channel root, a tab, or a live page. Anything
# after the handle is dropped, then the videos tab is appended.
_HANDLE = re.compile(
    r"^https?://(?:www\.)?youtube\.com/(@[\w.\-]+|channel/[\w\-]+|c/[\w.\-]+|user/[\w.\-]+)"
)


class ChannelError(RuntimeError):
    """Discovery failed, with a message fit to show a human."""


def normalize(url: str) -> str:
    """Turn any YouTube channel URL into the videos tab."""
    cleaned = url.strip()
    if not cleaned:
        raise ChannelError("channel url is empty")
    if cleaned.startswith("@"):
        cleaned = f"https://www.youtube.com/{cleaned}"
    elif not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned
    match = _HANDLE.match(cleaned)
    if match is None:
        raise ChannelError(f"not a channel url: {url}")
    return f"https://www.youtube.com/{match.group(1)}/videos"


def _parse_date(value: str | None) -> date | None:
    """yt-dlp gives YYYYMMDD strings."""
    if not value:
        return None
    try:
        return datetime.strptime(value[:8], "%Y%m%d").date()
    except ValueError:
        return None


def discover(url: str, limit: int = 25, log=None) -> tuple[Channel, list[Video]]:
    """Read a channel's video tab. No download, no transcript, flat extract."""
    import yt_dlp

    target = normalize(url)
    if log:
        log(f"opening {target}")
    options: Any = ytdlp.base_options()
    options.update(
        {
            "extract_flat": "in_playlist",
            "playlistend": max(limit, 1),
        }
    )
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as exc:
        raise ChannelError(f"youtube did not answer for {target}: {exc}") from exc

    if not info:
        raise ChannelError(f"no channel data for {target}")

    handle = info.get("uploader_id") or info.get("channel_id") or "unknown"
    name = info.get("channel") or info.get("uploader") or handle
    channel = Channel(
        channel_id=str(info.get("channel_id") or handle),
        name=str(name),
        handle=str(handle),
        url=target,
    )

    entries = info.get("entries") or []
    videos: list[Video] = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id")
        if not video_id:
            continue
        videos.append(
            Video(
                video_id=str(video_id),
                title=str(entry.get("title") or video_id),
                duration_s=int(entry.get("duration") or 0),
                published_at=_parse_date(entry.get("upload_date")),
                url=VIDEO_URL.format(video_id=video_id),
            )
        )
        if len(videos) >= limit:
            break

    if log:
        log(f"{len(videos)} videos listed from {channel.name}")
    if not videos:
        raise ChannelError(f"{channel.name} returned no videos on the videos tab")
    return channel, videos
