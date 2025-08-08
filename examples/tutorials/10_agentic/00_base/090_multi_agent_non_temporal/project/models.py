"""
Pydantic models for request/response data structures across all agents.
This provides type safety and clear documentation of expected data formats.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# Request Models

class OrchestratorRequest(BaseModel):
    """Request to the orchestrator agent to start a content creation workflow."""
    request: str = Field(..., description="The content creation request")
    rules: Optional[List[str]] = Field(default=None, description="Rules for content validation")
    target_format: Optional[str] = Field(default=None, description="Desired output format (HTML, MARKDOWN, JSON, TEXT, EMAIL)")


class CreatorRequest(BaseModel):
    """Request to the creator agent for content generation or revision."""
    request: str = Field(..., description="The content creation request")
    current_draft: Optional[str] = Field(default=None, description="Current draft for revision (if any)")
    feedback: Optional[List[str]] = Field(default=None, description="Feedback from critic for revision")
    orchestrator_task_id: Optional[str] = Field(default=None, description="Original orchestrator task ID for callback")


class CriticRequest(BaseModel):
    """Request to the critic agent for content review."""
    draft: str = Field(..., description="Content draft to review")
    rules: List[str] = Field(..., description="Rules to validate against")
    orchestrator_task_id: Optional[str] = Field(default=None, description="Original orchestrator task ID for callback")


class FormatterRequest(BaseModel):
    """Request to the formatter agent for content formatting."""
    content: str = Field(..., description="Content to format")
    target_format: str = Field(..., description="Target format (HTML, MARKDOWN, JSON, TEXT, EMAIL)")
    orchestrator_task_id: Optional[str] = Field(default=None, description="Original orchestrator task ID for callback")


# Response Models

class CreatorResponse(BaseModel):
    """Response from the creator agent."""
    agent: Literal["creator"] = Field(default="creator", description="Agent identifier")
    content: str = Field(..., description="Generated or revised content")
    task_id: str = Field(..., description="Task ID for this creation request")


class CriticResponse(BaseModel):
    """Response from the critic agent."""
    agent: Literal["critic"] = Field(default="critic", description="Agent identifier")
    feedback: List[str] = Field(..., description="List of feedback items (empty if approved)")
    approval_status: str = Field(..., description="Approval status (approved/needs_revision)")
    task_id: str = Field(..., description="Task ID for this review request")


class FormatterResponse(BaseModel):
    """Response from the formatter agent."""
    agent: Literal["formatter"] = Field(default="formatter", description="Agent identifier")
    formatted_content: str = Field(..., description="Content formatted in the target format")
    target_format: str = Field(..., description="The format used for formatting")
    task_id: str = Field(..., description="Task ID for this formatting request")


# Enums for validation

class SupportedFormat(str):
    """Supported output formats for the formatter."""
    HTML = "HTML"
    MARKDOWN = "MARKDOWN"
    JSON = "JSON"
    TEXT = "TEXT"
    EMAIL = "EMAIL"


class ApprovalStatus(str):
    """Content approval status from critic."""
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"