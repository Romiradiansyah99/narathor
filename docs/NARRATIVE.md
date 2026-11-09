# Narrative Brief

The contract that steers Narathor. The brief belongs to the boss — it is the only place content direction is decided.

The tool is neutral. The direction lives here.

---

## 1. Where the brief sits in the hierarchy

```
L0  SOUL.md + soul.lock      ← nobody can change it
L1  docs/BRAND.md            ← tool identity, fixed
L2  briefs/<id>.yaml         ← owned by the boss, bounded by L0 and L1
```

A brief cannot loosen the soul. The validator checks that before a run starts, not after.

---

## 2. Location and naming

```
briefs/<narrative_id>.yaml
```

`narrative_id` uses lowercase letters, digits, and hyphens. Examples: `cerdaskan-bangsa`, `literasi-utang-2027`.

Every brief has its own output folder: `output/<narrative_id>/<channel>/`. Two different briefs on the same channel never share artefacts.

---

## 3. Full schema

```yaml
id: cerdaskan-bangsa
title: "Making the nation smarter through useful attention"

# --- Required: what the audience understands after watching ---
learning_outcome: >
  The viewer understands that personal finance problems are rarely about
  the size of income, and more often about the direction of flow.

# --- Thesis: one idea that unites every script ---
thesis: >
  Attention is a limited asset. Content worth watching leaves one whole
  idea behind, not just an emotional jolt.

# --- Audience ---
audience:
  primary: "Indonesia, 18-35, short-form native, no foundation yet"
  literacy_level: menengah
  pain_points:
    - "feels like they already know, but results never change"
    - "easily baited by provocative titles"

# --- Values: what may and may not appear ---
values_allowed:
  - kejujuran_intelektual
  - kerja_keras_tanpa_shortcut
  - tanggung_jawab_personal
  - literasi_finansial_yang_sehat
values_blocked:
  - janji_kaya_instan
  - membenci_kelompok
  - pseudosains
  - manipulasi_emosi_untuk_engagement

# --- Style ---
register_level: 2            # 1..4, see docs/TREND.md
tone:
  target: "firm, clear, never preachy"
  avoid:
    - "preaching"
    - "begging for attention"

# --- Season ---
seasonal_context:
  as_of: 2026-11-09          # REQUIRED
  period: "Q4 2026"
  moments: []
  trend_notes: ""
  trend_expiry: null

# --- Sources ---
sources:
  channels:
    - "https://www.youtube.com/@example"
  recency_preference: any    # any | recent | classic
  min_duration_s: 180

# --- Output shape ---
output:
  scripts: 30
  target_duration_s: 15      # 13..20 or 60
  language: id
  montages: 0

# --- Score tuning (optional) ---
scoring_overrides:
  brand_fit_weight: 0.05
```

---

## 4. Semantics of each field

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Brief identity. Must not collide with another brief. |
| `title` | yes | Human name. Appears in reports. |
| `learning_outcome` | **yes** | One sentence of understanding. Without it, the brief is rejected (Articles 1 and 2). |
| `thesis` | yes | One idea uniting every script in this run. |
| `audience.primary` | yes | Who. Specific, not "everyone". |
| `audience.literacy_level` | yes | `rendah` / `menengah` / `tinggi`. Affects how terms are explained. |
| `audience.pain_points` | no | The audience's real problems. Helps the Matcher pick relevant segments. |
| `values_allowed` | yes | Values that may appear. May be empty only if `values_blocked` is filled. |
| `values_blocked` | yes | Values discarded permanently. May be empty. |
| `register_level` | yes | 1–4, see `docs/TREND.md`. |
| `tone.target` | yes | One phrase. Example: "firm, clear, never preachy". |
| `tone.avoid` | no | What to avoid in style. |
| `seasonal_context.as_of` | **yes** | The date this context was assembled. |
| `seasonal_context.trend_expiry` | no | When these trend notes must be reviewed. |
| `sources.channels` | yes | At least one channel URL. |
| `sources.recency_preference` | yes | `any` / `recent` / `classic`. |
| `sources.min_duration_s` | no | Filters out videos that are too short. Default 180. |
| `output.scripts` | yes | How many scripts are requested. |
| `output.target_duration_s` | yes | 13–20 or 60. The value 30 is rejected unless in experimental mode. |
| `output.language` | yes | `id` for now. |
| `output.montages` | no | 0 = produce no montage. |
| `scoring_overrides` | no | Weight tuning. See §6. |

---

## 5. The `brand_fit` anchor

`brand_fit` is how well a segment matches the brief. It is judged against anchors, not taste — so that two different briefs produce measurably different rankings.

**Score 5** — the segment directly serves the `learning_outcome` or `thesis`, and does not touch a single `values_blocked`.

> Example: the segment discusses a leak in small spending, while the brief holds that the problem is the direction of flow.

**Score 3** — the segment is relevant to the topic but does not directly serve the thesis; useful as evidence or context.

> Example: the segment contains a consumption statistic, with no argument about flow.

**Score 1** — the segment is about an entirely different topic; connected only by loose association.

**Score 0** — the segment touches one of the `values_blocked` → **permanent drop**, `total` is ignored.

Rule: a `brand_fit` below 3 on a strict brief → the segment does not enter a combo.

---

## 6. `scoring_overrides`

Only these fields may be changed, within bounds:

| Field | Default | Bounds |
|---|---|---|
| `brand_fit_weight` | 0.05 | 0.00–0.30 |
| `satisfaction_weight` | 0.20 | 0.10–0.35 |
| `hook_weight` | 0.25 | 0.15–0.30 |

