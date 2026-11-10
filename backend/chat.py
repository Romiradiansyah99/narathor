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

from backend import db, skills
from backend.config import Settings
from backend.jobs import Job, Registry
from briefs import load as briefs_load

URL_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?youtube\.com/[^\s<>\"']+", re.I)
BARE_HOST_RE = re.compile(r"\byoutube\.com/[^\s<>\"']+", re.I)
HANDLE_RE = re.compile(r"(?:^|[\s(])@([A-Za-z0-9._-]{2,})")
VIDEO_LINK_RE = re.compile(
    r"(?:youtube\.com/(?:watch|shorts|live|embed|playlist)|youtu\.be/)", re.I
)
SEARCH_VERBS = r"(?:cari|carikan|search|googling|google|riset|telusuri)"
SEARCH_RE = re.compile(
    rf"^(?:{SEARCH_VERBS}|cek\s+berita)\s+(?:di\s+|ke\s+)?(?:internet\s+|google\s+|web\s+)?(.+)$",
    re.I,
)
PICK_RE = re.compile(r"^pakai\s+(?:nomor\s+|hasil\s+|yang\s+)?(\d{1,2})\b", re.I)
SEARCH_LIMIT = 5
COUNT_RE = re.compile(r"\b(\d{1,2})\s*(?:naskah|script|naskahnya|video|vid)\b", re.I)
DURATION_RE = re.compile(r"\b(\d{1,2})\s*(?:detik|detiknya|sec|second|s)\b", re.I)

RESET_WORDS = {"reset", "ulang", "mulai ulang", "dari awal", "batal", "clear"}
ACTION_VERBS = {
    "bikin",
    "bikinin",
    "buatin",
    "rakit",
    "rakitin",
    "produksi",
    "tulis",
    "tulisin",
    "susun",
    "susunin",
    "generate",
    "jalanin",
    "kerjain",
    "eksekusi",
}
ACKS = {
    "gas",
    "lanjut",
    "oke",
    "ok",
    "ya",
    "sip",
    "ayo",
    "jalan",
    "jalanin",
    "boleh",
    "mantap",
    "go",
}
GREETINGS = {
    "halo",
    "hai",
    "hi",
    "hallo",
    "pagi",
    "siang",
    "malam",
    "test",
    "tes",
    "assalamualaikum",
    "p",
    "ping",
}
TOPIC_MARKERS = ("soal", "tentang", "tema", "topik", "bahas", "angkat")
AUDIENCE_MARKERS = ("buat", "untuk", "target", "audience", "penonton")
TONE_MARKERS = ("tone", "gaya", "nada")

DEFAULT_TONE = "santai, langsung, tanpa menggurui"
CANNED_ANSWERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("buat apa", "bisa apa", "kegunaan", "fungsinya", "ini apa", "ini apaan"),
        "gue bikin naskah short dari video channel kamu. tiap kalimat nempel ke detik sumbernya, "
        "jadi nggak ada klaim tanpa asal. mulai dari link channel, terus kasih topik satu kalimat.",
    ),
    (
        ("cara pakai", "gimana pakai", "gimana caranya", "caranya gimana", "how to"),
        "tiga langkah. tempel link channel, kasih topik, gue rakit naskahnya. "
        "kalau youtube nolak transkrip, tempel cookies.txt dari browser kamu di kolom ini.",
    ),
    (
        ("makasih", "thanks", "thx", "nice", "mantap"),
        "santai. kalau mau lanjut, kasih topik atau link channel.",
    ),
)
DEFAULT_AVOID = ["menggurui", "jargon"]
DEFAULT_DURATION = 15
DEFAULT_COUNT = 3
MIN_DURATION_S = 180

PLANNER_SYSTEM = (
    "Kamu asisten produksi konten yang membaca satu pesan user lalu mengeluarkan JSON. "
    "Balas JSON saja, tanpa penjelasan, tanpa markdown."
)

