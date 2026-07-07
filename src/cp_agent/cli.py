from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, TextIO

from .agent import Agent, AgentConfig, AgentResult, ModelClient
from .openai_client import OpenAIClientError, OpenAIModelClient
from .prompts import AgentMode

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_TIMEOUT_SECONDS = 2
DEFAULT_TRACE_FILE = "trace.jsonl"

MISSING_API_KEY_MESSAGE = """OPENAI_API_KEY is not set.
Set it with:
export OPENAI_API_KEY="..."
"""


class TaskValidationError(ValueError):
    """Raised when a task directory does not match the v0 task shape."""


@dataclass(frozen=True)
class TaskInfo:
    root: Path
    test_names: tuple[str, ...]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cp_agent",
        description="Minimal coding agent for competitive programming tasks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    solve = subparsers.add_parser(
        "solve",
        help="Validate and solve a competitive-programming task directory.",
    )
    add_agent_arguments(solve)

    advise = subparsers.add_parser(
        "advise",
        help="Validate a task directory and print a guided solving hint.",
    )
    add_agent_arguments(advise)

    return parser


def add_agent_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("task_dir", help="Path to the task directory.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum agent loop iterations. Default: {DEFAULT_MAX_ITERATIONS}.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-test timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--trace-file",
        default=DEFAULT_TRACE_FILE,
        help=f"JSONL trace output path. Default: {DEFAULT_TRACE_FILE}.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print human-readable progress while the agent runs.",
    )


def validate_task_dir(task_dir: str | Path) -> TaskInfo:
    root = Path(task_dir)

    if not root.exists():
        raise TaskValidationError(f"Task directory does not exist: {root}")
    if not root.is_dir():
        raise TaskValidationError(f"Task path is not a directory: {root}")

    statement = root / "statement.md"
    if not statement.is_file():
        raise TaskValidationError("Missing required file: statement.md")

    solution = root / "solution.py"
    if not solution.is_file():
        raise TaskValidationError("Missing required file: solution.py")

    tests_dir = root / "tests"
    if not tests_dir.exists():
        raise TaskValidationError("Missing required directory: tests/")
    if not tests_dir.is_dir():
        raise TaskValidationError("Required path is not a directory: tests/")

    test_names = find_test_pairs(tests_dir)
    if not test_names:
        raise TaskValidationError(
            "tests/ must contain at least one matching .in / .out pair"
        )

    return TaskInfo(root=root, test_names=test_names)


def find_test_pairs(tests_dir: Path) -> tuple[str, ...]:
    names: list[str] = []
    for input_path in sorted(tests_dir.glob("*.in")):
        if not input_path.is_file():
            continue
        output_path = input_path.with_suffix(".out")
        if output_path.is_file():
            names.append(input_path.stem)
    return tuple(names)


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    model_client_factory: Callable[[Mapping[str, str]], ModelClient] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    env = os.environ if environ is None else environ
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr

    if args.command == "solve":
        return solve(args, env, out, err, model_client_factory)
    if args.command == "advise":
        return advise(args, env, out, err, model_client_factory)

    parser.error(f"Unknown command: {args.command}")
    return 2


def solve(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
    model_client_factory: Callable[[Mapping[str, str]], ModelClient] | None = None,
) -> int:
    return run_agent_command(
        args,
        environ,
        stdout,
        stderr,
        mode="solve",
        model_client_factory=model_client_factory,
    )


def advise(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
    model_client_factory: Callable[[Mapping[str, str]], ModelClient] | None = None,
) -> int:
    return run_agent_command(
        args,
        environ,
        stdout,
        stderr,
        mode="advise",
        model_client_factory=model_client_factory,
    )


def run_agent_command(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
    *,
    mode: AgentMode,
    model_client_factory: Callable[[Mapping[str, str]], ModelClient] | None = None,
) -> int:
    if not environ.get("OPENAI_API_KEY"):
        print(MISSING_API_KEY_MESSAGE, file=stderr, end="")
        return 1

    try:
        task_info = validate_task_dir(args.task_dir)
    except TaskValidationError as exc:
        print(f"Task validation failed: {exc}", file=stderr)
        return 2

    create_model_client = model_client_factory or OpenAIModelClient.from_environ
    try:
        model_client = create_model_client(environ)
        result = Agent(
            task_info.root,
            model_client,
            config=AgentConfig(
                mode=mode,
                max_iterations=args.max_iterations,
                timeout_seconds=args.timeout_seconds,
                trace_file=args.trace_file,
                verbose=args.verbose,
                progress_stream=stdout if args.verbose else None,
            ),
        ).run()
    except OpenAIClientError as exc:
        print(f"OpenAI error: {exc}", file=stderr)
        return 4

    print_agent_result(result, stdout, mode=mode)
    return 0 if result.status == "success" else 3


def print_agent_result(
    result: AgentResult,
    stdout: TextIO,
    *,
    mode: AgentMode = "solve",
) -> None:
    if mode == "advise" and result.final_answer:
        print("Advice:", file=stdout)
        print(result.final_answer.strip(), file=stdout)
        print(file=stdout)
    print(f"Status: {result.status}", file=stdout)
    if result.reason:
        print(f"Reason: {result.reason}", file=stdout)
    print(f"Iterations: {result.iterations}", file=stdout)
    print(f"Tests: {result.tests_passed}/{result.tests_total} passed", file=stdout)
    if mode == "solve" and result.modified:
        print("Modified: solution.py", file=stdout)
