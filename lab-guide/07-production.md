# 07. Production Architecture

You have a bot that works on your laptop and in CI. This module asks what it costs, and what changes, when a few hundred developers depend on it.

Read [`production/README.md`](../production/README.md) alongside this guide. It is the reference architecture: three tiers, scaling, model updates, monitoring.

All commands run from the repository root with the environment active.

## 1. Point the bot at a different server

The tiers differ only in where the model runs. Prove it by starting a second Ollama server on another port, standing in for the team server. It uses the models you already downloaded and listens on loopback only.

In a second terminal:

```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"; ollama serve
```

Back in your first terminal:

```bash
OLLAMA_HOST=http://127.0.0.1:11435 python reference-pipeline/review.py --file target-app/models.py
```

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11435"
python reference-pipeline/review.py --file target-app/models.py
Remove-Item Env:OLLAMA_HOST
```

**You should see** the same JSON as Module 3, and request lines scrolling in the second terminal. Nothing in the bot changed except one environment variable. A real team server is the same command with an internal hostname.

Check what is listening:

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep ollama
```

```powershell
netstat -an | Select-String ":1143[45]"
```

**You should see** `127.0.0.1:11434` and `127.0.0.1:11435`, never `*:` or `0.0.0.0:`. A team server has to listen on a network interface, which is why it belongs on an internal network that only CI runners can reach (checklist item 4). Do not make your laptop that server on the workshop wifi.

Stop the second server with Ctrl+C.

## 2. The cost model

Open [`production/tco-model.xlsx`](../production/tco-model.xlsx) in Excel, Numbers, or LibreOffice.

- **Inputs**: blue cells are inputs, yellow cells are the ones that matter most. Column F says where each default came from.
- **TCO**: the results, every one a formula.
- **Sensitivity**: the same formulas for team sizes from 10 to 2,000.
- **Notes**: what the model leaves out.

With the placeholder inputs:

| | CI runner, 9B | Team server, 20B | GPU server, 120B-class | Commercial SaaS |
|---|---|---|---|---|
| Tool TCO, 3 years | about $31,000 | about $32,000 | about $94,000 | about $302,000 |
| Including developer triage time | about $520,000 | about $522,000 | about $584,000 | about $792,000 |

Work through these at your table:

1. **Put in your own team.** Developers, pull requests a week, loaded rates. Which option is cheapest now?
2. **Find the crossover.** On Sensitivity, at what team size does the team server beat the CI runner? Why does the CI runner get more expensive with size and the server not?
3. **Price the noise.** On Inputs, change the 120B-class false-positive share from 20% to 10%. Watch TCO row 19. How much is a point of precision worth to your team?
4. **Price compliance.** If your policy forbids sending source code off site, what is the SaaS column worth? (The Notes sheet has an answer.)

## 3. Gate a model update

A model update is a code change. Run the gates against a candidate model, here `gpt-oss:20b` standing in for "the new model":

```bash
REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low python reference-pipeline/smoke.py
REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low python eval-harness/capstone.py --reps 1
```

```powershell
$env:REVIEW_MODEL = "gpt-oss:20b"; $env:REVIEW_THINK = "low"
python reference-pipeline/smoke.py
python eval-harness/capstone.py --reps 1
Remove-Item Env:REVIEW_MODEL, Env:REVIEW_THINK
```

Then run the same two with your current model and compare. Would you promote the candidate? What would you need to see from the attack lab before you did?

On Codespaces or a CPU-only laptop, run only the smoke test.

## 4. Decide what to watch

The table in `production/README.md` lists six signals, all from the audit log, the CI job, or the comment. Pick the two you would put on a dashboard first, and the threshold that would page someone. Be ready to defend it in the group discussion.

## 5. Table presentations

About 40 minutes: 15 to prepare, then 5 minutes per table.

Use the pipeline you drew in Module 1. Each table presents:

1. **Which tier,** and why not the one next to it.
2. **The TCO,** with your own numbers in the yellow cells. Name the one input you are least sure of.
3. **Two signals** you would put on a dashboard, and the threshold that pages someone.
4. **Who owns the model update gate,** and what happens when that person is on vacation.

The room asks one question per table. The best question wins.

## Discussion

- Tier 1 needs no hardware and sends no code anywhere. What would make you move off it?
- The TCO model says triage time costs more than any tool. Does that match your experience with your current scanners?
- Who owns the model server in your organization: the platform team, the security team, or nobody? What happens to the bot when that person leaves?

## Instructor notes

- Section 1 runs on one machine. On Codespaces it works the same way inside the codespace.
- The tier 1 review time (8 to 12 minutes per job) was measured on a free GitHub runner in October 2026. Every other default in the workbook is a placeholder and says so.
- The workbook builds from a script kept in the project folder, not the repository, so attendees do not need `openpyxl`.
- Table presentations work best with a hard 5-minute timer. If time is short, do three tables and collect the rest on paper.
