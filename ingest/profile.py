"""What a channel is about, read from the channel itself.

Transcripts are the ideal source and YouTube refuses them from datacenter IPs. Titles,
view counts, durations, the channel description and its tags are not refused, and
together they answer the question someone actually asks when reviewing a channel:
what is this, in what format, what works, and what is missing.

Nothing here calls a model. The output is a set of facts a person can check, and the
console adds a written read on top only when one is asked for.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any

from ingest.channel import ChannelError, normalize

# Words that appear in every Indonesian title and therefore say nothing about content.
TITLE_STOPWORDS = {
    "yang",
    "dan",
    "untuk",
    "dengan",
    "dari",
    "ini",
    "itu",
    "ada",
    "apa",
    "cara",
    "bikin",
    "buat",
    "soal",
    "tentang",
    "saya",
    "kami",
    "kita",
    "kamu",
    "anda",
    "akan",
    "bisa",
    "juga",
    "lebih",
    "paling",
    "dalam",
    "pada",
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "you",
    "your",
    "how",
    "what",
    "why",
    "new",
    "part",
    "episode",
    "ep",
    "full",
    "official",
    "video",
    "youtube",
    "shorts",
    "short",
    "can",
    "here",
    "inside",
    "less",
    "more",
    "not",
    "but",
    "all",
    "who",
    "when",
    "where",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "his",
    "her",
    "their",
    "our",
    "its",
    "it's",
    "is",
    "of",
    "in",
    "on",
    "at",
    "to",
    "a",
    "an",
    "di",
    "ke",
    "si",
    "sih",
    "yg",
    "gak",
    "nggak",
    "tidak",
    "actually",
    "happens",
    "like",
    "get",
    "got",
    "make",
    "made",
    "thing",
    "things",
    "really",
    "every",
    "most",
    "much",
    "many",
    "some",
    "will",
    "would",
    "could",
    "should",
    "about",
    "into",
    "over",
    "out",
    "just",
    "even",
    "than",
    "then",
    "there",
    "these",
    "those",
    "them",
    "they",
    "still",
    "back",
    "never",
    "always",
    "does",
    "did",
    "doing",
    "done",
    "being",
    "been",
    "from",
}

MIN_CLIP_SECONDS = 30


@dataclass(frozen=True)
class Clip:
    """One video, with the numbers that show whether people watched it."""

    video_id: str
    title: str
    duration_s: int = 0
    views: int = 0
    published_day: str = ""


@dataclass(frozen=True)
class Profile:
    """A channel as it describes itself, plus its last few dozen videos."""

    channel_id: str
    name: str
    handle: str
    url: str
    followers: int = 0
    description: str = ""
    tags: list[str] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)

    @property
    def total_views(self) -> int:
        """Views across the clips that were read."""
        return sum(clip.views for clip in self.clips)

    def as_dict(self) -> dict[str, Any]:
        """Shape stored in the session so `/isi` can run without refetching."""
        return {
            "channel_id": self.channel_id,
            "name": self.name,
            "handle": self.handle,
            "url": self.url,
            "followers": self.followers,
            "description": self.description,
            "tags": self.tags,
            "clips": [
                {
                    "video_id": clip.video_id,
                    "title": clip.title,
                    "duration_s": clip.duration_s,
                    "views": clip.views,
                    "published_day": clip.published_day,
                }
                for clip in self.clips
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Profile:
        """Rebuild one from the session file."""
        clips = [
            Clip(
                video_id=str(row.get("video_id") or ""),
                title=str(row.get("title") or ""),
                duration_s=int(row.get("duration_s") or 0),
                views=int(row.get("views") or 0),
                published_day=str(row.get("published_day") or ""),
            )
            for row in payload.get("clips") or []
            if isinstance(row, dict)
        ]
        return cls(
            channel_id=str(payload.get("channel_id") or ""),
            name=str(payload.get("name") or ""),
            handle=str(payload.get("handle") or ""),
            url=str(payload.get("url") or ""),
            followers=int(payload.get("followers") or 0),
            description=str(payload.get("description") or ""),
            tags=[str(tag) for tag in payload.get("tags") or []],
            clips=clips,
        )


def human(number: int) -> str:
    """A count the way a person says it out loud."""
    if number >= 1_000_000_000:
        value, unit = number / 1_000_000_000, "miliar"
    elif number >= 1_000_000:
        value, unit = number / 1_000_000, "juta"
    elif number >= 1_000:
        value, unit = number / 1_000, "ribu"
    else:
        return str(number)
    if unit == "ribu" or value >= 100:
        return f"{int(value + 0.5)} {unit}"
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} {unit}"


def duration(seconds: int) -> str:
    """mm:ss, or h:mm:ss for the long ones."""
    if seconds <= 0:
        return "0:00"
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fetch(url: str, limit: int = 30) -> Profile:
    """Read a channel's video tab with the metadata a review needs."""
    import yt_dlp

    from ingest import ytdlp

    target = normalize(url)
    options: Any = ytdlp.base_options()
    options.update({"extract_flat": "in_playlist", "playlistend": max(limit, 1)})
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as exc:
        raise ChannelError(f"youtube did not answer for {target}: {exc}") from exc
    if not info:
        raise ChannelError(f"no channel data for {target}")

    clips: list[Clip] = []
    for entry in info.get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        seconds = int(entry.get("duration") or 0)
        if seconds and seconds < MIN_CLIP_SECONDS:
            continue
        stamp = str(entry.get("timestamp") or "")
        clips.append(
            Clip(
                video_id=str(entry.get("id")),
                title=str(entry.get("title") or entry.get("id")),
                duration_s=seconds,
                views=int(entry.get("view_count") or 0),
                published_day=stamp[:10],
            )
        )

    handle = str(info.get("uploader_id") or info.get("channel_id") or "unknown")
    return Profile(
        channel_id=str(info.get("channel_id") or handle),
        name=str(info.get("channel") or info.get("uploader") or handle),
        handle=handle,
        url=target,
        followers=int(info.get("channel_follower_count") or 0),
        description=str(info.get("description") or ""),
        tags=[str(tag) for tag in info.get("tags") or []][:20],
        clips=clips,
    )


