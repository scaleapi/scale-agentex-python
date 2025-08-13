"""Abstract knowledge repository interface and factory."""

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from .models import (
    KnowledgeItem, ResearchReport, KnowledgeUpdate, SourceReference,
    SourceType, SearchQuery, SearchResult, MonitorConfig
)


class KnowledgeRepository(ABC):
    """Abstract interface for knowledge storage and retrieval."""
    
    # Knowledge Item Operations
    
    @abstractmethod
    async def create_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Create a new knowledge item."""
        pass
    
    @abstractmethod
    async def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a knowledge item by ID."""
        pass
    
    @abstractmethod
    async def update_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Update an existing knowledge item."""
        pass
    
    @abstractmethod
    async def delete_item(self, item_id: str) -> bool:
        """Delete a knowledge item."""
        pass
    
    # Research Report Operations
    
    @abstractmethod
    async def create_research_report(self, report: ResearchReport) -> ResearchReport:
        """Create a new research report."""
        pass
    
    @abstractmethod
    async def get_research_reports(
        self,
        limit: int = 50,
        offset: int = 0,
        query_filter: Optional[str] = None
    ) -> List[ResearchReport]:
        """Get research reports with optional filtering."""
        pass
    
    # Knowledge Update Operations
    
    @abstractmethod
    async def create_knowledge_update(self, update: KnowledgeUpdate) -> KnowledgeUpdate:
        """Create a new knowledge update."""
        pass
    
    @abstractmethod
    async def get_knowledge_updates(
        self,
        source_type: Optional[SourceType] = None,
        source_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeUpdate]:
        """Get knowledge updates with optional filtering."""
        pass
    
    # Search Operations
    
    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResult:
        """Search across all knowledge items using vector similarity."""
        pass
    
    @abstractmethod
    async def search_by_text(
        self,
        query: str,
        source_types: Optional[List[SourceType]] = None,
        limit: int = 10,
        min_relevance: float = 0.3
    ) -> List[SourceReference]:
        """Simple text-based search returning source references."""
        pass
    
    # Monitor Configuration Operations
    
    @abstractmethod
    async def create_monitor_config(self, config: MonitorConfig) -> MonitorConfig:
        """Create a monitor configuration."""
        pass
    
    @abstractmethod
    async def get_monitor_configs(self, active_only: bool = True) -> List[MonitorConfig]:
        """Get monitor configurations."""
        pass
    
    @abstractmethod
    async def update_monitor_config(self, config: MonitorConfig) -> MonitorConfig:
        """Update a monitor configuration."""
        pass
    
    # Utility Operations
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check repository health."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close repository connections and cleanup."""
        pass


def get_repository(backend_type: Optional[str] = None) -> KnowledgeRepository:
    """
    Factory function to get a knowledge repository instance.
    
    Args:
        backend_type: Type of backend ('memory', 'sqlite', 'postgres').
                     If None, uses KNOWLEDGE_BACKEND environment variable.
                     Defaults to 'memory' if not specified.
    
    Returns:
        KnowledgeRepository instance
    """
    if backend_type is None:
        backend_type = os.environ.get("KNOWLEDGE_BACKEND", "memory")
    
    backend_type = backend_type.lower()
    
    if backend_type == "memory":
        from .backends.memory import MemoryKnowledgeRepository
        return MemoryKnowledgeRepository()
    
    elif backend_type == "sqlite":
        from .backends.sqlite import SQLiteKnowledgeRepository
        database_url = os.environ.get("DATABASE_URL", "sqlite:///knowledge_hub.db")
        return SQLiteKnowledgeRepository(database_url)
    
    elif backend_type == "postgres":
        from .backends.postgres import PostgreSQLKnowledgeRepository
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required for PostgreSQL backend")
        return PostgreSQLKnowledgeRepository(database_url)
    
    else:
        raise ValueError(f"Unsupported backend type: {backend_type}")


# Global repository instance (lazy-loaded)
_repository_instance: Optional[KnowledgeRepository] = None


async def get_shared_repository() -> KnowledgeRepository:
    """Get the shared repository instance (singleton pattern)."""
    global _repository_instance
    
    if _repository_instance is None:
        _repository_instance = get_repository()
    
    return _repository_instance


async def close_shared_repository() -> None:
    """Close the shared repository instance."""
    global _repository_instance
    
    if _repository_instance is not None:
        await _repository_instance.close()
        _repository_instance = None
