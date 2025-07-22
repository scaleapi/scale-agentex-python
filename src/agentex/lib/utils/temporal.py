from temporalio import activity, workflow


def in_temporal_workflow():
    try:
        return workflow.in_workflow()
    except RuntimeError:
        return False


def heartbeat_if_in_workflow(heartbeat_name: str):
    if in_temporal_workflow():
        activity.heartbeat(heartbeat_name)
