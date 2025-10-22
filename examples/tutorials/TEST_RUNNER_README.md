# Tutorial Test Runner

This directory contains a test runner script that automates the process of starting an agent and running its tests.

## Prerequisites

- Python 3.12+
- `uv` installed and available in PATH
- `httpx` Python package (for health checks)

## Usage

From the `tutorials/` directory, run:

```bash
python run_tutorial_test.py <tutorial_directory>
```

### Examples

```bash
# Test a sync tutorial
python run_tutorial_test.py 00_sync/000_hello_acp

# Test an agentic tutorial
python run_tutorial_test.py 10_agentic/00_base/000_hello_acp
python run_tutorial_test.py 10_agentic/00_base/010_multiturn
python run_tutorial_test.py 10_agentic/00_base/020_streaming

# Test with custom base URL
python run_tutorial_test.py 10_agentic/00_base/000_hello_acp --base-url http://localhost:5003
```

## What the Script Does

1. **Validates Paths**: Checks that the tutorial directory, manifest.yaml, and tests directory exist
2. **Starts Agent**: Runs `uv run agentex agents run --manifest manifest.yaml` in the tutorial directory
3. **Health Check**: Polls the agent's health endpoint (default: http://localhost:5003/health) until it's live
4. **Runs Tests**: Executes `uv run pytest tests/ -v --tb=short` in the tutorial directory
5. **Cleanup**: Gracefully stops the agent process (or kills it if necessary)

## Options

```
positional arguments:
  tutorial_dir          Path to the tutorial directory (relative to current directory)

optional arguments:
  -h, --help            Show help message and exit
  --base-url BASE_URL   Base URL for the AgentEx server (default: http://localhost:5003)
```

## Exit Codes

- `0`: All tests passed successfully
- `1`: Tests failed or error occurred
- `130`: Interrupted by user (Ctrl+C)

## Example Output

```
================================================================================
AgentEx Tutorial Test Runner
================================================================================

🚀 Starting agent from: 10_agentic/00_base/000_hello_acp
📄 Manifest: 10_agentic/00_base/000_hello_acp/manifest.yaml
💻 Running command: uv run agentex agents run --manifest manifest.yaml
📁 Working directory: 10_agentic/00_base/000_hello_acp
✅ Agent process started (PID: 12345)

🔍 Checking agent health at http://localhost:5003/health...
⏳ Waiting for agent... (attempt 1/30)
⏳ Waiting for agent... (attempt 2/30)
✅ Agent is live! (attempt 3/30)

⏳ Waiting 2 seconds for agent to fully initialize...

🧪 Running tests from: 10_agentic/00_base/000_hello_acp/tests
💻 Running command: uv run pytest tests/ -v --tb=short
📁 Working directory: 10_agentic/00_base/000_hello_acp

============================= test session starts ==============================
...
============================= X passed in Y.YYs ================================

✅ All tests passed!

🛑 Stopping agent (PID: 12345)...
✅ Agent stopped gracefully

================================================================================
✅ Test run completed successfully!
================================================================================
```

## Troubleshooting

### Agent doesn't become live

If the health check times out:
- Check that port 5003 is not already in use
- Look at the agent logs to see if there are startup errors
- Try increasing the timeout by modifying the `max_attempts` parameter in the script

### Tests fail

- Ensure the agent is properly configured in manifest.yaml
- Check that all dependencies are installed in the tutorial's virtual environment
- Review test output for specific failure reasons

### "uv: command not found"

Install `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Missing httpx package

The script requires `httpx` for health checks. It should be installed automatically via the tutorial's dependencies, but if needed:
```bash
pip install httpx
```

## Integration with CI/CD

This script is designed to be CI/CD friendly:

```bash
# Run all agentic tutorials
for tutorial in 10_agentic/00_base/*/; do
  python run_tutorial_test.py "$tutorial" || exit 1
done
```

## Notes

- The script automatically sets `AGENTEX_API_BASE_URL` environment variable when running tests
- Agent processes are always cleaned up, even if tests fail or the script is interrupted
- The script uses line-buffered output for real-time feedback
- Health checks poll every 1 second for up to 30 seconds (configurable in the code)
