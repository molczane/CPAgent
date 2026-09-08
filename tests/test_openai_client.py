from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cp_agent import cli
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

    def test_local_settings_are_passed_to_official_sdk(self):
        settings = {
            "OPENAI_API_KEY": "local-test-key",
            "OPENAI_MODEL": "local-qwen",
            "OPENAI_BASE_URL": "http://127.0.0.1:8888/v1",
            "OPENAI_TIMEOUT_SECONDS": "3600",
            "OPENAI_MAX_RETRIES": "0",
        }
        with patch("openai.OpenAI") as sdk:
            client = OpenAIModelClient.from_environ(settings)

        sdk.assert_called_once_with(
            api_key="local-test-key", base_url="http://127.0.0.1:8888/v1",
            timeout=3600.0, max_retries=0,
        )
        self.assertEqual(client.model, "local-qwen")
        sdk.return_value.models.list.assert_not_called()

    def test_unset_settings_preserve_sdk_defaults(self):
        with patch("openai.OpenAI") as sdk:
            client = OpenAIModelClient.from_environ({"OPENAI_API_KEY": "test-key"})
        sdk.assert_called_once_with(api_key="test-key")
        self.assertEqual(client.model, DEFAULT_MODEL)
        sdk.return_value.models.list.assert_not_called()

    def test_invalid_settings_fail_before_sdk_creation(self):
        invalid_settings = {
            "OPENAI_TIMEOUT_SECONDS": ["0", "-1", "nan", "inf", "oops"],
            "OPENAI_MAX_RETRIES": ["-1", "0.5", "nan", "oops"],
        }
        for name, values in invalid_settings.items():
            for value in values:
                with self.subTest(name=name, value=value), patch("openai.OpenAI") as sdk:
                    with self.assertRaisesRegex(OpenAIClientError, name):
                        OpenAIModelClient.from_environ({name: value})
                    sdk.assert_not_called()

    def test_auto_requires_explicit_endpoint(self):
        with patch("openai.OpenAI") as sdk:
            with self.assertRaisesRegex(OpenAIClientError, "requires OPENAI_BASE_URL"):
                OpenAIModelClient.from_environ({"OPENAI_MODEL": "auto"})
            sdk.assert_not_called()

    def test_auto_rejects_missing_or_ambiguous_loaded_models(self):
        for loaded in ([], ["qwen-a", "qwen-b"]):
            with self.subTest(loaded=loaded):
                sdk = Mock()
                sdk.models.list.return_value = SimpleNamespace(data=[
                    SimpleNamespace(id="cached", loaded=False),
                    SimpleNamespace(id="no-loaded-marker"),
                    *(SimpleNamespace(id=name, loaded=True) for name in loaded),
                ])
                with patch("cp_agent.openai_client.make_sdk_client", return_value=sdk):
                    with self.assertRaisesRegex(OpenAIClientError, "Expected one loaded model"):
                        OpenAIModelClient.from_environ({
                            "OPENAI_MODEL": "auto",
                            "OPENAI_BASE_URL": "http://127.0.0.1:8888/v1",
                        })
                sdk.responses.create.assert_not_called()

    def test_sdk_errors_are_actionable_and_do_not_expose_server_body(self):
        request = httpx.Request("POST", "http://127.0.0.1:8888/v1/responses")
        cases = [
            (APITimeoutError(request=request), "OPENAI_TIMEOUT_SECONDS"),
            (APIConnectionError(request=request), "OPENAI_BASE_URL"),
        ]
        for status, expected in [(401, "OPENAI_API_KEY"), (403, "OPENAI_API_KEY"),
                                 (404, "Responses API"), (500, "HTTP 500")]:
            response = httpx.Response(status, request=request)
            cases.append((APIStatusError(
                "secret-server-body", response=response, body={"key": "secret-test-key"},
            ), expected))
        for error, expected in cases:
            with self.subTest(error=type(error).__name__, expected=expected):
                client = OpenAIModelClient(sdk_client=FakeSdkClient(error))
                with self.assertRaises(OpenAIClientError) as raised:
                    client.complete([], [])
                self.assertIn(expected, str(raised.exception))
                self.assertNotIn("secret", str(raised.exception))

    def test_model_discovery_authentication_failure_stops_before_inference(self):
        requests = []

        def handle(request):
            requests.append(request)
            return httpx.Response(401, json={"error": {"message": "secret-server-body"}})

        with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
            sdk = OpenAI(
                api_key="local-test-key", base_url="http://127.0.0.1:8888/v1",
                max_retries=0, http_client=http_client,
            )
            with patch("cp_agent.openai_client.make_sdk_client", return_value=sdk):
                with self.assertRaisesRegex(OpenAIClientError, "Authentication failed"):
                    OpenAIModelClient.from_environ({
                        "OPENAI_MODEL": "auto",
                        "OPENAI_BASE_URL": "http://127.0.0.1:8888/v1",
                    })
        self.assertEqual([r.url.path for r in requests], ["/v1/models"])

    def test_local_sdk_transport_replays_tool_result_and_returns_advice(self):
        requests = []
        call = {
            "id": "fc-local", "type": "function_call", "call_id": "call-local",
            "name": "read_file", "status": "completed",
            "arguments": json.dumps({"path": "statement.md", "reason": "Read the task"}),
        }
        advice = {
            "id": "msg-local", "type": "message", "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Try doubling the input.", "annotations": []}],
        }

        def handle(request):
            requests.append(request)
            if request.method == "GET":
                return httpx.Response(200, json={"object": "list", "data": [
                    {"id": "cached-other", "object": "model", "created": 0,
                     "owned_by": "local", "loaded": False},
                    {"id": "local-qwen", "object": "model", "created": 0,
                     "owned_by": "local", "loaded": True},
                ]})
            return httpx.Response(200, json={
                "id": f"resp-{len(requests)}", "object": "response",
                "created_at": 0, "status": "completed", "model": "local-qwen",
                "output": [call if len(requests) == 2 else advice],
            })

        with tempfile.TemporaryDirectory() as tmp, \
                httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
            task = Path(tmp) / "task"
            task.mkdir()
            (task / "statement.md").write_text("Double the input.\n", encoding="utf-8")
            (task / "solution.py").write_text("print('wrong')\n", encoding="utf-8")
            (task / "tests").mkdir()
            (task / "tests/sample.in").write_text("2\n", encoding="utf-8")
            (task / "tests/sample.out").write_text("4\n", encoding="utf-8")

            def make_client(api_key, *, base_url, timeout_seconds, max_retries):
                return OpenAI(
                    api_key=api_key, base_url=base_url, timeout=timeout_seconds,
                    max_retries=max_retries, http_client=http_client,
                )

            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, {}, clear=True), patch(
                "cp_agent.openai_client.make_sdk_client", side_effect=make_client,
            ):
                code = cli.main(
                    ["advise", str(task), "--verbose", "--trace-file", str(Path(tmp) / "trace.jsonl")],
                    environ={
                        "OPENAI_API_KEY": "local-test-key", "OPENAI_MODEL": "auto",
                        "OPENAI_BASE_URL": "http://127.0.0.1:8888/v1",
                        "OPENAI_TIMEOUT_SECONDS": "3600", "OPENAI_MAX_RETRIES": "0",
                    },
                    stdout=stdout, stderr=stderr,
                )
            self.assertEqual((task / "solution.py").read_text(), "print('wrong')\n")
            self.assertFalse((task / ".solution.py.bak").exists())

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("Model: local-qwen", stdout.getvalue())
        self.assertIn("Try doubling the input.", stdout.getvalue())
        self.assertNotIn("local-test-key", stdout.getvalue())
        self.assertEqual([r.url.path for r in requests], [
            "/v1/models", "/v1/responses", "/v1/responses",
        ])
        for request in requests:
            self.assertEqual(request.url.host, "127.0.0.1")
            self.assertEqual(request.headers["authorization"], "Bearer local-test-key")
        first, second = [json.loads(r.content) for r in requests[1:]]
        self.assertEqual(first["model"], "local-qwen")
        self.assertIn("competitive programming advisor", first["instructions"])
        self.assertEqual([t["name"] for t in first["tools"]], ["list_files", "read_file", "run_tests"])
        self.assertIn(call, second["input"])
        tool_result = next(i for i in second["input"] if i.get("type") == "function_call_output")
        self.assertEqual(tool_result["call_id"], "call-local")
        self.assertEqual(json.loads(tool_result["output"])["content"], "Double the input.\n")

    def test_build_responses_input_converts_tool_loop_messages(self):
        response = ModelResponse(
            tool_calls=(
                ToolCall(
                    "call-1",
                    "read_file",
                    {
                        "path": "statement.md",
                        "reason": "I need to read the statement first",
                    },
                ),
            )
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
            {
                "path": "statement.md",
                "reason": "I need to read the statement first",
            },
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
                    arguments=(
                        '{"path": "statement.md", '
                        '"reason": "I need to inspect the task"}'
                    ),
                )
            ]
        )

        result = parse_response(response)

        self.assertEqual(
            result.tool_calls,
            (
                ToolCall(
                    "call-1",
                    "read_file",
                    {
                        "path": "statement.md",
                        "reason": "I need to inspect the task",
                    },
                ),
            ),
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
                            "arguments": json.dumps(
                                {
                                    "path": "statement.md",
                                    "reason": "I need to read the task",
                                }
                            ),
                        }
                    ]
                },
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-2",
                            "name": "run_tests",
                            "arguments": json.dumps(
                                {"reason": "I need to see current failures"}
                            ),
                        }
                    ]
                },
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-3",
                            "name": "write_solution",
                            "arguments": json.dumps(
                                {
                                    "content": corrected_solution,
                                    "reason": "I have a candidate fix",
                                }
                            ),
                        }
                    ]
                },
                {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call-4",
                            "name": "run_tests",
                            "arguments": json.dumps(
                                {"reason": "I need to verify the fix"}
                            ),
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

    def test_openai_wrapper_receives_read_only_tools_in_advise_mode(self):
        fake_sdk = SequencedFakeSdkClient(
            [
                {
                    "output_text": "Use the sample tests to infer the pattern.",
                    "output": [],
                }
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
                config=AgentConfig(
                    mode="advise",
                    max_iterations=2,
                    python_executable=sys.executable,
                ),
            )

            result = agent.run()

        self.assertEqual(result.status, "success")
        self.assertEqual(result.final_answer, "Use the sample tests to infer the pattern.")
        self.assertEqual(
            [tool["name"] for tool in fake_sdk.responses.calls[0]["tools"]],
            ["list_files", "read_file", "run_tests"],
        )


if __name__ == "__main__":
    unittest.main()
