"""Test Fase 5, 6, 7: matcher, writer, critic. Tanpa model, tanpa jaringan."""

from __future__ import annotations

import pytest

from agent import critic as critic_mod
from agent.graph import MAX_ITERATIONS, AgentDeps, Tracker, run_agent
from agent.matcher import contradicts, match, score_card
from agent.writer import WriterError, parse
from backend.store import InvariantError, save_script
from contracts import (
    Beat,
    Citation,
    Combo,
    NarrativeBrief,
    SegmentCard,
    ShortScript,
    TranscriptDoc,
    Video,
)
from tests.fixtures import FIXTURE_TRANSCRIPTS, FIXTURE_VIDEOS

BRIEF = NarrativeBrief.model_validate(
    {
        "id": "uji",
        "title": "Uji",
        "learning_outcome": "Penonton memahami arah aliran uang bukan jumlahnya",
        "thesis": "Masalah keuangan pribadi lebih sering soal arah aliran daripada jumlah",
        "audience": {"primary": "Indonesia 18-35", "literacy_level": "menengah"},
        "values_allowed": ["kejujuran_intelektual"],
        "values_blocked": ["janji_kaya_instan"],
        "register_level": 2,
        "tone": {"target": "tegas, jernih"},
        "seasonal_context": {"as_of": "2026-11-09"},
        "sources": {"channels": ["https://youtube.com/@x"], "recency_preference": "any"},
        "output": {"scripts": 2, "target_duration_s": 15, "language": "id"},
    }
)

REPLY = {
    "hook": "Uang bocor di tempat yang salah",
    "beats": [
        {
            "at_s": 0,
            "text": "Masalah keuangan bukan berapa yang masuk tapi ke mana perginya",
            "is_claim": True,
            "citation": {
                "video_id": "VID-0001",
                "t0": 0,
                "t1": 12,
                "quote": "masalahnya bukan berapa yang masuk",
            },
        },
        {
            "at_s": 8,
            "text": "Gaji naik dua kali lipat tabungan tidak bergerak",
            "is_claim": True,
            "citation": {
                "video_id": "VID-0002",
                "t0": 0,
                "t1": 5,
                "quote": "Gaji naik dua kali lipat, tabungan tidak bergerak",
            },
        },
    ],
    "payoff_at_s": 10,
    "payoff_pays_off": True,
    "single_minded_proposition": "Arah aliran uang lebih menentukan daripada jumlah",
    "title": "Arah aliran",
    "caption": "#uji",
    "discarded": ["angka statistik"],
}


