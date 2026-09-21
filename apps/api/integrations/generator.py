import logging
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from config.settings import Settings
from core.logging import log_operation


logger = logging.getLogger("GeneratorProvider")


NonblankText = Annotated[str, Field(min_length=1, pattern=r"\S")]


class GeneratorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    role: Literal["system", "user", "assistant"]
    content: NonblankText


class GeneratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    model: NonblankText
    messages: list[GeneratorMessage] = Field(min_length=1)
    stream: Literal[False] = False


class GeneratedMessage(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    role: Literal["assistant"]
    content: NonblankText


class GeneratorChoice(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    message: GeneratedMessage
    # Only completed text is usable; truncated or filtered output must fail.
    finish_reason: Literal["stop"]


class GeneratorResponse(BaseModel):
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)

    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    choices: list[GeneratorChoice] = Field(min_length=1)

    @property
    def content(self) -> str:
        return self.choices[0].message.content


class GeneratorProvider:
    """Text generation through OpenRouter, with a provider-owned HTTP client."""

    def __init__(self, settings: Settings) -> None:
        self._url = "https://openrouter.ai/api/v1/chat/completions"
        self._model = settings.generator_model
        self._timeout = settings.provider_timeout_seconds
        self._client = httpx.AsyncClient()
        self._headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def hit(self, messages: list[GeneratorMessage]) -> GeneratorResponse:
        """Generate text without automatic retries or criteria-specific parsing."""
        with log_operation(logger, "generator.generate"):
            payload = GeneratorRequest(model=self._model, messages=messages)
            response = await self._client.post(
                self._url,
                headers=self._headers,
                json=payload.model_dump(mode="json"),
                timeout=self._timeout,
            )
            response.raise_for_status()
            return GeneratorResponse.model_validate_json(response.content)

    async def aclose(self) -> None:
        await self._client.aclose()
