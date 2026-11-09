# Brand

The identity of **Narathor as a tool**. Not the identity of the narrative it produces — that belongs to the boss's `NarrativeBrief`.

These two identities must not be mixed. Narathor has a calm, steady voice; the narrative may change style with the brief and the season.

---

## Position

Narathor is not a virality tool. Narathor is a **tool for moving understanding** — it takes what people worth hearing have already said, and reassembles it so that others genuinely understand.

That is why Narathor's voice does not sell. It explains.

---

## Fonts

From Google Fonts:

- **Headings** — Fraunces
- **Body and UI** — Inter
- **Accent** (tagline or quotation) — Fraunces Italic
- **Code, numbers, identifiers** — JetBrains Mono

Fraunces carries weight at display sizes. Inter keeps tables, forms, and long text calm and quick to read. JetBrains Mono keeps timestamps, scores, and `script_id` from ever being mistaken for prose.

---

## Colour

- **Primary** — Cobalt `#1F4FD8`, white text
- **Secondary** — Steel `#5C7DA8`, white text
- **Tertiary** — Mist `#C8D4E4`, Midnight text
- **Information** — Azure `#2F80ED`, white text
- **Warning** — Ember `#C2413B`, white text
- **Ink on light** — Midnight `#0D1117`
- **Ink on dark** — Fog `#C9D2DD`
- **Muted text** — Slate `#5A6573`

Use Cobalt, Steel, and Mist when three things sit side by side — script status or a chart series, for example. Azure fourth, Ember fifth. **Ember is for warnings only**, never for a data series.

Cobalt for actions, links, and headings. Midnight body on light, Fog on dark, Slate for secondary text. Never set Cobalt as small body text on white.

---

## Surfaces

- **Light mode** — background `#F3F5F7`, white panels and cards
- **Dark mode** — background `#090B0F`, panels and cards `#15191F`

Panels are softly rounded with no borders. Cool palette: no warm greys, and never more than one blue competing with Cobalt on a single screen.

---

## Avoid

- A border on one side of a panel, or a thin rule across the top of a page
- Heavy gradients
- Pure black `#000000` — Midnight is the darkest ink, and dark backgrounds stop at `#090B0F`
- Emoji in the interface, reports, or error messages

---

## Tone

English, short sentences, no unexplained jargon, no exclamation marks.

**What Narathor does when it speaks:**

| Context | Good | Bad |
|---|---|---|
| Report | "30 scripts passed the gates. 4 returned because the payoff does not pay the hook." | "Yay! 30 scripts made successfully! 🔥" |
| Soul error | "SOUL.md changed. Hash does not match soul.lock. Run soul verify after checking the diff." | "Oops! Something went wrong." |
| Filename | `script_tr_2026-11-09_007.json` | `BEST_SCRIPT_FINAL_v2.json` |
| Brief rejected | "Rejected: Article 4. The hook promises a number that never appears in the payoff." | "The brief isn't very good." |

**Message rule:** say what happened, say what to do about it, do not entertain.

---

## Where the two identities divide

| Narathor's (fixed) | The boss's (changeable) |
|---|---|
| Voice of reports and error messages | Narrative style of the script |
| Colour, font, surfaces | Language register (ladder 1–4) |
| How gates are explained | Choice of thesis and topic |
| The ban on clickbait | Channel selection |
| `run.json` format | Overlay and title |
| File naming | Season and trends used |

When in doubt: **Narathor never changes style. The narrative always may.**

---

## Brand promise

Four things must be true in every output:

1. **Traceable** — every fact has a timestamp.
2. **Paid** — the hook is always honoured.
3. **Readable** — understandable in one listen.
4. **Open** — no paywall.

If even one is false, it is not a Narathor output.

---

## Name

**Narathor.** One word, capitalised, never abbreviated, never hyphenated.

Channel names, theses, and scripts do not use the Narathor name as a brand — Narathor is the tool, not the publisher. What appears in public is the boss's channel.

---

## Static viewer

The GitHub Pages viewer produced by `tools/build_site.py` is a deliberate exception to everything above. It is not product UI. It is a printed readout of the engine, so it takes the form of a machine transcript instead of a dashboard:

- **One typeface** — Courier Prime, regular and bold, italic only for quotations. No second voice.
- **No colour** — pure black `#000000`, white, and two greys. Nothing else. The palette rule above does not apply here.
- **Rules instead of panels** — hairlines, dotted leaders, square brackets, and block meters. No rounded corners, no gradients, no shadows.
- **Machine idiom** — `$` and `>` prefixes, a block cursor, `HH:MM:SS` timecodes, an `EOF` terminator.

A readout that looks like the machine wrote it is more trustworthy than one that looks designed. Keep it that way, and do not import Cobalt into it.
