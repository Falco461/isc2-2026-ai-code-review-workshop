# 07. Production Architecture

You have a bot that works on your laptop and in CI. This module asks what it costs, and what changes, when a few hundred developers depend on it.

Read [`production/README.md`](../production/README.md) alongside this guide. It is the reference architecture: three tiers, scaling, model updates, monitoring.

All commands run from the repository root with the environment active.

## 1. Point the bot at a different server

The tiers differ only in where the model runs. Prove it by starting a second Ollama server on another port, standing in for the team server. It uses the models you already downloaded and listens on loopback only.

In a second terminal:

```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"; ollama serve
```

Back in your first terminal:

```bash
OLLAMA_HOST=http://127.0.0.1:11435 python reference-pipeline/review.py --file target-app/models.py
```

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11435"
python reference-pipeline/review.py --file target-app/models.py
Remove-Item Env:OLLAMA_HOST
```

**You should see** the same JSON as Module 3, and request lines scrolling in the second terminal. Nothing in the bot changed except one environment variable. A real team server is the same command with an internal hostname.

Check what is listening:

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep ollama
```

```powershell
netstat -an | Select-String ":1143[45]"
```

**You should see** `127.0.0.1:11434` and `127.0.0.1:11435`, never `*:` or `0.0.0.0:`. A team server has to listen on a network interface, which is why it belongs on an internal network that only CI runners can reach (checklist item 4). Do not make your laptop that server on the workshop wifi.

Stop the second server with Ctrl+C.

## 2. The cost model

Open [`production/tco-model.xlsx`](../production/tco-model.xlsx) in Excel, Numbers, or LibreOffice.

- **Inputs**: blue cells are inputs, yellow cells are the ones that matter most. Column F says where each default came from.
- **TCO**: the results, every one a formula.
- **Sensitivity**: the same formulas for team sizes from 10 to 2,000.
- **Notes**: what the model leaves out.

With the placeholder inputs:

| | CI runner, 9B | Team server, 20B | GPU server, 120B-class | Commercial SaaS |
|---|---|---|---|---|
| Tool TCO, 3 years | about $31,000 | about $32,000 | about $94,000 | about $302,000 |
| Including developer triage time | about $520,000 | about $522,000 | about $584,000 | about $792,000 |

Work through these at your table:

1. **Put in your own team.** Developers, pull requests a week, loaded rates. Which option is cheapest now?
2. **Find the crossover.** On Sensitivity, at what team size does the team server beat the CI runner? Why does the CI runner get more expensive with size and the server not?
3. **Price the noise.** On Inputs, change the 120B-class false-positive share from 20% to 10%. Watch TCO row 19. How much is a point of precision worth to your team?
4. **Price compliance.** If your policy forbids sending source code off site, what is the SaaS column worth? (The Notes sheet has an answer.)

## 3. Gate a model update

A model update is a code change. Run the gates against a candidate model, here `gpt-oss:20b` standing in for "the new model":

```bash
REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low python reference-pipeline/smoke.py
REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low python eval-harness/capstone.py --reps 1
```

