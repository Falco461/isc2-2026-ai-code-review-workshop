#!/usr/bin/env bash
#
# Set up the review pipeline on macOS or Linux.
#
#   bash reference-pipeline/setup.sh
#
# Safe to run as many times as you like. It only does the work that is
# still missing, and every failure tells you how to fix it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$REPO_ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

say()  { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- python

step "Checking Python"

PYTHON_BIN=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    die "no Python 3.11 or newer found.
     Install it from https://www.python.org/downloads/ and run this script again.
     If you have several versions installed, make sure one of them is on your PATH."
fi

say "Using $($PYTHON_BIN --version) at $(command -v "$PYTHON_BIN")"

# ------------------------------------------------------------------ venv

step "Setting up the virtual environment"

if [ ! -x "$VENV_PY" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR" \
        || die "could not create a virtual environment at $VENV_DIR.
     On Debian or Ubuntu you may need: sudo apt install python3-venv"
    say "Created $VENV_DIR"
else
    say "Reusing $VENV_DIR"
fi

"$VENV_PY" -m pip install --quiet --upgrade pip \
    || die "could not upgrade pip inside the virtual environment.
     Check your network connection, then run this script again."

step "Installing pinned dependencies"

[ -f "$REQUIREMENTS" ] || die "requirements.txt is missing from $SCRIPT_DIR."

"$VENV_PY" -m pip install --quiet -r "$REQUIREMENTS" \
    || die "dependency installation failed.
     Re-run with more detail: $VENV_PY -m pip install -r $REQUIREMENTS"

say "Installed:"
"$VENV_PY" -m pip list --format=freeze 2>/dev/null \
    | grep -iE '^(bandit|bandit-sarif-formatter|detect-secrets|Flask|pytest|requests)=' \
    | sed 's/^/  /'

# ---------------------------------------------------------------- ollama

step "Checking Ollama"

HOST="$("$VENV_PY" - "$SCRIPT_DIR" <<'PY'
import os, sys, tomllib
from pathlib import Path
config = tomllib.loads((Path(sys.argv[1]) / "config.toml").read_text(encoding="utf-8"))
print((os.environ.get("OLLAMA_HOST") or config["model"]["host"]).rstrip("/"))
PY
)"

MODEL="$("$VENV_PY" - "$SCRIPT_DIR" <<'PY'
import os, sys, tomllib
from pathlib import Path
config = tomllib.loads((Path(sys.argv[1]) / "config.toml").read_text(encoding="utf-8"))
print(os.environ.get("REVIEW_MODEL") or config["model"]["name"])
PY
)"

say "Host:  $HOST"
say "Model: $MODEL"

if ! "$VENV_PY" -c "
import sys, requests
try:
    requests.get('$HOST/api/version', timeout=5).raise_for_status()
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    die "Ollama is not answering at $HOST.
     Start it with:  ollama serve
     If you do not have it, install it from https://ollama.com/download
     To use the instructor-hosted model instead:
       export OLLAMA_HOST=http://<address-given-in-room>:11434"
fi

say "Ollama is up."

step "Checking the model"

if "$VENV_PY" -c "
import sys, requests
tags = requests.get('$HOST/api/tags', timeout=10).json().get('models', [])
sys.exit(0 if any(m.get('name') == '$MODEL' for m in tags) else 1)
" 2>/dev/null; then
    say "Model $MODEL is present."
else
    say "Model $MODEL is not present on $HOST."
    if [ "${OLLAMA_HOST:-}" != "" ] && [ "$HOST" != "http://127.0.0.1:11434" ] && [ "$HOST" != "http://localhost:11434" ]; then
        die "that host is remote, so this script will not pull to it.
     Ask the instructor which model name the hosted server provides, then:
       export REVIEW_MODEL=<that name>"
    fi
    printf 'Pull it now? qwen3.5:9b is about 6.6 GB. [y/N] '
    read -r REPLY || REPLY="n"
    case "$REPLY" in
        [yY]*)
            command -v ollama >/dev/null 2>&1 \
                || die "the 'ollama' command is not on your PATH.
     Install it from https://ollama.com/download, or pull the model on
     another machine and copy it over."
            ollama pull "$MODEL" || die "pulling $MODEL failed. Check your connection and try again."
            ;;
        *)
            die "cannot run the smoke test without the model.
     Pull it when you are ready with:  ollama pull $MODEL
     Low on memory or disk? See \"If your laptop cannot run the model\" in README.md."
            ;;
    esac
fi

# ------------------------------------------------------------------ test

step "Running the smoke test"
say "This calls the model once per scanner finding, so it takes a minute or two."

"$VENV_PY" "$SCRIPT_DIR/smoke.py" \
    || die "the smoke test failed. The output above says which check did not pass."

step "Setup complete"
cat <<EOF

Activate the environment in this shell with:

  source .venv/bin/activate

Then review the vulnerable app with:

  cd reference-pipeline
  python review.py --file ../target-app

EOF
