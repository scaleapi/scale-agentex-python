#!/bin/bash
#
# Run a single agent tutorial test
#
# This script runs the test for a single agent tutorial.
# It starts the agent, runs tests against it, then stops the agent.
#
# Usage:
#   ./run_agent_test.sh <tutorial_path>                     # Run single tutorial test
#   ./run_agent_test.sh --build-cli <tutorial_path>         # Build CLI from source and run test
#   ./run_agent_test.sh --view-logs <tutorial_path>         # View logs for specific tutorial
#   ./run_agent_test.sh --view-logs                         # View most recent agent logs
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
TUTORIAL_PATH=""
VIEW_LOGS=false
BUILD_CLI=false

for arg in "$@"; do
    if [[ "$arg" == "--view-logs" ]]; then
        VIEW_LOGS=true
    elif [[ "$arg" == "--build-cli" ]]; then
        BUILD_CLI=true
    else
        TUTORIAL_PATH="$arg"
    fi
done

# Function to check prerequisites for running this test suite
check_prerequisites() {
    # Check that we are in the examples/tutorials directory
    if [[ "$PWD" != */examples/tutorials ]]; then
        echo -e "${RED}❌ Please run this script from the examples/tutorials directory${NC}"
        exit 1
    fi

    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ uv is required but not installed${NC}"
        echo "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Function to wait for agent to be ready
wait_for_agent_ready() {
    local name=$1
    local logfile="/tmp/agentex-${name}.log"
    local timeout=45  # seconds - increased to account for package installation time
    local elapsed=0

    echo -e "${YELLOW}⏳ Waiting for ${name} agent to be ready...${NC}"

    while [ $elapsed -lt $timeout ]; do
        # Check if agent is successfully registered
        if grep -q "Successfully registered agent" "$logfile" 2>/dev/null; then

            # For temporal agents, also wait for workers to be ready
            if [[ "$tutorial_path" == *"temporal"* ]]; then
                # This is a temporal agent - wait for workers too
                if grep -q "Running workers for task queue" "$logfile" 2>/dev/null; then
                    return 0
                fi
            else
                return 0
            fi
        fi
        sleep 1
        ((elapsed++))
    done

    echo -e "${RED}❌ Timeout waiting for ${name} agent to be ready${NC}"
    echo -e "${YELLOW}📋 Agent logs:${NC}"
    if [[ -f "$logfile" ]]; then
        echo "----------------------------------------"
        tail -50 "$logfile"
        echo "----------------------------------------"
    else
        echo "❌ Log file not found: $logfile"
    fi
    return 1
}

# Function to start agent in background
start_agent() {
    local tutorial_path=$1
    local name=$(basename "$tutorial_path")
    local logfile="/tmp/agentex-${name}.log"

    echo -e "${YELLOW}🚀 Starting ${name} agent...${NC}"

    # Check if tutorial directory exists
    if [[ ! -d "$tutorial_path" ]]; then
        echo -e "${RED}❌ Tutorial directory not found: $tutorial_path${NC}"
        return 1
    fi

    # Check if manifest exists
    if [[ ! -f "$tutorial_path/manifest.yaml" ]]; then
        echo -e "${RED}❌ Manifest not found: $tutorial_path/manifest.yaml${NC}"
        return 1
    fi

    # Save current directory
    local original_dir="$PWD"

    # Change to tutorial directory
    cd "$tutorial_path" || return 1

    # Start the agent in background and capture PID
    local manifest_path="$PWD/manifest.yaml"  # Always use full path

    if [ "$BUILD_CLI" = true ]; then

        # Use wheel from dist directory at repo root
        local wheel_file=$(ls /home/runner/work/*/*/dist/agentex_sdk-*.whl 2>/dev/null | head -n1)
        if [[ -z "$wheel_file" ]]; then
            echo -e "${RED}❌ No built wheel found in dist/agentex_sdk-*.whl${NC}"
            echo -e "${YELLOW}💡 Please build the local SDK first by running: uv build${NC}"
            echo -e "${YELLOW}💡 From the repo root directory${NC}"
            cd "$original_dir"
            return 1
        fi

        # Use the built wheel
        uv run --with "$wheel_file" agentex agents run --manifest "$manifest_path" > "$logfile" 2>&1 &
    else
        uv run agentex agents run --manifest manifest.yaml > "$logfile" 2>&1 &
    fi
    local pid=$!

    # Return to original directory
    cd "$original_dir"

    echo "$pid" > "/tmp/agentex-${name}.pid"
    echo -e "${GREEN}✅ ${name} agent started (PID: $pid, logs: $logfile)${NC}"

    # Wait for agent to be ready
    if ! wait_for_agent_ready "$name"; then
        kill -9 $pid 2>/dev/null
        return 1
    fi

    return 0
}

# Helper function to view agent container logs
view_agent_logs() {
    local tutorial_path=$1

    # If tutorial path is provided, view logs for that specific tutorial
    if [[ -n "$tutorial_path" ]]; then
        local name=$(basename "$tutorial_path")
        local logfile="/tmp/agentex-${name}.log"

        echo -e "${YELLOW}📋 Viewing logs for ${name}...${NC}"
        echo -e "${YELLOW}Log file: $logfile${NC}"
        echo ""

        if [[ ! -f "$logfile" ]]; then
            echo -e "${RED}❌ Log file not found: $logfile${NC}"
            return 1
        fi

        # Display the logs
        tail -f "$logfile"
    else
        # No specific tutorial, find the most recent log file
        local latest_log=$(ls -t /tmp/agentex-*.log 2>/dev/null | head -1)

        if [[ -z "$latest_log" ]]; then
            echo -e "${RED}❌ No agent log files found in /tmp/agentex-*.log${NC}"
            echo -e "${YELLOW}Available log files:${NC}"
            ls -lht /tmp/agentex-*.log 2>/dev/null || echo "  (none)"
            return 1
        fi

        echo -e "${YELLOW}📋 Viewing most recent agent logs...${NC}"
        echo -e "${YELLOW}Log file: $latest_log${NC}"
        echo ""

        # Display the logs
        tail -f "$latest_log"
    fi
}

# Function to stop agent
stop_agent() {
    local tutorial_path=$1
    local name=$(basename "$tutorial_path")
    local pidfile="/tmp/agentex-${name}.pid"
    local logfile="/tmp/agentex-${name}.log"

    echo -e "${YELLOW}🛑 Stopping ${name} agent...${NC}"

    # Check if PID file exists
    if [[ ! -f "$pidfile" ]]; then
        echo -e "${YELLOW}⚠️  No PID file found for ${name} agent${NC}"
        return 0
    fi

    # Read PID from file
    local pid=$(cat "$pidfile")

    # Check if process is running and kill it
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}Stopping ${name} agent (PID: $pid)${NC}"
        kill "$pid" 2>/dev/null || true
        rm -f "$pidfile"
    else
        echo -e "${YELLOW}⚠️  ${name} agent was not running${NC}"
        rm -f "$pidfile"
    fi

    echo -e "${GREEN}✅ ${name} agent stopped${NC}"
    echo -e "${YELLOW}Logs available at: $logfile${NC}"

    return 0
}


