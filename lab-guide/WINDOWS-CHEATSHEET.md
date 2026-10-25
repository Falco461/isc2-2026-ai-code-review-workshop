# Windows PowerShell cheat sheet

Every PowerShell command from the lab guides, in order, on one page. **Copy and paste them, do not retype them:** the commands are long, and one missing `$` or letter breaks them.

## Before every lab

Open **PowerShell** (not Command Prompt: the prompt must start with `PS`). Go to the repository folder, the one that contains `reference-pipeline`, `lab-guide`, and `target-app`. Then:

```powershell
cd C:\path\to\isc2-2026-ai-code-review-workshop
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)` and end in `\isc2-2026-ai-code-review-workshop>`.

## Rules that save you time

- **`$env:` settings stay for the whole window.** After a lab that sets `REVIEW_MODEL`, `REVIEW_THINK`, `REVIEW_SANITIZE`, or `OLLAMA_HOST`, run the `Remove-Item Env:...` line it ends with, or every later command keeps using that setting.
- **`The term '...' is not recognized`:** check the word in quotes. A misspelling, a missing `$`, the wrong folder, or a `.venv` that setup never finished creating.
- **`No module named bandit`:** setup did not finish. Run `.\reference-pipeline\setup.ps1` again from the repository folder.
- **Python 3.15, or a laptop with an ARM processor, and setup fails building PyYAML:** install Python 3.12 (64-bit) from python.org, then `Remove-Item -Recurse -Force .venv`, `py -3.12 -m venv .venv`, and run setup again.
- **Do not pipe text into `python`** (`something | python ...`). Windows PowerShell 5.1 garbles it. The commands below never do.
- **Anything that keeps fighting you:** use a Codespace (Path B in [00-setup.md](00-setup.md)). It is Linux, so the `bash` commands in the guides work there as written.

## 00. Setup

Full guide: [00-setup.md](00-setup.md)

**1. Install Python, Git, and Ollama**

```powershell
python --version
git --version
ollama --version
```

**2. Start the model download, and clone**

```powershell
ollama pull qwen3.5:9b
git clone https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop.git
cd isc2-2026-ai-code-review-workshop
```

**3. Allow local scripts, then run the setup script**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\reference-pipeline\setup.ps1
```

**4. Activate the environment**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Model from the USB stick**

```powershell
New-Item -ItemType Directory -Force "$HOME\.ollama\models" | Out-Null
Copy-Item -Recurse -Force "E:\ollama-models\*" "$HOME\.ollama\models\"
ollama list
```

## 01. The Landscape

Full guide: [01-landscape.md](01-landscape.md)

**Lab: run the scanners on their own**

```powershell
bandit -q -r target-app -x target-app/tests -f txt
detect-secrets scan --all-files target-app
```

**Does the scanner agree with you?**

```powershell
bandit -q -r target-app -x target-app/tests -f json > bandit.json
(Get-Content bandit.json -Raw | ConvertFrom-Json).results | ForEach-Object { "$($_.issue_severity) $($_.issue_confidence) $($_.filename) $($_.line_number) $($_.test_id)" }
Remove-Item bandit.json
```

## 02. Model Deployment

Full guide: [02-model-deployment.md](02-model-deployment.md)

**1. Pull the extra models**

```powershell
ollama pull qwen2.5-coder:7b
ollama pull gpt-oss:20b
```

```powershell
ollama list
```

**2. Talk to a model directly**

```powershell
ollama run qwen3.5:9b "In one sentence, what is SQL injection?"
```

**3. Same file, three models**

```powershell
$env:REVIEW_MODEL = "qwen3.5:9b"; $env:REVIEW_THINK = "false"; & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\app.py
$env:REVIEW_MODEL = "qwen2.5-coder:7b"; $env:REVIEW_THINK = "false"; & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\app.py
$env:REVIEW_MODEL = "gpt-oss:20b"; $env:REVIEW_THINK = "low"; & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\app.py

Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

**If GPT-OSS reports no findings**

```powershell
git pull --ff-only
```

**What does more thinking buy?**

```powershell
$env:REVIEW_MODEL = "gpt-oss:20b"
foreach ($level in "low", "medium", "high") {
    $env:REVIEW_THINK = $level
    $s = (Measure-Command { & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\auth.py | Out-Host }).TotalSeconds
    "think=$level took $([int]$s) seconds"
}
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

```powershell
$env:REVIEW_MODEL = "qwen3.5:9b"; $env:REVIEW_THINK = "true"
Measure-Command { & .\.venv\Scripts\python.exe reference-pipeline\review.py --file target-app\auth.py | Out-Host }
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

## 03. Building the Security Bot

Full guide: [03-building-the-bot.md](03-building-the-bot.md)

```powershell
cd reference-pipeline
```

**1. Review the whole target app**

```powershell
python review.py --file ../target-app > findings.json
```

**2. Read the output**

