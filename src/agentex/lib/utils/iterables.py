from __future__ import annotations

from typing import Any
from collections.abc import AsyncGenerator


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
