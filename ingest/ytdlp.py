"""yt-dlp plumbing shared by channel discovery and subtitle fetch.

Two environment knobs matter in practice. A datacenter IP gets a bot check from
YouTube, so a cookies file exported from a logged in browser is usually the
difference between working and not:

    YT_COOKIES_FILE=/opt/data/narathor/cookies.txt
    YT_PROXY=http://user:pass@host:port
"""

from __future__ import annotations

import os
from typing import Any


def base_options() -> dict[str, Any]:
    """Options every yt-dlp call in this repo shares."""
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignoreerrors": False,
    }
    cookies = os.environ.get("YT_COOKIES_FILE", "").strip()
    if cookies and os.path.exists(cookies):
        options["cookiefile"] = cookies
    proxy = os.environ.get("YT_PROXY", "").strip()
    if proxy:
        options["proxy"] = proxy
    return options


def cookies_present() -> bool:
    """True when a cookies file is configured and readable."""
    cookies = os.environ.get("YT_COOKIES_FILE", "").strip()
    return bool(cookies and os.path.exists(cookies))
