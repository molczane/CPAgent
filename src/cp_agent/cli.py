from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TextIO

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
    solve.add_argument("task_dir", help="Path to the task directory.")
    solve.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum agent loop iterations. Default: {DEFAULT_MAX_ITERATIONS}.",
    )
    solve.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-test timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}.",
    )
    solve.add_argument(
        "--trace-file",
        default=DEFAULT_TRACE_FILE,
        help=f"JSONL trace output path. Default: {DEFAULT_TRACE_FILE}.",
    )
    solve.add_argument(
        "--verbose",
        action="store_true",
        help="Print human-readable progress while the agent runs.",
    )

    return parser


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
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    env = os.environ if environ is None else environ
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr

    if args.command == "solve":
        return solve(args, env, out, err)

    parser.error(f"Unknown command: {args.command}")
    return 2


def solve(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if not environ.get("OPENAI_API_KEY"):
        print(MISSING_API_KEY_MESSAGE, file=stderr, end="")
        return 1

    try:
        task_info = validate_task_dir(args.task_dir)
    except TaskValidationError as exc:
        print(f"Task validation failed: {exc}", file=stderr)
        return 2

    print(f"Task validation passed: {task_info.root}", file=stdout)
    print(f"Tests discovered: {len(task_info.test_names)}", file=stdout)
    print("Agent loop is not implemented yet.", file=stdout)
    return 0
