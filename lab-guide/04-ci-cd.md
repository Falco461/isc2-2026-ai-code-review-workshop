# 04. CI/CD Integration

Put the bot in a real pipeline on your own GitHub or GitLab account, open a pull request with a vulnerable change, and watch the bot comment on it.

Pick one platform. You do not need both.

All commands run from the repository root. If your prompt ends in `reference-pipeline`, run `cd ..` first.

## Time

About 20 minutes of setup, then about 8 minutes per pipeline run. The run is slow because the free runner has no GPU. It never blocks the merge, so nobody waits on it.

## Do it

Follow `../ci-templates/README.md`. It has every step for both platforms:

1. Push this repository to a new repository of your own (GitHub: **public**, so the free runner has enough memory).
2. Copy the template into place and push it to `main`.
3. GitLab only: create the bot's token and add it as the masked CI/CD variable `REVIEW_BOT_TOKEN`.
4. Apply the lab change on a new branch and open a pull or merge request.

## What you should see

- The pipeline starts on your pull or merge request.
- After about 8 minutes, one comment from the bot appears, listing three findings in `target-app/importer.py`.
- Push another commit to the same branch. The bot **edits** its comment instead of adding a second one.

Do not read `../ci-templates/lab/add-order-importer.patch` before the bot has reviewed it. Compare its comment with what you find yourself.

## While the pipeline runs

The first run takes about 8 minutes. Use it.

### What can a finding put in the comment?

The comment shows each finding's title and explanation. The model writes those, and the code it reads was written by the pull request author. Open `ci-templates/lab/hostile-findings.json`, change the `title` and `explanation` to anything you like, and see what the comment would look like:

```bash
python reference-pipeline/post_comment.py ci-templates/lab/hostile-findings.json --print
```

Try to break the table, inject HTML, hide text, add a link, mention a team. What gets through `escape()` in `reference-pipeline/post_comment.py`, and what does not? Write down anything that gets through. Day 2 tries to get the model to write it for you.

Put the file back when you are done: `git checkout ci-templates/lab/hostile-findings.json`.

### Read the workflow

Open the template you used. Find the permissions, the cache, and the step that decides which lines changed. What would you change before this ran on your team's repositories?

## Discussion

- The bot only reviews the lines the pull request changes. Why is that both faster and a blind spot?
- The comment repeats what the model wrote about code from the pull request, and whoever opened the pull request wrote that code. What could a hostile pull request get into the comment? (Look at `escape()` in `reference-pipeline/post_comment.py`, and try the exercise above.)
- GitLab free tier: the token can create and edit comments, and it can also touch issues. What would you change before using this at work? Day 2 picks this up.

## Instructor notes

- Measured October 2026: GitHub free runner about 8.5 minutes total (6 minutes of review); GitLab medium runner about 10 minutes. Second runs restore the model from cache.
- Have the instructor's own pull request open in a tab as a fallback demo: https://github.com/cameronhopkin/review-bot-ci-test/pull/1
- While the pipeline runs: `escape()` stops HTML, pipes, newlines, and backticks, but not Markdown links or `@mentions`. Let the room find that. Do not fix it on Day 1; Module 5 tries to make the model write one and Module 6 fixes it.
