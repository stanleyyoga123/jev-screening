from typing import NoReturn

from core.errors import FeatureNotImplementedError


class ScreeningService:
    async def screen(self) -> NoReturn:
        raise FeatureNotImplementedError("Screening screen is not implemented yet")
