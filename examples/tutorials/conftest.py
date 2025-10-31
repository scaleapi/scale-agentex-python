"""
Pytest configuration for AgentEx tutorials.

Prevents pytest from trying to collect our testing framework helper functions
(test_sync_agent, test_agentic_agent) as if they were test functions.
"""


def pytest_configure(config):  # noqa: ARG001
    """
    Configure pytest to not collect our framework functions.

    Mark test_sync_agent and test_agentic_agent as non-tests.

    Args:
        config: Pytest config (required by hook signature)
    """
    # Import our testing module
    try:
        import agentex.lib.testing.sessions.sync
        import agentex.lib.testing.sessions.agentic

        # Mark our context manager functions as non-tests
        agentex.lib.testing.sessions.sync.test_sync_agent.__test__ = False
        agentex.lib.testing.sessions.agentic.test_agentic_agent.__test__ = False
    except (ImportError, AttributeError):
        # If module not available, that's fine
        pass
