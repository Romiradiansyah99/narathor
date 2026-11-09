"""Kontrak data Narathor. Satu tempat untuk seluruh model Pydantic.

Backend, agent, dan CLI semuanya mengimpor dari sini supaya schema tidak
bercabang tiga. Tidak ada logika I/O di file ini.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Pustaka
# --------------------------------------------------------------------------- #


class Channel(BaseModel):
    """Channel sumber pustaka."""

    model_config = ConfigDict(frozen=True)

    channel_id: str
    name: str
    handle: str
    url: str


class Video(BaseModel):
    """Satu video dalam pustaka."""

    model_config = ConfigDict(frozen=True)

    video_id: str
    title: str
    duration_s: int = Field(ge=0)
    published_at: date | None = None
    url: str | None = None


class Word(BaseModel):
    """Satu kata bertimestamp di dalam segmen."""

    t0: float
    t1: float
    text: str


class Segment(BaseModel):
    """Segmen transkrip hasil segmentasi."""

    t0: float = Field(ge=0)
    t1: float = Field(ge=0)
    text: str
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def _range_valid(self) -> Self:
        if self.t1 < self.t0:
            raise ValueError("t1 tidak boleh lebih kecil dari t0")
        return self


class SourceKind(StrEnum):
    """Asal transkrip."""

    CAPTIONS = "captions"
    WHISPER = "whisper"


class TranscriptDoc(BaseModel):
    """Transkrip penuh satu video."""

    video_id: str
    language: str
    source: SourceKind
    segments: list[Segment] = Field(default_factory=list)

    def text_between(self, t0: float, t1: float) -> str:
        """Gabungkan teks segmen yang beririsan dengan rentang waktu."""
        parts = [s.text for s in self.segments if s.t1 > t0 and s.t0 < t1]
        return " ".join(parts)


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #

LiteracyLevel = Literal["rendah", "menengah", "tinggi"]
RecencyPreference = Literal["any", "recent", "classic"]


class Audience(BaseModel):
    """Audiens sasaran brief."""

    primary: str = Field(min_length=3)
    literacy_level: LiteracyLevel
    pain_points: list[str] = Field(default_factory=list)


class Tone(BaseModel):
    """Gaya bahasa yang diminta brief."""

    target: str = Field(min_length=3)
    avoid: list[str] = Field(default_factory=list)


class SeasonalContext(BaseModel):
    """Konteks musiman brief."""

    as_of: date
    period: str | None = None
    moments: list[str] = Field(default_factory=list)
    trend_notes: str = ""
    trend_expiry: date | None = None


class Sources(BaseModel):
    """Sumber pustaka yang dipakai brief."""

    channels: list[str] = Field(min_length=1)
    recency_preference: RecencyPreference
    min_duration_s: int = 180


class OutputSpec(BaseModel):
    """Bentuk keluaran yang diminta."""

    scripts: int = Field(ge=1)
    target_duration_s: int
    language: Literal["id"]
    montages: int = 0

    @field_validator("target_duration_s")
    @classmethod
    def _duration_allowed(cls, v: int) -> int:
        if v == 30:
            raise ValueError("target_duration_s 30 adalah dead zone; pakai 13..20 atau 60")
        if not (13 <= v <= 20 or v == 60):
            raise ValueError("target_duration_s harus 13..20 atau 60")
        return v


class ScoringOverrides(BaseModel):
    """Penyetelan bobot skor brief."""

    model_config = ConfigDict(extra="forbid")

    brand_fit_weight: float | None = Field(default=None, ge=0, le=1)
    hook_weight: float | None = Field(default=None, ge=0, le=1)
    satisfaction_weight: float | None = Field(default=None, ge=0, le=1)


class NarrativeBrief(BaseModel):
    """Narrative Brief milik bos. Satu-satunya tempat arah konten."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    learning_outcome: str
    thesis: str
    audience: Audience
    values_allowed: list[str] = Field(default_factory=list)
    values_blocked: list[str] = Field(default_factory=list)
    register_level: int = Field(ge=1, le=4)
    tone: Tone
    seasonal_context: SeasonalContext
    sources: Sources
    output: OutputSpec
    scoring_overrides: ScoringOverrides | None = None

    @field_validator("id")
    @classmethod
    def _id_slug(cls, v: str) -> str:
        if not v or v != v.lower():
            raise ValueError("id harus huruf kecil")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if set(v) - allowed:
            raise ValueError("id hanya boleh huruf kecil, angka, dan tanda hubung")
        return v

    @model_validator(mode="after")
    def _values_disjoint(self) -> Self:
        overlap = set(self.values_allowed) & set(self.values_blocked)
        if overlap:
            raise ValueError(f"values_allowed dan values_blocked bertabrakan: {sorted(overlap)}")
        return self


# --------------------------------------------------------------------------- #
# Unit kerja
# --------------------------------------------------------------------------- #

SegmentKind = Literal["thesis", "story", "number", "rebuttal", "close"]
UnitStatus = Literal["pending", "running", "done", "returned", "deferred", "blocked"]


