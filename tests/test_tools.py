from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent.tools import TOOL_DEFINITIONS, ToolContext, dispatch_tool
from cp_agent.workspace import Workspace


class ToolsTests(unittest.TestCase):
    def make_task(self, root: Path) -> Path:
        task = root / "task"
        task.mkdir()
        (task / "statement.md").write_text("Echo input.\n", encoding="utf-8")
        (task / "solution.py").write_text("print('wrong')\n", encoding="utf-8")
        tests = task / "tests"
        tests.mkdir()
        (tests / "sample1.in").write_text("42\n", encoding="utf-8")
        (tests / "sample1.out").write_text("42\n", encoding="utf-8")
        return task

    def make_context(self, task: Path) -> ToolContext:
        return ToolContext(workspace=Workspace(task), python_executable=sys.executable)

    def test_tool_definitions_expose_exact_v0_tools_with_strict_schemas(self):
        self.assertEqual(
            [definition["name"] for definition in TOOL_DEFINITIONS],
            ["list_files", "read_file", "write_solution", "run_tests"],
        )
        for definition in TOOL_DEFINITIONS:
            self.assertEqual(definition["type"], "function")
            self.assertTrue(definition["description"])
            self.assertTrue(definition["strict"])
            parameters = definition["parameters"]
            self.assertEqual(parameters["type"], "object")
            self.assertIn("required", parameters)
            self.assertFalse(parameters["additionalProperties"])

    def test_list_files_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            context = self.make_context(task)

            result = dispatch_tool("list_files", {}, context)

        self.assertEqual(
            result,
            {
                "files": [
                    "solution.py",
                    "statement.md",
                    "tests/sample1.in",
                    "tests/sample1.out",
                ]
            },
        )

    def test_read_file_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            context = self.make_context(task)

            result = dispatch_tool("read_file", {"path": "statement.md"}, context)

        self.assertEqual(
            result,
            {"ok": True, "path": "statement.md", "content": "Echo input.\n"},
        )

    def test_write_solution_tool_replaces_only_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            context = self.make_context(task)
            outside = Path(tmp) / "outside.py"
            outside.write_text("outside\n", encoding="utf-8")

            result = dispatch_tool(
                "write_solution",
                {
                    "content": (
                        "import sys\n"
                        "print(sys.stdin.read().strip())\n"
                    )
                },
                context,
            )

            solution = (task / "solution.py").read_text(encoding="utf-8")
            backup = (task / ".solution.py.bak").read_text(encoding="utf-8")
            outside_content = outside.read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(result["path"], "solution.py")
        self.assertEqual(solution, "import sys\nprint(sys.stdin.read().strip())\n")
        self.assertEqual(backup, "print('wrong')\n")
        self.assertEqual(outside_content, "outside\n")

    def test_run_tests_tool_wraps_local_test_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            (task / "solution.py").write_text(
                "import sys\nprint(sys.stdin.read().strip())\n",
                encoding="utf-8",
            )
            context = self.make_context(task)

            result = dispatch_tool("run_tests", {}, context)

        self.assertTrue(result["ok"])
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["summary"], "1/1 tests passed")
        json.dumps(result)

    def test_dispatch_rejects_unknown_tool_and_invalid_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = self.make_task(Path(tmp))
            context = self.make_context(task)

            results = [
                dispatch_tool("shell", {}, context),
                dispatch_tool("list_files", {"path": "."}, context),
                dispatch_tool("read_file", {}, context),
                dispatch_tool("read_file", {"path": "statement.md", "extra": True}, context),
                dispatch_tool("write_solution", {"content": 123}, context),
                dispatch_tool("run_tests", {"path": "solution.py"}, context),
                dispatch_tool("run_tests", [], context),  # type: ignore[arg-type]
            ]

        self.assertTrue(all(result["ok"] is False for result in results))

    def test_read_file_tool_blocks_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_task(root)
            outside = root / "secret.txt"
            outside.write_text("secret\n", encoding="utf-8")
            context = self.make_context(task)

            result = dispatch_tool("read_file", {"path": "../secret.txt"}, context)

        self.assertEqual(
            result,
            {"ok": False, "error": "File not found or not allowed"},
        )

    def test_write_solution_tool_rejects_extra_path_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.make_task(root)
            outside = root / "outside.py"
            outside.write_text("outside\n", encoding="utf-8")
            context = self.make_context(task)

            result = dispatch_tool(
                "write_solution",
                {"path": str(outside), "content": "print('new')\n"},
                context,
            )

            outside_content = outside.read_text(encoding="utf-8")
            solution_content = (task / "solution.py").read_text(encoding="utf-8")

        self.assertFalse(result["ok"])
        self.assertEqual(outside_content, "outside\n")
        self.assertEqual(solution_content, "print('wrong')\n")


if __name__ == "__main__":
    unittest.main()
