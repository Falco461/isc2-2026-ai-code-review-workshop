# Hardening checklist for an AI code review bot

Take this home. Every item says what the control is, why it matters, where this workshop's bot does it, and how to check yours. Items marked **(attack)** were measured against the Module 5 attacks.

The one principle behind all of them: **the code under review is written by the person you are checking.** Everything the model reads from a pull request is attacker-controlled input.

## 1. Input sanitization

- [ ] **Strip author text before the model sees it.** Comments, docstrings, and bare strings are claims the author makes about their own code. Replace them with a placeholder and keep line numbers fixed. **(attack)** A docstring that called `app.py` test fixtures dropped two real secrets from high to info in 3 of 3 runs. With sanitizing on, the bot held in 3 of 3, and no real bug was lost.
  - Here: `sanitize_source` in `reference-pipeline/config.toml`, `sanitize_python()` in `review.py`.
  - Check: `REVIEW_SANITIZE=1 python review.py --file <file> --dry-run` shows the placeholders.
- [ ] **Compute trusted context outside the model.** "This is test code" comes from the file path, never from the file's contents.
- [ ] **Keep test files out of the cold review.** Security tests describe the bugs they test. Reviewed cold, they come back as findings in the test file. In October 2026 they were 2 of 4 unmatched findings on a full review, rising to 7 of 8 with sanitizing on, because sanitizing removed the docstrings that said they were tests. The scanners still check test files for real committed secrets.
  - Here: `looks_like_test_code()` in `review.py`.
- [ ] **Treat the prompt as a request, not a control.** The prompt already said not to trust a file's self-description, and the model trusted it anyway. Put the control in code.

## 2. Output validation

- [ ] **Require a citation.** A finding with no real file and line is dropped, not posted.
  - Here: `validate_finding()`. Check: Module 3, "Citation required".
- [ ] **Constrain the shape.** Pass a full JSON schema to the model, then validate in code anyway. A schema constrains shape, not truth.
- [ ] **Allow "no findings."** An empty result with a reason is a first-class answer, so the model is never pushed to invent one.
- [ ] **Escape what you render.** The comment repeats what the model wrote about code the pull request author controls. Strip HTML, pipes, and newlines, and cap the length before it becomes Markdown.
  - Links and `@mentions` too. The model writes the title and explanation, and the author's code can steer what it writes. The workshop's `escape()` deliberately lets both through; Module 6 closes the gap. Remember that bare URLs autolink.
  - Here: `escape()` in `post_comment.py`, with tests for a hostile explanation.
- [ ] **Watch for duplicates.** With sanitizing on, one finding can be widened to cover the bug on the next line and reported twice. Decide whether to merge overlapping findings.

## 3. Secret management

- [ ] **Least-privilege CI token.**
  - GitHub: the workflow grants only `contents: read` and `pull-requests: write`.
  - GitLab Free: a fine-grained personal access token with only `read_work_item`, `create_work_item`, `update_work_item`, and no repository permissions. Tested: posts and edits the comment.
- [ ] **Masked, short-lived, not protected.** Mask the CI variable, set an expiry, and know why it cannot be protected on merge request branches.
- [ ] **Know what the token can still do.** GitLab's work item permissions also cover issues and epics. Write down the residual risk.
- [ ] **No secrets reach the model unless they are in the diff.** Without repo-read the bot reviews one file at a time. **(attack)** A comment asking the bot to quote a token from another file leaked nothing in 3 of 3 runs, because the bot never saw that file. With repo-read on, see item 4.

## 4. Network segmentation

- [ ] **The model listens on loopback only.** Ollama binds `127.0.0.1:11434` by default.
  - Check: `lsof -nP -iTCP:11434 -sTCP:LISTEN` shows `127.0.0.1`, not `*` or `0.0.0.0`.
  - Never set `OLLAMA_HOST=0.0.0.0` on a laptop on shared Wi-Fi.
- [ ] **No cloud inference.** The workshop model runs on the attendee's machine or inside the CI runner. Nothing is sent to a third-party API.
- [ ] **The model has no tools, or tools you can bound.** The bot calls the model; without repo-read, the model cannot call anything back. The capstone's repo-read tool changes this.
  - Bound it in code: read-only, named functions only, one folder, no test files, four reads, 80 lines each, every read audited.
  - **(attack)** With repo-read on and sanitizing off, the exfiltration comment steered the model into reading `app.py`, where the token is, in 3 of 3 runs. The token still did not leak, only because the tool returns functions and the token is a module-level variable. With sanitizing on, the comment never reached the model and it read `app.py` in 0 of 3 runs.
  - Sanitize what the tool returns, not only the file under review.
- [ ] **CI runner egress.** In production, the review job needs the model registry (or a cache) and the platform API, and nothing else.

## 5. Audit logging

- [ ] **Log every model call.** Model, settings, a hash of the exact prompt, the prompt, and the answer, so any verdict can be traced.
  - Here: `audit_log` in `config.toml`, or `REVIEW_AUDIT_LOG=audit.jsonl`.
- [ ] **Protect the log like source code.** It contains the code that was reviewed. `audit*.jsonl` is gitignored here.

## 6. Resource limits

- [ ] **Cap the output.** `max_findings` bounds the comment and the runtime.
- [ ] **Time out.** `timeout_seconds` bounds each model call. A reasoning model left on its default can take minutes per call; set `think` explicitly.
- [ ] **Review the diff, not the repository,** in CI. It is faster, and in the capstone it was also more accurate: with the diff in focus and repo-read on, both models caught the access-control bug 3 of 3 times; given the whole file, both missed it. The blind spot is code the diff does not touch: run a scheduled whole-repository review for that, and say so.

## 7. Human in the loop

- [ ] **Advisory only.** The bot never blocks a merge. Both templates are non-blocking.
- [ ] **Say so in every comment.** The comment ends with "Advisory only... A human reviews before anything ships."
- [ ] **One-click fixes are suggestions, never commits.** A suggested fix is model-written code from a model that read the attacker's code. Post it with the platform's suggestion button and let a person apply it. Reject patches that are empty, unchanged, fenced, or much longer than the lines they replace, and post advice without a button when there is no safe in-place fix.
- [ ] **Bypasses are code.** A suppression names the finding, a reason, who approved it, and when it expires, in a file reviewed like code. Suppressed findings stay visible in the comment.
  - Read the file from the target branch in CI, so a pull request cannot approve a bypass of its own findings.
  - `approved_by` is a record, not a login: protect the file with CODEOWNERS or code owner approval.
- [ ] **Be careful with comment-triggered workflows.** A bot that takes replies in the thread runs on a comment event with write access. Never check out and run the pull request's code in that job.

## 8. Supply chain and model provenance

- [ ] **Pin dependencies.** `reference-pipeline/requirements.txt` pins every package.
- [ ] **Pull models from a known registry, and record the digest.** `ollama list` shows the model ID. If a model changes under the same tag, your results change: re-run your evaluation.
- [ ] **Measure before you switch models.** A bigger or security-trained model is not automatically better. See `docs/MODEL_EVAL.md`.

## How to use this at work

Run the Module 5 attacks against your own bot with each control off, then on. A control you have not measured is a hope.
