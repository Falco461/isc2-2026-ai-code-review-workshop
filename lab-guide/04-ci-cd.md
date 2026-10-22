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

## Discussion

- The bot only reviews the lines the pull request changes. Why is that both faster and a blind spot?
- The comment quotes code from the pull request, and whoever opened the pull request wrote that code. What could a hostile pull request put in the comment? (Look at `escape()` in `../reference-pipeline/post_comment.py`.)
- GitLab free tier: the token can create and edit comments, and it can also touch issues. What would you change before using this at work? Day 2 picks this up.

## Instructor notes

- Measured October 2026: GitHub free runner about 8.5 minutes total (6 minutes of review); GitLab medium runner about 10 minutes. Second runs restore the model from cache.
- Have the instructor's own pull request open in a tab as a fallback demo: https://github.com/cameronhopkin/review-bot-ci-test/pull/1
