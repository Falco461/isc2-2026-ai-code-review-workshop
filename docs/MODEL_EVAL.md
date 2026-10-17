# Model evaluation, October 2026

Why the default is `qwen3.5:9b` with reasoning off, why `gpt-oss:20b` is the Module 2 model, and why `qwen2.5-coder:3b` is retired. The September 2026 record follows below for history.

This is still a setup decision record, not the Phase 2 `eval-harness/`.

## Method

- Machine: MacBook Pro M5 Max, 48 GB, macOS. Ollama 0.35.1. Laptop timings will be several times slower.
- The real `review.py`, run against `target-app`, scored against `target-app/PLANTED.md` (six planted bugs after bug 6 was reclassified, see below).
- Temperature 0, `num_ctx` 8192, full JSON schema in Ollama's `format` field.
- Triage: scanners on. A real bug counts when rated above `info`. A false positive counts when rated above `info` and the finding is about the flagged value.
- Cold: `--no-scanner`. A bug counts when a finding's cited range covers it. "Unmatched" counts findings that match no planted bug.
- Reasoning set explicitly through `think`: `false` for Qwen models, `"low"` for gpt-oss, which cannot turn reasoning off.

## Triage, current prompt, five reps

| Model | Size | SQLi | Secret key | Reporting token | Cmd inj | Bug 6 | False positives | Time |
|---|---|---|---|---|---|---|---|---|
| **qwen3.5:9b** (default) | 6.6 GB | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0 | 25s |
| **gpt-oss:20b** (Module 2) | 13 GB | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0, one duplicate of bug 6 | 21s |
| qwen2.5-coder:7b (fallback) | 4.7 GB | 5/5 | 5/5 | **0/5** | 5/5 | **0/5** | 0 | 14s |

Three reps on the earlier prompt also covered `qwen2.5-coder:3b`, which dropped the hardcoded secret key and escalated a false positive in every run, and Cisco Foundation-Sec 1.1 8B Instruct, which dropped the secret key.

## Cold discovery, three reps

| Model | SQLi | Secret key | Reporting token | Cmd inj | Bug 6 | Path traversal | BOLA | Findings / unmatched | Time |
|---|---|---|---|---|---|---|---|---|---|
| qwen3.5:9b | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 | 0/3 | 0/3 | 5 / 1 | 22s |
| gpt-oss:20b | 3/3 | 0/3 | 0/3 | 3/3 | 0/3 | **3/3** | 0/3 | 3 / **0** | 14s |
| qwen2.5-coder:7b | 3/3 | 0/3 | 0/3 | 3/3 | 3/3 | 0/3 | 0/3 | 5 / 2 | 12s |
| Foundation-Sec 1.1 8B | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 | 0/3 | 20 / **15** | 42s |
| qwen2.5-coder:3b | 0/3 | 0/3 | 0/3 | 0/3 | n/a | 0/3 | 0/3 | 0 / 0 | 3s |

## What changed since September

1. **Bug 6.** `auth.py` line 56 accepts the literal `password123` for every account. It was listed as a scanner false positive. `gpt-oss:20b` reported it as a hardcoded credential, it is one, and it is now planted bug 6 with an exploit test.
2. **The default dismissed it by trusting a docstring.** `qwen3.5:9b` rated bug 6 `info` in 5 of 5 runs, quoting "Demo comparison, not a real password check," and escalated the template on the line above instead. The prompt rule "only compared against" read as covering a literal that a user-supplied password is compared with. Rewording that rule took bug 6 from 0/5 to 5/5 with no false positives. This is the September self-describing-source problem again, in a newer model, and it is a Module 5 demo.
3. **The 3B is retired.** On the hardened prompt it drops a real secret and escalates a false positive.
4. **Reasoning models are usable** with reasoning set explicitly. `qwen3:4b` in September was left on its default and took minutes per review.
5. **Security training is not code reading.** Foundation-Sec finds the reachable bugs cold but buries them in about 15 unmatched findings per run.
6. **The models fail differently.** gpt-oss is the only model to find path traversal cold and makes no unmatched findings; the 7B finds bug 6 cold but misses it in triage. That is the Module 2 comparison lab.