**Anti-shift rule:** `hook_weight` may not exceed `satisfaction_weight + 0.10`. The purpose is to stop a brief turning the product into a hook machine — that is a violation of Article 4.

`length_fit` is not a weight. It is a gate and cannot be overridden.

---

## 7. Why a brief is rejected

Twelve conditions. Each names the basis for its rejection.

| # | Condition | Basis |
|---|---|---|
| 1 | `learning_outcome` empty or missing | Articles 1, 2 |
| 2 | `thesis` empty | Nothing unites the scripts |
| 3 | `seasonal_context.as_of` empty | Style without a date cannot be accounted for |
| 4 | `values_blocked` collides with `values_allowed` | Internal contradiction |
| 5 | `values_blocked` contains a value the soul mandates | Articles 3, 4, 6 |
| 6 | `tone` or `trend_notes` asks to loosen citations | Article 5 |
| 7 | `tone` or `trend_notes` asks to forgive clickbait | Article 4 |
| 8 | `target_duration_s` = 30 without experimental mode | `docs/ALGORITHM.md` §4 |
| 9 | `sources.channels` empty or invalid | No material |
| 10 | `register_level` outside 1–4 | `docs/TREND.md` §1 |
| 11 | `scoring_overrides` beyond the bounds in §6 | Anti-shift |
| 12 | **Ambiguity** — the validator cannot establish that the brief passes or violates | Fail-closed |

**On number 12.** This is a deliberate decision. A brief that is not clear is safely treated as unsafe. No quarantine, no "passed with a warning", no human review that delays. An ambiguous brief is rejected, the reason names which part is ambiguous, and the boss fixes it.

The reason: a quarantine path always becomes a shortcut. If there is a way to pass a brief that is not clear, people will use it.

---

## 8. Behaviour on rejection

- Exit non-zero.
- Reason printed to stderr, naming the condition number and the article.
- **No artefacts** written to `output/`.
- **No generative model calls** after the rejection.

Example output:

```
Brief "cerdaskan-bangsa" rejected.

[12] Ambiguity in field values_blocked:
     "content that is too careful" cannot be mapped to any value.
     Clarify it, or remove it.

[5] Violation of Article 4:
     tone.target contains "make them curious until the end".
     This asks to delay the payoff.

No artefacts written.
```

---

## 9. Two complete examples

### 9.1 A strict brief

```yaml
id: literasi-utang-2027
title: "Debt literacy without fear-mongering"

learning_outcome: >
  The viewer understands the difference between debt that builds and debt
  that erodes, and can name one sign that applies to them.

thesis: >
  Debt is not morality, it is mathematics and time. What is dangerous is
  debt used to cover debt.

audience:
  primary: "Indonesia, 22-40, has active instalments"
  literacy_level: menengah
  pain_points:
    - "instalments grow but life does not feel better"

values_allowed:
  - kejujuran_intelektual
  - tanggung_jawab_personal
values_blocked:
  - janji_kaya_instan
  - manipulasi_emosi_untuk_engagement
  - menyalahkan_korban

register_level: 2
tone:
  target: "calm, clear, never judgemental"
  avoid: ["fear-mongering", "preaching"]

seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: ["fiscal year end"]
  trend_notes: "The audience responds to concrete numeric examples, not general advice."
  trend_expiry: 2027-02-01

sources:
  channels: ["https://www.youtube.com/@example"]
  recency_preference: any
  min_duration_s: 300

output:
  scripts: 20
  target_duration_s: 15
  language: id
  montages: 0
```

**Why it is strict:** `values_blocked` carries three things financial content violates easily. `tone.avoid` forbids the two most common approaches. `learning_outcome` demands a result measurable in the viewer.

### 9.2 A loose brief

```yaml
id: sains-sehari-hari
title: "The science in your kitchen"

learning_outcome: >
  The viewer understands one scientific principle that explains something
  they do every day.

thesis: >
  Science is not a school subject, it is an explanation of what is already ordinary.

audience:
  primary: "Indonesia, 15-30, high curiosity"
  literacy_level: rendah

values_allowed: [kejujuran_intelektual]
values_blocked: [pseudosains]

register_level: 1
tone:
  target: "casual, concrete"
  avoid: ["preaching"]

seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: []
  trend_notes: ""
  trend_expiry: 2027-02-01

sources:
  channels: ["https://www.youtube.com/@example-2"]
  recency_preference: any

output:
  scripts: 40
  target_duration_s: 15
  language: id
```

**Why it is loose:** only one value is blocked (`pseudosains` — an absolute limit), the lowest register, free tone. But `learning_outcome` is still required: the looseness is in style, never in purpose.

---

## 10. Three causal tests that must pass

Three things that prove the brief is actually used, not ignored:

1. **Change the brief, the ranking changes.** Two different briefs on the same channel must produce measurably different segment orders.
2. **A brief violating the soul → rejected with no artefacts.**
3. **A value in `values_blocked` → the segment disappears from the index and appears in `blocked.md`** with the article it refers to.

If any one of these fails, the brief is not really being read by the system — and this whole document is decoration.

---

## 11. Not allowed

- Putting themes, channels, or values in code. Everything goes through the brief.
- Copying one brief for every need and changing it slightly. Every change of direction is a new brief with a new `id`.
- Treating `trend_notes` as an instruction.
- Adding fields outside the schema without updating this document first.
- Treating `learning_outcome` as a formality. It is the reason the run exists.
