#!/usr/bin/env python3
"""Locate repository-specific review history without modifying the repository."""

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


class DiscoveryError(Exception):
    pass


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise DiscoveryError(os.fsdecode(result.stderr).strip())
    return result.stdout


def discover(repo, runtime):
    result = {"status": "error", "path": None, "source": None, "searched_paths": []}
    try:
        root = Path(os.fsdecode(git(repo, "rev-parse", "--show-toplevel")).rstrip("\n"))
        relative = Path(".claude" if runtime == "claude" else ".agents") / "skills/review-history/SKILL.md"
        candidates = [(root, "current")]
        # Query the main worktree only after the current candidate is absent.
        while candidates:
            worktree, source = candidates.pop(0)
            path = worktree / relative
            result["searched_paths"].append(str(path))
            try:
                metadata = path.stat()
            except FileNotFoundError:
                if path.is_symlink():
                    raise DiscoveryError(f"Broken symlink: {path}")
            else:
                if not stat.S_ISREG(metadata.st_mode):
                    raise DiscoveryError(f"Not a regular file: {path}")
                # Confirm readability; do not expose history contents in the output.
                with path.open("rb") as history:
                    history.read()
                result.update(status="found", path=str(path), source=source)
                return result
            if source == "current":
                listing = git(root, "worktree", "list", "--porcelain", "-z")
                first = listing.split(b"\0", 1)[0]
                if not first.startswith(b"worktree "):
                    raise DiscoveryError("Cannot identify the main worktree")
                main = Path(os.fsdecode(first[len(b"worktree "):]))
                if main.resolve() != root.resolve():
                    candidates.append((main, "main"))
        result["status"] = "missing"
    except (OSError, DiscoveryError) as error:
        result["error"] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("claude", "codex"), required=True)
    parser.add_argument("--repo", default=".", help="Directory inside the target worktree (default: cwd)")
    args = parser.parse_args()
    result = discover(args.repo, args.runtime)
    print(json.dumps(result, ensure_ascii=True))
    return {"found": 0, "missing": 1, "error": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
