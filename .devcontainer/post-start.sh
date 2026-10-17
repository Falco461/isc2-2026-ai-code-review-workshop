#!/usr/bin/env bash
#
# Runs every time the codespace starts. Starts Ollama if it is not running.

set -euo pipefail

if curl -fs "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
    echo "Ollama is already running."
    exit 0
fi

nohup ollama serve >/tmp/ollama.log 2>&1 &

for _ in $(seq 1 30); do
    if curl -fs "$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
        echo "Ollama is up."
        exit 0
    fi
    sleep 1
done

echo "ERROR: Ollama did not start. See /tmp/ollama.log, then run: bash .devcontainer/post-start.sh" >&2
exit 1
