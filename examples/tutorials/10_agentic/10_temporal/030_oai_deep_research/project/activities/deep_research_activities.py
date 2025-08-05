"""Custom activities for deep research workflow."""
import re
import traceback
from temporalio import activity
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib import adk

logger = make_logger(__name__)

class DeepResearchParams(BaseModelWithTraceParams):
    """Parameters for deep research activity."""
    task_id: str
    enriched_instructions: str
    research_model: str
    research_instructions: str

class DeepResearchResult(BaseModelWithTraceParams):
    """Result from deep research activity."""
    research_report: str
    citations: list[dict[str, str]]

async def use_background_mode_for_long_prompt(params: DeepResearchParams) -> DeepResearchResult:
    """Handle long-running research tasks with better timeout management."""
    logger.info("DeepResearchActivity: Handling long prompt with timeout management")
    
    try:
        from agents import Agent, Runner, WebSearchTool
        import asyncio
        
        # Send initial message to user
        await adk.messages.create(
            task_id=params.task_id,
            content=TextContent(
                author="agent",
                content="🔄 Processing complex research request... This typically takes 3-5 minutes for detailed financial analysis. I'll keep working on it."
            )
        )
        
        # Create agent
        research_agent = Agent(
            name="Deep Research Agent",
            model=params.research_model,
            instructions=params.research_instructions,
            tools=[WebSearchTool()]
        )
        
        final_output = ""
        citations = []
        message_sent = False
        
        try:
            logger.info("DeepResearchActivity: Starting long-running research")
            
            # Keep heartbeat alive during execution
            async def heartbeat_task():
                count = 0
                while True:
                    activity.heartbeat()
                    count += 1
                    if count % 4 == 0:  # Every 2 minutes (30s * 4)
                        await adk.messages.create(
                            task_id=params.task_id,
                            content=TextContent(
                                author="agent",
                                content=f"⏳ Still researching... ({count // 2} minutes elapsed)"
                            )
                        )
                    await asyncio.sleep(30)  # Heartbeat every 30 seconds
            
            # Run heartbeat in background
            heartbeat = asyncio.create_task(heartbeat_task())
            
            try:
                # For very long prompts, we'll use streaming to capture partial results
                result = Runner.run_streamed(
                    starting_agent=research_agent,
                    input=[
                        {"role": "user", "content": params.enriched_instructions}
                    ]
                )
                
                # Process streaming results
                current_message = ""
                event_count = 0
                
                async for event in result.stream_events():
                    event_count += 1
                    
                    # Keep activity alive
                    if event_count % 10 == 0:
                        activity.heartbeat()
                    
                    # Handle different event types
                    if event.type == "run_item_stream_event":
                        if hasattr(event, 'item'):
                            item = event.item
                            item_type = getattr(item, 'type', None)
                            
                            # Handle message items
                            if item_type == "message":
                                if hasattr(item, 'content') and isinstance(item.content, list):
                                    for content_item in item.content:
                                        if hasattr(content_item, 'type') and content_item.type == "output_text":
                                            text = getattr(content_item, 'text', '')
                                            if text:
                                                final_output = text
                                                message_sent = True
                                                logger.info(f"DeepResearchActivity: Found message output ({len(text)} chars)")
                                                
                                                # Send to UI
                                                await adk.messages.create(
                                                    task_id=params.task_id,
                                                    content=TextContent(
                                                        author="agent",
                                                        content=text
                                                    )
                                                )
                                                
                                                # Extract citations from annotations
                                                annotations = getattr(content_item, 'annotations', [])
                                                for annotation in annotations:
                                                    if hasattr(annotation, 'url') and hasattr(annotation, 'title'):
                                                        citations.append({
                                                            "title": annotation.title,
                                                            "url": annotation.url
                                                        })
                    
                    # Handle text deltas for streaming
                    elif hasattr(event, 'delta') and hasattr(event.delta, 'content'):
                        content = event.delta.content
                        current_message += content
                        
                        # Stream large chunks to user
                        if len(current_message) > 1000 and not message_sent:
                            await adk.messages.create(
                                task_id=params.task_id,
                                content=TextContent(
                                    author="agent",
                                    content=current_message
                                )
                            )
                            current_message = ""
                    
                    elif event.type == "agent_updated_stream_event":
                        logger.debug("DeepResearchActivity: Agent updated event")
                        continue
                
                # Send any remaining content
                if current_message and not message_sent:
                    final_output = current_message
                    await adk.messages.create(
                        task_id=params.task_id,
                        content=TextContent(
                            author="agent",
                            content=current_message
                        )
                    )
                
                # Try to get final output from result
                if not final_output and hasattr(result, 'final_output') and result.final_output:
                    final_output = result.final_output
                    if not message_sent:
                        await adk.messages.create(
                            task_id=params.task_id,
                            content=TextContent(
                                author="agent",
                                content=final_output
                            )
                        )
                
                logger.info(f"DeepResearchActivity: Research completed, processed {event_count} events")
                
            finally:
                # Cancel heartbeat task
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
                
        except asyncio.CancelledError:
            logger.error("DeepResearchActivity: Research was cancelled")
            error_msg = "The research request was cancelled. For complex financial analysis, please try breaking your request into smaller, specific queries."
            
            await adk.messages.create(
                task_id=params.task_id,
                content=TextContent(
                    author="agent",
                    content=error_msg
                )
            )
            
            return DeepResearchResult(
                research_report=error_msg,
                citations=[]
            )
            
        except Exception as e:
            logger.error(f"DeepResearchActivity: Error during long-running research: {e}")
            logger.error(f"DeepResearchActivity: Error type: {type(e).__name__}")
            
            error_msg = f"Error during research: {str(e)}. Please try a more focused question."
            
            await adk.messages.create(
                task_id=params.task_id,
                content=TextContent(
                    author="agent",
                    content=error_msg
                )
            )
            
            return DeepResearchResult(
                research_report=error_msg,
                citations=[]
            )
        
        # Send citations if found
        if citations:
            citations_text = "\\n\\nSources cited:\\n" + "\\n".join(
                [f"- [{c['title']}]({c['url']})" for c in citations[:10]]
            )
            await adk.messages.create(
                task_id=params.task_id,
                content=TextContent(
                    author="agent",
                    content=citations_text
                )
            )
        
        return DeepResearchResult(
            research_report=final_output or "Research completed.",
            citations=citations
        )
        
    except Exception as e:
        logger.error(f"DeepResearchActivity: Long prompt handler failed: {e}")
        logger.error(f"Full error: {traceback.format_exc()}")
        
        # Send error message to user
        error_msg = f"Failed to process research request: {str(e)}"
        await adk.messages.create(
            task_id=params.task_id,
            content=TextContent(
                author="agent",
                content=error_msg
            )
        )
        
        return DeepResearchResult(
            research_report=error_msg,
            citations=[]
        )

