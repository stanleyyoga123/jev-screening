from typing import NoReturn

from core.errors import FeatureNotImplementedError


class CriteriaService:
    async def generate(self) -> NoReturn:
        raise FeatureNotImplementedError("Criteria generate is not implemented yet")

    async def validate(self) -> NoReturn:
        raise FeatureNotImplementedError("Criteria validate is not implemented yet")

    async def prompt(self) -> NoReturn:
        raise FeatureNotImplementedError("Criteria prompt is not implemented yet")
