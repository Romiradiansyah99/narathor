# Narathor

A short-script assembly engine built on the video library of one YouTube channel.

Narathor takes hundreds of hours of material spoken by people worth hearing, and reassembles it into whole short scripts: one thesis, one arc, every fact traceable to the second it was said.

Not a video cutter. Not a virality tool. A tool for moving understanding.

---

## Three layers of authority

```
L0  SOUL.md + soul.lock     constitution — cannot be changed by brief, config, or flag
L1  docs/BRAND.md           tool identity — fixed
L2  briefs/<id>.yaml        content direction — owned by the boss, bounded by L0 and L1
```

Content direction is not embedded in code. It lives in a single file that can be swapped at any time without touching a line of program.

---

## Document map

| Document | Answers |
|---|---|
| [`SOUL.md`](SOUL.md) | What may not be violated, by anyone |
| [`docs/SOUL_GUARD.md`](docs/SOUL_GUARD.md) | How the soul is verified and changed |
| [`docs/SPEC.md`](docs/SPEC.md) | What this product is for, and its rules |
| [`docs/BRAND.md`](docs/BRAND.md) | How Narathor speaks and looks |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | System parts, versions, environment, Windows constraints |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Five roles, framework, concurrency mechanism |
| [`docs/ALGORITHM.md`](docs/ALGORITHM.md) | What the platform measures, and what is myth |
| [`docs/CRAFT.md`](docs/CRAFT.md) | Craft standard: combination, gates, three signature tests |
| [`docs/TREND.md`](docs/TREND.md) | Language register and seasonal context |
| [`docs/NARRATIVE.md`](docs/NARRATIVE.md) | The brief contract, and the reasons for rejection |
| [`docs/MODELS.md`](docs/MODELS.md) | Model per role, cost, how to swap them |
| [`docs/PROCESS.md`](docs/PROCESS.md) | How to plan, build, and hand over |
| [`docs/CODE_STANDARDS.md`](docs/CODE_STANDARDS.md) | Code rules |
| [`docs/PLAN.md`](docs/PLAN.md) | Build order and success criteria |
| [`docs/STATUS.md`](docs/STATUS.md) | State today, metrics, decisions |
| [`briefs/_template.yaml`](briefs/_template.yaml) | Brief template |

---

## Flow

```
Channel (400 videos)
  ├─ Curator   → which videos are in scope
  ├─ Indexer   → meaningful segments per video (no LLM)
  ├─ Matcher   → Combo: 2–5 segments from different videos, one thesis
  ├─ Writer    → full script + citation per claim
  └─ Critic    → seven gates; fail → returned
        ↓
  output/<narrative>/<channel>/
    scripts/*.md  scripts/*.json  index.md  blocked.md  run.json
```

---

## Quickstart

```bash
uv sync --extra dev
uv run narathor doctor
uv run narathor soul verify
```

A full run:

```bash
uv run narathor narrative check cerdaskan-bangsa
uv run narathor ingest --narrative cerdaskan-bangsa
uv run narathor index  --narrative cerdaskan-bangsa
uv run narathor mine   --narrative cerdaskan-bangsa --top 50
uv run narathor script --narrative cerdaskan-bangsa --count 30 --concurrency 5
uv run narathor report --narrative cerdaskan-bangsa
uv run narathor eval   --narrative cerdaskan-bangsa
```

---

## Golden rules

1. **Documents first, code second.** A behaviour change updates the spec first.
2. **The soul is not touched.** Only through an explicit `soul bump`.
3. **No themes in code.** Themes live in the brief.
4. **Facts must be traceable.** A claim without a citation → the script is rejected.
5. **No phrase blacklist.** Creativity is tested, not forbidden.
6. **Tests never call a model.**
7. **Never open `data/eval/`.** That is the answer key.

---

## What Narathor will never do

1. Publish a claim without a trace to its source.
2. Promise in the opening what the body does not deliver.
3. Hide that a source once said the opposite.
4. Make people pay to understand.

Those four are not negotiable policy. Three of them come from `SOUL.md`, and the fourth is the reason this product exists.

---

## Site

Scripts and their citations are published as a static site:

- https://romiradiansyah99.github.io/narathor/

Rebuilt after each run:

```bash
uv run python tools/build_site.py
git push origin master
# then copy the contents of site/ onto the gh-pages branch
```

GitHub Pages only serves files. The engine runs on your own machine through the CLI.

---

## Status

Phases 1–6 complete and verified; phases 7–8 partly done, waiting on a real library and a golden set. `uv run check` is green: ruff, pyright, 76 tests, 80% coverage.

See [`docs/STATUS.md`](docs/STATUS.md).

---

## License

Code is released under the MIT license. `SOUL.md` is the product's constitution: it may be read and quoted, but any redistribution of this system must keep it intact and hash-verified.
