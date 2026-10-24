# 00. Setup

About 15 minutes if your model is already downloaded, longer if it is not. Start this the moment you sit down.

## Pick your path

| You have | Use |
|---|---|
| A Mac or Linux laptop you can install software on | **Path A: your laptop.** Fastest. |
| A Windows laptop you can install software on | **Path C: Windows PowerShell**, or Path A inside WSL if you already use it. |
| A locked-down work laptop, a Chromebook, or you are not sure | **Path B: GitHub Codespaces** in your browser. Nothing to install. Slower, see below. |

## Path A: Mac or Linux

### 1. Install Python, Git, and Ollama

Check what you already have:

```bash
python3 --version
git --version
ollama --version
```

You need Python 3.11 or newer. Install anything that is missing:

**macOS**

- **Ollama:** download the Mac app from https://ollama.com/download, open the downloaded file, and drag Ollama to Applications. Open it once: a llama icon appears in the menu bar, and the `ollama` command now works in Terminal.
- **Python:** https://www.python.org/downloads/ (or `brew install python@3.12` if you use Homebrew).
- **Git:** run `xcode-select --install`, or `brew install git`.

**Linux (Ubuntu or Debian)**

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo apt update && sudo apt install -y python3 python3-venv git
```

The Ollama script installs it as a service that starts by itself. Check with `ollama --version`. If `python3 --version` is older than 3.11, use the Codespace (Path B) rather than fighting your system Python.

Open a new terminal after installing, so the new commands are found.

### 2. Start the model download now

If you did not pull the model before the workshop, start it first. It is about 6.6 GB and runs while you do the rest.

```bash
ollama pull qwen3.5:9b
```

If the download stalls on the room Wi-Fi, ask the instructor for the USB stick. Copying the model from it takes about a minute (see "Model from the USB stick" below).

### 3. Clone the repository

```bash
git clone https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop.git
cd isc2-2026-ai-code-review-workshop
```

### 4. Run the setup script

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

### 5. Activate the environment

Do this in every new terminal window, from the repository folder:

```bash
source .venv/bin/activate
```

### Path A inside WSL (Windows)

If you already use WSL with Ubuntu, Path A works inside it unchanged: install Ollama, Python, and Git **inside Ubuntu** with the Linux commands above, and run everything from the Ubuntu terminal. Use one Ollama only: if the Windows Ollama app is also running, quit it from the system tray first. (Not tested on the instructor's machines. If it fights you, switch to Path C or B.)

## Path C: Windows PowerShell

### 1. Install Python, Git, and Ollama

- **Ollama:** download the Windows installer from https://ollama.com/download and run it. Ollama runs in the system tray.
- **Python 3.11 or newer:** https://www.python.org/downloads/. In the installer, **tick "Add python.exe to PATH"**.
- **Git:** https://git-scm.com/download/win. The defaults are fine.

Then **open a new PowerShell window** and check:

```powershell
python --version
git --version
ollama --version
```

### 2. Start the model download, and clone

```powershell
ollama pull qwen3.5:9b
git clone https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop.git
cd isc2-2026-ai-code-review-workshop
```

### 3. Allow local scripts, then run the setup script

Windows blocks scripts by default. This allows them for this PowerShell window only, and needs no administrator rights:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\reference-pipeline\setup.ps1
```

**You are done when you see** `SMOKE TEST PASSED` and `==> Setup complete`.

### 4. Activate the environment

Do this in every new PowerShell window, from the repository folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Reading the guides on Windows

**Every PowerShell command from every module is on one page: [WINDOWS-CHEATSHEET.md](WINDOWS-CHEATSHEET.md).** Copy and paste from it rather than retyping.

The guides show `bash` commands. Most work in PowerShell as written (`python`, `git`, `ollama`, `cd`, `cp`, `mv`). Where a command differs, the guide shows a `powershell` block next to it. The general rules:

