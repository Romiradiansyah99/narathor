# Status

The state of the repo today. Updated at the end of every phase.

---

## Summary

Phases 1–6 complete and verified. Phases 7 and 8 partly done: what remains is waiting on a real library and a golden set.

`uv run check` is green: ruff, ruff format, pyright, 176 tests passing, 81% coverage.

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
| `tests/` | 176 tests, none calling a model or the network |
| `data/` | No real library yet. Tests use fixtures in `tests/fixtures.py` |

---

## Metrics

| Metric | Target | Now |
|---|---|---|
| Tests passing | all | 176 |
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
| 2026-11-10 | The console is a chat, not a three-step form | A form forces the writer to fill fields that do not matter yet; a conversation asks only what is missing and accepts a full brief in one message | `POST /api/chat` replaces the screen; the old form endpoints stay for the CLI's sake |
| 2026-11-10 | The chat reads a message with rules first, then a model | Rules are exact for URLs, handles, counts and durations and never fail; the model is only needed for topic and audience | `NARATHOR_CHAT_MODEL=off` still produces a working console |
| 2026-11-10 | The public page carries the name and one line, no demo scripts | Fixture output under the product's name reads as a result nobody asked for | `site/` no longer ships `scripts/`; the console is where output lives |
| 2026-11-10 | A failed run names the words the library actually uses | A lexical matcher cannot invent a topic; when zero scripts pass the gates the user needs to know what the transcripts talk about | `library_hints` in `backend/chat.py` |
| 2026-11-10 | The model is never called for a message the rules can settle | The provider takes 2 to 4 seconds to produce one word, so a URL, a greeting, an acknowledgement, a product question or a spelled-out brief answers in milliseconds from the deterministic path | `Chat._cheap`; open questions still reach the model, capped at 10 seconds |
| 2026-11-10 | The chat is an agent loop with three tools, not a question ladder | A ladder answers the same way every time, which reads as a form with extra steps; an agent reads the situation and decides | `_turn` / `_think` / `_start_tool` in `backend/chat.py`; the ladder survives as the fallback when no model answers |
| 2026-11-10 | A finished job is fed back to the model before the next line | Otherwise the console narrates what it expected instead of what happened | `_observe` turns a job into one plain sentence; the reply that follows is written from it |
| 2026-11-10 | Tool calls capped at three per user message; a finished `assemble` cannot restart | An agent that loops on its own tool is a bill, not a feature | Two guards in `_execute`, covered by tests |
| 2026-11-10 | A conversation counts only the channel it opened | The library on disk is shared across sessions, so counting all of it made a fresh chat announce ten videos it never read | `_counts(session)` and `fetch_videos_for_channel`; the start of a chat asks for a link instead of reporting numbers |
| 2026-11-10 | Slash commands are a registry, not if-statements in the page | The menu and the answers must not drift apart, and every command must run with no model call | `backend/skills.py` is the single list; `GET /api/skills` feeds the menu; `_cmd_*` handlers answer |
| 2026-11-10 | After a job, the next line comes from the rules, not the model | The provider costs 2 to 4 seconds; the job result is already a sentence, so a second call adds latency and nothing else | `_resume`; a channel job continues straight into ingest |
| 2026-11-10 | The tagline sits in the header, not in the flow | In the flow it collided with the first line of the conversation | `ui.py`: header carries it; the flow starts empty |
| 2026-11-10 | The chat routes on `deepseek-v4.1-flash-ultrafast`, the writer stays on `v4.1-flash` | The router is the only call between a keystroke and an answer; measured 1.2s against 3.2s for the same prompt, and the script quality does not depend on it | New `router` role with its own 200 token, 8 second budget; `MODEL_ROUTER` overrides it |
| 2026-11-10 | Search means YouTube, not the open web | The question is almost always "what already exists here and how did it do", and the videos, views and runtimes answer it; a web search returns blog posts about those videos | `search/youtube.py`, `/cari`, the `search_youtube` tool; the open web moved behind `/web` |
| 2026-11-10 | A channel link returns a profile, not a count | A number of videos says nothing about whether the channel is short-form explainers or hour-long podcasts, which changes every decision after it | `ingest/profile.py`: subscribers, description, tags, per-video views and runtimes; five checkable lines plus a written read |
| 2026-11-10 | The profile runs on its own role and budget | The same model at the writer's 500 token budget spent every token thinking and returned an empty string with `finish_reason=length` | `MODEL_PROFILE` / `ROLE_LIMITS["profile"]`: 1800 tokens, 40 seconds, measured about 18 seconds per read |
| 2026-11-10 | One scrape feeds the library and the profile | Fetching the channel tab twice doubled the wait for a report that should arrive while the first line is still being read | `_channel_job` builds Channel and Video from the profile |
| 2026-11-10 | An early poll waits instead of consuming the job | A poll that arrived before the job finished took the empty result, marked the job seen, and answered "isi channelnya nggak kebaca" while the real result was still coming | `handle(advance=True)` returns `pending` until the job is done |
| 2026-11-10 | A failed channel fetch no longer latches the conversation | `channel_fetched` was set before the job ran and never cleared, so one 404 answered every later link with the same sentence | `attempted_url` records what was tried; a pasted link or `coba lagi` retries; automatic resume does not |
| 2026-11-10 | The failure reason is shown, not guessed | The yt-dlp error went into session notes and the user was told "maybe the link is wrong", which was a guess | `_short_reason` names 404, 429, bot check and timeout in plain words |
| 2026-11-10 | The console can search the web without a key | The product needs facts and angles that are not in the library, and a keyed API would make search a paid dependency on day one | `search/web.py`; Bing, DuckDuckGo lite, Google News, Wikipedia; `BRAVE_API_KEY` is optional, never required |
| 2026-11-10 | Search results are scored by coverage, not by presence | The first working provider answered "inflasi indonesia" with a page about activating Windows, and one shared word ("Asia") made a generic page look authoritative | `_score` returns the ratio; a provider must clear half the query or the next one gets a turn |
| 2026-11-10 | Web search never becomes a citation in a script | The soul says every sentence traces back to the second it was spoken; a news link is not a spoken second | Search feeds the topic and the angle only; the writer still quotes transcripts only |
| 2026-11-10 | An empty model answer is asked once more, damaged JSON is salvaged | Ultrafast returned an empty body roughly one time in six on the long agent prompt; a retry costs 1.2s, a lost answer costs the whole conversation | `_think` retries once; `parse_plan` recovers a truncated `say` and refuses prose that claims work |

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
