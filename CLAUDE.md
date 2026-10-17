# CLAUDE.md

Project: ISC2 Security Congress 2026 workshop, "From Zero to Security Bot: Building and Hardening an AI-Powered Code Review Pipeline." Two-day hands-on workshop, Oct 24-25, 2026, 8 AM to 5 PM each day. Attendees build a laptop-local LLM code review pipeline, wire it into CI, break it on Day 2, and harden it. Everything in this repo is workshop material an attendee will run on their own machine.

## The submission is the contract

`docs/PROPOSAL_AS_SUBMITTED.md` records what ISC2 has published and what Bradley signed off on in May 2026. Check work against it. Anything in this repo that contradicts a published takeaway, module, or deliverable is drift, and drift gets fixed here, not in the submission. If a change genuinely needs the submission to move, say so and name what Bradley has to be told.

Audience level as published: Mid, 4 to 9 years. Track: Engineering/Architecture.

## Who the code is for

- Security engineers who are comfortable in a terminal and have never run a local model.
- Attendee laptops: mostly Windows 11 corporate machines, then macOS on Apple Silicon, some Linux. Baseline assumption: 16 GB RAM, no admin rights.
- Presentation and demo machine: MacBook Pro M5 Max 48 GB (macOS), upgraded October 2026 for the talk and the workshop. It runs `gpt-oss:20b` live for Module 2.
- Other test machines: Dell XPS 15 32 GB (Windows 11), Kubuntu desktop (Linux). The M5 Max is far faster than an attendee laptop, so time anything quoted to attendees on a 16 GB machine.

## Design decisions

Settled May 2026. Revised September 2026 only where measurement contradicted them. A decision here is not reopened on opinion. It is reopened when a test says it is wrong, and the test goes in the commit message.

- Eight modules, whole numbers only: (1) The Landscape, (2) Model Deployment, (3) Building the Security Bot, (4) CI/CD Integration, (5) Attacking Your Own Bot, (6) Defenses and Enterprise Hardening, (7) Production Architecture, (8) Capstone. Day 1 is modules 1 through 4. Day 2 is modules 5 through 8, four each day.
- The anti-hallucination patterns are part two of Module 3, not a module of their own. There is no Module 3.5. Citation-required, chain-of-verification, and refuse-over-guess are how the bot built in Module 3 is made trustworthy, and they are enforced in `review.py`, which is the thing Module 3 builds. Splitting them out produced a half-numbered module that read as an afterthought.
- The attendee path is an open-weight coder model via Ollama, laptop-local. The 120B-class self-hosted tier appears only as the Module 7 scale-up reference architecture.
- **Scanner output is the primary input to the bot.** The published takeaway promises a bot that consumes existing SAST and secret-detection output and turns it into an actionable review comment. Scanner findings in, triaged and explained findings out. Freeform review of raw code is the secondary path, not the headline.
- The input contract is SARIF. Bandit emits it via `bandit-sarif-formatter`, and so do Semgrep, CodeQL, and gitleaks, which is what makes the bot portable to whatever attendees already run at work.
- Grounded retrieval: the bot gets a repo-read tool as a first-class input and fetches the slice of code it asks for. No whole-repo dumps. This is where the model earns its keep, on the BOLA that no scanner catches.
- Three anti-hallucination patterns are taught and enforced in code, not just in prompts: citation-required (every finding cites file and line), chain-of-verification (the model checks its output against the provided context), refuse-over-guess (no findings is a valid, first-class answer).
- Capstone: the same vulnerable codebase reviewed by two bot configurations, diff-only vs diff plus repo-read, scored on planted BOLA bugs.
- No cloud, no API keys, no paid tiers. **No container runtime is a prerequisite**, and nothing in the workshop needs one.
- **ISC2 publishes no prerequisites for this workshop.** Checked September 2026: the public listing is one descriptive paragraph, with no technical requirements, no Docker, no Python version, no hardware floor. An earlier note in this repo claimed Docker Desktop was a submitted prerequisite. That claim came from a session summary, was never verified, and nothing public supports it. Treat it as unproven.
- That means the Prerequisites section of `README.md` is not reconciling against a published list, it **is** the list. It is the only prerequisites document that exists, so whatever it says is what attendees will be told. Write it accordingly.
- If a later module genuinely needs a container, for example sandboxing the bot in Module 6 or the scale-up architecture in Module 7, **use Podman, not Docker**. Rootless, no daemon, no licensing question on a work machine. Ask before it becomes a prerequisite rather than a demo.

## Model tiers (measured October 2026)

Bake-off on the real pipeline against `target-app`, three reps per model, triage and cold review, temperature 0, JSON-schema-constrained decoding. Numbers live in `docs/MODEL_EVAL.md`. Measured on an M5 Max; time the default on a 16 GB machine before quoting laptop speeds.

