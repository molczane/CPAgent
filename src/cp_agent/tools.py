from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable

from . import test_runner
from .workspace import DEFAULT_MAX_FILE_READ_CHARS, Workspace

DEFAULT_MAX_TOOL_OUTPUT_CHARS = 30000


@dataclass(frozen=True)
class ToolContext:
    workspace: Workspace
    timeout_seconds: float = test_runner.DEFAULT_TIMEOUT_SECONDS
    max_file_read_chars: int = DEFAULT_MAX_FILE_READ_CHARS
    max_stdout_chars: int = test_runner.DEFAULT_MAX_STDOUT_CHARS
    max_stderr_chars: int = test_runner.DEFAULT_MAX_STDERR_CHARS
    python_executable: str = sys.executable


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List readable files inside the task workspace.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a UTF-8 text file allowed in the task workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the task workspace.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "write_solution",
        "description": "Replace solution.py inside the task workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Complete UTF-8 content for solution.py.",
                }
            },
            "required": ["content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "run_tests",
        "description": "Run solution.py against matching tests/*.in and tests/*.out.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    return [definition.copy() for definition in TOOL_DEFINITIONS]


def dispatch_tool(
    name: str,
    args: dict[str, Any],
    context: ToolContext,
) -> dict[str, Any]:
    handlers: dict[str, Callable[[dict[str, Any], ToolContext], dict[str, Any]]] = {
        "list_files": _list_files,
        "read_file": _read_file,
        "write_solution": _write_solution,
        "run_tests": _run_tests,
    }

    handler = handlers.get(name)
    if handler is None:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    if not isinstance(args, dict):
        return {"ok": False, "error": "Tool arguments must be an object"}
    return handler(args, context)


def _list_files(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if args:
        return {"ok": False, "error": "list_files does not accept arguments"}
    return {"files": context.workspace.list_files()}


def _read_file(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if set(args) != {"path"} or not isinstance(args.get("path"), str):
        return {"ok": False, "error": "read_file requires string argument: path"}
    return context.workspace.read_file(
        args["path"],
        max_chars=context.max_file_read_chars,
    )


def _write_solution(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if set(args) != {"content"} or not isinstance(args.get("content"), str):
        return {
            "ok": False,
            "error": "write_solution requires string argument: content",
        }
    return context.workspace.write_solution(args["content"])


def _run_tests(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if args:
        return {"ok": False, "error": "run_tests does not accept arguments"}
    return test_runner.run_tests(
        context.workspace.root,
        timeout_seconds=context.timeout_seconds,
        max_stdout_chars=context.max_stdout_chars,
        max_stderr_chars=context.max_stderr_chars,
        python_executable=context.python_executable,
    )
