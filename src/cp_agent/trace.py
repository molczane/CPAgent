from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SECRET_KEYS = {
    "api_key",
    "authorization",
    "openai_api_key",
    "token",
}


class TraceWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        sanitized = sanitize(event)
        with self.path.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps(sanitized, ensure_ascii=False, sort_keys=True))
            trace.write("\n")


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if is_secret_key(str(key)):
                result[key] = "[redacted]"
            else:
                result[key] = sanitize(item)
        return result
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return redact_environment_secrets(value)
    return value


def is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SECRET_KEYS or normalized.endswith("_token")


def redact_environment_secrets(text: str) -> str:
    redacted = text
    for key, value in os.environ.items():
        if not value:
            continue
        if is_secret_key(key) or "KEY" in key.upper() or "TOKEN" in key.upper():
            redacted = redacted.replace(value, "[redacted]")
    return redacted


def summarize_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": result.get("ok")}
    if "error" in result:
        summary["error"] = result["error"]
    if "path" in result:
        summary["path"] = result["path"]
    if "bytes_written" in result:
        summary["bytes_written"] = result["bytes_written"]
    if "all_passed" in result:
        summary["all_passed"] = result["all_passed"]
    if "summary" in result:
        summary["summary"] = result["summary"]
    if "files" in result:
        summary["files"] = result["files"]
    return summary


def test_summary(result: dict[str, Any]) -> dict[str, Any]:
    results = result.get("results", [])
    passed = sum(1 for item in results if item.get("passed"))
    return {
        "passed": passed,
        "total": len(results),
        "summary": result.get("summary"),
        "all_passed": result.get("all_passed"),
    }
