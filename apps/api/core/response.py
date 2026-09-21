from typing import Generic, TypeVar

from pydantic import BaseModel


Data = TypeVar("Data")


class StandardResponse(BaseModel, Generic[Data]):
    success: bool
    data: Data