```powershell
Get-Content findings.json -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**3. See exactly what the model was sent**

```powershell
python review.py --file ../target-app/models.py --dry-run
```

**4. Turn it into a pull request comment**

```powershell
python post_comment.py findings.json --print
```

**Citation required**

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

**Refuse over guess**

```powershell
python review.py --file ../target-app/db.py
```

**Now open the answer key**

```powershell
Get-Content ..\target-app\PLANTED.md
```

```powershell
cd ..
```

**1. Save the original, and score the baseline once**

```powershell
Copy-Item prompts\review_system.md prompts\review_system.md.orig
python reference-pipeline/review.py --file target-app > scanner.json
python reference-pipeline/review.py --file target-app --no-scanner > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

**2. Edit, then test fast on one file**

```powershell
python reference-pipeline/review.py --file target-app/app.py --no-scanner
```

**3. Score the real thing**

```powershell
python reference-pipeline/review.py --file target-app --no-scanner > sweep.json
python eval-harness/score_planted.py scanner.json sweep.json
```

**When you are done**

```powershell
Move-Item -Force prompts\review_system.md.orig prompts\review_system.md
Remove-Item scanner.json, sweep.json -ErrorAction SilentlyContinue
```

## 04. CI/CD Integration

Full guide: [04-ci-cd.md](04-ci-cd.md)

**What can a finding put in the comment?**

```powershell
python reference-pipeline/post_comment.py ci-templates/lab/hostile-findings.json --print
```

**CI setup (ci-templates/README.md): Before you start**

> **`mine` is a nickname for your repository.** Replace `<your-repository-url>` with your new repository's URL (for example `https://github.com/jsmith/review-bot-practice.git`), never the instructor's. If git says `remote mine already exists`, fix it with `git remote set-url mine <your-repository-url>`.

```powershell
git remote add mine <your-repository-url>
git push mine HEAD:main
```

**CI setup (ci-templates/README.md): Or fork it (GitHub only)**

> **Three fork gotchas.**
> 1. **Turn Actions on.** A new fork has workflows switched off. Open your fork's **Actions** tab and click the green button to enable them, or nothing ever runs.
> 2. **Point the pull request at your fork.** When you open the pull request, GitHub sets the base to the instructor's repository. Change **base repository** to your fork before you click Create, or your pull request lands in the instructor's repository.
> 3. **GitLab cannot fork a GitHub repository.** On GitLab, create a new project and use the steps above.

```powershell
git remote add mine https://github.com/<your-username>/isc2-2026-ai-code-review-workshop.git
```

**CI setup (ci-templates/README.md): GitHub Actions**

```powershell
New-Item -ItemType Directory -Force .github\workflows | Out-Null
Copy-Item ci-templates\github\security-review.yml .github\workflows\
git add .github/workflows/security-review.yml
git commit -m "Add the security review bot"
git push mine HEAD:main
```

**CI setup (ci-templates/README.md): GitLab CI/CD**

```powershell
cp ci-templates/gitlab/security-review.gitlab-ci.yml .gitlab-ci.yml
git add .gitlab-ci.yml
git commit -m "Add the security review bot"
git push mine HEAD:main
```

**CI setup (ci-templates/README.md): The lab change**

```powershell
git switch -c add-order-importer
git apply ci-templates/lab/add-order-importer.patch
git add target-app/importer.py
git commit -m "Add bulk order import"
git push mine add-order-importer
```

## 05. Attacking Your Own Bot

Full guide: [05-attacking-your-bot.md](05-attacking-your-bot.md)

**Before you start: get today's bot**

```powershell
git switch main
git pull https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop.git main
```

**How the attack lab works**

```powershell
python attack-lab/run_attack.py --list
```

**1. Run the built-in attacks**

```powershell
python attack-lab/run_attack.py
```

**2. Write your own**

```powershell
python attack-lab/run_attack.py my-attack --reps 3
```

**4. The leaderboard**

```powershell
python attack-lab/run_attack.py my-attack --reps 3
$env:REVIEW_SANITIZE = "1"; python attack-lab/run_attack.py my-attack --reps 3
Remove-Item Env:REVIEW_SANITIZE
```

```powershell
python reference-pipeline/review.py --file target-app/app.py > attacked.json
python reference-pipeline/post_comment.py attacked.json --print
git checkout target-app/app.py
Remove-Item attacked.json -ErrorAction SilentlyContinue
```

## 06. Defenses and Enterprise Hardening

Full guide: [06-defenses.md](06-defenses.md)

**1. Input sanitization**

