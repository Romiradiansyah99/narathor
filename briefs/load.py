"""Parser dan validator Narrative Brief. Dua belas alasan penolakan, fail-closed."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from contracts import NarrativeBrief

# Nilai yang diwajibkan SOUL.md, sehingga tidak boleh masuk values_blocked.
SOUL_MANDATED: dict[str, str] = {
    "akses_bebas": "Pasal 3",
    "pengetahuan_bebas": "Pasal 3",
    "transparansi": "Pasal 7",
    "keterlacakan": "Pasal 7",
    "sitasi": "Pasal 5",
    "kejujuran_intelektual": "Pasal 5",
    "tanggung_jawab_personal": "Pasal 2",
    "pemahaman": "Pasal 2",
}

LOOSEN_CITATION = (
    "tanpa sitasi",
    "tanpa sumber",
    "tanpa rujukan",
    "abaikan sumber",
    "abaikan sitasi",
    "bebas fakta",
    "tidak perlu sitasi",
    "no citation",
    "ignore sources",
)

FORGIVE_CLICKBAIT = (
    "clickbait",
    "bikin penasaran sampai akhir",
    "tahan payoff",
    "tunda payoff",
    "tunda pembayaran",
    "teaser",
    "judul provokatif",
    "tahan informasi",
)

WEIGHT_BOUNDS = {
    "brand_fit_weight": (0.0, 0.30),
    "satisfaction_weight": (0.10, 0.35),
    "hook_weight": (0.15, 0.30),
}


def _is_token(value: str) -> bool:
    """True bila nilai berupa token snake_case huruf kecil."""
    if not value or not value[0].isalpha():
        return False
    return all(c.islower() or c.isdigit() or c == "_" for c in value)


@dataclass(frozen=True)
class Rejection:
    """Satu alasan penolakan beserta dasarnya."""

    code: int
    message: str


@dataclass
class BriefReport:
    """Hasil validasi satu brief."""

    brief_id: str
    brief: NarrativeBrief | None
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True bila tidak ada penolakan."""
        return not self.rejections and self.brief is not None

    def render(self) -> str:
        """Pesan penolakan untuk stderr."""
        head = f'Brief "{self.brief_id}" ditolak.'
        body = "\n\n".join(f"[{r.code}] {r.message}" for r in self.rejections)
        return f"{head}\n\n{body}\n\nTidak ada artefak yang ditulis."


class BriefRejected(RuntimeError):
    """Brief ditolak; tidak ada artefak yang boleh ditulis."""

    def __init__(self, report: BriefReport) -> None:
        super().__init__(report.render())
        self.report = report


def brief_path(briefs_dir: Path, brief_id: str) -> Path:
    """Jalur file brief."""
    return briefs_dir / f"{brief_id}.yaml"


