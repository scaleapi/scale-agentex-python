"""
Centralized port defaults for AgentEx.

These ports are chosen to avoid conflicts with common services (3000, 5003, 8000, 80).
All ports remain configurable via environment variables and manifest configuration.
"""

# AgentEx API server default port (configurable via AGENTEX_BASE_URL env var)
AGENTEX_API_PORT = 5718

# ACP (Agent Communication Protocol) server default port (configurable via ACP_PORT env var)
ACP_SERVER_PORT = 8718

# Health check endpoint default port (configurable via HEALTH_CHECK_PORT env var)
HEALTH_CHECK_PORT = 5720

# Debug server default port (configurable via AGENTEX_DEBUG_PORT env var)
DEBUG_PORT = 9678

# Temporal server default address (configurable via TEMPORAL_ADDRESS env var)
TEMPORAL_ADDRESS = "localhost:7233"

# Default Redis URL (configurable via REDIS_URL env var)
REDIS_URL = "redis://localhost:6379"

# AgentEx API base URL (configurable via AGENTEX_BASE_URL env var)
AGENTEX_API_BASE_URL = f"http://localhost:{AGENTEX_API_PORT}"
