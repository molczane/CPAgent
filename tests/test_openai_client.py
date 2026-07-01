from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent.agent import (
    Agent,
    AgentConfig,
    ModelResponse,
    ToolCall,
    model_message,
    tool_result_message,
)
from cp_agent.openai_client import (
    DEFAULT_MODEL,
    OpenAIClientError,
    OpenAIModelClient,
    build_responses_input,
    parse_response,
)
from cp_agent.tools import get_tool_definitions


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeSdkClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


class SequencedFakeResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class SequencedFakeSdkClient:
    def __init__(self, responses):
        self.responses = SequencedFakeResponses(responses)


class OpenAIClientTests(unittest.TestCase):
    def test_from_environ_uses_model_override_and_api_key(self):
        fake_sdk = FakeSdkClient(SimpleNamespace(output_text="done", output=[]))
        with patch("cp_agent.openai_client.make_sdk_client", return_value=fake_sdk):
            client = OpenAIModelClient.from_environ(
                {"OPENAI_MODEL": "test-model", "OPENAI_API_KEY": "test-key"}
            )

        self.assertEqual(client.model, "test-model")
        self.assertIs(client.client, fake_sdk)

    def test_default_model_constant_is_gpt_5_mini(self):
        self.assertEqual(DEFAULT_MODEL, "gpt-5-mini")

    def test_build_responses_input_converts_tool_loop_messages(self):
        response = ModelResponse(
            tool_calls=(ToolCall("call-1", "read_file", {"path": "statement.md"}),)
        )
        messages = [
            {"role": "system", "content": "system instructions"},
            {"role": "user", "content": "solve task"},
            model_message(response),
            tool_result_message(
                response.tool_calls[0],
                {"ok": True, "content": "statement"},
                config=SimpleNamespace(max_tool_output_chars=10000),
            ),
        ]

        instructions, response_input = build_responses_input(messages)

        self.assertEqual(instructions, "system instructions")
        self.assertEqual(response_input[0], {"role": "user", "content": "solve task"})
        self.assertEqual(response_input[1]["type"], "function_call")
        self.assertEqual(response_input[1]["call_id"], "call-1")
        self.assertEqual(response_input[1]["name"], "read_file")
        self.assertEqual(
            json.loads(response_input[1]["arguments"]),
            {"path": "statement.md"},
        )
        self.assertEqual(response_input[2]["type"], "function_call_output")
        self.assertEqual(response_input[2]["call_id"], "call-1")
        self.assertIn("statement", response_input[2]["output"])

    def test_complete_calls_responses_api_with_tools(self):
        fake_response = SimpleNamespace(output_text="All done.", output=[])
        fake_sdk = FakeSdkClient(fake_response)
        client = OpenAIModelClient(model="test-model", sdk_client=fake_sdk)

        result = client.complete(
            [{"role": "system", "content": "instructions"}],
            get_tool_definitions(),
        )

        self.assertEqual(result, ModelResponse(final_text="All done."))
        call = fake_sdk.responses.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["instructions"], "instructions")
        self.assertEqual(
            [tool["name"] for tool in call["tools"]],
            ["list_files", "read_file", "write_solution", "run_tests"],
        )

    def test_parse_response_returns_tool_calls(self):
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call-1",
                    name="read_file",
                    arguments='{"path": "statement.md"}',
                )
            ]
        )

        result = parse_response(response)

        self.assertEqual(
            result.tool_calls,
            (ToolCall("call-1", "read_file", {"path": "statement.md"}),),
        )
        self.assertEqual(result.response_items[0]["type"], "function_call")
        self.assertEqual(result.response_items[0]["call_id"], "call-1")

    def test_parse_response_returns_final_text_from_message_content(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "All tests pass."},
                    ],
                }
            ]
        }

        result = parse_response(response)

        self.assertEqual(result.final_text, "All tests pass.")
        self.assertEqual(result.response_items[0]["type"], "message")

    def test_api_errors_are_wrapped(self):
        client = OpenAIModelClient(
            model="test-model",
            sdk_client=FakeSdkClient(RuntimeError("boom")),
        )

        with self.assertRaises(OpenAIClientError):
            client.complete([], [])

    def test_openai_wrapper_drives_agent_tool_loop_with_fake_sdk(self):
        corrected_solution = "import sys\nprint(sys.stdin.read().strip())\n"
        fake_sdk = SequencedFakeSdkClient(
            [
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-1",
                            "name": "read_file",
                            "arguments": '{"path": "statement.md"}',
                        }
                    ]
                },
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-2",
                            "name": "run_tests",
                            "arguments": "{}",
                        }
                    ]
                },
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-3",
                            "name": "write_solution",
                            "arguments": json.dumps({"content": corrected_solution}),
                        }
                    ]
                },
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-4",
                            "name": "run_tests",
                            "arguments": "{}",
                        }
                    ]
                },
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "task"
            task.mkdir()
            (task / "statement.md").write_text("Echo input.\n", encoding="utf-8")
            (task / "solution.py").write_text("print('wrong')\n", encoding="utf-8")
            tests = task / "tests"
            tests.mkdir()
            (tests / "sample1.in").write_text("5\n", encoding="utf-8")
            (tests / "sample1.out").write_text("5\n", encoding="utf-8")

            client = OpenAIModelClient(model="test-model", sdk_client=fake_sdk)
            agent = Agent(
                task,
                client,
                config=AgentConfig(max_iterations=5, python_executable=sys.executable),
            )

            result = agent.run()

        self.assertEqual(result.status, "success")
        self.assertEqual(result.tests_passed, 1)
        self.assertEqual(result.tests_total, 1)
        self.assertEqual(
            [event["tool"] for event in result.tool_results],
            ["read_file", "run_tests", "write_solution", "run_tests"],
        )
        self.assertEqual(len(fake_sdk.responses.calls), 4)
        last_input = fake_sdk.responses.calls[-1]["input"]
        self.assertTrue(any(
            item.get("type") == "function_call_output" for item in last_input
        ))


if __name__ == "__main__":
    unittest.main()
