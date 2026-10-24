# 02. Model Deployment

Run three open-weight models through Ollama on the same code and compare what each one says.

| Model | Size | Who runs it |
|---|---|---|
| `qwen3.5:9b` | 6.6 GB | Everyone. The workshop default. |
| `qwen2.5-coder:7b` | 4.7 GB | Everyone. The low-memory fallback. |
| `gpt-oss:20b` | 13 GB | Laptops with 24 GB of RAM or more. Everyone else watches the instructor's screen. |

`gpt-oss:20b` is OpenAI's open-weight model. All three run entirely on your machine.

## 1. Pull the extra models

You already have `qwen3.5:9b`. Pull the fallback, and GPT-OSS if your laptop has 24 GB or more:

```bash
ollama pull qwen2.5-coder:7b
ollama pull gpt-oss:20b
```

Check:

```bash
ollama list
```

## 2. Talk to a model directly

Before any tooling, ask the model something yourself:

```bash
ollama run qwen3.5:9b "In one sentence, what is SQL injection?"
```

That is the whole interface: a local HTTP server that takes a prompt and returns text. Everything the bot does is built on top of it.

## 3. Same file, three models

Run the commands below from the repository root, the folder containing `.venv`
and `reference-pipeline`. They use the workshop's Python directly, so they work
in a new terminal without activating the environment. If `.venv` is missing,
run the setup script from [00. Setup](00-setup.md) first.

Review one file, `target-app/app.py`, with each model. `REVIEW_MODEL` picks the model and `REVIEW_THINK` sets its reasoning: `false` for the Qwen models, `low` for GPT-OSS, which cannot turn reasoning off.

```bash
REVIEW_MODEL=qwen3.5:9b REVIEW_THINK=false .venv/bin/python reference-pipeline/review.py --file target-app/app.py
REVIEW_MODEL=qwen2.5-coder:7b REVIEW_THINK=false .venv/bin/python reference-pipeline/review.py --file target-app/app.py
REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low .venv/bin/python reference-pipeline/review.py --file target-app/app.py
```

```powershell
$env:REVIEW_MODEL = "qwen3.5:9b"; $env:REVIEW_THINK = "false"; & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\app.py
$env:REVIEW_MODEL = "qwen2.5-coder:7b"; $env:REVIEW_THINK = "false"; & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\app.py
$env:REVIEW_MODEL = "gpt-oss:20b"; $env:REVIEW_THINK = "low"; & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\app.py

Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

If you see `No module named bandit` or `No module named detect_secrets`, the
scanners did not run. Use the `.venv` interpreter shown above and rerun setup if
the error persists. A failed scan is not evidence that the code is clean.

Each prints JSON. Look at the `severity` of each finding.

**What to look for:** `app.py` has two hardcoded credentials, on lines 15 and 17. Do all three models rate both of them as real?

### If GPT-OSS reports no findings

A warning that a finding was dropped because its quoted evidence is not on the
cited lines means the model's answer failed citation checking. If the output
says the scanners reported two items but none survived, both scanners ran;
the empty findings list does not mean the code is clean.

GPT-OSS sometimes puts an extra JSON string wrapper around an otherwise correct
source quote, adding outer quotes and backslash escapes. The current bot handles
that wrapping when matching evidence against the source. It still rejects a
quote from the wrong file or line, or text that does not match the source.

If an older checkout drops both credential findings for this reason, update it
from the repository root, then rerun the GPT-OSS command above:

```bash
git pull --ff-only
```

The update command also works in PowerShell. If citation warnings remain,
inspect the model's evidence and its cited lines. A model can still quote the
source incorrectly, and those findings should be rejected.

## 4. Write down what you saw

For each model: how many findings, what severity on line 17, and how long it took. Compare with your neighbour.

## Going further

About 30 minutes. Laptops with 24 GB of RAM or more only for the GPT-OSS parts; everyone else pairs up.

### What does more thinking buy?

GPT-OSS cannot turn reasoning off, but you can choose how much it does. Time the same review at each level:

```bash
time REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low .venv/bin/python reference-pipeline/review.py --file target-app/auth.py
time REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=medium .venv/bin/python reference-pipeline/review.py --file target-app/auth.py
time REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=high .venv/bin/python reference-pipeline/review.py --file target-app/auth.py
```

```powershell
$env:REVIEW_MODEL = "gpt-oss:20b"
foreach ($level in "low", "medium", "high") {
    $env:REVIEW_THINK = $level
    $s = (Measure-Command { & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\auth.py | Out-Host }).TotalSeconds
    "think=$level took $([int]$s) seconds"
}
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

Did the findings change, or only the time? Then try the default model with reasoning on:

```bash
time REVIEW_MODEL=qwen3.5:9b REVIEW_THINK=true .venv/bin/python reference-pipeline/review.py --file target-app/auth.py
```

```powershell
$env:REVIEW_MODEL = "qwen3.5:9b"; $env:REVIEW_THINK = "true"
Measure-Command { & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\auth.py | Out-Host }
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

Put the times on the board, by laptop. This is the data you need to choose a `think` setting for CI.

### Same model, five runs

Run the default model on `app.py` five times. Do you get the same findings every time? Temperature is 0 in `config.toml`. Day 2 comes back to why that is not a guarantee.

## Discussion

- The fallback model rates the hardcoded API token on line 17 as `info`. A reviewer who trusts it ships a live credential.
- A model can be confidently wrong in its explanation too. Read one explanation closely: does it claim anything the code does not say?
- Reasoning models think before they answer. Left on their default, a single review can take minutes. That is why `think` is always set explicitly in `config.toml`.

## Instructor notes

- On an M5 Max each run takes 5 to 11 seconds. On CPU-only laptops expect a minute or more per model.
- Measured results for all models are in `docs/MODEL_EVAL.md`. Foundation-Sec 8B (security-trained) is a good discussion point: it finds the bugs but buries them in about 15 unmatched findings per run.
- A known hallucination to point out: models have described `tok_live_...` as a Stripe token. Nothing in the code says Stripe.
- Going further: put a timing table on the board (model, think level, laptop, seconds). It feeds the Module 7 cost discussion.
