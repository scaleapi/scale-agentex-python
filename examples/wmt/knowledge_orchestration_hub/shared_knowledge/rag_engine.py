"""RAG (Retrieval-Augmented Generation) engine for knowledge search and retrieval."""

import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from .repository import get_repository
from .models import SourceReference, SourceType, SearchQuery
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class RAGEngine:
    """RAG engine for searching and retrieving relevant knowledge."""

    def __init__(self, db_repository=None):
        self.repository = db_repository

    async def _get_repository(self):
        """Lazy load the repository."""
        if self.repository is None:
            self.repository = get_repository()
        return self.repository

    async def search(
        self,
        query: str,
        max_results: int = 10,
        source_types: Optional[List[SourceType]] = None,
        min_relevance: float = 0.3,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Search the knowledge base and return relevant sources.

        Args:
            query: Search query
            max_results: Maximum number of results to return
            source_types: Filter by specific source types
            min_relevance: Minimum relevance score threshold
            include_metadata: Whether to include search metadata

        Returns:
            Dictionary with search results and metadata
        """
        start_time = time.time()

        try:
            repository = await self._get_repository()

            # Search the knowledge base
            results = await repository.search_by_text(
                query=query,
                source_types=source_types,
                limit=max_results,
                min_relevance=min_relevance,
            )

            search_time_ms = int((time.time() - start_time) * 1000)

            # Prepare response
            response = {
                "results": results,
                "total_found": len(results),
                "query_processed": self._process_query(query),
                "search_time_ms": search_time_ms,
            }

            if include_metadata:
                response["metadata"] = {
                    "source_types_searched": (
                        [st.value for st in source_types] if source_types else ["all"]
                    ),
                    "min_relevance_threshold": min_relevance,
                    "search_timestamp": datetime.utcnow().isoformat(),
                    "avg_relevance_score": (
                        sum(r.relevance_score for r in results) / len(results)
                        if results
                        else 0.0
                    ),
                }

            logger.info(
                f"RAG search completed: {len(results)} results in {search_time_ms}ms for query: {query}"
            )
            return response

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return {
                "results": [],
                "total_found": 0,
                "query_processed": query,
                "search_time_ms": int((time.time() - start_time) * 1000),
                "error": str(e),
            }

    async def get_context_for_query(
        self, query: str, max_context_length: int = 4000, max_sources: int = 5
    ) -> Dict[str, Any]:
        """
        Get relevant context for a query, formatted for LLM consumption.

        Args:
            query: User query
            max_context_length: Maximum context length in characters
            max_sources: Maximum number of sources to include

        Returns:
            Dictionary with formatted context and source information
        """
        search_results = await self.search(query, max_results=max_sources * 2)
        sources = search_results["results"][:max_sources]

        if not sources:
            return {
                "context": "No relevant information found in the knowledge base.",
                "sources": [],
                "context_length": 0,
            }

        # Build context string
        context_parts = []
        current_length = 0
        used_sources = []

        for source in sources:
            source_text = f"[Source: {source.title}]\n{source.excerpt}\n"

            if current_length + len(source_text) > max_context_length:
                # Try to fit a truncated version
                remaining_space = (
                    max_context_length - current_length - 50
                )  # Leave some buffer
                if remaining_space > 100:  # Only include if we have reasonable space
                    truncated_excerpt = source.excerpt[:remaining_space] + "..."
                    source_text = f"[Source: {source.title}]\n{truncated_excerpt}\n"
                    context_parts.append(source_text)
                    used_sources.append(source)
                break

            context_parts.append(source_text)
            used_sources.append(source)
            current_length += len(source_text)

        context = "\n".join(context_parts)

        return {
            "context": context,
            "sources": used_sources,
            "context_length": len(context),
            "sources_available": len(sources),
            "sources_used": len(used_sources),
        }

    def generate_source_citations(self, sources: List[SourceReference]) -> str:
        """Generate formatted citations for sources."""
        if not sources:
            return ""

        citations = []
        for i, source in enumerate(sources, 1):
            citation = f"{i}. {source.title}"
            if source.url:
                citation += f" - {source.url}"
            citation += f" (Relevance: {source.relevance_score:.2f})"
            citations.append(citation)

        return "\n".join(citations)

    def _process_query(self, query: str) -> str:
        """Process and potentially expand the search query."""
        # For now, just clean up the query
        # In the future, could add query expansion, synonym handling, etc.
        processed = query.strip().lower()

        # Remove common stop words that don't help with semantic search
        stop_words = {"what", "is", "the", "how", "can", "you", "tell", "me", "about"}
        words = processed.split()
        filtered_words = [w for w in words if w not in stop_words or len(words) <= 3]

        return " ".join(filtered_words) if filtered_words else query

    async def close(self):
        """Close the RAG engine and cleanup resources."""
        if self.repository:
            await self.repository.close()