AGENT_SYSTEM = """Kamu Narathor, editor naskah short di sebuah agensi konten. Kamu ngobrol sama Romi,
yang pegang channel dan briefnya. Kamu bukan formulir. Kamu orang yang sudah biasa kerja:
santai, singkat, langsung, tanpa emoji, tanpa tanda pisah panjang.

Kamu punya alat. Kamu sendiri yang memutuskan kapan memakainya, dan kamu tidak pernah bilang
sudah mengerjakan sesuatu sebelum alatnya benar benar dipanggil.

ATURAN:
- Baca situasinya dulu. Kalau datanya sudah ada, jangan diminta lagi.
- Kalau channel belum ada, minta link atau handle-nya. Jangan mengarang channel.
- Kalau channel ada dan transkripnya nol, panggil ingest tanpa nanya.
- Kalau transkrip ada dan topiknya sudah jelas, panggil assemble tanpa nanya.
- Kalau topik belum jelas, tanya satu hal saja, singkat, kayak ngobrol.
- Kalau hasil alat nol atau gagal, bilang apa adanya dan sebut langkah berikutnya.
- "say" maksimal dua kalimat. Jangan mengulang isi naskah yang sudah tercetak.

Balas JSON dengan bentuk ini:
{"say": "kalimat kamu", "tool": null, "args": {}}

tool hanya boleh: null, "fetch_channel", "ingest", "assemble", "web_search".
args:
- fetch_channel: {"url": "https://www.youtube.com/@handle"}
- ingest: {"limit": 25}
- assemble: {"topic": "...", "audience": "...", "tone": "...", "count": 2, "duration": 15}
- web_search: {"query": "kata kunci pendek"}

Pakai web_search kalau user minta data, berita, contoh, atau fakta dari luar, atau kalau
kamu butuh konteks yang tidak ada di transkrip. Jangan pakai web_search untuk pertanyaan
soal percakapan ini, channel, atau isi pustaka."""


def agent_prompt(session: Session, state: dict[str, Any]) -> str:
    """Everything the agent needs to decide the next move, in one block."""
    lines = [
        "KONDISI SEKARANG",
        f"channel: {state['channel'] or 'belum ada'}",
        f"video di pustaka: {state['videos']}",
        f"transkrip siap: {state['transcripts']}",
        f"topik yang sudah disebut: {session.slots.get('topic') or 'belum ada'}",
        f"audiens: {session.slots.get('audience') or 'belum ada'}",
        f"tone: {session.slots.get('tone') or 'belum ada'}",
        f"jumlah naskah: {session.slots.get('count') or 'belum disebut'}",
        f"alat yang sudah dipanggil untuk pesan ini: {session.tool_calls}",
    ]
    if session.notes:
        lines.append("")
        lines.append("HASIL ALAT TERAKHIR")
        lines.extend(session.notes[-4:])
    lines.append("")
    lines.append("PERCAKAPAN")
    for message in session.messages[-10:]:
        who = {"user": "Romi", "bot": "Kamu", "tool": "hasil alat"}.get(message["role"], "?")
        lines.append(f"{who}: {message['text'][:400]}")
    return "\n".join(lines)


SAY_RE = re.compile(r'"say"\s*:\s*"((?:[^"\\]|\\.)*)"')


