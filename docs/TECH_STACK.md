# Tech Stack

The shape of the system and the reasoning behind it. Versions, parts, and constraints.

---

## 1. System parts

```
narathor/     CLI (Typer). Thin: calls the backend, prints progress
backend/      FastAPI + SQLAlchemy Core. The only door to data
agent/        LangGraph. Five roles, fan-out, checkpointer
data/         Read-only. Video library, transcripts, eval key
prompts/      Prompt per stage, with prompt_version
output/       Artefacts from a run
briefs/       Narrative Brief owned by the boss
dashboard/    React + Vite + TS. Phase 2, not built
e2e/          Playwright. Phase 2, not built
```

**The backend is the only door to data.** The agent never reads `data/` or the database directly. It calls the API. This is what makes the invariants enforceable: soul check, citation gate, and the concurrency cap all go through the backend.

---

## 2. Python

Python 3.12, managed by `uv`. All dependencies in the root `pyproject.toml`.

| Library | Role | Why |
|---|---|---|
| `fastapi` | API backend | Lightweight, clear types, automatic OpenAPI |
| `sqlalchemy` (Core) | Database access | One query for SQLite and Postgres |
| `pydantic` v2 | Data contracts | Validation and JSON serialisation |
| `typer` | CLI | Typed arguments without boilerplate |
| `pyyaml` | Brief parsing | A human-readable brief format |
| `httpx` | HTTP client | Used by CLI and agent |
| `langchain` | `create_agent` | Supervisor and tool use |
| `langgraph` | `StateGraph`, `Send`, checkpointer, `interrupt()` | Per-role graph and durability |
| `yt-dlp` | Download audio/captions | Fallback when captions are unavailable |
| `youtube-transcript-api` | Fetch captions | Fast path, no download |
| `faster-whisper` | Transcript fallback | Optional; used only when captions are poor |
| `jinja2` | Report templates | `index.md`, script `.md` |
| `pytest` | Tests | Stub models, no network |
| `ruff` | Lint + format | One tool for two jobs |
| `pyright` | Type check | Strict |
| `langfuse` | Tracing | Optional, off when the key is absent |

**Rejected alternatives:**

- *Full ORM (Django, SQLModel)* — over-abstraction for simple queries. Core is enough.
- *Celery/Redis for workers* — fan-out is handled by LangGraph; adding a broker only adds parts that can break.
- *Paid Whisper API* — the local fallback is enough and adds no dependency.
- *Other agent frameworks* — `create_agent` + `StateGraph` covers the need; the reference project also uses this path.

---

## 3. Node & browser

| Library | Role | Status |
|---|---|---|
| Node 26 | Tooling runtime | In use |
| React + Vite + TS | Dashboard | Phase 2 |
| Playwright | E2E | Phase 2 |

TypeScript strict, no `any`. `package.json` scripts are written as `uv run` or `.mjs` files so they work on Windows.

---

## 4. Models

Summary; details in `docs/MODELS.md`.

| Role | Model | Cost per run |
|---|---|---|
| Indexer | no LLM | $0 |
| Curator, Matcher, Writer | `deepseek/deepseek-v4.1-flash` | ~$3.0 combined |
| Critic | `claude-haiku-5-5` | ~$0.1 |
| Eval | `stealth/crouton-alpha` | $0 |
| Writer backup | `claude-sonnet-5-5` | +$32 if enabled |

The Writer dominates ~84% of cost. Only the Writer model decision is economically significant.

---

## 5. Database

SQLite for development and tests; Postgres for real data.

- Tables in schema `narathor`.
- `MetaData(schema="narathor")` + `schema_translate_map={"narathor": None}` → unqualified queries that run on both.
- At most 4 connections per process.
- Tests never touch the network.
- The SQLite file can be deleted to reset; there is no migration code.

Core tables: `channels`, `videos`, `transcripts`, `segments`, `combos`, `scripts`, `citations`, `audits`, `runs`, `agent_calls`, `cache`.

---

## 6. API

Every operation must have an `operation_id`, a one-line docstring, and no optional inputs. Optional inputs hide behaviour and make tests harder.

Example:

```python
@app.get("/api/videos", operation_id="list_videos")
def list_videos():
    """List videos in the library."""
```

Summary:

