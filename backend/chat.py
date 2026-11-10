"""The chat. One column: you type, it answers, it runs.

The console is a conversation, not a form. Every message is read for what it
adds: a channel, a topic, an audience, a tone, a number of scripts. Whatever is
still missing gets asked, one short question at a time. When nothing is missing
the pipeline runs, and the scripts come back as text.

Nothing here is decorative. There is no soul panel, no library table, no
counter in a footer. State lives in the session file, the answer lives in the
transcript.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.engine import Engine

from backend import db
from backend.config import Settings
from backend.jobs import Job, Registry
from briefs import load as briefs_load

URL_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?youtube\.com/[^\s<>\"']+", re.I)
BARE_HOST_RE = re.compile(r"\byoutube\.com/[^\s<>\"']+", re.I)
HANDLE_RE = re.compile(r"(?:^|[\s(])@([A-Za-z0-9._-]{2,})")
COUNT_RE = re.compile(r"\b(\d{1,2})\s*(?:naskah|script|naskahnya|video|vid)\b", re.I)
DURATION_RE = re.compile(r"\b(\d{1,2})\s*(?:detik|detiknya|sec|second|s)\b", re.I)

RESET_WORDS = {"reset", "ulang", "mulai ulang", "dari awal", "batal", "clear"}
TOPIC_MARKERS = ("soal", "tentang", "tema", "topik", "bahas", "angkat")
AUDIENCE_MARKERS = ("buat", "untuk", "target", "audience", "penonton")
TONE_MARKERS = ("tone", "gaya", "nada")

DEFAULT_TONE = "santai, langsung, tanpa menggurui"
DEFAULT_AVOID = ["menggurui", "jargon"]
DEFAULT_DURATION = 15
DEFAULT_COUNT = 3
MIN_DURATION_S = 180

PLANNER_SYSTEM = (
    "Kamu asisten produksi konten yang membaca satu pesan user lalu mengeluarkan JSON. "
    "Balas JSON saja, tanpa penjelasan, tanpa markdown."
)

PLANNER_PROMPT = """Baca pesan user, keluarkan objek JSON dengan kunci berikut:
channel_url (link atau @handle channel YouTube, null kalau tidak ada),
topic (topik naskah, satu frasa pendek, null kalau tidak ada),
audience (siapa penontonnya, null kalau tidak ada),
message (satu pesan yang harus nyangkut di kepala penonton, kalimat pendek, null kalau tidak ada),
tone (gaya penyampaian, null kalau tidak ada),
count (jumlah naskah yang diminta sebagai angka, null kalau tidak ada),
duration (durasi tiap naskah dalam detik, null kalau tidak ada).

Aturan: jangan mengarang nilai yang tidak disebut user. Kalau user cuma menyapa atau
bertanya, semua kunci null.