def keywords(profile: Profile, top: int = 8) -> list[str]:
    """The words the channel keeps putting in its titles.

    A word has to appear in more than one title and in at least a tenth of them:
    a speaker's name once is not a theme, and neither is a word that only shows up
    in a single video.
    """
    counts: dict[str, int] = {}
    for clip in profile.clips:
        seen = set(re.findall(r"[a-zA-Z][a-zA-Z0-9+]{2,}", clip.title.lower()))
        for word in seen:
            if word in TITLE_STOPWORDS or word.isdigit():
                continue
            counts[word] = counts.get(word, 0) + 1
    floor = max(3, int(len(profile.clips) * 0.15))
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [word for word, count in ranked[:top] if count >= floor]


def median_minutes(profile: Profile) -> float:
    """The typical length, which is what the format actually is."""
    lengths = [clip.duration_s for clip in profile.clips if clip.duration_s > 0]
    if not lengths:
        return 0.0
    return statistics.median(lengths) / 60


def overview(profile: Profile) -> list[str]:
    """Five lines that answer 'what is inside this channel' without a model."""
    if not profile.clips:
        return [f"{profile.name}: nggak ada video yang kebaca di tab videos."]

    lines = [f"{profile.name}: {len(profile.clips)} video kebaca"]
    if profile.followers:
        lines[0] += f", {human(profile.followers)} subscriber"

    typical = median_minutes(profile)
    short_share = sum(1 for clip in profile.clips if 0 < clip.duration_s <= 90) / len(profile.clips)
    lines.append(f"format: median {typical:.1f} menit, {short_share:.0%} di bawah 90 detik")

    watched = sorted(profile.clips, key=lambda clip: -clip.views)[:3]
    if watched and watched[0].views:
        tops = ", ".join(f"{clip.title[:45]} ({human(clip.views)})" for clip in watched)
        lines.append(f"paling laku: {tops}")

    words = keywords(profile, top=8)
    if words:
        lines.append("kata yang berulang di judul: " + ", ".join(words))

    if profile.description:
        first = " ".join(profile.description.split())[:200]
        lines.append(f"deskripsi channel: {first}")
    return lines


def model_brief(profile: Profile, max_clips: int = 20) -> str:
    """The raw material for a written read, compact enough for one prompt."""
    lines = [
        f"channel: {profile.name} ({profile.handle})",
        f"subscriber: {human(profile.followers)}"
        if profile.followers
        else "subscriber: tidak terbaca",
        f"deskripsi: {' '.join(profile.description.split())[:600]}",
    ]
    if profile.tags:
        lines.append(f"tag channel: {', '.join(profile.tags[:15])}")
    lines.append("")
    lines.append("video (judul | durasi | tayangan):")
    ranked = sorted(profile.clips, key=lambda clip: -clip.views)[:max_clips]
    for clip in ranked:
        lines.append(f"- {clip.title} | {duration(clip.duration_s)} | {human(clip.views)}")
    return "\n".join(lines)
