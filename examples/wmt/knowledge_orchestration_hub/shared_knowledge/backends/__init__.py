"""Storage backends for the knowledge repository."""

from .postgres import PostgreSQLKnowledgeRepository

__all__ = ["PostgreSQLKnowledgeRepository"]