Pesan user:
{message}"""


@dataclass
class Session:
    """One conversation: what the user already told us, and what was said."""

    sid: str
    slots: dict[str, Any] = field(default_factory=dict)
    messages: list[dict[str, str]] = field(default_factory=list)
    channel_fetched: bool = False
    ingest_tried: bool = False
    ran: bool = False
    brief_id: str | None = None
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Shape that gets written to disk."""
        return {
            "sid": self.sid,
            "slots": self.slots,
            "messages": self.messages,
            "channel_fetched": self.channel_fetched,
            "ingest_tried": self.ingest_tried,
            "ran": self.ran,
            "brief_id": self.brief_id,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Session:
        """Rebuild a session from disk, tolerating older files."""
        return cls(
            sid=str(payload.get("sid") or uuid.uuid4().hex[:16]),
            slots=dict(payload.get("slots") or {}),
            messages=list(payload.get("messages") or []),
            channel_fetched=bool(payload.get("channel_fetched")),
            ingest_tried=bool(payload.get("ingest_tried")),
            ran=bool(payload.get("ran")),
            brief_id=payload.get("brief_id"),
            updated_at=str(payload.get("updated_at") or ""),
        )


class SessionStore:
    """Sessions on disk, one JSON file each, so a tunnel restart keeps the thread."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def path(self, sid: str) -> Path:
        """Where one session lives."""
        safe = re.sub(r"[^A-Za-z0-9_-]", "", sid)[:64] or "anon"
        return self._dir / f"{safe}.json"

    def load(self, sid: str) -> Session:
        """Read a session, or start a fresh one."""
        target = self.path(sid)
        if target.exists():
            try:
                return Session.from_dict(json.loads(target.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        return Session(sid=sid)

    def save(self, session: Session) -> None:
        """Write the session. A failure here must not break the reply."""
        session.updated_at = datetime.now(UTC).isoformat()
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self.path(session.sid).write_text(
                json.dumps(session.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Reading a message
# --------------------------------------------------------------------------- #


def _url_from(text: str) -> str | None:
    """Pull a channel URL out of free text, including a bare handle."""
    match = URL_RE.search(text)
    if match:
        return match.group(0).rstrip(".,;)")
    match = BARE_HOST_RE.search(text)
    if match:
        return f"https://{match.group(0).rstrip('.,;)')}"
    match = HANDLE_RE.search(text)
    if match:
        return f"https://www.youtube.com/@{match.group(1)}"
    return None


def _after_marker(text: str, markers: tuple[str, ...]) -> str | None:
    """Take whatever follows 'soal', 'buat', 'tone', and cut it at a comma."""
    lowered = text.lower()
    for marker in markers:
        match = re.search(rf"(?:^|\s){marker}\s+", lowered)
        if match is None:
            continue
        tail = text[match.end() :].strip(" :.,-")
        tail = URL_RE.sub(" ", tail)
        tail = re.split(r"[,.;]|\s+(?:buat|untuk|tone|gaya|dengan)\s+", tail, maxsplit=1)[0]
        tail = " ".join(tail.split()).strip(" :.,-")
        if tail:
            return tail
    return None


def extract_rules(message: str) -> dict[str, Any]:
    """Deterministic reading. Always available, never calls the network."""
    found: dict[str, Any] = {}
    url = _url_from(message)
    if url:
        found["channel_url"] = url
    count = COUNT_RE.search(message)
    if count:
        found["count"] = max(1, min(20, int(count.group(1))))
    duration = DURATION_RE.search(message)
    if duration:
        found["duration"] = int(duration.group(1))
    topic = _after_marker(message, TOPIC_MARKERS)
    if topic:
        found["topic"] = topic
    audience = _after_marker(message, AUDIENCE_MARKERS)
    if audience:
        found["audience"] = audience
    tone = _after_marker(message, TONE_MARKERS)
    if tone:
        found["tone"] = tone
    return found


def _parse_json(text: str) -> dict[str, Any]:
    """Read the first JSON object in a model answer."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {k: v for k, v in payload.items() if v not in (None, "", "null")}


def understand(
    message: str,
    llm: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Merge the model's reading with the rules; rules win where they are exact."""
    found: dict[str, Any] = {}
    if llm is not None:
        try:
            found.update(_parse_json(llm(PLANNER_PROMPT.format(message=message))))
        except Exception:
            found = {}
    rules = extract_rules(message)
    merged = {**found, **rules}
    cleaned: dict[str, Any] = {}
    for key in ("channel_url", "topic", "audience", "message", "tone"):
        value = merged.get(key)
        if isinstance(value, str) and value.strip():
            cleaned[key] = value.strip()
    for key in ("count", "duration"):
        value = merged.get(key)
        if (isinstance(value, int | float) and value > 0) or (
            isinstance(value, str) and value.isdigit()
        ):
            cleaned[key] = int(value)
    return cleaned


# --------------------------------------------------------------------------- #
# Turning slots into a brief the validator accepts
# --------------------------------------------------------------------------- #


def slug(text: str) -> str:
    """A brief id from a topic, lowercase and dash separated."""
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (base[:40].strip("-") or "naskah-baru") + "-" + uuid.uuid4().hex[:4]


def _sentence(text: str) -> str:
    """Trim a topic into something that reads like a line, not a form field."""
    cleaned = text.strip().rstrip(".")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


def compose_brief(slots: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Build a brief payload from what the user said. Returns (id, payload)."""
    topic = _sentence(str(slots.get("topic") or "naskah pendek"))
    stick = str(slots.get("message") or "").strip() or topic
    audience = str(slots.get("audience") or "penonton umum").strip()
    tone = str(slots.get("tone") or DEFAULT_TONE).strip()
    count = int(slots.get("count") or DEFAULT_COUNT)
    duration = int(slots.get("duration") or DEFAULT_DURATION)
    if duration not in range(13, 21) and duration != 60:
        duration = DEFAULT_DURATION

    brief_id = slug(topic)
    payload: dict[str, Any] = {
        "id": brief_id,
        "title": topic[:90],
        "learning_outcome": f"Setelah nonton, penonton paham satu hal: {stick.rstrip('.')}.",
        "thesis": stick,
        "audience": {
            "primary": audience,
            "literacy_level": "menengah",
            "pain_points": [],
        },
        "values_allowed": ["transparansi", "keterlacakan"],
        "values_blocked": [],
        "register_level": 2,
        "tone": {"target": tone, "avoid": list(DEFAULT_AVOID)},
        "seasonal_context": {
            "as_of": datetime.now(UTC).date().isoformat(),
            "period": None,
            "moments": [],
            "trend_notes": "",
        },
        "sources": {
            "channels": [str(slots.get("channel_url") or "")],
            "recency_preference": "any",
            "min_duration_s": MIN_DURATION_S,
        },
        "output": {
            "scripts": max(1, min(20, count)),
            "target_duration_s": duration,
            "language": "id",
            "montages": 0,
        },
    }
    return brief_id, payload


# --------------------------------------------------------------------------- #
# Printing scripts back into the chat
# --------------------------------------------------------------------------- #


def _mmss(seconds: float) -> str:
    """Seconds as mm:ss."""
    total = round(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


STOPWORDS = {
    "yang",
    "untuk",
    "dengan",
    "dalam",
    "adalah",
    "karena",
    "tetapi",
    "tapi",
    "kalau",
    "bukan",
    "juga",
    "akan",
    "bisa",
    "harus",
    "sudah",
    "belum",
    "masih",
    "lebih",
    "sangat",
    "kita",
    "kamu",
    "saya",
    "mereka",
    "orang",
    "jadi",
    "atau",
    "pada",
    "dari",
    "saja",
    "itu",
    "ini",
    "ada",
    "tidak",
    "bagi",
    "saat",
    "ketika",
    "seperti",
    "supaya",
    "agar",
    "pernah",
    "semua",
    "banyak",
    "gitu",
    "gini",
    "banget",
    "memang",
    "cuma",
    "hanya",
    "sama",
    "satu",
    "video",
    "naskah",
    "soal",
    "tentang",
    "bikin",
    "buat",
}


def library_hints(engine: Engine, limit: int = 6) -> list[str]:
    """The words a library actually talks about, so a topic can be aimed at it."""
    counts: dict[str, int] = {}
    for video in db.fetch_videos(engine):
        doc = db.fetch_transcript(engine, video.video_id)
        if doc is None:
            continue
        for segment in doc.segments:
            text = str(getattr(segment, "text", "") or "")
            for word in re.findall(r"[a-zA-Z]{5,}", text.lower()):
                if word in STOPWORDS:
                    continue
                counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, count in ranked[:limit] if count > 1] or [w for w, _ in ranked[:limit]]


def format_scripts(files: list[Path]) -> str:
    """Render saved scripts as the text the chat shows."""
    blocks: list[str] = []
    for index, path in enumerate(files, start=1):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        title = str(doc.get("title") or "tanpa judul")
        duration = doc.get("target_duration_s") or 15
        lines = [f"naskah {index} — {title} · {duration} detik", ""]
        for beat in doc.get("beats") or []:
            at = _mmss(float(beat.get("at_s") or 0))
            lines.append(f"{at}  {beat.get('text') or ''}")
            citation = beat.get("citation") or {}
            if citation:
                t0 = float(citation.get("t0") or 0)
                t1 = float(citation.get("t1") or 0)
                lines.append(f"        {citation.get('video_id')} {t0:.1f}-{t1:.1f}s")
        blocks.append("\n".join(lines))
    return "\n\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# The conversation
# --------------------------------------------------------------------------- #


class Chat:
    """Answers one message at a time, and starts work when there is enough to start."""

    def __init__(
        self,
        settings: Settings,
        engine: Engine,
        jobs: Registry,
        store: SessionStore | None = None,
        llm: Callable[[str], str] | None = None,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.jobs = jobs
        self.store = store or SessionStore(settings.output_dir / "_chat")
        self._llm = llm
        self._llm_ready = llm is not None

    # -- model ---------------------------------------------------------- #

    def model(self) -> Callable[[str], str] | None:
        """The planner model, built once. Missing key means rules only."""
        if not self._llm_ready:
            self._llm_ready = True
            if os.environ.get("NARATHOR_CHAT_MODEL", "").strip().lower() in {"off", "0", "no"}:
                self._llm = None
                return None
            try:
                from agent.models import for_role

                planner = for_role("matcher")

                def call(prompt: str) -> str:
                    return planner.complete(prompt, system=PLANNER_SYSTEM)

                self._llm = call
            except Exception:
                self._llm = None
        return self._llm

    # -- public --------------------------------------------------------- #

    def history(self, sid: str) -> dict[str, Any]:
        """Everything said so far, for a page that just loaded."""
        session = self.store.load(sid)
        return {"sid": session.sid, "messages": session.messages, "slots": session.slots}

    def handle(self, sid: str, message: str | None = None, advance: bool = False) -> dict[str, Any]:
        """Read one message, or resume after a job finished, and answer."""
        session = self.store.load(sid)

        if message and message.strip():
            text = message.strip()
            if text.lower() in RESET_WORDS:
                session = Session(sid=session.sid)
                session.messages.append({"role": "user", "text": text})
                reply = ["oke, gue lupa semuanya. mulai dari channel youtube-nya."]
                session.messages.extend({"role": "bot", "text": line} for line in reply)
                self.store.save(session)
                return {"sid": session.sid, "reply": reply, "job_id": None, "messages": []}
            session.slots.update(understand(text, self.model()))
            session.ran = False
            if "coba lagi" in text.lower():
                session.ingest_tried = False
                session.channel_fetched = False
            session.messages.append({"role": "user", "text": text})

        reply, job = self._next(session)
        session.messages.extend({"role": "bot", "text": line} for line in reply)
        self.store.save(session)
        return {
            "sid": session.sid,
            "reply": reply,
            "job_id": job.job_id if job else None,
            "job_kind": job.kind if job else None,
        }

    # -- decisions ------------------------------------------------------ #

    def _counts(self) -> tuple[Any, int, int]:
        """Channel, videos, transcripts. The only state that matters."""
        channel = db.fetch_channel(self.engine)
        videos = db.fetch_videos(self.engine)
        transcripts = sum(
            1 for video in videos if db.fetch_transcript(self.engine, video.video_id) is not None
        )
        return channel, len(videos), transcripts

    def _next(self, session: Session) -> tuple[list[str], Job | None]:
        """What to say next, and the job to start if the next step is work."""
        slots = session.slots
        channel, videos, transcripts = self._counts()

        url = str(slots.get("channel_url") or "").strip()
        if not url and channel is not None:
            slots["channel_url"] = channel.url
            url = channel.url

        if not url:
            return (
                ["gas. channel youtube-nya mana? tempel link atau @handle-nya."],
                None,
            )

        if not session.channel_fetched and (channel is None or channel.url != url):
            job = self._channel_job(session, url)
            session.channel_fetched = True
            return (["siap, gue baca dulu daftar video di channel itu."], job)

        if channel is None or videos == 0:
            return (
                [
                    "channel-nya nggak kebaca. bisa jadi link-nya salah atau videonya kosong.",
                    "coba tempel link lain, format youtube.com/@handle.",
                ],
                None,
            )

        if not slots.get("topic"):
            return (
                [
                    f"dapet {videos} video.",
                    "sekarang mau bikin naskah soal apa? satu kalimat aja, santai.",
                ],
                None,
            )

        if transcripts == 0:
            if session.ingest_tried:
                return (
                    [
                        "transkripnya tetap nol. youtube nolak mesin ini, bukan videonya.",
                        "pilih satu: taruh cookies.txt dari browser kamu, pasang proxy residensial,",
                        "atau jalanin ingest dari laptop lalu kirim hasilnya ke sini.",
                        "kalau sudah beres, bilang 'coba lagi'.",
                    ],
                    None,
                )
            job = self._ingest_job(session, videos)
            session.ingest_tried = True
            return (["transkripnya belum ada. gue ambil dulu, bentar."], job)

        return self._run_turn(session, videos, transcripts)

    def _run_turn(
        self, session: Session, videos: int, transcripts: int
    ) -> tuple[list[str], Job | None]:
        """Compose the brief, save it, and start the pipeline."""
        if session.ran:
            return (
                [
                    "yang tadi udah kelar, hasilnya di atas.",
                    "mau ubah arahan? kirim aja, gue rangkai ulang dari nol.",
                ],
                None,
            )
        brief_id, payload = compose_brief(session.slots)
        report = briefs_load.validate(brief_id, payload)
        if not report.ok:
            reasons = "; ".join(f"{r.code} {r.message}" for r in report.rejections)
            return (
                [f"brief-nya ditolak mesin: {reasons}", "ubah arahan dikit, lalu kirim lagi."],
                None,
            )

        path = briefs_load.brief_path(self.settings.briefs_dir, brief_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        session.brief_id = brief_id
        session.ran = True

        count = int(payload["output"]["scripts"])
        duration = int(payload["output"]["target_duration_s"])
        opening = [
            f"{transcripts} transkrip siap, {videos} video di pustaka.",
            f"gue rangkai {count} naskah {duration} detik. jalan.",
        ]
        return (opening, self._run_job(brief_id))

    # -- jobs ----------------------------------------------------------- #

    def _channel_job(self, session: Session, url: str) -> Job:
        """Read the channel's video tab into the library."""
        from ingest.channel import discover

        limit = 25
        engine = self.engine

        def work(log: Callable[[str], None]) -> dict[str, Any]:
            channel, found = discover(url, limit=limit, log=log)
            log(f"ketemu {len(found)} video di {channel.name}")
            counts = db.save_library(engine, channel, found)
            log(f"pustaka sekarang {counts['videos']} video")
            return {"channel": channel.name, "videos": counts["videos"]}

        return self.jobs.start("channel", f"channel {url}", work)

    def _ingest_job(self, session: Session, videos: int) -> Job:
        """Fetch transcripts: captions first, Whisper second."""
        from ingest.pipeline import DbStore, default_fetchers
        from ingest.pipeline import run as run_ingest

        engine = self.engine
        brief_id = session.brief_id
        min_duration = MIN_DURATION_S
        if brief_id:
            try:
                brief = briefs_load.load_or_raise(self.settings.briefs_dir, brief_id)
                min_duration = brief.sources.min_duration_s
            except Exception:
                min_duration = MIN_DURATION_S

        def work(log: Callable[[str], None]) -> dict[str, Any]:
            class LoggingStore(DbStore):
                """DbStore that says what it wrote."""

                def put(self, doc) -> None:
                    super().put(doc)
                    log(f"{doc.video_id}: {doc.source}, {len(doc.segments)} potongan")

            rows = [v for v in db.fetch_videos(engine) if v.duration_s >= min_duration]
            log(f"{len(rows)} video bakal diambil transkripnya")
            captions, whisper = default_fetchers()
            report = run_ingest(rows, LoggingStore(engine), captions, whisper)
            for video_id in report.cached:
                log(f"{video_id}: udah ada, nggak diunduh ulang")
            for video_id in report.skipped:
                log(f"{video_id}: gagal, {report.errors.get(video_id, 'tidak ada transkrip')}")
            blocked = sum(1 for e in report.errors.values() if "Blocked" in e)
            if blocked:
                log("youtube nolak mesin ini, bukan videonya.")
                log("butuh cookies dari browser kamu, proxy residensial, atau jalan dari laptop.")
            log(
                f"masuk {len(report.ingested)} / cache {len(report.cached)} / gagal {len(report.skipped)}"
            )
            data = report.as_dict()
            data["blocked"] = blocked
            return data

        return self.jobs.start("ingest", f"ingest {videos} video", work)

    def _run_job(self, brief_id: str) -> Job:
        """Assemble scripts and print them as text."""
        from narathor.run import orchestrate

        settings = self.settings
        engine = self.engine

        def work(log: Callable[[str], None]) -> dict[str, Any]:
            log("nyusun kartu segmen dari transkrip")
            summary = orchestrate(brief_id, settings=settings, engine=engine)
            log(f"{summary['cards']} kartu, {summary['combos']} kombinasi")
            log(f"{summary['scripts']} naskah lolos tujuh gate")
            files = sorted(Path(summary["output"]).glob("scripts/*.json"))
            if not files:
                hints = library_hints(engine)
                topic_line = (
                    f"pustaka ini paling banyak bicara soal: {', '.join(hints)}."
                    if hints
                    else "transkripnya belum ada, jadi belum ada bahan."
                )
                return {
                    "lines": ["nol naskah"],
                    "block": (
                        "nggak ada naskah yang lolos gate.\n"
                        f"{topic_line}\n"
                        "pakai salah satu kata itu jadi topik, atau tambah video ke pustaka."
                    ),
                    **summary,
                }
            return {
                "lines": [f"{len(files)} naskah jadi"],
                "block": format_scripts(files),
                **summary,
            }

        return self.jobs.start("run", f"run {brief_id}", work)
