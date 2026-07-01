from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent.trace import TraceWriter, summarize_tool_result


class TraceTests(unittest.TestCase):
    def test_trace_writer_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            trace = TraceWriter(path)

            trace.write({"type": "tool_call", "tool": "run_tests"})
            trace.write({"type": "final", "status": "success"})

            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(events[0], {"type": "tool_call", "tool": "run_tests"})
        self.assertEqual(events[1], {"type": "final", "status": "success"})

    def test_trace_writer_redacts_environment_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            old_value = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "secret-value"
            try:
                trace = TraceWriter(path)
                trace.write(
                    {
                        "type": "tool_call",
                        "api_key": "secret-value",
                        "message": "secret-value should not appear",
                    }
                )
            finally:
                if old_value is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = old_value

            raw = path.read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn("secret-value", raw)
        self.assertEqual(event["api_key"], "[redacted]")
        self.assertIn("[redacted]", event["message"])

    def test_tool_result_summary_excludes_file_content(self):
        summary = summarize_tool_result(
            {
                "ok": True,
                "path": "statement.md",
                "content": "large problem statement",
            }
        )

        self.assertEqual(summary, {"ok": True, "path": "statement.md"})


if __name__ == "__main__":
    unittest.main()