# Function to run test for a tutorial
run_test() {
    local tutorial_path=$1
    local name=$(basename "$tutorial_path")

    echo -e "${YELLOW}🧪 Running tests for ${name}...${NC}"

    # Check if tutorial directory exists
    if [[ ! -d "$tutorial_path" ]]; then
        echo -e "${RED}❌ Tutorial directory not found: $tutorial_path${NC}"
        return 1
    fi

    # Check if test file exists
    if [[ ! -f "$tutorial_path/tests/test_agent.py" ]]; then
        echo -e "${RED}❌ Test file not found: $tutorial_path/tests/test_agent.py${NC}"
        return 1
    fi

    # Save current directory
    local original_dir="$PWD"

    # Change to tutorial directory
    cd "$tutorial_path" || return 1


    # Run the tests with retry mechanism
    local max_retries=5
    local retry_count=0
    local exit_code=1

    while [ $retry_count -lt $max_retries ]; do
        if [ $retry_count -gt 0 ]; then
            echo -e "${YELLOW}🔄 Retrying tests (attempt $((retry_count + 1))/$max_retries)...${NC}"
        fi

        # Stream pytest output directly in real-time
        uv run pytest tests/test_agent.py -v -s
        exit_code=$?

        if [ $exit_code -eq 0 ]; then
            break
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                sleep 5
            fi
        fi
    done

    # Return to original directory
    cd "$original_dir"

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Tests passed for ${name}${NC}"
        return 0
    else
        echo -e "${RED}❌ Tests failed for ${name}${NC}"
        return 1
    fi
}