| bash | PowerShell |
|---|---|
| `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| `REVIEW_MODEL=gpt-oss:20b python review.py ...` | `$env:REVIEW_MODEL = "gpt-oss:20b"; python review.py ...` |
| (the setting ends with the command) | (the setting stays: undo it with `Remove-Item Env:REVIEW_MODEL`) |
| `time python ...` | `Measure-Command { python ... }` |
| `rm -f a.json b.json` | `Remove-Item a.json, b.json -ErrorAction SilentlyContinue` |
| `less file` | `Get-Content file` |
| `python3` | `python` |

Saving output with `>` works: the tools read the files Windows PowerShell writes. Do not pipe text into `python` (`something | python ...`): Windows PowerShell 5.1 garbles it on the way in, and Python fails with `Expecting value: line 1 column 1`. The PowerShell blocks in the guides never do it; use them instead of translating a `bash` pipe yourself.

## Path B: GitHub Codespaces

The link below is the instructor's repository, but **the codespace you create is your own**: it runs in your GitHub account, on your free hours, and nobody else can see into it. You do not need to fork first.

1. Sign in to GitHub in your browser.
2. Open https://github.com/cameronhopkin/isc2-2026-ai-code-review-workshop
3. Select **Code > Codespaces > Create codespace on main**.
4. Wait. The first start builds the machine, installs Ollama, and downloads the model. That takes about 5 minutes. Watch the terminal panel; it ends with `The codespace is ready.`
5. In a new terminal in the codespace, check that the bot works by reviewing one file:

   ```bash
   source .venv/bin/activate
   python reference-pipeline/review.py --file target-app/models.py
   ```

   **You are done when you see** JSON with a finding titled something like "SQL Injection" on line 59. The first review takes about 3 minutes because the model is loading; after that, about 40 seconds per file. (Do not run the full smoke test here: on a codespace it takes about 20 minutes.)

The codespace is Linux, so every `bash` command in the guides works as written.

**Know before you choose Codespaces:** it has no GPU, so the model runs on CPU. Reviewing one file takes about 1 to 2 minutes; reviewing the whole target app takes about 20 minutes. The labs tell you when to review a single file. For whole-app runs, pair with a neighbour on a laptop or watch the instructor's screen.

A free GitHub account includes 120 core-hours of Codespaces a month. This codespace uses 4 cores, so you have about 30 hours. Stop it at the end of each day: **Codespaces > ... > Stop codespace**.

## If something goes wrong

| You see | Do this |
|---|---|
| `ollama: command not found` (or "not recognized") | Ollama is not installed, or the terminal was open before you installed it. Install it (above), then open a new terminal. |
| `no Python 3.11 or newer found` | Install Python 3.11+ from python.org (Windows: tick "Add python.exe to PATH"), open a new terminal, run the setup script again. |
| `Ollama is not answering` | macOS: open the Ollama app. Windows: start Ollama from the Start menu. Linux: `sudo systemctl start ollama`, or run `ollama serve` in another terminal. |
| `Model qwen3.5:9b is not present` | Run `ollama pull qwen3.5:9b`, or use the USB stick. |
| PowerShell says running scripts is disabled | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that window, then try again. |
| The smoke test is very slow | Your laptop is running the model on CPU. It still works. Pair with a neighbour for the whole-app runs. |
| `SMOKE TEST FAILED` | The output above it names which check failed. Show it to the instructor. |

`OLLAMA_HOST` accepts both `host:port` (for example, `localhost:11434`) and full
HTTP or HTTPS URLs. The setup scripts and review bot add `http://` when the
scheme is missing. Listener addresses such as `0.0.0.0:11434` are mapped to
loopback for client requests. An invalid address reports a configuration error
with an example you can use.

## Model from the USB stick

The stick, labelled **Workshop**, holds `qwen3.5:9b` and the low-memory fallback `qwen2.5-coder:7b`. Quit Ollama first (menu bar or system tray icon > Quit), copy, then start Ollama again.

**macOS:**

```bash
mkdir -p ~/.ollama/models
cp -R /Volumes/Workshop/ollama-models/* ~/.ollama/models/
ollama list
```

**Linux** (the Ollama service keeps its models in its own folder):

```bash
sudo systemctl stop ollama
sudo mkdir -p /usr/share/ollama/.ollama/models
sudo cp -R /media/$USER/Workshop/ollama-models/* /usr/share/ollama/.ollama/models/
sudo chown -R ollama:ollama /usr/share/ollama/.ollama/models
sudo systemctl start ollama
ollama list
```

(If the stick is not under `/media/$USER/Workshop`, run `lsblk` to find where it mounted.)

**Windows** (replace `E:` with the stick's drive letter):

```powershell
New-Item -ItemType Directory -Force "$HOME\.ollama\models" | Out-Null
Copy-Item -Recurse -Force "E:\ollama-models\*" "$HOME\.ollama\models\"
ollama list
```

You should see `qwen3.5:9b` in the list.