def brief_hash(brief: NarrativeBrief) -> str:
    """Hash stabil atas isi brief, dipakai cache key dan run.json."""
    payload = brief.model_dump_json(exclude_none=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text_blob(brief: NarrativeBrief) -> str:
    parts = [brief.tone.target, *brief.tone.avoid, brief.seasonal_context.trend_notes or ""]
    return " ".join(parts).lower()


def validate(brief_id: str, raw: dict) -> BriefReport:
    """Validasi deterministik. Lapis B (model judge) ditangani soul/guard.py."""
    rejections: list[Rejection] = []

    for name in ("learning_outcome", "thesis"):
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            code = 1 if name == "learning_outcome" else 2
            rejections.append(
                Rejection(
                    code, f"field {name} kosong. Pasal 1 dan 2 menuntut pemahaman yang dinyatakan."
                )
            )

    seasonal = raw.get("seasonal_context")
    if not isinstance(seasonal, dict) or not seasonal.get("as_of"):
        rejections.append(
            Rejection(
                3,
                "seasonal_context.as_of kosong; gaya tanpa tanggal tidak dapat dipertanggungjawabkan.",
            )
        )

    blocked = raw.get("values_blocked") or []
    allowed = raw.get("values_allowed") or []
    if isinstance(blocked, list):
        for value in blocked:
            if not isinstance(value, str):
                rejections.append(
                    Rejection(12, f"values_blocked memuat nilai bukan teks: {value!r}.")
                )
                continue
            key = value.strip().lower()
            if key in SOUL_MANDATED:
                rejections.append(
                    Rejection(
                        5,
                        f'values_blocked memuat "{value}", yang justru diwajibkan soul ({SOUL_MANDATED[key]}).',
                    )
                )
            elif not _is_token(key):
                rejections.append(
                    Rejection(
                        12,
                        f'Ambiguitas pada field values_blocked: "{value}" tidak dapat dipetakan ke nilai mana pun. '
                        "Perjelas, atau hapus.",
                    )
                )

    overlap = {str(v).strip().lower() for v in blocked if isinstance(v, str)} & {
        str(v).strip().lower() for v in allowed if isinstance(v, str)
    }
    if overlap:
        rejections.append(
            Rejection(4, f"values_allowed dan values_blocked bertabrakan: {sorted(overlap)}.")
        )

    sources = raw.get("sources")
    channels = sources.get("channels") if isinstance(sources, dict) else None
    if not isinstance(channels, list) or not channels:
        rejections.append(Rejection(9, "sources.channels kosong; tidak ada bahan."))
    elif not all(isinstance(c, str) and c.startswith("http") for c in channels):
        rejections.append(Rejection(9, "sources.channels memuat nilai yang bukan URL."))

    register = raw.get("register_level")
    if not isinstance(register, int) or not 1 <= register <= 4:
        rejections.append(Rejection(10, "register_level harus 1..4."))

    duration = (
        (raw.get("output") or {}).get("target_duration_s")
        if isinstance(raw.get("output"), dict)
        else None
    )
    if duration == 30:
        rejections.append(
            Rejection(8, "target_duration_s 30 adalah dead zone; pakai 13..20 atau 60.")
        )

    blob = " ".join(
        str(x)
        for x in [
            (raw.get("tone") or {}).get("target", "") if isinstance(raw.get("tone"), dict) else "",
            *(
                (raw.get("tone") or {}).get("avoid") or []
                if isinstance(raw.get("tone"), dict)
                else []
            ),
            seasonal.get("trend_notes", "") if isinstance(seasonal, dict) else "",
        ]
    ).lower()
    for needle in LOOSEN_CITATION:
        if needle in blob:
            rejections.append(
                Rejection(
                    6,
                    f'tone atau trend_notes memuat "{needle}"; ini meminta melonggarkan sitasi (Pasal 5).',
                )
            )
            break
    for needle in FORGIVE_CLICKBAIT:
        if needle in blob:
            rejections.append(
                Rejection(
                    7,
                    f'tone atau trend_notes memuat "{needle}"; ini meminta memaafkan clickbait (Pasal 4).',
                )
            )
            break

    overrides = raw.get("scoring_overrides")
    if isinstance(overrides, dict):
        for key, (low, high) in WEIGHT_BOUNDS.items():
            value = overrides.get(key)
            if value is None:
                continue
            if not isinstance(value, int | float) or not low <= float(value) <= high:
                rejections.append(
                    Rejection(11, f"scoring_overrides.{key}={value} di luar batas {low}..{high}.")
                )
        hook = overrides.get("hook_weight")
        satisfaction = overrides.get("satisfaction_weight")
        if (
            hook is not None
            and satisfaction is not None
            and float(hook) > float(satisfaction) + 0.10
        ):
            rejections.append(
                Rejection(
                    11,
                    f"hook_weight {hook} melebihi satisfaction_weight {satisfaction} + 0.10; "
                    "ini menggeser produk menjadi mesin hook (Pasal 4).",
                )
            )
        elif hook is not None and satisfaction is None and float(hook) > 0.20 + 0.10:
            rejections.append(
                Rejection(
                    11,
                    f"hook_weight {hook} melebihi satisfaction_weight default 0.20 + 0.10 (Pasal 4).",
                )
            )

    brief: NarrativeBrief | None = None
    if not rejections:
        try:
            brief = NarrativeBrief.model_validate(raw)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                rejections.append(Rejection(12, f"Ambiguitas pada field {loc}: {err['msg']}."))
        else:
            if not brief.title.strip():
                rejections.append(
                    Rejection(12, "title kosong; brief tanpa nama tidak dapat dilaporkan.")
                )
            if not brief.values_allowed and not brief.values_blocked:
                rejections.append(
                    Rejection(
                        12,
                        "values_allowed dan values_blocked keduanya kosong; arah nilai tidak jelas.",
                    )
                )
    return BriefReport(
        brief_id=brief_id, brief=brief if not rejections else None, rejections=rejections
    )


def load(briefs_dir: Path, brief_id: str) -> BriefReport:
    """Baca satu brief dari disk lalu validasi. Tidak pernah menulis apa pun."""
    path = brief_path(briefs_dir, brief_id)
    if not path.exists():
        return BriefReport(
            brief_id=brief_id,
            brief=None,
            rejections=[Rejection(12, f"brief {path.name} tidak ada di {briefs_dir}.")],
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return BriefReport(
            brief_id=brief_id,
            brief=None,
            rejections=[Rejection(12, f"YAML tidak valid: {exc}.")],
        )
    if not isinstance(raw, dict):
        return BriefReport(
            brief_id=brief_id,
            brief=None,
            rejections=[Rejection(12, "isi brief bukan mapping YAML.")],
        )
    if raw.get("id") != brief_id:
        return BriefReport(
            brief_id=brief_id,
            brief=None,
            rejections=[
                Rejection(12, f"id di file ({raw.get('id')!r}) tidak sama dengan nama file.")
            ],
        )
    return validate(brief_id, raw)


def load_or_raise(briefs_dir: Path, brief_id: str) -> NarrativeBrief:
    """Muat brief, lempar BriefRejected bila tidak lolos."""
    report = load(briefs_dir, brief_id)
    if not report.ok:
        raise BriefRejected(report)
    assert report.brief is not None
    return report.brief


def list_ids(briefs_dir: Path) -> list[str]:
    """Semua id brief dari nama file, urut abjad."""
    if not briefs_dir.exists():
        return []
    return sorted(p.stem for p in briefs_dir.glob("*.yaml") if not p.name.startswith("_"))