```powershell
python reference-pipeline/review.py --file target-app/app.py --dry-run > before.json
$env:REVIEW_SANITIZE = "1"
python reference-pipeline/review.py --file target-app/app.py --dry-run > after.json
Remove-Item Env:REVIEW_SANITIZE
(Get-Content before.json -Raw | ConvertFrom-Json).prompts[0].user -split "`n" | Select-Object -First 22
(Get-Content after.json -Raw | ConvertFrom-Json).prompts[0].user -split "`n" | Select-Object -First 22
Remove-Item before.json, after.json
```

```powershell
$env:REVIEW_SANITIZE = "1"; python attack-lab/run_attack.py --reps 3
Remove-Item Env:REVIEW_SANITIZE
```

**2. Did the fix cost anything?**

```powershell
cd reference-pipeline
python review.py --file ../target-app > before.json
$env:REVIEW_SANITIZE = "1"; python review.py --file ../target-app > after.json
Remove-Item Env:REVIEW_SANITIZE
python post_comment.py before.json --print
python post_comment.py after.json --print
cd ..
```

**3. Audit logging**

```powershell
$env:REVIEW_AUDIT_LOG = "audit.jsonl"; $env:REVIEW_SANITIZE = "1"
python reference-pipeline/review.py --file target-app/app.py
Remove-Item Env:REVIEW_AUDIT_LOG, Env:REVIEW_SANITIZE
python -c "import json; [print(r['time'], r['model'], r['prompt_sha256'][:16], r['answer'][:60].replace(chr(10),' ')) for r in map(json.loads, open('audit.jsonl'))]"
```

**4. Network segmentation**

```powershell
netstat -an | Select-String ":11434"
```

**Close the gap in `escape()`**

```powershell
cd reference-pipeline
python -m pytest tests/test_post_comment.py -q
cd ..
```

## 07. Production Architecture

Full guide: [07-production.md](07-production.md)

**1. Point the bot at a different server**

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"; ollama serve
```

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11435"
python reference-pipeline/review.py --file target-app/models.py
Remove-Item Env:OLLAMA_HOST
```

```powershell
netstat -an | Select-String ":1143[45]"
```

**3. Gate a model update**

```powershell
$env:REVIEW_MODEL = "gpt-oss:20b"; $env:REVIEW_THINK = "low"
python reference-pipeline/smoke.py
python eval-harness/capstone.py --reps 1
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

**Suggested fixes, one click**

```powershell
git switch add-order-importer
git merge --no-edit main
git diff main...HEAD > pr.diff
python reference-pipeline/review.py --diff pr.diff --sweep > findings.json
python reference-pipeline/post_comment.py findings.json --print --suggest --diff pr.diff
git switch main
```

**Bypasses, as code**

```powershell
Set-Content -Encoding ascii security-suppressions.toml @'
[[suppress]]
file = "target-app/importer.py"
match = "verify=False"
reason = "Partner feed is on the internal network. SEC-123 adds the CA bundle."
approved_by = "appsec-oncall"
expires = 2026-11-30
'@
```

```powershell
python reference-pipeline/review.py --diff pr.diff --sweep > findings.json
python reference-pipeline/post_comment.py findings.json --print
```

## 08. Capstone

Full guide: [08-capstone.md](08-capstone.md)

**1. Read the pull request yourself first**

```powershell
python -c "import sys; sys.path[:0]=['eval-harness','attack-lab']; import capstone; print(capstone.ENDPOINT)"
```

**2. Score both configurations**

```powershell
python eval-harness/capstone.py
```

```powershell
$env:REVIEW_MODEL = "gpt-oss:20b"; $env:REVIEW_THINK = "low"
python eval-harness/capstone.py
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

**3. Watch the tool work**

```powershell
python -c "import sys, pathlib; sys.path[:0]=['eval-harness','attack-lab']; import capstone; pathlib.Path('pr.diff').write_text(capstone.apply_pull_request(pathlib.Path('.'))[0])"
```

```powershell
$env:REVIEW_AUDIT_LOG = "audit-capstone.jsonl"
python reference-pipeline/review.py --diff pr.diff --no-scanner --repo-read
Remove-Item Env:REVIEW_AUDIT_LOG
python eval-harness/show_reads.py audit-capstone.jsonl
```

```powershell
python reference-pipeline/review.py --diff pr.diff --no-scanner
```

```powershell
git checkout target-app/app.py
Remove-Item pr.diff, audit-capstone.jsonl -ErrorAction SilentlyContinue
```

**4. What the tool is allowed to do**

```powershell
python eval-harness/try_read_limits.py
```

**6. The whole app, fully hardened**

```powershell
$env:REVIEW_SANITIZE = "1"
python reference-pipeline/review.py --file target-app > scanner.json
python reference-pipeline/review.py --file target-app --no-scanner --repo-read > sweep.json
Remove-Item Env:REVIEW_SANITIZE
python eval-harness/score_planted.py scanner.json sweep.json
```

```powershell
Remove-Item scanner.json, sweep.json -ErrorAction SilentlyContinue
```

**7. Plant a bug for your neighbour**

```powershell
git switch -c planted
# edit target-app
git diff main > mine.diff
```

```powershell
python reference-pipeline/review.py --diff mine.diff
python reference-pipeline/review.py --diff mine.diff --no-scanner
python reference-pipeline/review.py --diff mine.diff --no-scanner --repo-read
```

```powershell
git checkout main
git branch -D planted
Remove-Item mine.diff -ErrorAction SilentlyContinue
```
