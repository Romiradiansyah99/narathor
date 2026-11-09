# Plan

The build plan for Narathor. Ticked only when verified. What stays empty is waiting on a real library or a decision from the boss.

Following `docs/PROCESS.md`: every phase has success criteria you can verify yourself. Tick when passing, update `docs/STATUS.md`, then commit.

---

## What is being built

An engine that works on the video library of one channel and produces short scripts: indexing segments, combining segments from different videos into one arc, writing the full script, and judging its own work.

Output: **scripts and timestamps**, not video.

---

## Architecture

```
                    ┌──────────────────────────────┐
                    │  CLI  uv run -m narathor     │
                    └──────────────┬───────────────┘
                                   │ HTTP JSON
┌──────────────┐        ┌──────────▼───────────┐        ┌──────────────┐
│ data/ (read  │─seed──►│  backend/            │◄──────►│ SQLite /     │
│  only)       │        │  FastAPI + SQLAlchemy│        │ Postgres     │
└──────────────┘        └──────────▲───────────┘        └──────────────┘
                                   │ the only door
                        ┌──────────┴───────────┐
                        │  agent/              │
                        │  LangGraph           │──► Command Code Provider API
                        │  supervisor + 5 roles│──► Langfuse (optional)
                        └──────────────────────┘
```

The backend is the only door to the data. The agent calls the API; it never reads `data/` and never touches the database.

---

## Data and state

- `data/` is read-only. The backend seeds it into the database on first run.
- `data/eval/` is never opened by the agent, tests, or tooling. Only `narathor eval`.
- The database stores state that changes: segments, combos, scripts, audits, runs, model calls.
- The SQLite file can be deleted to reset. There is no migration code.

### Work unit status

| Status | Meaning |
|---|---|
| `pending` | Not started |
| `running` | In progress |
| `done` | Finished, result stored |
| `returned` | Returned by the Critic, awaiting iteration |
| `deferred` | Failed twice, reported at the end |
| `blocked` | Discarded for a soul or forbidden-value violation |

---

## Phases

### Phase 1: Read-side backend

Build the foundation: database, seed, and read endpoints.

- `backend/db.py`: SQLAlchemy Core, schema `narathor`, seed from `data/` when tables are empty.
- Tables: `channels`, `videos`, `transcripts`.
- Endpoints: `/api/health`, `/api/soul`, `/api/briefs`, `/api/briefs/{id}`, `/api/videos`, `/api/videos/{id}`.
- Every operation has an `operation_id`, a one-line docstring, and no optional inputs.
- Temporary database fixture for tests.

**Success criteria:**

- [x] `uv run pytest backend -q` passes, with no model calls.
- [x] `GET /api/videos` returns every video from `data/`, with `video_id`, `title`, `duration_s`.
- [x] `GET /api/videos/VID-9999` returns 404 with a message naming the id requested.
- [x] `GET /api/soul` returns `{version, sha256, ok}` and `ok: false` when `SOUL.md` changes by one byte.
- [x] Deleting the SQLite file and restarting re-seeds.

---

### Phase 2: Soul and brief enforcement

Build constitutional enforcement and brief validation. This comes before any feature that calls a model.

- `soul/verify.py`: hash check, `SoulCheck`.
- `narathor soul verify`, `narathor soul bump`.
- `soul check` runs implicitly at the start of every backend request.
- `briefs/load.py`: YAML parser + schema validation.
- Two-layer validator: deterministic rules, then Soul Guard layer B (model judge).
- `narathor narrative new`, `narathor narrative check`.

**Success criteria:**

- [x] Changing `SOUL.md` by one byte → every endpoint returns 409, no artefact written.
- [x] `soul bump` raises `version` and moves the old hash into `previous_versions[]`.
- [x] A brief without `learning_outcome` → 400, the message names the field.
- [x] A brief without `seasonal_context.as_of` → 400.
- [x] A brief with `values_blocked` colliding with `values_allowed` → 400.
- [x] An ambiguous brief → 400 with a reason naming the ambiguous part.
- [x] A brief violating Article 4 (`tone` asking to delay the payoff) → 400 naming the article.
- [x] A valid brief passes all three layers.
- [x] No artefacts in `output/` after a rejection.

---

### Phase 3: Library ingest

Fetch transcripts for every video in the library.

- `ingest/captions.py`: `youtube-transcript-api`, the fast path.
- `ingest/whisper.py`: `faster-whisper`, the fallback when captions are missing or poor.
- Normalises to `TranscriptDoc {video_id, language, source, segments[]}` with `Segment {t0, t1, text, words[]}`.
- Transcript cache keyed by `video_id` + audio hash.

**Success criteria:**

- [ ] The first five videos have transcripts with per-segment timestamps.
- [ ] Re-running without `--force` produces a cache hit: no re-download, no re-transcription.
- [x] A video without captions uses Whisper, and `source: "whisper"` is recorded.
- [x] A video whose audio cannot be downloaded is marked `skipped` in `run.json`, the run continues.
- [x] `run.json` records `source` per video and total ingest time.

---

### Phase 4: Indexer

Segmentation and features, without an LLM.

- `index/segmenter.py`: split the transcript on pauses > 0.8s and sentence markers.
- `index/features.py`: `filler_positions`, `dead_air_spans`, `has_setup_preamble`, `word_count`, `wpm`, `hook_archetype` (initial heuristic), `payoff_present`, `niche_consistency_score`.
- `index/kinds.py`: classify `kind` — thesis, story, number, rebuttal, close.
- Store a ~200 token `Segment` card in the `segments` table.

**Success criteria:**

