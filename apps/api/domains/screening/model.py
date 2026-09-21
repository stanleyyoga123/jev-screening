from typing import Annotated

from pydantic import Field

from integrations.jev import Question


ScreeningQuestions = Annotated[
    dict[Annotated[str, Field(min_length=1)], Question],
    Field(min_length=1, max_length=25),
]


class ScreeningError(Exception):
    """Jev could not return a valid screening result."""


class ScreeningTimeout(ScreeningError):
    """The screening provider timed out."""
