#
# Set up the review pipeline on Windows.
#
#   .\reference-pipeline\setup.ps1
#
# Safe to run as many times as you like. It only does the work that is
# still missing, and every failure tells you how to fix it.
#
# If PowerShell refuses to run this file, allow local scripts for your
# user account only (this does not need administrator rights):
#
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#

$ErrorActionPreference = "Stop"

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot     = Split-Path -Parent $ScriptDir
$VenvDir      = Join-Path $RepoRoot ".venv"
$VenvPy       = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ScriptDir "requirements.txt"

function Step($message) { Write-Host "`n==> $message" }
function Say($message)  { Write-Host $message }
function Die($message) {
    Write-Host "`nERROR: $message" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- python

Step "Checking Python"

$PythonBin = $null
foreach ($candidate in @("python", "python3", "py")) {
    $found = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $found) { continue }
    & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $PythonBin = $candidate; break }
}

if (-not $PythonBin) {
    Die @"
no Python 3.11 or newer found.
     Install it from https://www.python.org/downloads/ and tick
     "Add python.exe to PATH" in the installer, then open a new
     PowerShell window and run this script again.
"@
}

Say "Using $(& $PythonBin --version) at $((Get-Command $PythonBin).Source)"

# ------------------------------------------------------------------ venv

Step "Setting up the virtual environment"

if (-not (Test-Path $VenvPy)) {
    & $PythonBin -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Die "could not create a virtual environment at $VenvDir." }
    Say "Created $VenvDir"
} else {
    Say "Reusing $VenvDir"
}

& $VenvPy -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Die "could not upgrade pip inside the virtual environment.
     Check your network connection, then run this script again."
}

Step "Installing pinned dependencies"

if (-not (Test-Path $Requirements)) { Die "requirements.txt is missing from $ScriptDir." }

& $VenvPy -m pip install --quiet -r $Requirements
if ($LASTEXITCODE -ne 0) {
    Die "dependency installation failed.
     Re-run with more detail: $VenvPy -m pip install -r $Requirements"
}

Say "Installed:"
& $VenvPy -m pip list --format=freeze 2>$null |
    Select-String -Pattern "^(bandit|bandit-sarif-formatter|detect-secrets|Flask|pytest|requests)=" |
    ForEach-Object { Say "  $_" }

# ---------------------------------------------------------------- ollama

Step "Checking Ollama"

$ConfigReader = @"
import os, sys, tomllib
from pathlib import Path
config = tomllib.loads((Path(sys.argv[1]) / 'config.toml').read_text(encoding='utf-8'))
host = (os.environ.get('OLLAMA_HOST') or config['model']['host']).rstrip('/')
model = os.environ.get('REVIEW_MODEL') or config['model']['name']
print(host)
print(model)
"@

$ConfigValues = & $VenvPy -c $ConfigReader $ScriptDir
$OllamaHost = $ConfigValues[0]
$Model      = $ConfigValues[1]

Say "Host:  $OllamaHost"
Say "Model: $Model"

& $VenvPy -c "import sys, requests
try:
    requests.get('$OllamaHost/api/version', timeout=5).raise_for_status()
except Exception:
    sys.exit(1)" 2>$null

if ($LASTEXITCODE -ne 0) {
    Die @"
Ollama is not answering at $OllamaHost.
     Start it from the Start Menu, or run:  ollama serve
     If you do not have it, install it from https://ollama.com/download
     To use the instructor-hosted model instead:
       `$env:OLLAMA_HOST = "http://<address-given-in-room>:11434"
"@
}

Say "Ollama is up."

Step "Checking the model"

& $VenvPy -c "import sys, requests
tags = requests.get('$OllamaHost/api/tags', timeout=10).json().get('models', [])
sys.exit(0 if any(m.get('name') == '$Model' for m in tags) else 1)" 2>$null

if ($LASTEXITCODE -eq 0) {
    Say "Model $Model is present."
} else {
    Say "Model $Model is not present on $OllamaHost."

    $isLocal = $OllamaHost -eq "http://127.0.0.1:11434" -or $OllamaHost -eq "http://localhost:11434"
    if (-not $isLocal) {
        Die @"
that host is remote, so this script will not pull to it.
     Ask the instructor which model name the hosted server provides, then:
       `$env:REVIEW_MODEL = "<that name>"
"@
    }

    $reply = Read-Host "Pull it now? qwen3.5:9b is about 6.6 GB. [y/N]"
    if ($reply -match '^[yY]') {
        if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
            Die @"
the 'ollama' command is not on your PATH.
     Install it from https://ollama.com/download, then open a new
     PowerShell window and run this script again.
"@
        }
        ollama pull $Model
        if ($LASTEXITCODE -ne 0) { Die "pulling $Model failed. Check your connection and try again." }
    } else {
        Die @"
cannot run the smoke test without the model.
     Pull it when you are ready with:  ollama pull $Model
     Low on memory or disk? See "If your laptop cannot run the model"
     in README.md.
"@
    }
}

# ------------------------------------------------------------------ test

Step "Running the smoke test"
Say "This calls the model once per scanner finding, so it takes a minute or two."

& $VenvPy (Join-Path $ScriptDir "smoke.py")
if ($LASTEXITCODE -ne 0) {
    Die "the smoke test failed. The output above says which check did not pass."
}

Step "Setup complete"
Write-Host @"

Activate the environment in this shell with:

  .\.venv\Scripts\Activate.ps1

Then review the vulnerable app with:

  cd reference-pipeline
  python review.py --file ..\target-app

"@
