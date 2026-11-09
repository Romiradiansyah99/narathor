# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportReturnType=false, reportTypedDictNotRequiredAccess=false, reportIndexIssue=false
"""Graf lima peran. Fan-out lewat Send, batas konkurensi eksplisit, state durabel."""

from __future__ import annotations

import operator
import threading
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from agent import critic as critic_mod
from agent import matcher as matcher_mod
from agent import writer as writer_mod
from agent.models import LanguageModel
from contracts import (
    Audit,
    Combo,
    NarrativeBrief,
    SegmentCard,
    ShortScript,
    TranscriptDoc,
    Video,
)
from index.build import build_cards
from index.segmenter import segment_transcript

MAX_ITERATIONS = 2


class Tracker:
    """Catat berapa unit berjalan bersamaan. Diukur, bukan diasumsikan."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current = 0
        self.max_seen = 0
        self.events: list[tuple[str, int]] = []

    def enter(self, unit: str) -> int:
        """Tandai satu unit mulai."""
        with self._lock:
            self.current += 1
            self.max_seen = max(self.max_seen, self.current)
            self.events.append((unit, self.current))
            return self.current

    def leave(self) -> None:
        """Tandai satu unit selesai."""
        with self._lock:
            self.current = max(self.current - 1, 0)


class AgentState(TypedDict, total=False):
    """State bersama seluruh node."""

    brief: NarrativeBrief
    videos: list[Video]
    transcripts: dict[str, TranscriptDoc]
    cards: Annotated[list[SegmentCard], operator.add]
    combos: list[Combo]
    scripts: Annotated[list[ShortScript], operator.add]
    audits: Annotated[list[Audit], operator.add]
    deferred: Annotated[list[str], operator.add]
    blocked: Annotated[list[str], operator.add]
    attempts: Annotated[dict[str, int], lambda a, b: {**a, **b}]
    iteration: int


@dataclass
class AgentDeps:
    """Ketergantungan yang disuntikkan; test memakai stub, bukan model."""

    writer_llm: LanguageModel | None = None
    matcher_llm: LanguageModel | None = None
    tracker: Tracker = field(default_factory=Tracker)
    max_concurrency: int = 5
    quote_checker: Any = None
    brief: NarrativeBrief | None = None
    target_combos: int = 30


def _safe_index(dep: AgentDeps, video_id: str, doc: TranscriptDoc) -> list[SegmentCard]:
    """Satu unit index; gagal tidak menghentikan run."""
    dep.tracker.enter(video_id)
    try:
        segments = segment_transcript(doc.segments)
        return build_cards(doc, segments)
    except Exception:
        return []
    finally:
        dep.tracker.leave()


def build_graph(dep: AgentDeps, checkpointer: Any = None):
    """Bangun StateGraph. Model hanya dipanggil bila llm diberikan."""

    def plan(state: AgentState) -> dict[str, Any]:
        """Kirim satu unit index per video lewat Send, bukan loop."""
        return {"cards": [], "deferred": [], "blocked": [], "attempts": {}, "iteration": 0}

    def fan_out(state: AgentState) -> list[Send]:
        """Fan-out: satu Send per video."""
        return [
            Send("index", {"video_id": v.video_id, "transcripts": state["transcripts"]})
            for v in state["videos"]
        ]

    def index_node(payload: dict[str, Any]) -> dict[str, Any]:
        """Node index per video. Unit tetap tercatat walau transkrip tidak ada."""
        video_id = payload["video_id"]
        doc = payload.get("transcripts", {}).get(video_id)
        if doc is None:
            dep.tracker.enter(video_id)
            dep.tracker.leave()
            return {"deferred": [video_id]}
        return {"cards": _safe_index(dep, video_id, doc)}

    def match_node(state: AgentState) -> dict[str, Any]:
        """Matcher: rakit combo lintas video."""
        brief = state["brief"]
        combos = matcher_mod.match(state["cards"], brief, dep.target_combos, llm=dep.matcher_llm)
        return {"combos": combos}

    def write_node(state: AgentState) -> list[Send]:
        """Fan-out: satu unit write per combo."""
        return [
            Send(
                "write",
                {
                    "combo": c,
                    "brief": state["brief"],
                    "cards": state["cards"],
                    "transcripts": state["transcripts"],
                    "attempts": dict(state.get("attempts", {})),
                },
            )
            for c in state["combos"]
        ]

    def write_one(payload: dict[str, Any]) -> dict[str, Any]:
        """Tulis satu naskah. Dua kegagalan berturut menjadi deferred."""
        combo: Combo = payload["combo"]
        llm = dep.writer_llm
        if llm is None:
            return {"deferred": [combo.combo_id], "attempts": {combo.combo_id: MAX_ITERATIONS}}
        attempts = dict(payload.get("attempts", {}))
        attempt = attempts.get(combo.combo_id, 0)
        while attempt < MAX_ITERATIONS:
            attempt += 1
            try:
                script = writer_mod.write(
                    combo,
                    payload["brief"],
                    payload["cards"],
                    payload["transcripts"],
                    llm,
                    script_id=f"script-{combo.combo_id}",
                )
            except Exception:
                attempts[combo.combo_id] = attempt
                continue
            attempts[combo.combo_id] = attempt
            return {"scripts": [script], "attempts": attempts}
        attempts[combo.combo_id] = attempt
        return {"deferred": [combo.combo_id], "attempts": attempts}

    def critique_node(state: AgentState) -> dict[str, Any]:
        """Tujuh gate per naskah. Gagal -> Writer sekali lagi, maks dua iterasi."""
        audits: list[Audit] = []
        scripts: list[ShortScript] = []
        deferred = list(state.get("deferred", []))
        attempts = dict(state.get("attempts", {}))
        checker = dep.quote_checker or (lambda _citation: True)
        for script in state["scripts"]:
            current = script
            audit = critic_mod.judge(current, state["brief"], state["transcripts"], checker)
            tries = attempts.get(current.script_id, 1)
            while audit.verdict != "pass" and audit.verdict != "deny" and tries < MAX_ITERATIONS:
                combo = next((c for c in state["combos"] if c.combo_id == current.combo_id), None)
                if combo is None or dep.writer_llm is None:
                    break
                try:
                    current = writer_mod.write(
                        combo,
                        state["brief"],
                        state["cards"],
                        state["transcripts"],
                        dep.writer_llm,
                        script_id=current.script_id,
                    )
                except Exception:
                    tries += 1
                    attempts[current.script_id] = tries
                    continue
                tries += 1
                attempts[current.script_id] = tries
                audit = critic_mod.judge(current, state["brief"], state["transcripts"], checker)
            attempts[current.script_id] = tries
            if audit.verdict != "pass":
                deferred.append(current.script_id)
            audits.append(audit)
            scripts.append(current)
        return {"audits": audits, "scripts": scripts, "deferred": deferred, "attempts": attempts}

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("index", index_node)
    graph.add_node("match", match_node)
    graph.add_node("write", write_one)
    graph.add_node("critique", critique_node)
    graph.add_edge("__start__", "plan")
    graph.add_conditional_edges("plan", fan_out, ["index"])
    graph.add_edge("index", "match")
    graph.add_conditional_edges("match", write_node, ["write"])
    graph.add_edge("write", "critique")
    graph.add_edge("critique", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())


def run_agent(
    brief: NarrativeBrief,
    videos: list[Video],
    transcripts: dict[str, TranscriptDoc],
    dep: AgentDeps,
    thread_id: str = "default",
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Jalankan graf sekali. State akhir dikembalikan."""
    graph = build_graph(dep, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}, "max_concurrency": dep.max_concurrency}
    payload: AgentState = {
        "brief": brief,
        "videos": videos,
        "transcripts": transcripts,
        "cards": [],
        "combos": [],
        "scripts": [],
        "audits": [],
        "deferred": [],
        "blocked": [],
        "attempts": {},
        "iteration": 0,
    }
    result = dict(graph.invoke(payload, config=config))
    scripts: dict[str, ShortScript] = {}
    for script in result.get("scripts", []):
        scripts[script.script_id] = script
    result["scripts"] = [scripts[key] for key in sorted(scripts)]
    audits: dict[str, Audit] = {}
    for audit in result.get("audits", []):
        audits[audit.script_id] = audit
    result["audits"] = [audits[key] for key in sorted(audits)]
    result["deferred"] = sorted(set(result.get("deferred", [])))
    return result
