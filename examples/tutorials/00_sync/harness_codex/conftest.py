"""Add the agent's project root to sys.path so ``import project`` works.

Also sets minimal environment variables so the FastACP and tracing modules
can be imported without a running agent server.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("AGENT_NAME", "s-harness-codex-test")
os.environ.setdefault("ACP_URL", "http://localhost:8000")
