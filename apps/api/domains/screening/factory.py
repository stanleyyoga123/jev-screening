from collections.abc import AsyncIterator

from config.settings import Settings
from domains.screening.service import ScreeningService
from integrations.jev import JevProvider


async def get_screening_service() -> AsyncIterator[ScreeningService]:
    async with JevProvider(Settings()) as jev:
        yield ScreeningService(jev)
