#!/bin/bash

# AgentEx Tutorial Launcher
# This script helps you easily launch and test all tutorials in the repository
# 
# Usage:
#   ./launch-tutorials.sh           # Show interactive menu
#   ./launch-tutorials.sh 1         # Launch tutorial #1 directly  
#   ./launch-tutorials.sh a         # Launch all tutorials with confirmations
#   ./launch-tutorials.sh c         # Clean up orphaned tutorial processes
#
# Note: Excludes 90_multi_agent_non_temporal (use its own start-agents.sh)

# Simple cleanup function for orphaned processes
cleanup() {
    # Kill any remaining agentex or uvicorn processes from tutorials
    local agentex_pids=$(pgrep -f "agentex agents run.*tutorials" 2>/dev/null || true)
    if [[ -n "$agentex_pids" ]]; then
        echo "$agentex_pids" | xargs kill -TERM 2>/dev/null || true
        sleep 1
        echo "$agentex_pids" | xargs kill -KILL 2>/dev/null || true
    fi
    
    local uvicorn_pids=$(pgrep -f "uvicorn.*project\." 2>/dev/null || true)
    if [[ -n "$uvicorn_pids" ]]; then
        echo "$uvicorn_pids" | xargs kill -TERM 2>/dev/null || true
        sleep 1
        echo "$uvicorn_pids" | xargs kill -KILL 2>/dev/null || true
    fi
}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Tutorial definitions
declare -a TUTORIALS=(
    "tutorials/00_sync/000_hello_acp|Basic Hello ACP (Sync)"
    "tutorials/00_sync/010_multiturn|Multi-turn Chat (Sync)"
    "tutorials/00_sync/020_streaming|Streaming Response (Sync)"
    "tutorials/10_agentic/00_base/000_hello_acp|Basic Hello ACP (Agentic)"
    "tutorials/10_agentic/00_base/010_multiturn|Multi-turn Chat (Agentic)"
    "tutorials/10_agentic/00_base/020_streaming|Streaming Response (Agentic)"
    "tutorials/10_agentic/00_base/030_tracing|Tracing Example (Agentic)"
    "tutorials/10_agentic/00_base/040_other_sdks|Other SDKs Integration (Agentic)"
    "tutorials/10_agentic/00_base/080_batch_events|Batch Events (Agentic)"
    "tutorials/10_agentic/10_temporal/000_hello_acp|Basic Hello ACP (Temporal)"
    "tutorials/10_agentic/10_temporal/010_agent_chat|Agent Chat (Temporal)"
    "tutorials/10_agentic/10_temporal/020_state_machine|State Machine (Temporal)"
)

# Function to print colored output
print_colored() {
    local color=$1
    local message=$2
    # Check if terminal supports colors
    if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
        printf "${color}%s${NC}\n" "$message"
    else
        printf "%s\n" "$message"
    fi
}

# Function to display the menu
show_menu() {
    print_colored $BLUE "╔════════════════════════════════════════════════════════════════╗"
    print_colored $BLUE "║                    AgentEx Tutorial Launcher                  ║"
    print_colored $BLUE "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    print_colored $YELLOW "Available tutorials:"
    echo ""
    
    local index=1
    for tutorial in "${TUTORIALS[@]}"; do
        IFS='|' read -r path description <<< "$tutorial"
        if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
            printf "${GREEN}%2d.${NC} %s\n" $index "$description"
        else
            printf "%2d. %s\n" $index "$description"
        fi
        index=$((index + 1))
    done
    
    echo ""
    print_colored $BLUE "Other options:"
    print_colored $GREEN "  a. Run all tutorials sequentially (with confirmations)"
    print_colored $GREEN "  c. Clean up any orphaned tutorial processes"
    print_colored $GREEN "  q. Quit"
    echo ""
    print_colored $YELLOW "📌 Note: The multi-agent system tutorial (tutorials/10_agentic/90_multi_agent_non_temporal) is excluded"
    print_colored $YELLOW "   as it has a special launch process. Use its own start-agents.sh script."
    echo ""
}

