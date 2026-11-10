"""Web search for the console.

The console has to answer questions about the world, not only about the channel it
just read. This module is the one place that leaves the machine.

Providers are tried in order, and the first one that returns usable rows wins: a
keyed API when the deployment has a key, then DuckDuckGo lite, then Google News,
then Wikipedia. Everything is parsed from text, so when one of them changes shape
there is one regex to fix and no dependency to bump.

Every provider is allowed to fail. A search that returns nothing is an honest
answer, not an exception the console has to apologise for.
"""

from __future__ import annotations

import base64
import html
import os
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Words that carry no meaning on their own. A result sharing only these with the
# query is noise, and noise is what made the first working provider look broken.
STOPWORDS = {
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
    "the",
    "and",
    "for",
    "with",
    "how",
    "what",
    "why",
    "best",
    "2025",
    "2026",
}


@dataclass(frozen=True)
class Result:
    """One row a human can act on: a title, where it lives, one line of gist."""

    title: str
    url: str
    snippet: str = ""
    source: str = "web"
    site: str = ""

    @property
    def domain(self) -> str:
        """Just the host, for a line that stays short."""
        if self.site:
            return self.site
        host = urllib.parse.urlparse(self.url).netloc.lower()
        return host.removeprefix("www.")

    def as_dict(self) -> dict[str, str]:
        """Shape kept in the session and sent to the page."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "source": self.source,
            "site": self.site,
        }


def _tokens(text: str) -> set[str]:
    """Meaningful words, lowercased, stopwords removed."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def _score(query_tokens: set[str], result: Result) -> float:
    """How much of the question the result actually answers.

    Ratio, not a yes/no. A page about Asia shares one word with "asia tenggara
    startup gagal" and sounds authoritative, which is exactly how a bad answer gets
    picked. One third is not good enough when another engine offers two thirds.
    """
    if not query_tokens:
        return 1.0
    overlap = query_tokens & _tokens(f"{result.title} {result.snippet}")
    return len(overlap) / len(query_tokens)


def _relevant(query: str, result: Result) -> bool:
    """Does this row share a real word with the question?"""
    return _score(_tokens(query), result) > 0.0


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #


def _clean(text: str) -> str:
    """Strip tags, decode entities, collapse whitespace.

    Entities are decoded first, then tags are stripped again: feeds escape their
    HTML, so unescaping once reveals a second layer of markup that has to go.
    """
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.S)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    for _ in range(3):
        text = html.unescape(text)
        stripped = re.sub(r"<[^>]+>", " ", text)
        if stripped == text:
            break
        text = stripped
    return " ".join(text.split())


def _tag(block: str, name: str) -> str:
    """First value of a tag inside an RSS item."""
    match = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
    return _clean(match.group(1)) if match else ""


def _rss(xml: str, limit: int, source: str) -> list[Result]:
    """Every RSS feed in this file has the same shape, so one reader serves all."""
    rows: list[Result] = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S)[: limit * 2]:
        title = _tag(item, "title")
        link = _tag(item, "link")
        if not title or not link.startswith("http"):
            continue
        rows.append(Result(title=title, url=link, snippet=_tag(item, "description"), source=source))
        if len(rows) >= limit:
            break
    return rows


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


def _ddg(query: str, limit: int, timeout: float) -> list[Result]:
    """DuckDuckGo lite, posted as a form.

    The GET page serves a challenge from this network. The POST endpoint still
    answers with real results, and it is the only general engine that does.
    """
    response = httpx.post(
        "https://lite.duckduckgo.com/lite/",
        data={"q": query, "kl": "id-id"},
        headers=HEADERS,
        timeout=timeout,
        follow_redirects=True,
    )
    body = response.text
    if "anomaly" in body.lower():
        raise RuntimeError("duckduckgo served the bot challenge")
    links = re.findall(
        r"<a[^>]*class=['\"]result-link['\"][^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>"
        r"|<a[^>]*href=['\"]([^'\"]+)['\"][^>]*class=['\"]result-link['\"][^>]*>(.*?)</a>",
        body,
        re.S,
    )
    snippets = re.findall(r"<td[^>]*class=['\"]result-snippet['\"][^>]*>(.*?)</td>", body, re.S)
    rows: list[Result] = []
    for index, group in enumerate(links[: limit * 2]):
        url = group[0] or group[2]
        title = _clean(group[1] or group[3])
        if not url.startswith("http") or not title:
            continue
        snippet = _clean(snippets[index]) if index < len(snippets) else ""
        rows.append(Result(title=title, url=url, snippet=snippet, source="web"))
        if len(rows) >= limit:
            break
    return rows