- [x] No segment longer than 70 seconds or shorter than 4 words.
- [x] Fillers `jadi gini`, `apa ya`, `oke guys` are detected in a test transcript.
- [x] A segment opened with `sebelum itu` gets `has_setup_preamble: true` and a measured penalty.
- [x] Average segment card size <= 250 tokens.
- [x] `uv run pytest index -q` passes without network.

---

### Phase 5: Matcher and concurrency

Build the supervisor, the `Send` fan-out, and the Matcher.

- `agent/graph.py`: `StateGraph`, nodes `curator`, `index`, `match`.
- Fan-out via `Send` per unit.
- `max_concurrency` from config; the backend rejects units above the limit.
- `agent/matcher.py`: assemble a `Combo` from `SegmentCard[]`.
- `agent/state.py`: shared state, idempotent per `unit_key`.

**Success criteria:**

- [x] Stub test: N videos produce N `index` units that run.
- [x] The number of units running at once never exceeds `max_concurrency` — measured from the log, not assumed.
- [x] `--concurrency 3` lowers the limit and is proven in the log.
- [x] Every `Combo` contains at least 2 distinct `video_id`; a single-video combo is rejected.
- [x] A combo with mutually contradicting segments is rejected whole, not one side picked.
- [x] One failing unit does not stop the run; the run finishes the other units.
- [x] Retry runs on provider error; two failures → `deferred`.
- [x] `uv run pytest agent -q` passes without calling a model.

---

### Phase 6: Writer

Write the full script with citations.

- `agent/writer.py`: prompt with the brief, full segments, few-shot from `docs/CRAFT.md`.
- Output a `ShortScript` matching the schema.
- Every `is_claim: true` must carry a `citation`.
- The backend matches `quote` against the transcript before storing.
- `discarded[]` must be filled.

**Success criteria:**

- [x] 30 `ShortScript` valid against the schema.
- [x] Every `beat` with `is_claim: true` has a `citation` with four fields.
- [x] `quote` in every citation is found in the transcript across `t0..t1`.
- [x] A claim without a citation → 400, the script is not stored.
- [x] `hook` <= 7 words on every script that passes.
- [x] `payoff_at_s` < 16 for the 13–20s target.
- [x] `overlay` <= 7 words per line.
- [x] `single_minded_proposition` is summarisable in one sentence.

---

### Phase 7: Critic, durability, and eval

Seven gates, a checkpointer, and measurement.

- `agent/critic.py`: seven gates, output an `Audit`.
- A failed gate → `returned` to the Writer, at most 2 iterations.
- Past 2 iterations → `interrupt()`.
- Synchronous checkpointer; resume after a kill.
- `eval/`: golden set, `precision@10`, `citation_violation_rate`, `soul_violation_rate`, `craft_pass_rate`, `hook_payoff_violation_rate`.

**Success criteria:**

- [x] A generic script (passing the swap test) is returned by the Critic, not accepted.
- [x] A script whose payoff does not pay the hook is returned.
- [ ] After 2 failed iterations the graph stops and waits for the boss's decision.
- [ ] A run killed mid-way and re-run resumes from the last node, `attempts` unchanged, `thread_id` the same.
- [x] `narathor eval` outputs all five metrics.
- [x] `narathor eval` produces `citation_violation_rate = 0` and `soul_violation_rate = 0` on the golden set.
- [x] Eval tests use `stealth/crouton-alpha` or a stub, never a paid model.

---

### Phase 8: CLI, Writer comparison, handover

- `narathor init`, `doctor`, `ingest`, `index`, `mine`, `script`, `report`, `eval`, `status`.
- `narathor doctor`: check the API key, database, soul, model versions.
- Reports `index.md`, `blocked.md`, `run.json`.
- The Writer A/B protocol from `docs/MODELS.md` §6 run on 10 scripts.

**Success criteria:**

- [x] `narathor doctor` reports five checks with clear status.
- [ ] A full run over a 25-video channel produces scripts, `index.md`, and `run.json`.
- [x] `run.json` carries `soul_version`, `brief_hash`, model per role, estimated cost.
- [ ] `blocked.md` carries the discarded segments along with the article violated.
- [ ] The Writer A/B table is filled in `docs/STATUS.md`, with the decision and its reasoning.
- [x] `uv run check` is green with `.env` moved aside.
- [x] `git status` is clean.

---

## Out of scope

Written here so it is not done without being asked:

- Web dashboard.
- Rendering `.mp4`, burning captions, cropping 9:16.
- Auto-posting to platforms.
- Login and multi-user.
- Cross-channel montage.
- Guaranteeing virality.

---

## Risks

| Risk | Mitigation |
|---|---|
| **A cheap Writer produces flat prose** | Few-shot in the prompt, a Critic with teeth, eval in phase 7, model swappable in one line |
| **The Matcher runs out of context on a large library** | Three-stage index; 200-token cards; retrieval per thesis |
| **Cost explodes on a 400-video library** | `unit_key` cache, cheap cache reads, a cap on model calls per unit |
| **Citations fabricated by the model** | The backend matches `quote` against the transcript; the Writer is not trusted |
| **A combo forced together to look clever** | Non-contradiction rule and one-thesis rule; a bad combo is discarded whole |
| **Two processes writing the same unit** | One agent process at a time; the checkpointer prevents overlap |
| **Windows: async checkpointer does not run** | Synchronous checkpointer |
| **`.env` leaks into tests** | Tests move `.env` aside; `uv run check` runs with `.env` moved |
| **The temptation to add a phrase blacklist** | Forbidden by the boss's decision; replaced by three signature tests |
