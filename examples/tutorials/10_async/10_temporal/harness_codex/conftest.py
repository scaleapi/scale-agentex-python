"""Add the agent's project root to sys.path so ``import project`` works.

Also sets minimal environment variables so FastACP, tracing, and the
Temporal workflow module can be imported without a running server.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("AGENT_NAME", "at-harness-codex-test")
os.environ.setdefault("ACP_URL", "http://localhost:8000")
os.environ.setdefault("WORKFLOW_NAME", "at-harness-codex")
os.environ.setdefault("WORKFLOW_TASK_QUEUE", "at_harness_codex_queue")
