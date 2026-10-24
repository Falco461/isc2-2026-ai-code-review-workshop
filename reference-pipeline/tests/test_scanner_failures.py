"""A failed scanner must not become a successful review with no findings."""

import json
import subprocess

import pytest

import review


CLEAN_BANDIT = {"runs": [{"tool": {"driver": {"name": "Bandit"}}, "results": []}]}
CLEAN_SECRETS = {"results": {}}


def run_scanner(scanner):
    targets = [review.REPO_ROOT / "target-app" / "app.py"]
    if scanner == "bandit":
        return review.run_bandit(targets, [])
    return review.run_detect_secrets(targets)


@pytest.mark.parametrize("scanner", ["bandit", "detect-secrets"])
@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr"),
    [
        (1, "", "No module named scanner"),
        (2, "", "scanner could not run"),
        (0, "", ""),
        (0, "not JSON", ""),
        (0, "{}", ""),
    ],
)
def test_scanner_failure_is_actionable(scanner, returncode, stdout, stderr, monkeypatch, capsys):
    monkeypatch.setattr(
        review.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], returncode, stdout, stderr),
    )
    with pytest.raises(SystemExit) as exc:
        run_scanner(scanner)
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert scanner in output.err
    assert ".venv" in output.err
    if stderr:
        assert stderr in output.err


@pytest.mark.parametrize(
    ("scanner", "document"),
    [("bandit", CLEAN_BANDIT), ("detect-secrets", CLEAN_SECRETS)],
)
def test_successful_clean_scan_still_returns_no_findings(scanner, document, monkeypatch):
    monkeypatch.setattr(
        review.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, json.dumps(document), ""),
    )
    assert run_scanner(scanner) == []


@pytest.mark.parametrize(
    ("scanner", "returncode", "document"),
    [("bandit", 2, CLEAN_BANDIT), ("detect-secrets", 1, CLEAN_SECRETS)],
)
def test_failed_exit_with_valid_output_is_still_a_failure(scanner, returncode, document, monkeypatch):
    monkeypatch.setattr(
        review.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], returncode, json.dumps(document), ""),
    )
    with pytest.raises(SystemExit):
        run_scanner(scanner)


def test_bandit_exit_one_with_findings_is_success(monkeypatch):
    document = {
        "runs": [{
            "tool": {"driver": {"name": "Bandit"}},
            "results": [{
                "ruleId": "B105",
                "message": {"text": "Hardcoded password"},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": "target-app/app.py"},
                    "region": {"startLine": 15},
                }}],
            }],
        }],
    }
    monkeypatch.setattr(
        review.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, json.dumps(document), ""),
    )
    findings = run_scanner("bandit")
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "B105"


@pytest.mark.parametrize("failed_scanner", ["bandit", "detect-secrets"])
def test_review_does_not_print_clean_result_when_scanner_fails(failed_scanner, monkeypatch, capsys):
    def completed(command, **kwargs):
        scanner = "bandit" if "bandit" in command else "detect-secrets"
        if scanner == failed_scanner:
            return subprocess.CompletedProcess(command, 1, "", "No module named scanner")
        document = CLEAN_BANDIT if scanner == "bandit" else CLEAN_SECRETS
        return subprocess.CompletedProcess(command, 0, json.dumps(document), "")

    monkeypatch.setattr(review.subprocess, "run", completed)
    with pytest.raises(SystemExit) as exc:
        review.main(["--file", str(review.REPO_ROOT / "target-app" / "app.py")])
    assert exc.value.code == 1
    assert capsys.readouterr().out == ""
