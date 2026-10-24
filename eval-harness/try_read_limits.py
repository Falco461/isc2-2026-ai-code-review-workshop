#!/usr/bin/env python3
"""Ask the repo-read tool for things it must refuse (Module 8, section 4).

  python eval-harness/try_read_limits.py

Expect two refusals and a "not found". No model needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reference-pipeline"))
import review  # noqa: E402

ATTEMPTS = [
    ("target-app/../reference-pipeline/review.py", "main"),
    ("target-app/tests/conftest.py", "login"),
    ("target-app/auth.py", "nope"),
]


def main():
    config = review.load_config()
    scope = review.repo_scope("target-app/app.py")
    for file, symbol in ATTEMPTS:
        print(review.read_symbol({"file": file, "symbol": symbol}, scope, config)[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
