# Process

How work is done in this repo. Follows `00. Plan Build References/PROCESS.md`, adapted for Narathor.

---

## Setup

```bash
uv sync
```

Python dependencies live in the root `pyproject.toml`. In Phase 2, `npm install` is added for the dashboard.

---

## Checks

```bash
uv run check
```

Runs: ruff (lint + format), pyright, pytest with a minimum of 80% coverage.

In Phase 2 this adds: Prettier, ESLint, tsc, vitest, and Playwright.

A pre-commit hook runs format, lint, type check, and unit tests on every commit.

---

## Planning

When asked to plan — for example "please plan the pilot" — write the plan into `docs/PLAN.md` and **write no code**.

How to structure it:

1. Break the work into phases, usually 5 to 8, each built on the previous one.
2. Every phase has detailed success criteria you can verify yourself: tests that pass, commands and their output, API calls and responses, files produced and their contents.
3. Write each criterion as a checkbox.
4. Stop. Wait until you are asked to implement.

A plan you cannot verify yourself is not a plan; it is an intention.

---

## Implementing

When asked to implement, build each phase in order **without stopping**. For every phase:

1. Build it, with tests.
2. Check every success criterion and fix what fails.
3. Tick the criteria in `docs/PLAN.md` and update `docs/STATUS.md`.
4. Commit. The pre-commit hook runs the checks; if it fails, fix it and commit again.

After the last phase: run `uv run check` and report the result.

---

## Rules

- **Add a test with every change.** Tests never call a model; use stub models.
- **Never read `data/eval/`.** That folder is the answer key. Agents, tests, and tooling do not touch it.
- **Run `uv run check` before handing over work.**
- **Never use `git commit --no-verify`.**
- **Never lower a threshold, disable a rule, or exclude a file** to make a check green. If a rule feels wrong, stop and ask.
- **Keep `docs/STATUS.md` true.**
- **Do not push.** (Superseded: pushing is allowed when the boss asks for it in the same session.)
- **Everything must run on Windows.** Scripts go through `uv run` or `.mjs` files.
- **The soul is not touched.** No task may change `SOUL.md` or `soul.lock` except an explicit, boss-approved `soul bump`.
- **Spec first, code second.** A behaviour change updates `docs/SPEC.md` first.
- **No themes in code.** `if channel == "..."` or a hardcoded list of values is a bug. Move it to the brief.
- **Prompts are code.** Keep them in `prompts/` with a `prompt_version`; a prompt change requires an eval.

---

## Work order per task

1. Read the task.
2. Read the relevant part of the spec — do not guess.
3. Write the test first.
4. Implement.
5. Run `uv run check`.
6. Update `docs/STATUS.md`.
7. Commit.

Skipping step 2 produces code that is right for the wrong problem. Skipping step 3 produces tests that follow the implementation instead of testing behaviour.

---

## Definition of Done

A task is done when **all** of these are true:

- [ ] Tests pass, including tests for new behaviour.
- [ ] `uv run check` is green without lowering anything.
- [ ] No test calls a model.
- [ ] No reference to `data/eval/`.
- [ ] A sample output is saved in `output/_samples/` if the task produces artefacts.
- [ ] `docs/STATUS.md` updated.
- [ ] Affected documents updated (SPEC, AGENTS, CRAFT, or NARRATIVE).
- [ ] If it touches scoring or prompts: the `narathor eval` result is attached.

---

## Commit

Message format:

```
<phase>: <what changed>

<short reason when the title does not make it obvious>
```

Example:

```
fase 4: heuristic indexer + filler detection

Segmentation uses pauses >0.8s and sentence markers. Fillers are detected
with a pattern list, not a model, because the Indexer takes no LLM.
```

Commits in English. No emoji. One commit per logical change.

---

## When in doubt

| Situation | Action |
|---|---|
| The spec is unclear | Stop and ask. Do not invent a behaviour. |
| A check fails for a reason that looks wrong | Fix the reason, never the threshold. |
| Something needs a bypass flag | It does not. Redesign it. |
| A source is missing | Report the gap; do not fabricate a substitute. |
