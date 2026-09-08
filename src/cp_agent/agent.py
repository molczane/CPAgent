from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TextIO

from . import test_runner
from .prompts import AgentMode, initial_user_message, system_prompt
from .tools import (
    ADVISE_TOOL_NAMES,
    DEFAULT_MAX_TOOL_OUTPUT_CHARS,
    PUBLIC_REASON_ARG,
    SOLVE_TOOL_NAMES,
    ToolContext,
    dispatch_tool,
    get_tool_definitions,
)
from .trace import TraceWriter, summarize_tool_result, test_summary
from .workspace import DEFAULT_MAX_FILE_READ_CHARS, Workspace


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    response_items: tuple[dict[str, Any], ...] = ()


class ModelClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        """Return either a final answer or one or more requested tool calls."""


@dataclass(frozen=True)
class AgentConfig:
    mode: AgentMode = "solve"
    max_iterations: int = 5
    timeout_seconds: float = test_runner.DEFAULT_TIMEOUT_SECONDS
    max_file_read_chars: int = DEFAULT_MAX_FILE_READ_CHARS
    max_stdout_chars: int = test_runner.DEFAULT_MAX_STDOUT_CHARS
    max_stderr_chars: int = test_runner.DEFAULT_MAX_STDERR_CHARS
    max_tool_output_chars: int = DEFAULT_MAX_TOOL_OUTPUT_CHARS
    python_executable: str | None = None
    trace_file: str | Path | None = None
    verbose: bool = False
    progress_stream: TextIO | None = None


@dataclass
class AgentResult:
    status: str
    iterations: int
    reason: str | None = None
    final_answer: str | None = None
    tests_passed: int = 0
    tests_total: int = 0
    modified: bool = False
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    last_test_result: dict[str, Any] | None = None


class Agent:
    def __init__(
        self,
        task_dir: str | Path,
        model_client: ModelClient,
        *,
        config: AgentConfig | None = None,
    ):
        self.task_dir = Path(task_dir)
        self.model_client = model_client
        self.config = config or AgentConfig()
        self.trace = TraceWriter(self.config.trace_file) if self.config.trace_file else None
        self.workspace = Workspace(self.task_dir)
        self.tool_context = ToolContext(
            workspace=self.workspace,
            timeout_seconds=self.config.timeout_seconds,
            max_file_read_chars=self.config.max_file_read_chars,
            max_stdout_chars=self.config.max_stdout_chars,
            max_stderr_chars=self.config.max_stderr_chars,
            python_executable=self.config.python_executable or sys.executable,
        )

    def run(self) -> AgentResult:
        messages = [
            {"role": "system", "content": system_prompt(self.config.mode)},
            {
                "role": "user",
                "content": initial_user_message(self.task_dir, self.config.mode),
            },
        ]
        tool_definitions = get_tool_definitions(tool_names_for_mode(self.config.mode))
        tool_results: list[dict[str, Any]] = []
        last_test_result: dict[str, Any] | None = None
        modified = False

        for iteration in range(1, self.config.max_iterations + 1):
            self.write_trace({"type": "model_request", "iteration": iteration})
            model_response = self.model_client.complete(messages, tool_definitions)
            # region Logging
            self.write_trace(
                {
                    "type": "model_response",
                    "iteration": iteration,
                    "tool_calls": [call.name for call in model_response.tool_calls],
                    "final": not bool(model_response.tool_calls),
                }
            )
            # endregion
            messages.append(model_message(model_response))

            if not model_response.tool_calls:
                status, reason = status_for_final_answer(
                    last_test_result,
                    mode=self.config.mode,
                    final_text=model_response.final_text,
                )
                passed, total = test_counts(last_test_result)
                # region Agent Result
                result = AgentResult(
                    status=status,
                    reason=reason,
                    iterations=iteration,
                    final_answer=model_response.final_text,
                    tests_passed=passed,
                    tests_total=total,
                    modified=modified,
                    messages=messages,
                    tool_results=tool_results,
                    last_test_result=last_test_result,
                )
                # endregion
                self.write_final_trace(result)
                return result

            for tool_call in model_response.tool_calls:
                self.write_progress(
                    iteration,
                    tool_progress_message(tool_call, modified=modified),
                )
                # region Logging
                self.write_trace(
                    {
                        "type": "tool_call",
                        "iteration": iteration,
                        "tool_call_id": tool_call.id,
                        "tool": tool_call.name,
                        "args": tool_call.args,
                    }
                )
                # endregion
                result = self.dispatch_tool_call(tool_call)
                # region Logging
                self.write_trace(
                    {
                        "type": "tool_result",
                        "iteration": iteration,
                        "tool_call_id": tool_call.id,
                        "tool": tool_call.name,
                        "result": summarize_tool_result(result),
                    }
                )
                # endregion
                tool_event = {
                    "iteration": iteration,
                    "tool_call_id": tool_call.id,
                    "tool": tool_call.name,
                    "args": tool_call.args,
                    "result": result,
                }
                tool_results.append(tool_event)
                messages.append(tool_result_message(tool_call, result, self.config))

                if tool_call.name == "write_solution" and result.get("ok"):
                    modified = True
                if tool_call.name == "run_tests" and result.get("ok"):
                    last_test_result = result
                    progress_passed, progress_total = test_counts(result)
                    # region Logging
                    self.write_progress(
                        iteration,
                        f"Tests: {progress_passed}/{progress_total} passed",
                    )
                    self.write_trace(
                        {
                            "type": "test_summary",
                            "iteration": iteration,
                            **test_summary(result),
                        }
                    )
                    # endregion
                    if self.config.mode == "solve" and result.get("all_passed"):
                        passed, total = test_counts(last_test_result)
                        agent_result = AgentResult(
                            status="success",
                            reason=None,
                            iterations=iteration,
                            final_answer=None,
                            tests_passed=passed,
                            tests_total=total,
                            modified=modified,
                            messages=messages,
                            tool_results=tool_results,
                            last_test_result=last_test_result,
                        )
                        self.write_final_trace(agent_result)
                        return agent_result

        passed, total = test_counts(last_test_result)
        result = AgentResult(
            status="failed",
            reason="max iterations reached",
            iterations=self.config.max_iterations,
            final_answer=None,
            tests_passed=passed,
            tests_total=total,
            modified=modified,
            messages=messages,
            tool_results=tool_results,
            last_test_result=last_test_result,
        )
        self.write_final_trace(result)
        return result

    def dispatch_tool_call(self, tool_call: ToolCall) -> dict[str, Any]:
        if (
            self.config.mode == "advise"
            and tool_call.name not in tool_names_for_mode(self.config.mode)
        ):
            return {
                "ok": False,
                "error": (
                    f"Tool not allowed in {self.config.mode} mode: "
                    f"{tool_call.name}"
                ),
            }
        return dispatch_tool(tool_call.name, tool_call.args, self.tool_context)

    def write_trace(self, event: dict[str, Any]) -> None:
        if self.trace:
            self.trace.write(event)

    def write_progress(self, iteration: int, message: str) -> None:
        if not self.config.verbose:
            return
        stream = self.config.progress_stream or sys.stdout
        print(f"[{iteration}] {message}", file=stream, flush=True)

    def write_final_trace(self, result: AgentResult) -> None:
        event: dict[str, Any] = {
            "type": "final",
            "status": result.status,
            "iterations": result.iterations,
            "tests_passed": result.tests_passed,
            "tests_total": result.tests_total,
            "modified": result.modified,
        }
        if result.reason:
            event["reason"] = result.reason
        self.write_trace(event)


