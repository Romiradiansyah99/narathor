"""Penegakan konstitusi. Hash byte-per-byte, tanpa normalisasi."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from contracts import SoulCheck


class SoulLockError(RuntimeError):
    """soul.lock tidak ada atau tidak dapat dibaca."""


def file_sha256(path: Path) -> str:
    """SHA-256 atas isi file apa adanya."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lock(path: Path) -> dict:
    """Baca soul.lock sebagai dict."""
    if not path.exists():
        raise SoulLockError(
            f"soul.lock tidak ada di {path}; jalankan `narathor soul bump --reason`"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SoulLockError(f"soul.lock tidak valid JSON: {exc}") from exc
    if "sha256" not in data:
        raise SoulLockError("soul.lock tidak memuat sha256")
    return data


def verify(soul_path: Path, lock_path: Path) -> SoulCheck:
    """Periksa SOUL.md terhadap soul.lock. Tidak pernah menulis apa pun."""
    now = datetime.now(UTC)
    if not soul_path.exists():
        return SoulCheck(
            ok=False,
            version=None,
            expected_hash=None,
            actual_hash=None,
            checked_at=now,
            reason=f"SOUL.md tidak ada di {soul_path}; sistem tidak dapat dijalankan",
        )
    actual = file_sha256(soul_path)
    try:
        lock = load_lock(lock_path)
    except SoulLockError as exc:
        return SoulCheck(
            ok=False,
            version=None,
            expected_hash=None,
            actual_hash=actual,
            checked_at=now,
            reason=str(exc),
        )
    expected = str(lock["sha256"])
    version = int(lock.get("version", 0))
    if actual != expected:
        return SoulCheck(
            ok=False,
            version=version,
            expected_hash=expected,
            actual_hash=actual,
            checked_at=now,
            reason=(
                "SOUL.md berubah. Ini alarm, bukan gangguan: periksa `git diff SOUL.md`. "
                "Kalau perubahan disengaja, jalankan `narathor soul bump`."
            ),
        )
    return SoulCheck(
        ok=True,
        version=version,
        expected_hash=expected,
        actual_hash=actual,
        checked_at=now,
        reason="",
    )


def bump(soul_path: Path, lock_path: Path, reason: str) -> dict:
    """Naikkan versi soul dan simpan hash lama ke previous_versions."""
    if not reason.strip():
        raise SoulLockError("soul bump menuntut --reason yang tidak kosong")
    if not soul_path.exists():
        raise SoulLockError("SOUL.md tidak ada; tidak ada yang bisa dikunci")
    lock = load_lock(lock_path)
    new_hash = file_sha256(soul_path)
    previous = list(lock.get("previous_versions", []))
    if new_hash != lock["sha256"]:
        previous.append(
            {
                "version": int(lock.get("version", 0)),
                "sha256": lock["sha256"],
                "replaced_at": datetime.now(UTC).date().isoformat(),
                "reason": reason.strip(),
            }
        )
        new_version = int(lock.get("version", 0)) + 1
    else:
        new_version = int(lock.get("version", 0))
    updated = {
        "version": new_version,
        "sha256": new_hash,
        "locked_at": datetime.now(UTC).date().isoformat(),
        "locked_by": lock.get("locked_by", "boss"),
        "algorithm": "sha256",
        "file": lock.get("file", "SOUL.md"),
        "previous_versions": previous,
    }
    lock_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    return updated
