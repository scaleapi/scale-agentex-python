#!/bin/bash
#
# Run all agentic tutorial tests
#
# This script runs the test runner for all agentic tutorials in sequence.
# It stops at the first failure unless --continue-on-error is specified.
#
# Usage:
#   ./run_all_agentic_tests.sh                              # Run all tutorials
#   ./run_all_agentic_tests.sh --continue-on-error          # Run all, continue on error
#   ./run_all_agentic_tests.sh <tutorial_path>              # Run single tutorial
#   ./run_all_agentic_tests.sh --view-logs                  # View most recent agent logs
#   ./run_all_agentic_tests.sh --view-logs <tutorial_path>  # View logs for specific tutorial
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

AGENT_PORT=8000
AGENTEX_SERVER_PORT=5003

# Parse arguments
CONTINUE_ON_ERROR=false
SINGLE_TUTORIAL=""
VIEW_LOGS=false

for arg in "$@"; do
    if [[ "$arg" == "--continue-on-error" ]]; then
        CONTINUE_ON_ERROR=true
    elif [[ "$arg" == "--view-logs" ]]; then
        VIEW_LOGS=true
    else
        SINGLE_TUTORIAL="$arg"
    fi
done

# Find all agentic tutorial directories
ALL_TUTORIALS=(
    # sync tutorials
    "00_sync/000_hello_acp"
    "00_sync/010_multiturn"
    "00_sync/020_streaming"
    # base tutorials
    "10_agentic/00_base/000_hello_acp"
    "10_agentic/00_base/010_multiturn"
    "10_agentic/00_base/020_streaming"
    "10_agentic/00_base/030_tracing"
    "10_agentic/00_base/040_other_sdks"
    "10_agentic/00_base/080_batch_events"
#    "10_agentic/00_base/090_multi_agent_non_temporal" This will require its own version of this
    # temporal tutorials
    "10_agentic/10_temporal/000_hello_acp"
    "10_agentic/10_temporal/010_agent_chat"
    "10_agentic/10_temporal/020_state_machine"
)

PASSED=0
FAILED=0
FAILED_TESTS=()

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
    local timeout=30  # seconds
    local elapsed=0

    echo -e "${YELLOW}⏳ Waiting for ${name} agent to be ready...${NC}"

    while [ $elapsed -lt $timeout ]; do
        if grep -q "Application startup complete" "$logfile" 2>/dev/null || \
           grep -q "Running workers for task queue" "$logfile" 2>/dev/null; then
            echo -e "${GREEN}✅ ${name} agent is ready${NC}"
            return 0
        fi
        sleep 1
        ((elapsed++))
    done

    echo -e "${RED}❌ Timeout waiting for ${name} agent to be ready${NC}"
    echo "Check logs: tail -f $logfile"
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
    uv run agentex agents run --manifest manifest.yaml > "$logfile" 2>&1 &
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

    # Run the tests
    uv run pytest tests/test_agent.py -v -s
    local exit_code=$?

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
    echo "--------------------------------------------------------------------------------"
    echo "Testing: $tutorial"
    echo "--------------------------------------------------------------------------------"

    # Start the agent
    if ! start_agent "$tutorial"; then
        echo -e "${RED}❌ FAILED to start agent: $tutorial${NC}"
        ((FAILED++))
        FAILED_TESTS+=("$tutorial")
        return 1
    fi

    # Run the tests
    local test_passed=false
    if run_test "$tutorial"; then
        echo -e "${GREEN}✅ PASSED: $tutorial${NC}"
        ((PASSED++))
        test_passed=true
    else
        echo -e "${RED}❌ FAILED: $tutorial${NC}"
        ((FAILED++))
        FAILED_TESTS+=("$tutorial")
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

# Main execution function
main() {
    # Handle --view-logs flag
    if [ "$VIEW_LOGS" = true ]; then
        if [[ -n "$SINGLE_TUTORIAL" ]]; then
            view_agent_logs "$SINGLE_TUTORIAL"
        else
            view_agent_logs
        fi
        exit 0
    fi

    echo "================================================================================"
    if [[ -n "$SINGLE_TUTORIAL" ]]; then
        echo "Running Single Tutorial Test: $SINGLE_TUTORIAL"
    else
        echo "Running All Agentic Tutorial Tests"
        if [ "$CONTINUE_ON_ERROR" = true ]; then
            echo -e "${YELLOW}⚠️  Running in continue-on-error mode${NC}"
        fi
    fi
    echo "================================================================================"
    echo ""

    # Check prerequisites
    check_prerequisites

    echo ""

    # Determine which tutorials to run
    if [[ -n "$SINGLE_TUTORIAL" ]]; then
        TUTORIALS=("$SINGLE_TUTORIAL")
    else
        TUTORIALS=("${ALL_TUTORIALS[@]}")
    fi

    # Iterate over tutorials
    for tutorial in "${TUTORIALS[@]}"; do
        execute_tutorial_test "$tutorial"

        # Exit early if in fail-fast mode
        if [ "$CONTINUE_ON_ERROR" = false ] && [ $FAILED -gt 0 ]; then
            echo ""
            echo -e "${RED}Stopping due to test failure. Use --continue-on-error to continue.${NC}"
            exit 1
        fi
    done

    # Print summary
    echo ""
    echo "================================================================================"
    echo "Test Summary"
    echo "================================================================================"
    echo -e "Total:  $((PASSED + FAILED))"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""

    if [ $FAILED -gt 0 ]; then
        echo "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            echo -e "  ${RED}✗${NC} $test"
        done
        echo ""
        exit 1
    else
        echo -e "${GREEN}🎉 All tests passed!${NC}"
        echo ""
        exit 0
    fi
}

# Run main function
main