def _bing_target(href: str) -> str:
    """Bing wraps every result in a click tracker whose payload is the real URL."""
    match = re.search(r"[?&]u=a1([A-Za-z0-9_\-]+)", href)
    if match is None:
        return href
    padded = match.group(1) + "=" * (-len(match.group(1)) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", "ignore")
    except Exception:
        return href


def _bing(query: str, limit: int, timeout: float) -> list[Result]:
    """Bing's result page, which still renders server side and does not block here.

    The RSS endpoint on the same domain answers with unrelated pages, so the HTML
    is read directly and the click trackers are unwrapped back into real URLs.
    """
    response = httpx.get(
        "https://www.bing.com/search",
        params={"q": query, "setlang": "id"},
        headers=HEADERS,
        timeout=timeout,
        follow_redirects=True,
    )
    blocks = re.findall(r'<li class="b_algo".*?</li>', response.text, re.S)
    rows: list[Result] = []
    for block in blocks:
        heading = re.search(r"<h2[^>]*>\s*<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", block, re.S)
        if heading is None:
            continue
        url = _bing_target(html.unescape(heading.group(1)))
        title = _clean(heading.group(2))
        if not title or not url.startswith("http"):
            continue
        paragraph = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        snippet = _clean(paragraph.group(1)) if paragraph else ""
        rows.append(Result(title=title, url=url, snippet=snippet, source="web"))
        if len(rows) >= limit:
            break
    return rows


def _gnews(query: str, limit: int, timeout: float) -> list[Result]:
    """Google News RSS: the best relevance for Indonesian topical questions."""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=id&gl=ID&ceid=ID:id"
    response = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    rows = _rss(response.text, limit, "berita")
    cleaned: list[Result] = []
    for row in rows:
        # "Judul - Kompas.id": the publisher is in the title, so it becomes the label
        # instead of news.google.com, which tells a reader nothing.
        title, _, publisher = row.title.rpartition(" - ")
        if not title:
            title, publisher = row.title, ""
        snippet = "" if row.title[:25].lower() in row.snippet.lower() else row.snippet
        cleaned.append(Result(title, row.url, snippet, "berita", publisher.strip()))
    return cleaned


def _wikipedia(query: str, limit: int, timeout: float) -> list[Result]:
    """Last resort: an encyclopedia, for facts rather than for angles."""
    response = httpx.get(
        "https://id.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": limit,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    payload: dict[str, Any] = response.json()
    hits = (payload.get("query") or {}).get("search") or []
    rows: list[Result] = []
    for hit in hits[:limit]:
        title = str(hit.get("title") or "")
        if not title:
            continue
        slug = urllib.parse.quote(title.replace(" ", "_"))
        rows.append(
            Result(
                title=title,
                url=f"https://id.wikipedia.org/wiki/{slug}",
                snippet=_clean(str(hit.get("snippet") or "")),
                source="wikipedia",
            )
        )
    return rows


def _brave(query: str, limit: int, timeout: float) -> list[Result]:
    """Only runs when the deployment has a key. No key, no call."""
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("no BRAVE_API_KEY")
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        timeout=timeout,
    )
    payload: dict[str, Any] = response.json()
    rows: list[Result] = []
    for item in (payload.get("web") or {}).get("results") or []:
        rows.append(
            Result(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                snippet=_clean(str(item.get("description") or "")),
                source="web",
            )
        )
    return rows[:limit]


PROVIDERS: tuple[tuple[str, Callable[[str, int, float], list[Result]]], ...] = (
    ("brave", _brave),
    ("bing", _bing),
    ("duckduckgo", _ddg),
    ("gnews", _gnews),
    ("wikipedia", _wikipedia),
)


# --------------------------------------------------------------------------- #
# Public
# --------------------------------------------------------------------------- #


def search(query: str, limit: int = 5, timeout: float = 8.0) -> tuple[list[Result], list[str]]:
    """Ask providers in turn until one answers the question well enough.

    A provider that returns something vaguely matching stops the search only when
    it clears half the query. Below that, the next provider gets a chance and the
    better answer wins. Returns the rows and the failures, so the console can say
    what actually happened instead of pretending a thin result is a full one.
    """
    cleaned = " ".join(query.split())
    if not cleaned:
        return [], ["kata kuncinya kosong"]
    wanted = _tokens(cleaned)
    problems: list[str] = []
    best: list[Result] = []
    best_score = 0.0
    for name, provider in PROVIDERS:
        try:
            rows = provider(cleaned, limit, timeout)
        except Exception as exc:  # a dead provider is a missing answer, not a crash
            problems.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        scored = [(score, row) for row in rows if (score := _score(wanted, row)) > 0]
        if not scored:
            problems.append(f"{name}: nol hasil yang nyambung")
            continue
        scored.sort(key=lambda pair: -pair[0])
        top = scored[0][0]
        if top > best_score:
            best = _dedupe([row for _score_value, row in scored])[:limit]
            best_score = top
        if best_score >= 0.5:
            break
    return best, problems


def _dedupe(rows: list[Result]) -> list[Result]:
    """One row per page, keeping the first mention in provider order."""
    seen: set[str] = set()
    kept: list[Result] = []
    for row in rows:
        key = row.url.split("?")[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def read(url: str, limit: int = 1400, timeout: float = 8.0) -> str:
    """Fetch one page as plain text, so the answer can quote it instead of guessing.

    Fails quietly: a page behind a paywall or a bot check returns nothing, and the
    caller decides what to say about that.
    """
    try:
        response = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    except Exception:
        return ""
    kind = response.headers.get("content-type", "")
    if "html" not in kind and "text" not in kind:
        return ""
    body = response.text
    paragraphs = [_clean(chunk) for chunk in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    prose = " ".join(chunk for chunk in paragraphs if len(chunk) > 60)
    text = prose if len(prose) >= 300 else _clean(body)
    if len(text) < 200:
        return ""
    return text[:limit]