# Function to run a specific tutorial
run_tutorial() {
    local tutorial_index=$1
    local tutorial_info="${TUTORIALS[$((tutorial_index - 1))]}"
    IFS='|' read -r path description <<< "$tutorial_info"
    
    local manifest_path="${path}/manifest.yaml"
    
    print_colored $BLUE "╔════════════════════════════════════════════════════════════════╗"
    printf "║ Running: %-54s ║\n" "$description"
    print_colored $BLUE "╚════════════════════════════════════════════════════════════════╝"
    
    if [[ ! -f "$manifest_path" ]]; then
        print_colored $RED "❌ Error: Manifest file not found at $manifest_path"
        return 1
    fi
    
    print_colored $YELLOW "📂 Tutorial path: $path"
    print_colored $YELLOW "📄 Manifest: $manifest_path"
    echo ""
    print_colored $GREEN "🚀 Executing: cd .. && uv run agentex agents run --manifest examples/$manifest_path"
    print_colored $YELLOW "💡 Press Ctrl+C to stop the tutorial"
    echo ""
    
    # Run the tutorial directly (need to go to parent dir where uv project is)
    (cd .. && uv run agentex agents run --manifest "examples/$manifest_path")
    
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        print_colored $GREEN "✅ Tutorial completed successfully!"
    elif [[ $exit_code -eq 130 ]]; then
        print_colored $YELLOW "🛑 Tutorial was interrupted by user"
    else
        print_colored $RED "❌ Tutorial failed with exit code: $exit_code"
    fi
    
    return $exit_code
}

# Function to run all tutorials
run_all_tutorials() {
    print_colored $BLUE "🎯 Running all tutorials sequentially..."
    echo ""
    
    local success_count=0
    local total_count=${#TUTORIALS[@]}
    
    for i in $(seq 1 $total_count); do
        local tutorial_info="${TUTORIALS[$((i - 1))]}"
        IFS='|' read -r path description <<< "$tutorial_info"
        
        print_colored $YELLOW "┌─ Tutorial $i/$total_count: $description"
        echo ""
        
        # Ask for confirmation
        while true; do
            print_colored $BLUE "Run this tutorial? (y/n/q to quit): "
            read -r response
            case $response in
                [Yy]* ) 
                    if run_tutorial $i; then
                        success_count=$((success_count + 1))
                    fi
                    break
                    ;;
                [Nn]* ) 
                    print_colored $YELLOW "⏭️  Skipping tutorial $i"
                    break
                    ;;
                [Qq]* ) 
                    print_colored $YELLOW "🛑 Stopping tutorial run"
                    echo ""
                    print_colored $BLUE "📊 Summary: $success_count/$((i-1)) tutorials completed successfully"
                    return 0
                    ;;
                * ) 
                    print_colored $RED "Please answer y, n, or q."
                    ;;
            esac
        done
        
        if [[ $i -lt $total_count ]]; then
            echo ""
            print_colored $BLUE "────────────────────────────────────────────────────────────────"
            echo ""
        fi
    done
    
    echo ""
    print_colored $BLUE "🎉 All tutorials completed!"
    print_colored $BLUE "📊 Summary: $success_count/$total_count tutorials completed successfully"
}

