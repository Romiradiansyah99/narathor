# Agents

Five roles, one graph, and the concurrency mechanism that governs them.

This document answers two questions that are usually left behind: **where the part that makes five agents work at once lives**, and **which framework is used**.

---

## 1. Framework

| Layer | Technology | Role |
|---|---|---|
| Role orchestration | **LangGraph `StateGraph`** | Five-node graph, shared state, conditional edges |
| Parallel fan-out | **LangGraph `Send`** | Dispatches N work units to the same node in parallel |
| Concurrency limit | **`max_concurrency`** in the invoke config | Enforces at most 5 units running at once |
| Durability | **LangGraph checkpointer** (synchronous) | Saves state after each node; resumes after a crash |
| Human approval | **LangGraph `interrupt()`** | Stops on a borderline Critic, continues after the boss decides |
| Supervisor | **LangChain `create_agent`** | Plans the work order, picks units, summarises |
| Tracing | **Langfuse** (optional) | One session per run, one span per role |
| Model | **Command Code Provider API** via LangChain | See `docs/MODELS.md` |

All model calls go through a LangChain chat model, never a CLI subprocess. Selection lives in `agent/models.py` and can be overridden per role through the environment.

---

## 2. The five roles

| Role | Scope | Input | Output | Model |
|---|---|---|---|---|
| **Curator** | channel + brief | `NarrativeBrief`, video list | `VideoSelection[]` + reasons | cheap LLM |
| **Indexer** | per video | `TranscriptDoc` | `Segment[]` + `kind` + features | **no LLM** |
| **Matcher** | per candidate thesis | `SegmentCard[]` across videos | `Combo[]` (2–5 segments, >=2 videos) | cheap LLM |
| **Writer** | per `Combo` | combo, full segments, brief, `CRAFT.md` | `ShortScript` + citations | LLM (see `MODELS.md`) |
| **Critic** | per `ShortScript` | script, transcript, soul, 7 gates | `Audit {gates, cites_ok, verdict, pressed[], reason}` | instruction-following LLM |

### 2.1 Curator

Decides which videos are in scope, and why. Assigns `niche_consistency_score` — how consistent a video's topic is with the brief's thesis.

This role matters more than the initial estimate. Because a script is built from what the source said, choosing the right library is the most influential craft decision, long before a single sentence is written.

### 2.2 Indexer

**Calls no model.** Transcript segmentation and feature computation are entirely heuristic:

- splitting on pauses > 0.8s and sentence markers
- filler detection (`jadi gini`, `apa ya`, `gimana ya`, `oke guys`)
- administrative opening detection (`sebelum itu`, `di video kali ini`)
- `kind`: thesis, story, number, rebuttal, close
- `key_quote` extraction per segment

Output: a compact `Segment` card of ~200 tokens, stored in the database. This is what makes 400 videos possible at all.

### 2.3 Matcher

Finds combinations. One work unit = one candidate thesis.

Rules that are enforced (not hoped for):

- at least 2 different videos
- no contradiction between segments
- one thesis
- order supporting claim → evidence → consequence → close
- source diversity is scored

### 2.4 Writer

Writes the full script on top of one `Combo`: hook, beats, payoff, overlay, title, caption.

Obligations:

- every `beat` with `is_claim: true` carries a `citation {video_id, t0, t1, quote}`
- `quote` must **actually exist** in the transcript across that range
- `hook` <= 7 words, first word before second 1
- `payoff_at_s` < 16 for the 13–20s target
- `overlay` <= 7 words per line
- mark what was **not** used (`discarded[]`)

### 2.5 Critic

Runs the seven gates from `docs/CRAFT.md` §6. One failure → return to the Writer. Two iterations maximum, then `interrupt()`.

The Critic also verifies citations independently. A Writer claiming a citation is valid is not trusted; the backend matches it, and the Critic checks whether the quotation is reasonable for the claim.

---

## 3. The graph

```
                    ┌────────────┐
                    │ supervisor │  (create_agent)
                    └──────┬─────┘
                           │ Send per unit
        ┌──────────┬───────┴────────┬───────────┐
        ▼          ▼                ▼           ▼
   ┌─────────┐ ┌────────┐     ┌────────┐  ┌────────┐
   │ curator │ │ index  │     │ match  │  │ write  │
   └────┬────┘ └───┬────┘     └───┬────┘  └───┬────┘
        │          │              │            │
        └──────────┴──────────────┴────────────┘
                           │
                    ┌──────▼─────┐
                    │  critique  │
                    └──────┬─────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           pass         return       interrupt
           (END)      (→ write)     (wait for boss)
```

The nodes `index`, `match`, `write`, and `critique` are `Send` targets. A single node can receive N units at once — this is where parallelism happens.

---

## 4. Concurrency — explicit specification

### 4.1 Fan-out

```python
# the supervisor decides units, it does not run a loop
sends = [Send("index", {"video_id": v}) for v in selected_videos]
```

No `for` waiting one by one. No hand-rolled `asyncio.gather`.

### 4.2 Limit

```python
graph.invoke(state, config={"max_concurrency": 5})
```

