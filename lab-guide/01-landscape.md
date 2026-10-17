# 01. The Landscape

Mostly discussion. One short lab: see what scanners alone give you, before any model is involved.

## Lab: run the scanners on their own

The target app is a small Flask application with deliberate bugs in it. Run both scanners on it:

```bash
bandit -q -r target-app -x target-app/tests -f txt
detect-secrets scan --all-files target-app
```

Count what they report. **You should see about 6 results from Bandit and 7 from detect-secrets.**

Now answer, without looking anything up:

1. How many of those 13 results do you think are real bugs?
2. Which ones would you look at first?
3. How long would it take you to triage all 13 by hand, for every pull request?

Hold on to your answers. Module 3 compares them with what the bot says.

## Discussion

- **Scanners report patterns, not defects.** Some of these results are real, some are noise, and some real bugs are not in the list at all.
- **The bot's job in this workshop is triage first:** take scanner output, decide what each finding means in this code, explain it, and rate it. Finding bugs no scanner flags comes later, and is much harder.
- **Model size matters, but not the way you expect.** Module 2 shows a bigger model is not always more accurate, and a model trained on security text is not always better at reading code.

## Instructor notes

- Of the 13 results, 4 are real defects (SQL injection, two hardcoded secrets, command injection), and one more real bug (a hardcoded universal password in `auth.py`) is flagged but easy to dismiss as noise. Two real bugs (path traversal, broken access control) are not flagged by anything. See `target-app/PLANTED.md`.
- detect-secrets also fires on documentation and test files. That is the false-positive discussion.
