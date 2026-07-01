from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent import ModelResponse


@dataclass
class ScriptedFakeModelClient:
    responses: list[ModelResponse]
    fallback_text: str = "No more scripted responses."
    requests: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = field(
        default_factory=list
    )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        self.requests.append((list(messages), list(tools)))
        if not self.responses:
            return ModelResponse(final_text=self.fallback_text)
        return self.responses.pop(0)
