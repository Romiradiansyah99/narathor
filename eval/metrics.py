"""Metrik eval. Golden set dibaca hanya oleh modul ini."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from contracts import Audit, ShortScript


@dataclass
class Metrics:
    """Lima metrik yang menentukan keputusan model."""

    precision_at_10: float = 0.0
    citation_violation_rate: float = 0.0
    soul_violation_rate: float = 0.0
    hook_payoff_violation_rate: float = 0.0
    craft_pass_rate: float = 0.0
    samples: int = 0
    notes: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Bentuk siap tulis ke laporan."""
        return {
            "precision_at_10": round(self.precision_at_10, 4),
            "citation_violation_rate": round(self.citation_violation_rate, 4),
            "soul_violation_rate": round(self.soul_violation_rate, 4),
            "hook_payoff_violation_rate": round(self.hook_payoff_violation_rate, 4),
            "craft_pass_rate": round(self.craft_pass_rate, 4),
            "samples": self.samples,
            "notes": self.notes,
        }


def precision_at_k(golden: list[str], predicted: list[str], k: int = 10) -> float:
    """Bagian dari k prediksi teratas yang ada di golden set."""
    if not golden or not predicted:
        return 0.0
    top = predicted[:k]
    hits = sum(1 for item in top if item in set(golden))
    return hits / min(k, len(top))


def rates(scripts: list[ShortScript], audits: list[Audit]) -> Metrics:
    """Hitung keempat tingkat pelanggaran dari naskah dan auditnya."""
    result = Metrics(samples=len(scripts))
    if not scripts:
        result.notes["empty"] = "tidak ada naskah untuk dinilai"
        return result
    by_id = {audit.script_id: audit for audit in audits}
    citation_bad = 0
    soul_bad = 0
    hook_bad = 0
    craft_bad = 0
    for script in scripts:
        audit = by_id.get(script.script_id)
        if audit is None:
            citation_bad += 1
            continue
        pressed = set(audit.pressed)
        if not audit.cites_ok or "citation_integrity" in pressed:
            citation_bad += 1
        if "values_clean" in pressed or "soul_compliance" in pressed:
            soul_bad += 1
        if "hook_payoff" in pressed:
            hook_bad += 1
        if "craft_distinctiveness" in pressed:
            craft_bad += 1
    total = len(scripts)
    result.citation_violation_rate = citation_bad / total
    result.soul_violation_rate = soul_bad / total
    result.hook_payoff_violation_rate = hook_bad / total
    result.craft_pass_rate = 1 - (craft_bad / total)
    return result


def read_golden(path: Path) -> list[str]:
    """Baca golden set. Hanya dipanggil oleh perintah eval."""
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("segment_ids", [])
    return [str(item) for item in payload]


def evaluate(scripts: list[ShortScript], audits: list[Audit], golden_path: Path) -> Metrics:
    """Gabungkan metrik golden set dan metrik run."""
    result = rates(scripts, audits)
    golden = read_golden(golden_path)
    predicted = [
        beat.citation.video_id for script in scripts for beat in script.beats if beat.citation
    ]
    result.precision_at_10 = precision_at_k(golden, predicted, 10)
    if not golden:
        result.notes["golden"] = f"golden set kosong di {golden_path}"
    return result
