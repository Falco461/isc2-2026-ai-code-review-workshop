#!/usr/bin/env python3
"""Score review.py output against the six planted bugs in target-app/PLANTED.md.

Pass one or more findings files. Findings from every file are pooled, so
a scanner run and a repo-read sweep can be scored together, the way a
pipeline that runs both would report them.

  python reference-pipeline/review.py --file target-app > scanner.json
  python reference-pipeline/review.py --file target-app --no-scanner --repo-read > sweep.json
  python eval-harness/score_planted.py scanner.json sweep.json

A planted bug counts as found when a finding that is not `info` covers
one of its lines. Where a bug shows up in a second place, such as the
endpoint that calls the vulnerable helper, a finding there must also
name the bug, so a finding about something else on the same lines does
not count. Findings that match no planted bug are listed
too: some are real extra issues, some are noise. Deciding which is the
discussion.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ACCESS_WORDS = re.compile(
    r"author|owner|ownership|idor|bola|another user|other user|any user|any order|access control", re.I
)

TRAVERSAL_WORDS = re.compile(r"travers|\.\./|outside the upload|arbitrary file", re.I)

# Each planted bug lists the spots where a finding counts:
# (file, first line, last line, pattern, where the pattern must appear).
# A pattern of None means any non-info finding on those lines counts. The
# access-control spots match on the title only, because a finding that
# trusts the decorator still says "authorized" in its explanation.
PLANTED = [
    (1, "BOLA on GET /api/orders/<id>", [
        ("target-app/auth.py", 33, 47, ACCESS_WORDS, ("title",)),
        ("target-app/app.py", 47, 58, ACCESS_WORDS, ("title",)),
    ]),
    (2, "SQL injection in the order search", [("target-app/models.py", 59, 59, None, ())]),
    (3, "Hardcoded secrets in source", [("target-app/app.py", 15, 17, None, ())]),
    (4, "Command injection in GET /api/export", [("target-app/storage.py", 37, 40, None, ())]),
    (5, "Path traversal in GET /api/download", [
        ("target-app/storage.py", 25, 25, None, ()),
        ("target-app/app.py", 83, 90, TRAVERSAL_WORDS, ("title", "explanation")),
    ]),
    (6, "Hardcoded universal password", [("target-app/auth.py", 56, 56, None, ())]),
]



def read_input_text(path):
    """Read a file another tool wrote, whatever its encoding.

    Windows PowerShell 5.1 writes `>` redirects as UTF-16 with a byte order
    mark, and some editors add a UTF-8 one. Both are decoded here, so a
    findings file or diff made on any platform reads the same way.
    """
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def load(paths):
    findings = []
    for path in paths:
        try:
            findings += json.loads(read_input_text(path))["findings"]
        except (OSError, ValueError, KeyError) as exc:
            sys.exit("score_planted: cannot read findings from %s: %s" % (path, exc))
    return findings


def matches(finding, spots):
    if finding.get("severity") == "info":
        return False
    file = finding.get("file", "").replace("\\", "/")
    for spot_file, first, last, pattern, fields in spots:
        if file != spot_file or finding["line_start"] > last or finding["line_end"] < first:
            continue
        if pattern is None or any(pattern.search(finding.get(f) or "") for f in fields):
            return True
    return False


def score(findings):
    results, used = [], set()
    for number, name, spots in PLANTED:
        hits = [i for i, f in enumerate(findings) if matches(f, spots)]
        used.update(hits)
        results.append({"bug": number, "name": name, "found": bool(hits),
                        "by": [findings[i]["title"] for i in hits]})
    extras = [f for i, f in enumerate(findings) if i not in used and f.get("severity") != "info"]
    return results, extras


POINTS_PER_BUG = 10
POINTS_PER_UNMATCHED = -2


def points(results, extras):
    """Module 3 tournament score: a found bug is worth more than a noisy finding costs."""
    return POINTS_PER_BUG * sum(r["found"] for r in results) + POINTS_PER_UNMATCHED * len(extras)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score findings against target-app/PLANTED.md.")
    parser.add_argument("findings", nargs="+", help="review.py JSON output files")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results, extras = score(load(args.findings))
    found = sum(r["found"] for r in results)
    if args.json:
        print(json.dumps({"found": found, "of": len(results), "points": points(results, extras), "bugs": results,
                          "unmatched": [{"file": f["file"], "line": f["line_start"], "title": f["title"]}
                                        for f in extras]}, indent=2))
        return 0

    for r in results:
        print("%d. %-38s %s" % (r["bug"], r["name"], "FOUND  " + r["by"][0] if r["found"] else "missed"))
    print("\n%d of %d planted bugs found." % (found, len(results)))
    if extras:
        print("\n%d finding(s) matched no planted bug. Real, or noise?" % len(extras))
        for f in extras:
            print("  %s:%d  [%s]  %s" % (f["file"], f["line_start"], f["severity"], f["title"]))
    print("\nScore: %d points (%+d per planted bug found, %d per unmatched finding)."
          % (points(results, extras), POINTS_PER_BUG, POINTS_PER_UNMATCHED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
