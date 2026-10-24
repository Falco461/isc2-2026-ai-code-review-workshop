# From Zero to Security Bot

Building and Hardening an AI-Powered Code Review Pipeline.

Workshop materials for the ISC2 Security Congress 2026 two-day hands-on workshop. You build a code review bot that runs entirely on your own laptop, wire it into CI, attack it, and harden it.

**Status:** Workshop preparation in progress. Final lab guide published after October 2026.

## What this is

A reference implementation and lab guide for security engineers who want LLM-assisted code review in their pipelines without sending code to a vendor.

The bot consumes the scanner output you already have. Bandit and detect-secrets findings go in, and triaged, explained, prioritized review comments come out, each one citing a real file and line. SARIF is the input contract, so anything that emits SARIF (Semgrep, CodeQL, gitleaks) works the same way.

Everything runs on an open-weight model served locally by Ollama. No cloud, no API keys, no paid tiers, no Docker.

## What you leave with

- A working review pipeline you can fork into your own GitHub Actions or GitLab CI setup, on the free tier, with templates provided.
- Three anti-hallucination patterns enforced in code, not just in prompts: every finding cites a file and line, the model checks its output against the context it was given, and reporting nothing is a valid answer.
- Hands-on experience attacking an LLM review bot: prompt injection through comments and commit messages, false-negative manipulation, exfiltration, resource exhaustion.
- A hardening checklist and a total cost of ownership model for self-hosted versus commercial.

## The model

The attendee path is an open-weight model running on your laptop through Ollama. The default is `qwen3.5:9b` with reasoning turned off. It is 6.6 GB and fits a 16 GB laptop.

Module 2 deploys OpenAI's open-weight `gpt-oss:20b` through Ollama and compares it with the default on the same code. It is 13 GB and needs about 24 GB of RAM to run comfortably, so on a 16 GB laptop you watch the instructor run it rather than run it yourself.

Both are reasoning-capable models. The bot sets reasoning explicitly for each one (`think` in `config.toml`), because a reasoning model left on its default spends minutes thinking before it answers. Measurements are in `docs/MODEL_EVAL.md`, and comparing models is itself a Day 1 lab.

The 120B-class self-hosted tier is not something you run on a laptop. It appears in Module 7 as the scale-up reference architecture.

## Get started

Follow [`lab-guide/00-setup.md`](lab-guide/00-setup.md): clone this repository, run the setup script, and see `SMOKE TEST PASSED`. Every lab is in [`lab-guide/`](lab-guide/).

## Two-day outline

Both days run 8:00 AM to 5:00 PM with an hour for lunch and two breaks.

### Day 1

| Time | Module |
|---|---|
| 8:00 | Setup check and introductions |
| 8:30 | **1. The Landscape.** Where LLM code review actually helps, where it does not, and what model size buys you. |
| 9:45 | Break |
| 10:00 | **2. Model Deployment.** Lab: get a model running on your own machine, then compare a small and a large model on the same finding. |
| 11:30 | Lunch |
| 12:30 | **3. Building the Security Bot.** Lab: read scanner results, triage them through the model, produce a review comment. |
| 14:15 | Break |
| 14:30 | **3, continued. Making the bot trustworthy.** Citation-required, chain-of-verification, refuse-over-guess, enforced in code rather than asked for in the prompt. |
| 15:15 | **4. CI/CD Integration.** Lab: the bot runs in a live pipeline against a commit with planted vulnerabilities, non-blocking. |
| 17:00 | End |

### Day 2

| Time | Module |
|---|---|
| 8:00 | Recap |
| 8:15 | **5. Attacking Your Own Bot.** Prompt injection via comments and commit messages, false-negative manipulation, exfiltration, resource exhaustion. Lab: attack each other's bots. |
| 10:00 | Break |
| 10:15 | **6. Defenses and Enterprise Hardening.** Input isolation, output validation, secret management, network segmentation, audit logging, rate limiting. |
| 11:45 | Lunch |
| 12:45 | **7. Production Architecture.** Scaling, the 120B-class tier, model update strategy, monitoring, and the TCO model. |
| 14:15 | Break |
| 14:30 | **8. Capstone.** A hardened bot against a realistic vulnerable codebase, scored on bugs no scanner catches. |
| 16:30 | Group comparison and wrap |

## Prerequisites

Please complete all of this **before you travel**. The model download is several gigabytes and conference wifi will not be kind to it.

