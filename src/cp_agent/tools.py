from __future__ import annotations

"""Tools and tool execution for the competitive programming agent.

Teaching mental model:
In AI agents, tools have two sides:
1. Schema (what the LLM sees):
   A JSON Schema description that defines the tool's name, purpose, and
   expected arguments. The LLM reads this schema to decide when and how
   to call the tool.
2. Dispatcher (what Python executes):
   The local Python function that actually runs the action (reading files,
   executing tests, modifying code) and returns structured observations
   back to the agent loop.

Why tools require a 'reason' parameter:
Every tool schema includes a mandatory `reason` argument (`PUBLIC_REASON_ARG`).
Forcing the model to explain why it is invoking a tool before execution:
- Encourages the model to plan its next action,
- Provides human-readable progress messages in the CLI and trace logs,
- Avoids ungrounded, blind tool calls.
"""

import sys
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from . import test_runner
from .workspace import DEFAULT_MAX_FILE_READ_CHARS, Workspace

DEFAULT_MAX_TOOL_OUTPUT_CHARS = 30000
PUBLIC_REASON_ARG = "reason"

PUBLIC_REASON_PROPERTY: dict[str, str] = {
    "type": "string",
    "description": (
        "One short public sentence explaining why this tool is useful now. "
        "Do not include hidden chain-of-thought."
    ),
}


@dataclass(frozen=True)
class ToolContext:
    workspace: Workspace
    timeout_seconds: float = test_runner.DEFAULT_TIMEOUT_SECONDS
    max_file_read_chars: int = DEFAULT_MAX_FILE_READ_CHARS
    max_stdout_chars: int = test_runner.DEFAULT_MAX_STDOUT_CHARS
    max_stderr_chars: int = test_runner.DEFAULT_MAX_STDERR_CHARS
    python_executable: str = sys.executable


# =============================================================================
# 1. Tool Schemas (What the Model Sees)
# =============================================================================

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List readable files inside the task workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                PUBLIC_REASON_ARG: PUBLIC_REASON_PROPERTY,
            },
            "required": [PUBLIC_REASON_ARG],
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
                },
                PUBLIC_REASON_ARG: PUBLIC_REASON_PROPERTY,
            },
            "required": ["path", PUBLIC_REASON_ARG],
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
                },
                PUBLIC_REASON_ARG: PUBLIC_REASON_PROPERTY,
            },
            "required": ["content", PUBLIC_REASON_ARG],
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
            "properties": {
                PUBLIC_REASON_ARG: PUBLIC_REASON_PROPERTY,
            },
            "required": [PUBLIC_REASON_ARG],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


SOLVE_TOOL_NAMES = ("list_files", "read_file", "write_solution", "run_tests")
ADVISE_TOOL_NAMES = ("list_files", "read_file", "run_tests")


def get_tool_definitions(
    tool_names: tuple[str, ...] = SOLVE_TOOL_NAMES,
) -> list[dict[str, Any]]:
    """Return a deep copy of tool schemas filtered by the allowed tool names."""
    allowed = set(tool_names)
    return [
        deepcopy(definition)
        for definition in TOOL_DEFINITIONS
        if definition["name"] in allowed
    ]


# =============================================================================
# 2. Tool Dispatcher (Routing Model Calls to Python Functions)
# =============================================================================


def dispatch_tool(
    name: str,
    args: dict[str, Any],
    context: ToolContext,
) -> dict[str, Any]:
    """Validate tool call arguments and dispatch to the matching local handler."""
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
    if PUBLIC_REASON_ARG in args and not isinstance(args[PUBLIC_REASON_ARG], str):
        return {"ok": False, "error": "Tool reason must be a string"}
    return handler(strip_public_reason(args), context)


def strip_public_reason(args: dict[str, Any]) -> dict[str, Any]:
    """Remove the model's public 'reason' argument before calling the handler."""
    return {key: value for key, value in args.items() if key != PUBLIC_REASON_ARG}


# =============================================================================
# 3. Local Tool Implementations (Executing Safe Actions in Workspace)
# =============================================================================


def _list_files(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """List readable task files inside the workspace."""
    if args:
        return {"ok": False, "error": "list_files does not accept arguments"}
    return {"files": context.workspace.list_files()}


def _read_file(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Read a permitted workspace file up to the character limit."""
    if set(args) != {"path"} or not isinstance(args.get("path"), str):
        return {"ok": False, "error": "read_file requires string argument: path"}
    return context.workspace.read_file(
        args["path"],
        max_chars=context.max_file_read_chars,
    )


def _write_solution(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Atomically write new content to solution.py with automatic backup."""
    if set(args) != {"content"} or not isinstance(args.get("content"), str):
        return {
            "ok": False,
            "error": "write_solution requires string argument: content",
        }
    return context.workspace.write_solution(args["content"])


def _run_tests(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Execute solution.py against input/output test fixtures and return results."""
    if args:
        return {"ok": False, "error": "run_tests does not accept arguments"}
    return test_runner.run_tests(
        context.workspace.root,
        timeout_seconds=context.timeout_seconds,
        max_stdout_chars=context.max_stdout_chars,
        max_stderr_chars=context.max_stderr_chars,
        python_executable=context.python_executable,
    )
