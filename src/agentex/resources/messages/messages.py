# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal

import httpx

from .batch import (
    BatchResource,
    AsyncBatchResource,
    BatchResourceWithRawResponse,
    AsyncBatchResourceWithRawResponse,
    BatchResourceWithStreamingResponse,
    AsyncBatchResourceWithStreamingResponse,
)
from ...types import (
    message_list_params,
    message_create_params,
    message_update_params,
    message_list_paginated_params,
)
from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.task_message import TaskMessage
from ...types.message_list_response import MessageListResponse
from ...types.task_message_content_param import TaskMessageContentParam
from ...types.message_list_paginated_response import MessageListPaginatedResponse

__all__ = ["MessagesResource", "AsyncMessagesResource"]


class MessagesResource(SyncAPIResource):
    @cached_property
    def batch(self) -> BatchResource:
        return BatchResource(self._client)

    @cached_property
    def with_raw_response(self) -> MessagesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return MessagesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> MessagesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return MessagesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        content: TaskMessageContentParam,
        task_id: str,
        streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskMessage:
        """
        Create Message

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/messages",
            body=maybe_transform(
                {
                    "content": content,
                    "task_id": task_id,
                    "streaming_status": streaming_status,
                },
                message_create_params.MessageCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TaskMessage,
        )

    def retrieve(
        self,
        message_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskMessage:
        """
        Get Message

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not message_id:
            raise ValueError(f"Expected a non-empty value for `message_id` but received {message_id!r}")
        return self._get(
            f"/messages/{message_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TaskMessage,
        )

    def update(
        self,
        message_id: str,
        *,
        content: TaskMessageContentParam,
        task_id: str,
        streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskMessage:
        """
        Update Message

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not message_id:
            raise ValueError(f"Expected a non-empty value for `message_id` but received {message_id!r}")
        return self._put(
            f"/messages/{message_id}",
            body=maybe_transform(
                {
                    "content": content,
                    "task_id": task_id,
                    "streaming_status": streaming_status,
                },
                message_update_params.MessageUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TaskMessage,
        )

    def list(
        self,
        *,
        task_id: str,
        filters: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        order_by: Optional[str] | Omit = omit,
        order_direction: str | Omit = omit,
        page_number: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> MessageListResponse:
        """
        List messages for a task with offset-based pagination.

        For cursor-based pagination with infinite scroll support, use
        /messages/paginated.

        Args:
          task_id: The task ID

          filters: JSON-encoded array of TaskMessageEntityFilter objects.

              Schema: {
              "$defs": {
                  "DataContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "data",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `data`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "data": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the data message.",
                        "title": "Data"
                      }
                    },
                    "title": "DataContentEntityOptional",
                    "type": "object"
                  },
                  "FileAttachmentEntity": {
                    "description": "Represents a file attachment in messages.",
                    "properties": {
                      "file_id": {
                        "description": "The unique ID of the attached file",
                        "title": "File Id",
                        "type": "string"
                      },
                      "name": {
                        "description": "The name of the file",
                        "title": "Name",
                        "type": "string"
                      },
                      "size": {
                        "description": "The size of the file in bytes",
                        "title": "Size",
                        "type": "integer"
                      },
                      "type": {
                        "description": "The MIME type or content type of the file",
                        "title": "Type",
                        "type": "string"
                      }
                    },
                    "required": [
                      "file_id",
                      "name",
                      "size",
                      "type"
                    ],
                    "title": "FileAttachmentEntity",
                    "type": "object"
                  },
                  "MessageAuthor": {
                    "enum": [
                      "user",
                      "agent"
                    ],
                    "title": "MessageAuthor",
                    "type": "string"
                  },
                  "MessageStyle": {
                    "enum": [
                      "static",
                      "active"
                    ],
                    "title": "MessageStyle",
                    "type": "string"
                  },
                  "ReasoningContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "reasoning",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `reasoning`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "summary": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "A list of short reasoning summaries",
                        "title": "Summary"
                      },
                      "content": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The reasoning content or chain-of-thought text",
                        "title": "Content"
                      }
                    },
                    "title": "ReasoningContentEntityOptional",
                    "type": "object"
                  },
                  "TextContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "text",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `text`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "format": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/TextFormat"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The format of the message. This is used by the client to determine how to display the message."
                      },
                      "content": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the text message.",
                        "title": "Content"
                      },
                      "attachments": {
                        "anyOf": [
                          {
                            "items": {
                              "$ref":
              "#/$defs/FileAttachmentEntity"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "Optional list of file attachments with structured metadata.",
                        "title": "Attachments"
                      }
                    },
                    "title": "TextContentEntityOptional",
                    "type": "object"
                  },
                  "TextFormat": {
                    "enum": [
                      "markdown",
                      "plain",
                      "code"
                    ],
                    "title": "TextFormat",
                    "type": "string"
                  },
                  "ToolRequestContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_request",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_request`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being requested.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being requested.",
                        "title": "Name"
                      },
                      "arguments": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The arguments to the tool.",
                        "title": "Arguments"
                      }
                    },
                    "title": "ToolRequestContentEntityOptional",
                    "type": "object"
                  },
                  "ToolResponseContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_response",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_response`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being responded to.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being responded to.",
                        "title": "Name"
                      },
                      "content": {
                        "anyOf": [
                          {},
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The result of the tool.",
                        "title": "Content"
                      }
                    },
                    "title": "ToolResponseContentEntityOptional",
                    "type": "object"
                  }
                },
                "description": "Filter model for TaskMessage - all fields optional for flexible filtering.\n\nThe `exclude` field determines whether this filter is inclusionary or exclusionary.\nWhen multiple filters are provided:\n- Inclusionary filters (exclude=False) are OR'd together\n- Exclusionary filters (exclude=True) are OR'd together and negated with $nor\n- The two groups are AND'd: (include1 OR include2) AND NOT (exclude1 OR exclude2)",
                "properties": {
                  "content": {
                    "anyOf": [
                      {
                        "$ref":
              "#/$defs/ToolRequestContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/DataContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/TextContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ToolResponseContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ReasoningContentEntityOptional" }, { "type": "null" } ], "default":
              null, "description": "Filter by message content", "title": "Content" },
              "streaming_status": { "anyOf": [ { "enum": [ "IN_PROGRESS", "DONE" ], "type":
              "string" }, { "type": "null" } ], "default": null, "description": "Filter by
              streaming status", "title": "Streaming Status" }, "exclude": { "default": false,
              "description": "If true, this filter excludes matching messages", "title":
              "Exclude", "type": "boolean" } }, "title": "TaskMessageEntityFilter", "type":
              "object" }

              Each filter can include:

              - `content`: Filter by message content (type, author, data fields)
              - `streaming_status`: Filter by status ("IN_PROGRESS" or "DONE")
              - `exclude`: If true, excludes matching messages (default: false)

              Multiple filters are combined: inclusionary filters (exclude=false) are OR'd
              together, exclusionary filters (exclude=true) are OR'd and negated, then both
              groups are AND'd.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/messages",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "task_id": task_id,
                        "filters": filters,
                        "limit": limit,
                        "order_by": order_by,
                        "order_direction": order_direction,
                        "page_number": page_number,
                    },
                    message_list_params.MessageListParams,
                ),
            ),
            cast_to=MessageListResponse,
        )

    def list_paginated(
        self,
        *,
        task_id: str,
        cursor: Optional[str] | Omit = omit,
        direction: Literal["older", "newer"] | Omit = omit,
        filters: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> MessageListPaginatedResponse:
        """
        List messages for a task with cursor-based pagination.

        This endpoint is designed for infinite scroll UIs where new messages may arrive
        while paginating through older ones.

        Args: task_id: The task ID to filter messages by limit: Maximum number of
        messages to return (default: 50) cursor: Opaque cursor string for pagination.
        Pass the `next_cursor` from a previous response to get the next page. direction:
        Pagination direction - "older" to get older messages (default), "newer" to get
        newer messages.

        Returns: PaginatedMessagesResponse with: - data: List of messages (newest first
        when direction="older") - next_cursor: Cursor for fetching the next page (null
        if no more pages) - has_more: Whether there are more messages to fetch

        Example: First request: GET /messages/paginated?task_id=xxx&limit=50 Next page:
        GET /messages/paginated?task_id=xxx&limit=50&cursor=<next_cursor>

        Args:
          task_id: The task ID

          filters: JSON-encoded array of TaskMessageEntityFilter objects.

              Schema: {
              "$defs": {
                  "DataContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "data",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `data`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "data": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the data message.",
                        "title": "Data"
                      }
                    },
                    "title": "DataContentEntityOptional",
                    "type": "object"
                  },
                  "FileAttachmentEntity": {
                    "description": "Represents a file attachment in messages.",
                    "properties": {
                      "file_id": {
                        "description": "The unique ID of the attached file",
                        "title": "File Id",
                        "type": "string"
                      },
                      "name": {
                        "description": "The name of the file",
                        "title": "Name",
                        "type": "string"
                      },
                      "size": {
                        "description": "The size of the file in bytes",
                        "title": "Size",
                        "type": "integer"
                      },
                      "type": {
                        "description": "The MIME type or content type of the file",
                        "title": "Type",
                        "type": "string"
                      }
                    },
                    "required": [
                      "file_id",
                      "name",
                      "size",
                      "type"
                    ],
                    "title": "FileAttachmentEntity",
                    "type": "object"
                  },
                  "MessageAuthor": {
                    "enum": [
                      "user",
                      "agent"
                    ],
                    "title": "MessageAuthor",
                    "type": "string"
                  },
                  "MessageStyle": {
                    "enum": [
                      "static",
                      "active"
                    ],
                    "title": "MessageStyle",
                    "type": "string"
                  },
                  "ReasoningContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "reasoning",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `reasoning`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "summary": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "A list of short reasoning summaries",
                        "title": "Summary"
                      },
                      "content": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The reasoning content or chain-of-thought text",
                        "title": "Content"
                      }
                    },
                    "title": "ReasoningContentEntityOptional",
                    "type": "object"
                  },
                  "TextContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "text",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `text`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "format": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/TextFormat"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The format of the message. This is used by the client to determine how to display the message."
                      },
                      "content": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the text message.",
                        "title": "Content"
                      },
                      "attachments": {
                        "anyOf": [
                          {
                            "items": {
                              "$ref":
              "#/$defs/FileAttachmentEntity"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "Optional list of file attachments with structured metadata.",
                        "title": "Attachments"
                      }
                    },
                    "title": "TextContentEntityOptional",
                    "type": "object"
                  },
                  "TextFormat": {
                    "enum": [
                      "markdown",
                      "plain",
                      "code"
                    ],
                    "title": "TextFormat",
                    "type": "string"
                  },
                  "ToolRequestContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_request",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_request`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being requested.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being requested.",
                        "title": "Name"
                      },
                      "arguments": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The arguments to the tool.",
                        "title": "Arguments"
                      }
                    },
                    "title": "ToolRequestContentEntityOptional",
                    "type": "object"
                  },
                  "ToolResponseContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_response",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_response`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being responded to.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being responded to.",
                        "title": "Name"
                      },
                      "content": {
                        "anyOf": [
                          {},
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The result of the tool.",
                        "title": "Content"
                      }
                    },
                    "title": "ToolResponseContentEntityOptional",
                    "type": "object"
                  }
                },
                "description": "Filter model for TaskMessage - all fields optional for flexible filtering.\n\nThe `exclude` field determines whether this filter is inclusionary or exclusionary.\nWhen multiple filters are provided:\n- Inclusionary filters (exclude=False) are OR'd together\n- Exclusionary filters (exclude=True) are OR'd together and negated with $nor\n- The two groups are AND'd: (include1 OR include2) AND NOT (exclude1 OR exclude2)",
                "properties": {
                  "content": {
                    "anyOf": [
                      {
                        "$ref":
              "#/$defs/ToolRequestContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/DataContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/TextContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ToolResponseContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ReasoningContentEntityOptional" }, { "type": "null" } ], "default":
              null, "description": "Filter by message content", "title": "Content" },
              "streaming_status": { "anyOf": [ { "enum": [ "IN_PROGRESS", "DONE" ], "type":
              "string" }, { "type": "null" } ], "default": null, "description": "Filter by
              streaming status", "title": "Streaming Status" }, "exclude": { "default": false,
              "description": "If true, this filter excludes matching messages", "title":
              "Exclude", "type": "boolean" } }, "title": "TaskMessageEntityFilter", "type":
              "object" }

              Each filter can include:

              - `content`: Filter by message content (type, author, data fields)
              - `streaming_status`: Filter by status ("IN_PROGRESS" or "DONE")
              - `exclude`: If true, excludes matching messages (default: false)

              Multiple filters are combined: inclusionary filters (exclude=false) are OR'd
              together, exclusionary filters (exclude=true) are OR'd and negated, then both
              groups are AND'd.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/messages/paginated",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "task_id": task_id,
                        "cursor": cursor,
                        "direction": direction,
                        "filters": filters,
                        "limit": limit,
                    },
                    message_list_paginated_params.MessageListPaginatedParams,
                ),
            ),
            cast_to=MessageListPaginatedResponse,
        )


class AsyncMessagesResource(AsyncAPIResource):
    @cached_property
    def batch(self) -> AsyncBatchResource:
        return AsyncBatchResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncMessagesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#accessing-raw-response-data-eg-headers
        """
        return AsyncMessagesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncMessagesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/scaleapi/scale-agentex-python#with_streaming_response
        """
        return AsyncMessagesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        content: TaskMessageContentParam,
        task_id: str,
        streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskMessage:
        """
        Create Message

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/messages",
            body=await async_maybe_transform(
                {
                    "content": content,
                    "task_id": task_id,
                    "streaming_status": streaming_status,
                },
                message_create_params.MessageCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TaskMessage,
        )

    async def retrieve(
        self,
        message_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskMessage:
        """
        Get Message

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not message_id:
            raise ValueError(f"Expected a non-empty value for `message_id` but received {message_id!r}")
        return await self._get(
            f"/messages/{message_id}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TaskMessage,
        )

    async def update(
        self,
        message_id: str,
        *,
        content: TaskMessageContentParam,
        task_id: str,
        streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TaskMessage:
        """
        Update Message

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not message_id:
            raise ValueError(f"Expected a non-empty value for `message_id` but received {message_id!r}")
        return await self._put(
            f"/messages/{message_id}",
            body=await async_maybe_transform(
                {
                    "content": content,
                    "task_id": task_id,
                    "streaming_status": streaming_status,
                },
                message_update_params.MessageUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TaskMessage,
        )

    async def list(
        self,
        *,
        task_id: str,
        filters: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        order_by: Optional[str] | Omit = omit,
        order_direction: str | Omit = omit,
        page_number: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> MessageListResponse:
        """
        List messages for a task with offset-based pagination.

        For cursor-based pagination with infinite scroll support, use
        /messages/paginated.

        Args:
          task_id: The task ID

          filters: JSON-encoded array of TaskMessageEntityFilter objects.

              Schema: {
              "$defs": {
                  "DataContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "data",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `data`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "data": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the data message.",
                        "title": "Data"
                      }
                    },
                    "title": "DataContentEntityOptional",
                    "type": "object"
                  },
                  "FileAttachmentEntity": {
                    "description": "Represents a file attachment in messages.",
                    "properties": {
                      "file_id": {
                        "description": "The unique ID of the attached file",
                        "title": "File Id",
                        "type": "string"
                      },
                      "name": {
                        "description": "The name of the file",
                        "title": "Name",
                        "type": "string"
                      },
                      "size": {
                        "description": "The size of the file in bytes",
                        "title": "Size",
                        "type": "integer"
                      },
                      "type": {
                        "description": "The MIME type or content type of the file",
                        "title": "Type",
                        "type": "string"
                      }
                    },
                    "required": [
                      "file_id",
                      "name",
                      "size",
                      "type"
                    ],
                    "title": "FileAttachmentEntity",
                    "type": "object"
                  },
                  "MessageAuthor": {
                    "enum": [
                      "user",
                      "agent"
                    ],
                    "title": "MessageAuthor",
                    "type": "string"
                  },
                  "MessageStyle": {
                    "enum": [
                      "static",
                      "active"
                    ],
                    "title": "MessageStyle",
                    "type": "string"
                  },
                  "ReasoningContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "reasoning",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `reasoning`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "summary": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "A list of short reasoning summaries",
                        "title": "Summary"
                      },
                      "content": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The reasoning content or chain-of-thought text",
                        "title": "Content"
                      }
                    },
                    "title": "ReasoningContentEntityOptional",
                    "type": "object"
                  },
                  "TextContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "text",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `text`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "format": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/TextFormat"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The format of the message. This is used by the client to determine how to display the message."
                      },
                      "content": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the text message.",
                        "title": "Content"
                      },
                      "attachments": {
                        "anyOf": [
                          {
                            "items": {
                              "$ref":
              "#/$defs/FileAttachmentEntity"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "Optional list of file attachments with structured metadata.",
                        "title": "Attachments"
                      }
                    },
                    "title": "TextContentEntityOptional",
                    "type": "object"
                  },
                  "TextFormat": {
                    "enum": [
                      "markdown",
                      "plain",
                      "code"
                    ],
                    "title": "TextFormat",
                    "type": "string"
                  },
                  "ToolRequestContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_request",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_request`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being requested.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being requested.",
                        "title": "Name"
                      },
                      "arguments": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The arguments to the tool.",
                        "title": "Arguments"
                      }
                    },
                    "title": "ToolRequestContentEntityOptional",
                    "type": "object"
                  },
                  "ToolResponseContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_response",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_response`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being responded to.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being responded to.",
                        "title": "Name"
                      },
                      "content": {
                        "anyOf": [
                          {},
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The result of the tool.",
                        "title": "Content"
                      }
                    },
                    "title": "ToolResponseContentEntityOptional",
                    "type": "object"
                  }
                },
                "description": "Filter model for TaskMessage - all fields optional for flexible filtering.\n\nThe `exclude` field determines whether this filter is inclusionary or exclusionary.\nWhen multiple filters are provided:\n- Inclusionary filters (exclude=False) are OR'd together\n- Exclusionary filters (exclude=True) are OR'd together and negated with $nor\n- The two groups are AND'd: (include1 OR include2) AND NOT (exclude1 OR exclude2)",
                "properties": {
                  "content": {
                    "anyOf": [
                      {
                        "$ref":
              "#/$defs/ToolRequestContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/DataContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/TextContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ToolResponseContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ReasoningContentEntityOptional" }, { "type": "null" } ], "default":
              null, "description": "Filter by message content", "title": "Content" },
              "streaming_status": { "anyOf": [ { "enum": [ "IN_PROGRESS", "DONE" ], "type":
              "string" }, { "type": "null" } ], "default": null, "description": "Filter by
              streaming status", "title": "Streaming Status" }, "exclude": { "default": false,
              "description": "If true, this filter excludes matching messages", "title":
              "Exclude", "type": "boolean" } }, "title": "TaskMessageEntityFilter", "type":
              "object" }

              Each filter can include:

              - `content`: Filter by message content (type, author, data fields)
              - `streaming_status`: Filter by status ("IN_PROGRESS" or "DONE")
              - `exclude`: If true, excludes matching messages (default: false)

              Multiple filters are combined: inclusionary filters (exclude=false) are OR'd
              together, exclusionary filters (exclude=true) are OR'd and negated, then both
              groups are AND'd.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/messages",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "task_id": task_id,
                        "filters": filters,
                        "limit": limit,
                        "order_by": order_by,
                        "order_direction": order_direction,
                        "page_number": page_number,
                    },
                    message_list_params.MessageListParams,
                ),
            ),
            cast_to=MessageListResponse,
        )

    async def list_paginated(
        self,
        *,
        task_id: str,
        cursor: Optional[str] | Omit = omit,
        direction: Literal["older", "newer"] | Omit = omit,
        filters: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> MessageListPaginatedResponse:
        """
        List messages for a task with cursor-based pagination.

        This endpoint is designed for infinite scroll UIs where new messages may arrive
        while paginating through older ones.

        Args: task_id: The task ID to filter messages by limit: Maximum number of
        messages to return (default: 50) cursor: Opaque cursor string for pagination.
        Pass the `next_cursor` from a previous response to get the next page. direction:
        Pagination direction - "older" to get older messages (default), "newer" to get
        newer messages.

        Returns: PaginatedMessagesResponse with: - data: List of messages (newest first
        when direction="older") - next_cursor: Cursor for fetching the next page (null
        if no more pages) - has_more: Whether there are more messages to fetch

        Example: First request: GET /messages/paginated?task_id=xxx&limit=50 Next page:
        GET /messages/paginated?task_id=xxx&limit=50&cursor=<next_cursor>

        Args:
          task_id: The task ID

          filters: JSON-encoded array of TaskMessageEntityFilter objects.

              Schema: {
              "$defs": {
                  "DataContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "data",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `data`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "data": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the data message.",
                        "title": "Data"
                      }
                    },
                    "title": "DataContentEntityOptional",
                    "type": "object"
                  },
                  "FileAttachmentEntity": {
                    "description": "Represents a file attachment in messages.",
                    "properties": {
                      "file_id": {
                        "description": "The unique ID of the attached file",
                        "title": "File Id",
                        "type": "string"
                      },
                      "name": {
                        "description": "The name of the file",
                        "title": "Name",
                        "type": "string"
                      },
                      "size": {
                        "description": "The size of the file in bytes",
                        "title": "Size",
                        "type": "integer"
                      },
                      "type": {
                        "description": "The MIME type or content type of the file",
                        "title": "Type",
                        "type": "string"
                      }
                    },
                    "required": [
                      "file_id",
                      "name",
                      "size",
                      "type"
                    ],
                    "title": "FileAttachmentEntity",
                    "type": "object"
                  },
                  "MessageAuthor": {
                    "enum": [
                      "user",
                      "agent"
                    ],
                    "title": "MessageAuthor",
                    "type": "string"
                  },
                  "MessageStyle": {
                    "enum": [
                      "static",
                      "active"
                    ],
                    "title": "MessageStyle",
                    "type": "string"
                  },
                  "ReasoningContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "reasoning",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `reasoning`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "summary": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "A list of short reasoning summaries",
                        "title": "Summary"
                      },
                      "content": {
                        "anyOf": [
                          {
                            "items": {
                              "type": "string"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The reasoning content or chain-of-thought text",
                        "title": "Content"
                      }
                    },
                    "title": "ReasoningContentEntityOptional",
                    "type": "object"
                  },
                  "TextContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "text",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `text`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "format": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/TextFormat"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The format of the message. This is used by the client to determine how to display the message."
                      },
                      "content": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The contents of the text message.",
                        "title": "Content"
                      },
                      "attachments": {
                        "anyOf": [
                          {
                            "items": {
                              "$ref":
              "#/$defs/FileAttachmentEntity"
                            },
                            "type": "array"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "Optional list of file attachments with structured metadata.",
                        "title": "Attachments"
                      }
                    },
                    "title": "TextContentEntityOptional",
                    "type": "object"
                  },
                  "TextFormat": {
                    "enum": [
                      "markdown",
                      "plain",
                      "code"
                    ],
                    "title": "TextFormat",
                    "type": "string"
                  },
                  "ToolRequestContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_request",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_request`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being requested.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being requested.",
                        "title": "Name"
                      },
                      "arguments": {
                        "anyOf": [
                          {
                            "additionalProperties": true,
                            "type": "object"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The arguments to the tool.",
                        "title": "Arguments"
                      }
                    },
                    "title": "ToolRequestContentEntityOptional",
                    "type": "object"
                  },
                  "ToolResponseContentEntityOptional": {
                    "properties": {
                      "type": {
                        "anyOf": [
                          {
                            "const": "tool_response",
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The type of the message, in this case `tool_response`.",
                        "title": "Type"
                      },
                      "author": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageAuthor"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The role of the messages author, in this case `system`, `user`, `assistant`, or `tool`."
                      },
                      "style": {
                        "anyOf": [
                          {
                            "$ref":
              "#/$defs/MessageStyle"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The style of the message. This is used by the client to determine how to display the message."
                      },
                      "tool_call_id": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The ID of the tool call that is being responded to.",
                        "title": "Tool Call Id"
                      },
                      "name": {
                        "anyOf": [
                          {
                            "type": "string"
                          },
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The name of the tool that is being responded to.",
                        "title": "Name"
                      },
                      "content": {
                        "anyOf": [
                          {},
                          {
                            "type": "null"
                          }
                        ],
                        "default": null,
                        "description": "The result of the tool.",
                        "title": "Content"
                      }
                    },
                    "title": "ToolResponseContentEntityOptional",
                    "type": "object"
                  }
                },
                "description": "Filter model for TaskMessage - all fields optional for flexible filtering.\n\nThe `exclude` field determines whether this filter is inclusionary or exclusionary.\nWhen multiple filters are provided:\n- Inclusionary filters (exclude=False) are OR'd together\n- Exclusionary filters (exclude=True) are OR'd together and negated with $nor\n- The two groups are AND'd: (include1 OR include2) AND NOT (exclude1 OR exclude2)",
                "properties": {
                  "content": {
                    "anyOf": [
                      {
                        "$ref":
              "#/$defs/ToolRequestContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/DataContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/TextContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ToolResponseContentEntityOptional"
                      },
                      {
                        "$ref":
              "#/$defs/ReasoningContentEntityOptional" }, { "type": "null" } ], "default":
              null, "description": "Filter by message content", "title": "Content" },
              "streaming_status": { "anyOf": [ { "enum": [ "IN_PROGRESS", "DONE" ], "type":
              "string" }, { "type": "null" } ], "default": null, "description": "Filter by
              streaming status", "title": "Streaming Status" }, "exclude": { "default": false,
              "description": "If true, this filter excludes matching messages", "title":
              "Exclude", "type": "boolean" } }, "title": "TaskMessageEntityFilter", "type":
              "object" }

              Each filter can include:

              - `content`: Filter by message content (type, author, data fields)
              - `streaming_status`: Filter by status ("IN_PROGRESS" or "DONE")
              - `exclude`: If true, excludes matching messages (default: false)

              Multiple filters are combined: inclusionary filters (exclude=false) are OR'd
              together, exclusionary filters (exclude=true) are OR'd and negated, then both
              groups are AND'd.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/messages/paginated",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "task_id": task_id,
                        "cursor": cursor,
                        "direction": direction,
                        "filters": filters,
                        "limit": limit,
                    },
                    message_list_paginated_params.MessageListPaginatedParams,
                ),
            ),
            cast_to=MessageListPaginatedResponse,
        )


class MessagesResourceWithRawResponse:
    def __init__(self, messages: MessagesResource) -> None:
        self._messages = messages

        self.create = to_raw_response_wrapper(
            messages.create,
        )
        self.retrieve = to_raw_response_wrapper(
            messages.retrieve,
        )
        self.update = to_raw_response_wrapper(
            messages.update,
        )
        self.list = to_raw_response_wrapper(
            messages.list,
        )
        self.list_paginated = to_raw_response_wrapper(
            messages.list_paginated,
        )

    @cached_property
    def batch(self) -> BatchResourceWithRawResponse:
        return BatchResourceWithRawResponse(self._messages.batch)


class AsyncMessagesResourceWithRawResponse:
    def __init__(self, messages: AsyncMessagesResource) -> None:
        self._messages = messages

        self.create = async_to_raw_response_wrapper(
            messages.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            messages.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            messages.update,
        )
        self.list = async_to_raw_response_wrapper(
            messages.list,
        )
        self.list_paginated = async_to_raw_response_wrapper(
            messages.list_paginated,
        )

    @cached_property
    def batch(self) -> AsyncBatchResourceWithRawResponse:
        return AsyncBatchResourceWithRawResponse(self._messages.batch)


class MessagesResourceWithStreamingResponse:
    def __init__(self, messages: MessagesResource) -> None:
        self._messages = messages

        self.create = to_streamed_response_wrapper(
            messages.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            messages.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            messages.update,
        )
        self.list = to_streamed_response_wrapper(
            messages.list,
        )
        self.list_paginated = to_streamed_response_wrapper(
            messages.list_paginated,
        )

    @cached_property
    def batch(self) -> BatchResourceWithStreamingResponse:
        return BatchResourceWithStreamingResponse(self._messages.batch)


class AsyncMessagesResourceWithStreamingResponse:
    def __init__(self, messages: AsyncMessagesResource) -> None:
        self._messages = messages

        self.create = async_to_streamed_response_wrapper(
            messages.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            messages.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            messages.update,
        )
        self.list = async_to_streamed_response_wrapper(
            messages.list,
        )
        self.list_paginated = async_to_streamed_response_wrapper(
            messages.list_paginated,
        )

    @cached_property
    def batch(self) -> AsyncBatchResourceWithStreamingResponse:
        return AsyncBatchResourceWithStreamingResponse(self._messages.batch)