# Function to execute test flow for a single tutorial
execute_tutorial_test() {
    local tutorial=$1

    echo ""
    echo "================================================================================"
    echo "Testing: $tutorial"
    echo "================================================================================"

    # Start the agent
    if ! start_agent "$tutorial"; then
        echo -e "${RED}❌ FAILED to start agent: $tutorial${NC}"
        return 1
    fi

    # Run the tests
    local test_passed=false
    if run_test "$tutorial"; then
        echo -e "${GREEN}✅ PASSED: $tutorial${NC}"
        test_passed=true
    else
        echo -e "${RED}❌ FAILED: $tutorial${NC}"
    fi

    # Stop the agent
    stop_agent "$tutorial"

    echo ""

    if [ "$test_passed" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to check if built wheel is available
check_built_wheel() {

    # Navigate to the repo root (two levels up from examples/tutorials)
    local repo_root="../../"
    local original_dir="$PWD"

    cd "$repo_root" || {
        echo -e "${RED}❌ Failed to navigate to repo root${NC}"
        return 1
    }

    # Check if wheel exists in dist directory at repo root
    local wheel_file=$(ls /home/runner/work/*/*/dist/agentex_sdk-*.whl 2>/dev/null | head -n1)
    if [[ -z "$wheel_file" ]]; then
        echo -e "${RED}❌ No built wheel found in dist/agentex_sdk-*.whl${NC}"
        echo -e "${YELLOW}💡 Please build the local SDK first by running: uv build${NC}"
        echo -e "${YELLOW}💡 From the repo root directory${NC}"
        cd "$original_dir"
        return 1
    fi

    # Test the wheel by running agentex --help
    if ! uv run --with "$wheel_file" agentex --help >/dev/null 2>&1; then
        echo -e "${RED}❌ Failed to run agentex with built wheel${NC}"
        cd "$original_dir"
        return 1
    fi
    cd "$original_dir"
    return 0
}


# Main execution function
main() {
    # Handle --view-logs flag
    if [ "$VIEW_LOGS" = true ]; then
        if [[ -n "$TUTORIAL_PATH" ]]; then
            view_agent_logs "$TUTORIAL_PATH"
        else
            view_agent_logs
        fi
        exit 0
    fi
        # Require tutorial path
    if [[ -z "$TUTORIAL_PATH" ]]; then
        echo -e "${RED}❌ Error: Tutorial path is required${NC}"
        echo ""
        echo "Usage:"
        echo "  ./run_agent_test.sh <tutorial_path>                     # Run single tutorial test"
        echo "  ./run_agent_test.sh --build-cli <tutorial_path>         # Build CLI from source and run test"
        echo "  ./run_agent_test.sh --view-logs <tutorial_path>         # View logs for specific tutorial"
        echo "  ./run_agent_test.sh --view-logs                         # View most recent agent logs"
        echo ""
        echo "Examples:"
        echo "  ./run_agent_test.sh 00_sync/000_hello_acp"
        echo "  ./run_agent_test.sh --build-cli 00_sync/000_hello_acp"
        exit 1
    fi

    echo "================================================================================"
    echo "Running Tutorial Test: $TUTORIAL_PATH"
    echo "================================================================================"

    # Check prerequisites
    check_prerequisites

    echo ""

    # Check built wheel if requested
    if [ "$BUILD_CLI" = true ]; then
        if ! check_built_wheel; then
            echo -e "${RED}❌ Failed to find or verify built wheel${NC}"
            exit 1
        fi
        echo ""
    fi

    # Execute the single tutorial test
    if execute_tutorial_test "$TUTORIAL_PATH"; then
        echo ""
        echo "================================================================================"
        echo -e "${GREEN}🎉 Test passed for: $TUTORIAL_PATH${NC}"
        echo "================================================================================"
        exit 0
    else
        echo ""
        echo "================================================================================"
        echo -e "${RED}❌ Test failed for: $TUTORIAL_PATH${NC}"
        echo "================================================================================"
        exit 1
    fi
}

# Run main function
main
