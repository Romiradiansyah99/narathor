# Status

The state of the repo today. Updated at the end of every phase.

---

## Summary

Phases 1–6 complete and verified. Phases 7 and 8 partly done: what remains is waiting on a real library and a golden set.

`uv run check` is green: ruff, ruff format, pyright, 76 tests passing, 80% coverage.

---

## What exists

| Part | State |
|---|---|
| `SOUL.md` + `soul.lock` | v2 (English), hash matches |
| `contracts.py` | Every Pydantic contract in one place |
| `backend/` | FastAPI + SQLAlchemy Core, 8 endpoints, seeds from `data/`, soul gate on every request |
| `briefs/load.py` | YAML parser + twelve rejection reasons |
| `ingest/` | YouTube captions, Whisper fallback, per-video cache, run report |
| `index/` | Segmenter, heuristic features, kind classification, segment cards |
| `agent/` | LangGraph: plan, index, match, write, critique, seven gates |
| `report/render.py` | `scripts/*.md`, `*.json`, `index.md`, `blocked.md`, `run.json` |
| `eval/metrics.py` | Five metrics; the golden set is read only here |
| `narathor/` | Typer CLI: soul, narrative, ingest, index, mine, script, report, eval, doctor, status, check |
| `tools/build_site.py` | Static site generator for GitHub Pages |
| `tests/` | 76 tests, none calling a model or the network |
| `data/` | No real library yet. Tests use fixtures in `tests/fixtures.py` |

---

## Metrics

| Metric | Target | Now |
|---|---|---|
| Tests passing | all | 76 |
| Coverage | >= 80% | 80% |
| `pyright` | 0 errors | 0 |
| `ruff` | clean | clean |
| `citation_violation_rate` | = 0 | 0 on fixtures |
| `soul_violation_rate` | = 0 | 0 on fixtures |
| `precision@10` | >= 0.6 | not measured, no golden set |
| Cost per run (30 scripts) | <= $5 | not measured, needs a real library |

---

## Writer comparison

Not run. Waiting on a golden set and 10 identical `Combo`s.

| Date | Candidate | Backup | Winner | Decision |
|---|---|---|---|---|
| - | `deepseek/deepseek-v4.1-flash` | `claude-sonnet-5-5` | - | Not tested |

---

## Soul Compliance Log

| Date | Soul version | `soul verify` | Scripts discarded | Note |
|---|---|---|---|---|
| 2026-11-09 | 1 | ok | - | Soul v1 ratified in Indonesian |
| 2026-11-09 | 2 | ok | - | Translated to English; seven articles preserved in meaning. Text of v1 remains in git history at `8f4c140` |

---

## Decision Log

| Date | Decision | Reason | Impact |
|---|---|---|---|
| 2026-11-09 | Data contracts live in `contracts.py` at the repo root | Backend, agent, and CLI need the same schema; one place stops the schema branching | Every module imports from here |
| 2026-11-09 | `data/` layout: `channel.json`, `videos.json`, `transcripts/<video_id>.json` | `docs/` did not specify the library shape; this is the simplest form that fits `TranscriptDoc` | The backend seeds from here and never writes back |
| 2026-11-09 | Soul gate as a FastAPI dependency, not middleware | Dependencies are testable and appear in OpenAPI; middleware hides ordering | Every endpoint returns 409 when the hash does not match |
| 2026-11-09 | Writer retries happen inside the node, not via a back-edge | A back-edge into the `Send` fan-out node is not cleanly supported in LangGraph | `attempts` recorded per combo, `deferred` after two tries |
| 2026-11-09 | `critique` also performs the second iteration | Keeps the graph acyclic and testable without a model | Two iterations maximum, then `deferred` and reported |
| 2026-11-09 | Deterministic `brand_fit` using word overlap with light stemming | The anchor in `NARRATIVE.md` still applies; this is the stand-in before a model is called | Threshold 0.12 for score 5, 0.05 for score 3 |
| 2026-11-09 | Coverage measured with `omit = ["data/*", "tests/*"]` | The pattern `*/data/*` also cut the whole repo because the repo lives under `/opt/data` | Coverage reads correctly at 80% |
| 2026-11-09 | Soul v1 → v2: translation to English | The constitution must be readable in the repo's language; meaning of all seven articles preserved | Every cached artefact invalidated; nothing in production yet |
| 2026-11-09 | `soul bump` and `soul verify` bypass the implicit soul check in the CLI | A deliberate change could otherwise never be ratified, because every command halts on mismatch | The ceremony stays reachable while the hash is broken |

---

## Active risks

| Risk | State |
|---|---|
| A cheap Writer produces flat prose | Not measured; needs a golden set and a real model |
| The `data/` library is still empty | Waiting for the boss to name the first channel |
| No golden set | Must be labelled by a human, 10-20 moments per brief |
| LangGraph `interrupt()` is not wired | The second iteration falls through to `deferred` instead of waiting for the boss |
| Resume after a kill is untested | Checkpointer is `MemorySaver`; no crash-resume test yet |
| Function-level docstrings are still Indonesian | Module docstrings and CLI messages are English; ~200 function docstrings remain |
| `review Feb 2027` for `ALGORITHM.md` | Outside code control |

---

## Open questions

1. **First channel.** The example brief uses `@example`. Which real channel for the first run?
2. **Golden set.** Who labels 10-20 worthwhile moments per brief?
3. **Montage.** `output.montages` is 0 in every brief. MVP or a later phase?
4. **Second language.** `output.language` is only `id`. Is `en` needed?

---

## How to run

```bash
uv sync --extra dev
uv run narathor soul verify
uv run narathor doctor
uv run narathor narrative check cerdaskan-bangsa
uv run narathor ingest --narrative cerdaskan-bangsa
uv run narathor index  --narrative cerdaskan-bangsa
uv run narathor mine   --narrative cerdaskan-bangsa --top 50
uv run narathor script --narrative cerdaskan-bangsa --count 30 --concurrency 5
uv run narathor report --narrative cerdaskan-bangsa
uv run narathor eval   --narrative cerdaskan-bangsa
uv run narathor check
```
