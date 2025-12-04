from pydantic import BaseModel


class StateModel(BaseModel):
    num_batches_processed: int = 0
    num_batches_failed: int = 0
    total_events_processed: int = 0
    total_events_dropped: int = 0
    total_events_enqueued: int = 0


class IncomingEventData(BaseModel):
    clear_queue: bool = False
    cancel_running_tasks: bool = False