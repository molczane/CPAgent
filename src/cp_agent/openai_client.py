from __future__ import annotations

import json
from typing import Any, Mapping

from .agent import ModelResponse, ToolCall

DEFAULT_MODEL = "gpt-5-mini"


class OpenAIClientError(RuntimeError):
    """Raised when the OpenAI SDK is unavailable or a request fails."""


class OpenAIModelClient:
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        sdk_client: Any | None = None,
    ):
        self.model = model
        self.client = sdk_client or make_sdk_client(api_key)

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "OpenAIModelClient":
        model = environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        return cls(model=model, api_key=environ.get("OPENAI_API_KEY"))

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        instructions, response_input = build_responses_input(messages)
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=response_input,
                tools=tools,
            )
        except Exception as exc:  # pragma: no cover - exact SDK errors vary.
            raise OpenAIClientError("OpenAI API request failed.") from exc

        return parse_response(response)


def make_sdk_client(api_key: str | None) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIClientError(
            "The openai package is not installed. Install project dependencies first."
        ) from exc

    if api_key:
        return OpenAI(api_key=api_key)
    return OpenAI()


def build_responses_input(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    instructions: list[str] = []
    response_input: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""

        if role == "system":
            if content:
                instructions.append(content)
            continue

        if role == "user":
            response_input.append({"role": "user", "content": content})
            continue

        if role == "assistant":
            response_items = message.get("response_items") or []
            if response_items:
                response_input.extend(response_items)
                continue
            if content:
                response_input.append({"role": "assistant", "content": content})
            for tool_call in message.get("tool_calls", []):
                response_input.append(
                    {
                        "type": "function_call",
                        "call_id": tool_call["id"],
                        "name": tool_call["name"],
                        "arguments": json.dumps(
                            tool_call.get("args", {}),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )
            continue

        if role == "tool":
            response_input.append(
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": content,
                }
            )

    return "\n\n".join(instructions) or None, response_input


def parse_response(response: Any) -> ModelResponse:
    output_items = get_output_items(response)
    tool_calls: list[ToolCall] = []
    response_items = tuple(to_response_input_item(item) for item in output_items)
    for item in output_items:
        if get_value(item, "type") != "function_call":
            continue
        call_id = get_value(item, "call_id") or get_value(item, "id")
        name = get_value(item, "name")
        if not call_id or not name:
            continue
        tool_calls.append(
            ToolCall(
                id=str(call_id),
                name=str(name),
                args=parse_arguments(get_value(item, "arguments")),
            )
        )

    if tool_calls:
        return ModelResponse(
            tool_calls=tuple(tool_calls),
            response_items=response_items,
        )

    return ModelResponse(final_text=extract_text(response), response_items=response_items)


def get_output_items(response: Any) -> list[Any]:
    output = get_value(response, "output", [])
    return list(output or [])


def to_response_input_item(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)

    result: dict[str, Any] = {}
    for key in (
        "id",
        "type",
        "call_id",
        "name",
        "arguments",
        "status",
        "summary",
        "content",
    ):
        value = getattr(item, key, None)
        if value is not None:
            result[key] = value
    return result


def extract_text(response: Any) -> str:
    output_text = get_value(response, "output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    for item in get_output_items(response):
        if get_value(item, "type") != "message":
            continue
        for content_item in get_value(item, "content", []) or []:
            text = get_value(content_item, "text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str):
        return {}
    try:
        decoded = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return decoded
    return {}


def get_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
