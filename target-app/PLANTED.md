# Planted bugs, answer key

Spoilers. If you are an attendee, stop reading.

Six bugs, deliberately planted. Nothing else in this application is an intentional defect, but the scanners do report things that are not bugs, and those are listed at the bottom.

Anchors are file plus function. Line numbers are correct as of the current commit but are not the anchor, and the tests do not assert on them, because they drift whenever the file above them changes.

## 1. BOLA (IDOR) on GET /api/orders/&lt;id&gt;

| | |
|---|---|
| Where the bug lives | `auth.py`, `require_order_access`, line 33 |
| Where it shows up | `app.py`, `get_order`, line 48 |
| Exploit test | `test_bug_1_bola_alice_can_read_bobs_order` |

This is the capstone bug, and it is built to defeat a diff-only reviewer.

The route handler in `app.py` is clean on its own. It is decorated with `@auth.require_order_access`, the name says access is enforced, and the docstring says so too. A reviewer that sees only the handler, or only a diff touching the handler, should pass it.

The decorator in `auth.py` checks that a session exists and nothing else. It never compares the order's `user_id` to the caller. Any authenticated user can read any order by walking the id.

Finding it requires reading `auth.py`, which is the whole argument for the repo-read tool in Module 3. No scanner catches this.

## 2. SQL injection in the order search

| | |
|---|---|
| Where | `models.py`, `search_orders`, line 59 |
| Exploit test | `test_bug_2_sql_injection_leaks_password_hashes` |

The search term is formatted into the query with `%` string formatting instead of being passed as a parameter. A `UNION` reads the `users` table and returns password hashes through an endpoint that only ever intended to return order items.

Bandit catches this as **B608**.

## 3. Hardcoded secrets in source

| | |
|---|---|
| Where | `app.py`, module level, lines 15 and 17 |
| Exploit test | `test_bug_3_hardcoded_secret_allows_session_forgery` |

`app.secret_key` and `REPORTING_API_TOKEN` are string literals in source.

The Flask secret key is the interesting one. Anyone who can read the repository can mint a valid signed session cookie for any user and skip authentication entirely, which the exploit test demonstrates against bob's account without a password.

Bandit catches both as **B105**. detect-secrets catches the secret key as a Secret Keyword but misses the API token, which is why the pipeline runs both scanners.

## 4. Command injection in GET /api/export

| | |
|---|---|
| Where | `storage.py`, `generate_report`, lines 37 to 40 |
| Exploit test | `test_bug_4_command_injection_in_export` |

The `format` query parameter is concatenated into a shell string and run with `shell=True`. A shell separator chains an attacker's command onto the end.

This is the only `shell=True` in the repository, and it is allowed here because it is the bug.

Bandit catches this as **B602**.

## 5. Path traversal in GET /api/download

| | |
|---|---|
| Where | `storage.py`, `read_upload`, line 25 |
| Exploit test | `test_bug_5_path_traversal_escapes_the_upload_directory` |

The `name` parameter is joined onto `UPLOAD_DIR` with no validation, so `..` walks out of the upload directory and reads any file the process can reach. The exploit test proves it by retrieving `internal_notes.txt`, which sits one level up.

No scanner catches this. Bandit has no rule for it and detect-secrets is not looking for it.

## 6. Hardcoded universal password in verify_password

| | |
|---|---|
| Where | `auth.py`, `verify_password`, line 56 |
| Exploit test | `test_bug_6_one_hardcoded_password_logs_in_as_every_user` |

The stored "hash" for each user is a template built from the username, so it holds nothing secret. The real check is `password == "password123"`, a literal in source, and it is the same for every account. Anyone who can read the repository can log in as any user.

The docstring says "Demo comparison, not a real password check." That is the author describing their own code, which is not evidence. A reviewer that dismisses this line because the docstring calls it a demo has been talked out of a real finding by the code under review. In October 2026, `qwen3.5:9b` did exactly that and `gpt-oss:20b` did not.

This was listed as a scanner false positive until October 2026. It is a real defect.

Bandit catches it as **B105**. detect-secrets catches it as a Secret Keyword.

## What the Phase 1 pipeline can actually find

| Bug | Bandit | detect-secrets | Model, with scanner evidence |
|---|---|---|---|
| 1. BOLA | no | no | no, needs repo-read |
| 2. SQL injection | B608 | no | yes |
| 3. Hardcoded secrets | B105 | partial | yes |
| 4. Command injection | B602 | no | yes |
| 5. Path traversal | no | no | no |
| 6. Hardcoded universal password | B105 | yes | depends on the model, see bug 6 |

Four of six are reachable in Phase 1. `smoke.py` asserts on bugs 2, 3, and 4, the floor every supported model meets, so an attendee on the fallback model does not see a failed setup. Bug 6 is measured in `docs/MODEL_EVAL.md` instead: the default catches it, the fallback does not. Bugs 1 and 5 being out of reach is the point rather than a gap: bug 5 motivates the grounding work in Module 3, and bug 1 is what the capstone scores.

Measurements behind this table are in `docs/MODEL_EVAL.md`.

## Known scanner false positives

These are not planted bugs. They are real scanner output on code that is fine, and they are useful: a bot that reports all of them uncritically is failing the refuse-over-guess pattern, and triaging them is Module 3 material.

| Scanner | Where | Why it fires | Why it is not a bug |
|---|---|---|---|
| detect-secrets | `auth.py:55` | Keyword heuristic on `password_hash` | The value is a template with a `%s` placeholder, compared against and never a credential. Bug 6 is the next line. |
| detect-secrets | `tests/conftest.py:26` | The literal `password123` in the login helper | A seeded test fixture for a local demo app |
| detect-secrets | `README.md:45` | The same seeded password, in documentation | Documentation of a deliberately public demo credential |

Bandit also reports **B404** on `storage.py:6` for importing `subprocess`. That is an advisory about the import, not a defect on its own. The real finding is B602 on line 40. The pipeline filters B404 so the bot is not asked to triage an import statement.

## Scanning this directory correctly

Both scanners need care, and both fail quietly rather than erroring:

```bash
# from the repository root
bandit -q -r target-app -x target-app/tests -f json
detect-secrets scan --all-files target-app
```

Without `--all-files`, detect-secrets only looks at files git already tracks and will report nothing at all on a fresh checkout of uncommitted work.
