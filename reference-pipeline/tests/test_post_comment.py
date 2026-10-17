"""The PR or MR comment is rendered safely from untrusted model output.

No network calls. Findings quote code from the change under review, so a
hostile pull request controls part of the comment. These tests check that
it cannot break out of the table or inject markup.
"""

import post_comment


FINDING = {
    "severity": "high",
    "title": "SQL injection",
    "file": "target-app/models.py",
    "line_start": 59,
    "line_end": 59,
    "explanation": "The search term is formatted into the query.",
}


def test_marker_lets_later_pushes_edit_the_same_comment():
    body = post_comment.render({"model": "qwen3.5:9b", "findings": [FINDING]})
    assert body.startswith(post_comment.MARKER)


def test_finding_appears_as_one_table_row():
    body = post_comment.render({"model": "qwen3.5:9b", "findings": [FINDING]})
    rows = [line for line in body.splitlines() if line.startswith("| ") and "models.py" in line]
    assert len(rows) == 1
    assert "`target-app/models.py:59`" in rows[0]


def test_hostile_text_cannot_break_the_table_or_inject_html():
    hostile = dict(FINDING, explanation="ok | fake | cells\n## Approved <img src=x onerror=alert(1)>")
    body = post_comment.render({"model": "m", "findings": [hostile]})
    row = next(line for line in body.splitlines() if "models.py" in line)
    assert row.count(" | ") == 3
    assert "<img" not in body
    assert "\n## Approved" not in body


def test_long_fields_are_truncated():
    long_text = dict(FINDING, explanation="x" * 5000)
    body = post_comment.render({"model": "m", "findings": [long_text]})
    assert "x" * 1000 not in body


def test_no_findings_says_so_with_the_reason():
    body = post_comment.render({"model": "m", "findings": [], "no_findings_reason": "The diff touched no Python."})
    assert "No findings" in body
    assert "The diff touched no Python." in body


def test_multi_line_range_is_shown():
    ranged = dict(FINDING, line_start=37, line_end=43)
    body = post_comment.render({"model": "m", "findings": [ranged]})
    assert "models.py:37-43" in body


def test_platform_detection(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    assert post_comment.detect_platform() is None
    monkeypatch.setenv("GITLAB_CI", "true")
    assert post_comment.detect_platform() == "gitlab"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert post_comment.detect_platform() == "github"


def test_gitlab_without_token_names_the_fix(monkeypatch):
    monkeypatch.delenv("REVIEW_BOT_TOKEN", raising=False)
    target, problem = post_comment.gitlab_target()
    assert target is None
    assert "fine-grained personal access" in problem


def test_print_mode_needs_no_ci(tmp_path, capsys):
    path = tmp_path / "findings.json"
    path.write_text('{"model": "m", "findings": []}', encoding="utf-8")
    assert post_comment.main([str(path), "--print"]) == 0
    assert post_comment.MARKER in capsys.readouterr().out
