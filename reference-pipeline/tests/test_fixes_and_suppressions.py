"""Suppressions as code, and one-click suggested fixes. No model calls."""

import json

import fixes
import post_comment
import review


def finding(**kw):
    f = {"file": "target-app/app.py", "line_start": 15, "line_end": 15, "severity": "high",
         "title": "Hardcoded secret", "explanation": "x", "scanner_ref": "B105"}
    f.update(kw)
    return f


# ---------------------------------------------------------- suppressions

def write(tmp_path, text):
    path = tmp_path / "security-suppressions.toml"
    path.write_text(text)
    return path


def test_an_approved_suppression_marks_the_finding(tmp_path):
    path = write(tmp_path, '[[suppress]]\nfile = "target-app/app.py"\nline = 15\nreason = "rotated test key"\napproved_by = "appsec"\n')
    out = review.apply_suppressions([finding()], path)
    assert out[0]["suppressed"] == {"reason": "rotated test key", "approved_by": "appsec"}


def test_a_suppression_without_approval_is_ignored(tmp_path, capsys):
    path = write(tmp_path, '[[suppress]]\nfile = "target-app/app.py"\nline = 15\nreason = "trust me"\n')
    out = review.apply_suppressions([finding()], path)
    assert "suppressed" not in out[0]
    assert "approved_by" in capsys.readouterr().err


def test_an_expired_suppression_is_ignored(tmp_path):
    path = write(tmp_path, '[[suppress]]\nfile = "target-app/app.py"\nline = 15\nreason = "r"\napproved_by = "a"\nexpires = 2020-01-01\n')
    assert "suppressed" not in review.apply_suppressions([finding()], path)[0]


def test_rule_and_match_must_agree(tmp_path):
    path = write(tmp_path, '[[suppress]]\nfile = "target-app/app.py"\nmatch = "secret_key"\nrule = "B105"\nreason = "r"\napproved_by = "a"\n')
    assert "suppressed" in review.apply_suppressions([finding()], path)[0]
    assert "suppressed" not in review.apply_suppressions([finding(scanner_ref="B608")], path)[0]
    assert "suppressed" not in review.apply_suppressions([finding(line_start=17, line_end=17)], path)[0]


def test_no_file_means_no_suppressions(tmp_path):
    assert "suppressed" not in review.apply_suppressions([finding()], tmp_path / "missing.toml")[0]


def test_suppressed_findings_are_shown_not_hidden():
    doc = {"model": "m", "findings": [finding(suppressed={"reason": "rotated", "approved_by": "appsec"}),
                                      finding(line_start=17, line_end=17, title="Token")]}
    body = post_comment.render(doc)
    assert "1 finding(s)" in body
    assert "Suppressed by `security-suppressions.toml`" in body
    assert "rotated" in body and "appsec" in body


# ----------------------------------------------------------------- fixes

def test_check_fix_rejects_empty_identical_fenced_and_oversized():
    original = ['    x = "secret"']
    assert fixes.check_fix(original, "") is None
    assert fixes.check_fix(original, '    x = "secret"') is None
    assert fixes.check_fix(original, "```\nx\n```") is None
    assert fixes.check_fix(original, "\n".join("a" for _ in range(20))) is None
    assert fixes.check_fix(original, '15:     x = os.environ["X"]') == ['    x = os.environ["X"]']


def test_only_real_findings_wholly_on_changed_lines_get_suggestions():
    changed = {"target-app/app.py": {15, 16, 17}}
    picked = post_comment.suggestion_candidates([
        finding(), finding(severity="info"), finding(line_start=17, line_end=18),
        finding(suppressed={"reason": "r", "approved_by": "a"}), finding(file="target-app/auth.py"),
    ], changed)
    assert [(f["file"], f["line_start"]) for f in picked] == [("target-app/app.py", 15)]


def test_suggestion_fences_match_each_platform():
    fix = {"lines": ["a", "b"], "rationale": "why"}
    f = finding(line_start=10, line_end=11)
    assert "```suggestion\na\nb\n```" in post_comment.suggestion_body(f, fix, "github")
    assert "```suggestion:-0+1\na\nb\n```" in post_comment.suggestion_body(f, fix, "gitlab")


def test_advice_without_a_patch_has_no_apply_button():
    body = post_comment.suggestion_body(finding(), {"lines": None, "rationale": "switch to json"}, "github")
    assert "```suggestion" not in body and "Recommended fix" in body


def test_line_payloads():
    gh = post_comment.github_line_payload(finding(line_start=10, line_end=12), "b", "abc")
    assert gh["line"] == 12 and gh["start_line"] == 10 and gh["commit_id"] == "abc" and gh["side"] == "RIGHT"
    assert "start_line" not in post_comment.github_line_payload(finding(), "b", "abc")
    gl = post_comment.gitlab_line_payload(finding(), "b", ("b1", "s1", "h1"))
    assert gl["position"]["new_line"] == 15 and gl["position"]["head_sha"] == "h1"


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code, self._data, self.text = status, data, ""

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def test_post_suggestions_skips_fixes_already_posted(monkeypatch, tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 1, "head": {"sha": "abc"}}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    posted = []
    already = post_comment.FIX_MARKER % ("target-app/app.py", 15)
    monkeypatch.setattr(post_comment.requests, "get", lambda *a, **k: FakeResponse(data=[{"body": already}]))
    monkeypatch.setattr(post_comment.requests, "post", lambda url, **k: posted.append(k["json"]) or FakeResponse(201))
    target = {"create": "https://api/repos/o/r/issues/1/comments", "headers": {}}
    fix = {"lines": ["x"], "rationale": ""}
    n = post_comment.post_suggestions("github", target, [(finding(), fix), (finding(line_start=17, line_end=17), fix)])
    assert n == 1 and posted[0]["line"] == 17 and posted[0]["commit_id"] == "abc"


def test_with_a_ref_the_pull_request_copy_is_ignored(tmp_path, monkeypatch):
    """CI reads suppressions from the target branch, so a PR cannot approve its own bypass."""
    import subprocess

    path = write(tmp_path, '[[suppress]]\nfile = "target-app/app.py"\nline = 15\nreason = "r"\napproved_by = "a"\n')
    monkeypatch.setattr(review.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 128, "", "fatal: path does not exist"))
    assert "suppressed" not in review.apply_suppressions([finding()], path, ref="origin/main")[0]
    monkeypatch.setattr(review.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, '[[suppress]]\nfile = "target-app/app.py"\nline = 15\nreason = "merged"\napproved_by = "appsec"\n', ""))
    assert review.apply_suppressions([finding()], path, ref="origin/main")[0]["suppressed"]["reason"] == "merged"


def test_a_patch_that_only_adds_lines_is_not_a_fix():
    original = ["    return pickle.loads(blob)"]
    assert fixes.check_fix(original, "    import pickle\n    return pickle.loads(blob)") is None
    assert fixes.check_fix(original, "    return json.loads(blob)") == ["    return json.loads(blob)"]
