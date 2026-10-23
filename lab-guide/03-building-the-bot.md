# 03. Building the Security Bot

Scanner findings go in. A cited, prioritized review comes out. Then the afternoon part: what makes it trustworthy enough to put in front of developers.

All commands run from `reference-pipeline/` with the environment active:

```bash
cd reference-pipeline
```

## Part 1. Run the bot

### 1. Review the whole target app

```bash
python review.py --file ../target-app > findings.json
```

On a Mac this takes under a minute. On Codespaces or a CPU-only laptop it takes much longer: review a single file instead (`--file ../target-app/app.py`) and pair with a neighbour for the full run.

### 2. Read the output

```bash
python -m json.tool findings.json
```

Every finding has a `file`, a `line_start`, the exact source line in `evidence`, a `severity`, and an `explanation`. **You should see about 8 findings, some of them marked `info`.**

Compare with your Module 1 answers. Which findings did the bot escalate, and which did it mark as false positives?

### 3. See exactly what the model was sent

```bash
python review.py --file ../target-app/models.py --dry-run
```

`--dry-run` prints the prompts without calling the model: the scanner finding, then the numbered source of the file. That is all the model sees. Nothing is hidden from you.

### 4. Turn it into a pull request comment

```bash
python post_comment.py findings.json --print
```

That is the comment the bot posts in Module 4. Notice that it says it is advisory and never blocks the merge.

## Part 2. Making the bot trustworthy

Three patterns, each enforced in code in `review.py`, not just asked for in the prompt.

### Citation required

Every finding must cite a real line. Try to sneak in a finding on a line that does not exist:

```bash
python -c "
import review
fake = {'severity': 'high', 'title': 'Made up', 'line_start': 999, 'line_end': 999,
        'evidence': 'nope', 'explanation': 'x', 'confidence': 'high'}
print('kept' if review.validate_finding(fake, 'target-app/app.py', line_budget=40) else 'dropped')
"
```

**You should see a warning and `dropped`.** A model that invents a line number does not get a comment.

### Refuse over guess

No findings is a valid answer. Review a file the scanners have nothing to say about:

```bash
python review.py --file ../target-app/db.py
```

**You should see `"findings": []` and a `no_findings_reason`.** The bot says why it is quiet instead of making something up.

### Do not trust the code's description of itself

Open `../target-app/auth.py` and read `verify_password` around line 50. The docstring says "Demo comparison, not a real password check."

Now look at line 56. Is it a real problem?

During the build of this workshop, the default model rated line 56 as `info` in 5 out of 5 runs and quoted that docstring as the reason. The prompt was changed so the model may not use the file's own comments as evidence. See the rule in `../prompts/review_system.md` under "Do not take the file's own word for it."

**Why it matters:** the author of the code under review writes the comments. A comment that says "this is fine" is the cheapest attack on a review bot there is. Day 2 starts here.

## Now open the answer key

```bash
less ../target-app/PLANTED.md
```

How many of the six planted bugs did the bot find? Which ones can no scanner and no model find without reading another file? That gap is the capstone.

Go back to the repository root before Module 4:

```bash
cd ..
```

## Going further: the prompt tournament

About 45 to 60 minutes, as tables. The scoring tool is the one Module 8 uses.

Your bot's behavior is mostly the prompt in `prompts/review_system.md`. Change it, and score the result against the six planted bugs:

```bash
cp prompts/review_system.md prompts/review_system.md.orig
# edit prompts/review_system.md
python reference-pipeline/review.py --file target-app > scanner.json
python reference-pipeline/review.py --file target-app --no-scanner > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

The scorer prints which planted bugs were found, every finding that matched no planted bug, and a score: **10 points per planted bug found, minus 2 per unmatched finding**. Noise costs you.

Rules:

1. Edit only `prompts/review_system.md`. No code changes.
2. Do not name the planted bugs or their lines in the prompt. A prompt that only works on this app is not a better prompt.
3. Keep the section headings: `review.py` loads each section by its heading.
4. Post your best score and one sentence on what you changed.

The unchanged prompt scored 36 points on the instructor's laptop (4 of 6 planted bugs, 2 unmatched findings), the same in two runs on October 23. Path traversal and broken access control are the bugs to win. A full scored run takes about 2 minutes on a fast laptop; on Codespaces it takes about 40, so pair with a laptop.

When you are done, put the original prompt back. Module 4 pushes the repository, and you want the original in CI:

```bash
mv prompts/review_system.md.orig prompts/review_system.md
rm -f scanner.json sweep.json
```

## Instructor notes

- Expected full-app findings with `qwen3.5:9b`: SQL injection, both secrets in `app.py`, command injection, and the universal password in `auth.py` escalated; the hash template on `auth.py:55` and the test fixture marked `info`.
- Path traversal (bug 5) and BOLA (bug 1) are not found. That is by design.
- Before and after numbers for the docstring fix are in `docs/MODEL_EVAL.md`.
- Prompt tournament: run it if Part 2 finishes before 14:15, or as the first activity after the break. Collect scores on the board. Ask the winner to read their change aloud, then ask the room whether it would generalize to other code.
- Watch for rule 2. A prompt that says "check line 59 of models.py" scores well and teaches nothing.
