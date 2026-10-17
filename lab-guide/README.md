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

Modules 5 to 8 are added before the workshop.

## Where you are working

Every command in these guides runs in a terminal at the root of the repository (the folder that contains `README.md`), with the virtual environment active. If a command says "not found", you are in the wrong folder or the environment is not active:

```bash
cd isc2-2026-ai-code-review-workshop
source .venv/bin/activate
```

The guides use macOS and Linux commands. On Windows, use the GitHub Codespace described in [00-setup.md](00-setup.md), which is Linux.

## Answer key

`target-app/PLANTED.md` lists every planted bug. Do not open it until the guide tells you to: the point of the Day 1 labs is to see what the bot finds before you know what is there.
