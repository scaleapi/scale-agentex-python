from enum import Enum


class SignalName(str, Enum):
    RECEIVE_EVENT = "receive_event"
    # Dedicated non-terminal "stop the current turn" signal (design doc section 7).
    # Routed to the overridable BaseWorkflow.on_interrupt hook. Kept separate from
    # RECEIVE_EVENT so the interrupt handler can interleave with (and cancel) the
    # in-flight turn WITHOUT waiting on the turn lock the running turn holds.
    INTERRUPT_TURN = "interrupt_turn"
