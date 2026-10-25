# Production reference architecture

What the workshop bot looks like when a team of hundreds depends on it. Module 7 walks through this page and the TCO model next to it.

Everything here is a pattern, not a product. The workshop code runs all of it: the only thing that changes between tiers is `OLLAMA_HOST` and `REVIEW_MODEL`.

## Three tiers

| | 1. CI runner | 2. Team server | 3. GPU server |
|---|---|---|---|
| Model | `qwen3.5:9b` | `gpt-oss:20b` | a 120B-class open-weight model, such as `gpt-oss-120b` |
| Where it runs | inside each CI job | one machine on the internal network | one or more servers with an 80 GB GPU |
| Review time | 8 to 12 minutes per job, CPU only (measured) | under a minute | under a minute |
| What you buy | nothing, or larger runners | one GPU desktop or Mac with 32 GB or more | GPU servers |
| When it fits | a pilot, a small team, public repos on free runners | most teams | many teams, or the higher precision is worth it |

Tier 1 is what you built in Module 4. Tiers 2 and 3 are the same workflow with one change: the job stops installing Ollama and calls the shared server instead.

```bash
OLLAMA_HOST=http://review-model.internal:11434 REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low \
  python reference-pipeline/review.py --diff pr.diff
```

## The shape of tiers 2 and 3

```
 pull request ──> CI job (diff, scanners, validation, comment)
                    │  internal network only, no internet egress
                    ▼
              model server (Ollama or vLLM, loopback or internal interface)
                    │  pulls models from an internal registry or cache only
                    ▼
              audit log store (treated like source code)
```

The bot is still the CI job. The model server only answers questions. Every control from Module 6 stays in the job, where you can test it: sanitizing, citation checks, evidence checks, escaping, the comment marker, the token.

## Scaling

- **Review the diff.** The capstone measured it: with the diff in focus, both models caught the access-control bug 3 of 3 times. Given the whole file, both missed it, even after reading the decorator, because two hardcoded secrets at the top took their attention. Diff reviews are faster and, here, more accurate. A whole-repository review is a separate scheduled job, not a pull request check.
- **Size for the peak hour, not the average.** The TCO model sizes servers from pull requests per peak hour and seconds per review.
- **Fail open, visibly.** A model call that runs past `timeout_seconds` stops the review with an error and posts nothing. The review job is non-blocking in both templates, so a busy server costs a comment, never a merge. Watch the failure rate: it is your capacity alarm.
- **One spare** if a dead server must not stop reviews.

## Model updates

A model update is a code change. It goes through the same gate as a prompt change.

1. **Pin.** Name the exact model tag in `config.toml`. Record its ID from `ollama list`, which is the start of the model's digest. `latest` is not a version.
2. **Measure before you switch.** Run the four gates in this repository against the candidate:
   - `python reference-pipeline/smoke.py`: the three scanner-reachable bugs.
   - `python eval-harness/score_planted.py` on a full review: all six planted bugs, plus the unmatched findings that become noise.
   - `python attack-lab/run_attack.py --reps 3`: every Module 5 attack, unhardened and hardened.
   - `python eval-harness/capstone.py`: the bug that needs repo-read.
3. **Compare, then promote.** Switch only if the candidate is no worse on all four. Keep the previous model on the server for a fast rollback.
4. **Re-run on every prompt change too.** In October 2026 a sharper triage prompt fixed one false negative. Without the gates it could as easily have caused one.

The Module 2 bake-off is this process done once by hand.

## Monitoring

The audit log already holds what you need. Count these per week:

| Signal | Where it comes from | What a change means |
|---|---|---|
| Findings per pull request | the posted comment | a jump after a model or prompt change is noise until proved otherwise |
| Dropped findings | `review.py` warnings: no citation, evidence not on the cited lines, file not read | rising drops mean the model is guessing more |
| Developer dismissals | reactions or a "not a bug" label on the comment | the real false-positive rate, the one in the TCO model |
| Review time | the CI job duration | sizing, and runaway reasoning settings |
| Repo-read requests and refusals | audit records whose prompt is a short `file: symbol` request, and answers starting `refused:` | reads unrelated to the diff, or refusals, are what a prompt injection steering the tool looks like; in Module 8 one steered the reads in 3 of 3 runs |
| Comments with no findings | the comment body | healthy when the code is clean; suspicious if it suddenly rises |

## Fixes and bypasses

Developers act on a finding in one of two ways, and the bot supports both in the pull request itself, on GitHub and GitLab:

- **Apply the fix.** `post_comment.py --suggest` posts a model-written fix on the finding's line, with the platform's one-click suggestion button. A person reviews it and applies it; nothing is committed automatically.
- **Disagree, with a record.** A bypass is an entry in `security-suppressions.toml`: what, why, who approved it, and when it expires. In CI the bot reads the file from the target branch, so a bypass counts only after its own review. Suppressed findings stay in the comment, in their own table.

Replying in the thread ("/dismiss") is the other common pattern. It needs a comment-triggered workflow on GitHub, which runs with write access and must never run the pull request's code, and a webhook service on GitLab. Module 7 walks through why suppressions as code reach the same outcome more safely.

## Cost

Open [`tco-model.xlsx`](tco-model.xlsx). Change the yellow cells on the Inputs sheet. With its placeholder inputs (200 developers, 3 pull requests each a week), the three self-hosted tiers cost between about $30,000 and $95,000 over three years, and per-seat SaaS about $300,000. Developer time triaging findings, about $160,000 a year, is larger than any tool. A bot's precision is a cost line.

These numbers are only as good as the yellow cells. Replace them before you show them to anyone.
