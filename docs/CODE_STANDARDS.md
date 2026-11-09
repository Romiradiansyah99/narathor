# Code Standards

The rules for all code in this repo. They follow `00. Plan Build References/CODE_STANDARDS.md`, with additions specific to Narathor.

---

## General

1. **Simple first.** Do not abstract until there are two real callers, not two imagined ones.
2. **Comments only when necessary.** Code that needs a comment to be understood usually needs a better name.
3. **Terse.** Short README. No emoji in code, commits, or technical documents.
4. **Avoid excessive defensiveness.** Handle exceptions at system boundaries (user input, external APIs, filesystem). Trust your own internal code.
5. **Always `uv run`.** Never call `python3` or `python` directly.
6. **TypeScript strict, no `any`.** Applies when the dashboard is built (Phase 2).

---

## Specific to Narathor

7. **No themed behaviour in code.** If `if channel == "..."` or a hardcoded list of values appears, that is a bug. Move it to the Narrative Brief.
8. **The soul is not a variable.** Never place the soul's contents, its hash, or a bypass path in code that config can change.
9. **Invariants are enforced in the backend, not in prompts.** A prompt can be ignored by a model. An endpoint cannot.
10. **Every API operation has an `operation_id`, a one-line docstring, and no optional inputs.** Follows `docs/TECH_STACK.md`.
11. **Tests never call a model.** Use stub models. No exceptions.
12. **Do not read `data/eval/`.** That folder is the answer key. Agents, tests, and tooling do not touch it.
13. **Prompts are code.** Prompts live in `prompts/` with a `prompt_version`, and a prompt change requires an eval.
14. **Cache keys carry versions.** `unit_id + prompt_version + brief_hash + soul_version + craft_version`. A versionless cache yields stale output that looks legitimate.

---

## Python

- Python 3.12, managed by `uv`.
- Pydantic v2 for every data contract. Contract models live in one place, not scattered.
- `ruff` for lint and format; `pyright` for types.
- Pure functions are separated from anything touching I/O. Transcript segmentation, feature computation, and gate checks must be testable without a database, network, or model.
- No `time.sleep` in application code. Retries use middleware.
- Paths always go through `pathlib`. Manually concatenated path strings are a bug on Windows.

---

## Concurrency

- Fan-out uses LangGraph's `Send`, not a hand-rolled `asyncio` loop.
- `max_concurrency` is **always** explicit. Default 5. Never unbounded.
- Every work unit is idempotent. A node re-run after a crash must not duplicate cost or data.
- Deterministic merge: sort by `script_id`, not by arrival order.
- One failing unit must not stop the run.

---

## Errors

- Failure from a soul or citation violation → **stop**, not continue with a warning.
- Failure from a provider or timeout → retry once, then `deferred`, the run continues.
- Failure from bad input (video has no audio, empty transcript) → `skipped`, recorded in `run.json`, the run continues.
- An error message names what is wrong and what to do about it. "Error 400" is not a message.

---

## Not allowed

- `git commit --no-verify`.
- Lowering a threshold, disabling a rule, or excluding a file to make a check green.
- Adding a bypass flag for the soul, citations, or craft gates.
- Storing secrets in the repo. Everything goes through `.env`, and `.env` is in `.gitignore`.
- Writing artefacts without `run.json`.
