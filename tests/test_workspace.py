from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def make_task(self, root: Path) -> Path:
        task = root / "task"
        task.mkdir()
        (task / "statement.md").write_text("Statement\n", encoding="utf-8")
        (task / "solution.py").write_text("print('old')\n", encoding="utf-8")
        (task / "notes.txt").write_text("not readable\n", encoding="utf-8")
        tests = task / "tests"
        tests.mkdir()
        (tests / "sample2.in").write_text("2\n", encoding="utf-8")
        (tests / "sample2.out").write_text("2\n", encoding="utf-8")
        (tests / "sample1.in").write_text("1\n", encoding="utf-8")
        (tests / "sample1.out").write_text("1\n", encoding="utf-8")
        return task

    def test_list_files_returns_only_allowed_relative_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            workspace = Workspace(task)

            files = workspace.list_files()

        self.assertEqual(
            files,
            [
                "solution.py",
                "statement.md",
                "tests/sample1.in",
                "tests/sample1.out",
                "tests/sample2.in",
                "tests/sample2.out",
            ],
        )

    def test_read_file_allows_statement_solution_and_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            workspace = Workspace(task)

            statement = workspace.read_file("statement.md")
            solution = workspace.read_file("solution.py")
            sample = workspace.read_file("tests/sample1.in")

        self.assertEqual(statement["content"], "Statement\n")
        self.assertEqual(solution["content"], "print('old')\n")
        self.assertEqual(sample["content"], "1\n")

    def test_read_file_rejects_missing_unlisted_and_escape_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_task(root)
            outside = root / "secret.txt"
            outside.write_text("secret\n", encoding="utf-8")
            workspace = Workspace(task)

            cases = [
                "missing.md",
                "notes.txt",
                "../secret.txt",
                str(outside),
                "~/.ssh/id_rsa",
            ]
            results = [workspace.read_file(path) for path in cases]

        self.assertTrue(all(result == {
            "ok": False,
            "error": "File not found or not allowed",
        } for result in results))

    def test_read_file_rejects_symlink_that_resolves_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_task(root)
            outside = root / "outside.in"
            outside.write_text("secret\n", encoding="utf-8")
            link = task / "tests" / "leak.in"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink not available: {exc}")
            workspace = Workspace(task)

            result = workspace.read_file("tests/leak.in")

        self.assertEqual(
            result,
            {"ok": False, "error": "File not found or not allowed"},
        )

    def test_read_file_truncates_large_files_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            (task / "statement.md").write_text("abcdef", encoding="utf-8")
            workspace = Workspace(task)

            result = workspace.read_file("statement.md", max_chars=3)

        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "abc")
        self.assertTrue(result["truncated"])
        self.assertIn("truncated", result["warning"])

    def test_write_solution_replaces_solution_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            workspace = Workspace(task)

            result = workspace.write_solution("print('new snowman: ☃')\n")

            solution = (task / "solution.py").read_text(encoding="utf-8")
            backup = (task / ".solution.py.bak").read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {
                "ok": True,
                "path": "solution.py",
                "bytes_written": len("print('new snowman: ☃')\n".encode("utf-8")),
            },
        )
        self.assertEqual(solution, "print('new snowman: ☃')\n")
        self.assertEqual(backup, "print('old')\n")

    def test_write_solution_rejects_solution_symlink_to_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_task(root)
            outside = root / "outside_solution.py"
            outside.write_text("outside\n", encoding="utf-8")
            (task / "solution.py").unlink()
            try:
                (task / "solution.py").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink not available: {exc}")
            workspace = Workspace(task)

            result = workspace.write_solution("print('new')\n")

            outside_content = outside.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"ok": False, "error": "solution.py is not writable or not allowed"},
        )
        self.assertEqual(outside_content, "outside\n")

    def test_write_solution_rejects_backup_symlink_to_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_task(root)
            outside = root / "outside_backup.py"
            outside.write_text("outside backup\n", encoding="utf-8")
            try:
                (task / ".solution.py.bak").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink not available: {exc}")
            workspace = Workspace(task)

            result = workspace.write_solution("print('new')\n")

            solution_content = (task / "solution.py").read_text(encoding="utf-8")
            outside_content = outside.read_text(encoding="utf-8")

        self.assertEqual(
            result,
            {"ok": False, "error": "solution.py is not writable or not allowed"},
        )
        self.assertEqual(solution_content, "print('old')\n")
        self.assertEqual(outside_content, "outside backup\n")


if __name__ == "__main__":
    unittest.main()