---

# Model evaluation, September 2026

Why the default model is `qwen2.5-coder:7b` and why `qwen2.5-coder:3b` is a triage-only tier.

This is a setup decision record, not the Phase 2 `eval-harness/`. The harness will supersede it with a reproducible version.

## Method

- Machine: MacBook Pro M1, 16 GB, macOS. Ollama 0.34.0.
- Target: a Flask sample with five planted bugs (SQL injection, two hardcoded secrets, command injection via `shell=True`, path traversal).
- Five repetitions per model, `temperature: 0`, fixed seed per rep, `num_ctx: 8192`.
- Bandit findings supplied to the model as evidence in every run.
- Output constrained by passing a full JSON schema to Ollama's `format` field.
- A bug counts as detected only when a finding cites its actual line number. Citing the right vulnerability at the wrong line does not count.

## Cold discovery

The model is shown the code and the scanner evidence and asked to produce the full finding set.

| Model | Size | Schema valid | Findings/run | SQL inj | Secret | Cmd inj | Path trav | Latency |
|---|---|---|---|---|---|---|---|---|
| qwen2.5-coder:3b | 1.9 GB | 5/5 | 1 | 0/5 | 0/5 | 5/5 | 0/5 | 7s |
| qwen2.5-coder:3b-instruct-q8_0 | 3.3 GB | 5/5 | 1 | 0/5 | 0/5 | 5/5 | 0/5 | 16s |
| qwen3:4b | 2.5 GB | aborted | minutes per review, see note | | | | | |
| **qwen2.5-coder:7b** | 4.7 GB | 5/5 | 5 | **5/5** | **5/5** | 5/5 | 0/5 | 60s |

The 3B reports exactly one finding per run and stops, even with Bandit handing it five on a plate. The q8 quant behaves identically, so this is a capability ceiling at 3B, not a quantization artifact.

`qwen3:4b` is a hybrid reasoning model. It burns thinking tokens before emitting JSON, taking minutes per review, and was aborted. Do not ship a reasoning model as the attendee default.

### Decomposition does not rescue the 3B

One confirm-or-reject call per scanner finding, plus one open sweep for what the scanner missed:

| Model | Schema valid | Findings/run | SQL inj | Secret | Cmd inj | Latency |
|---|---|---|---|---|---|---|
| qwen2.5-coder:3b decomposed | 5/5 | 1 | 0/5 | 5/5 | 0/5 | 25s |

It got slower, and it rejects true positives. Given the option to say no, the 3B says no to real bugs.

## Scanner triage

The scanner finding is presented as true. The model explains and prioritizes it rather than deciding whether it is real. Four findings, five reps, so twenty calls per model.

| Model | Schema valid | Correct line preserved | On topic | Latency per 4-finding review |
|---|---|---|---|---|
| qwen2.5-coder:3b | 20/20 | 20/20 | 20/20 | **30s** |
| qwen2.5-coder:7b | 20/20 | 20/20 | 20/20 | 65s |

**Both models are perfect at triage, and the 3B is twice as fast.** This is the result that makes the tiered story work, and it is stronger than expected: on the primary scanner-triage path the 3B is not a degraded fallback, it is the better choice. Equal accuracy, half the latency, 1.9 GB instead of 4.7 GB.

The 7B is still the default because it is the only model that also handles cold discovery, which the capstone and the definition of done require. But an attendee on a CPU-only Windows laptop who runs 3B for Modules 3 and 4 gives up nothing on the published architecture.

## Structured output

The first three probes asked for JSON in the prompt, the way the original brief specified. Results at `temperature: 0` were unstable: three different answers across three runs, one containing a bare string inside the `findings` array, and enum values in the wrong case.

