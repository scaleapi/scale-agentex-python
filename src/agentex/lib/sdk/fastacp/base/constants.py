from __future__ import annotations

# Header filtering rules for FastACP server

# Prefixes to skip (case-insensitive beginswith checks)
FASTACP_HEADER_SKIP_PREFIXES: tuple[str, ...] = (
    "content-",
    "host",
    "user-agent",
    "x-forwarded-",
    "sec-",
)

# Exact header names to skip (case-insensitive matching done by lowercasing keys)
FASTACP_HEADER_SKIP_EXACT: set[str] = {
    "x-agent-api-key",
    "connection",
    "accept-encoding",
    "cookie",
    "content-length",
    "transfer-encoding",
}


