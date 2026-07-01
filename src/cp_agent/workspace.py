from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_MAX_FILE_READ_CHARS = 20000

READ_ERROR = "File not found or not allowed"
WRITE_ERROR = "solution.py is not writable or not allowed"


class Workspace:
    def __init__(self, task_dir: str | Path):
        self.root = Path(task_dir).resolve()

    def list_files(self) -> list[str]:
        files: list[str] = []
        if not self.root.is_dir():
            return files

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            try:
                resolved = path.resolve(strict=True)
                self._ensure_inside(resolved)
                relative = path.relative_to(self.root).as_posix()
            except (OSError, ValueError):
                continue
            if self._is_allowed_read_path(relative):
                files.append(relative)

        return sorted(files)

    def read_file(
        self,
        requested_path: str,
        *,
        max_chars: int = DEFAULT_MAX_FILE_READ_CHARS,
    ) -> dict[str, Any]:
        try:
            path = self._resolve_read_path(requested_path)
            content = path.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError):
            return {"ok": False, "error": READ_ERROR}

        relative = path.relative_to(self.root).as_posix()
        if len(content) <= max_chars:
            return {"ok": True, "path": relative, "content": content}

        return {
            "ok": True,
            "path": relative,
            "content": content[:max_chars],
            "truncated": True,
            "warning": f"File was truncated to {max_chars} characters.",
        }

    def write_solution(self, content: str) -> dict[str, Any]:
        solution_path = self.root / "solution.py"
        backup_path = self.root / ".solution.py.bak"

        try:
            self._ensure_safe_write_target(solution_path)
            self._ensure_safe_backup_target(backup_path)
            previous_content = solution_path.read_text(encoding="utf-8")
            backup_path.write_text(previous_content, encoding="utf-8")
            solution_path.write_text(content, encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError):
            return {"ok": False, "error": WRITE_ERROR}

        return {
            "ok": True,
            "path": "solution.py",
            "bytes_written": len(content.encode("utf-8")),
        }

    def _resolve_read_path(self, requested_path: str) -> Path:
        if not isinstance(requested_path, str) or not requested_path:
            raise ValueError("path must be a non-empty string")
        if "\x00" in requested_path:
            raise ValueError("path contains a null byte")

        raw_path = Path(requested_path)
        if raw_path.is_absolute() or raw_path.parts[:1] == ("~",):
            raise ValueError("path must be relative")

        resolved = (self.root / raw_path).resolve(strict=True)
        self._ensure_inside(resolved)
        relative = resolved.relative_to(self.root).as_posix()
        if not self._is_allowed_read_path(relative):
            raise ValueError("path is not readable in v0")
        if not resolved.is_file():
            raise ValueError("path is not a file")
        return resolved

    def _ensure_safe_write_target(self, path: Path) -> None:
        if path.name != "solution.py" or path.parent != self.root:
            raise ValueError("only solution.py can be written")
        if path.is_symlink():
            raise ValueError("solution.py must not be a symlink")
        resolved = path.resolve(strict=True)
        self._ensure_inside(resolved)
        if not resolved.is_file():
            raise ValueError("solution.py must be a file")

    def _ensure_safe_backup_target(self, path: Path) -> None:
        if path.name != ".solution.py.bak" or path.parent != self.root:
            raise ValueError("invalid backup path")
        if path.is_symlink():
            raise ValueError("backup path must not be a symlink")
        resolved = path.resolve(strict=False)
        self._ensure_inside(resolved)

    def _ensure_inside(self, path: Path) -> None:
        path.relative_to(self.root)

    def _is_allowed_read_path(self, relative_path: str) -> bool:
        path = Path(relative_path)
        if path.as_posix() in {"statement.md", "solution.py"}:
            return True
        return (
            len(path.parts) == 2
            and path.parts[0] == "tests"
            and path.suffix in {".in", ".out"}
        )