Passing a full JSON schema to Ollama's `format` field instead produced valid, correctly-cased output on every run of every model tested. Schema-constrained decoding is the mechanism. The in-code validation layer stays anyway, because a schema constrains shape and not truth.

## Scanner coverage on the sample

| Bug | Bandit | detect-secrets |
|---|---|---|
| SQL injection | B608 | no |
| Hardcoded secret key | B105 | Secret Keyword |
| Hardcoded API token | B105 | no |
| Command injection | B602 | no |
| Path traversal | **no** | no |
| BOLA | **no** | no |

Two findings that shape the build:

1. **Bandit and detect-secrets are complementary.** Neither alone covers both planted secrets.
2. **Path traversal is invisible to the Phase 1 pipeline.** No scanner rule fires and no model found it. Of the five planted bugs, Phase 1 reliably finds three. BOLA is designed to be missed, and path traversal missing alongside it strengthens the Module 3 grounding argument, but `smoke.py` must assert against the three detectable bugs, not all five.

## Gotchas

- **detect-secrets has two silent-failure modes, both returning an empty result rather than an error.** First, a directory scan only covers git-tracked files, so a directory of new uncommitted files reports nothing; `--all-files` fixes it but does not honor `.gitignore`, so noise paths need explicit exclusion. Second, it only reports files whose path resolves under the current working directory, so an absolute path to a file outside cwd returns nothing. Run it from the repo root with repo-relative paths, and have the caller verify a non-zero file count.
- **Bandit does not emit SARIF out of the box.** Formats are csv, custom, html, json, screen, txt, xml, yaml. SARIF requires the `bandit-sarif-formatter` package, which is pip-installable and pure Python.

## Workshop content

The 3B versus 7B split is teachable material, not just configuration. The same finding through both models is the Module 2 "what it catches, misses, and hallucinates" lab, and the numbers above are the Module 1 model-size discussion. The experiment is already run.

## Triage quality tuning, September 2026

Phase 1 shipped with the model reporting documented false positives as real findings. Fixed by prompt work plus one deterministic signal, measured on all seven scanner findings against `target-app`, three reps each, `qwen2.5-coder:7b`.

Ground truth is `target-app/PLANTED.md`: four real defects, three known scanner false positives.

| Prompt | Real bugs escalated | False positives marked info |
|---|---|---|
| Phase 1 baseline | 12/12 | 3/9 |
| Stronger false-positive rules | **6/12** | 9/9 |
| Hardened against self-describing source | **12/12** | **9/9** |

Severity calibration improved alongside it. The baseline rated SQL injection and command injection `medium`. The final prompt rates hardcoded secrets `critical` and both injections `high`.

### The regression is the interesting part

The middle row is a false negative, which is worse than the problem being fixed. Strengthening the false-positive rules made the model dismiss the genuine hardcoded secrets in `app.py` as `info`.

The cause was `target-app`'s own docstrings. Every module opens with "Intentionally vulnerable workshop application. Do not deploy." The prompt at that point allowed dismissing a finding when the value was "clearly illustrative," and the model took the file's self-description as evidence and suppressed a real defect.

**Source text is written by the author of the code under review.** In a security review that is exactly the party you are checking. A prompt that lets comments, docstrings, or variable names influence severity hands an attacker a suppression primitive: add a comment claiming the file is a demo and findings quietly drop to `info`.

The fix has two parts:

1. The prompt states that the file's own claims about itself are not evidence, lists the dismissal conditions as exhaustive, and names categories that are never dismissed regardless of surrounding text.
2. The only trusted "this is test code" signal is computed in code from the file path (`looks_like_test_code`), not read from file contents, and is passed to the model as context.

That second point is the general pattern: trusted context is derived outside the model from data the author of the reviewed code does not control.

### Workshop content

This is a ready-made Module 5 demo. Adding one comment to a file to suppress a real finding is prompt injection through attacker-controlled code, which is the exact surface the workshop is about. The before and after numbers above are the measurement.
