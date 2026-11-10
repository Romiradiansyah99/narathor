"""Konfigurasi runtime Narathor. Semua jalur lewat pathlib."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MODELS: dict[str, str] = {
    # The router reads one message and picks a move. It runs on the fastest model the
    # provider offers, because this is the only call standing between a keystroke and
    # an answer. The writer keeps the slower, better model.
    "router": "deepseek/deepseek-v4.1-flash-ultrafast",
    "curator": "deepseek/deepseek-v4.1-flash",
    "matcher": "deepseek/deepseek-v4.1-flash",
    "writer": "deepseek/deepseek-v4.1-flash",
    # The profile reads a whole channel at once. It needs room to think before it
    # writes: the same model that answers in one sentence will spend its entire
    # budget on reasoning and return nothing if the budget is small.
    "profile": "deepseek/deepseek-v4.1-flash",
    "critic": "claude-haiku-5-5",
    "eval": "stealth/crouton-alpha",
}

PROMPT_VERSION = "v1"
CRAFT_VERSION = "v1"


def _read_dotenv(path: Path) -> None:
    """Muat .env tanpa dependensi tambahan; nilai yang sudah ada tidak ditimpa."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    """Pengaturan yang dibaca sekali per proses."""

    root: Path
    data_dir: Path
    output_dir: Path
    briefs_dir: Path
    prompts_dir: Path
    soul_path: Path
    soul_lock_path: Path
    database_url: str
    api_key: str
    max_concurrency: int
    models: dict[str, str]

    @property
    def is_sqlite(self) -> bool:
        """True bila database yang dipakai SQLite."""
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Baca konfigurasi dari environment sekali, lalu cache."""
    _read_dotenv(ROOT / ".env")
    api_key = os.environ.get("COMMAND_CODE_API_KEY", "").strip()
    database_url = (
        os.environ.get("DATABASE_URL", "").strip()
        or f"sqlite+pysqlite:///{ROOT / 'narathor.sqlite3'}"
    )
    models = dict(DEFAULT_MODELS)
    model_name = os.environ.get("MODEL_NAME", "").strip()
    if model_name:
        models = dict.fromkeys(models, model_name)
    for role in DEFAULT_MODELS:
        override = os.environ.get(f"MODEL_{role.upper()}", "").strip()
        if override:
            models[role] = override
    concurrency = int(os.environ.get("MAX_CONCURRENCY", "5"))
    if concurrency < 1:
        raise ValueError("MAX_CONCURRENCY minimal 1")
    return Settings(
        root=ROOT,
        data_dir=Path(os.environ.get("NARATHOR_DATA", ROOT / "data")),
        output_dir=Path(os.environ.get("NARATHOR_OUTPUT", ROOT / "output")),
        briefs_dir=ROOT / "briefs",
        prompts_dir=ROOT / "prompts",
        soul_path=ROOT / "SOUL.md",
        soul_lock_path=ROOT / "soul.lock",
        database_url=database_url,
        api_key=api_key,
        max_concurrency=concurrency,
        models=models,
    )


def reset_settings_cache() -> None:
    """Kosongkan cache settings, dipakai test yang mengganti environment."""
    get_settings.cache_clear()
