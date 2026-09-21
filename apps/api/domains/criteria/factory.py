from collections.abc import AsyncIterator

from config.settings import Settings
from domains.criteria.service import CriteriaService
from integrations.generator import GeneratorProvider


def get_generator_provider() -> GeneratorProvider:
    return GeneratorProvider(Settings())


async def get_criteria_service() -> AsyncIterator[CriteriaService]:
    generator = get_generator_provider()
    try:
        yield CriteriaService(generator)
    finally:
        await generator.aclose()
