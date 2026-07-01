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
from cp_agent.agent import ModelResponse, ToolCall
from cp_agent.fake_model import ScriptedFakeModelClient
from cp_agent.openai_client import OpenAIClientError


class CliValidationTests(unittest.TestCase):
    def run_cli(
        self,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        model_client_factory=None,
    ):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(
            argv,
            environ=env or {},
            stdout=stdout,
            stderr=stderr,
            model_client_factory=model_client_factory,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def make_valid_task(self, root: Path) -> Path:
        task = root / "task"
        task.mkdir()
        (task / "statement.md").write_text("Solve the sample task.\n", encoding="utf-8")
        (task / "solution.py").write_text(
            "import sys\nprint(sys.stdin.read().strip())\n",
            encoding="utf-8",
        )
        tests = task / "tests"
        tests.mkdir()
        (tests / "sample1.in").write_text("1\n", encoding="utf-8")
        (tests / "sample1.out").write_text("1\n", encoding="utf-8")
        return task

    def make_success_model_factory(self):
        def factory(_env):
            return ScriptedFakeModelClient(
                [ModelResponse(tool_calls=(ToolCall("call-1", "run_tests", {}),))]
            )

        return factory

    def solve_args(self, task: Path, trace_file: Path | None = None) -> list[str]:
        args = ["solve", str(task)]
        if trace_file:
            args.extend(["--trace-file", str(trace_file)])
        return args

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

    def test_accepts_valid_task_and_runs_injected_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_valid_task(root)
            trace_file = root / "trace.jsonl"

            code, stdout, stderr = self.run_cli(
                self.solve_args(task, trace_file),
                env={"OPENAI_API_KEY": "test-key"},
                model_client_factory=self.make_success_model_factory(),
            )
            trace_exists = trace_file.is_file()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Status: success", stdout)
        self.assertIn("Iterations: 1", stdout)
        self.assertIn("Tests: 1/1 passed", stdout)
        self.assertTrue(trace_exists)

    def test_accepts_supported_solve_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_valid_task(root)
            trace_file = root / "custom-trace.jsonl"

            code, stdout, stderr = self.run_cli(
                [
                    "solve",
                    str(task),
                    "--max-iterations",
                    "3",
                    "--timeout-seconds",
                    "1.5",
                    "--trace-file",
                    str(trace_file),
                    "--verbose",
                ],
                env={"OPENAI_API_KEY": "test-key"},
                model_client_factory=self.make_success_model_factory(),
            )
            trace_exists = trace_file.is_file()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Status: success", stdout)
        self.assertTrue(trace_exists)

    def test_openai_client_error_is_reported_without_secret(self):
        def failing_factory(_env):
            raise OpenAIClientError("The openai package is not installed.")

        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))

            code, stdout, stderr = self.run_cli(
                ["solve", str(task)],
                env={"OPENAI_API_KEY": "secret-test-key"},
                model_client_factory=failing_factory,
            )

        self.assertEqual(code, 4)
        self.assertEqual(stdout, "")
        self.assertIn("OpenAI error:", stderr)
        self.assertIn("not installed", stderr)
        self.assertNotIn("secret-test-key", stderr)

    def test_module_entrypoint_reaches_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_valid_task(Path(tmp))
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY", None)
            env["PYTHONPATH"] = str(SRC)

            result = subprocess.run(
                [sys.executable, "-m", "cp_agent", "solve", str(task)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("OPENAI_API_KEY is not set.", result.stderr)


if __name__ == "__main__":
    unittest.main()