@activity.defn(name="run_deep_research")
async def run_deep_research(params: DeepResearchParams) -> DeepResearchResult:
    """Run deep research using OpenAI agents library directly."""
    logger.info("DeepResearchActivity: Starting deep research")
    logger.info(f"DeepResearchActivity: Task ID: {params.task_id}")
    logger.info(f"DeepResearchActivity: Instructions length: {len(params.enriched_instructions)}")
    logger.info(f"DeepResearchActivity: Model: {params.research_model}")
    
    # Check if this is a long prompt that needs background mode
    if len(params.enriched_instructions) > 5000:
        logger.info(f"DeepResearchActivity: Long prompt detected ({len(params.enriched_instructions)} chars), considering background mode")
        # For now, we'll continue with the agents library approach but with better error handling
    
    try:
        from agents import Agent, Runner, WebSearchTool
        logger.info("DeepResearchActivity: Successfully imported agents library")
    except ImportError as e:
        logger.error(f"DeepResearchActivity: Failed to import agents library: {e}")
        raise RuntimeError("agents library is required. Install with: pip install openai-agents") from e
    
    # Create agent directly using OpenAI agents library
    logger.info("DeepResearchActivity: Creating research agent with WebSearchTool")
    research_agent = Agent(
        name="Deep Research Agent",
        model=params.research_model,
        instructions=params.research_instructions,
        tools=[WebSearchTool()]  # Use WebSearchTool directly
    )
    
    # For long prompts, use background mode
    if len(params.enriched_instructions) > 5000:
        logger.info(f"DeepResearchActivity: Using background mode for long prompt ({len(params.enriched_instructions)} chars)")
        return await use_background_mode_for_long_prompt(params)
    
    # Run agent with streaming for shorter prompts
    logger.info("DeepResearchActivity: Starting agent run with streaming")
    try:
        result = Runner.run_streamed(
            starting_agent=research_agent,
            input=[
                {"role": "user", "content": params.enriched_instructions}
            ]
        )
        logger.info("DeepResearchActivity: Runner.run_streamed created successfully")
    except Exception as e:
        logger.error(f"DeepResearchActivity: Failed to create runner: {e}")
        raise
    
    # Process streaming results and send messages
    final_output = ""
    current_message = ""
    citations = []
    web_searches = []
    message_found = False  # Track if we found the final message
    
    try:
        event_count = 0
        async for event in result.stream_events():
            event_count += 1
            activity.heartbeat()  # Keep activity alive
            
            # Handle different event types based on agents library
            logger.debug(f"DeepResearchActivity: Event #{event_count}, type: {event.type}")
            
            if event.type == "run_item_stream_event":
                # Process streaming item events
                if hasattr(event, 'item'):
                    item = event.item
                    item_type = getattr(item, 'type', None)
                    logger.debug(f"DeepResearchActivity: Item type: {item_type}")
                    
                    # Log item attributes for debugging
                    if item_type == "message":
                        logger.info(f"DeepResearchActivity: Message item found, has content: {hasattr(item, 'content')}")
                    
                    # Handle web search calls
                    if item_type == "web_search_call":
                        if hasattr(item, 'action'):
                            action_type = getattr(item.action, 'type', 'unknown')
                            query = getattr(item.action, 'query', '')
                            logger.info(f"DeepResearchActivity: Web search - {action_type}: {query}")
                            web_searches.append({"type": action_type, "query": query})
                    
                    # Handle message items with content
                    elif hasattr(item, 'type') and item.type == "message":
                        if hasattr(item, 'content') and isinstance(item.content, list):
                            for content_item in item.content:
                                if hasattr(content_item, 'type') and content_item.type == "output_text":
                                    text = getattr(content_item, 'text', '')
                                    if text:
                                        # We found the final message
                                        final_output = text
                                        message_found = True
                                        logger.info(f"DeepResearchActivity: Found final message in event stream ({len(text)} chars)")
                                        
                                        # Extract citations from annotations
                                        annotations = getattr(content_item, 'annotations', [])
                                        for annotation in annotations:
                                            if hasattr(annotation, 'url') and hasattr(annotation, 'title'):
                                                citations.append({
                                                    "title": annotation.title,
                                                    "url": annotation.url
                                                })
                                        logger.info(f"DeepResearchActivity: Found {len(annotations)} annotations")
                
                # Handle text deltas for streaming (only if we haven't found the final message)
                if not message_found and hasattr(event, 'delta') and hasattr(event.delta, 'content'):
                    content = event.delta.content
                    current_message += content
                    
                    # Stream text content to user
                    await adk.messages.create(
                        task_id=params.task_id,
                        content=TextContent(
                            author="agent",
                            content=content
                        )
                    )
                    
            elif event.type == "raw_response_event":
                # Log raw events for debugging
                logger.debug(f"DeepResearchActivity: Raw event type - {event}")
            
            elif event.type == "agent_updated_stream_event":
                # This event type is expected - just log it
                logger.info(f"DeepResearchActivity: Agent updated event - continuing to process events...")
                continue  # Explicitly continue to next event
            
            # Log any other event types we might be missing
            else:
                logger.debug(f"DeepResearchActivity: Other event type: {event.type} (continuing...)")
        
        # After streaming, check if we can access the final result
        logger.info(f"DeepResearchActivity: Finished streaming events (processed {event_count} events)")
        
        # Check if result has new_items that might contain the final message
        if not final_output and hasattr(result, 'new_items'):
            logger.info(f"DeepResearchActivity: Checking {len(result.new_items)} new items")
            for item in result.new_items:
                if hasattr(item, 'type') and item.type == "message":
                    if hasattr(item, 'content') and isinstance(item.content, list):
                        for content_item in item.content:
                            if hasattr(content_item, 'type') and content_item.type == "output_text":
                                text = getattr(content_item, 'text', '')
                                if text:
                                    final_output = text
                                    message_found = True
                                    logger.info(f"DeepResearchActivity: Found final message in new_items ({len(text)} chars)")
                                    
                                    # Extract citations from annotations
                                    annotations = getattr(content_item, 'annotations', [])
                                    for annotation in annotations:
                                        if hasattr(annotation, 'url') and hasattr(annotation, 'title'):
                                            citations.append({
                                                "title": annotation.title,
                                                "url": annotation.url
                                            })
                                    break
                if final_output:
                    break
                
        # If we didn't get final output from structured response, use accumulated message
        if not final_output and current_message:
            final_output = current_message
            logger.info(f"DeepResearchActivity: Using accumulated message as final output ({len(current_message)} chars)")
            
        # Check if we can get final output from result object
        if not final_output and hasattr(result, 'final_output') and result.final_output:
            final_output = result.final_output
            logger.info(f"DeepResearchActivity: Using result.final_output ({len(result.final_output)} chars)")
            logger.debug(f"DeepResearchActivity: First 500 chars of result.final_output: {result.final_output[:500]}")
            
        # Extract citations using regex as fallback if needed
        if final_output and not citations:
            citation_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
            found_citations = re.findall(citation_pattern, final_output)
            for title, url in found_citations:
                if not any(c['url'] == url for c in citations):
                    citations.append({"title": title, "url": url})
            if found_citations:
                logger.info(f"DeepResearchActivity: Extracted {len(found_citations)} citations via regex")
            
    except Exception as e:
        logger.error(f"DeepResearchActivity: Error during agent streaming: {e}")
        logger.error(f"DeepResearchActivity: Error type: {type(e).__name__}")
        logger.error(f"DeepResearchActivity: Error details: {str(e)}")
        import traceback
        logger.error(f"DeepResearchActivity: Traceback: {traceback.format_exc()}")
        raise
    
    # Wait for result to complete if streaming didn't capture everything
    if not final_output and hasattr(result, 'wait'):
        logger.info("DeepResearchActivity: No output captured during streaming, waiting for result...")
        try:
            # Some streaming results need to be awaited
            if callable(result.wait):
                await result.wait()
            
            # Check again for final_output
            if hasattr(result, 'final_output') and result.final_output:
                final_output = result.final_output
                logger.info(f"DeepResearchActivity: Got final_output after wait ({len(final_output)} chars)")
        except Exception as e:
            logger.error(f"DeepResearchActivity: Error waiting for result: {e}")
    
    # Try to get output from other result attributes
    if not final_output:
        # Check for other possible output attributes
        for attr in ['output', 'text', 'content', 'response']:
            if hasattr(result, attr):
                value = getattr(result, attr)
                if value and isinstance(value, str):
                    final_output = value
                    logger.info(f"DeepResearchActivity: Found output in result.{attr} ({len(value)} chars)")
                    break
    
    # Log all available attributes for debugging
    if not final_output:
        logger.warning("DeepResearchActivity: No final output found, checking available attributes...")
        attrs = [attr for attr in dir(result) if not attr.startswith('_')]
        logger.info(f"DeepResearchActivity: Available result attributes: {attrs}")
        
        # Try to get any string representation
        try:
            final_output = str(result)
            if final_output and len(final_output) > 100:  # Meaningful content
                logger.info(f"DeepResearchActivity: Using string representation of result ({len(final_output)} chars)")
            else:
                final_output = ""
        except:
            final_output = ""
    
    # Ensure we have some output
    if not final_output:
        logger.warning("DeepResearchActivity: No final output captured after all attempts")
        if current_message and len(current_message) > 100:
            final_output = current_message
            logger.info(f"DeepResearchActivity: Using accumulated message as fallback ({len(current_message)} chars)")
        else:
            final_output = "I apologize, but I was unable to complete the research. The request may be too complex or there may have been a technical issue. Please try breaking down your request into smaller, more specific queries."
    
    # Send the final output to the UI if we haven't sent it already
    if final_output and not message_found:
        logger.info(f"DeepResearchActivity: Sending final output to UI ({len(final_output)} chars)")
        await adk.messages.create(
            task_id=params.task_id,
            content=TextContent(
                author="agent",
                content=final_output
            )
        )
    
    # Display citations if found
    if citations:
        citations_text = "\\n\\nSources cited:\\n" + "\\n".join(
            [f"- [{c['title']}]({c['url']})" for c in citations[:10]]
        )
        await adk.messages.create(
            task_id=params.task_id,
            content=TextContent(
                author="agent",
                content=citations_text
            )
        )
        logger.info(f"DeepResearchActivity: Found {len(citations)} citations from annotations")
    
    # Log web searches performed
    if web_searches:
        logger.info(f"DeepResearchActivity: Performed {len(web_searches)} web searches")
        for search in web_searches[:5]:  # Log first 5 searches
            logger.info(f"  - {search['type']}: {search['query']}")
    
    logger.info(f"DeepResearchActivity: Research completed, report length: {len(final_output)} chars")
    
    return DeepResearchResult(
        research_report=final_output,
        citations=citations
    )