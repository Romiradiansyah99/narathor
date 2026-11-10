"""Phase 13: the console can leave the machine and search the web."""

from __future__ import annotations

from typing import Any

import pytest

from backend import chat
from search import web

# --------------------------------------------------------------------------- #
# Scoring: the difference between a result and a random page
# --------------------------------------------------------------------------- #


def _row(title: str, snippet: str = "", url: str = "https://example.com/a") -> web.Result:
    return web.Result(title=title, url=url, snippet=snippet)


def test_score_counts_how_much_of_the_question_is_answered() -> None:
    wanted = web._tokens("asia tenggara startup gagal")
    assert web._score(wanted, _row("Asia - Wikipedia")) < 0.5
    assert web._score(wanted, _row("Kegagalan startup Asia Tenggara berakar dari struktur")) >= 0.5


def test_a_generic_page_does_not_beat_a_specific_one() -> None:
    """One shared word sounds authoritative and answers nothing."""
    wanted = web._tokens("inflasi indonesia terbaru")
    generic = _row("Indonesia - Wikipedia")
    specific = _row("Inflasi Indonesia terbaru naik", "Badan Pusat Statistik mencatat inflasi")
    assert web._score(wanted, specific) > web._score(wanted, generic)


def test_stopwords_carry_no_weight() -> None:
    assert web._tokens("cara bikin yang untuk") == set()


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


def test_the_weak_provider_loses_to_the_strong_one(monkeypatch: pytest.MonkeyPatch) -> None:
    def weak(_q: str, _l: int, _t: float) -> list[web.Result]:
        return [_row("Asia - Wikipedia")]

    def strong(_q: str, _l: int, _t: float) -> list[web.Result]:
        return [_row("Kegagalan startup Asia Tenggara makin banyak")]

    monkeypatch.setattr(
        web,
        "PROVIDERS",
        (("weak", weak), ("strong", strong)),
    )
    rows, _problems = web.search("asia tenggara startup gagal")
    assert rows[0].title.startswith("Kegagalan startup")


def test_a_good_enough_provider_stops_the_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """No point calling the next engine when the first one already answered."""
    calls: list[str] = []

    def first(_q: str, _l: int, _t: float) -> list[web.Result]:
        calls.append("first")
        return [_row("Inflasi Indonesia terbaru", "inflasi naik")]

    def second(_q: str, _l: int, _t: float) -> list[web.Result]:
        calls.append("second")
        return []

    monkeypatch.setattr(web, "PROVIDERS", (("first", first), ("second", second)))
    rows, _problems = web.search("inflasi indonesia")
    assert len(rows) == 1
    assert calls == ["first"]


def test_a_dead_provider_is_a_missing_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_q: str, _l: int, _t: float) -> list[web.Result]:
        raise RuntimeError("network down")

    monkeypatch.setattr(web, "PROVIDERS", (("broken", broken),))
    rows, problems = web.search("inflasi indonesia")
    assert rows == []
    assert "broken" in problems[0]


def test_an_empty_query_never_hits_the_network() -> None:
    rows, problems = web.search("   ")
    assert rows == []
    assert problems


def test_bing_click_trackers_are_unwrapped() -> None:
    import base64

    target = "https://www.bi.go.id/id/statistik/indikator/data-inflasi.aspx"
    payload = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    assert web._bing_target(f"https://www.bing.com/ck/a?!&&p=abc&u=a1{payload}&ntb=1") == target
    assert web._bing_target("https://example.com/plain") == "https://example.com/plain"


def test_escaped_markup_is_stripped_twice() -> None:
    """Feeds escape their HTML, so one unescape reveals a second layer of tags."""
    assert web._clean("&lt;a href=&quot;x&quot;&gt;Judul&lt;/a&gt; berita") == "Judul berita"


# --------------------------------------------------------------------------- #
# The console
# --------------------------------------------------------------------------- #


def _fake_search(monkeypatch: pytest.MonkeyPatch, rows: list[web.Result]) -> list[str]:
    calls: list[str] = []

    def fake(
        query: str, limit: int = 5, timeout: float = 8.0
    ) -> tuple[list[web.Result], list[str]]:
        calls.append(query)
        return rows[:limit], []

    monkeypatch.setattr(web, "search", fake)
    return calls


def _chat(settings, monkeypatch: pytest.MonkeyPatch, **state: Any):
    from tests.test_phase11_chat import FakeJobs, _patch_db

    _patch_db(monkeypatch, channel=state.get("channel"), videos=state.get("videos"))
    model_calls: list[str] = []

    def llm(prompt: str) -> str:
        model_calls.append(prompt)
        return "{}"

    jobs = FakeJobs()
    return chat.Chat(settings=settings, engine=object(), jobs=jobs, llm=llm), model_calls