class SequenceModel:
    """Model stub yang menjawab berbeda tiap panggilan."""

    def __init__(self, replies: list[str | dict]) -> None:
        self.replies = replies
        self.calls = 0

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Kembalikan jawaban ke-n, atau jawaban terakhir bila habis."""
        import json

        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return reply if isinstance(reply, str) else json.dumps(reply)


@pytest.fixture
def videos() -> list[Video]:
    return [Video.model_validate(v) for v in FIXTURE_VIDEOS]


@pytest.fixture
def transcripts() -> dict[str, TranscriptDoc]:
    return {key: TranscriptDoc.model_validate(doc) for key, doc in FIXTURE_TRANSCRIPTS.items()}


def _card(video_id: str, text: str, kind: str = "thesis") -> SegmentCard:
    return SegmentCard(
        segment_id=f"{video_id}:0",
        video_id=video_id,
        t0=0.0,
        t1=10.0,
        kind=kind,
        key_quote=text,
    )


def test_one_unit_per_video(videos, transcripts) -> None:
    dep = AgentDeps(
        writer_llm=SequenceModel([REPLY]), max_concurrency=2, quote_checker=lambda c: True
    )
    run_agent(BRIEF, videos, transcripts, dep, thread_id="t1")
    assert len(dep.tracker.events) == len(videos)


def test_concurrency_never_exceeds_cap(videos, transcripts) -> None:
    dep = AgentDeps(
        writer_llm=SequenceModel([REPLY]), max_concurrency=1, quote_checker=lambda c: True
    )
    run_agent(BRIEF, videos, transcripts, dep, thread_id="t1")
    assert dep.tracker.max_seen <= 1
    assert max(observed for _, observed in dep.tracker.events) <= 1


def test_tracker_records_overlap() -> None:
    tracker = Tracker()
    tracker.enter("a")
    tracker.enter("b")
    tracker.leave()
    assert tracker.max_seen == 2


def test_single_video_combo_rejected() -> None:
    with pytest.raises(ValueError):
        Combo(
            combo_id="c",
            thesis="t",
            segment_ids=["a", "b"],
            video_ids=["VID-1"],
        )


def test_contradiction_rejected() -> None:
    a = _card("VID-1", "Masalahnya memang aliran uang pergi")
    b = _card("VID-2", "Itu tidak benar, masalahnya bukan aliran uang pergi", kind="rebuttal")
    assert contradicts(a, b) is True


def test_failing_unit_does_not_stop_run(videos, transcripts) -> None:
    partial = dict(transcripts)
    del partial["VID-0002"]
    dep = AgentDeps(
        writer_llm=SequenceModel([REPLY]), max_concurrency=2, quote_checker=lambda c: True
    )
    result = run_agent(BRIEF, videos, partial, dep, thread_id="t1")
    assert "VID-0002" in result["deferred"]
    assert result["cards"]


def test_retry_then_deferred(videos, transcripts) -> None:
    dep = AgentDeps(
        writer_llm=SequenceModel(["{rusak", "{rusak lagi"]),
        max_concurrency=2,
        quote_checker=lambda c: True,
        target_combos=2,
    )
    result = run_agent(BRIEF, videos, transcripts, dep, thread_id="t1")
    assert result["deferred"]
    assert all(attempts >= MAX_ITERATIONS for attempts in result["attempts"].values())


def test_second_attempt_can_succeed(videos, transcripts) -> None:
    dep = AgentDeps(
        writer_llm=SequenceModel(["{rusak", REPLY]),
        max_concurrency=2,
        quote_checker=lambda c: True,
        target_combos=1,
    )
    result = run_agent(BRIEF, videos, transcripts, dep, thread_id="t1")
    assert result["scripts"]
    assert result["audits"][0].verdict in {"pass", "return"}


def test_writer_prompt_contains_brief(videos, transcripts) -> None:
    from agent.writer import build_prompt

    dep = AgentDeps(
        writer_llm=SequenceModel([REPLY]), max_concurrency=2, quote_checker=lambda c: True
    )
    result = run_agent(BRIEF, videos, transcripts, dep, thread_id="t1")
    cards = result["cards"]
    prompt = build_prompt(BRIEF, result["combos"][0], cards, transcripts)
    assert BRIEF.learning_outcome.strip()[:20] in prompt
    assert "VID-" in prompt


def test_script_rejects_claim_without_citation() -> None:
    with pytest.raises(ValueError):
        ShortScript(
            script_id="s",
            combo_id="c",
            brief_id="b",
            hook="hook pendek saja",
            beats=[
                Beat(at_s=0, text="a", is_claim=True),
                Beat(at_s=5, text="b"),
            ],
            payoff_at_s=5,
            payoff_pays_off=True,
            single_minded_proposition="p",
            title="t",
            caption="c",
            target_duration_s=15,
        )


def test_hook_length_enforced() -> None:
    with pytest.raises(ValueError):
        ShortScript(
            script_id="s",
            combo_id="c",
            brief_id="b",
            hook="hook ini jauh terlalu panjang untuk satu short",
            beats=[Beat(at_s=0, text="a"), Beat(at_s=5, text="b")],
            payoff_at_s=5,
            payoff_pays_off=True,
            single_minded_proposition="p",
            title="t",
            caption="c",
            target_duration_s=15,
        )


def test_parse_rejects_non_json() -> None:
    combo = Combo.model_construct(
        combo_id="c1", thesis="t", segment_ids=["a", "b"], video_ids=["V1", "V2"], rationale=""
    )
    with pytest.raises(WriterError):
        parse("bukan json", combo, BRIEF, "s1")


def test_store_rejects_fake_quote(settings) -> None:
    from backend import db

    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    script = ShortScript(
        script_id="s1",
        combo_id="c1",
        brief_id="b1",
        hook="hook pendek",
        beats=[
            Beat(
                at_s=0,
                text="klaim",
                is_claim=True,
                citation=Citation(
                    video_id="VID-0001", t0=0, t1=10, quote="kalimat yang tidak pernah diucapkan"
                ),
            ),
            Beat(at_s=5, text="penutup"),
        ],
        payoff_at_s=5,
        payoff_pays_off=True,
        single_minded_proposition="p",
        title="t",
        caption="c",
        target_duration_s=15,
    )
    with pytest.raises(InvariantError):
        save_script(engine, script)
    engine.dispose()


def test_store_accepts_real_quote(settings) -> None:
    from backend import db

    engine = db.build_engine(settings.database_url)
    db.ensure_ready(engine, settings.data_dir)
    script = ShortScript(
        script_id="s2",
        combo_id="c1",
        brief_id="b1",
        hook="hook pendek",
        beats=[
            Beat(
                at_s=0,
                text="klaim",
                is_claim=True,
                citation=Citation(
                    video_id="VID-0001", t0=0, t1=12, quote="masalahnya bukan berapa yang masuk"
                ),
            ),
            Beat(at_s=5, text="penutup"),
        ],
        payoff_at_s=5,
        payoff_pays_off=True,
        single_minded_proposition="p",
        title="t",
        caption="c",
        target_duration_s=15,
    )
    save_script(engine, script)
    engine.dispose()


def _script(**overrides) -> ShortScript:
    payload = {
        "script_id": "s1",
        "combo_id": "c1",
        "brief_id": "uji",
        "hook": "Uang bocor di tempat salah",
        "beats": [
            Beat(
                at_s=0,
                text="Masalah keuangan bukan jumlah tapi arah aliran uang",
                is_claim=True,
                citation=Citation(
                    video_id="VID-0001", t0=0, t1=12, quote="masalahnya bukan berapa yang masuk"
                ),
            ),
            Beat(
                at_s=8,
                text="Gaji naik tabungan tidak bergerak karena pengeluaran ikut naik",
                is_claim=True,
                citation=Citation(
                    video_id="VID-0002", t0=0, t1=5, quote="Gaji naik dua kali lipat"
                ),
            ),
        ],
        "payoff_at_s": 8,
        "payoff_pays_off": True,
        "single_minded_proposition": "Arah aliran uang lebih menentukan daripada jumlah",
        "title": "t",
        "caption": "c",
        "target_duration_s": 15,
    }
    payload.update(overrides)
    return ShortScript(**payload)


def test_critic_passes_aligned_script(transcripts) -> None:
    audit = critic_mod.judge(_script(), BRIEF, transcripts, lambda c: True)
    assert {g.name for g in audit.gates} == set(critic_mod.gate_names())
    assert audit.verdict == "pass", audit.reason


def test_critic_returns_generic_script(transcripts) -> None:
    script = _script(hook="Di era digital semua orang bisa kaya")
    audit = critic_mod.judge(script, BRIEF, transcripts, lambda c: True)
    assert audit.verdict == "return"
    assert "craft_distinctiveness" in audit.pressed


def test_critic_returns_unpaid_hook(transcripts) -> None:
    script = _script(payoff_pays_off=False)
    audit = critic_mod.judge(script, BRIEF, transcripts, lambda c: True)
    assert audit.verdict == "return"
    assert "hook_payoff" in audit.pressed


def test_critic_denies_blocked_value(transcripts) -> None:
    script = _script(caption="janji kaya instan")
    audit = critic_mod.judge(script, BRIEF, transcripts, lambda c: True)
    assert audit.verdict in {"return", "deny"}
    assert "values_clean" in audit.pressed


def test_match_respects_brand_fit_floor(videos, transcripts) -> None:
    dep = AgentDeps(max_concurrency=1, quote_checker=lambda c: True)
    result = run_agent(BRIEF, videos, transcripts, dep, thread_id="t1")
    cards = result["cards"]
    combos = match(cards, BRIEF, 5)
    for combo in combos:
        assert len(set(combo.video_ids)) >= 2
    assert all(score_card(c, BRIEF) >= 0 for c in cards)
