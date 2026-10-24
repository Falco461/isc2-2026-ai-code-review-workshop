# Lab guide

Step-by-step instructions for every lab. Work through them in order. Each one says what you will see, so you know when you are on track.

## Before Module 1

- [00. Setup](00-setup.md): clone, install, run the smoke test. Do this first, at 8:00 on Day 1.

## Day 1

| Time | Module | Guide |
|---|---|---|
| 8:30 | 1. The Landscape | [01-landscape.md](01-landscape.md) |
| 10:00 | 2. Model Deployment | [02-model-deployment.md](02-model-deployment.md) |
| 12:30 | 3. Building the Security Bot | [03-building-the-bot.md](03-building-the-bot.md) |
| 15:15 | 4. CI/CD Integration | [04-ci-cd.md](04-ci-cd.md) |

## Day 2

| Time | Module | Guide |
|---|---|---|
| 8:15 | 5. Attacking Your Own Bot | [05-attacking-your-bot.md](05-attacking-your-bot.md) |
| 10:15 | 6. Defenses and Enterprise Hardening | [06-defenses.md](06-defenses.md) |
| 12:45 | 7. Production Architecture | [07-production.md](07-production.md) |
| 14:30 | 8. Capstone | [08-capstone.md](08-capstone.md) |

## Where you are working

Every command in these guides runs in a terminal at the root of the repository (the folder that contains `README.md`), with the virtual environment active. If a command says "not found", you are in the wrong folder or the environment is not active:

```bash
cd isc2-2026-ai-code-review-workshop
source .venv/bin/activate
```

```powershell
cd isc2-2026-ai-code-review-workshop
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
```

The guides use macOS and Linux (`bash`) commands, with `powershell` blocks where Windows differs. Windows users: see "Reading the guides on Windows" in [00-setup.md](00-setup.md). In a Codespace, every `bash` command works as written.

## Answer key

`target-app/PLANTED.md` lists every planted bug. Do not open it until the guide tells you to: the point of the Day 1 labs is to see what the bot finds before you know what is there.
