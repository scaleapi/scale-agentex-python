#!/bin/bash
# Multi-Agent Content Assembly Line - Start All Agents (Flattened Structure)
# This script starts all 4 agents in the simplified flattened structure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ORCHESTRATOR_PORT=8718
CREATOR_PORT=8719
CRITIC_PORT=8720
FORMATTER_PORT=8721

# Base directory
BASE_DIR="examples/tutorials/10_async/00_base/090_multi_agent_non_temporal"

echo -e "${BLUE}🎭 Multi-Agent Content Assembly Line (Flattened)${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}❌ Port $port is already in use${NC}"
        echo "Please stop the process using port $port or change the port in the manifest files"
        return 1
    fi
    return 0
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
    
    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]] || [[ ! -d "src/agentex" ]]; then
        echo -e "${RED}❌ Please run this script from the agentex-sdk-python repository root${NC}"
        exit 1
    fi
    
    # Check if flattened directory exists
    if [[ ! -d "$BASE_DIR" ]]; then
        echo -e "${RED}❌ Flattened multi-agent directory not found: $BASE_DIR${NC}"
        exit 1
    fi
    
    # Check if project directory exists
    if [[ ! -d "$BASE_DIR/project" ]]; then
        echo -e "${RED}❌ Project directory not found: $BASE_DIR/project${NC}"
        exit 1
    fi
    
    # Check if manifest files exist
    if [[ ! -f "$BASE_DIR/orchestrator.yaml" ]]; then
        echo -e "${RED}❌ Orchestrator manifest not found: $BASE_DIR/orchestrator.yaml${NC}"
        exit 1
    fi
    
    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ uv is required but not installed${NC}"
        echo "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    # Check if OPENAI_API_KEY is set
    if [[ -z "${OPENAI_API_KEY}" ]]; then
        echo -e "${YELLOW}⚠️  OPENAI_API_KEY not found in environment${NC}"
        if [[ -f ".env" ]]; then
            echo -e "${GREEN}✅ Found .env file - agents will load it automatically${NC}"
        else
            echo -e "${RED}❌ No .env file found and OPENAI_API_KEY not set${NC}"
            echo "Please create a .env file with OPENAI_API_KEY=your_key_here"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ OPENAI_API_KEY found in environment${NC}"
    fi
    
    # Check ports
    echo -e "${YELLOW}🔍 Checking ports...${NC}"
    check_port $ORCHESTRATOR_PORT || exit 1
    check_port $CREATOR_PORT || exit 1
    check_port $CRITIC_PORT || exit 1
    check_port $FORMATTER_PORT || exit 1
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
    echo ""
}

# Function to start agent in background
start_agent() {
    local name=$1
    local manifest=$2
    local port=$3
    local logfile="/tmp/agentex-${name}.log"
    
    echo -e "${YELLOW}🚀 Starting ${name} agent on port ${port}...${NC}"
    
    # Start the agent in background and capture PID
    uv run agentex agents run --manifest "$manifest" > "$logfile" 2>&1 &
    local pid=$!
    
    echo "$pid" > "/tmp/agentex-${name}.pid"
    echo -e "${GREEN}✅ ${name} agent started (PID: $pid, logs: $logfile)${NC}"
    
    # Give it a moment to start
    sleep 2
    
    # Check if process is still running
    if ! kill -0 $pid 2>/dev/null; then
        echo -e "${RED}❌ ${name} agent failed to start${NC}"
        echo "Check logs: tail -f $logfile"
        return 1
    fi
    
    return 0
}

# Function to stop all agents
stop_agents() {
    echo -e "${YELLOW}🛑 Stopping all agents...${NC}"
    
    for agent in orchestrator creator critic formatter; do
        pidfile="/tmp/agentex-${agent}.pid"
        if [[ -f "$pidfile" ]]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${YELLOW}🛑 Stopping ${agent} agent (PID: $pid)${NC}"
                kill "$pid"
                rm -f "$pidfile"
            else
                echo -e "${YELLOW}⚠️  ${agent} agent was not running${NC}"
                rm -f "$pidfile"
            fi
        fi
    done
    
    echo -e "${GREEN}✅ All agents stopped${NC}"
}

# Function to show agent status
show_status() {
    echo -e "${BLUE}📊 Agent Status${NC}"
    echo -e "${BLUE}==============${NC}"
    
    for agent in orchestrator creator critic formatter; do
        pidfile="/tmp/agentex-${agent}.pid"
        if [[ -f "$pidfile" ]]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                case $agent in
                    orchestrator) port=$ORCHESTRATOR_PORT ;;
                    creator) port=$CREATOR_PORT ;;
                    critic) port=$CRITIC_PORT ;;
                    formatter) port=$FORMATTER_PORT ;;
                esac
                echo -e "${GREEN}✅ ${agent} agent running (PID: $pid, Port: $port)${NC}"
            else
                echo -e "${RED}❌ ${agent} agent not running (stale PID file)${NC}"
                rm -f "$pidfile"
            fi
        else
            echo -e "${RED}❌ ${agent} agent not running${NC}"
        fi
    done
}

