import logging
from types import TracebackType
from typing import Annotated, Literal, Self

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationInfo,
    field_validator,
)
from config.settings import Settings
from core.logging import log_operation


logger = logging.getLogger("JevProvider")

Content = str | dict[str, JsonValue] | list[JsonValue]
Criteria = dict[str, JsonValue] | list[JsonValue]


class Question(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, validate_default=True
    )

    type: Literal["choice", "score", "noul"]
    instructions: Content
    criteria: Criteria | None = None

    @field_validator("instructions")
    @classmethod
    def nonempty_instructions(cls, value: Content) -> Content:
        if not value or isinstance(value, str) and not value.strip():
            raise ValueError("Question instructions must not be empty")
        return value

    @field_validator("criteria", mode="after")
    @classmethod
    def validate_criteria(
        cls, value: Criteria | None, info: ValidationInfo
    ) -> Criteria | None:
        kind = info.data.get("type")
        if kind == "choice" and (not isinstance(value, dict) or not value):
            raise ValueError("Choice questions need a nonempty criteria map")
        if kind == "score" and (not isinstance(value, list) or not value):
            raise ValueError("Score questions need a nonempty criteria list")
        if kind == "noul" and value is not None:
            raise ValueError("Noul questions do not accept criteria")
        return value


class JevRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    model: str = Field(min_length=1)
    state: Content
    questions: dict[Annotated[str, Field(min_length=1)], Question] = Field(min_length=1)

    @field_validator("state")
    @classmethod
    def nonempty_state(cls, value: Content) -> Content:
        if not value or isinstance(value, str) and not value.strip():
            raise ValueError("State must not be empty")
        return value


class JevResponse(BaseModel):
    # The experimental endpoint may add usage or other metadata.
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)

    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    answers: dict[str, JsonValue]


class JevResponseError(ValueError):
    """The response does not contain all requested answers."""


class JevProvider:
    def __init__(self, settings: Settings) -> None:
        self._url = "https://openrouter.ai/api/alpha/decisions"
        self._model = settings.jev_model
        self._timeout = settings.provider_timeout_seconds
        self._client = httpx.AsyncClient()
        self._headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def hit(
        self,
        state: Content,
        questions: dict[str, Question | dict[str, JsonValue]],
    ) -> JevResponse:
        with log_operation(logger, "jev.evaluate"):
            payload = JevRequest(model=self._model, state=state, questions=questions)
            response = await self._client.post(
                self._url,
                headers=self._headers,
                json=payload.model_dump(mode="json", exclude_none=True),
                timeout=self._timeout,
            )
            response.raise_for_status()
            result = JevResponse.model_validate_json(response.content)
            if not payload.questions.keys() <= result.answers.keys():
                raise JevResponseError("Jev response is missing requested answers")
            return result

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
