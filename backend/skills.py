"""The slash menu. One list, shared by the page and the answer.

Typing `/` opens this. Every entry answers without a model, because a command is a
decision the user already made: the only work left is running it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Skill:
    """One command: how to type it, and what it does."""

    name: str
    args: str
    about: str

    @property
    def usage(self) -> str:
        """What the menu shows in the left column."""
        return f"/{self.name} {self.args}".strip()

    def as_dict(self) -> dict[str, Any]:
        """Shape sent to the page."""
        return {
            "name": f"/{self.name}",
            "usage": self.usage,
            "about": self.about,
            "takes_args": bool(self.args),
        }


SKILLS: tuple[Skill, ...] = (
    Skill("channel", "<link|@handle>", "baca daftar video channel ke pustaka"),
    Skill("ingest", "[jumlah]", "tarik transkrip video yang belum ada"),
    Skill("naskah", "[jumlah]", "rakit naskah dari topik yang sudah disebut"),
    Skill("topik", "<satu kalimat>", "tentukan topik naskah"),
    Skill("audiens", "<siapa penontonnya>", "tentukan audiens"),
    Skill("brief", "", "lihat arahan yang sedang dipakai"),
    Skill("status", "", "isi pustaka percakapan ini"),
    Skill("blocked", "", "segmen yang ditolak critic terakhir"),
    Skill("doctor", "", "cek api key, database, soul, cookies"),
    Skill("cookies", "", "cara memasang cookies youtube"),
    Skill("reset", "", "lupakan percakapan, mulai dari nol"),
)

BY_NAME: dict[str, Skill] = {skill.name: skill for skill in SKILLS}


def catalogue() -> list[dict[str, str]]:
    """Everything the menu needs, in order."""
    return [skill.as_dict() for skill in SKILLS]


def help_lines() -> list[str]:
    """The same list as plain text, for the chat itself."""
    width = max(len(skill.usage) for skill in SKILLS)
    return [f"{skill.usage.ljust(width)}  {skill.about}" for skill in SKILLS]


def find(name: str) -> Skill | None:
    """Look one up, ignoring the leading slash."""
    return BY_NAME.get(name.lstrip("/").strip().lower())


def as_json() -> list[dict[str, str]]:
    """Debug shape, same as catalogue."""
    return [asdict(skill) for skill in SKILLS]