def tool_progress_message(tool_call: ToolCall, *, modified: bool) -> str:
    return (
        f"I am using {tool_call_display(tool_call)} because "
        f"{tool_call_reason(tool_call, modified=modified)}."
    )


def tool_call_display(tool_call: ToolCall) -> str:
    if tool_call.name in {"list_files", "run_tests"}:
        return f"{tool_call.name}()"
    if tool_call.name == "read_file":
        path = tool_call.args.get("path")
        if isinstance(path, str) and path:
            return f"read_file({compact_display_value(path)})"
        return "read_file"
    if tool_call.name == "write_solution":
        return "write_solution"
    return compact_display_value(tool_call.name)


def tool_call_reason(tool_call: ToolCall, *, modified: bool) -> str:
    public_reason = public_tool_reason(tool_call)
    if public_reason:
        return public_reason

    if tool_call.name == "list_files":
        return "I need to see which task files are available"
    if tool_call.name == "read_file":
        path = tool_call.args.get("path")
        if path == "statement.md":
            return "I need to understand the task statement"
        if path == "solution.py":
            return "I need to inspect the current solution"
        if isinstance(path, str) and path.startswith("tests/"):
            return "I need to inspect the sample tests"
        return "I need to inspect a permitted workspace file"
    if tool_call.name == "write_solution":
        return "I have a candidate fix for solution.py"
    if tool_call.name == "run_tests":
        if modified:
            return "I need to verify the updated solution"
        return "test feedback tells me what is failing"
    return "this is the next requested local action"


def public_tool_reason(tool_call: ToolCall) -> str | None:
    reason = tool_call.args.get(PUBLIC_REASON_ARG)
    if not isinstance(reason, str):
        return None

    text = " ".join(reason.split()).strip()
    if not text:
        return None

    return compact_display_value(text.rstrip(".?!"), max_chars=180)


def compact_display_value(value: str, max_chars: int = 80) -> str:
    text = value.replace("\n", "\\n").replace("\r", "\\r")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def model_message(model_response: ModelResponse) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": model_response.final_text or "",
        "response_items": list(model_response.response_items),
        "tool_calls": [
            {
                "id": tool_call.id,
                "name": tool_call.name,
                "args": tool_call.args,
            }
            for tool_call in model_response.tool_calls
        ],
    }


def tool_result_message(
    tool_call: ToolCall,
    result: dict[str, Any],
    config: AgentConfig,
) -> dict[str, Any]:
    content = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if len(content) > config.max_tool_output_chars:
        content = content[: config.max_tool_output_chars] + "\n...[truncated]"
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.name,
        "content": content,
    }


def tool_names_for_mode(mode: AgentMode) -> tuple[str, ...]:
    if mode == "advise":
        return ADVISE_TOOL_NAMES
    return SOLVE_TOOL_NAMES


def status_for_final_answer(
    last_test_result: dict[str, Any] | None,
    *,
    mode: AgentMode = "solve",
    final_text: str | None = None,
) -> tuple[str, str | None]:
    if mode == "advise":
        if final_text and final_text.strip():
            return "success", None
        return "failed", "model returned empty advice"
    if last_test_result and last_test_result.get("all_passed"):
        return "success", None
    return "failed", "model returned final answer before tests passed"


def test_counts(last_test_result: dict[str, Any] | None) -> tuple[int, int]:
    if not last_test_result:
        return 0, 0
    results = last_test_result.get("results", [])
    passed = sum(1 for result in results if result.get("passed"))
    return passed, len(results)
