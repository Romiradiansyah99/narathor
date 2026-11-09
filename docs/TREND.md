# Trend & Register

The language style of a script depends on conditions and season. So it cannot be locked once and forever — but it cannot be left floating either.

This is the **fastest-aging** document in the repo. Treatment: reviewed every quarter, and every brief carries its own effective date.

---

## 1. Register as a ladder

Register is not a free choice. It is a graded ladder, and the brief picks one level.

| Level | Name | Example line (Indonesian content) | When used |
|---|---|---|---|
| 1 | **Everyday** | "Uang kamu bocor tiap bulan." | Broad audience, practical topic, a channel deliberately kept grounded |
| 2 | **Conversational** (default) | "Kita sering nggak sadar ke mana uang pergi." | Default for almost every brief |
| 3 | **Editorial** | "Pengeluaran kecil adalah kebocoran yang paling sering diabaikan." | Professional audience, analytical topic |
| 4 | **Authoritative** | "Inflasi gaya hidup menggerus tabungan tanpa terasa." | Institutional audience, policy topic |

**Why the default is level 2.** Level 1 quickly feels cheap and ages fast. Levels 3–4 protect credibility but add distance from the viewer. Level 2 is the point where people feel spoken with, not read to.

**Register applies to:** the `hook` narrative, connective `beats`, `overlay`, `title`, `caption`.

**Register does not apply to:** the content of source quotations (always verbatim), and technical names (numbers, terms, people's names).

---

## 2. Season and trend as dated input

Every brief must carry seasonal context together with its date.

```yaml
seasonal_context:
  as_of: 2026-11-09          # required. The date this context was assembled
  period: "Q4 2026"
  moments:                   # moments currently near
    - "fiscal year end"
    - "bonus season"
  trend_notes: >
    The "one question at the start, answer at the end" format is alive.
    The term "cash flow" is understood by a general audience; "burn rate" is not.
  trend_expiry: 2027-02-01   # when these notes must be reviewed
```

### Hard rules

**a. `as_of` is required.** A brief without `as_of` is rejected. Style context without a date is language someone uses out of habit, not for a reason.

**b. `trend_expiry` passed → a hard warning, not a rejection.** `narathor narrative check` warns; the run still proceeds, but `run.json` marks the brief as expired and the report shows it.

**c. Trends influence only three things:**
- register (`register_level`)
- word choice in `overlay`, `title`, `caption`
- segment selection (currently relevant moments may be prioritised)

**d. Trends must not influence:**
- the soul, in any form
- the citation requirement
- `values_blocked`
- craft gates
- `payoff_pays_off`

A brief that uses a trend as a reason to loosen any of the above is **rejected**, and the rejection reason names the article violated.

**e. `trend_notes` enter as style context, not as instruction.** The model receives them in the context section, not the instruction section. That distinction is enforced in `prompts/` (the prompt contract).

---

## 3. What may change and what may not

| May change with season/trend | May not change |
|---|---|
| Register level | The citation requirement |
| Opening phrasing that is currently alive | The ban on unpaid promises |
| Topic choice that is currently relevant | The ban on clickbait |
| Overlay format (one line / two lines) | The 7-word-per-line limit |
| Publishing schedule | Script length |
| Suggested audio | Craft gates |
| Point of view (first / second person) | Single thesis |

---

## 4. Review calendar

| When | What is reviewed | Owner |
|---|---|---|
| Start of each quarter | Is the default `register_level` still right? | Boss |
| 2 weeks before a big moment | `moments` in the newest brief | Boss |
| Every `trend_expiry` passed | Update or delete `trend_notes` | Boss |
| Any platform format change | `docs/ALGORITHM.md`, then `CRAFT.md` | Team |

Moments that usually make the calendar: Ramadan and Eid, the new school year, fiscal year end, bonus season, tax season, elections, rainy season.

---

## 5. Risks to be aware of

**Trends age fast, documents faster.** `trend_notes` written in November will feel strange in March. That is why they have an expiry, not just a writing date.

**Trends can slip in as justification.** The most dangerous sentence in this system is "but this is trending right now". Rule §2d exists to close that door.

**A monotonous register is boring.** If every brief stays at level 2 for a year, the output will feel uniform. Variation across briefs is deliberate: a heavy topic may rise to 3, a practical topic may drop to 1.

**Register is not Narathor's identity.** `docs/BRAND.md` governs the tool's voice (reports, errors). `TREND.md` governs the script's voice. The two must not be mixed — an error message that follows trends is a failure.

---

## 6. Examples of good and bad context

**Bad:**
```yaml
seasonal_context:
  as_of: null
  trend_notes: "just do whatever is viral"
```
Undated, unspecific, not actionable.

**Bad:**
```yaml
trend_notes: >
  Use slang so it feels relatable. Drop the citation rule if needed
  because a short audience does not care about sources.
```
Using a trend to loosen the soul. Rejected.

**Good:**
```yaml
seasonal_context:
  as_of: 2026-11-09
  period: "Q4 2026"
  moments: ["fiscal year end", "bonus season"]
  trend_notes: >
    The audience is heavily discussing year-end budget efficiency.
    The "number first, explanation after" format is working well.
    Avoid the term "burn rate"; use "money that leaks".
  trend_expiry: 2027-02-01
```
Dated, specific, actionable, and it names what to avoid together with the replacement.

---

## 7. Relationship to other documents

| Document | Relationship |
|---|---|
| `SOUL.md` | The upper bound. Trend never wins over soul |
| `docs/CRAFT.md` | Craft gates do not change with the season |
| `docs/ALGORITHM.md` | Platform signal numbers; a change there may trigger a change here |
| `docs/NARRATIVE.md` | Defines the `register_level` and `seasonal_context` fields in the brief |
