"""Ollama's host:port settings must also work in the HTTP clients."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import review


PIPELINE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def clear_connection_overrides(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("REVIEW_MODEL", raising=False)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("0.0.0.0:11434", "http://127.0.0.1:11434"),
        ("localhost:11434", "http://localhost:11434"),
        ("127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("model-server:11434", "http://model-server:11434"),
        ("http://model-server:11434/", "http://model-server:11434"),
        ("https://models.example.test/ollama/", "https://models.example.test/ollama"),
        ("  localhost:11434/  ", "http://localhost:11434"),
        ("http://0.0.0.0:12345", "http://127.0.0.1:12345"),
        ("[::]:11434", "http://[::1]:11434"),
        ("http://[::]:12345", "http://[::1]:12345"),
        ("[::1]:11434", "http://[::1]:11434"),
        ("[2001:db8::1]:11434", "http://[2001:db8::1]:11434"),
    ],
)
def test_review_normalizes_host(monkeypatch, host, expected):
    monkeypatch.setenv("OLLAMA_HOST", host)
    assert review.load_config()["model"]["host"] == expected


def test_review_normalizes_host_from_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[model]\nname = "test-model"\nhost = "localhost:12345"\n')
    assert review.load_config(path)["model"]["host"] == "http://localhost:12345"


@pytest.mark.parametrize(
    "host",
    [
        "ftp://localhost:11434",
        "http://",
        "http:///missing-host",
        "http://localhost:not-a-port",
        "http://localhost:70000",
        "http://bad host:11434",
        "http://localhost:11434?unexpected=query",
        "http://localhost:11434#fragment",
    ],
)
def test_invalid_host_reports_configuration_error(monkeypatch, capsys, host):
    monkeypatch.setenv("OLLAMA_HOST", host)
    with pytest.raises(SystemExit) as exc:
        review.load_config()
    assert exc.value.code == 1
    error = capsys.readouterr().err
    assert "Ollama host" in error
    assert "http://127.0.0.1:11434" in error


def run_setup_config(host, model=None):
    env = os.environ.copy()
    env["OLLAMA_HOST"] = host
    if model is not None:
        env["REVIEW_MODEL"] = model
    return subprocess.run(
        [sys.executable, str(PIPELINE_DIR / "ollama_config.py"), str(review.CONFIG_PATH)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("0.0.0.0:11434", "http://127.0.0.1:11434"),
        ("localhost:11434", "http://localhost:11434"),
        ("https://models.example.test/ollama/", "https://models.example.test/ollama"),
    ],
)
def test_setup_config_matches_review_config(monkeypatch, host, expected):
    result = run_setup_config(host, "test-model")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [expected, "test-model"]
    monkeypatch.setenv("OLLAMA_HOST", host)
    assert review.load_config()["model"]["host"] == result.stdout.splitlines()[0]


def test_setup_config_rejects_invalid_host():
    result = run_setup_config("ftp://localhost:11434")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "Ollama host" in result.stderr
    assert "http://127.0.0.1:11434" in result.stderr
    assert "Traceback" not in result.stderr


def test_setup_config_handles_quotes_as_data():
    result = run_setup_config("localhost:11434", "model'with-quote")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["http://localhost:11434", "model'with-quote"]