# Function to manually clean up tutorial processes
manual_cleanup() {
    print_colored $BLUE "🧹 Manual cleanup of tutorial processes..."
    echo ""
    
    # Check for running tutorial processes
    local found_processes=false
    
    # Check for agentex processes
    local agentex_pids=$(pgrep -f "agentex agents run.*tutorials" 2>/dev/null || true)
    if [[ -n "$agentex_pids" ]]; then
        found_processes=true
        print_colored $YELLOW "🔍 Found agentex tutorial processes:"
        ps -p $agentex_pids -o pid,command 2>/dev/null || true
        echo ""
    fi
    
    # Check for uvicorn processes
    local uvicorn_pids=$(pgrep -f "uvicorn.*project\." 2>/dev/null || true)
    if [[ -n "$uvicorn_pids" ]]; then
        found_processes=true
        print_colored $YELLOW "🔍 Found uvicorn tutorial processes:"
        ps -p $uvicorn_pids -o pid,command 2>/dev/null || true
        echo ""
    fi
    
    # Check for occupied ports
    print_colored $YELLOW "🔍 Checking common tutorial ports (8000-8003)..."
    local port_check=$(lsof -i :8000 -i :8001 -i :8002 -i :8003 2>/dev/null || true)
    if [[ -n "$port_check" ]]; then
        found_processes=true
        echo "$port_check"
        echo ""
    fi
    
    if [[ "$found_processes" == "false" ]]; then
        print_colored $GREEN "✅ No tutorial processes found - system is clean!"
        return 0
    fi
    
    # Ask for confirmation before cleaning
    while true; do
        print_colored $BLUE "Kill these processes? (y/n): "
        read -r response
        case $response in
            [Yy]* )
                print_colored $YELLOW "🧹 Cleaning up..."
                cleanup
                print_colored $GREEN "✅ Manual cleanup completed!"
                break
                ;;
            [Nn]* )
                print_colored $YELLOW "⏭️  Cleanup cancelled"
                break
                ;;
            * )
                print_colored $RED "Please answer y or n."
                ;;
        esac
    done
}

# Function to validate tutorial number
validate_tutorial_number() {
    local num=$1
    if [[ ! "$num" =~ ^[0-9]+$ ]] || [[ $num -lt 1 ]] || [[ $num -gt ${#TUTORIALS[@]} ]]; then
        return 1
    fi
    return 0
}

# Main script logic
main() {
    # Check if we're in the right directory
    if [[ ! -f "../pyproject.toml" ]] || [[ ! -d "tutorials" ]]; then
        print_colored $RED "❌ Error: This script must be run from the examples directory"
        print_colored $YELLOW "💡 Current directory: $(pwd)"
        print_colored $YELLOW "💡 Expected files: ../pyproject.toml, tutorials/"
        exit 1
    fi
    
    # If a tutorial number is provided as argument
    if [[ $# -eq 1 ]]; then
        local tutorial_num=$1
        
        if [[ "$tutorial_num" == "a" ]] || [[ "$tutorial_num" == "all" ]]; then
            run_all_tutorials
            exit 0
        elif [[ "$tutorial_num" == "c" ]] || [[ "$tutorial_num" == "cleanup" ]]; then
            manual_cleanup
            exit 0
        fi
        
        if validate_tutorial_number "$tutorial_num"; then
            run_tutorial "$tutorial_num"
            exit $?
        else
            print_colored $RED "❌ Error: Invalid tutorial number '$tutorial_num'"
            print_colored $YELLOW "💡 Valid range: 1-${#TUTORIALS[@]}"
            exit 1
        fi
    fi
    
    # Interactive mode
    while true; do
        show_menu
        print_colored $BLUE "Enter your choice (1-${#TUTORIALS[@]}, a, c, or q): "
        read -r choice
        
        case $choice in
            [Qq]* )
                print_colored $YELLOW "👋 Goodbye!"
                exit 0
                ;;
            [Aa]* )
                echo ""
                run_all_tutorials
                echo ""
                ;;
            [Cc]* )
                echo ""
                manual_cleanup
                echo ""
                print_colored $BLUE "Press Enter to continue..."
                read -r
                ;;
            * )
                if validate_tutorial_number "$choice"; then
                    echo ""
                    run_tutorial "$choice"
                    echo ""
                    print_colored $BLUE "Press Enter to continue..."
                    read -r
                else
                    print_colored $RED "❌ Invalid choice: '$choice'"
                    print_colored $YELLOW "💡 Please enter a number between 1 and ${#TUTORIALS[@]}, 'a' for all, 'c' for cleanup, or 'q' to quit"
                fi
                ;;
        esac
        
        echo ""
    done
}

# Run the main function
main "$@"