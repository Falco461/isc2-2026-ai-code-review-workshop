#!/usr/bin/env bash
#
# Runs once, when the codespace is created. Installs Ollama, pulls the
# default model from config.toml, and builds .venv with the pinned
# requirements, the same way reference-pipeline/setup.sh does locally.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_ROOT/.venv/bin/python"

step() { printf '\n==> %s\n' "$*"; }

step "Installing Ollama"
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
ollama --version

step "Starting Ollama"
bash "$REPO_ROOT/.devcontainer/post-start.sh"

step "Building the virtual environment"
python3 -m venv "$REPO_ROOT/.venv"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r "$REPO_ROOT/reference-pipeline/requirements.txt"

step "Pulling the model"
MODEL="$("$VENV_PY" - "$REPO_ROOT" <<'PY'
import os, sys, tomllib
from pathlib import Path
config = tomllib.loads((Path(sys.argv[1]) / "reference-pipeline" / "config.toml").read_text(encoding="utf-8"))
print(os.environ.get("REVIEW_MODEL") or config["model"]["name"])
PY
)"
echo "Pulling $MODEL. This is several gigabytes and takes a few minutes."
ollama pull "$MODEL"

step "Ready"
cat <<MSG

The codespace is ready. In a new terminal:

  source .venv/bin/activate
  cd reference-pipeline
  python smoke.py

MSG
