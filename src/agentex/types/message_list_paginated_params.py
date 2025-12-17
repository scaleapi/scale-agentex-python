# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["MessageListPaginatedParams"]


class MessageListPaginatedParams(TypedDict, total=False):
    task_id: Required[str]
    """The task ID"""

    cursor: Optional[str]

    direction: Literal["older", "newer"]

    filters: Optional[str]
    """JSON-encoded array of TaskMessageEntityFilter objects.

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
    """

    limit: int
