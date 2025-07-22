from agentex import AsyncAgentex
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.utils.logging import make_logger
from agentex.types.agent_task_tracker import AgentTaskTracker

logger = make_logger(__name__)


class AgentTaskTrackerService:
    def __init__(
        self, agentex_client: AsyncAgentex, tracer: AsyncTracer,
    ):
        self._agentex_client = agentex_client
        self._tracer = tracer

    async def get_agent_task_tracker(
        self,
        tracker_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> AgentTaskTracker:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="get_agent_task_tracker",
            input={"tracker_id": tracker_id},
        ) as span:
            tracker = await self._agentex_client.tracker.retrieve(
                tracker_id
            )
            if span:
                span.output = tracker.model_dump()
            return tracker

    async def get_by_task_and_agent(
        self,
        task_id: str,
        agent_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> AgentTaskTracker | None:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="get_by_task_and_agent",
            input={"task_id": task_id, "agent_id": agent_id},
        ) as span:
            trackers = await self._agentex_client.tracker.list(
                task_id=task_id,
                agent_id=agent_id,
            )
            tracker = trackers[0] if trackers else None
            if span:
                span.output = tracker.model_dump() if tracker else None
            return tracker

    async def update_agent_task_tracker(
        self,
        tracker_id: str,
        last_processed_event_id: str | None = None,
        status: str | None = None,
        status_reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> AgentTaskTracker:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="update_agent_task_tracker",
            input={
                "tracker_id": tracker_id,
                "last_processed_event_id": last_processed_event_id,
                "status": status,
                "status_reason": status_reason,
            },
        ) as span:
            tracker = await self._agentex_client.tracker.update(
                tracker_id=tracker_id,
                last_processed_event_id=last_processed_event_id,
                status=status,
                status_reason=status_reason,
            )
            if span:
                span.output = tracker.model_dump()
            return tracker