### Hardware

- **16 GB of RAM minimum.** 32 GB recommended. An 8 GB machine will not work, so please do not plan to bring one.
- **About 12 GB of free disk space** for the model, Python, and the workshop repository. Add 13 GB if you also pull `gpt-oss:20b`.
- A discrete GPU or Apple Silicon is recommended but not required. On a CPU-only laptop the bot still works, it just thinks out loud slowly: expect a minute or two per review instead of a few seconds.

### Operating system

Any one of these:

- macOS 13 Ventura or newer, Apple Silicon or Intel. Apple Silicon is the smoothest path.
- Linux, Ubuntu 22.04 or newer or equivalent.
- **Windows:** PowerShell works (Path C in `lab-guide/00-setup.md`), and so does WSL with Ubuntu (Path A). Every PowerShell command is on one page: [`lab-guide/WINDOWS-CHEATSHEET.md`](lab-guide/WINDOWS-CHEATSHEET.md).
- **Any laptop you cannot install software on:** use a GitHub Codespace in your browser instead. It is a Linux machine with everything preinstalled, and it needs only a free GitHub account. It has no GPU, so reviews are slower: about 1 to 2 minutes per file. See `lab-guide/00-setup.md`.


### Software

You need the ability to install software on the laptop you bring. None of the tools below require administrator rights, but some corporate device management blocks installers outright. Please check this before the event, because there is no way to fix it in the room.

1. **Python 3.11 or newer.** Check with `python3 --version`. If it is missing or older, install from [python.org/downloads](https://www.python.org/downloads/).
2. **Git.** Check with `git --version`. If it is missing, install from [git-scm.com/downloads](https://git-scm.com/downloads).
3. **A GitHub or GitLab account.** The free tier is all you need. You will push a small repository and open a pull or merge request against it.
4. **Ollama.** Download from [ollama.com/download](https://ollama.com/download) and install it. Check with `ollama --version`.

### Pull the model before you travel

With Ollama installed and running:

```bash
ollama pull qwen3.5:9b
```

That is about 6.6 GB. If your laptop has 24 GB of RAM or more, also pull the Module 2 model, which is about 13 GB:

```bash
ollama pull gpt-oss:20b
```

Confirm the download worked:

```bash
ollama list
```

You should see the model you pulled. If the list is empty, the pull did not finish, so run it again on a stable connection.

### If your laptop cannot run the model

Two fallbacks, in order.

**1. Use the previous default.** `qwen2.5-coder:7b` is 4.7 GB instead of 6.6 GB and has no reasoning mode. It finds the same bugs on most of the Day 1 path, with one known miss: in triage it rates a hardcoded API token as informational. That miss is discussed in Module 3. Pull it and point the tooling at it:

```bash
ollama pull qwen2.5-coder:7b
export REVIEW_MODEL=qwen2.5-coder:7b
```

**2. Pair with a neighbour.** The labs work fine with two people at one machine, and Day 2 involves attacking each other's bots anyway.

The tooling also reads `OLLAMA_HOST`, so it can point at a model served from another machine if you have one available:

```bash
export OLLAMA_HOST=http://<address>:11434
```

That is a mechanism, not a promise. Plan on your own laptop running the model.

## Structure

- `reference-pipeline/` Working review bot: setup scripts, CLI, comment poster, smoke test, and tests
- `target-app/` Intentionally vulnerable Flask application used throughout the labs, with its answer key in `PLANTED.md`
- `prompts/` Prompt templates with documentation
- `ci-templates/` GitHub Actions and GitLab CI templates for free runners, and the Module 4 practice patch
- `attack-lab/` Module 5 attacks on the bot, run unhardened and hardened
- `defense-patterns/` The hardening checklist, the take-home deliverable
- `production/` Module 7 reference architecture and the TCO model (`tco-model.xlsx`)
- `eval-harness/` Module 8 capstone scoring and the planted-bug scorer
- `instructor/` Copying models to USB drives for offline installs
- `lab-guide/` Step-by-step instructions for every module
- `.devcontainer/` GitHub Codespaces setup, for Windows and anyone without a capable laptop
- `docs/` Build brief, model evaluation, and the proposal of record
- `slides/` Workshop slides (published after delivery)

## Topics

AI security, code review, DevSecOps, GitLab CI, SAST, LLM security, ISC2.

## License

Apache 2.0. See [LICENSE](LICENSE).
