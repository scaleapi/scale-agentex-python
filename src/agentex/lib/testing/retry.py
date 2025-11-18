"""
Retry Logic for API Calls.

Provides decorators for retrying API calls with exponential backoff.
"""

from __future__ import annotations

import time
import asyncio
import logging
from typing import TypeVar, Callable, ParamSpec
from functools import wraps

from agentex.lib.testing.config import config

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def with_retry(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to retry sync functions on transient failures.

    Args:
        func: Function to wrap with retry logic

    Returns:
        Wrapped function with retry behavior
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        last_exception = None
        delay = config.api_retry_delay

        for attempt in range(1, config.api_retry_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Don't retry on last attempt
                if attempt == config.api_retry_attempts:
                    break

                # Log retry attempt
                logger.warning(
                    f"API call failed (attempt {attempt}/{config.api_retry_attempts}): {e}. Retrying in {delay}s..."
                )

                # Wait before retry
                time.sleep(delay)

                # Exponential backoff
                delay *= config.api_retry_backoff_factor

        # All retries exhausted
        logger.error(f"API call failed after {config.api_retry_attempts} attempts: {last_exception}")
        if last_exception:
            raise last_exception
        raise RuntimeError("All retries exhausted without exception")

    return wrapper


def with_async_retry(func):  # type: ignore[no-untyped-def]
    """
    Decorator to retry async functions on transient failures.

    Args:
        func: Async function to wrap with retry logic

    Returns:
        Wrapped async function with retry behavior
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
        last_exception = None
        delay = config.api_retry_delay

        for attempt in range(1, config.api_retry_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Don't retry on last attempt
                if attempt == config.api_retry_attempts:
                    break

                # Log retry attempt
                logger.warning(
                    f"API call failed (attempt {attempt}/{config.api_retry_attempts}): {e}. Retrying in {delay}s..."
                )

                # Wait before retry
                await asyncio.sleep(delay)

                # Exponential backoff
                delay *= config.api_retry_backoff_factor

        # All retries exhausted
        logger.error(f"API call failed after {config.api_retry_attempts} attempts: {last_exception}")
        if last_exception:
            raise last_exception
        raise RuntimeError("All retries exhausted without exception")

    return wrapper  # type: ignore[return-value]
