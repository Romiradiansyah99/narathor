"""Critic: tujuh gate. Deterministik dulu, model hanya bila perlu."""

from __future__ import annotations

import re

from contracts import (
    GATE_NAMES,
    Audit,
    GateResult,
    NarrativeBrief,
    ShortScript,
    TranscriptDoc,
)

CLICKBAIT = ("bikin penasaran", "tunggu sampai akhir", "jangan skip", "rahasia yang")
GENERIC = ("semua orang", "kebanyakan orang", "di era digital", "seiring berkembangnya")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3}


def _all_claims_cited(script: ShortScript) -> bool:
    return all(beat.citation is not None for beat in script.beats if beat.is_claim)


def _traceable(script: ShortScript) -> bool:
    return bool(
        script.script_id
        and script.combo_id
        and script.brief_id
        and script.single_minded_proposition
    )


def judge(
    script: ShortScript,
    brief: NarrativeBrief,
    transcript_lookup: dict[str, TranscriptDoc],
    quote_checker,
) -> Audit:
    """Jalankan tujuh gate dan kembalikan audit."""
    gates: list[GateResult] = []
    body = " ".join(
        [script.hook, script.title, script.caption, *(beat.text for beat in script.beats)]
    )
    lowered = body.lower()

    blocked = [value.replace("_", " ") for value in brief.values_blocked]
    hit_blocked = [value for value in blocked if value and value in lowered]
    gates.append(
        GateResult(
            name="values_clean",
            passed=not hit_blocked,
            reason="" if not hit_blocked else f"nilai terlarang muncul: {hit_blocked}",
        )
    )

    clickbait = [token for token in CLICKBAIT if token in lowered]
    soul_ok = not clickbait
    gates.append(
        GateResult(
            name="soul_compliance",
            passed=soul_ok,
            reason="" if soul_ok else f"Pasal 4: hook menjanjikan lebih dari payoff ({clickbait})",
        )
    )

    cites_ok = _all_claims_cited(script) and all(
        quote_checker(beat.citation) for beat in script.beats if beat.citation is not None
    )
    gates.append(
        GateResult(
            name="citation_integrity",
            passed=cites_ok,
            reason="" if cites_ok else "Pasal 5: klaim tanpa sitasi valid",
        )
    )

    hook_ok = len(script.hook.split()) <= 7
    payoff_ok = script.payoff_pays_off and (
        script.payoff_at_s < 16 if script.target_duration_s <= 20 else script.payoff_at_s < 55
    )
    gates.append(
        GateResult(
            name="hook_payoff",
            passed=hook_ok and payoff_ok,
            reason=""
            if hook_ok and payoff_ok
            else "hook terlalu panjang atau payoff tidak membayar",
        )
    )

    distinct = not any(token in lowered for token in GENERIC)
    distinct = (
        distinct and len({beat.citation.video_id for beat in script.beats if beat.citation}) >= 2
    )
    gates.append(
        GateResult(
            name="craft_distinctiveness",
            passed=distinct,
            reason="" if distinct else "uji tukar: naskah bisa dipakai brief lain tanpa berubah",
        )
    )

    brief_words = _words(f"{brief.thesis} {brief.learning_outcome}")
    script_words = _words(body)
    overlap = len(brief_words & script_words) / max(len(brief_words), 1)
    aligned = overlap >= 0.15
    gates.append(
        GateResult(
            name="brief_alignment",
            passed=aligned,
            reason="" if aligned else f"irisan dengan tesis brief terlalu rendah ({overlap:.2f})",
        )
    )

    gates.append(
        GateResult(
            name="traceability",
            passed=_traceable(script),
            reason="" if _traceable(script) else "Pasal 7: artefak tanpa jejak",
        )
    )

    pressed = [gate.name for gate in gates if not gate.passed]
    if not all(gate.passed for gate in gates):
        verdict = (
            "deny" if any(g.name == "values_clean" and not g.passed for g in gates) else "return"
        )
    else:
        verdict = "pass"
    return Audit(
        script_id=script.script_id,
        gates=gates,
        cites_ok=cites_ok,
        verdict=verdict,
        pressed=pressed,
        reason="; ".join(g.reason for g in gates if g.reason),
    )


def gate_names() -> tuple[str, ...]:
    """Nama tujuh gate, dalam urutan tetap."""
    return GATE_NAMES
