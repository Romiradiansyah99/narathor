"""Start the Narathor console.

The token is read from .ui_token and injected into the environment here, so it
never appears on a command line, in shell history, or in a process list.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    """exec uvicorn with the token in the environment."""
    token_file = ROOT / ".ui_token"
    token = token_file.read_text(encoding="utf-8").strip() if token_file.exists() else ""
    env = dict(os.environ)
    if token:
        env["NARATHOR_UI_TOKEN"] = token
    os.chdir(ROOT)
    os.execvpe(
        "uv",
        [
            "uv",
            "run",
            "uvicorn",
            "backend.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8811",
            "--log-level",
            "warning",
        ],
        env,
    )


if __name__ == "__main__":
    main()
