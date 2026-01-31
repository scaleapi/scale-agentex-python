"""Voice Agent base class for LiveKit-powered voice agents.

This module provides the VoiceAgentBase class which handles:
- State management and persistence
- Message interruption handling
- Guardrail execution
- Streaming with concurrent guardrail checks
- Conversation history management
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Generic, Optional, Type, TypeVar

from agentex.lib import adk
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.utils.logging import make_logger
from agentex.types import DataContent, Span, TextContent, TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
    TaskMessageUpdate,
)
from agents import FunctionTool, OpenAIChatCompletionsModel
from openai.types.responses import ResponseTextDeltaEvent
from partial_json_parser import MalformedJSON
from partial_json_parser import loads as partial_json_loads
from pydantic import ValidationError

from agentex.voice.guardrails import Guardrail
from agentex.voice.models import AgentResponse, AgentState, ProcessingInfo

logger = make_logger(__name__)

# Timeout for processing info - if older than this, consider it stale/crashed
PROCESSING_TIMEOUT_SECONDS = 5


# Define TypeVars bounded to the base types
TState = TypeVar("TState", bound=AgentState)
TResponse = TypeVar("TResponse", bound=AgentResponse)


class VoiceAgentBase(ABC, Generic[TState, TResponse]):
    """Base class for voice agents with LiveKit integration.
    
    This class provides:
    - Automatic state management and persistence
    - Message interruption handling for voice
    - Guardrail system integration
    - Streaming with concurrent processing
    - Conversation history tracking
    
    Subclasses must implement:
    - get_system_prompt(): Return the LLM system prompt
    - update_state_and_tracing_from_response(): Update state after LLM response
    
    Optional override:
    - finish_agent_turn(): Stream additional content after main response
    
    Example:
        class MyVoiceAgent(VoiceAgentBase):
            state_class = MyAgentState
            response_class = MyAgentResponse
            
            def get_system_prompt(self, state, guardrail_override=None):
                return "You are a helpful assistant."
            
            def update_state_and_tracing_from_response(self, state, response, span):
                span.output = response
                return state
    """
    
    # Subclasses must define these class attributes
    state_class: Type[TState] = AgentState  # type: ignore
    response_class: Type[TResponse] = AgentResponse  # type: ignore

    def __init__(
        self,
        agent_name: str,
        llm_model: str,
        tools: Optional[list[FunctionTool]] = None,
        guardrails: Optional[list[Guardrail]] = None,
        openai_client = None,
    ):
        """Initialize the voice agent.
        
        Args:
            agent_name: Unique name for this agent
            llm_model: LLM model identifier (e.g., "vertex_ai/gemini-2.5-flash")
            tools: List of FunctionTools for the agent to use
            guardrails: List of Guardrails to enforce
            openai_client: OpenAI-compatible client (defaults to adk default)
        """
        self.agent_name = agent_name
        self.llm_model = llm_model
        self.tools = tools or []
        self.guardrails = guardrails or []
        self.openai_client = openai_client

    ### Abstract methods - must be implemented by subclasses

    @abstractmethod
    def get_system_prompt(
        self, conversation_state: TState, guardrail_override: Optional[str] = None
    ) -> str:
        """Generate the system prompt for the agent LLM.
        
        Args:
            conversation_state: Current conversation state
            guardrail_override: If provided, use this as the prompt (for guardrail failures)
        
        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def update_state_and_tracing_from_response(
        self, conversation_state: TState, response_data: TResponse, span: Span
    ) -> TState:
        """Update and return the conversation state based on the response data from the agent LLM.
        
        Args:
            conversation_state: Current conversation state
            response_data: Structured response from LLM
            span: Tracing span for logging
        
        Returns:
            Updated conversation state
        """
        pass

    async def finish_agent_turn(
        self, conversation_state: TState
    ) -> AsyncGenerator[TaskMessageUpdate, None]:
        """Stream any additional chunks to the user after the main response.
        
        Default implementation yields nothing. Override this method if your agent
        needs to stream additional content after the main response.
        
        Args:
            conversation_state: Current conversation state
        
        Yields:
            TaskMessageUpdate objects for additional content
        """
        return
        yield  # This line is never reached but makes it an async generator

    ### State management / interruption handling methods

    async def get_or_create_conversation_state(
        self, task_id: str, agent_id: str
    ) -> tuple[TState, str | None]:
        """Get existing conversation state or create a new one.
        
        Args:
            task_id: Unique task identifier
            agent_id: Unique agent identifier
        
        Returns:
            Tuple of (state, state_id)
        """
        try:
            # Try to get existing state
            task_state = await adk.state.get_by_task_and_agent(task_id=task_id, agent_id=agent_id)

            if task_state and task_state.state:
                # Parse existing state
                if isinstance(task_state.state, dict):
                    return self.state_class(**task_state.state), task_state.id
                else:
                    return task_state.state, task_state.id
            else:
                # Create new state
                new_state = self.state_class()
                created_state = await adk.state.create(
                    task_id=task_id, agent_id=agent_id, state=new_state
                )
                return new_state, created_state.id

        except Exception as e:
            logger.warning(f"Could not retrieve state, creating new: {e}")
            # Fallback to new state
            new_state = self.state_class()
            try:
                created_state = await adk.state.create(
                    task_id=task_id, agent_id=agent_id, state=new_state
                )
                return new_state, created_state.id
            except Exception:
                # If creation fails, just use in-memory state
                return new_state, None

    async def check_if_interrupted(self, task_id: str, agent_id: str, my_message_id: str) -> bool:
        """Check if this message's processing has been interrupted by another message.
        
        Args:
            task_id: Unique task identifier
            agent_id: Unique agent identifier
            my_message_id: ID of the message being processed
        
        Returns:
            True if interrupted, False otherwise
        """
        state, _ = await self.get_or_create_conversation_state(task_id, agent_id)
        if state.processing_info:
            return (
                state.processing_info.interrupted
                and state.processing_info.message_id == my_message_id
            )
        return False

    async def clear_processing_info(
        self, task_id: str, agent_id: str, state_id: str | None
    ) -> None:
        """Clear processing_info to signal processing has ended.
        
        Args:
            task_id: Unique task identifier
            agent_id: Unique agent identifier
            state_id: State ID for updates (can be None)
        """
        if not state_id:
            return

        try:
            state, _ = await self.get_or_create_conversation_state(task_id, agent_id)
            if state.processing_info:
                state.processing_info = None
                await adk.state.update(
                    state_id=state_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    state=state,
                )
                logger.info("Cleared processing_info")
        except Exception as e:
            logger.warning(f"Failed to clear processing_info: {e}")

    async def wait_for_processing_clear(
        self,
        task_id: str,
        agent_id: str,
        interrupted_message_id: str,
        timeout: float = 5.0,
        poll_interval: float = 0.2,
    ) -> bool:
        """Wait for the interrupted processor to acknowledge and clear processing_info.
        
        Args:
            task_id: Unique task identifier
            agent_id: Unique agent identifier
            interrupted_message_id: ID of the message that was interrupted
            timeout: Maximum time to wait (seconds)
            poll_interval: How often to check (seconds)
        
        Returns:
            True if cleared, False if timeout reached
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            state, _ = await self.get_or_create_conversation_state(task_id, agent_id)

            # Check if processing_info is cleared or belongs to a different message
            if not state.processing_info:
                return True
            if state.processing_info.message_id != interrupted_message_id:
                return True

            await asyncio.sleep(poll_interval)

        # Timeout - old processor may have crashed, proceed anyway
        logger.warning("Timeout waiting for interrupted processor to clear")
        return False

    async def handle_message_interruption(
        self,
        task_id: str,
        agent_id: str,
        state_id: str | None,
        new_content: str,
        new_message_id: str,
        state: TState,
    ) -> tuple[str, bool]:
        """Handle interruption of active processing when a new message arrives.
        
        This is critical for voice agents where users may speak over the agent
        or correct themselves mid-sentence.
        
        Args:
            task_id: Unique task identifier
            agent_id: Unique agent identifier
            state_id: State ID for updates
            new_content: New message content
            new_message_id: ID of the new message
            state: Current conversation state
        
        Returns:
            Tuple of (final_content, was_interrupted) where:
            - final_content: The message content to process (may be combined with old content)
            - was_interrupted: True if we interrupted another message's processing
        """
        if not state.processing_info:
            # No active processing - process normally
            return new_content, False

        # Check if processing info is stale (processor may have crashed)
        processing_age = time.time() - state.processing_info.started_at
        if processing_age > PROCESSING_TIMEOUT_SECONDS:
            logger.warning(f"Processing info is stale (age: {processing_age:.1f}s), ignoring")
            return new_content, False

        # Check if already interrupted (another message already took over)
        if state.processing_info.interrupted:
            logger.info("Processing already interrupted by another message")
            return new_content, False

        old_content = state.processing_info.message_content
        old_message_id = state.processing_info.message_id

        # Determine final content based on prefix check
        if new_content.startswith(old_content):
            # New message is a prefix extension - use new content only
            final_content = new_content
            logger.info("New message is prefix extension of old, using new content only")
        else:
            # Concatenate old and new content
            final_content = old_content + " " + new_content
            logger.info("Concatenating old and new message content")

        # Signal interruption to the old processor
        state.processing_info.interrupted = True
        state.processing_info.interrupted_by = new_message_id

        if state_id:
            await adk.state.update(
                state_id=state_id,
                task_id=task_id,
                agent_id=agent_id,
                state=state,
            )

        # Wait for old processor to acknowledge and clean up
        await self.wait_for_processing_clear(task_id, agent_id, old_message_id)

        return final_content, True

    async def save_state(
        self,
        state: TState,
        state_id: str | None,
        task_id: str,
        agent_id: str,
    ) -> bool:
        """Save the conversation state.
        
        Args:
            state: Conversation state to save
            state_id: State ID for updates
            task_id: Unique task identifier
            agent_id: Unique agent identifier
        
        Returns:
            True if saved successfully, False otherwise
        """
        if not state_id:
            logger.warning("No state_id provided, cannot save state")
            return False

        # Clear processing_info and increment version
        state.processing_info = None
        state.state_version += 1

        await adk.state.update(
            state_id=state_id,
            task_id=task_id,
            agent_id=agent_id,
            state=state,
        )

        logger.info(f"Saved state (version {state.state_version})")
        return True

    ### LLM request methods

    async def run_all_guardrails(
        self, user_message: str, conversation_state: TState
    ) -> tuple[bool, list[Guardrail]]:
        """Run all guardrails concurrently.
        
        Args:
            user_message: The user's input message
            conversation_state: Current conversation state
        
        Returns:
            Tuple of (all_passed, failed_guardrails):
            - all_passed: True if all guardrails passed
            - failed_guardrails: List of Guardrail instances that failed
        """
        if len(self.guardrails) == 0:
            return True, []

        if len(user_message) <= 5:
            logger.info("Skipping guardrails for short message")
            return True, []

        logger.info(f"Running {len(self.guardrails)} guardrails concurrently")

        # Run all guardrails concurrently
        results = await asyncio.gather(
            *[guardrail.check(user_message, conversation_state) for guardrail in self.guardrails],
            return_exceptions=True,
        )

        # Process results
        failed_guardrails = []
        all_passed = True

        for guardrail, result in zip(self.guardrails, results):
            if isinstance(result, Exception):
                logger.error(f"Guardrail {guardrail.name} raised exception: {result}")
                failed_guardrails.append(guardrail)
                all_passed = False
            elif not result:
                logger.warning(f"Guardrail {guardrail.name} failed")
                failed_guardrails.append(guardrail)
                all_passed = False

        logger.info(f"Guardrail check complete. All passed: {all_passed}")
        return all_passed, failed_guardrails

    async def stream_response(
        self,
        conversation_state: TState,
        max_turns: int = 1000,
        guardrail_override: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Call an LLM with streaming using the OpenAI Agents SDK.
        
        Args:
            conversation_state: Current conversation state
            max_turns: Maximum number of conversation turns to include
            guardrail_override: Override prompt (used when guardrail fails)
        
        Yields:
            Text deltas from the LLM
        """
        recent_context = conversation_state.conversation_history
        if max_turns is not None and len(recent_context) > max_turns:
            recent_context = recent_context[-max_turns:]

        system_prompt = self.get_system_prompt(conversation_state, guardrail_override)
        output_type = self.response_class if guardrail_override is None else None

        try:
            result = await adk.providers.openai.run_agent_streamed(
                input_list=recent_context,
                mcp_server_params=[],
                agent_name=self.agent_name,
                agent_instructions=system_prompt,
                model=OpenAIChatCompletionsModel(
                    model=self.llm_model,
                    openai_client=self.openai_client,
                ),
                tools=self.tools,
                output_type=output_type,
                max_turns=max_turns,
            )

            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    yield event.data.delta

        except Exception as e:
            logger.error(f"Streaming LLM call failed: {e}", exc_info=True)
            raise e

    ### Message handling methods

    async def handle_data_content_message(
        self,
        params: SendMessageParams,
        span: Span,
    ) -> AsyncGenerator[TaskMessageUpdate, None]:
        """Handle DataContent messages - initialize conversation state to a specific point.
        
        Args:
            params: Message parameters
            span: Tracing span
        
        Yields:
            TaskMessageUpdate with confirmation or error
        """
        try:
            new_state = self.state_class.model_validate(params.content.data)
            created_state = await adk.state.create(
                task_id=params.task.id, agent_id=params.agent.id, state=new_state
            )
            response = f"Successfully initialized conversation state. State ID: {created_state.id}"
            span.output = {"response_text": response}
            yield StreamTaskMessageFull(
                type="full",
                index=0,
                content=TextContent(
                    type="text",
                    author="agent",
                    content=response,
                ),
            )
        except ValidationError as e:
            raise ValueError(f"Failed to create conversation state from provided data content: {e}")

    async def handle_text_content_message(
        self,
        params: SendMessageParams,
        conversation_state: TState,
        state_id: str | None,
        span: Span,
        message_id: str,
        message_content: str,
    ) -> AsyncGenerator[TaskMessageUpdate, None]:
        """Handle TextContent messages with guardrails and streaming.
        
        This is the main message processing pipeline for voice agents.
        
        Args:
            params: Message parameters
            conversation_state: Current conversation state
            state_id: State ID for updates
            span: Tracing span
            message_id: Unique message ID
            message_content: The text content to process
        
        Yields:
            TaskMessageUpdate objects for streaming response
        """
        # Add user message to conversation history
        conversation_state.conversation_history.append({"role": "user", "content": message_content})

        # Start both guardrails and streaming concurrently
        guardrail_task = asyncio.create_task(
            self.run_all_guardrails(message_content, conversation_state)
        )
        # Create an async generator that we'll consume
        stream_generator = self.stream_response(conversation_state)

        # Buffer to store streaming chunks while waiting for guardrails
        buffered_chunks = []
        full_json_response = ""
        assistant_response_text = ""
        guardrails_completed = False
        guardrails_passed = False
        failed_guardrails = []

        # Consume stream and buffer until guardrails complete
        try:
            yield StreamTaskMessageStart(
                type="start",
                index=0,
                content=TextContent(author="agent", content=""),
            )
            async for chunk in stream_generator:
                full_json_response += chunk

                # Check for interruption periodically
                if await self.check_if_interrupted(params.task.id, params.agent.id, message_id):
                    logger.info("Processing interrupted by newer message, stopping")
                    await self.clear_processing_info(params.task.id, params.agent.id, state_id)
                    if not guardrail_task.done():
                        guardrail_task.cancel()
                    yield StreamTaskMessageDone(type="done", index=0)
                    return

                # Check if guardrails have completed
                if not guardrails_completed and guardrail_task.done():
                    guardrails_completed = True
                    guardrails_passed, failed_guardrails = guardrail_task.result()

                    if not guardrails_passed:
                        # Guardrails failed - stop processing
                        logger.warning(f"Guardrails failed: {[g.name for g in failed_guardrails]}")
                        break
                    else:
                        # Guardrails passed - yield all buffered chunks
                        logger.info("Guardrails passed, streaming response to user")
                        for buffered_chunk in buffered_chunks:
                            yield buffered_chunk
                        # Clear buffer as we've yielded everything
                        buffered_chunks.clear()

                # Process this chunk for streaming
                try:
                    new_assistant_response_text = partial_json_loads(full_json_response).get(
                        "response_text", assistant_response_text
                    )
                    if len(new_assistant_response_text) > len(assistant_response_text):
                        text_delta = new_assistant_response_text[len(assistant_response_text) :]
                        delta_message = StreamTaskMessageDelta(
                            type="delta",
                            index=0,
                            delta=TextDelta(text_delta=text_delta, type="text"),
                        )

                        if guardrails_completed and guardrails_passed:
                            # Guardrails already passed, stream directly
                            yield delta_message
                        else:
                            # Guardrails still running, buffer the chunk
                            buffered_chunks.append(delta_message)

                        assistant_response_text = new_assistant_response_text
                except MalformedJSON:
                    # usually this happens at the start of the stream
                    continue

            # If guardrails haven't completed yet, wait for them
            if not guardrails_completed:
                guardrails_passed, failed_guardrails = await guardrail_task
                guardrails_completed = True

                if not guardrails_passed:
                    logger.warning(f"Guardrails failed: {[g.name for g in failed_guardrails]}")
                else:
                    # Guardrails passed - yield all buffered chunks
                    logger.info(
                        "Guardrails passed (after streaming completed), yielding buffered response"
                    )
                    for buffered_chunk in buffered_chunks:
                        yield buffered_chunk

            # If guardrails failed, stream using the prompt override
            if not guardrails_passed:
                # Use the first failed guardrail's prompt
                failed_guardrail = failed_guardrails[0]
                assistant_response_text = ""
                async for text_delta in self.stream_response(
                    conversation_state, guardrail_override=failed_guardrail.outcome_prompt
                ):
                    assistant_response_text += text_delta
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=0,
                        delta=TextDelta(text_delta=text_delta, type="text"),
                    )

                span.output = {
                    "response_text": assistant_response_text,
                    "guardrails_hit": [gr.name for gr in failed_guardrails],
                }

            else:
                # Process the complete response to update state
                response_data = self.response_class.model_validate_json(full_json_response)
                conversation_state = self.update_state_and_tracing_from_response(
                    conversation_state, response_data, span
                )

            # Add agent response to conversation history
            conversation_state.conversation_history.append(
                {"role": "assistant", "content": assistant_response_text}
            )

            # Output any additional messages we want to surface to the user
            async for update in self.finish_agent_turn(conversation_state):
                yield update

            # Save updated state
            if state_id:
                await self.save_state(
                    state=conversation_state,
                    state_id=state_id,
                    task_id=params.task.id,
                    agent_id=params.agent.id,
                )

        except asyncio.CancelledError:
            # Handle cancellation gracefully
            logger.info("Streaming cancelled")
            raise
        except Exception as stream_error:
            # Cancel guardrail task if it's still running
            if not guardrail_task.done():
                guardrail_task.cancel()
            raise stream_error
        finally:
            # Always clear processing_info
            await self.clear_processing_info(params.task.id, params.agent.id, state_id)
            yield StreamTaskMessageDone(type="done", index=0)

    async def send_message(
        self,
        params: SendMessageParams,
    ) -> AsyncGenerator[TaskMessageUpdate, None]:
        """Main entry point to send a message request to a voice agent.
        
        This is the method called by the ACP handler. It orchestrates:
        - State retrieval/creation
        - Interruption handling
        - Routing to appropriate content handlers
        - Error handling
        
        Args:
            params: Message parameters from ACP
        
        Yields:
            TaskMessageUpdate objects for streaming response
        """
        # Use task_id as trace_id for consistency
        trace_id = params.task.id
        async with adk.tracing.span(
            trace_id=trace_id,
            name="handle_message_send",
            input=params,
        ) as span:
            try:
                if isinstance(params.content, DataContent):
                    # If DataContent is sent, try to initialize state from the sent data
                    async for update in self.handle_data_content_message(params, span):
                        yield update

                elif isinstance(params.content, TextContent):
                    # if TextContent is sent, process it as a voice message
                    # Generate a unique message ID for this processing request
                    message_id = f"{params.task.id}:{uuid.uuid4()}"
                    new_content = params.content.content

                    # Get or create conversation state
                    conversation_state, state_id = await self.get_or_create_conversation_state(
                        params.task.id, params.agent.id
                    )

                    # Handle interruption if there's active processing
                    final_content, was_interrupted = await self.handle_message_interruption(
                        task_id=params.task.id,
                        agent_id=params.agent.id,
                        state_id=state_id,
                        new_content=new_content,
                        new_message_id=message_id,
                        state=conversation_state,
                    )

                    if was_interrupted:
                        # Re-read state after interruption cleanup
                        conversation_state, state_id = await self.get_or_create_conversation_state(
                            params.task.id, params.agent.id
                        )

                    # Set up processing_info for this message
                    conversation_state.processing_info = ProcessingInfo(
                        message_id=message_id,
                        message_content=final_content,
                        started_at=time.time(),
                    )
                    if state_id:
                        await adk.state.update(
                            state_id=state_id,
                            task_id=params.task.id,
                            agent_id=params.agent.id,
                            state=conversation_state,
                        )

                    # Delegate to TextContent handler with guardrails
                    async for update in self.handle_text_content_message(
                        params, conversation_state, state_id, span, message_id, final_content
                    ):
                        yield update

            except Exception as e:
                logger.error(f"Error processing voice message: {e}", exc_info=True)
                # Return error message to user
                span.output = {"error": str(e)}
                yield StreamTaskMessageFull(
                    type="full",
                    index=1,
                    content=TextContent(
                        type="text",
                        author="agent",
                        content="I apologize, but I encountered an error. Could you please try again?",
                    ),
                )
