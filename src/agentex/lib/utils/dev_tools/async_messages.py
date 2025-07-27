"""
Development utility for subscribing to async task messages with streaming support.

This module provides utilities to read existing messages from a task and subscribe
to new streaming messages, handling mid-stream connections gracefully.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional

from yaspin.core import Yaspin

from agentex import Agentex
from agentex.types import Task, TaskMessage, TextContent
from agentex.types.task_message_update import (
    TaskMessageUpdate,
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone
)
from agentex.types.text_delta import TextDelta

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from yaspin import yaspin


def print_task_message(
  message: TaskMessage, 
  print_messages: bool = True,
  rich_print: bool = True,
) -> None:
    """
    Print a task message in a formatted way.
    
    Args:
        message: The task message to print
        print_messages: Whether to actually print the message (for debugging)
        rich_print: Whether to use rich to print the message
    """
    if not print_messages:
        return
    
    # Skip empty messages
    if isinstance(message.content, TextContent) and not message.content.content.strip():
        return
    
    timestamp = message.created_at.strftime("%m/%d/%Y %H:%M:%S") if message.created_at else "N/A"
    
    console = None
    if rich_print:
        console = Console(width=80)  # Fit better in Jupyter cells
    
    if isinstance(message.content, TextContent):        
        content = message.content.content
    else:
        content = f"{type(message.content).__name__}: {message.content}"
    
    if rich_print and console:
        author_color = "bright_cyan" if message.content.author == "user" else "green"
        title = f"[bold {author_color}]{message.content.author.upper()}[/bold {author_color}] [{timestamp}]"
        panel = Panel(Markdown(content), title=title, border_style=author_color, width=80)
        console.print(panel)
    else:
        title = f"{message.content.author.upper()} [{timestamp}]"
        print(f"{title}\n{content}\n")


def print_task_message_update(
    task_message_update: TaskMessageUpdate,
    print_messages: bool = True,
    rich_print: bool = True,
    show_deltas: bool = True,
) -> None:
    """
    Print a task message update in a formatted way.
    
    This function handles different types of TaskMessageUpdate objects:
    - StreamTaskMessageStart: Shows start indicator
    - StreamTaskMessageDelta: Shows deltas in real-time (if show_deltas=True)
    - StreamTaskMessageFull: Shows complete message content
    - StreamTaskMessageDone: Shows completion indicator
    
    Args:
        task_message_update: The TaskMessageUpdate object to print
        print_messages: Whether to actually print the message (for debugging)
        rich_print: Whether to use rich formatting
        show_deltas: Whether to show delta updates in real-time
    """
    if not print_messages:
        return
    
    console = None
    if rich_print:
        console = Console(width=80)
    
    if isinstance(task_message_update, StreamTaskMessageStart):
        if rich_print and console:
            console.print("🚀 [cyan]Agent started responding...[/cyan]")
        else:
            print("🚀 Agent started responding...")
            
    elif isinstance(task_message_update, StreamTaskMessageDelta):
        if show_deltas and task_message_update.delta:
            if isinstance(task_message_update.delta, TextDelta):
                print(task_message_update.delta.text_delta, end="", flush=True)
            elif rich_print and console:
                console.print(f"[yellow]Non-text delta: {type(task_message_update.delta).__name__}[/yellow]")
            else:
                print(f"Non-text delta: {type(task_message_update.delta).__name__}")
                
    elif isinstance(task_message_update, StreamTaskMessageFull):
        if isinstance(task_message_update.content, TextContent):
            timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            
            if rich_print and console:
                author_color = "bright_cyan" if task_message_update.content.author == "user" else "green"
                title = f"[bold {author_color}]{task_message_update.content.author.upper()}[/bold {author_color}] [{timestamp}]"
                panel = Panel(Markdown(task_message_update.content.content), title=title, border_style=author_color, width=80)
                console.print(panel)
            else:
                title = f"{task_message_update.content.author.upper()} [{timestamp}]"
                print(f"\n{title}\n{task_message_update.content.content}\n")
        else:
            content_type = type(task_message_update.content).__name__
            if rich_print and console:
                console.print(f"[yellow]Non-text content: {content_type}[/yellow]")
            else:
                print(f"Non-text content: {content_type}")
                
    elif isinstance(task_message_update, StreamTaskMessageDone):
        if rich_print and console:
            console.print("\n✅ [green]Agent finished responding.[/green]")
        else:
            print("\n✅ Agent finished responding.")


def subscribe_to_async_task_messages(
    client: Agentex,
    task: Task, 
    only_after_timestamp: Optional[datetime] = None,
    print_messages: bool = True,
    rich_print: bool = True,
    timeout: int = 10,
) -> List[TaskMessage]:
    """
    Subscribe to async task messages and collect completed messages.
    
    This function:
    1. Reads all existing messages from the task
    2. Optionally filters messages after a timestamp
    3. Shows a loading message while listening
    4. Subscribes to task message events
    5. Fetches and displays complete messages when they finish
    6. Returns all messages collected during the session
    
    Features:
    - Uses Rich library for beautiful formatting in Jupyter notebooks
    - Agent messages are formatted as Markdown
    - User and agent messages are displayed in colored panels with fixed width
    - Optimized for Jupyter notebook display
    
    Args:
        client: The Agentex client instance
        task: The task to subscribe to
        print_messages: Whether to print messages as they arrive
        only_after_timestamp: Only include messages created after this timestamp. If None, all messages will be included.
        rich_print: Whether to use rich to print the message
        timeout: The timeout in seconds for the streaming connection. If the connection times out, the function will return with any messages collected so far.
    Returns:
        List of TaskMessage objects collected during the session
        
    Raises:
        ValueError: If the task doesn't have a name (required for streaming)
    """

    messages_to_return: List[TaskMessage] = []

    # Read existing messages
    messages = []
    try:
        # List all messages for this task - MessageListResponse is just a List[TaskMessage]
        messages = client.messages.list(task_id=task.id)
        
    except Exception as e:
        print(f"Error reading existing messages: {e}")

    # Filter and display existing messages
    for message in messages:
        if only_after_timestamp:
            if message.created_at is not None:
                # Handle timezone comparison - make both datetimes timezone-aware
                message_time = message.created_at
                if message_time.tzinfo is None:
                    # If message time is naive, assume it's in UTC
                    message_time = message_time.replace(tzinfo=timezone.utc)
                
                comparison_time = only_after_timestamp
                if comparison_time.tzinfo is None:
                    # If comparison time is naive, assume it's in UTC
                    comparison_time = comparison_time.replace(tzinfo=timezone.utc)
                
                if message_time < comparison_time:
                    continue
                else:
                    messages_to_return.append(message)
                    print_task_message(message, print_messages, rich_print)
        else:
            messages_to_return.append(message)
            print_task_message(message, print_messages, rich_print)

    # Subscribe to server-side events using tasks.stream_events_by_name
    # This is the proper way to get agent responses after sending an event in agentic agents

    # Ensure task has a name
    if not task.name:
        print("Error: Task must have a name to use stream_events_by_name")
        raise ValueError("Task name is required")

    try:
        # Use stream_events_by_name to subscribe to TaskMessageUpdate events for this task
        # This doesn't require knowing the agent_id, just the task name
        
        # Track active streaming spinners per message index
        active_spinners: dict[int, Yaspin] = {}  # index -> yaspin spinner object
            
        with client.tasks.with_streaming_response.stream_events_by_name(
            task_name=task.name,
            timeout=timeout
        ) as response:
            
            try:
                for task_message_update_str in response.iter_text():
                    try:
                        # Parse SSE format 
                        if task_message_update_str.strip().startswith('data: '):
                            task_message_update_json = task_message_update_str.strip()[6:]  # Remove 'data: ' prefix
                            task_message_update_data = json.loads(task_message_update_json)
                            
                            # Deserialize the discriminated union TaskMessageUpdate based on the "type" field
                            message_type = task_message_update_data.get("type", "unknown")
                            
                            # Handle different message types for streaming progress
                            if message_type == "start":
                                task_message_update = StreamTaskMessageStart.model_validate(task_message_update_data)
                                index = task_message_update.index or 0
                                
                                # Start a yaspin spinner for this message
                                if print_messages and index not in active_spinners:
                                    spinner = yaspin(text="🔄 Agent responding...")
                                    spinner.start()
                                    active_spinners[index] = spinner
                                    
                            elif message_type == "delta":
                                task_message_update = StreamTaskMessageDelta.model_validate(task_message_update_data)
                                index = task_message_update.index or 0
                                
                                # Spinner continues running (no update needed for HTML) or if spinner has not been created yet, create it
                                if print_messages and index not in active_spinners:
                                    spinner = yaspin(text="🔄 Agent responding...")
                                    spinner.start()
                                    active_spinners[index] = spinner
                                
                            elif message_type == "full":
                                task_message_update = StreamTaskMessageFull.model_validate(task_message_update_data)
                                index = task_message_update.index or 0
                                
                                # Stop spinner and show message
                                if index in active_spinners:
                                    active_spinners[index].stop()
                                    del active_spinners[index]
                                
                                if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                                    finished_message = client.messages.retrieve(task_message_update.parent_task_message.id)
                                    messages_to_return.append(finished_message)
                                    print_task_message(finished_message, print_messages, rich_print)
                                
                            elif message_type == "done":
                                task_message_update = StreamTaskMessageDone.model_validate(task_message_update_data)
                                index = task_message_update.index or 0
                                
                                # Stop spinner and show message
                                if index in active_spinners:
                                    active_spinners[index].stop()
                                    del active_spinners[index]
                                
                                if task_message_update.parent_task_message and task_message_update.parent_task_message.id:
                                    finished_message = client.messages.retrieve(task_message_update.parent_task_message.id)
                                    messages_to_return.append(finished_message)
                                    print_task_message(finished_message, print_messages, rich_print)
                                
                            # Ignore "connected" message type
                            elif message_type == "connected":
                                pass
                            else:
                                if print_messages:
                                    print(f"Unknown TaskMessageUpdate type: {message_type}")
                                
                    except json.JSONDecodeError:
                        # Skip invalid JSON or SSE metadata lines
                        if task_message_update_str.strip() and not task_message_update_str.startswith(':'):
                            if print_messages:
                                print(f"Skipping non-JSON: {task_message_update_str.strip()}")
                        continue
                    except Exception as e:
                        if print_messages:
                            print(f"Error processing TaskMessageUpdate: {e}")
                            print(f"Raw data: {task_message_update_str.strip()}")
                        continue
            finally:
                # Stop any remaining spinners when we're done
                for spinner in active_spinners.values():
                    spinner.stop()
                active_spinners.clear()
                    
    except Exception as e:
        # Handle timeout gracefully
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            if print_messages:
                print(f"Streaming timed out after {timeout} seconds - returning collected messages")
        else:
            if print_messages:
                print(f"Error subscribing to events: {e}")
                print("Make sure your agent is running and the task exists")
    
    return messages_to_return 