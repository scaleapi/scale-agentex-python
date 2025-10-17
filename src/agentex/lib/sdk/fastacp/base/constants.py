from __future__ import annotations

# Header filtering rules for FastACP server
# These rules match the gateway's security filtering

# Hop-by-hop headers that should not be forwarded
HOP_BY_HOP_HEADERS: set[str] = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
    "host",
}

# Sensitive headers that should never be forwarded
BLOCKED_HEADERS: set[str] = {
    "authorization",
    "cookie",
    "x-agent-api-key",
}

# Legacy constants for backward compatibility
FASTACP_HEADER_SKIP_EXACT: set[str] = HOP_BY_HOP_HEADERS | BLOCKED_HEADERS

FASTACP_HEADER_SKIP_PREFIXES: tuple[str, ...] = (
    "x-forwarded-",  # proxy headers
    "sec-",  # security headers added by browsers
)


