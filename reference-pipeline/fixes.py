"""Suggested fixes: one model call per finding, checked before anyone sees it.

The suggestion is posted on the pull request or merge request line, where a
human reviews it and applies it with one click. The model writes the code,
and the code under review can influence the model, so nothing here is ever
committed automatically.
"""

import re

import review

FIX_SCHEMA = {
    "type": "object",
    "properties": {
        "replacement": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["replacement", "rationale"],
}

CONTEXT_LINES = 5
MAX_EXTRA_LINES = 6
MAX_SPAN = 8


def cited_lines(finding):
    path = review.REPO_ROOT / finding["file"]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines


def build_fix_user(finding, lines):
    start, end = finding["line_start"], finding["line_end"]
    lo, hi = max(1, start - CONTEXT_LINES), min(len(lines), end + CONTEXT_LINES)
    numbered = "\n".join("%d: %s" % (n, lines[n - 1]) for n in range(lo, hi + 1))
    return (
        "Finding: %s (%s)\nWhy: %s\nReplace lines %d to %d of %s.\n\nNumbered source:\n%s"
        % (finding.get("title", ""), finding.get("severity", ""), finding.get("explanation", ""),
           start, end, finding["file"], numbered)
    )


def check_fix(original, replacement):
    """Return the cleaned replacement lines, or None if it should not be posted."""
    if not isinstance(replacement, str) or not replacement.strip():
        return None
    if "```" in replacement:
        return None
    new = [re.sub(r"^\s*\d+:\s?", "", line) for line in replacement.strip("\n").splitlines()]
    if len(new) > len(original) + MAX_EXTRA_LINES:
        return None
    if [l.rstrip() for l in new] == [l.rstrip() for l in original]:
        return None
    # A patch that keeps every original line exactly, and only adds lines
    # around them, has not changed the defect. Re-indenting counts as a change.
    kept = {l.rstrip() for l in new}
    if all(l.rstrip() in kept for l in original if l.strip()):
        return None
    return new


def suggest_fix(config, prompts, finding):
    """Ask for a fix to one finding. Returns {"lines", "rationale"} or None."""
    start, end = finding["line_start"], finding["line_end"]
    if end - start + 1 > MAX_SPAN:
        return None
    try:
        lines = cited_lines(finding)
    except OSError:
        return None
    if end > len(lines):
        return None
    result = review.call_model(config, prompts["fix"], build_fix_user(finding, lines), FIX_SCHEMA)
    if not isinstance(result, dict):
        return None
    rationale = str(result.get("rationale", "")).strip()
    new = check_fix(lines[start - 1:end], result.get("replacement"))
    if new is None:
        # No safe one-click patch: still pass on the advice, without a button.
        return {"lines": None, "rationale": rationale} if rationale else None
    return {"lines": new, "rationale": rationale}
