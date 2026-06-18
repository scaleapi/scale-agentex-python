"""Shared, harness-independent machinery for the unified harness surface.

The Agentex StreamTaskMessage* stream is the single source of truth; this
package derives spans from it and delivers it (yield or auto-send), so every
harness tap gets streaming + tracing + turn usage uniformly.
"""
