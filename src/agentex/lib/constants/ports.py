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
HEALTH_CHECK_PORT = 8080
