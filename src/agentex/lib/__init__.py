from agentex.lib._version_guard import verify_client_compatibility

# Fail fast + clearly on a skewed/incomplete agentex-client install.
verify_client_compatibility()
