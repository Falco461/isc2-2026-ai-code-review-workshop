"""Shared Ollama address handling for setup and the review client."""

import os
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


HOST_ERROR = (
    "invalid Ollama host. Set OLLAMA_HOST or model.host to an HTTP(S) URL "
    "or host:port, for example http://127.0.0.1:11434."
)


def normalize_ollama_host(value):
    """Accept Ollama's host:port syntax and turn bind addresses into loopback."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(HOST_ERROR)
    host = value.strip()
    if any(character.isspace() for character in host):
        raise ValueError(HOST_ERROR)
    if "://" not in host:
        host = "http://" + host

    try:
        parts = urlsplit(host)
        port = parts.port
    except ValueError:
        raise ValueError(HOST_ERROR) from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.query
        or parts.fragment
    ):
        raise ValueError(HOST_ERROR)

    # These are server listener addresses, not portable client destinations.
    loopback = {"0.0.0.0": "127.0.0.1", "::": "[::1]"}.get(parts.hostname)
    if loopback:
        userinfo = parts.netloc[: parts.netloc.rfind("@") + 1]
        address = loopback + (":" + str(port) if port is not None else "")
        parts = parts._replace(netloc=userinfo + address)
    return urlunsplit(parts).rstrip("/")


def main():
    """Print the host and model, one per line, for both setup scripts."""
    with Path(sys.argv[1]).open("rb") as handle:
        model = tomllib.load(handle)["model"]
    try:
        host = normalize_ollama_host(os.environ.get("OLLAMA_HOST") or model.get("host"))
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print(host)
    print(os.environ.get("REVIEW_MODEL") or model["name"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
