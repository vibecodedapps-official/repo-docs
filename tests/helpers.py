"""Shared helpers for the repo_docs_check test suite.

`run_checker` and `run_checker_json` are plain functions; `can_symlink` is a
plain probe that a test calls (and skips itself on, via self.skipTest)
rather than a fixture that decides for it.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "repo-docs" / "scripts" / "repo_docs_check.py"


def run_checker(*args):
    """Run the checker as a subprocess, the way a real caller would."""

    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def run_checker_json(*args):
    """Run the checker with --json and return (parsed, raw result)."""

    result = run_checker(*args, "--json")
    return json.loads(result.stdout), result


def can_symlink(tmp_path):
    """Probe whether tmp_path's filesystem supports symlinks."""

    target = tmp_path / "_symlink_probe_target"
    link = tmp_path / "_symlink_probe_link"
    target.write_text("x", encoding="utf-8")
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        return False
    return True