def parse_plan(raw: str) -> dict[str, Any] | None:
    """Read the agent's plan, even when the JSON arrived damaged.

    The fast model sometimes runs out of budget mid-object. A truncated answer still
    carries a usable sentence, and dropping it would turn a real reply into a canned
    one, so the sentence is salvaged before giving up.
    """
    payload = _parse_json(raw)
    if not payload:
        salvaged = SAY_RE.search(raw)
        if salvaged:
            text = salvaged.group(1).encode().decode("unicode_escape", "ignore").strip()
            if text:
                return {"say": text, "tool": None, "args": {}}
        prose = raw.strip()
        claims_work = re.search(r"\b(?:gue|aku)\s+(?:ambil|rangkai|baca|jalankan|kerjain)\b", prose)
        if prose and not prose.startswith("{") and len(prose) <= 400 and not claims_work:
            return {"say": prose, "tool": None, "args": {}}
        return None
    say = payload.get("say")
    tool = payload.get("tool")
    args = payload.get("args")
    if tool in {"none", "null", ""}:
        tool = None
    return {
        "say": str(say).strip() if isinstance(say, str) else "",
        "tool": tool if isinstance(tool, str) else None,
        "args": args if isinstance(args, dict) else {},
    }


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
    attempted_url: str = ""
    last_channel_error: str = ""
    research: list[dict[str, str]] = field(default_factory=list)
    ingest_tried: bool = False
    ran: bool = False
    pending_job: str | None = None
    tool_calls: int = 0
    notes: list[str] = field(default_factory=list)
    last_text: str = ""
    brief_id: str | None = None
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Shape that gets written to disk."""
        return {
            "sid": self.sid,
            "slots": self.slots,
            "messages": self.messages,
            "attempted_url": self.attempted_url,
            "last_channel_error": self.last_channel_error,
            "research": self.research,
            "ingest_tried": self.ingest_tried,
            "ran": self.ran,
            "pending_job": self.pending_job,
            "tool_calls": self.tool_calls,
            "notes": self.notes,
            "last_text": self.last_text,
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
            attempted_url=str(payload.get("attempted_url") or ""),
            last_channel_error=str(payload.get("last_channel_error") or ""),
            research=[dict(row) for row in payload.get("research") or [] if isinstance(row, dict)],
            ingest_tried=bool(payload.get("ingest_tried")),
            ran=bool(payload.get("ran")),
            pending_job=payload.get("pending_job"),
            tool_calls=int(payload.get("tool_calls") or 0),
            notes=list(payload.get("notes") or []),
            last_text=str(payload.get("last_text") or ""),
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


def _same_channel(left: str, right: str) -> bool:
    """Two links point at the same channel even when one carries /videos."""

    def key(value: str) -> str:
        text = value.strip().lower().rstrip("/")
        for prefix in ("https://", "http://"):
            text = text.removeprefix(prefix)
        text = text.removeprefix("www.")
        return text.removesuffix("/videos").rstrip("/")

    return bool(left) and key(left) == key(right)


def _short_reason(error: str) -> str:
    """One clause a human can act on, not a wall of yt-dlp output."""
    text = error.split("\n")[0].strip()
    lowered = text.lower()
    if "404" in text:
        return "channel-nya nggak ada, youtube balas 404"
    if "429" in text or "too many requests" in lowered:
        return "youtube nolak karena kebanyakan permintaan, coba lagi nanti"
    if "confirm you" in lowered or "sign in" in lowered or "bot" in lowered:
        return "youtube minta login, ini bot check dari ip server"
    if "timed out" in lowered or "timeout" in lowered:
        return "koneksi ke youtube timeout"
    text = text.replace("ChannelError: ", "").strip()
    text = re.sub(r"^youtube did not answer for \S+: ", "", text)
    text = re.sub(r"^\w*Error: ", "", text)
    return text[:160]


def _link_problem(url: str) -> str | None:
    """Say why a link cannot be a channel before yt-dlp wastes a round trip.

    A watch link is the mistake people actually make, and "coba link lain" is a
    useless answer to it: the link is fine, it is just the wrong kind of page.
    """
    if VIDEO_LINK_RE.search(url):
        return (
            "itu link video, bukan link channel. gue butuh halaman channel-nya: "
            "youtube.com/@nama-channel"
        )
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


COOKIE_MARKER = "# Netscape HTTP Cookie File"


def looks_like_cookies(text: str) -> bool:
    """True when what was pasted is a cookies export, not a sentence."""
    head = text.lstrip()
    if head.startswith(COOKIE_MARKER):
        return True
    return "\tyoutube.com\t" in text and text.count("\t") > 12


def cookies_path(settings: Settings) -> Path:
    """Where the cookies file lives. Gitignored, next to the repo root."""
    return settings.root / "cookies.txt"


def save_cookies(settings: Settings, text: str) -> Path:
    """Write the cookies export and point yt-dlp at it for this process."""
    path = cookies_path(settings)
    body = text if text.endswith("\n") else text + "\n"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)
    os.environ["YT_COOKIES_FILE"] = str(path)
    return path


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

                planner = for_role("router")

                def call(prompt: str) -> str:
                    return planner.complete(prompt, system=AGENT_SYSTEM)

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
            bare = text.lstrip("/").strip().lower()
            if bare in RESET_WORDS:
                session = Session(sid=session.sid)
                session.messages.append({"role": "user", "text": text})
                reply = ["oke, gue lupa semuanya. mulai dari channel youtube-nya."]
                session.messages.extend({"role": "bot", "text": line} for line in reply)
                self.store.save(session)
                return {"sid": session.sid, "reply": reply, "job_id": None, "messages": []}
            prefix: list[str] = []
            command = self._command(session, text)
            if command is not None:
                reply, job = command
                if job is not None:
                    session.pending_job = job.job_id
                    session.last_text = ""
                session.messages.append({"role": "user", "text": text})
                session.messages.extend({"role": "bot", "text": line} for line in reply)
                self.store.save(session)
                return {
                    "sid": session.sid,
                    "reply": reply,
                    "job_id": job.job_id if job else None,
                    "job_kind": job.kind if job else None,
                }
            if looks_like_cookies(text):
                path = save_cookies(self.settings, text)
                session.tool_calls = 0
                session.ingest_tried = False
                session.notes = []
                session.last_text = ""
                session.messages.append({"role": "user", "text": "(cookies youtube ditempel)"})
                prefix = [f"cookies masuk, disimpan di {path.name}. gue coba ambil transkrip lagi."]
            else:
                incoming = understand(text, None)
                session.slots.update(incoming)
                session.tool_calls = 0
                session.notes = []
                session.last_text = text
                if incoming.get("channel_url") or "coba lagi" in text.lower():
                    # An explicit link or an explicit retry is permission to hit YouTube again.
                    session.attempted_url = ""
                    session.last_channel_error = ""
                if "coba lagi" in text.lower():
                    session.ingest_tried = False
                session.messages.append({"role": "user", "text": text})
            session.ran = False
            reply, job = self._turn(session)
            reply = prefix + reply
            if job is not None:
                session.pending_job = job.job_id
            session.messages.extend({"role": "bot", "text": line} for line in reply)
            self.store.save(session)
            return {
                "sid": session.sid,
                "reply": reply,
                "job_id": job.job_id if job else None,
                "job_kind": job.kind if job else None,
            }
        elif advance and session.pending_job:
            session.last_text = ""
            observation = self._observe(session)
            session.pending_job = None
            session.notes.append(observation)

        reply, job = self._turn(session)
        if job is not None:
            session.pending_job = job.job_id
        session.messages.extend({"role": "bot", "text": line} for line in reply)
        self.store.save(session)
        return {
            "sid": session.sid,
            "reply": reply,
            "job_id": job.job_id if job else None,
            "job_kind": job.kind if job else None,
        }

    # -- the agent ------------------------------------------------------ #

    def _turn(self, session: Session) -> tuple[list[str], Job | None]:
        """Answer from the rules when the message is unambiguous, ask the model otherwise."""
        if not session.last_text.strip():
            return self._resume(session)
        cheap = self._cheap(session)
        if cheap is not None:
            return cheap
        llm = self.model()
        if llm is not None:
            plan = self._think(session, llm)
            if plan is not None:
                return self._execute(session, plan)
        return self._next(session)

    def _cheap(self, session: Session) -> tuple[list[str], Job | None] | None:
        """The fast path: a URL, an acknowledgement, a greeting, or a brief already spelled out.

        The provider takes two to four seconds for a one-word answer, so anything the rules
        can settle must never wait for it.
        """
        text = session.last_text.strip()
        if not text:
            return None
        lowered = text.lower()
        words = re.findall(r"[a-z]+", lowered)
        if lowered in GREETINGS:
            return ([self._status_line(session)], None)
        canned = self._canned(session, lowered)
        if canned is not None:
            return ([canned], None)
        pick = PICK_RE.match(lowered)
        if pick is not None and session.research:
            return self._pick_research(session, int(pick.group(1)))
        query = self._search_query(text)
        if query:
            return (self._search_lines(session, query), None)
        rules = extract_rules(text)
        if rules.get("channel_url"):
            return self._next(session)
        if words and set(words) <= ACKS:
            return self._next(session)
        brief_ready = rules.get("topic") and any(
            rules.get(key) for key in ("count", "tone", "audience")
        )
        if brief_ready and set(words[:4]) & ACTION_VERBS:
            return self._next(session)
        return None

    def _search_query(self, text: str) -> str | None:
        """Read 'cari X' as a search, and leave everything else alone.

        A link, a channel, or a script request is not a search even when the verb is
        there: the console has other tools for those, and sending them to the web
        would answer the wrong question quickly.
        """
        stripped = text.strip()
        if URL_RE.search(stripped) or HANDLE_RE.search(stripped):
            return None
        if re.search(r"\b(?:youtube|channel|transkrip|naskah|script)\b", stripped, re.I):
            return None
        match = SEARCH_RE.match(stripped)
        if match is None:
            return None
        query = match.group(1).strip(" .,-")
        query = re.sub(
            r"\s+(?:dong|ya|deh|sih|di internet|di google|di web)$", "", query, flags=re.I
        )
        return query or None

    def _search_lines(self, session: Session, query: str) -> list[str]:
        """Search the web and print what came back, with a door back to the brief."""
        from search.web import search

        rows, problems = search(query, limit=SEARCH_LIMIT)
        session.research = [row.as_dict() for row in rows]
        if not rows:
            reason = problems[-1] if problems else "nggak ada yang balas"
            session.notes.append(f"web_search '{query}': nol hasil ({reason})")
            return [
                f'gue cari "{query}" tapi hasilnya nol.',
                "coba kata kunci yang lebih spesifik, atau pakai bahasa inggris.",
            ]
        session.notes.append(f"web_search '{query}': {len(rows)} hasil, sumber {rows[0].source}")
        lines = [f'hasil "{query}":']
        for index, row in enumerate(rows, 1):
            lines.append(f"{index}. {row.title[:95]}")
            detail = f"   {row.domain}"
            if row.snippet:
                detail += f" · {row.snippet[:110]}"
            lines.append(detail)
        lines.append('mau topiknya dari salah satu ini? bilang "pakai 2".')
        return lines

    def _pick_research(self, session: Session, number: int) -> tuple[list[str], None]:
        """Turn one search hit into the topic, so research reaches the brief."""
        if number < 1 or number > len(session.research):
            return ([f"nomornya cuma sampai {len(session.research)}."], None)
        row = session.research[number - 1]
        title = str(row.get("title") or "").strip()
        if not title:
            return (["baris itu kosong, coba nomor lain."], None)
        session.slots["topic"] = title
        session.ran = False
        return (
            [
                f"topik: {title}",
                'audiensnya siapa? atau bilang "gas" kalau gue yang pilih.',
            ],
            None,
        )

    def _status_line(self, session: Session) -> str:
        """A greeting answered from this conversation's own library, no model call."""
        channel, videos, transcripts = self._counts(session)
        if channel is None:
            return "gue siap. mulai dari channel youtube kamu: tempel link atau @handle-nya."
        if transcripts:
            return (
                f"{videos} video di pustaka, {transcripts} transkrip siap. "
                "mau bikin naskah soal apa?"
            )
        return (
            f"{videos} video di pustaka, transkripnya belum ada. "
            "kasih topik, nanti gue ambil transkripnya dulu."
        )

    def _canned(self, session: Session, lowered: str) -> str | None:
        """Questions about the product itself, answered without waiting for a model."""
        for needles, answer in CANNED_ANSWERS:
            if any(needle in lowered for needle in needles):
                return answer
        if any(
            needle in lowered for needle in ("status", "udah ada apa", "progres", "gimana kabar")
        ):
            return self._status_line(session)
        return None

    def _think(self, session: Session, llm: Callable[[str], str]) -> dict[str, Any] | None:
        """One model call, one plan. A dead model is a missing plan, not a crash."""
        channel, videos, transcripts = self._counts(session)
        state = {
            "channel": channel.name if channel is not None else None,
            "videos": videos,
            "transcripts": transcripts,
        }
        prompt = agent_prompt(session, state)
        for attempt in range(2):
            try:
                raw = llm(prompt)
            except Exception as exc:
                if os.environ.get("NARATHOR_CHAT_DEBUG"):
                    print(f"[chat] router failed: {type(exc).__name__}: {exc}", flush=True)
                return None
            if os.environ.get("NARATHOR_CHAT_DEBUG"):
                print(f"[chat] router raw ({attempt}): {raw[:160]!r}", flush=True)
            plan = parse_plan(raw)
            if plan is not None:
                return plan
        return None

    def _execute(self, session: Session, plan: dict[str, Any]) -> tuple[list[str], Job | None]:
        """Carry out the plan: say the line, and start the tool it asked for."""
        say = str(plan.get("say") or "").strip()
        tool = plan.get("tool")
        args = plan.get("args") or {}
        if not tool:
            if say:
                return ([say], None)
            return self._next(session)

        if session.tool_calls >= 3:
            return ([say or "gue berhenti dulu, takutnya muter. lanjut?"], None)

        if tool == "assemble" and session.ran:
            return ([say or "yang tadi udah kelar, hasilnya di atas."], None)

        if tool == "web_search":
            query = str(args.get("query") or session.last_text or "").strip()
            if not query:
                return ([say or "cari apa? satu kata kunci aja."], None)
            session.tool_calls += 1
            lines = self._search_lines(session, query)
            return ([say, *lines] if say else lines, None)

        job, problem = self._start_tool(session, tool, args)
        if problem:
            return ([say, problem] if say else [problem], None)

        session.tool_calls += 1
        assert job is not None
        session.pending_job = job.job_id
        fallback = {
            "fetch_channel": "gue baca dulu daftar video di channel itu.",
            "ingest": "transkripnya gue ambil dulu, bentar.",
            "assemble": "gue rangkai sekarang.",
        }[tool]
        return ([say or fallback], job)

    def _start_tool(
        self, session: Session, tool: str, args: dict[str, Any]
    ) -> tuple[Job | None, str | None]:
        """Start one job. Returns (job, problem)."""
        if tool == "fetch_channel":
            url = str(args.get("url") or session.slots.get("channel_url") or "").strip()
            if not url:
                return None, "link channel-nya belum ada, tempel dulu."
            session.slots["channel_url"] = url
            session.attempted_url = url
            session.last_channel_error = ""
            return self._channel_job(session, url), None

        if tool == "ingest":
            session.ingest_tried = True
            limit = int(args.get("limit") or 25)
            return self._ingest_job(session, limit), None

        if tool == "assemble":
            session.slots.update(
                {
                    k: v
                    for k, v in args.items()
                    if v not in (None, "", [])
                    and k
                    in {
                        "topic",
                        "audience",
                        "tone",
                        "count",
                        "duration",
                        "message",
                    }
                }
            )
            if not session.slots.get("channel_url"):
                channel, _videos, _transcripts = self._counts(session)
                if channel is not None:
                    session.slots["channel_url"] = channel.url
                    session.slots["channel_id"] = channel.channel_id
            if not session.slots.get("topic"):
                return None, "topiknya belum jelas, mau bikin naskah soal apa?"
            return self._start_run(session)

        return None, f"alat {tool} nggak ada di daftar."

    def _observe(self, session: Session) -> str:
        """What a finished job tells the agent, in plain words."""
        job = self.jobs.get(str(session.pending_job))
        if job is None:
            return "hasil alat tidak ketemu, session ini kehilangan job-nya."
        result = job.result or {}
        if job.status == "failed":
            reason = job.error or "tanpa pesan"
            if job.kind == "channel":
                session.last_channel_error = _short_reason(reason)
            return f"{job.kind} gagal: {reason}"
        if job.kind == "channel":
            channel_id = str(result.get("channel_id") or "")
            if channel_id:
                session.slots["channel_id"] = channel_id
            return f"fetch_channel selesai: {result.get('videos', 0)} video masuk pustaka."
        if job.kind == "ingest":
            return (
                "ingest selesai: "
                f"masuk {len(result.get('ingested') or [])}, "
                f"cache {len(result.get('cached') or [])}, "
                f"gagal {len(result.get('skipped') or [])}, "
                f"diblokir youtube {result.get('blocked', 0)}."
            )
        block = str(result.get("block") or "")
        return f"assemble selesai: {result.get('scripts', 0)} naskah.\n{block[:900]}"

    # -- commands ------------------------------------------------------- #

    def _command(self, session: Session, text: str) -> tuple[list[str], Job | None] | None:
        """A slash command. Known ones run here, unknown ones say so.

        A command is a decision the user already made, so it never waits for a model.
        """
        if not text.startswith("/"):
            return None
        stripped = text[1:].strip()
        if not stripped:
            return (skills.help_lines(), None)
        name, _, rest = stripped.partition(" ")
        skill = skills.find(name)
        if skill is None:
            return (
                [f"/{name} nggak ada di daftar. yang ada:", *skills.help_lines()],
                None,
            )
        handler = getattr(self, f"_cmd_{skill.name}", None)
        if handler is None:
            return ([f"/{skill.name} belum nyambung ke mesin. laporin ya."], None)
        return handler(session, rest.strip())

    def _cmd_help(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Every command, one line each."""
        return (skills.help_lines(), None)

    def _cmd_cari(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Search the web from the console, without waiting for a model."""
        if not arg:
            return (["pakai: /cari inflasi indonesia terbaru"], None)
        return (self._search_lines(session, arg), None)

    def _cmd_status(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """What this conversation has read so far."""
        channel, videos, transcripts = self._counts(session)
        if channel is None:
            return (["belum ada channel di percakapan ini. ketik /channel <link>."], None)
        return ([f"{channel.name}: {videos} video, {transcripts} transkrip."], None)

    def _cmd_channel(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Read a channel's video tab."""
        if not arg:
            return (["pakai: /channel https://youtube.com/@handle"], None)
        url = _url_from(arg) or arg.strip()
        problem = _link_problem(url)
        if problem:
            return ([problem], None)
        session.slots["channel_url"] = url
        session.slots.pop("channel_id", None)
        session.attempted_url = url
        session.last_channel_error = ""
        session.ingest_tried = False
        session.ran = False
        return (["gue baca dulu daftar video channel itu."], self._channel_job(session, url))

    def _cmd_ingest(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Fetch transcripts for the videos already in the library."""
        channel, videos, _transcripts = self._counts(session)
        if channel is None:
            return (["channel-nya belum ada. /channel <link> dulu."], None)
        if videos == 0:
            return (["pustaka channel ini kosong, belum ada yang bisa diambil."], None)
        session.ingest_tried = True
        return (
            [f"transkrip buat {videos} video gue ambil dulu."],
            self._ingest_job(session, videos),
        )

    def _cmd_naskah(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Run the pipeline on the brief built so far."""
        _channel, _videos, transcripts = self._counts(session)
        if session.slots.get("channel_url") is None:
            return (["channel-nya belum ada. /channel <link> dulu."], None)
        if transcripts == 0:
            return (
                ["transkripnya belum ada. /ingest dulu, atau tempel cookies kalau diblokir."],
                None,
            )
        if arg.isdigit():
            session.slots["count"] = max(1, min(20, int(arg)))
        if not session.slots.get("topic"):
            return (["topiknya mana? /topik uang masuk dan pergi"], None)
        job, problem = self._start_run(session)
        if problem:
            return ([problem], None)
        count = int(session.slots.get("count") or DEFAULT_COUNT)
        return ([f"gue rangkai {count} naskah sekarang."], job)

    def _cmd_topik(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Set the topic in one line."""
        if not arg:
            return ([f"topik sekarang: {session.slots.get('topic') or 'belum ada'}"], None)
        session.slots["topic"] = arg
        session.ran = False
        return ([f"topik: {arg}"], None)

    def _cmd_audiens(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Set who the scripts are for."""
        if not arg:
            return ([f"audiens sekarang: {session.slots.get('audience') or 'belum ada'}"], None)
        session.slots["audience"] = arg
        session.ran = False
        return ([f"audiens: {arg}"], None)

    def _cmd_brief(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Show the brief that would run right now."""
        slots = session.slots
        return (
            [
                f"topik: {slots.get('topic') or 'belum ada'}",
                f"audiens: {slots.get('audience') or 'belum ada'}",
                f"tone: {slots.get('tone') or DEFAULT_TONE}",
                f"naskah: {slots.get('count') or DEFAULT_COUNT} x "
                f"{slots.get('duration') or DEFAULT_DURATION} detik",
            ],
            None,
        )

    def _cmd_blocked(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """The segments the critic refused on the last run."""
        runs = sorted(
            (p for p in self.settings.output_dir.glob("*/blocked.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not runs:
            return (["belum ada run, jadi belum ada yang diblokir."], None)
        try:
            body = runs[0].read_text(encoding="utf-8").strip()
        except OSError:
            return (["file blocked.md nggak kebaca."], None)
        if not body:
            return (["blocked.md kosong, semua segmen lolos gate."], None)
        return (body.splitlines()[:24], None)

    def _cmd_doctor(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """The five checks, in chat."""
        from backend import soul as soul_mod

        channel, videos, transcripts = self._counts(session)
        checks = [
            (
                "api key",
                bool(self.settings.api_key),
                "terisi" if self.settings.api_key else "kosong",
            ),
            (
                "database",
                True,
                "sqlite" if self.settings.is_sqlite else "postgres",
            ),
            (
                "soul",
                soul_mod.verify(self.settings.soul_path, self.settings.soul_lock_path).ok,
                "hash cocok",
            ),
            (
                "pustaka",
                channel is not None,
                f"{videos} video, {transcripts} transkrip" if channel else "belum ada channel",
            ),
        ]
        try:
            from ingest import ytdlp

            checks.append(
                (
                    "cookies",
                    ytdlp.cookies_present(),
                    "ada" if ytdlp.cookies_present() else "belum ada",
                )
            )
        except Exception:
            checks.append(("cookies", False, "modul nggak kebaca"))
        return ([f"[{'ok' if ok else 'gagal'}] {name}: {note}" for name, ok, note in checks], None)

    def _cmd_cookies(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """How to hand the console a browser session."""
        return (
            [
                "pasang extension 'get cookies.txt' di chrome, buka youtube dalam keadaan login,",
                "export, lalu tempel seluruh isi file ke kolom ini. gue simpan sendiri, nggak masuk git.",
            ],
            None,
        )

    def _cmd_reset(self, session: Session, arg: str) -> tuple[list[str], Job | None]:
        """Reset is handled before dispatch; this keeps the registry honest."""
        return (["ketik /reset lagi."], None)

    def _resume(self, session: Session) -> tuple[list[str], Job | None]:
        """What to say after a job, decided from the job itself, not the model."""
        note = session.notes[-1] if session.notes else ""
        _channel, videos, transcripts = self._counts(session)
        if " gagal: " in note:
            kind = note.split(" gagal: ", 1)[0].strip()
            if kind == "channel" and session.last_channel_error:
                return (
                    [
                        "channel-nya gagal gue baca.",
                        f"alasannya: {session.last_channel_error}",
                        "coba link lain, atau ketik /doctor buat cek koneksi youtube.",
                    ],
                    None,
                )
            return ([note], None)
        if note.startswith("fetch_channel selesai"):
            if videos == 0:
                return (["channel-nya kebaca, tapi videonya nol. coba link lain."], None)
            if transcripts == 0 and session.tool_calls < 3:
                session.tool_calls += 1
                return (
                    [f"{videos} video masuk. transkripnya gue ambil dulu."],
                    self._ingest_job(session, videos),
                )
            return ([f"{videos} video masuk, {transcripts} transkrip siap. topiknya apa?"], None)
        if note.startswith("ingest selesai"):
            if transcripts == 0:
                return (
                    [
                        "youtube tetap nolak transkrip dari server ini.",
                        "tempel cookies.txt di kolom ini, atau bilang 'coba lagi' setelah cookies masuk.",
                    ],
                    None,
                )
            return (
                [
                    f"{transcripts} transkrip siap dari {videos} video. sekarang topiknya, satu kalimat."
                ],
                None,
            )
        if note.startswith("assemble selesai"):
            return ([], None)
        return ([], None)

    # -- decisions ------------------------------------------------------ #

    def _counts(self, session: Session) -> tuple[Any, int, int]:
        """Channel, videos, transcripts for this conversation only.

        The library on disk is shared, so counting all of it would let a fresh chat
        announce work it never did. A conversation counts what it actually read.
        """
        channel = self._channel(session)
        if channel is None:
            return None, 0, 0
        videos = db.fetch_videos_for_channel(self.engine, channel.channel_id)
        transcripts = sum(
            1 for video in videos if db.fetch_transcript(self.engine, video.video_id) is not None
        )
        return channel, len(videos), transcripts

    def _channel(self, session: Session) -> Any:
        """The channel this conversation opened, None before the first link.

        The URL wins over the stored id. Pasting a second channel used to keep
        answering with the first one, because a channel_id from an earlier turn
        was trusted over the link the user just sent.
        """
        url = str(session.slots.get("channel_url") or "").strip()
        if url:
            found = db.fetch_channel_by_url(self.engine, url)
            if found is not None:
                session.slots["channel_id"] = found.channel_id
                return found
            session.slots.pop("channel_id", None)
            return None
        channel_id = str(session.slots.get("channel_id") or "").strip()
        if channel_id:
            return db.fetch_channel_by_id(self.engine, channel_id)
        return None

    def _next(self, session: Session) -> tuple[list[str], Job | None]:
        """What to say next, and the job to start if the next step is work."""
        slots = session.slots
        channel, videos, transcripts = self._counts(session)

        url = str(slots.get("channel_url") or "").strip()
        if not url and channel is not None:
            slots["channel_url"] = channel.url
            url = channel.url

        if not url:
            return (
                ["gas. channel youtube-nya mana? tempel link atau @handle-nya."],
                None,
            )

        problem = _link_problem(url)
        if problem:
            return ([problem], None)

        from ingest.channel import ChannelError, normalize

        try:
            target = normalize(url)
        except ChannelError:
            return (
                [
                    "link itu nggak kebaca sebagai channel youtube.",
                    "format yang bisa gue pakai: youtube.com/@nama-channel",
                ],
                None,
            )
        session.slots["channel_url"] = target

        channel = self._channel(session)
        if channel is not None and not _same_channel(channel.url, target):
            # The user moved to another channel: the old one must stop answering.
            session.slots.pop("channel_id", None)
            channel = None

        if channel is None:
            if session.attempted_url != target:
                session.attempted_url = target
                session.last_channel_error = ""
                return (
                    ["siap, gue baca dulu daftar video di channel itu."],
                    self._channel_job(session, target),
                )
            lines = ["channel itu udah gue coba, hasilnya kosong."]
            if session.last_channel_error:
                lines.append(f"alasannya: {session.last_channel_error}")
            lines.extend(
                [
                    "tempel link channel lain, atau ketik /doctor buat cek koneksi youtube.",
                    "kalau mau gue ulang link yang sama, bilang 'coba lagi'.",
                ]
            )
            return (lines, None)

        if videos == 0:
            return (
                [
                    "channel-nya kebaca, tapi daftar videonya kosong.",
                    "coba channel lain, atau tab /videos yang publik.",
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
        job, problem = self._start_run(session)
        if problem:
            return [problem], None
        count = int(session.slots.get("count") or DEFAULT_COUNT)
        duration = int(session.slots.get("duration") or DEFAULT_DURATION)
        opening = [
            f"{transcripts} transkrip siap, {videos} video di pustaka.",
            f"gue rangkai {count} naskah {duration} detik. jalan.",
        ]
        return (opening, job)

    def _start_run(self, session: Session) -> tuple[Job | None, str | None]:
        """Validate the brief, write it, and start the run job. Returns (job, problem)."""
        brief_id, payload = compose_brief(session.slots)
        report = briefs_load.validate(brief_id, payload)
        if not report.ok:
            reasons = "; ".join(f"{r.code} {r.message}" for r in report.rejections)
            return None, f"brief-nya ditolak mesin: {reasons}. ubah arahan dikit, lalu kirim lagi."

        path = briefs_load.brief_path(self.settings.briefs_dir, brief_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        session.brief_id = brief_id
        session.ran = True
        session.slots["count"] = int(payload["output"]["scripts"])
        session.slots["duration"] = int(payload["output"]["target_duration_s"])
        return self._run_job(brief_id), None

    # -- jobs ----------------------------------------------------------- #

    def _channel_job(self, session: Session, url: str) -> Job:
        """Read the channel's video tab into the library."""
        from ingest.channel import discover

        limit = 25
        engine = self.engine

        def work(log: Callable[[str], None]) -> dict[str, Any]:
            channel, found = discover(url, limit=limit, log=log)
            log(f"ketemu {len(found)} video di {channel.name}")
            db.save_library(engine, channel, found)
            mine = db.fetch_videos_for_channel(engine, channel.channel_id)
            log(f"pustaka channel ini {len(mine)} video")
            return {
                "channel": channel.name,
                "channel_id": channel.channel_id,
                "videos": len(mine),
            }

        return self.jobs.start("channel", f"channel {url}", work)

    def _ingest_job(self, session: Session, videos: int) -> Job:
        """Fetch transcripts: captions first, Whisper second."""
        from ingest.pipeline import DbStore, default_fetchers
        from ingest.pipeline import run as run_ingest

        engine = self.engine
        brief_id = session.brief_id
        channel_id = str(session.slots.get("channel_id") or "")
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

            pool = (
                db.fetch_videos_for_channel(engine, channel_id)
                if channel_id
                else db.fetch_videos(engine)
            )
            rows = [v for v in pool if v.duration_s >= min_duration]
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
