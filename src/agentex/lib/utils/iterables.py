from collections.abc import AsyncGenerator
from typing import Any


async def async_enumerate(
    aiterable: AsyncGenerator, start: int = 0
) -> AsyncGenerator[tuple[int, Any], None]:
    """
    Enumerate an async generator.
    """
    i = start
    async for item in aiterable:
        yield i, item
        i += 1
