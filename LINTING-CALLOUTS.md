# Linting Callouts and Remaining Issues

## Summary
**Progress**: Fixed ~220 out of 335 linting issues (66% improvement) with additional inline ignores for obvious cases.

**Fixed Issues**: Import sorting, exception handling, obvious unused parameters, core library logging
**Remaining**: Mostly tutorial files, complex workflow interfaces, and test patterns

## Remaining Issues Analysis & Suggestions

### 1. Tutorial Print Statements (T201) - ~65 issues
**Files**: All tutorial `dev.ipynb` files and some project files
**Suggestion**: Consider these approaches:
- **Option A**: Add `# noqa: T201` to tutorial print statements (keeps educational value)
- **Option B**: Replace with `logger.info()` calls (promotes best practices)
- **Option C**: Disable T201 for tutorial directories in pyproject.toml

**Recommendation**: Option A - tutorials should demonstrate actual usage patterns users expect.

### 2. Temporal Workflow/Activity Arguments (ARG001/ARG002) - ~25 issues
**Files**:
- `examples/tutorials/10_agentic/10_temporal/*/project/workflow.py`
- `examples/tutorials/10_agentic/00_base/090_multi_agent_non_temporal/project/state_machines/content_workflow.py`

**Issues**:
- `context` parameters required by Temporal framework but not used in simple examples
- `ctx`, `agent` parameters in workflow signal handlers
- `state_machine`, `state_machine_data` parameters in state machine handlers

**Suggestions**:
- Add `# noqa: ARG001` to temporal interface methods that need unused context
- Consider using `_context` naming for clearly unused framework parameters
- For state machine: May indicate over-parameterized interface design

### 3. Test-Related Arguments (ARG001/ARG002/ARG005) - ~15 issues
**Files**:
- `tests/test_function_tool.py`
- `tests/test_header_forwarding.py`
- Various test helper functions

**Suggestion**: Add `# noqa: ARG001` for test fixtures and mock function parameters that are required by test framework patterns.

### 4. Development/Debug Tools (T201) - ~10 issues
**Files**:
- `src/agentex/lib/sdk/fastacp/tests/run_tests.py`
- `src/agentex/lib/utils/dev_tools/async_messages.py`

**Suggestion**: These are intentionally using print() for direct user output in CLI tools. Add `# noqa: T201` or exclude these directories from T201 checks.

### 5. Provider/Service Arguments - ~8 issues
**Files**:
- `src/agentex/lib/core/services/adk/providers/openai.py`
- `src/agentex/lib/core/temporal/workers/worker.py`

**Suggestion**: These appear to be interface consistency parameters or future extension points. Add `# noqa: ARG002` with comments explaining the purpose.

## Recommended Actions

### Quick Wins (can be automated):
```bash
# Add noqa comments to tutorial notebooks (if keeping print statements)
find examples/tutorials -name "*.py" -o -name "*.ipynb" | xargs sed -i 's/print(/print(  # noqa: T201/g'

# Add noqa to test fixtures
grep -r "def.*context.*:" tests/ | # add # noqa: ARG001 to test helper functions
```

### Configuration Option:
Add to `pyproject.toml`:
```toml
[tool.ruff]
per-file-ignores = {
    "examples/tutorials/**" = ["T201"],  # Allow prints in tutorials
    "tests/**" = ["ARG001", "ARG002"],   # Allow unused test params
    "**/run_tests.py" = ["T201"],        # Allow prints in test runners
    "**/dev_tools/**" = ["T201"],        # Allow prints in dev tools
}
```

### Complex Cases Needing Review:
1. **State Machine Interface**: 8 unused parameters suggest possible over-parameterization
2. **OpenAI Provider**: `previous_response_id` parameter - verify if this is used elsewhere or future feature
3. **Worker Lambda**: Request parameter in worker registration - may be temporal framework requirement

## Current Status
- **Easy fixes applied**: Import sorting, exception handling, obvious unused parameters
- **Inline ignores added**: Deprecated functions, framework callbacks, configuration parameters
- **Remaining**: ~115 issues, mostly in tutorials and test patterns that can be bulk-ignored or are legitimate design choices