- **Default is `qwen3.5:9b` with `think = false`.** It escalated every scanner-reachable planted bug in triage (SQL injection, both hardcoded secrets, command injection) and found the same four cold. 6.6 GB, fits 16 GB.
- **`gpt-oss:20b` with `think = "low"` is the Module 2 model**, because the published description names GPT-OSS. It cannot turn reasoning off, so it needs a level. It was the only model that found path traversal cold, with the fewest and most precise findings. 13 GB, needs about 24 GB RAM.
- **`qwen2.5-coder:7b` is the low-memory fallback.** It rates the hardcoded reporting token in `app.py` as info in every triage run, a real false negative.
- **`qwen2.5-coder:3b` is no longer a triage tier.** On the current prompt it drops the hardcoded secret key and escalates a known false positive. Do not recommend it.
- **Reasoning models only with reasoning set explicitly.** `think` in `config.toml` (or `REVIEW_THINK`) is always set. A reasoning model left on its default, like `qwen3:4b` in September, takes minutes per review.
- Every newer model escalates the `auth.py` false positive that the 7B dismisses. That is prompt work, and the before and after numbers are Module 3 content.
- Cisco Foundation-Sec 8B (security-trained) found the reachable bugs cold but at 19 to 20 findings per run, and dropped the secret key in triage. Security training is not code reading; useful Module 1 discussion, not a default.

Hardware honesty for the prerequisites, which go to ISC2 verbatim: 16 GB RAM minimum, no 8 GB machines, GPU or Apple Silicon recommended, model pre-pulled before travel. A CPU-only Windows laptop produces a few tokens per second, so state plainly that a review takes a minute or two there.

**There is no instructor-hosted fallback server.** The M5 Max is the presentation machine and is busy presenting, and no laptop can serve a room over conference wifi. The attendee-facing docs must not promise one.

The fallback story is `qwen2.5-coder:7b` (4.7 GB, no reasoning mode) plus pairing. The 3B tier is retired: on the current prompt it drops a real secret in triage. `OLLAMA_HOST` stays documented as a mechanism for anyone who has another machine, and is described as a mechanism, never as something provided in the room.

## Standing rules

- Python 3.11 minimum, because that is what ISC2 published as the prerequisite. Attendee-facing docs say 3.11 or newer and nothing stricter. CI tests the 3.11 floor on all three operating systems and also tests 3.14, so forward breakage is caught. Dev machines run 3.14. Code must run on both, so no syntax or stdlib newer than 3.11.
- Always a venv (`python -m venv .venv`). Never system pip. Every setup path and every doc shows venv creation and activation for both bash and PowerShell.
- Cross-platform is a hard requirement: pathlib for paths, no `shell=True`, no bash-isms inside Python, line endings handled. Anything that works on one OS only is a bug.
- Minimal pinned dependencies: requests, bandit, bandit-sarif-formatter, detect-secrets, flask, pytest. Ask before adding anything else.
- Scanners are Bandit for SAST and detect-secrets for secret detection. Both are pip-installable, pure Python, and run on Windows. They are complementary: Bandit caught both planted secrets via B105, detect-secrets caught one of them plus classes Bandit has no rule for. Semgrep is an optional add-on later; verify its native Windows status before it appears in any prerequisite.
- **detect-secrets fails silently in two ways, and both return an empty result rather than an error.** Every code path and doc must handle them.
  1. A directory scan only covers files that git already tracks. Point it at a directory of new, uncommitted files and it reports nothing. Pass `--all-files` to scan the working tree, and exclude `.venv`, `.pytest_cache`, and other noise explicitly, because `--all-files` does not honor `.gitignore`.
  2. It only reports files whose path resolves under the current working directory. An absolute path to a file outside cwd returns nothing. Run it from the repo root and pass repo-relative paths.
- Because a silent empty result is indistinguishable from a clean scan, `review.py` must assert that a scanner actually examined the files it was given and fail loudly when the count is zero.
- LLM access is Ollama's HTTP API called directly with requests. Base URL from `OLLAMA_HOST` (default `http://127.0.0.1:11434`). Model name from `config.toml`, overridable by `REVIEW_MODEL`. Changing the default stays a one-line change.
- Structured output: pass a full JSON schema to Ollama's `format` field, not the string `"json"`. Schema-constrained decoding produced valid output on every run of every model tested, where asking for JSON in the prompt produced malformed arrays and wrong enum casing. Validate in code anyway, and drop anything that fails validation with a logged warning.
- No em dashes anywhere: docs, comments, strings, commit messages. Use commas, colons, or parentheses instead.
- Attendee voice in all docs: short sentences, every command shown for bash (macOS, Linux, and Codespaces; there is no native Windows path), every error message names the fix.
- Git: one commit per deliverable, descriptive messages, no force push, never modify LICENSE. Run the smoke test before any commit that touches code.

## Phase order

Phase 1 is `docs/BUILD_BRIEF.md`. Do not start Phase 2 work unless asked.

Promised in the submission and therefore Phase 2 work, not optional extras:

- GitLab CI template alongside the GitHub Actions one. Both CI systems were promised, on free tier, with templates provided.
- Posting the review back as a comment on the PR or MR. The Module 3 lab as submitted ends with a comment on the PR, not JSON on stdout.
- Practice repositories with planted bugs that attendees push to their own GitHub or GitLab account, so they see findings land in the PR or MR interface rather than only in a terminal.
- A hardening checklist deliverable.
- A TCO model for self-hosted versus commercial, which is the third published takeaway.

Phase 2 status, October 17, 2026: all of the above is built and tested, plus the Module 5 attack lab, Module 6 defenses (sanitizing, audit log, evidence check), the Module 8 repo-read tool and capstone, the Module 7 architecture page and TCO workbook, Codespaces, and lab guides 00 to 08. Branch `phase2/model-update` merges to main on October 21. The TCO workbook is built by a script kept in the project folder, not this repository.