```powershell
$env:REVIEW_MODEL = "gpt-oss:20b"; $env:REVIEW_THINK = "low"
python reference-pipeline/smoke.py
python eval-harness/capstone.py --reps 1
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

Then run the same two with your current model and compare. Would you promote the candidate? What would you need to see from the attack lab before you did?

On Codespaces or a CPU-only laptop, run only the smoke test.

## 4. Decide what to watch

The table in `production/README.md` lists six signals, all from the audit log, the CI job, or the comment. Pick the two you would put on a dashboard first, and the threshold that would page someone. Be ready to defend it in the group discussion.

## 5. Fixes and bypasses in the pull request

A bot that only complains gets ignored. In production, developers need two more things from it: **a fix they can apply**, and **a way to disagree** that leaves a record. This section adds both, on GitHub and GitLab.

### Suggested fixes, one click

For each finding on a line the pull request changed, the bot asks the model for a fix and posts it **on that line**, as a suggestion with the platform's own button: **Commit suggestion** on GitHub, **Apply suggestion** on GitLab. When the model is not confident it can fix something safely in place, the bot posts its advice without a button.

See it locally first, on the Module 4 branch (`add-order-importer`). Bring today's bot into the branch first (`git merge --no-edit main`), or the branch still has yesterday's code; then diff only what the branch changed (`main...HEAD`, three dots):

```bash
git switch add-order-importer
git merge --no-edit main
git diff main...HEAD > pr.diff
python reference-pipeline/review.py --diff pr.diff --sweep > findings.json
python reference-pipeline/post_comment.py findings.json --print --suggest --diff pr.diff
git switch main
```

The commands are the same in PowerShell. No `add-order-importer` branch? Make one: `git switch -c add-order-importer`, then `git apply ci-templates/lab/add-order-importer.patch`, `git add target-app/importer.py`, and `git commit -m "Add bulk order import"`. **You should see** the summary comment, then one block per finding: a suggested patch for the hardcoded token and for `verify=False`, and advice only for `pickle.loads`, where no safe one-click fix exists.

Read the token fix closely. It reads the token from `os.environ`, and the file has no `import os`. The rationale says so; the button does not. **A one-click fix is still model-written code that read the attacker's code.** That is why nothing is committed until a person clicks, and why the suggestion says so.

In CI, the templates already do this (`post_comment.py --suggest --diff pr.diff`). To get it on your Module 4 repository, copy the template again, push it to `main`, then push any commit to your pull request branch.

### Bypasses, as code

A developer who disagrees with a finding does not argue with the bot. They add an entry to `security-suppressions.toml` in the pull request, and that change gets reviewed like any other:

```toml
[[suppress]]
file = "target-app/importer.py"
match = "verify=False"
reason = "Partner feed is on the internal network. SEC-123 adds the CA bundle."
approved_by = "appsec-oncall"
expires = 2026-11-30
```

`file`, a `reason`, and `approved_by` are required, plus either a `line` or a `match` (text on the finding's lines). `rule` (such as `B501`) and `expires` are optional. An entry missing any required part, or past its expiry, is ignored with a warning.

On Windows, create it from PowerShell, so the encoding is right:

```powershell
Set-Content -Encoding ascii security-suppressions.toml @'
[[suppress]]
file = "target-app/importer.py"
match = "verify=False"
reason = "Partner feed is on the internal network. SEC-123 adds the CA bundle."
approved_by = "appsec-oncall"
expires = 2026-11-30
'@
```

Try it: save that file at the repository root (on the `add-order-importer` branch, with `pr.diff` from above), rerun the review and the comment, and look for the **Suppressed** table at the bottom. The finding is still shown, with the reason and who approved it. Then delete `approved_by` and run it again.

```bash
python reference-pipeline/review.py --diff pr.diff --sweep > findings.json
python reference-pipeline/post_comment.py findings.json --print
```

The commands are the same in PowerShell. Delete `security-suppressions.toml` when you are done (`rm security-suppressions.toml`, or `Remove-Item security-suppressions.toml` in PowerShell).

**In CI, a pull request cannot approve its own bypass.** The templates set `REVIEW_SUPPRESSIONS_REF` to the target branch, so the bot reads `security-suppressions.toml` from `main`, not from the pull request. A new bypass counts only after its own change has been reviewed and merged.

**`approved_by` is a record, not a login.** Anyone can type a name. The control is the review of the file itself: in production, protect `security-suppressions.toml` with CODEOWNERS (GitHub) or code owners approval (GitLab) so only the security team can approve changes to it.

### What we did not build: replying in the thread

A production bot can also take replies on its comment ("/dismiss, test fixture") and suggestions by button. On GitHub that means a workflow triggered by pull request comments, and comment-triggered workflows run with write access: if one ever checks out and runs the pull request's code, any commenter owns your repository. On GitLab, CI cannot trigger on a comment at all without a separate service listening for webhooks. Both are real patterns; both are work to do safely. Suppressions as code give you the same outcome, a reviewed and recorded bypass, with no new trigger.

## 6. Table presentations

About 40 minutes: 15 to prepare, then 5 minutes per table.

Use the pipeline you drew in Module 1. Each table presents:

1. **Which tier,** and why not the one next to it.
2. **The TCO,** with your own numbers in the yellow cells. Name the one input you are least sure of.
3. **Two signals** you would put on a dashboard, and the threshold that pages someone.
4. **Who owns the model update gate,** and what happens when that person is on vacation.

The room asks one question per table. The best question wins.

## Discussion

- Tier 1 needs no hardware and sends no code anywhere. What would make you move off it?
- The TCO model says triage time costs more than any tool. Does that match your experience with your current scanners?
- Who owns the model server in your organization: the platform team, the security team, or nobody? What happens to the bot when that person leaves?

## Instructor notes

- Section 1 runs on one machine. On Codespaces it works the same way inside the codespace.
- The tier 1 review time (8 to 12 minutes per job) was measured on a free GitHub runner in October 2026. Every other default in the workbook is a placeholder and says so.
- The workbook builds from a script kept in the project folder, not the repository, so attendees do not need `openpyxl`.
- Table presentations work best with a hard 5-minute timer. If time is short, do three tables and collect the rest on paper.
- Section 5, measured Oct 24 with `qwen3.5:9b`, 2 of 2 runs: patches for the token, `verify=False`, and `pickle.loads` (switched to `json.loads`, with a warning that the data format changes). The path traversal patch checks `file_path.is_relative_to(base_dir)` **without resolving the path first**, so `../../etc/passwd` still passes, and it uses `Path` without importing it. It looks right and is not. Use it as the read-before-you-click example.
