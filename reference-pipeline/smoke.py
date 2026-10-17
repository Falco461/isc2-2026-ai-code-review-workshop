#!/usr/bin/env python3
"""Smoke test for the review pipeline.

Runs review.py against target-app and checks that the output is valid
JSON, conforms to the findings schema, and reports the three planted bugs
that Phase 1 can actually reach.

  python smoke.py            full run, needs Ollama and the model
  python smoke.py --dry-run  renders the prompts only, no model needed

The dry run is what CI uses, because CI runners have no model.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import review

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
TARGET = REPO_ROOT / "target-app"

# The three planted bugs the Phase 1 pipeline can reach. Path traversal
# and BOLA are deliberately absent: no scanner rule fires on either, and
# the model cannot see them without the repo-read tool from Module 3.
# See target-app/PLANTED.md.
REQUIRED_BUGS = [
    ("SQL injection", "target-app/models.py", 59),
    ("hardcoded secret", "target-app/app.py", 15),
    ("command injection", "target-app/storage.py", 38),
]

REQUIRED_FINDING_KEYS = {
    "id",
    "severity",
    "title",
    "file",
    "line_start",
    "line_end",
    "evidence",
    "explanation",
    "scanner_ref",
    "confidence",
}


class SmokeFailure(Exception):
    """Raised when a check fails, so every failure names its fix."""


def run_review(dry_run):
    """Invoke review.py as a subprocess, the way a user would."""
    command = [sys.executable, str(HERE / "review.py"), "--file", str(TARGET)]
    if dry_run:
        command.append("--dry-run")

    completed = subprocess.run(command, capture_output=True, text=True)

    if completed.returncode != 0:
        raise SmokeFailure(
            "review.py exited %d. Its error output was:\n%s"
            % (completed.returncode, completed.stderr.strip() or "(nothing)")
        )
    if not completed.stdout.strip():
        raise SmokeFailure("review.py printed nothing to stdout.")

    try:
        return json.loads(completed.stdout), completed.stderr
    except json.JSONDecodeError as exc:
        raise SmokeFailure(
            "review.py stdout was not valid JSON (%s). First 300 characters:\n%s"
            % (exc, completed.stdout[:300])
        ) from exc


def check_schema(document):
    """Every field the schema promises is present and the right type."""
    for key in ("model", "target", "findings", "no_findings_reason"):
        if key not in document:
            raise SmokeFailure("output is missing the '%s' key." % key)

    if not isinstance(document["findings"], list):
        raise SmokeFailure("'findings' must be a list.")

    if not document["findings"] and not document["no_findings_reason"]:
        raise SmokeFailure(
            "findings is empty but no_findings_reason is null. An empty "
            "result must always explain itself."
        )

    for index, finding in enumerate(document["findings"]):
        if not isinstance(finding, dict):
            raise SmokeFailure("finding %d is not an object." % index)

        missing = REQUIRED_FINDING_KEYS - set(finding)
        if missing:
            raise SmokeFailure(
                "finding %d is missing %s." % (index, ", ".join(sorted(missing)))
            )

        if finding["severity"] not in review.SEVERITIES:
            raise SmokeFailure(
                "finding %d has severity '%s', which is not one of %s."
                % (index, finding["severity"], review.SEVERITIES)
            )
        if finding["confidence"] not in review.CONFIDENCES:
            raise SmokeFailure(
                "finding %d has confidence '%s', which is not one of %s."
                % (index, finding["confidence"], review.CONFIDENCES)
            )

        for key in ("line_start", "line_end"):
            if not isinstance(finding[key], int) or finding[key] < 1:
                raise SmokeFailure(
                    "finding %d has %s=%r, which is not a line number."
                    % (index, key, finding[key])
                )

        if finding["line_end"] < finding["line_start"]:
            raise SmokeFailure("finding %d has line_end before line_start." % index)

        if not str(finding["file"]).strip():
            raise SmokeFailure(
                "finding %d cites no file. Citation-required should have "
                "dropped it in review.py." % index
            )


def check_required_bugs(document):
    """The three reachable planted bugs are all reported.

    A finding counts when its cited range covers the bug's line. Models
    cite a whole statement, so a multi-line subprocess.run call can start
    a line or two above the line Bandit flags.
    """
    missed = []
    for label, path, line in REQUIRED_BUGS:
        covered = any(
            f["file"] == path and f["line_start"] <= line <= f["line_end"]
            for f in document["findings"]
        )
        if not covered:
            missed.append("%s (expected %s:%d)" % (label, path, line))

    if missed:
        raise SmokeFailure(
            "the review did not report:\n  %s\n"
            "Check that the model in config.toml is qwen3.5:9b with think = false. "
            "See docs/MODEL_EVAL.md for which models pass." % "\n  ".join(missed)
        )


def check_dry_run(document):
    """The dry run renders real prompts without calling the model."""
    if not document.get("dry_run"):
        raise SmokeFailure("dry run output is missing the 'dry_run' flag.")

    prompts = document.get("prompts")
    if not prompts:
        raise SmokeFailure(
            "dry run rendered no prompts. The scanners found nothing, which "
            "usually means detect-secrets or bandit failed silently."
        )

    for index, prompt in enumerate(prompts):
        for key in ("system", "user"):
            if not str(prompt.get(key, "")).strip():
                raise SmokeFailure("prompt %d has an empty '%s'." % (index, key))
        if "Numbered source:" not in prompt["user"]:
            raise SmokeFailure(
                "prompt %d does not include numbered source, so the model "
                "could not cite a line even if it wanted to." % index
            )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="smoke.py", description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render prompts without calling the model (used by CI)",
    )
    args = parser.parse_args(argv)

    mode = "dry run" if args.dry_run else "full run"
    print("Smoke test, %s, against %s" % (mode, TARGET))

    try:
        document, stderr = run_review(args.dry_run)

        if args.dry_run:
            check_dry_run(document)
            print("  prompts rendered: %d" % len(document["prompts"]))
            print("  scanner findings: %d" % document["scanner_findings"])
        else:
            check_schema(document)
            print("  model:    %s" % document["model"])
            print("  findings: %d" % len(document["findings"]))
            check_required_bugs(document)
            for label, path, line in REQUIRED_BUGS:
                print("  found %s at %s:%d" % (label, path, line))

        if stderr.strip():
            print("\n  review.py warnings:")
            for line in stderr.strip().splitlines():
                print("    %s" % line)

    except SmokeFailure as failure:
        print("\nSMOKE TEST FAILED\n\n%s" % failure, file=sys.stderr)
        return 1

    print("\nSMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
