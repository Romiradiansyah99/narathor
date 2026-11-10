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

The public page is a single screen:

- https://romiradiansyah99.github.io/narathor/

It carries the name, one line, and nothing else. Earlier commits published demo scripts
built from the synthetic transcripts in `data/`; those pages are gone on purpose. A static
host cannot take a brief or run a pipeline, and showing fixture output next to the product
name reads as a result. The page stays empty until a real run has something worth showing.

```bash
uv run python tools/build_landing.py   # writes site/index.html
```

---

## Console

The console is a conversation, not a form. You type, it answers, and it decides what to do
next. It is an agent loop: one model call reads the situation, the conversation and the last
tool result, then either says something or calls a tool.

Tools it can call:

- `fetch_channel` — read a channel's video tab into the library
- `ingest` — pull transcripts, captions first
- `assemble` — compose the brief from what you said and run the pipeline

Long work runs as a job and its log is appended to the same conversation. After a job ends,
the result is fed back to the model so the next line answers what actually happened, not what
was expected. Every turn is stored in `output/_chat/<session>.json`, so closing the tab loses
nothing. Tool calls are capped at three per message, and a finished `assemble` will not
restart itself.

```bash
# 1. a token, so a tunnel is not an open door
printf '%s' "$(python -c 'import secrets;print(secrets.token_urlsafe(12))')" > .ui_token

# 2. start it
python tools/run_console.py          # 127.0.0.1:8811

# 3. reach it from anywhere
cloudflared tunnel --url http://127.0.0.1:8811
# open the printed https://<name>.trycloudflare.com/?t=<token>
```

When the model is unavailable the console does not break: it falls back to a deterministic
ladder (ask for the channel, then the topic, then ingest, then assemble) that reads URLs,
handles, counts and durations with regex. Set `NARATHOR_CHAT_MODEL=off` to run that way on
purpose.

**One known blocker.** YouTube refuses transcripts and media from datacenter IPs:
`youtube_transcript_api` raises `RequestBlocked` and yt-dlp answers "Sign in to confirm
you're not a bot". Channel listing still works, which is why the library fills but
transcripts come back skipped. The fixes, in order of effort:

1. a cookies file from a logged-in browser: `YT_COOKIES_FILE=/path/cookies.txt` (yt-dlp then
   fetches the subtitle track, no audio download, no Whisper)
2. a residential proxy: `YT_PROXY=http://user:pass@host:port`
3. run `uv run narathor ingest` on a normal connection and copy the transcripts over

Whisper is the third fallback and needs `uv sync --extra whisper`; it downloads audio, so it
hits the same IP block.

---

## Status

Phases 1–6 complete and verified; phases 7–8 partly done, waiting on a real library and a golden set. `uv run check` is green: ruff, pyright, 112 tests, 81% coverage.

See [`docs/STATUS.md`](docs/STATUS.md).

---

## License

Code is released under the MIT license. `SOUL.md` is the product's constitution: it may be read and quoted, but any redistribution of this system must keep it intact and hash-verified.
