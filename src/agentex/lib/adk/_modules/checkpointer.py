from __future__ import annotations

import asyncio
import os

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Pool configuration - sized for single agent with concurrent task execution
# Checkpoint operations are fast (single row upserts), so connections are released quickly
_POOL_MIN_SIZE = 2  # Keep a couple connections warm
_POOL_MAX_SIZE = 20  # Handle concurrent tasks within a single agent pod
_POOL_TIMEOUT = 60.0  # Wait for connection before failing
_POOL_MAX_IDLE = 300.0  # Clean up idle connections after 5 minutes


class AgentexCheckpointer:
    """LangGraph checkpointer using AgentEx PostgreSQL.

    Provides a singleton PostgreSQL connection pool for LangGraph checkpoint storage.
    Thread-safe initialization with proper cleanup support.

    Usage:
        checkpointer = await AgentexCheckpointer.create()
        # Use checkpointer with LangGraph...

        # On shutdown:
        await AgentexCheckpointer.close()
    """

    _pool: AsyncConnectionPool | None = None
    _checkpointer: AsyncPostgresSaver | None = None
    _lock: asyncio.Lock | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the initialization lock."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def create(cls) -> AsyncPostgresSaver:
        """Create a PostgreSQL checkpointer.

        Uses DATABASE_URL from environment (same as AgentEx).
        Tables are auto-created on first use via CREATE IF NOT EXISTS.

        Returns:
            AsyncPostgresSaver configured for LangGraph checkpoint storage.

        Raises:
            ValueError: If DATABASE_URL is not set.
            Exception: If connection to PostgreSQL fails.
        """
        # Fast path - already initialized
        if cls._checkpointer is not None:
            return cls._checkpointer

        async with cls._get_lock():
            # Double-check after acquiring lock
            if cls._checkpointer is not None:
                return cls._checkpointer

            db_url = os.environ.get("DATABASE_URL")
            if not db_url:
                raise ValueError(
                    "DATABASE_URL not set. "
                    "Add it to your manifest.yaml env section."
                )

            pool = None
            try:
                logger.info("Initializing PostgreSQL checkpointer connection pool")

                pool = AsyncConnectionPool(
                    conninfo=db_url,
                    min_size=_POOL_MIN_SIZE,
                    max_size=_POOL_MAX_SIZE,
                    timeout=_POOL_TIMEOUT,
                    max_idle=_POOL_MAX_IDLE,
                    open=False,
                    kwargs={"autocommit": True},
                )
                await pool.open()

                checkpointer = AsyncPostgresSaver(pool)
                await checkpointer.setup()  # Idempotent - creates tables if needed

                # Only set class state after everything succeeds
                cls._pool = pool
                cls._checkpointer = checkpointer

                logger.info("PostgreSQL checkpointer initialized successfully")
                return cls._checkpointer

            except Exception as e:
                # Clean up pool if it was created
                if pool is not None:
                    try:
                        await pool.close()
                    except Exception as close_error:
                        logger.warning(f"Error closing pool during cleanup: {close_error}")

                logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
                raise

    @classmethod
    async def close(cls) -> None:
        """Close the connection pool and clean up resources.

        Safe to call multiple times. Should be called on application shutdown.
        """
        async with cls._get_lock():
            if cls._pool is not None:
                try:
                    logger.info("Closing PostgreSQL checkpointer connection pool")
                    await cls._pool.close()
                    logger.info("PostgreSQL checkpointer connection pool closed")
                except Exception as e:
                    logger.error(f"Error closing PostgreSQL connection pool: {e}")
                    raise
                finally:
                    cls._pool = None
                    cls._checkpointer = None

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the checkpointer has been initialized."""
        return cls._checkpointer is not None
