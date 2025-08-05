import asyncio
import inspect
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter, ValidationError

# from agentex.lib.sdk.fastacp.types import BaseACPConfig
from agentex.lib.environment_variables import EnvironmentVariables, refreshed_environment_variables
from agentex.lib.types.acp import (
    PARAMS_MODEL_BY_METHOD,
    RPC_SYNC_METHODS,
    CancelTaskParams,
    CreateTaskParams,
    RPCMethod,
    SendEventParams,
    SendMessageParams,
)
from agentex.lib.types.json_rpc import JSONRPCError, JSONRPCRequest, JSONRPCResponse
from agentex.lib.types.task_message_updates import StreamTaskMessageFull, TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.utils.registration import register_agent

logger = make_logger(__name__)

# Create a TypeAdapter for TaskMessageUpdate validation
task_message_update_adapter = TypeAdapter(TaskMessageUpdate)


class BaseACPServer(FastAPI):
    """
    AsyncAgentACP provides RPC-style hooks for agent events and commands asynchronously.
    All methods follow JSON-RPC 2.0 format.

    Available methods:
    - event/send → Send a message to a task
    - task/cancel → Cancel a task
    - task/approve → Approve a task
    """

    def __init__(self):
        super().__init__(lifespan=self.get_lifespan_function())

        self.get("/healthz")(self._healthz)
        self.post("/api")(self._handle_jsonrpc)

        # Method handlers
        self._handlers: dict[RPCMethod, Callable] = {}

    @classmethod
    def create(cls):
        """Create and initialize BaseACPServer instance"""
        instance = cls()
        instance._setup_handlers()
        return instance

    def _setup_handlers(self):
        """Set up default handlers - override in subclasses"""
        # Base class has no default handlers
        pass

    def get_lifespan_function(self):
        @asynccontextmanager
        async def lifespan_context(app: FastAPI):
            env_vars = EnvironmentVariables.refresh()
            if env_vars.AGENTEX_BASE_URL:
                await register_agent(env_vars)
            else:
                logger.warning("AGENTEX_BASE_URL not set, skipping agent registration")

            yield

        return lifespan_context

    async def _healthz(self):
        """Health check endpoint"""
        return {"status": "healthy"}

    def _wrap_handler(self, fn: Callable[..., Awaitable[Any]]):
        """Wraps handler functions to provide JSON-RPC 2.0 response format"""

        async def wrapper(*args, **kwargs) -> Any:
            return await fn(*args, **kwargs)

        return wrapper

    async def _handle_jsonrpc(self, request: Request):
        """Main JSON-RPC endpoint handler"""
        rpc_request = None
        try:
            data = await request.json()
            rpc_request = JSONRPCRequest(**data)

            # Check if the request is authenticated
            if refreshed_environment_variables and getattr(refreshed_environment_variables, "AGENT_API_KEY", None):
                authorization_header = request.headers.get("x-agent-api-key")
                if authorization_header != refreshed_environment_variables.AGENT_API_KEY:
                    return JSONRPCResponse(
                        id=rpc_request.id,
                        error=JSONRPCError(code=-32601, message="Unauthorized"),
                    )


            # Check if method is valid first
            try:
                method = RPCMethod(rpc_request.method)
            except ValueError:
                logger.error(f"Method {rpc_request.method} was invalid")
                return JSONRPCResponse(
                    id=rpc_request.id,
                    error=JSONRPCError(
                        code=-32601, message=f"Method {rpc_request.method} not found"
                    ),
                )

            if method not in self._handlers or self._handlers[method] is None:
                logger.error(f"Method {method} not found on existing ACP server")
                return JSONRPCResponse(
                    id=rpc_request.id,
                    error=JSONRPCError(
                        code=-32601, message=f"Method {method} not found"
                    ),
                )

            # Parse params into appropriate model based on method
            params_model = PARAMS_MODEL_BY_METHOD[method]
            params = params_model.model_validate(rpc_request.params)

            if method in RPC_SYNC_METHODS:
                handler = self._handlers[method]
                result = await handler(params)

                if rpc_request.id is None:
                    # Seems like you should return None for notifications
                    return None
                else:
                    # Handle streaming vs non-streaming for MESSAGE_SEND
                    if method == RPCMethod.MESSAGE_SEND and isinstance(
                        result, AsyncGenerator
                    ):
                        return await self._handle_streaming_response(
                            rpc_request.id, result
                        )
                    else:
                        if isinstance(result, BaseModel):
                            result = result.model_dump()
                        return JSONRPCResponse(id=rpc_request.id, result=result)
            else:
                # If this is a notification (no request ID), process in background and return immediately
                if rpc_request.id is None:
                    asyncio.create_task(self._process_notification(method, params))
                    return JSONRPCResponse(id=None)

                # For regular requests, start processing in background but return immediately
                asyncio.create_task(
                    self._process_request(rpc_request.id, method, params)
                )

                # Return immediate acknowledgment
                return JSONRPCResponse(
                    id=rpc_request.id, result={"status": "processing"}
                )

        except Exception as e:
            logger.error(f"Error handling JSON-RPC request: {e}", exc_info=True)
            request_id = None
            if rpc_request is not None:
                request_id = rpc_request.id
            return JSONRPCResponse(
                id=request_id,
                error=JSONRPCError(code=-32603, message=str(e)).model_dump(),
            )

    async def _handle_streaming_response(
        self, request_id: int | str, async_gen: AsyncGenerator
    ):
        """Handle streaming response by formatting TaskMessageUpdate objects as JSON-RPC stream"""

        async def generate_json_rpc_stream():
            try:
                async for chunk in async_gen:
                    # Each chunk should be a TaskMessageUpdate object
                    # Validate using Pydantic's TypeAdapter to ensure it's a proper TaskMessageUpdate
                    try:
                        # This will validate that chunk conforms to the TaskMessageUpdate union type
                        validated_chunk = task_message_update_adapter.validate_python(
                            chunk
                        )
                        # Use mode="json" to properly serialize datetime objects
                        chunk_data = validated_chunk.model_dump(mode="json")
                    except ValidationError as e:
                        raise TypeError(
                            f"Streaming chunks must be TaskMessageUpdate objects. Validation error: {e}"
                        ) from e
                    except Exception as e:
                        raise TypeError(
                            f"Streaming chunks must be TaskMessageUpdate objects, got {type(chunk)}: {e}"
                        ) from e

                    # Wrap in JSON-RPC response format
                    response = JSONRPCResponse(id=request_id, result=chunk_data)
                    # Use model_dump_json() which handles datetime serialization automatically
                    yield f"{response.model_dump_json()}\n"

            except Exception as e:
                logger.error(f"Error in streaming response: {e}", exc_info=True)
                error_response = JSONRPCResponse(
                    id=request_id,
                    error=JSONRPCError(code=-32603, message=str(e)).model_dump(),
                )
                yield f"{error_response.model_dump_json()}\n"

        return StreamingResponse(
            generate_json_rpc_stream(),
            media_type="application/x-ndjson",  # Newline Delimited JSON
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    async def _process_notification(self, method: RPCMethod, params: Any):
        """Process a notification (request with no ID) in the background"""
        try:
            handler = self._handlers[method]
            await handler(params)
        except Exception as e:
            logger.error(f"Error processing notification {method}: {e}", exc_info=True)

    async def _process_request(
        self, request_id: int | str, method: RPCMethod, params: Any
    ):
        """Process a request in the background"""
        try:
            handler = self._handlers[method]
            await handler(params)
            # Note: In a real implementation, you might want to store the result somewhere
            # or notify the client through a different mechanism
            logger.info(
                f"Successfully processed request {request_id} for method {method}"
            )
        except Exception as e:
            logger.error(
                f"Error processing request {request_id} for method {method}: {e}",
                exc_info=True,
            )

    """
    Define all possible decorators to be overriden and implemented by each ACP implementation
    Then the users can override the default handlers by implementing their own handlers

    ACP Type: Agentic
    Decorators:
    - on_task_create
    - on_task_event_send
    - on_task_cancel

    ACP Type: Sync
    Decorators:
    - on_message_send
    """

    # Type: Agentic
    def on_task_create(self, fn: Callable[[CreateTaskParams], Awaitable[Any]]):
        """Handle task/init method"""
        wrapped = self._wrap_handler(fn)
        self._handlers[RPCMethod.TASK_CREATE] = wrapped
        return fn

    # Type: Agentic
    def on_task_event_send(self, fn: Callable[[SendEventParams], Awaitable[Any]]):
        """Handle event/send method"""

        async def wrapped_handler(params: SendEventParams):
            # # # Send message to client first most of the time
            # ## But, sometimes you may want to process the message first
            # ## and then send a message to the client
            # await agentex.interactions.send_messages_to_client(
            #     task_id=params.task_id,
            #     messages=[params.message]
            # )
            return await fn(params)

        wrapped = self._wrap_handler(wrapped_handler)
        self._handlers[RPCMethod.EVENT_SEND] = wrapped
        return fn

    # Type: Agentic
    def on_task_cancel(self, fn: Callable[[CancelTaskParams], Awaitable[Any]]):
        """Handle task/cancel method"""
        wrapped = self._wrap_handler(fn)
        self._handlers[RPCMethod.TASK_CANCEL] = wrapped
        return fn

    # Type: Sync
    def on_message_send(
        self,
        fn: Callable[
            [SendMessageParams],
            Awaitable[TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]],
        ],
    ):
        """Handle message/send method - supports both single and streaming responses

        For non-streaming: return a single TaskMessage
        For streaming: return an AsyncGenerator that yields TaskMessageUpdate objects
        """

        async def message_send_wrapper(params: SendMessageParams):
            """Special wrapper for message_send that handles both regular async functions and async generators"""
            # Check if the function is an async generator function

            # Regardless of whether the Agent developer implemented an Async generator or not, we will always turn the function into an async generator and yield SSE events back tot he Agentex server so there is only one way for it to process the response. Then, based on the client's desire to stream or not, the Agentex server will either yield back the async generator objects directly (if streaming) or aggregate the content into a list of TaskMessageContents and to dispatch to the client. This basically gives the Agentex server the flexibility to handle both cases itself.
            
            if inspect.isasyncgenfunction(fn):
                # The client wants streaming, an async generator already streams the content, so just return it
                return fn(params)
            else:
                # The client wants streaming, but the function is not an async generator, so we turn it into one and yield each TaskMessageContent as a StreamTaskMessageFull which will be streamed to the client by the Agentex server.
                task_message_content_response = await fn(params)
                if isinstance(task_message_content_response, list):
                    task_message_content_list = task_message_content_response
                else:
                    task_message_content_list = [task_message_content_response]

                async def async_generator(task_message_content_list: list[TaskMessageContent]):
                    for i, task_message_content in enumerate(task_message_content_list):
                        yield StreamTaskMessageFull(index=i, content=task_message_content)

                return async_generator(task_message_content_list)

        self._handlers[RPCMethod.MESSAGE_SEND] = message_send_wrapper
        return fn

    """
    End of Decorators
    """

    """
    ACP Server Lifecycle Methods
    """

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs):
        """Start the Uvicorn server for async handlers."""
        uvicorn.run(self, host=host, port=port, **kwargs)

    