class SegmentFeatures(BaseModel):
    """Fitur heuristik satu segmen. Dihitung tanpa LLM."""

    word_count: int = 0
    wpm: float = 0.0
    filler_positions: list[int] = Field(default_factory=list)
    dead_air_spans: list[tuple[float, float]] = Field(default_factory=list)
    has_setup_preamble: bool = False
    payoff_present: bool = False
    niche_consistency_score: float = 0.0
    hook_archetype: str | None = None


class SegmentCard(BaseModel):
    """Kartu ringkas segmen, bahan Matcher. Target <= 250 token."""

    segment_id: str
    video_id: str
    t0: float
    t1: float
    kind: SegmentKind
    key_quote: str
    features: SegmentFeatures = Field(default_factory=SegmentFeatures)
    brand_fit: int = Field(default=0, ge=0, le=5)


class Combo(BaseModel):
    """Kombinasi 2-5 segmen dari minimal 2 video, satu tesis."""

    combo_id: str
    thesis: str
    segment_ids: list[str]
    video_ids: list[str]
    rationale: str = ""

    @model_validator(mode="after")
    def _cross_video(self) -> Self:
        if len(self.segment_ids) < 2:
            raise ValueError("combo minimal 2 segmen")
        if len(self.segment_ids) > 5:
            raise ValueError("combo maksimal 5 segmen")
        if len(set(self.video_ids)) < 2:
            raise ValueError("combo minimal 2 video berbeda")
        return self


class Citation(BaseModel):
    """Jejak fakta ke detik sumber."""

    video_id: str
    t0: float
    t1: float
    quote: str = Field(min_length=2)


class Beat(BaseModel):
    """Satu ketukan naskah."""

    at_s: float = Field(ge=0)
    text: str
    is_claim: bool = False
    citation: Citation | None = None
    overlay: str | None = None

    @model_validator(mode="after")
    def _claim_cited(self) -> Self:
        if self.is_claim and self.citation is None:
            raise ValueError("beat dengan is_claim true wajib punya citation")
        return self


class ShortScript(BaseModel):
    """Naskah short lengkap dengan sitasi."""

    script_id: str
    combo_id: str
    brief_id: str
    hook: str
    beats: list[Beat]
    payoff_at_s: float = Field(ge=0)
    payoff_pays_off: bool
    single_minded_proposition: str
    title: str
    caption: str
    target_duration_s: int
    discarded: list[str] = Field(default_factory=list)

    @field_validator("hook")
    @classmethod
    def _hook_short(cls, v: str) -> str:
        if len(v.split()) > 7:
            raise ValueError("hook maksimal 7 kata")
        return v

    @model_validator(mode="after")
    def _payoff_within(self) -> Self:
        longest = max((b.at_s for b in self.beats), default=0.0)
        if self.payoff_at_s > longest + 2:
            raise ValueError("payoff_at_s melewati beat terakhir")
        if len(self.beats) < 2:
            raise ValueError("naskah minimal 2 beat")
        return self


GATE_NAMES = (
    "soul_compliance",
    "citation_integrity",
    "hook_payoff",
    "craft_distinctiveness",
    "brief_alignment",
    "values_clean",
    "traceability",
)


class GateResult(BaseModel):
    """Hasil satu gate Critic."""

    name: str
    passed: bool
    reason: str = ""


class Audit(BaseModel):
    """Hasil penilaian tujuh gate."""

    script_id: str
    gates: list[GateResult]
    cites_ok: bool
    verdict: Literal["pass", "return", "interrupt", "deny"]
    pressed: list[str] = Field(default_factory=list)
    reason: str = ""

    @model_validator(mode="after")
    def _all_gates(self) -> Self:
        missing = set(GATE_NAMES) - {g.name for g in self.gates}
        if missing:
            raise ValueError(f"gate belum dinilai: {sorted(missing)}")
        return self

    @property
    def all_passed(self) -> bool:
        """True bila seluruh gate lulus."""
        return all(g.passed for g in self.gates)


# --------------------------------------------------------------------------- #
# Run dan audit sistem
# --------------------------------------------------------------------------- #


class SoulCheck(BaseModel):
    """Hasil pemeriksaan konstitusi."""

    ok: bool
    version: int | None
    expected_hash: str | None
    actual_hash: str | None
    checked_at: datetime
    reason: str = ""


class SourceRef(BaseModel):
    """Sumber yang dipakai satu run."""

    video_id: str
    source: SourceKind
    duration_s: float = 0.0


class RunRecord(BaseModel):
    """Jejak satu run. Tanpa ini artefak tidak boleh ditulis."""

    run_id: str
    brief_id: str
    brief_hash: str
    soul_version: int
    prompt_version: str
    models: dict[str, str] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "done", "failed"] = "running"
    est_cost_usd: float = 0.0
    skipped: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _traceable(self) -> Self:
        if not self.soul_version or not self.prompt_version or not self.brief_hash:
            raise ValueError("run tanpa soul_version, prompt_version, atau brief_hash ditolak")
        return self
