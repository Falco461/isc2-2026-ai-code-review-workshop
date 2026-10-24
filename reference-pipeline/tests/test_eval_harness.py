"""The Module 8 scorers still point at the right code.

No model calls. The planted-bug scorer and the capstone are anchored to
line numbers in target-app, so an edit there can silently break scoring.
"""

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "eval-harness"), str(REPO_ROOT / "attack-lab")]

import capstone  # noqa: E402
import score_planted  # noqa: E402

# One line inside each planted span that must still hold the planted code.
ANCHORS = {
    1: ("target-app/auth.py", 33, "def require_order_access"),
    2: ("target-app/models.py", 59, "LIKE"),
    3: ("target-app/app.py", 15, "secret_key"),
    4: ("target-app/storage.py", 37, "echo Generating %s"),
    5: ("target-app/storage.py", 25, "UPLOAD_DIR / name"),
    6: ("target-app/auth.py", 56, 'password == "password123"'),
}


def line(file, number):
    return (REPO_ROOT / file).read_text(encoding="utf-8").split("\n")[number - 1]


def finding(file, start, title="Some defect", severity="high", end=None):
    return {"file": file, "line_start": start, "line_end": end or start, "title": title, "severity": severity}


def test_every_planted_span_still_holds_its_bug():
    for number, (file, at, text) in ANCHORS.items():
        assert text in line(file, at), "bug %d moved: %s:%d is %r" % (number, file, at, line(file, at))


def test_the_command_injection_span_holds_the_shell_call():
    span = [line("target-app/storage.py", n) for n in range(37, 41)]
    assert any("shell=True" in l for l in span)


def test_bola_on_the_endpoint_line_counts_only_with_an_access_title():
    results, _ = score_planted.score([finding("target-app/app.py", 49, "Missing ownership check")])
    assert results[0]["found"]
    results, extras = score_planted.score([finding("target-app/app.py", 49, "Verbose error message")])
    assert not results[0]["found"]
    assert len(extras) == 1


def test_info_findings_never_count():
    results, extras = score_planted.score([finding("target-app/models.py", 59, severity="info")])
    assert not results[1]["found"]
    assert extras == []


def test_a_range_covering_the_line_counts():
    results, _ = score_planted.score([finding("target-app/storage.py", 35, end=38)])
    assert results[3]["found"]


def test_findings_from_several_files_are_pooled(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text('{"findings": [%s]}' % '{"file": "target-app/models.py", "line_start": 59, "line_end": 59, "title": "SQLi", "severity": "high"}')
    b.write_text('{"findings": []}')
    assert len(score_planted.load([str(a), str(b)])) == 1


def test_the_capstone_pull_request_still_applies(tmp_path):
    shutil.copytree(REPO_ROOT / "target-app", tmp_path / "target-app")
    diff, after = capstone.apply_pull_request(tmp_path)
    assert "+@auth.require_order_access" in diff
    start, _ = capstone.endpoint_lines(after)
    assert "@app.route" in after.split("\n")[start - 1]
    first, _ = capstone.decorator_lines(tmp_path)
    assert line("target-app/auth.py", first).startswith("def require_order_access")


def test_the_cold_review_skips_test_files():
    """Test files hold the exploits; a cold review of them reports the tested bugs as test bugs."""
    import json
    import subprocess

    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "reference-pipeline" / "review.py"),
         "--file", "target-app", "--no-scanner", "--dry-run"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    reviewed = [p["user"] for p in json.loads(completed.stdout)["prompts"]]
    assert reviewed
    assert not any("Numbered source of target-app/tests/" in u for u in reviewed)
    assert "skips 3 test file(s)" in completed.stderr


def test_path_traversal_at_the_endpoint_counts_when_it_says_traversal():
    hit = dict(finding("target-app/app.py", 87, "Missing input validation", end=88),
               explanation="An attacker can pass ../../etc/passwd as the name.")
    miss = dict(finding("target-app/app.py", 87, "Missing input validation", end=88),
                explanation="The name is not validated.")
    assert score_planted.score([hit])[0][4]["found"]
    assert not score_planted.score([miss])[0][4]["found"]


def test_tournament_points_reward_bugs_and_charge_for_noise():
    results, extras = score_planted.score([
        finding("target-app/models.py", 59),
        finding("target-app/app.py", 3, "Something unrelated"),
    ])
    assert score_planted.points(results, extras) == 10 - 2


def test_findings_written_by_windows_powershell_still_load(tmp_path):
    """Windows PowerShell 5.1 writes `>` redirects as UTF-16 with a byte order mark."""
    body = '{"findings": [{"file": "target-app/models.py", "line_start": 59, "line_end": 59, "title": "SQLi", "severity": "high"}]}'
    utf16, bom8 = tmp_path / "ps51.json", tmp_path / "bom.json"
    utf16.write_bytes(body.encode("utf-16"))
    bom8.write_bytes(body.encode("utf-8-sig"))
    assert len(score_planted.load([str(utf16), str(bom8)])) == 2


def test_review_and_post_comment_read_utf16_files(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "reference-pipeline"))
    import post_comment
    import review
    text = "diff --git a/x b/x\n+line\n"
    f = tmp_path / "pr.diff"
    f.write_bytes(text.encode("utf-16"))
    assert review.read_input_text(f) == text
    assert post_comment.read_input_text(f) == text


def test_sweep_adds_a_cold_review_after_triage():
    """--sweep: scanner findings are triaged, then each file is cold-reviewed too."""
    import json
    import subprocess

    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "reference-pipeline" / "review.py"),
         "--file", "target-app/app.py", "--sweep", "--dry-run"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    users = [p["user"] for p in json.loads(completed.stdout)["prompts"]]
    assert sum(u.startswith("Scanner:") for u in users) >= 1
    sweep = [u for u in users if u.startswith("Already-known findings")]
    assert len(sweep) == 1 and "line 15" in sweep[0]
