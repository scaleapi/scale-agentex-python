# Procurement Agent Evals

Integration tests for the procurement agent that verify tool calls and database state.

## Prerequisites

1. AgentEx backend running (`make dev` from scale-agentex)
2. Procurement agent running:
   ```bash
   cd examples/demos/procurement_agent
   export ENVIRONMENT=development
   uv run agentex agents run --manifest manifest.yaml
   ```

## Running Tests

From the `procurement_agent` directory:

```bash
# Run all tests
cd evals && uv run pytest

# Run specific test file
cd evals && uv run pytest tasks/test_shipment_departed.py -v

# Run single test
cd evals && uv run pytest tasks/test_shipment_departed.py::test_departed_01_no_flag_5_days_early -v
```

## Test Structure

| File | Event Type | Focus |
|------|------------|-------|
| `test_submittal_approved.py` | Submittal_Approved | PO issued, DB entry |
| `test_shipment_departed.py` | Shipment_Departed | **False positive detection** |
| `test_shipment_arrived.py` | Shipment_Arrived | Team notification, inspection |
| `test_inspection_failed.py` | Inspection_Failed | Human-in-the-loop |
| `test_inspection_passed.py` | Inspection_Passed | Status update |

## Test Cases Summary

| Event | Tests | Key Assertions |
|-------|-------|----------------|
| Submittal_Approved | 2 | `issue_purchase_order` called, DB item created |
| Shipment_Departed | 6 | Forbidden: `flag_potential_issue` when ETA < required_by |
| Shipment_Arrived | 2 | `notify_team`, `schedule_inspection` called |
| Inspection_Failed | 3 | Human-in-loop: approve, approve+extra, reject+delete |
| Inspection_Passed | 2 | Forbidden: `wait_for_human`, `flag_potential_issue` |

## Graders

- **tool_calls.py**: Verifies required and forbidden tool calls in transcripts
- **database.py**: Verifies database state changes

## False Positive Detection

The `test_shipment_departed.py` tests are specifically designed to catch the false positive issue where the agent incorrectly flags conflicts.

**Conflict logic:**
- **Flag if** ETA >= required_by (zero/negative buffer)
- **Don't flag if** ETA < required_by (has buffer remaining)

The tests use `assert_forbidden_tools(["flag_potential_issue"])` to catch cases where the agent incorrectly escalates.
