# Linting Callouts and Remaining Issues

## Summary
Fixed 213 out of 335 linting issues (63% improvement). Remaining 122 issues are mostly in tutorial files and specific edge cases.

## Questions/Decisions Needed

### 1. Tutorial Print Statements (T201)
**Status**: Left as-is
**Issue**: Many tutorial notebooks and example files contain `print()` statements
**Question**: Should tutorial `print()` statements be left for educational purposes, or converted to logger calls?
**Files**: All tutorial dev.ipynb files, tutorial project files

### 2. Unused Arguments in Workflow/Activity Functions (ARG001/ARG002)
**Status**: Partially fixed
**Issue**: Many temporal workflow and activity functions have unused `context` parameters that are required by the framework
**Question**: Should these be prefixed with underscore or left as-is since they're part of the temporal interface?
**Files**:
- `examples/tutorials/10_agentic/10_temporal/*/project/workflow.py`
- Various activity and handler functions

### 3. Test File Print Statements
**Status**: Left as-is
**Issue**: Test runner and dev tools intentionally use print for user output
**Files**:
- `src/agentex/lib/sdk/fastacp/tests/run_tests.py`
- `src/agentex/lib/utils/dev_tools/async_messages.py`

### 4. Debug Template Import Error Setup
**Status**: Left error print statements
**Issue**: Debug setup in templates still uses print() for error cases (ImportError, Exception)
**Question**: Should error messages stay as print() to ensure they're visible even if logging isn't set up?

## Remaining Issues by Category

### Print Statements (T201) - 85 issues
- **Tutorial notebooks**: 67 issues across example/tutorial dev.ipynb files
- **Test/Dev tools**: 15 issues in test runners and dev utilities
- **Template error handling**: 3 issues in Jinja template error cases

### Unused Arguments (ARG*) - 36 issues
- **Temporal workflows**: Required by framework but unused
- **Test fixtures**: Standard pytest/test patterns
- **CLI init functions**: Legacy parameters
- **Lambda functions**: Anonymous function parameters

### Import Issues (I001, F401, TC004) - 1 issue
- **Type checking import**: One import used outside type checking block

## Fixed Issues (213 total)
- ✅ Import sorting (I001): 190+ issues
- ✅ Unused imports (F401): Multiple files
- ✅ Exception handling (B904): Added proper exception chaining
- ✅ Return in finally (B012): Restructured exception handling
- ✅ Bare except (E722): Specified Exception type
- ✅ Blind exception assert (B017): Specified exact exception types
- ✅ Core library print statements: Converted to logger calls
- ✅ Template print statements: Fixed debug logging in Jinja templates

## Recommendations for PR Discussion

1. **Tutorial Policy**: Establish whether tutorials should use print() or logger
2. **Framework Interface**: Decide on unused parameter naming for temporal/framework interfaces
3. **Test Output**: Confirm test runners should keep print() for user visibility
4. **Error Handling**: Review if debug setup errors should remain as print() statements

## Files with Significant Remaining Issues
- Tutorial notebooks: All dev.ipynb files (print statements)
- `examples/tutorials/10_agentic/00_base/090_multi_agent_non_temporal/project/state_machines/content_workflow.py` (8 unused arguments)
- `examples/tutorials/10_agentic/10_temporal/050_agent_chat_guardrails/project/workflow.py` (10 unused arguments)
- Various test files (unused test fixture parameters)