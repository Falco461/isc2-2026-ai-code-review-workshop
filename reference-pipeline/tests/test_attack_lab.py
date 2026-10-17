"""Every Module 5 attack still applies to the current target app.

No model calls. Attacks are anchored to lines of code, so an edit to
target-app can silently break one. This applies each attack to a scratch
copy and checks that every targeted bug can still be located.
"""

import shutil
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[2] / "attack-lab"
sys.path.insert(0, str(LAB))

import run_attack  # noqa: E402
from attacks import ATTACKS  # noqa: E402


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_attack_applies_and_targets_are_found(name):
    spec = ATTACKS[name]
    root = run_attack.make_copy()
    try:
        for edit in spec["edits"]:
            run_attack.apply_edit(root, edit)
        for label, file, anchor, _span in spec["targets"]:
            assert run_attack.anchor_line(root, file, anchor), "%s: cannot find %s in %s" % (name, label, file)
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_attack_changes_something(name):
    spec = ATTACKS[name]
    root = run_attack.make_copy()
    try:
        files = {e["file"] for e in spec["edits"]}
        before = {f: (root / f).read_text(encoding="utf-8") for f in files}
        for edit in spec["edits"]:
            run_attack.apply_edit(root, edit)
        assert any((root / f).read_text(encoding="utf-8") != before[f] for f in files)
    finally:
        shutil.rmtree(root, ignore_errors=True)
