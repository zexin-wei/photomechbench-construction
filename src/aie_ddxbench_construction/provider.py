"""Provider-neutral model request boundary.

The package records a provider label and model identifier, but never stores an
API key. Endpoints are supplied at runtime and are not embedded in prompts.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    response_id: str | None = None
    response_model: str | None = None
    usage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ModelClient(Protocol):
    provider_name: str
    model: str

    def complete(self, *, system_prompt: str, user_text: str, image_paths: tuple[Path, ...] = ()) -> ModelResponse:
        ...


class OpenAICompatibleClient:
    """Small adapter around an injected OpenAI-compatible SDK client."""

    def __init__(
        self,
        *,
        client: Any,
        provider_name: str,
        model: str,
        temperature: float = 0.0,
        max_output_tokens: int = 8192,
        api_protocol: str = "chat_completions",
        empty_response_retries: int = 1,
    ) -> None:
        if api_protocol not in {"chat_completions", "responses"}:
            raise ValueError(f"Unsupported API protocol: {api_protocol}")
        self._client = client
        self.provider_name = provider_name
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.api_protocol = api_protocol
        self.empty_response_retries = max(0, empty_response_retries)

    def complete(self, *, system_prompt: str, user_text: str, image_paths: tuple[Path, ...] = ()) -> ModelResponse:
        if self.api_protocol == "responses":
            return self._complete_responses(
                system_prompt=system_prompt,
                user_text=user_text,
                image_paths=image_paths,
            )
        return self._complete_chat_completions(
            system_prompt=system_prompt,
            user_text=user_text,
            image_paths=image_paths,
        )

    def _complete_chat_completions(
        self,
        *,
        system_prompt: str,
        user_text: str,
        image_paths: tuple[Path, ...],
    ) -> ModelResponse:
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image_path in image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _image_data_url(image_path)},
                }
            )
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=self.temperature,
            max_tokens=self.max_output_tokens,
        )
        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        if usage is not None and hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        return ModelResponse(
            text=choice.message.content or "",
            response_id=getattr(response, "id", None),
            response_model=getattr(response, "model", None),
            usage=usage if isinstance(usage, dict) else None,
        )

    def _complete_responses(
        self,
        *,
        system_prompt: str,
        user_text: str,
        image_paths: tuple[Path, ...],
    ) -> ModelResponse:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user_text}]
        for image_path in image_paths:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _image_data_url(image_path),
                }
            )
        response = None
        text = ""
        attempts = 1 + self.empty_response_retries
        for attempt in range(1, attempts + 1):
            try:
                stream = self._client.responses.create(
                    model=self.model,
                    instructions=system_prompt,
                    input=[{"role": "user", "content": content}],
                    max_output_tokens=self.max_output_tokens,
                    stream=True,
                )
                chunks: list[str] = []
                response = None
                for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", None)
                        if isinstance(delta, str):
                            chunks.append(delta)
                    elif event_type == "response.completed":
                        response = getattr(event, "response", None)
            except Exception:
                if attempt >= attempts:
                    raise
                continue
            text = "".join(chunks)
            if not text and response is not None:
                text = _responses_output_text(response)
            if text:
                break
        usage = getattr(response, "usage", None)
        if usage is not None and hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        return ModelResponse(
            text=text,
            response_id=getattr(response, "id", None),
            response_model=getattr(response, "model", None),
            usage=usage if isinstance(usage, dict) else None,
            metadata={
                "status": getattr(response, "status", None),
                "incomplete_details": _model_dump(getattr(response, "incomplete_details", None)),
                "empty_response_attempts": attempt,
            },
        )


def _image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(suffix)
    if media_type is None:
        raise ValueError(f"Unsupported review image type: {path.suffix}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _responses_output_text(response: Any) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct:
        return direct
    parts: list[str] = []
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts)


def _model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value if isinstance(value, (str, int, float, bool, list, dict)) else str(value)
