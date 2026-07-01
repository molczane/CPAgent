from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent import test_runner


class TestRunnerTests(unittest.TestCase):
    def make_task(
        self,
        root: Path,
        *,
        solution: str,
        cases: dict[str, tuple[str, str]] | None = None,
    ) -> Path:
        task = root / "task"
        task.mkdir()
        (task / "statement.md").write_text("Test task.\n", encoding="utf-8")
        (task / "solution.py").write_text(solution, encoding="utf-8")
        tests = task / "tests"
        tests.mkdir()

        for name, (input_text, output_text) in (cases or {}).items():
            (tests / f"{name}.in").write_text(input_text, encoding="utf-8")
            (tests / f"{name}.out").write_text(output_text, encoding="utf-8")

        return task

    def run_task(
        self,
        task: Path,
        *,
        timeout_seconds: float = 2,
        max_stdout_chars: int = 10000,
        max_stderr_chars: int = 10000,
    ) -> dict:
        return test_runner.run_tests(
            task,
            timeout_seconds=timeout_seconds,
            max_stdout_chars=max_stdout_chars,
            max_stderr_chars=max_stderr_chars,
            python_executable=sys.executable,
        )

    def test_discovers_sorted_matching_test_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution="print('unused')\n",
                cases={
                    "sample2": ("2\n", "2\n"),
                    "sample1": ("1\n", "1\n"),
                },
            )
            tests = task / "tests"
            (tests / "orphan.in").write_text("ignored\n", encoding="utf-8")
            (tests / "lonely.out").write_text("ignored\n", encoding="utf-8")

            cases = test_runner.discover_tests(task)

        self.assertEqual([case.name for case in cases], ["sample1", "sample2"])

    def test_passing_solution_returns_success_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution=(
                    "import sys\n"
                    "value = sys.stdin.read().strip()\n"
                    "print(value)\n"
                ),
                cases={
                    "sample1": ("4\n", "4\n"),
                    "sample2": ("7\n", "7\n"),
                },
            )

            result = self.run_task(task)

        self.assertTrue(result["ok"])
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["summary"], "2/2 tests passed")
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(test["passed"] for test in result["results"]))
        json.dumps(result)

    def test_wrong_answer_includes_expected_and_actual(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution="print(6)\n",
                cases={"sample1": ("", "7\n")},
            )

            result = self.run_task(task)

        self.assertTrue(result["ok"])
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["summary"], "0/1 tests passed")
        failure = result["results"][0]
        self.assertFalse(failure["passed"])
        self.assertEqual(failure["exit_code"], 0)
        self.assertEqual(failure["expected"], "7")
        self.assertEqual(failure["actual"], "6")
        self.assertEqual(failure["stderr"], "")

    def test_runtime_error_captures_nonzero_exit_code_and_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution="raise RuntimeError('boom')\n",
                cases={"sample1": ("", "")},
            )

            result = self.run_task(task, max_stderr_chars=10000)

        failure = result["results"][0]
        self.assertFalse(failure["passed"])
        self.assertNotEqual(failure["exit_code"], 0)
        self.assertIn("RuntimeError", failure["stderr"])
        self.assertIn("boom", failure["stderr"])

    def test_syntax_error_captures_failure_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution="def broken(:\n    pass\n",
                cases={"sample1": ("", "")},
            )

            result = self.run_task(task)

        failure = result["results"][0]
        self.assertFalse(failure["passed"])
        self.assertNotEqual(failure["exit_code"], 0)
        self.assertIn("SyntaxError", failure["stderr"])

    def test_timeout_returns_structured_timeout_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution="import time\ntime.sleep(5)\n",
                cases={"sample1": ("", "")},
            )

            result = self.run_task(task, timeout_seconds=0.1)

        failure = result["results"][0]
        self.assertFalse(failure["passed"])
        self.assertIsNone(failure["exit_code"])
        self.assertEqual(failure["error"], "timeout")
        self.assertIsInstance(failure["runtime_ms"], int)

    def test_output_comparison_normalizes_trailing_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution="import sys\nsys.stdout.write('a   \\nb\\t \\n\\n')\n",
                cases={"sample1": ("", "a\nb\n")},
            )

            result = self.run_task(task)

        self.assertTrue(result["all_passed"])
        self.assertEqual(result["results"][0]["actual"], "a\nb")
        self.assertEqual(result["results"][0]["expected"], "a\nb")

    def test_captured_stdout_and_stderr_are_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(
                Path(tmp),
                solution=(
                    "import sys\n"
                    "sys.stdout.write('x' * 80)\n"
                    "sys.stderr.write('e' * 80)\n"
                    "raise SystemExit(1)\n"
                ),
                cases={"sample1": ("", "")},
            )

            result = self.run_task(
                task,
                max_stdout_chars=25,
                max_stderr_chars=30,
            )

        failure = result["results"][0]
        self.assertLessEqual(len(failure["actual"]), 25)
        self.assertLessEqual(len(failure["stderr"]), 30)
        self.assertIn("truncated", failure["actual"])
        self.assertIn("truncated", failure["stderr"])


if __name__ == "__main__":
    unittest.main()
