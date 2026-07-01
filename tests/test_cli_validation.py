from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent import cli


class CliValidationTests(unittest.TestCase):
    def run_cli(self, argv: list[str], *, env: dict[str, str] | None = None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(argv, environ=env or {}, stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def make_valid_task(self, root: Path) -> Path:
        task = root / "task"
        task.mkdir()
        (task / "statement.md").write_text("Solve the sample task.\n", encoding="utf-8")
        (task / "solution.py").write_text("print('placeholder')\n", encoding="utf-8")
        tests = task / "tests"
        tests.mkdir()
        (tests / "sample1.in").write_text("1\n", encoding="utf-8")
        (tests / "sample1.out").write_text("1\n", encoding="utf-8")
        return task

    def test_missing_openai_api_key_exits_nonzero_with_helpful_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))

            code, stdout, stderr = self.run_cli(["solve", str(task)], env={})

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            'OPENAI_API_KEY is not set.\n'
            "Set it with:\n"
            'export OPENAI_API_KEY="..."\n',
        )

    def test_openai_api_key_is_checked_before_task_validation(self):
        code, stdout, stderr = self.run_cli(["solve", "/path/that/does/not/exist"], env={})

        self.assertNotEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertIn("OPENAI_API_KEY is not set.", stderr)
        self.assertNotIn("Task validation failed", stderr)

    def test_rejects_missing_task_directory(self):
        code, stdout, stderr = self.run_cli(
            ["solve", "/path/that/does/not/exist"],
            env={"OPENAI_API_KEY": "test-key"},
        )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Task validation failed:", stderr)
        self.assertIn("does not exist", stderr)

    def test_rejects_task_missing_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))
            (task / "statement.md").unlink()

            code, stdout, stderr = self.run_cli(
                ["solve", str(task)],
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Missing required file: statement.md", stderr)

    def test_rejects_task_missing_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))
            (task / "solution.py").unlink()

            code, stdout, stderr = self.run_cli(
                ["solve", str(task)],
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Missing required file: solution.py", stderr)

    def test_rejects_task_missing_tests_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))
            for child in (task / "tests").iterdir():
                child.unlink()
            (task / "tests").rmdir()

            code, stdout, stderr = self.run_cli(
                ["solve", str(task)],
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Missing required directory: tests/", stderr)

    def test_rejects_task_without_matching_test_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))
            (task / "tests" / "sample1.out").unlink()

            code, stdout, stderr = self.run_cli(
                ["solve", str(task)],
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("at least one matching .in / .out pair", stderr)

    def test_accepts_valid_task_and_stops_at_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))

            code, stdout, stderr = self.run_cli(
                ["solve", str(task)],
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Task validation passed:", stdout)
        self.assertIn("Tests discovered: 1", stdout)
        self.assertIn("Agent loop is not implemented yet.", stdout)

    def test_accepts_supported_solve_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))

            code, stdout, stderr = self.run_cli(
                [
                    "solve",
                    str(task),
                    "--max-iterations",
                    "3",
                    "--timeout-seconds",
                    "1.5",
                    "--trace-file",
                    "custom-trace.jsonl",
                    "--verbose",
                ],
                env={"OPENAI_API_KEY": "test-key"},
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Agent loop is not implemented yet.", stdout)

    def test_module_entrypoint_reaches_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = "test-key"
            env["PYTHONPATH"] = str(SRC)

            result = subprocess.run(
                [sys.executable, "-m", "cp_agent", "solve", str(task)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("Agent loop is not implemented yet.", result.stdout)


if __name__ == "__main__":
    unittest.main()
