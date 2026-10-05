"""Integration tests using isolated Git worktrees."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/pre-pr-review/scripts/find_review_history.py"
spec = importlib.util.spec_from_file_location("find_review_history", SCRIPT)
finder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finder)


class FindReviewHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.main = self.base / 'main 履歴 "project"'
        self.main.mkdir()
        self.git("init", str(self.main))
        self.git("-C", str(self.main), "-c", "user.name=Test", "-c",
                 "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                 "commit", "--allow-empty", "-m", "Initial")
        self.worktree = self.base / 'linked 作業 "tree"'
        self.git("-C", str(self.main), "worktree", "add", "--detach", str(self.worktree))

    def git(self, *args):
        return subprocess.run(["git", *args], check=True, capture_output=True)

    def history(self, root, runtime="codex"):
        directory = ".agents" if runtime == "codex" else ".claude"
        path = root / directory / "skills/review-history/SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Review history\n", encoding="utf-8")
        return path

    def run_finder(self, repo=None, runtime="codex"):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--runtime", runtime, "--repo",
             str(repo or self.worktree)], capture_output=True, text=True
        )
        return process.returncode, json.loads(process.stdout)

    def test_main_fallback_from_nested_directory(self):
        path = self.history(self.main)
        nested = self.worktree / "src/nested"
        nested.mkdir(parents=True)
        code, result = self.run_finder(nested)
        self.assertEqual(code, 0)
        self.assertEqual(result["path"], str(path))
        self.assertEqual(result["source"], "main")
        self.assertEqual(len(result["searched_paths"]), 2)

    def test_current_takes_precedence(self):
        self.history(self.main)
        path = self.history(self.worktree)
        code, result = self.run_finder()
        self.assertEqual(code, 0)
        self.assertEqual(result["path"], str(path))
        self.assertEqual(result["source"], "current")
        self.assertEqual(result["searched_paths"], [str(path)])

    def test_runtime_selects_history_location(self):
        claude = self.history(self.main, "claude")
        codex = self.history(self.main, "codex")
        for runtime, path in (("claude", claude), ("codex", codex)):
            with self.subTest(runtime=runtime):
                code, result = self.run_finder(runtime=runtime)
                self.assertEqual(code, 0)
                self.assertEqual(result["path"], str(path))

    def test_missing_does_not_search_other_worktrees(self):
        other = self.base / "other"
        self.git("-C", str(self.main), "worktree", "add", "--detach", str(other))
        self.history(other)
        code, result = self.run_finder()
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(len(result["searched_paths"]), 2)

    def test_main_worktree_is_checked_once(self):
        code, result = self.run_finder(self.main)
        self.assertEqual(code, 1)
        self.assertEqual(len(result["searched_paths"]), 1)

    def test_invalid_current_file_is_error_without_fallback(self):
        self.history(self.main)
        path = self.history(self.worktree)
        path.unlink()
        path.mkdir()
        code, result = self.run_finder()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["searched_paths"], [str(path)])

    def test_permission_failure_is_error(self):
        path = self.history(self.worktree)
        self.history(self.main)
        with patch.object(Path, "open", side_effect=PermissionError("Permission denied")):
            result = finder.discover(self.worktree, "codex")
        self.assertEqual(result["status"], "error")
        self.assertIn("Permission denied", result["error"])
        self.assertEqual(result["searched_paths"], [str(path)])

    def test_broken_symlink_is_error(self):
        path = self.history(self.worktree)
        path.unlink()
        path.symlink_to("missing.md")
        code, result = self.run_finder()
        self.assertEqual(code, 2)
        self.assertIn("Broken symlink", result["error"])

    def test_non_repository_is_error(self):
        code, result = self.run_finder(self.base)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["searched_paths"], [])

    def test_default_repo_is_current_directory(self):
        path = self.history(self.main)
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--runtime", "codex"],
            cwd=self.worktree, capture_output=True, text=True
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout)["path"], str(path))


if __name__ == "__main__":
    unittest.main()