| Method | Path | operation_id |
|---|---|---|
| GET | `/api/health` | `health` |
| GET | `/api/soul` | `get_soul_status` |
| GET | `/api/briefs` | `list_briefs` |
| GET | `/api/briefs/{brief_id}` | `get_brief` |
| GET | `/api/videos` | `list_videos` |
| GET | `/api/videos/{video_id}` | `get_video` |
| GET | `/api/segments` | `list_segments` |
| POST | `/api/runs` | `start_run` |
| GET | `/api/runs/{run_id}` | `get_run` |
| POST | `/api/runs/{run_id}/finish` | `finish_run` |
| POST | `/api/runs/{run_id}/fail` | `fail_run` |
| PUT | `/api/units/{unit_id}/result` | `record_unit_result` |
| POST | `/api/scripts` | `save_script` |
| GET | `/api/scripts/{script_id}` | `get_script` |

---

## 7. Environment

`.env` at the root, in `.gitignore`. `.env.example` holds variable names without values.

| Variable | Required | Default | Used in |
|---|---|---|---|
| `COMMAND_CODE_API_KEY` | yes | — | All model calls |
| `DATABASE_URL` | no | — | Postgres; without it, SQLite is used |
| `NARATHOR_DB` | no | `narathor.db` | SQLite path |
| `MODEL_WRITER` | no | `deepseek/deepseek-v4.1-flash` | Writer |
| `MODEL_MATCHER` | no | `deepseek/deepseek-v4.1-flash` | Matcher |
| `MODEL_CRITIC` | no | `claude-haiku-5-5` | Critic |
| `MODEL_CURATOR` | no | `deepseek/deepseek-v4.1-flash` | Curator |
| `MODEL_NAME` | no | — | Blanket override |
| `LANGFUSE_PUBLIC_KEY` | no | — | Tracing |
| `LANGFUSE_SECRET_KEY` | no | — | Tracing |
| `MAX_CONCURRENCY` | no | `5` | Fan-out |

**Note on a reference inconsistency.** `00. Plan Build References/TECH_STACK.md` writes `COMMANDCODE_API_KEY`, while `PLAN.md` writes `COMMAND_CODE_API_KEY`. What is used here: **`COMMAND_CODE_API_KEY`**, per the headless Command Code documentation. Do not use both names.

Without `LANGFUSE_*`, tracing is fully off. Tests never need network.

---

## 8. Windows constraints

Needed because the main development machine is Windows:

- All scripts go through `uv run` or `.mjs` files; no `python3`.
- Paths always via `pathlib.Path`. No manually concatenated path strings.
- Synchronous checkpointer. The async Postgres checkpointer does not work with Windows' default event loop.
- Explicit `utf-8` encoding when reading and writing files. The Windows default is not utf-8.
- PowerShell for command examples; `curl` as an alternative in notes, not an assumption.

---

## 9. Output

```
output/<narrative_id>/<channel>/
  scripts/<script_id>.json       contract for the render engine (Phase 2)
  scripts/<script_id>.md         human-readable version
  index.md                       all scripts, ordered by score
  blocked.md                     discarded segments + article violated
  segments.jsonl                 segment cards
  combos.json                    combos and their scores
  run.json                       soul_version, brief_hash, model per role, timings
```

An artefact without `run.json` may not be written. Without a trace, output cannot be reproduced.

### 9.1 Output of `narathor script`

This command does not print scripts to stdout. It writes artefacts and prints a summary:

```
narathor script --narrative cerdaskan-bangsa --count 30 --workers 5

run_2026-11-09T142233  cerdaskan-bangsa  @example
  unit: 30 requested   27 done   2 returned   1 deferred
  gate : one_thesis 27/27 · traceable 27/27 · paid 25/27
  cost : $2.61 (writer 84%)
  output: output/cerdaskan-bangsa/example/
```

Per-script detail is in `index.md`; failures are in the "returned" section of `index.md` with the failing gate and its reason.

Exit code: `0` when at least one script passes, `1` when all fail, `2` when the brief or the soul is rejected.

---

## 10. Checks

One command runs everything:

```bash
uv run check    # ruff format, ruff check, pyright, pytest --cov (min 80%)
```

Rule: never lower a threshold, disable a rule, or exclude a file to make it green. If a rule feels wrong, stop and ask.

Tests must use stub models. No test calls a real model, and no test reads `data/eval/`.
