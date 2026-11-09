# Soul Guard

The operating manual for `SOUL.md`. This document may be fixed at any time; `SOUL.md` may not.

Why they are separated: if the manual and the constitution lived in the same file, every wording fix in the manual would trigger a soul mismatch.

---

## 1. Verification

```bash
uv run -m narathor soul verify
```

What it does:

1. Read `SOUL.md`.
2. Compute SHA-256 over the file contents as-is (byte for byte, no line-ending normalisation).
3. Compare with the `sha256` in `soul.lock`.
4. Report `SoulCheck {ok, expected_hash, actual_hash, version, checked_at}`.

Result:

| Condition | Behaviour |
|---|---|
| Hash matches | `ok: true`, execution continues |
| Hash does not match | `ok: false`, **the whole command stops**, non-zero exit |
| `soul.lock` missing | `ok: false`, the message names how to regenerate it |
| `SOUL.md` missing | `ok: false`, the system cannot be run |

Verification runs **implicitly at the start of every command**, including inside every agent request to the backend. Not only when `soul verify` is invoked manually.

When there is a mismatch, what **does not** happen: no model call, no artefact written, no new database entry. The system stops before work begins.

---

## 2. Mismatch: what to do

Do not overwrite `soul.lock` immediately. A mismatch is an alarm, not an inconvenience.

1. **Find out what changed.**
   ```bash
   git diff SOUL.md
   ```
   If it is not a commit you made yourself, stop all work and inspect the repo.

2. **If the change was unintentional** — revert it:
   ```bash
   git checkout -- SOUL.md
   uv run -m narathor soul verify
   ```

3. **If the change was intentional** — that is a `soul bump`. Continue to section 3.

A mismatch overwritten without inspection destroys the only guarantee this system has.

---

## 3. The `soul bump` procedure

Changing the soul is not routine work. It changes the foundation of the whole product.

**Step 1 — Write the reason.** One paragraph. What is wrong with the old article, why the new one is more correct. No reason, no bump.

**Step 2 — Edit `SOUL.md`.** Raise the version at the end of the document. The change must be a whole article, not a sentence patch.

**Step 3 — Check the impact.** Which article changed, and which part of the system depends on it:

| Article | Depends on it |
|---|---|
| 1 | `learning_outcome` required in the brief |
| 2 | `single_minded_proposition` in the script |
| 3 | CTA checks |
| 4 | `payoff_pays_off`, the weight ratio limit |
| 5 | the citation gate |
| 6 | the two-layer `values_blocked` check |
| 7 | `run.json` |

**Step 4 — Run the bump.**
```bash
uv run -m narathor soul bump --reason "Article 5: verbatim replaced by fidelity to the trace because output is now a full script"
```
What happens: `soul.lock` raises `version`, stores the old hash in `previous_versions[]`, writes the new hash, and records the date and reason.

**Step 5 — Re-evaluate.** `soul_version` is part of the cache key. Every script produced under the old soul is **no longer valid**. Re-run eval:
```bash
uv run -m narathor eval --narrative <id>
```
Without this step, the bump is void.

**Step 6 — Record it in the Decision Log.** Add an entry to `docs/STATUS.md`:

```
| Date | Decision | Reason | Impact |
|---|---|---|---|
| 2026-11-09 | Soul v1 → v2, Article 5 | output is now a full script | every narrative needs re-eval |
```

---

## 4. Soul changelog format

`previous_versions[]` stores a trace, not the contents:

```json
{
  "version": 2,
  "sha256": "<new hash>",
  "locked_at": "2026-11-09",
  "locked_by": "boss",
  "previous_versions": [
    {
      "version": 1,
      "sha256": "<old hash>",
      "replaced_at": "2026-11-09",
      "reason": "Article 5: verbatim replaced by fidelity to the trace"
    }
  ]
}
```

The old contents are always available in git history. `soul.lock` only has to prove that the change was recorded.

---

## 5. Cache integrity

`soul_version` enters the cache key of every stage:

```
cache_key = hash(unit_id, prompt_version, brief_hash, soul_version, craft_version)
```

The consequence that must be understood: **changing the soul invalidates the entire cache.** That is deliberate. A script produced under different articles may not be reused as if it were still valid.

The re-eval cost after a bump is roughly one full run. That is the price of a constitutional change, and it is fair.

---

## 6. The limits of the guarantee — stated openly

What **is** guaranteed:

- Every mismatch between `SOUL.md` and `soul.lock` halts execution.
- A soul change cannot happen without changing `soul.lock`.
- Every `soul.lock` change is recorded in git history.
- Every artefact names the `soul_version` in force when it was created.

What is **not** guaranteed:

- That someone cannot edit `SOUL.md` **and** `soul.lock` together. On a local machine, anyone who controls the repo can.
- That the hash proves who changed it. A hash detects, it does not identify.

That is why the term used is **tamper-evident**, not tamper-proof. Calling it tamper-proof would be a lie that makes people trust a guarantee that does not exist.

---

## 7. Phase 2 hardening (not done)

Recorded as a plan, not as today's capability:

1. **Signing key outside the repo.** `soul.lock` is signed; the public key is distributed separately. Editing the lock is not enough without the private key.
2. **Remote attestation.** The soul hash is published at an endpoint that cannot be changed from the local machine.
3. **Soul as a release artefact.** The soul travels inside a signed release package; the binary refuses to run with a soul that does not match its release.

All three add friction. For the MVP, tamper-evident is enough, provided nothing more is claimed.

---

## 8. What must not be done

- Overwriting `soul.lock` without checking the diff.
- Running `soul bump` without a written reason.
- Changing the soul to let a failing brief through. If a brief fails, the brief is wrong.
- Adding a `--skip-soul` flag for emergencies. No emergency justifies bypassing the constitution.
- Calling this system tamper-proof.

---

## 9. Cross-references

| Document | Relationship |
|---|---|
| `SOUL.md` | What is protected |
| `soul.lock` | The integrity proof |
| `docs/SPEC.md` | Product rules derived from the soul |
| `docs/NARRATIVE.md` | What may and may not appear in a brief |
| `docs/AGENTS.md` | Where the soul check sits in the pipeline |
| `docs/STATUS.md` | Decision Log and Soul Compliance Log |
