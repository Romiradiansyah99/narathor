"""Pemilihan model per peran. Satu baris untuk mengganti model Writer."""

from __future__ import annotations

import os
from typing import Protocol

from backend.config import get_settings

BASE_URL = os.environ.get("COMMAND_CODE_BASE_URL", "https://api.commandcode.ai/provider/v1")
USER_AGENT = "narathor/0.1"

# Peran yang menjawab langsung ke manusia dapat anggaran kecil: satu kalimat dan satu
# nama alat. Peran yang menulis naskah dapat anggaran penuh.
ROLE_LIMITS: dict[str, dict[str, float]] = {
    "router": {"max_completion_tokens": 200, "timeout": 8.0, "temperature": 0.2},
}


class LanguageModel(Protocol):
    """Antarmuka minimal yang dibutuhkan agent. Stub test memakai protokol ini."""

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Kembalikan teks jawaban model."""
        ...


class StubModel:
    """Model palsu untuk test. Tidak pernah memanggil jaringan."""

    def __init__(self, reply: str | dict) -> None:
        self.reply = reply
        self.calls: list[str] = []

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Catat prompt dan kembalikan jawaban tetap."""
        self.calls.append(prompt)
        if isinstance(self.reply, str):
            return self.reply
        import json

        return json.dumps(self.reply)


class ProviderModel:
    """Model lewat Command Code Provider API, dibungkus LangChain chat model."""

    def __init__(self, role: str) -> None:
        settings = get_settings()
        if not settings.api_key:
            raise RuntimeError("COMMAND_CODE_API_KEY kosong; isi .env sebelum memanggil model")
        self.role = role
        self.model_name = settings.models[role]
        self.limits = ROLE_LIMITS.get(
            role, {"max_completion_tokens": 500, "timeout": 10.0, "temperature": 0.3}
        )
        self._client = None

    def _build(self):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model_name,
            api_key=get_settings().api_key,  # pyright: ignore[reportArgumentType]
            base_url=BASE_URL,
            temperature=float(self.limits["temperature"]),
            max_retries=0,
            timeout=float(self.limits["timeout"]),
            max_completion_tokens=int(self.limits["max_completion_tokens"]),
            default_headers={"User-Agent": USER_AGENT, "X-Title": "Narathor"},
        )

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Kirim satu prompt, kembalikan teks."""
        if self._client is None:
            self._client = self._build()
        messages = []
        if system:
            messages.append(("system", system))
        messages.append(("human", prompt))
        response = self._client.invoke(messages)
        content = response.content
        if isinstance(content, list):
            return "".join(str(part) for part in content)
        return str(content)


def for_role(role: str) -> LanguageModel:
    """Model untuk satu peran."""
    return ProviderModel(role)


def model_name(role: str) -> str:
    """Id model yang dipakai peran ini, untuk run.json."""
    return get_settings().models[role]
