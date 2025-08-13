"""PostgreSQL backend for knowledge repository."""

import asyncio
import json
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import asyncpg
from sentence_transformers import SentenceTransformer

from ..repository import KnowledgeRepository
from ..models import (
    KnowledgeItem, ResearchReport, KnowledgeUpdate, SourceReference,
    SourceType, SearchQuery, SearchResult, MonitorConfig
)


class PostgreSQLKnowledgeRepository(KnowledgeRepository):
    """PostgreSQL implementation of the knowledge repository."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        self._embedding_model = None
    
    @property
    def embedding_model(self):
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model
    
    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
        return self.pool
    
    async def _ensure_schema(self):
        """Ensure database schema exists."""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            # Enable required extensions
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            
            # Create knowledge_items table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    source_id TEXT NOT NULL,
                    source_url TEXT,
                    metadata JSONB DEFAULT '{}',
                    tags TEXT[] DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    embedding vector(384)  -- all-MiniLM-L6-v2 dimension
                );
            """)
            
            # Create research_reports table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS research_reports (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_type VARCHAR(50) DEFAULT 'research_report',
                    source_id TEXT NOT NULL,
                    source_url TEXT,
                    metadata JSONB DEFAULT '{}',
                    tags TEXT[] DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    embedding vector(384),
                    query TEXT NOT NULL,
                    depth_level VARCHAR(20) NOT NULL,
                    iterations_performed INTEGER DEFAULT 1,
                    sources_searched INTEGER DEFAULT 0,
                    confidence_score FLOAT DEFAULT 0.0,
                    citations TEXT[] DEFAULT '{}',
                    source_urls TEXT[] DEFAULT '{}',
                    task_id TEXT,
                    user_id TEXT
                );
            """)
            
            # Create knowledge_updates table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_updates (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    source_id TEXT NOT NULL,
                    source_url TEXT,
                    metadata JSONB DEFAULT '{}',
                    tags TEXT[] DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    embedding vector(384),
                    change_type VARCHAR(20) DEFAULT 'created',
                    previous_version_id UUID,
                    summary TEXT,
                    source_created_at TIMESTAMPTZ,
                    source_updated_at TIMESTAMPTZ,
                    processing_status VARCHAR(20) DEFAULT 'pending',
                    processing_error TEXT,
                    processed_at TIMESTAMPTZ,
                    author TEXT,
                    version TEXT
                );
            """)
            
            # Create monitor_configs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS monitor_configs (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    source_type VARCHAR(50) NOT NULL,
                    source_identifier TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    check_interval_minutes INTEGER DEFAULT 60,
                    watch_updates BOOLEAN DEFAULT true,
                    watch_creates BOOLEAN DEFAULT true,
                    watch_deletes BOOLEAN DEFAULT false,
                    auto_process BOOLEAN DEFAULT true,
                    notification_threshold INTEGER DEFAULT 5,
                    extraction_config JSONB DEFAULT '{}',
                    filters JSONB DEFAULT '{}',
                    last_check_at TIMESTAMPTZ,
                    last_success_at TIMESTAMPTZ,
                    last_error_at TIMESTAMPTZ,
                    last_error_message TEXT,
                    consecutive_errors INTEGER DEFAULT 0,
                    total_items_found INTEGER DEFAULT 0,
                    total_items_processed INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_items_source ON knowledge_items(source_type, source_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_items_embedding ON knowledge_items USING ivfflat (embedding vector_cosine_ops);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_research_reports_embedding ON research_reports USING ivfflat (embedding vector_cosine_ops);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_updates_embedding ON knowledge_updates USING ivfflat (embedding vector_cosine_ops);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_monitor_configs_active ON monitor_configs(is_active, source_type);")
    
    # Knowledge Item Operations
    
    async def create_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Create a new knowledge item."""
        await self._ensure_schema()
        pool = await self._get_pool()
        
        # Generate embedding
        embedding = self.embedding_model.encode(item.content).tolist()
        
        async with pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO knowledge_items 
                (title, content, source_type, source_id, source_url, metadata, tags, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, created_at, updated_at
            """, item.title, item.content, item.source_type.value, item.source_id, 
                item.source_url, json.dumps(item.metadata), item.tags, embedding)
            
            item.id = str(result['id'])
            item.created_at = result['created_at']
            item.updated_at = result['updated_at']
            item.embedding = embedding
            
            return item
    
    async def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a knowledge item by ID."""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT * FROM knowledge_items WHERE id = $1
            """, UUID(item_id))
            
            if not result:
                return None
            
            return KnowledgeItem(
                id=str(result['id']),
                title=result['title'],
                content=result['content'],
                source_type=SourceType(result['source_type']),
                source_id=result['source_id'],
                source_url=result['source_url'],
                metadata=result['metadata'] or {},
                tags=result['tags'] or [],
                created_at=result['created_at'],
                updated_at=result['updated_at'],
                embedding=result['embedding']
            )
    
    async def update_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Update an existing knowledge item."""
        pool = await self._get_pool()
        
        # Regenerate embedding if content changed
        if item.embedding is None:
            item.embedding = self.embedding_model.encode(item.content).tolist()
        
        item.updated_at = datetime.utcnow()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE knowledge_items 
                SET title = $1, content = $2, source_url = $3, metadata = $4, 
                    tags = $5, updated_at = $6, embedding = $7
                WHERE id = $8
            """, item.title, item.content, item.source_url, json.dumps(item.metadata),
                item.tags, item.updated_at, item.embedding, UUID(item.id))
            
            return item
    
    async def delete_item(self, item_id: str) -> bool:
        """Delete a knowledge item."""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM knowledge_items WHERE id = $1
            """, UUID(item_id))
            
            return result == "DELETE 1"
    
    # Research Report Operations
    
    async def create_research_report(self, report: ResearchReport) -> ResearchReport:
        """Create a new research report."""
        await self._ensure_schema()
        pool = await self._get_pool()
        
        # Generate embedding
        embedding = self.embedding_model.encode(report.content).tolist()
        
        async with pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO research_reports 
                (title, content, source_id, metadata, tags, embedding, query, depth_level,
                 iterations_performed, sources_searched, confidence_score, citations, 
                 source_urls, task_id, user_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id, created_at, updated_at
            """, report.title, report.content, report.source_id, json.dumps(report.metadata),
                report.tags, embedding, report.query, report.depth_level.value,
                report.iterations_performed, report.sources_searched, report.confidence_score,
                report.citations, report.source_urls, report.task_id, report.user_id)
            
            report.id = str(result['id'])
            report.created_at = result['created_at']
            report.updated_at = result['updated_at']
            report.embedding = embedding
            
            return report
    
    async def get_research_reports(
        self,
        limit: int = 50,
        offset: int = 0,
        query_filter: Optional[str] = None
    ) -> List[ResearchReport]:
        """Get research reports with optional filtering."""
        pool = await self._get_pool()
        
        query = "SELECT * FROM research_reports"
        params = []
        
        if query_filter:
            query += " WHERE query ILIKE $1 OR title ILIKE $1 OR content ILIKE $1"
            params.append(f"%{query_filter}%")
        
        query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1) + " OFFSET $" + str(len(params) + 2)
        params.extend([limit, offset])
        
        async with pool.acquire() as conn:
            results = await conn.fetch(query, *params)
            
            reports = []
            for result in results:
                report = ResearchReport(
                    id=str(result['id']),
                    title=result['title'],
                    content=result['content'],
                    source_id=result['source_id'],
                    metadata=result['metadata'] or {},
                    tags=result['tags'] or [],
                    created_at=result['created_at'],
                    updated_at=result['updated_at'],
                    embedding=result['embedding'],
                    query=result['query'],
                    depth_level=result['depth_level'],
                    iterations_performed=result['iterations_performed'],
                    sources_searched=result['sources_searched'],
                    confidence_score=result['confidence_score'],
                    citations=result['citations'] or [],
                    source_urls=result['source_urls'] or [],
                    task_id=result['task_id'],
                    user_id=result['user_id']
                )
                reports.append(report)
            
            return reports
    
    # Knowledge Update Operations
    
    async def create_knowledge_update(self, update: KnowledgeUpdate) -> KnowledgeUpdate:
        """Create a new knowledge update."""
        await self._ensure_schema()
        pool = await self._get_pool()
        
        # Generate embedding
        embedding = self.embedding_model.encode(update.content).tolist()
        
        async with pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO knowledge_updates 
                (title, content, source_type, source_id, source_url, metadata, tags, embedding,
                 change_type, summary, source_created_at, source_updated_at, author, version)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id, created_at, updated_at
            """, update.title, update.content, update.source_type.value, update.source_id,
                update.source_url, json.dumps(update.metadata), update.tags, embedding,
                update.change_type, update.summary, update.source_created_at,
                update.source_updated_at, update.author, update.version)
            
            update.id = str(result['id'])
            update.created_at = result['created_at']
            update.updated_at = result['updated_at']
            update.embedding = embedding
            
            return update
    
    async def get_knowledge_updates(
        self,
        source_type: Optional[SourceType] = None,
        source_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeUpdate]:
        """Get knowledge updates with optional filtering."""
        pool = await self._get_pool()
        
        query = "SELECT * FROM knowledge_updates"
        params = []
        conditions = []
        
        if source_type:
            conditions.append(f"source_type = ${len(params) + 1}")
            params.append(source_type.value)
        
        if source_id:
            conditions.append(f"source_id = ${len(params) + 1}")
            params.append(source_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        params.extend([limit, offset])
        
        async with pool.acquire() as conn:
            results = await conn.fetch(query, *params)
            
            updates = []
            for result in results:
                update = KnowledgeUpdate(
                    id=str(result['id']),
                    title=result['title'],
                    content=result['content'],
                    source_type=SourceType(result['source_type']),
                    source_id=result['source_id'],
                    source_url=result['source_url'],
                    metadata=result['metadata'] or {},
                    tags=result['tags'] or [],
                    created_at=result['created_at'],
                    updated_at=result['updated_at'],
                    embedding=result['embedding'],
                    change_type=result['change_type'],
                    summary=result['summary'],
                    source_created_at=result['source_created_at'],
                    source_updated_at=result['source_updated_at'],
                    processing_status=result['processing_status'],
                    processing_error=result['processing_error'],
                    processed_at=result['processed_at'],
                    author=result['author'],
                    version=result['version']
                )
                updates.append(update)
            
            return updates
    
    # Search Operations
    
    async def search(self, query: SearchQuery) -> SearchResult:
        """Search across all knowledge items using vector similarity."""
        start_time = time.time()
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query.query).tolist()
        
        pool = await self._get_pool()
        
        # Build search query
        tables = ["knowledge_items", "research_reports", "knowledge_updates"]
        if query.source_types:
            source_filter = " AND source_type = ANY($2)"
            source_types = [st.value for st in query.source_types]
        else:
            source_filter = ""
            source_types = None
        
        all_results = []
        
        async with pool.acquire() as conn:
            for table in tables:
                sql = f"""
                    SELECT id, title, content, source_type, source_url, updated_at,
                           1 - (embedding <=> $1) as similarity
                    FROM {table}
                    WHERE embedding IS NOT NULL
                    {source_filter}
                    AND 1 - (embedding <=> $1) >= $3
                    ORDER BY similarity DESC
                    LIMIT $4
                """
                
                params = [query_embedding, query.min_relevance, query.max_results // len(tables)]
                if source_types:
                    params.insert(1, source_types)
                    params[2] = query.min_relevance
                    params[3] = query.max_results // len(tables)
                
                results = await conn.fetch(sql, *params)
                
                for result in results:
                    source_ref = SourceReference(
                        id=str(result['id']),
                        title=result['title'],
                        type=SourceType(result['source_type']),
                        url=result['source_url'],
                        excerpt=result['content'][:200] + "..." if len(result['content']) > 200 else result['content'],
                        relevance_score=float(result['similarity']),
                        last_updated=result['updated_at']
                    )
                    all_results.append(source_ref)
        
        # Sort by relevance and limit
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        final_results = all_results[:query.max_results]
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResult(
            results=final_results,
            total_found=len(final_results),
            query_processed=query.query,
            search_time_ms=search_time_ms,
            metadata={
                "tables_searched": tables,
                "min_relevance": query.min_relevance,
                "avg_relevance": sum(r.relevance_score for r in final_results) / len(final_results) if final_results else 0.0
            }
        )
    
    async def search_by_text(
        self,
        query: str,
        source_types: Optional[List[SourceType]] = None,
        limit: int = 10,
        min_relevance: float = 0.3
    ) -> List[SourceReference]:
        """Simple text-based search returning source references."""
        search_query = SearchQuery(
            query=query,
            source_types=source_types,
            max_results=limit,
            min_relevance=min_relevance
        )
        
        result = await self.search(search_query)
        return result.results
    
    # Monitor Configuration Operations
    
    async def create_monitor_config(self, config: MonitorConfig) -> MonitorConfig:
        """Create a monitor configuration."""
        await self._ensure_schema()
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO monitor_configs 
                (source_type, source_identifier, is_active, check_interval_minutes,
                 watch_updates, watch_creates, watch_deletes, auto_process,
                 notification_threshold, extraction_config, filters)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id, created_at, updated_at
            """, config.source_type.value, config.source_identifier, config.is_active,
                config.check_interval_minutes, config.watch_updates, config.watch_creates,
                config.watch_deletes, config.auto_process, config.notification_threshold,
                json.dumps(config.extraction_config), json.dumps(config.filters))
            
            config.id = str(result['id'])
            config.created_at = result['created_at']
            config.updated_at = result['updated_at']
            
            return config
    
    async def get_monitor_configs(self, active_only: bool = True) -> List[MonitorConfig]:
        """Get monitor configurations."""
        pool = await self._get_pool()
        
        query = "SELECT * FROM monitor_configs"
        if active_only:
            query += " WHERE is_active = true"
        query += " ORDER BY created_at DESC"
        
        async with pool.acquire() as conn:
            results = await conn.fetch(query)
            
            configs = []
            for result in results:
                config = MonitorConfig(
                    id=str(result['id']),
                    source_type=SourceType(result['source_type']),
                    source_identifier=result['source_identifier'],
                    is_active=result['is_active'],
                    check_interval_minutes=result['check_interval_minutes'],
                    watch_updates=result['watch_updates'],
                    watch_creates=result['watch_creates'],
                    watch_deletes=result['watch_deletes'],
                    auto_process=result['auto_process'],
                    notification_threshold=result['notification_threshold'],
                    extraction_config=result['extraction_config'] or {},
                    filters=result['filters'] or {},
                    last_check_at=result['last_check_at'],
                    last_success_at=result['last_success_at'],
                    last_error_at=result['last_error_at'],
                    last_error_message=result['last_error_message'],
                    consecutive_errors=result['consecutive_errors'],
                    total_items_found=result['total_items_found'],
                    total_items_processed=result['total_items_processed'],
                    total_errors=result['total_errors'],
                    created_at=result['created_at'],
                    updated_at=result['updated_at']
                )
                configs.append(config)
            
            return configs
    
    async def update_monitor_config(self, config: MonitorConfig) -> MonitorConfig:
        """Update a monitor configuration."""
        pool = await self._get_pool()
        
        config.updated_at = datetime.utcnow()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE monitor_configs 
                SET is_active = $1, check_interval_minutes = $2, last_check_at = $3,
                    last_success_at = $4, last_error_at = $5, last_error_message = $6,
                    consecutive_errors = $7, total_items_found = $8, 
                    total_items_processed = $9, total_errors = $10, updated_at = $11
                WHERE id = $12
            """, config.is_active, config.check_interval_minutes, config.last_check_at,
                config.last_success_at, config.last_error_at, config.last_error_message,
                config.consecutive_errors, config.total_items_found,
                config.total_items_processed, config.total_errors, config.updated_at,
                UUID(config.id))
            
            return config
    
    # Utility Operations
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            stats = {}
            
            # Count records in each table
            for table in ["knowledge_items", "research_reports", "knowledge_updates", "monitor_configs"]:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = count
            
            # Active monitors
            active_monitors = await conn.fetchval("SELECT COUNT(*) FROM monitor_configs WHERE is_active = true")
            stats["active_monitors"] = active_monitors
            
            # Recent activity (last 24 hours)
            recent_items = await conn.fetchval("""
                SELECT COUNT(*) FROM knowledge_items 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            stats["recent_items_24h"] = recent_items
            
            return stats
    
    async def health_check(self) -> bool:
        """Check repository health."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close repository connections and cleanup."""
        if self.pool:
            await self.pool.close()
            self.pool = None
