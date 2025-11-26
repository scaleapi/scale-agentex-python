"""
Pytest configuration for AgentEx tutorials.

Prevents pytest from trying to collect our testing framework helper functions
(sync_test_agent, async_test_agent) as if they were test functions.
"""


def pytest_configure(config):  # noqa: ARG001
    """
    Configure pytest to not collect our framework functions.

    Mark sync_test_agent and async_test_agent as non-tests.

    Args:
        config: Pytest config (required by hook signature)
    """
    # Import our testing module
    try:
        import agentex.lib.testing.sessions.sync
        import agentex.lib.testing.sessions.asynchronous

        # Mark our context manager functions as non-tests
        agentex.lib.testing.sessions.sync.sync_test_agent.__test__ = False
        agentex.lib.testing.sessions.asynchronous.async_test_agent.__test__ = False
    except (ImportError, AttributeError):
        # If module not available, that's fine
        pass
