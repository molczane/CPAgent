from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 2
DEFAULT_MAX_STDOUT_CHARS = 10000
DEFAULT_MAX_STDERR_CHARS = 10000


@dataclass(frozen=True)
class TestCase:
    name: str
    input_path: Path
    output_path: Path


def discover_tests(task_dir: str | Path) -> list[TestCase]:
    root = Path(task_dir)
    tests_dir = root / "tests"
    cases: list[TestCase] = []

    for input_path in sorted(tests_dir.glob("*.in")):
        if not input_path.is_file():
            continue
        output_path = input_path.with_suffix(".out")
        if output_path.is_file():
            cases.append(
                TestCase(
                    name=input_path.stem,
                    input_path=input_path,
                    output_path=output_path,
                )
            )

    return cases


def run_tests(
    task_dir: str | Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_stdout_chars: int = DEFAULT_MAX_STDOUT_CHARS,
    max_stderr_chars: int = DEFAULT_MAX_STDERR_CHARS,
    python_executable: str | None = None,
) -> dict[str, Any]:
    root = Path(task_dir)
    cases = discover_tests(root)
    results = [
        run_test_case(
            root,
            case,
            timeout_seconds=timeout_seconds,
            max_stdout_chars=max_stdout_chars,
            max_stderr_chars=max_stderr_chars,
            python_executable=python_executable,
        )
        for case in cases
    ]
    passed = sum(1 for result in results if result["passed"])
    total = len(results)

    return {
        "ok": True,
        "all_passed": total > 0 and passed == total,
        "summary": f"{passed}/{total} tests passed",
        "results": results,
    }


def run_test_case(
    task_root: Path,
    case: TestCase,
    *,
    timeout_seconds: float,
    max_stdout_chars: int,
    max_stderr_chars: int,
    python_executable: str | None,
) -> dict[str, Any]:
    input_text = case.input_path.read_text(encoding="utf-8")
    expected_text = case.output_path.read_text(encoding="utf-8")
    executable = python_executable or sys.executable

    started = time.monotonic()
    try:
        completed = subprocess.run(
            [executable, "solution.py"],
            cwd=task_root,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        runtime_ms = elapsed_ms(started)
        return {
            "name": case.name,
            "passed": False,
            "exit_code": None,
            "runtime_ms": runtime_ms,
            "error": "timeout",
            "stdout": limit_text(to_text(exc.stdout), max_stdout_chars),
            "stderr": limit_text(to_text(exc.stderr), max_stderr_chars),
        }

    runtime_ms = elapsed_ms(started)
    actual = normalize_output(limit_text(completed.stdout, max_stdout_chars))
    expected = normalize_output(expected_text)
    stderr = limit_text(completed.stderr, max_stderr_chars)
    passed = completed.returncode == 0 and actual == expected

    return {
        "name": case.name,
        "passed": passed,
        "exit_code": completed.returncode,
        "runtime_ms": runtime_ms,
        "expected": expected,
        "actual": actual,
        "stderr": stderr,
    }


def normalize_output(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(line.rstrip() for line in lines)


def limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n...[truncated]"
    if max_chars <= len(suffix):
        return suffix[:max_chars]
    return text[: max_chars - len(suffix)] + suffix


def elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
