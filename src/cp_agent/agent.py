from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from . import test_runner
from .prompts import SYSTEM_PROMPT, initial_user_message
from .tools import (
    DEFAULT_MAX_TOOL_OUTPUT_CHARS,
    ToolContext,
    dispatch_tool,
    get_tool_definitions,
)
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
    max_iterations: int = 5
    timeout_seconds: float = test_runner.DEFAULT_TIMEOUT_SECONDS
    max_file_read_chars: int = DEFAULT_MAX_FILE_READ_CHARS
    max_stdout_chars: int = test_runner.DEFAULT_MAX_STDOUT_CHARS
    max_stderr_chars: int = test_runner.DEFAULT_MAX_STDERR_CHARS
    max_tool_output_chars: int = DEFAULT_MAX_TOOL_OUTPUT_CHARS
    python_executable: str | None = None


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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": initial_user_message(self.task_dir)},
        ]
        tool_definitions = get_tool_definitions()
        tool_results: list[dict[str, Any]] = []
        last_test_result: dict[str, Any] | None = None
        modified = False

        for iteration in range(1, self.config.max_iterations + 1):
            model_response = self.model_client.complete(messages, tool_definitions)
            messages.append(model_message(model_response))

            if not model_response.tool_calls:
                status, reason = status_for_final_answer(last_test_result)
                passed, total = test_counts(last_test_result)
                return AgentResult(
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

            for tool_call in model_response.tool_calls:
                result = dispatch_tool(tool_call.name, tool_call.args, self.tool_context)
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
                    if result.get("all_passed"):
                        passed, total = test_counts(last_test_result)
                        return AgentResult(
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

        passed, total = test_counts(last_test_result)
        return AgentResult(
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


def status_for_final_answer(
    last_test_result: dict[str, Any] | None,
) -> tuple[str, str | None]:
    if last_test_result and last_test_result.get("all_passed"):
        return "success", None
    return "failed", "model returned final answer before tests passed"


def test_counts(last_test_result: dict[str, Any] | None) -> tuple[int, int]:
    if not last_test_result:
        return 0, 0
    results = last_test_result.get("results", [])
    passed = sum(1 for result in results if result.get("passed"))
    return passed, len(results)
