"""The Module 2 credential quotes must survive GPT-OSS's JSON wrapping."""

import json

import pytest

import review


APP_FILE = "target-app/app.py"


def source_line(line):
    return (review.REPO_ROOT / APP_FILE).read_text(encoding="utf-8").splitlines()[line - 1]


def candidate(line, evidence):
    return {
        "severity": "high",
        "title": "Hardcoded credential",
        "line_start": line,
        "line_end": line,
        "evidence": evidence,
        "explanation": "A credential is committed in application code.",
        "confidence": "high",
    }


@pytest.mark.parametrize("line", [15, 17])
def test_gpt_wrapped_credential_quote_survives(line):
    finding = review.validate_finding(
        candidate(line, json.dumps(source_line(line))), APP_FILE, ["B105"], line_budget=100
    )
    assert finding is not None
    assert finding["file"] == APP_FILE
    assert finding["line_start"] == finding["line_end"] == line
    assert finding["scanner_ref"] == "B105"


@pytest.mark.parametrize("line", [15, 17])
def test_wrapped_quote_at_wrong_line_is_rejected(line):
    assert review.validate_finding(candidate(50, json.dumps(source_line(line))), APP_FILE) is None


@pytest.mark.parametrize("line", [15, 17])
def test_wrapping_cannot_make_unrelated_source_valid(line):
    unrelated = 'if password == "password123":'
    assert review.validate_finding(candidate(line, json.dumps(unrelated)), APP_FILE) is None


@pytest.mark.parametrize("line", [15, 17])
def test_plain_credential_quote_is_preserved(line):
    quote = source_line(line)
    finding = review.validate_finding(candidate(line, quote), APP_FILE)
    assert finding is not None
    assert finding["evidence"] == quote


def test_triage_keeps_both_gpt_wrapped_credentials(monkeypatch):
    replies = iter(candidate(line, json.dumps(source_line(line))) for line in (15, 17))
    monkeypatch.setattr(review, "call_model", lambda *args: next(replies))
    scanners = [
        {
            "tool": "Bandit",
            "refs": ["B105"],
            "file": APP_FILE,
            "line": line,
            "message": "Possible hardcoded password.",
        }
        for line in (15, 17)
    ]
    findings, rendered = review.triage_findings(
        review.load_config(), review.load_prompts(), scanners, dry_run=False
    )
    assert [(finding["file"], finding["line_start"]) for finding in findings] == [
        (APP_FILE, 15),
        (APP_FILE, 17),
    ]
    assert rendered == []
