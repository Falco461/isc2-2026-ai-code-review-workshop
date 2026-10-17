"""Module 6 audit logging writes one traceable record per model call.

No model calls: requests.post is replaced with a fake Ollama reply.
"""

import hashlib
import json

import review


class FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return {"message": {"content": '{"severity": "high", "title": "t"}'}}


def config(log_path):
    return {
        "model": {"name": "test-model", "host": "http://127.0.0.1:1", "think": False},
        "review": {"audit_log": str(log_path), "sanitize_source": True},
    }


def test_each_call_appends_a_record(tmp_path, monkeypatch):
    monkeypatch.setattr(review.requests, "post", lambda *a, **k: FakeResponse())
    log = tmp_path / "audit.jsonl"
    cfg = config(log)

    review.call_model(cfg, "system text", "user text one", {})
    review.call_model(cfg, "system text", "user text two", {})

    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    first = records[0]
    assert first["model"] == "test-model"
    assert first["sanitized"] is True
    assert first["user_prompt"] == "user text one"
    assert first["prompt_sha256"] == hashlib.sha256(b"system text\n\nuser text one").hexdigest()
    assert json.loads(first["answer"])["severity"] == "high"


def test_no_log_when_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(review.requests, "post", lambda *a, **k: FakeResponse())
    cfg = config("")
    review.call_model(cfg, "s", "u", {})
    assert list(tmp_path.iterdir()) == []
