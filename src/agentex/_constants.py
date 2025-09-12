# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import httpx

RAW_RESPONSE_HEADER = "X-Stainless-Raw-Response"
OVERRIDE_CAST_TO_HEADER = "____stainless_override_cast_to"

# default timeout is 1 minute
DEFAULT_TIMEOUT = httpx.Timeout(timeout=300, connect=5.0)
DEFAULT_MAX_RETRIES = 0
DEFAULT_CONNECTION_LIMITS = httpx.Limits(max_connections=1000, max_keepalive_connections=1000)

INITIAL_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 8.0
