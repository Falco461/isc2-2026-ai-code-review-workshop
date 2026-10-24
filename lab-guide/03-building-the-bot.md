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

```powershell
Get-Content findings.json -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 10
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

```powershell
Set-Content check_citation.py @'
import review
fake = {'severity': 'high', 'title': 'Made up', 'line_start': 999, 'line_end': 999,
        'evidence': 'nope', 'explanation': 'x', 'confidence': 'high'}
print('kept' if review.validate_finding(fake, 'target-app/app.py', line_budget=40) else 'dropped')
'@
python check_citation.py
Remove-Item check_citation.py
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

```powershell
Get-Content ..\target-app\PLANTED.md
```

How many of the six planted bugs did the bot find? Which ones can no scanner and no model find without reading another file? That gap is the capstone.

Go back to the repository root before Module 4:

```bash
cd ..
```

## Going further: the prompt tournament

About 45 to 60 minutes, in pairs or tables. **The bugs are already planted. Your job is to make the bot find more of them, without adding noise.**

### The goal

> **Spoiler, added after the Oct 24 workshop:** the room's winning rule is now rule 8 in the `## sweep` section ("Follow the input"), and CI runs the cold read with `--sweep`. To play the tournament yourself, delete rule 8 first.

Beat **36 points**, the score of the unchanged prompt. The scorer gives **10 points per planted bug found, minus 2 for every finding that matches no planted bug.** A prompt that finds everything by reporting everything loses.

The unchanged bot finds 4 of the 6 planted bugs. The two it misses are **path traversal** and **broken access control**. No scanner flags either, so the bot can only find them in its cold read of the code.

### What to edit

Open `prompts/review_system.md` and edit **only the `## sweep` section**. That is the prompt for the cold read. The `## triage` section only ever sees what the scanners flagged, so it cannot win you the two missing bugs.

Rules:

1. Edit only `prompts/review_system.md`. No code changes.
2. **Teach the bot how to look, not what to find.** Never name the planted bugs, the files, the functions, or line numbers. A prompt that only works on this app is not a better prompt.
3. Keep the headings (`## triage`, `## sweep`, `## repo_read`): `review.py` loads each section by its heading.

### 1. Save the original, and score the baseline once

```bash
cp prompts/review_system.md prompts/review_system.md.orig
python reference-pipeline/review.py --file target-app > scanner.json
python reference-pipeline/review.py --file target-app --no-scanner > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

```powershell
Copy-Item prompts\review_system.md prompts\review_system.md.orig
python reference-pipeline/review.py --file target-app > scanner.json
python reference-pipeline/review.py --file target-app --no-scanner > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

You only need `scanner.json` once: it does not change when you edit the `## sweep` section.

### 2. Edit, then test fast on one file

A full sweep takes about 2 minutes. While you experiment, review only `app.py`, in about 10 seconds (about a minute on a laptop without a GPU). It is where requests come in, so it is where the bot can see untrusted input meet something dangerous:

```bash
python reference-pipeline/review.py --file target-app/app.py --no-scanner
```

The command is the same in PowerShell. Look for a new finding, and check that the bot did not add junk.

**What we saw:** adding the "follow the input" hint below to the `## sweep` section turned up path traversal on `app.py` in 2 of 2 runs, where the unchanged prompt missed it. Broken access control is the hard one: the proof is in another file, and the bot reviews one file at a time. Module 8 gives it a tool for exactly that. If your table gets it from the prompt alone, you have won.

### 3. Score the real thing

When a change looks good, rerun the full sweep and score it:

```bash
python reference-pipeline/review.py --file target-app --no-scanner > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

The commands are the same in PowerShell. Put your best score on the board, with one sentence on what you changed. The model is not perfectly repeatable, so run your best prompt twice before you claim the win.

### Hints, if you are stuck

These are techniques a human reviewer uses. Turn one into an instruction:

- **Follow the input.** For every value that comes from a request (query string, form field, URL path), follow it to where it is used: a SQL query, a shell command, a file path. Report the line where untrusted input reaches something dangerous.
- **File paths built from input.** When code joins a folder and a name that came from a request, ask: what happens if the name contains `..`?
- **Names are promises, code is proof.** A function or decorator whose name promises a check is only as good as what it actually checks. Compare the name with the code. If it promises more than it checks, that is a finding.
- **Cut the noise.** Look at the scorer's unmatched findings. Tell the bot what is *not* worth reporting, without telling it to ignore real defects.

### When you are done

Put the original prompt back, so later modules and your CI use it:

```bash
mv prompts/review_system.md.orig prompts/review_system.md
rm -f scanner.json sweep.json
```

```powershell
Move-Item -Force prompts\review_system.md.orig prompts\review_system.md
Remove-Item scanner.json, sweep.json -ErrorAction SilentlyContinue
```

## Instructor notes

- Expected full-app findings with `qwen3.5:9b`: SQL injection, both secrets in `app.py`, command injection, and the universal password in `auth.py` escalated; the hash template on `auth.py:55` and the test fixture marked `info`.
- Path traversal (bug 5) and BOLA (bug 1) are not found. That is by design.
- Before and after numbers for the docstring fix are in `docs/MODEL_EVAL.md`.
- Prompt tournament: run it if Part 2 finishes before 14:15, or as the first activity after the break. Collect scores on the board. Ask the winner to read their change aloud, then ask the room whether it would generalize to other code.
- Watch for rule 2. A prompt that says "check line 59 of models.py" scores well and teaches nothing.
