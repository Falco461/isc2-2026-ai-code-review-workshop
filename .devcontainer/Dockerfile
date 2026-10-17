FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# The base image ships a Yarn apt source whose signing key has expired,
# so apt-get update fails. Dev container features install packages with
# apt, so one failure there sends Codespaces to its Alpine recovery
# container. Nothing in this workshop uses Yarn.
#
# zstd is required by the Ollama installer to unpack its release.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends zstd \
    && rm -rf /var/lib/apt/lists/*
