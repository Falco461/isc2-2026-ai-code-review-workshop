# 00. Setup

About 15 minutes if your model is already downloaded, longer if it is not. Start this the moment you sit down.

## Pick your path

| You have | Use |
|---|---|
| A Mac or Linux laptop you can install software on | **Path A: your laptop.** Fastest. |
| Windows, a locked-down work laptop, or a Chromebook | **Path B: GitHub Codespaces** in your browser. Nothing to install. Slower, see below. |

## Path A: your laptop

### 1. Start the model download now

If you did not pull the model before the workshop, start it first. It is about 6.6 GB and runs in the background while you do the rest.

```bash
ollama pull qwen3.5:9b
```

If the download stalls on the room Wi-Fi, ask the instructor for the USB stick. Copying the model from it takes about a minute (see "Model from the USB stick" below).

### 2. Clone the repository

```bash
git clone https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop.git
cd isc2-2026-ai-code-review-workshop
```

### 3. Run the setup script

```bash
bash reference-pipeline/setup.sh
```

It creates a virtual environment in `.venv`, installs the pinned tools, checks that Ollama answers and that the model is present, then runs the smoke test. It is safe to run again: it only does what is still missing.

**You are done when you see:**

```
SMOKE TEST PASSED

==> Setup complete
```

On an Apple Silicon Mac this takes under a minute once the model is downloaded. On a laptop without a GPU it can take several minutes.

### 4. Activate the environment

Do this in every new terminal window:

```bash
source .venv/bin/activate
```

## Path B: GitHub Codespaces

1. Sign in to GitHub in your browser.
2. Open https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop
3. Select **Code > Codespaces > Create codespace on main**.
4. Wait. The first start builds the machine, installs Ollama, and downloads the model. That takes about 5 minutes. Watch the terminal panel; it ends with `The codespace is ready.`
5. In a new terminal in the codespace:

   ```bash
   source .venv/bin/activate
   cd reference-pipeline
   python smoke.py
   ```

**Know before you choose Codespaces:** it has no GPU, so the model runs on CPU. Reviewing one file takes about 1 to 2 minutes; reviewing the whole target app takes about 20 minutes. The labs tell you when to review a single file. For whole-app runs, pair with a neighbour on a laptop or watch the instructor's screen.

A free GitHub account includes 120 core-hours of Codespaces a month. This codespace uses 4 cores, so you have about 30 hours. Stop it at the end of each day: **Codespaces > ... > Stop codespace**.

## If something goes wrong

| You see | Do this |
|---|---|
| `no Python 3.11 or newer found` | Install Python 3.11+ from python.org, then run the setup script again. |
| `Ollama is not answering` | Start the Ollama app (macOS) or run `ollama serve` in another terminal (Linux). |
| `Model qwen3.5:9b is not present` | Run `ollama pull qwen3.5:9b`, or use the USB stick. |
| The smoke test is very slow | Your laptop is running the model on CPU. It still works. Pair with a neighbour for the whole-app runs. |
| `SMOKE TEST FAILED` | The output above it names which check failed. Show it to the instructor. |

## Model from the USB stick

The stick holds a copy of an Ollama models folder with `qwen3.5:9b` in it.

```bash
# Quit Ollama first (macOS: menu bar icon > Quit Ollama).
mkdir -p ~/.ollama
cp -R /Volumes/<stick-name>/ollama-models/* ~/.ollama/models/
# Start Ollama again, then check:
ollama list
```

You should see `qwen3.5:9b` in the list.