# Function to show logs
show_logs() {
    local agent=${1:-"all"}
    
    if [[ "$agent" == "all" ]]; then
        echo -e "${BLUE}📝 Showing logs for all agents (press Ctrl+C to stop)${NC}"
        tail -f /tmp/agentex-*.log 2>/dev/null || echo "No log files found"
    else
        local logfile="/tmp/agentex-${agent}.log"
        if [[ -f "$logfile" ]]; then
            echo -e "${BLUE}📝 Showing logs for ${agent} agent (press Ctrl+C to stop)${NC}"
            tail -f "$logfile"
        else
            echo -e "${RED}❌ Log file not found: $logfile${NC}"
        fi
    fi
}

# Function to test agent connectivity
test_system() {
    echo -e "${BLUE}🧪 Testing agent connectivity${NC}"
    echo -e "${BLUE}=============================${NC}"
    
    # Check if agents are responding on their ports
    echo -e "${YELLOW}🔍 Testing agent connectivity...${NC}"
    
    ports=(8718 8719 8720 8721)
    agents=("orchestrator" "creator" "critic" "formatter")
    all_responding=true
    
    for i in "${!ports[@]}"; do
        port=${ports[$i]}
        agent=${agents[$i]}
        if nc -z localhost $port 2>/dev/null; then
            echo -e "${GREEN}✅ ${agent} agent responding on port $port${NC}"
        else
            echo -e "${RED}❌ ${agent} agent not responding on port $port${NC}"
            all_responding=false
        fi
    done
    
    echo ""
    if $all_responding; then
        echo -e "${GREEN}🎉 All agents are ready and responding!${NC}"
        echo -e "${BLUE}💡 You can now:${NC}"
        echo "   1. Monitor logs: $0 logs"
        echo "   2. Send requests through the AgentEx platform UI"
        echo "   3. Use direct HTTP calls to test individual agents"
        echo ""
        echo -e "${BLUE}🔗 Agent Endpoints:${NC}"
        echo "   • Orchestrator: http://localhost:8718"
        echo "   • Creator: http://localhost:8719"
        echo "   • Critic: http://localhost:8720"
        echo "   • Formatter: http://localhost:8721"
        echo ""
        echo -e "${BLUE}📝 Sample Request (send via AgentEx UI):${NC}"
        echo '{"request": "Write a brief welcome message for our new AI assistant", "rules": ["Under 100 words", "Friendly tone", "Include emoji"], "target_format": "HTML"}'
    else
        echo -e "${RED}❌ Some agents are not responding${NC}"
        echo "Check status: $0 status"
        echo "Check logs: $0 logs"
    fi
}

# Main script logic
case "${1:-start}" in
    "start")
        check_prerequisites
        
        echo -e "${YELLOW}🚀 Starting all agents in flattened structure...${NC}"
        echo ""
        
        # Start all agents using the flattened manifests
        start_agent "orchestrator" "$BASE_DIR/orchestrator.yaml" $ORCHESTRATOR_PORT || exit 1
        start_agent "creator" "$BASE_DIR/creator.yaml" $CREATOR_PORT || exit 1
        start_agent "critic" "$BASE_DIR/critic.yaml" $CRITIC_PORT || exit 1
        start_agent "formatter" "$BASE_DIR/formatter.yaml" $FORMATTER_PORT || exit 1
        
        echo ""
        echo -e "${GREEN}🎉 All agents started successfully!${NC}"
        echo ""
        echo -e "${BLUE}📝 Available commands:${NC}"
        echo "  $0 status    - Show agent status"
        echo "  $0 logs      - Show all agent logs"
        echo "  $0 logs <agent> - Show specific agent logs (orchestrator|creator|critic|formatter)"
        echo "  $0 test      - Test agent connectivity"
        echo "  $0 stop      - Stop all agents"
        echo ""
        echo -e "${BLUE}📤 Agent Endpoints:${NC}"
        echo "  • Orchestrator: http://localhost:8718"
        echo "  • Creator: http://localhost:8719" 
        echo "  • Critic: http://localhost:8720"
        echo "  • Formatter: http://localhost:8721"
        echo ""
        echo -e "${BLUE}💡 To interact with agents:${NC}"
        echo "  1. Use the AgentEx platform to send tasks"
        echo "  2. Send HTTP requests directly to agent endpoints"
        echo "  3. Monitor workflow progress with: $0 logs"
        echo ""
        ;;
        
    "stop")
        stop_agents
        ;;
        
    "status")
        show_status
        ;;
        
    "logs")
        show_logs "$2"
        ;;
        
    "test")
        test_system
        ;;
        
    "help"|"-h"|"--help")
        echo -e "${BLUE}🎭 Multi-Agent Content Assembly Line (Flattened Structure)${NC}"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     Start all agents (default)"
        echo "  stop      Stop all agents"
        echo "  status    Show agent status"
        echo "  logs      Show all agent logs"
        echo "  logs <agent>  Show specific agent logs"
        echo "  test      Test agent connectivity"
        echo "  help      Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 start     # Start all agents"
        echo "  $0 status    # Check if agents are running"
        echo "  $0 logs      # Monitor all logs"
        echo "  $0 logs orchestrator  # Monitor orchestrator logs only"
        echo "  $0 test      # Check agent connectivity"
        echo "  $0 stop      # Stop all agents"
        echo ""
        echo "Architecture Benefits:"
        echo "  • 90% less boilerplate (12 files vs ~40 files)"
        echo "  • Single shared Dockerfile and pyproject.toml"
        echo "  • All agent code in one directory"
        echo "  • Maintains AgentEx CLI compatibility"
        ;;
        
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
