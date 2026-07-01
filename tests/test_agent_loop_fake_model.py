from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent.agent import Agent, AgentConfig, ModelResponse, ToolCall
from cp_agent.fake_model import ScriptedFakeModelClient


class AgentLoopFakeModelTests(unittest.TestCase):
    def make_task(self, root: Path) -> Path:
        task = root / "task"
        task.mkdir()
        (task / "statement.md").write_text(
            "Read one integer and print it.\n",
            encoding="utf-8",
        )
        (task / "solution.py").write_text("print('wrong')\n", encoding="utf-8")
        tests = task / "tests"
        tests.mkdir()
        (tests / "sample1.in").write_text("42\n", encoding="utf-8")
        (tests / "sample1.out").write_text("42\n", encoding="utf-8")
        return task

    def test_fake_model_loop_repairs_task_without_openai(self):
        corrected_solution = "import sys\nprint(sys.stdin.read().strip())\n"
        fake_model = ScriptedFakeModelClient(
            [
                ModelResponse(
                    tool_calls=(
                        ToolCall("call-1", "read_file", {"path": "statement.md"}),
                    )
                ),
                ModelResponse(
                    tool_calls=(
                        ToolCall("call-2", "read_file", {"path": "solution.py"}),
                    )
                ),
                ModelResponse(
                    tool_calls=(ToolCall("call-3", "run_tests", {}),)
                ),
                ModelResponse(
                    tool_calls=(
                        ToolCall(
                            "call-4",
                            "write_solution",
                            {"content": corrected_solution},
                        ),
                    )
                ),
                ModelResponse(
                    tool_calls=(ToolCall("call-5", "run_tests", {}),)
                ),
                ModelResponse(final_text="All tests pass."),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            agent = Agent(
                task,
                fake_model,
                config=AgentConfig(
                    max_iterations=6,
                    python_executable=sys.executable,
                ),
            )

            result = agent.run()

            solution = (task / "solution.py").read_text(encoding="utf-8")
            backup = (task / ".solution.py.bak").read_text(encoding="utf-8")

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.reason)
        self.assertEqual(result.iterations, 5)
        self.assertTrue(result.modified)
        self.assertEqual(result.tests_passed, 1)
        self.assertEqual(result.tests_total, 1)
        self.assertEqual(solution, corrected_solution)
        self.assertEqual(backup, "print('wrong')\n")
        self.assertEqual(len(fake_model.requests), 5)
        self.assertEqual([event["tool"] for event in result.tool_results], [
            "read_file",
            "read_file",
            "run_tests",
            "write_solution",
            "run_tests",
        ])

        tool_messages = [
            message for message in result.messages if message["role"] == "tool"
        ]
        self.assertEqual(len(tool_messages), 5)
        self.assertTrue(json.loads(tool_messages[-1]["content"])["all_passed"])

    def test_agent_stops_with_failure_when_max_iterations_reached(self):
        fake_model = ScriptedFakeModelClient(
            [
                ModelResponse(
                    tool_calls=(ToolCall("call-1", "read_file", {"path": "statement.md"}),)
                ),
                ModelResponse(
                    tool_calls=(ToolCall("call-2", "read_file", {"path": "solution.py"}),)
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            agent = Agent(
                task,
                fake_model,
                config=AgentConfig(max_iterations=2, python_executable=sys.executable),
            )

            result = agent.run()

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "max iterations reached")
        self.assertEqual(result.iterations, 2)
        self.assertEqual(result.tests_passed, 0)
        self.assertEqual(result.tests_total, 0)
        self.assertEqual(len(fake_model.requests), 2)

    def test_agent_appends_structured_errors_for_invalid_tool_calls(self):
        fake_model = ScriptedFakeModelClient(
            [
                ModelResponse(
                    tool_calls=(
                        ToolCall("call-1", "shell", {"cmd": "echo nope"}),
                        ToolCall("call-2", "read_file", {}),
                    )
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            agent = Agent(
                task,
                fake_model,
                config=AgentConfig(max_iterations=1, python_executable=sys.executable),
            )

            result = agent.run()

            solution = (task / "solution.py").read_text(encoding="utf-8")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "max iterations reached")
        self.assertEqual(solution, "print('wrong')\n")
        self.assertEqual(len(result.tool_results), 2)
        self.assertTrue(all(
            event["result"]["ok"] is False for event in result.tool_results
        ))
        self.assertIn("Unknown tool", result.tool_results[0]["result"]["error"])
        self.assertIn("requires", result.tool_results[1]["result"]["error"])

    def test_agent_stops_when_model_returns_final_answer_without_tools(self):
        fake_model = ScriptedFakeModelClient(
            [ModelResponse(final_text="I am done.")]
        )

        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            agent = Agent(
                task,
                fake_model,
                config=AgentConfig(max_iterations=5, python_executable=sys.executable),
            )

            result = agent.run()

        self.assertEqual(result.status, "failed")
        self.assertEqual(
            result.reason,
            "model returned final answer before tests passed",
        )
        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.final_answer, "I am done.")
        self.assertEqual(result.tool_results, [])


if __name__ == "__main__":
    unittest.main()