def test_cari_searches_without_waiting_for_the_model(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_search(monkeypatch, [_row("Inflasi Indonesia", "naik 3,2 persen")])
    service, model_calls = _chat(settings, monkeypatch)
    reply = service.handle("s", "cari inflasi indonesia")["reply"]
    assert "hasil" in reply[0]
    assert calls == ["inflasi indonesia"]
    assert model_calls == []


def test_cari_says_nothing_when_the_web_says_nothing(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_search(monkeypatch, [])
    service, _model = _chat(settings, monkeypatch)
    reply = " ".join(service.handle("s", "cari topik yang tidak ada")["reply"])
    assert "nol" in reply


def test_cari_keeps_the_hits_for_the_next_turn(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_search(
        monkeypatch,
        [
            _row("Kegagalan startup Asia Tenggara", "struktur rapuh"),
            _row("Startup tutup karena struktur", "bukan modal"),
        ],
    )
    service, _model = _chat(settings, monkeypatch)
    service.handle("s", "cari startup gagal")
    reply = service.handle("s", "pakai 2")["reply"]
    assert reply[0].startswith("topik:")
    assert "Startup tutup" in reply[0]


def test_pakai_without_research_is_not_a_topic(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _model = _chat(settings, monkeypatch)
    service.handle("s", "halo")
    reply = " ".join(service.handle("s", "pakai 2")["reply"])
    assert "topik:" not in reply


def test_a_channel_link_is_never_sent_to_the_web(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """'cari channel @x' is a channel request, and searching it would answer nothing."""
    calls = _fake_search(monkeypatch, [_row("YouTube", "video")])
    service, _model = _chat(settings, monkeypatch)
    service.handle("s", "cari channel youtube.com/@ted")
    assert calls == []


def test_slash_cari_uses_the_same_path(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_search(monkeypatch, [_row("Inflasi Indonesia", "naik")])
    service, model_calls = _chat(settings, monkeypatch)
    reply = service.handle("s", "/cari inflasi indonesia")["reply"]
    assert "hasil" in reply[0]
    assert calls == ["inflasi indonesia"]
    assert model_calls == []


def test_the_menu_lists_cari() -> None:
    from backend import skills

    assert any(skill.name == "cari" for skill in skills.SKILLS)
    assert skills.find("/cari") is not None


# --------------------------------------------------------------------------- #
# The parsers, against the shapes the engines actually send
# --------------------------------------------------------------------------- #


class _Response:
    """Just enough of httpx.Response for the parsers."""

    def __init__(
        self, text: str = "", payload: Any = None, content_type: str = "text/html"
    ) -> None:
        self.text = text
        self._payload = payload
        self.headers = {"content-type": content_type}

    def json(self) -> Any:
        return self._payload


BING_PAGE = """
<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?!&amp;&amp;p=1&amp;u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9h&amp;ntb=1">
Inflasi Indonesia naik</a></h2><p>Badan Pusat Statistik mencatat inflasi 3,2 persen.</p></li>
<li class="b_algo"><h2><a href="https://example.org/b">Inflasi bulanan</a></h2><p>angka terbaru</p></li>
"""

DDG_PAGE = """
<td><a class="result-link" href="https://example.com/inflasi">Inflasi Indonesia</a></td>
<td class="result-snippet">angka inflasi indonesia terbaru</td>
<td><a class="result-link" href="https://example.com/lain">Lain</a></td>
"""

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Inflasi Indonesia melandai - Kompas.com</title>
<link>https://news.google.com/rss/articles/1</link><description>Inflasi Indonesia melandai - Kompas.com</description></item>
<item><title>Tanpa link</title></item>
</channel></rss>"""

WIKI = {
    "query": {"search": [{"title": "Inflasi", "snippet": "<b>Inflasi</b> adalah kenaikan harga"}]}
}

BRAVE = {
    "web": {
        "results": [
            {"title": "Inflasi Indonesia", "url": "https://brave.example/1", "description": "naik"}
        ]
    }
}


def test_bing_reads_titles_snippets_and_real_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Response(BING_PAGE))
    rows = web._bing("inflasi indonesia", 5, 5)
    assert len(rows) == 2
    assert rows[0].url == "https://example.com/a"
    assert "Badan Pusat" in rows[0].snippet


def test_duckduckgo_reads_its_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Response(DDG_PAGE))
    rows = web._ddg("inflasi indonesia", 5, 5)
    assert rows[0].title == "Inflasi Indonesia"
    assert rows[0].snippet.startswith("angka inflasi")


def test_duckduckgo_challenge_is_an_error_not_a_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Response("anomaly detected"))
    with pytest.raises(RuntimeError, match="challenge"):
        web._ddg("inflasi", 5, 5)


def test_google_news_splits_the_publisher_off_the_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Response(RSS, content_type="text/xml"))
    rows = web._gnews("inflasi", 5, 5)
    assert rows[0].title == "Inflasi Indonesia melandai"
    assert rows[0].site == "Kompas.com"
    assert len(rows) == 1  # the item without a link is dropped


def test_wikipedia_builds_article_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Response(payload=WIKI))
    rows = web._wikipedia("inflasi", 5, 5)
    assert rows[0].url == "https://id.wikipedia.org/wiki/Inflasi"


def test_brave_only_runs_with_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BRAVE_API_KEY"):
        web._brave("inflasi", 5, 5)
    monkeypatch.setenv("BRAVE_API_KEY", "test")
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Response(payload=BRAVE))
    rows = web._brave("inflasi", 5, 5)
    assert rows[0].url == "https://brave.example/1"


def test_read_returns_prose_not_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    body = (
        "<html><body><nav>Skip Ribbon Commands</nav>"
        + "<p>"
        + "Inflasi Indonesia turun tipis pada bulan Oktober. " * 8
        + "</p>"
        + "<p>"
        + "Badan Pusat Statistik mencatat angka baru. " * 8
        + "</p>"
        + "</body></html>"
    )
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Response(body))
    text = web.read("https://example.com/a", limit=400)
    assert "Inflasi Indonesia turun" in text
    assert "Skip Ribbon" not in text


def test_read_says_nothing_for_a_binary_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web.httpx, "get", lambda *a, **k: _Response("x", content_type="application/pdf")
    )
    assert web.read("https://example.com/a.pdf") == ""


def test_dedupe_keeps_one_row_per_page() -> None:
    rows = [
        _row("A", url="https://example.com/page/?utm=1"),
        _row("A lagi", url="https://example.com/page/"),
        _row("B", url="https://example.com/b"),
    ]
    assert len(web._dedupe(rows)) == 2