- Default **5**. Changeable: `--concurrency N` or `MAX_CONCURRENCY`.
- The backend rejects a `Send` that would push running units above the limit. This is an invariant, not a hope.
- A value of 0, negative, or infinite → rejected at startup.

**Why 5.** Enough to cover model latency, low enough to keep cost per minute in check, and small enough to keep logs readable while debugging.

### 4.3 Thread per unit

| Role | `thread_id` |
|---|---|
| Indexer | `{narrative_id}:{video_id}` |
| Matcher | `{narrative_id}:thesis-{n}` |
| Writer | `{narrative_id}:combo-{combo_id}` |
| Critic | `{narrative_id}:combo-{combo_id}` |

A stable thread means resume finds the same state. Writer and Critic share a thread because the Critic must see the iteration history.

### 4.4 Idempotency

Unit key:

```
unit_key = hash(unit_id, prompt_version, brief_hash, soul_version, craft_version)
```

A node re-run after a crash does not duplicate cost or data. An existing result with the same `unit_key` is returned from cache.

Deliberate consequence: **changing the soul or the brief invalidates the entire cache.** Scripts from a different constitution may not be reused as if they were valid.

### 4.5 Durability

The checkpointer saves state after every node. A run that is killed:

- continues from the last completed node
- does **not** increase `attempts`
- uses the same `thread_id`

Synchronous, not async. The async Postgres checkpointer does not work with Windows' default event loop.

### 4.6 Model call cap

| Role | Max calls per unit |
|---|---|
| Curator | 1 |
| Indexer | 0 |
| Matcher | 1 |
| Writer | 3 (write + max 2 revisions) |
| Critic | 1 |

Past the cap → the node fails in a controlled way. Not a loop, not a silent stop. Counted in the `agent_calls` table.

### 4.7 Retry

`ModelRetryMiddleware`, one retry for provider error or timeout. Two failures → the unit is marked `deferred`, the run continues. Deferred units are reported at the end and do not stop the run.

### 4.8 Failure isolation

One failing unit does not stop the run. The run finishes other units, then reports:

```
done: 27   returned: 2   deferred: 1
```

### 4.9 Deterministic merge

Results are merged sorted by `script_id`, not by arrival order. Two runs with the same input produce the same order.

---

## 5. Scale limits

400 videos × 1 hour ≈ **5 million tokens** of transcript. That does not fit in any 1M context, including the largest in the catalogue.

So matching is three-stage:

**Stage 1 — segment cards.** The Indexer produces ~200 tokens per segment, ~10 segments per video. 400 videos → ~800,000 tokens stored in the database, not in context.

**Stage 2 — thesis clusters.** Batches of 50 cards per call. A cheap model reads cards, not transcripts. Produces 30–50 candidate theses.

**Stage 3 — combo assembly.** For one thesis, take only relevant segments (by `topic` and `kind`). The Writer receives 2–5 full segments, not the whole library.

Without these three stages, the Matcher fails on a full context and cost explodes quadratically.

---

## 6. Invariants enforced by the backend

A prompt can be ignored by a model. An endpoint cannot.

| Invariant | When checked | Consequence of violation |
|---|---|---|
| Soul hash matches | Start of **every** agent request | 409, the agent stops |
| Brief valid, not ambiguous, not expired | Before a run is created | 400 + article |
| `values_blocked` does not leak | When saving a `ShortScript` | 400, script discarded |
| Every `is_claim` has a valid citation | When saving | 400, script rejected |
| `quote` actually exists in the transcript | When saving | 400, script rejected |
| `payoff_pays_off` | When saving | 400, returned to the Writer |
| Seven craft gates | When saving | 400, returned |
| No duplicate script | When saving | Idempotent, 200 |
| Concurrency <= limit | On `Send` | Unit rejected |
| Model call cap | Every call | Rejected, marked failed |

---

## 7. Testing without a model

Mandatory. No test calls a real model.

A stub model per role returns canned responses. What gets proven:

1. Fan-out produces N units matching the number of `Send`s.
2. `max_concurrency` is never exceeded — measured from concurrently running units in the log, not assumed.
3. Retry runs on provider error, then the unit becomes `deferred`.
4. `interrupt()` stops the graph and continues it on resume.
5. A failing unit does not stop the run.
6. The citation gate rejects a claim without a reference.
7. The distinctiveness gate rejects a script that could be swapped with another short.

Tests run without network. If a test needs network, that test is badly designed.

---

## 8. Not allowed

- Replacing the `Send` fan-out with a sequential loop.
- Running `max_concurrency` unbounded.
- Storing a result before the backend verifies citations.
- Letting the agent read `data/` or the database directly.
- Using different models between tests and production on the metric being compared.
- Creating a new worker outside the five roles without updating this document first.
- Deferring the soul check until after a script is written.

---

## 9. Relationship to other documents

| Document | Relationship |
|---|---|
| `SOUL.md` | Checked at the start of every request |
| `docs/CRAFT.md` | The seven gates the Critic runs |
| `docs/MODELS.md` | Model per role and how to override |
| `docs/NARRATIVE.md` | The brief the Curator and Writer read |
| `docs/TECH_STACK.md` | System parts and API |
| `docs/PLAN.md` | Build order |
