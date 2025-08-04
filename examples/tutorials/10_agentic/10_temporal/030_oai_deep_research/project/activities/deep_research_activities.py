"""Custom activities for deep research workflow."""
import re
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

@activity.defn(name="run_deep_research")
async def run_deep_research(params: DeepResearchParams) -> DeepResearchResult:
    """Run deep research using OpenAI agents library directly."""
    logger.info("DeepResearchActivity: Starting deep research")
    logger.info(f"DeepResearchActivity: Task ID: {params.task_id}")
    logger.info(f"DeepResearchActivity: Instructions length: {len(params.enriched_instructions)}")
    logger.info(f"DeepResearchActivity: Model: {params.research_model}")
    
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
    
    # Run agent with streaming
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
        if not final_output and hasattr(result, 'final_output'):
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
    
    # Ensure we have some output
    if not final_output:
        logger.warning("DeepResearchActivity: No final output captured, using placeholder")
        final_output = "Research completed but no output was captured. Please check the logs."
    
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