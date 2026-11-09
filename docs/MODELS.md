# Models

Narathor's model strategy. This document changes whenever a new model appears, which is why it is separated from `TECH_STACK.md` and `AGENTS.md`.

Every id below is an **exact** id from the Command Code catalogue. Do not invent ids.

---

## 1. Principle

One model for all roles is an economic mistake and a quality mistake. Five roles have different needs:

- Work that heuristics can do → **use no model at all**.
- Work with small input and structured output → a cheap model is enough.
- Work that determines product quality → the one place model quality genuinely matters.
- Work that judges compliance → a model with strong instruction-following, not the best prose.

---

## 2. Allocation per role

| Role | Model | Exact id | $/1M in/out | Cache read | Why |
|---|---|---|---|---|---|
| **Indexer** | no LLM | — | $0 | — | Segmentation and filler detection are purely heuristic: timestamps, regex, pauses. A model adds nothing but cost. |
| **Curator** | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | $0.003 | Input is only video titles and descriptions. 1M context, cheap, enough. |
| **Matcher** | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | $0.003 | Large input (segment cards across videos). Cache read at $0.003 is the core of this system's economics. |
| **Writer** | DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | $0.003 | The boss's decision: economical first. See §4. |
| **Critic** | Claude Haiku 5.5 | `claude-haiku-5-5` | $0.10 / $0.50 | $0.01 | Judges seven gates, does not write prose. Strong instruction-following at a low price. |
| **Eval / tests** | Crouton Alpha | `stealth/crouton-alpha` | $0 / $0 | $0 | Pipeline iteration and testing at no cost. 1.05M context. |
| **Writer backup** | Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 | $0.10 | Enabled only when eval proves the main Writer falls short. |

Note: `claude-haiku-5-5` and `claude-sonnet-5-5` require the **GOAT** plan or above. `stealth/crouton-alpha` requires **Go** or above. DeepSeek models require **Go** or above.

---

## 3. Cost of one full run

Assumption: a 400-video channel, one hour average, producing 30 scripts.

| Stage | Volume | Estimated tokens | Cost |
|---|---|---|---|
| Library index | 400 videos × ~8 calls | ~2.0M input, 0.3M output | **~$0.30** |
| Thesis clustering | ~8 calls, batches of 50 cards | ~0.15M | ~$0.02 |
| Combo assembly | 30 theses × 1 | ~0.45M | ~$0.07 |
| Writing scripts (2 iterations) | 30 × 3 calls | ~4.2M input, 0.6M output | **~$2.60** |
| Critic | 30 × 1 | ~0.2M | ~$0.10 |
| **Total** | | | **~$3.10** |

**The Writer dominates ~84% of cost.** Practical consequences:

- Curator and Matcher may be cheap without hesitation.
- Only the Writer model decision is economically significant.
- Cutting Writer cost 10× saves only $2.3 of $3.1. Not worth it if quality drops.

With the Sonnet 5.5 backup, the total rises to **~$35 per run**. For 30 production-ready scripts that is still reasonable — but the decision must be based on eval, not feeling.

---

## 4. Writer: economical first, with the risk covered

A cheap model writes Indonesian prose that tends to be flat and formulaic. That is a real risk to the craft standard.

So the quality burden is **moved from the model to the structure**:

1. **Few-shot in the prompt.** `docs/CRAFT.md` holds 3 golden scripts. Concrete examples raise a cheap Writer's output more than upgrading the model class without examples.
2. **The Critic has teeth.** Flat scripts are returned, not accepted. Two iterations maximum, then `interrupt()` to the boss.
3. **The model is swappable in one line.** `MODEL_WRITER=claude-sonnet-5-5`. No code change.
4. **The eval harness is built in phase 7**, not phase 8, so the decision to change models rests on data.
5. **A/B comparison is mandatory** before the decision. Protocol in §6.

**A realistic ceiling with the cheapest Writer: neat and clear, not necessarily brilliant.** That is a knowingly accepted consequence, and eval will measure it — not hide it.

---

## 5. Override

Layered, from most specific to most general:

```bash
# per role
MODEL_WRITER=claude-sonnet-5-5
MODEL_MATCHER=deepseek/deepseek-v4.1-flash
MODEL_CRITIC=claude-haiku-5-5
MODEL_CURATOR=deepseek/deepseek-v4.1-flash

# blanket override (following the reference pattern)
MODEL_NAME=stealth/crouton-alpha
```

Rules:

- `MODEL_NAME` overrides every role at once; useful for free tests.
- Per-role variables win over `MODEL_NAME`.
- With no override, the defaults in §2 apply.
- Reasoning effort: low for every role except the Writer (medium). Models without effort support are not given the parameter.
- Overrides are recorded in `run.json`. A run that does not record its models cannot be reproduced.

---

## 6. Writer replacement protocol

Do not change based on impression. Follow this:

1. Take the same 10 `Combo`s. Run the candidate Writer and the backup Writer on identical input.
2. Produce 10 scripts from each.
3. Score with `narathor eval` on the same metrics: `craft_pass_rate`, `citation_violation_rate`, `hook_payoff_violation_rate`.
4. Read the ten script pairs without knowing which is which. Pick the better one per pair.
5. If the candidate wins in ≥ 7 of 10 and `craft_pass_rate` is higher → switch. Otherwise → keep.
6. Record the result in the `docs/STATUS.md` comparison table.

Without step 4 (the blind test), the decision will be influenced by the model brand, not by output quality.

---

## 7. Reasoning effort & parameters

| Role | Effort | Note |
|---|---|---|
| Curator | low | Classification; depth does not help |
| Matcher | low | Assembly; depth helps on complicated combos, but not by default |
| Writer | medium | The only place depth affects prose quality |
| Critic | low | Gate judging; explicit instruction matters more than deep reasoning |
| Eval | off | Pipeline testing; does not judge quality |

`max_retries=0` at the client level. Retries are handled by `ModelRetryMiddleware`, not the SDK.

---

## 8. Not allowed

- Inventing model ids. Every id in this document comes from the catalogue.
- Using an expensive model for a role that can be heuristic (Indexer).
- Using a cheap model for the Critic. A lenient Critic makes every gate meaningless.
- Changing a model without an eval.
- Hiding which model was used. Every `run.json` lists the model per role.
- Using different models between a production run and an eval run on the metric being compared.
