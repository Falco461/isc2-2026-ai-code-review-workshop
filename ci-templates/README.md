# Run the bot on your pull requests

Module 4. The bot reviews only the lines a pull request or merge request changes and posts one comment. It edits that comment on later pushes instead of adding new ones. It never blocks the merge.

The model runs inside the free CI runner. No API keys and no cloud model. The first run downloads the model (about 6.6 GB). Later runs restore it from the CI cache.

**Expect about 8 to 12 minutes per pull or merge request.** Measured on free GitHub and GitLab runners in October 2026 on the lab change below: about 1 minute to install Ollama, about 6 minutes for the review itself (the runner has no GPU, so the model runs on CPU), and seconds to post. Because the check never blocks the merge, nobody waits on it.

Pick GitHub or GitLab. You do not need both.

## Before you start

You need your own copy of this repository on GitHub or GitLab.

- **GitHub:** create a new **public** repository and push this repository to it. It must be public: GitHub's free runners for public repositories have 16 GB of memory, which the model needs, while private repositories get 7 GB. Everything in this repository is deliberately vulnerable demo code, so it is safe to publish.
- **GitLab:** create a new project and push this repository to it. Public or private both work.

> **`mine` is a nickname for your repository.** Replace `<your-repository-url>` with your new repository's URL (for example `https://github.com/jsmith/review-bot-practice.git`), never the instructor's. If git says `remote mine already exists`, fix it with `git remote set-url mine <your-repository-url>`.

```bash
git remote add mine <your-repository-url>
git push mine HEAD:main
```

### Or fork it (GitHub only)

Instead of creating an empty repository, you can fork this one: **Fork** at the top right of the repository page, on GitHub. A fork of a public repository is public, so the free runner has enough memory. Add your fork as `mine`, then follow the GitHub Actions steps below unchanged:

> **Three fork gotchas.**
> 1. **Turn Actions on.** A new fork has workflows switched off. Open your fork's **Actions** tab and click the green button to enable them, or nothing ever runs.
> 2. **Point the pull request at your fork.** When you open the pull request, GitHub sets the base to the instructor's repository. Change **base repository** to your fork before you click Create, or your pull request lands in the instructor's repository.
> 3. **GitLab cannot fork a GitHub repository.** On GitLab, create a new project and use the steps above.

```bash
git remote add mine https://github.com/<your-username>/isc2-2026-ai-code-review-workshop.git
```

## GitHub Actions

1. Copy the workflow into place on `main` and push it:

   ```bash
   mkdir -p .github/workflows
   cp ci-templates/github/security-review.yml .github/workflows/
   git add .github/workflows/security-review.yml
   git commit -m "Add the security review bot"
   git push mine HEAD:main
   ```

   ```powershell
   New-Item -ItemType Directory -Force .github\workflows | Out-Null
   Copy-Item ci-templates\github\security-review.yml .github\workflows\
   git add .github/workflows/security-review.yml
   git commit -m "Add the security review bot"
   git push mine HEAD:main
   ```

2. Open a pull request with the lab change (see "The lab change" below).
3. Watch the **Actions** tab. When the job finishes, the bot's comment appears on the pull request.

Nothing else to set up. The workflow uses the built-in `GITHUB_TOKEN`.

## GitLab CI/CD

1. Create the token the bot comments with. GitLab's built-in job token cannot comment on merge requests, and on the free tier of GitLab.com you cannot create a project access token, so the bot uses a personal access token.
   - **Your avatar > Edit profile > Access tokens > Add new token.** Choose **fine-grained** permissions, not the legacy scopes. Name it `review-bot` and set the expiry to the day after the workshop.
   - Select exactly three permissions, and nothing for the repository:
     - `read_work_item`: the bot looks for its own earlier comment
     - `create_work_item`: the bot posts its first comment
     - `update_work_item`: the bot edits that comment on later pushes
   - If the form lets you limit the token to one project, pick this project.
   - Copy the token. GitLab shows it only once.
   - In your project: **Settings > CI/CD > Variables > Add variable.** Key `REVIEW_BOT_TOKEN`, paste the token, set visibility to **Masked**, and leave **Protect variable** unticked (merge request branches are not protected, so a protected variable would not reach the job).

   Merge request comments sit under GitLab's "work item" permissions, which also cover issues and epics. That is as narrow as GitLab goes, and it is a Module 6 discussion. The job checks out code with GitLab's own job token, so the bot token needs no repository access at all. If your form only offers legacy scopes, use scope **api** with a short expiry; it is far broader. On Premium or Ultimate, a project access token (role **Reporter**, scope **api**) also works.
2. Copy the pipeline into place on `main` and push it:

   ```bash
   cp ci-templates/gitlab/security-review.gitlab-ci.yml .gitlab-ci.yml
   git add .gitlab-ci.yml
   git commit -m "Add the security review bot"
   git push mine HEAD:main
   ```

3. Open a merge request with the lab change (see below).
4. Watch **Build > Pipelines**. When the job finishes, the bot's comment appears on the merge request.

The pipeline asks for GitLab's medium runner, because the default model needs more memory than the small one has. The medium runner uses your free compute minutes faster. If it is not available to you, delete the `tags` lines and set the variables `REVIEW_MODEL` to `qwen2.5-coder:7b` and `REVIEW_THINK` to `false`.

## The lab change

`lab/add-order-importer.patch` adds a small, plausible feature with three real bugs in it. Apply it on a new branch and open a pull or merge request from that branch:

```bash
git switch -c add-order-importer
git apply ci-templates/lab/add-order-importer.patch
git add target-app/importer.py
git commit -m "Add bulk order import"
git push mine add-order-importer
```

Then open the pull or merge request from `add-order-importer` into `main` in the web interface.

Do not read the patch before the bot has reviewed it. Compare the bot's comment with what you find yourself afterwards.

## If something goes wrong

- **No comment appears, GitHub.** Open the job log. If it says the token lacks permission, check that the workflow file still has `pull-requests: write` under `permissions`.
- **No comment appears, GitLab.** The job log names the problem. Most often `REVIEW_BOT_TOKEN` is missing, has expired, is marked protected, or lacks one of the three work item permissions. Without `read_work_item` the bot cannot find its earlier comment and posts nothing.
- **The job runs out of time or memory.** Use the smaller model: set `REVIEW_MODEL` to `qwen2.5-coder:7b` and `REVIEW_THINK` to `false` (GitHub: repository variables; GitLab: CI/CD variables).
- **The comment says no findings.** The diff contained no Python files, or the scanners found nothing on the changed lines. The comment says which.
