from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.agent_task_tracker import AgentTaskTrackerService
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger
from agentex.types.agent_task_tracker import AgentTaskTracker

logger = make_logger(__name__)


class AgentTaskTrackerActivityName(str, Enum):
    GET_AGENT_TASK_TRACKER = "get-agent-task-tracker"
    GET_AGENT_TASK_TRACKER_BY_TASK_AND_AGENT = (
        "get-agent-task-tracker-by-task-and-agent"
    )
    UPDATE_AGENT_TASK_TRACKER = "update-agent-task-tracker"


class GetAgentTaskTrackerParams(BaseModelWithTraceParams):
    tracker_id: str


class GetAgentTaskTrackerByTaskAndAgentParams(BaseModelWithTraceParams):
    task_id: str
    agent_id: str


class UpdateAgentTaskTrackerParams(BaseModelWithTraceParams):
    tracker_id: str
    last_processed_event_id: str | None
    status: str | None
    status_reason: str | None


class AgentTaskTrackerActivities:
    def __init__(self, agent_task_tracker_service: AgentTaskTrackerService):
        self._agent_task_tracker_service = agent_task_tracker_service

    @activity.defn(name=AgentTaskTrackerActivityName.GET_AGENT_TASK_TRACKER)
    async def get_agent_task_tracker(
        self, params: GetAgentTaskTrackerParams
    ) -> AgentTaskTracker:
        return await self._agent_task_tracker_service.get_agent_task_tracker(
            tracker_id=params.tracker_id,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(
        name=AgentTaskTrackerActivityName.GET_AGENT_TASK_TRACKER_BY_TASK_AND_AGENT
    )
    async def get_agent_task_tracker_by_task_and_agent(
        self,
        params: GetAgentTaskTrackerByTaskAndAgentParams,
    ) -> AgentTaskTracker | None:
        return await self._agent_task_tracker_service.get_by_task_and_agent(
            task_id=params.task_id,
            agent_id=params.agent_id,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=AgentTaskTrackerActivityName.UPDATE_AGENT_TASK_TRACKER)
    async def update_agent_task_tracker(
        self, params: UpdateAgentTaskTrackerParams
    ) -> AgentTaskTracker:
        return await self._agent_task_tracker_service.update_agent_task_tracker(
            tracker_id=params.tracker_id,
            last_processed_event_id=params.last_processed_event_id,
            status=params.status,
            status_reason=params.status_reason,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
