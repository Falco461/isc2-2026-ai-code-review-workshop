#!/usr/bin/env python3
"""Module 8 capstone: does the bot catch broken access control in a pull request?

The pull request adds an invoice endpoint guarded by
@auth.require_order_access. On its own the endpoint looks correct. The
decorator, in another file, checks only that someone is logged in, never
that they own the order. A reviewer that sees only the diff should pass
it. A reviewer that reads the decorator should not.

  python eval-harness/capstone.py               both configurations, 3 runs each
  python eval-harness/capstone.py --reps 5
  REVIEW_MODEL=gpt-oss:20b REVIEW_THINK=low python eval-harness/capstone.py

Runs in a temporary copy of the code, like the attack lab. Your checkout
is never changed. The model and settings come from config.toml or the
REVIEW_* environment variables, exactly as for review.py.
"""

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "attack-lab"))

import run_attack  # noqa: E402  (reuses its copy helper)

APP = "target-app/app.py"
ANCHOR = 'if __name__ == "__main__":'
ENDPOINT = '''@app.route("/api/orders/<int:order_id>/invoice")
@auth.require_order_access
def order_invoice(order_id):
    """Return the invoice for one of the caller's orders."""
    order = models.get_order(order_id)
    if order is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "invoice": {
            "order_id": order["id"],
            "item": order["item"],
            "total_cents": order["total_cents"],
        }
    })


'''
DECORATOR = ("target-app/auth.py", "def require_order_access")
ACCESS_WORDS = re.compile(r"author|owner|ownership|idor|bola|another user|other user|any user|any order|access control", re.I)

CONFIGS = {
    "diff only": [],
    "diff + repo-read": ["--repo-read"],
}


def apply_pull_request(root):
    """Add the endpoint and return the unified diff of the change."""
    path = root / APP
    before = path.read_text(encoding="utf-8")
    if ANCHOR not in before:
        run_attack.fail("cannot find %r in %s" % (ANCHOR, APP))
    after = before.replace(ANCHOR, ENDPOINT + ANCHOR, 1)
    path.write_text(after, encoding="utf-8")
    diff = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/" + APP, tofile="b/" + APP,
    )
    return "".join(diff), after


def endpoint_lines(after):
    lines = after.split("\n")
    start = next(i for i, l in enumerate(lines, 1) if "def order_invoice" in l) - 2
    return start, start + ENDPOINT.count("\n") - 2


def decorator_lines(root):
    file, anchor = DECORATOR
    lines = (root / file).read_text(encoding="utf-8").split("\n")
    start = next(i for i, l in enumerate(lines, 1) if l.startswith(anchor))
    end = next((i for i, l in enumerate(lines[start:], start + 1) if l.startswith("def ")), len(lines)) - 1
    return start, end


def found_bola(findings, root, after):
    spots = {APP: endpoint_lines(after), DECORATOR[0]: decorator_lines(root)}
    for f in findings:
        span = spots.get(f["file"].replace("\\", "/"))
        if not span:
            continue
        overlaps = f["line_start"] <= span[1] and f["line_end"] >= span[0]
        if overlaps and f["severity"] != "info" and ACCESS_WORDS.search(f["title"]):
            return f
    return None


def run_once(flags):
    root = run_attack.make_copy()
    try:
        diff, after = apply_pull_request(root)
        (root / "pr.diff").write_text(diff, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(root / "reference-pipeline" / "review.py"), "--diff", "pr.diff", "--no-scanner", *flags],
            cwd=root, capture_output=True, text=True,
        )
        if completed.returncode != 0:
            run_attack.fail("review.py failed:\n%s" % completed.stderr.strip()[-600:])
        findings = json.loads(completed.stdout)["findings"]
        return found_bola(findings, root, after), findings
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score the Module 8 capstone.")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = []
    for name, flags in CONFIGS.items():
        hits = 0
        for rep in range(args.reps):
            hit, findings = run_once(flags)
            hits += bool(hit)
            results.append({"config": name, "rep": rep + 1, "found": bool(hit),
                            "where": "%s:%d" % (hit["file"], hit["line_start"]) if hit else None,
                            "title": hit["title"] if hit else None, "findings": len(findings)})
            if not args.json:
                print("%-18s run %d: %s" % (name, rep + 1,
                      "FOUND  %s:%d  %s" % (hit["file"], hit["line_start"], hit["title"]) if hit else "missed"))
        if not args.json:
            print("%-18s %d of %d\n" % (name, hits, args.reps))
    if args.json:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
