"""ASGI entry point. `uvicorn backend.server:app` starts the console.

Kept out of backend.main so importing the module inside tests never opens the
real database or reads the real .env.
"""

from __future__ import annotations

from backend.main import create_app

app = create_app()
