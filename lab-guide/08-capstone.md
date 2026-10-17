# 08. Capstone

One pull request, two bot configurations. The pull request adds an invoice endpoint protected by `@auth.require_order_access`. Read on its own, the endpoint is correct. The decorator, in another file, checks only that someone is logged in, never that they own the order. Any logged-in user can read any invoice.

Which bot catches it?

| Configuration | What the bot sees |
|---|---|
| **Diff only** | The changed lines, with the rest of `app.py` as context |
| **Diff + repo-read** | The same, plus up to four functions it chooses to read elsewhere in the repository |

All commands run from the repository root with the environment active.

## 1. Read the pull request yourself first

```bash
python -c "import sys; sys.path[:0]=['eval-harness','attack-lab']; import capstone; print(capstone.ENDPOINT)"
```

Before you run anything: is this endpoint safe? What would you need to read to be sure?

## 2. Score both configurations

```bash
python eval-harness/capstone.py
```

It applies the pull request in a temporary copy (your checkout is never changed), reviews the diff three times with each configuration, and counts a catch only if a finding's title names broken access control on the endpoint or the decorator.

**What we measured**, three runs each, October 2026:

| Model | Diff only | Diff + repo-read |
|---|---|---|
| `qwen3.5:9b` | 0 of 3 | **3 of 3** |
| `gpt-oss:20b` | 0 of 3 | **3 of 3** |

Run it with GPT-OSS if your laptop can:

```bash
REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low python eval-harness/capstone.py
```

On Codespaces or a CPU-only laptop, use `--reps 1`.

## 3. Watch the tool work

Make the change in your own checkout and save the diff:

```bash
python -c "import sys, pathlib; sys.path[:0]=['eval-harness','attack-lab']; import capstone; pathlib.Path('pr.diff').write_text(capstone.apply_pull_request(pathlib.Path('.'))[0])"
```

Review it with repo-read, logging every model call and every read:

```bash
REVIEW_AUDIT_LOG=audit-capstone.jsonl python reference-pipeline/review.py --diff pr.diff --no-scanner --repo-read
python -c "import json; [print('read', r['user_prompt']) for r in map(json.loads, open('audit-capstone.jsonl')) if '\\n' not in r['user_prompt']]"
```

**You should see** reads like `target-app/auth.py: require_order_access` and `target-app/models.py: get_order`, and a finding such as "Broken Access Control: User can access any order via IDOR vulnerability" on the endpoint.

Now the same diff without repo-read:

```bash
python reference-pipeline/review.py --diff pr.diff --no-scanner
```

Read the explanations closely. In our runs the diff-only bot reported side issues (response contents, error handling) and wrote that the decorator "ensures only authorized users" can reach the order. It trusted the name.

Put your checkout back:

```bash
git checkout target-app/app.py
rm -f pr.diff audit-capstone.jsonl
```

## 4. What the tool is allowed to do

The repo-read tool is the first time the model can choose what the bot does next. Its limits are enforced in code (`read_symbol()` in `review.py`):

- read-only, and only named functions and classes, never a whole file
- only inside the reviewed file's folder (`target-app/`), Python only
- never test files or excluded paths
- at most four reads, at most 80 lines each
- sanitized when sanitizing is on, and every read is audited

Try to break it. Ask for `target-app/../reference-pipeline/review.py`, a test file, or a name that does not exist:

```bash
python -c "
import sys; sys.path.insert(0, 'reference-pipeline')
import review
cfg = review.load_config(); scope = review.repo_scope('target-app/app.py')
for f, s in [('target-app/../reference-pipeline/review.py', 'main'), ('target-app/tests/conftest.py', 'login'), ('target-app/auth.py', 'nope')]:
    print(review.read_symbol({'file': f, 'symbol': s}, scope, cfg)[1])
"
```

**You should see** two refusals and a "not found."

## 5. The tool reopens Module 5

In Module 5 the exfiltration attack failed because the bot only saw one file. The repo-read tool lets the model open other files. So we ran that attack again with repo-read on, three runs each:

| | Model read `app.py`, where the token is | Token leaked into a finding |
|---|---|---|
| Sanitizing off | **3 of 3**: the attacker's comment steered the tool | 0 of 3 |
| Sanitizing on | 0 of 3: the comment never reached the model | 0 of 3 |

The attacker controlled what the tool read. The token still did not leak, for one reason only: the tool returns named functions, and the token is a module-level variable. Change the tool to return whole files and that protection is gone.

## 6. The whole app, fully hardened

The capstone reviewed one small diff. Now review the whole target app the way a scheduled job would: scanners plus a cold review with repo-read, sanitizing on, then score against all six planted bugs.

```bash
REVIEW_SANITIZE=1 python reference-pipeline/review.py --file target-app > scanner.json
REVIEW_SANITIZE=1 python reference-pipeline/review.py --file target-app --no-scanner --repo-read > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

The scorer pools both files, lists each planted bug as found or missed, and lists every finding that matched no planted bug. Some of those are real extra issues, some are noise. Deciding which is the exercise. Then run the same two reviews without `REVIEW_SANITIZE=1` and compare.

**What we measured** with `qwen3.5:9b`, three runs each, October 17, 2026:

| | Planted bugs found | Unmatched findings |
|---|---|---|
| Not sanitized | 4 of 6, every run | 1 |
| Sanitized | 5 of 6, every run | 0 |

Three things to notice:

- **BOLA was missed in every run, both ways.** Given the whole of `app.py`, the model read `require_order_access` and still reported only the two hardcoded secrets at the top of the file. `gpt-oss:20b` did the same. The capstone diff caught it 3 of 3 because the question was narrow. Focus beat context.
- **The cold review skips test files.** The security tests describe the bugs they test, and an earlier version reviewed them: 2 of its 4 unmatched findings were in test files, and with sanitizing on, 7 of 8, because sanitizing removed the docstrings that said they were tests. The scanners still check test files.
- **Temperature 0 is not reproducibility.** Earlier the same day, the unsanitized review found the path traversal in `storage.py` in 2 of 2 runs. Later, with no change to that file's prompt, it missed it 3 of 3. The model server's state differs between sessions. Score over several runs, and compare runs made in the same session.

A full review takes about 2 minutes on an M5 Max. On Codespaces, review one file at a time with `--file target-app/storage.py`.

Clean up when you are done:

```bash
rm -f scanner.json sweep.json
```

## Discussion

- Repo-read caught a bug no scanner and no diff-only review found. What did it cost? (Time, an extra model call, a new attack surface.)
- The exfiltration attack steered the tool in 3 of 3 runs. What would you add to the checklist for any bot that can choose its own reads?
- The capstone counts a catch only by title. Is that fair? What would a stricter or a looser scorer change?
- The whole-app review missed the bug the diff review caught. What does that say about scheduled full-repository scans?
- Of everything in the two days, what would you actually run on your team's pull requests on Monday?

## Instructor notes

- `eval-harness/capstone.py` takes about a minute for three runs of both configurations with `qwen3.5:9b` on an M5 Max (one review is about 10 seconds). Budget 5 to 10 minutes per configuration on Codespaces.
- If a model scores diff-only above zero, read the finding: earlier versions of the scorer counted explanations that mentioned "authorized" while trusting the decorator.
- Group comparison: collect each table's `capstone.py` result on the board, by model and by laptop.
