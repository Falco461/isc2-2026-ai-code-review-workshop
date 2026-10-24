#!/usr/bin/env python3
"""Print every repo-read request in an audit log (Module 8).

  python eval-harness/show_reads.py audit-capstone.jsonl

A repo-read record's prompt is a short "file: symbol" label, so any record
whose prompt is a single line is a read.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reference-pipeline"))
from review import read_input_text  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit("usage: python eval-harness/show_reads.py AUDIT_LOG")
    for line in read_input_text(argv[0]).splitlines():
        if line.strip():
            record = json.loads(line)
            if "\n" not in record["user_prompt"]:
                print("read", record["user_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
