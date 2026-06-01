"""
PostgreSQL memory manager for storing structured lead memory and interaction history.
"""
import pg8000
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from .base import BaseMemoryManager

logger = logging.getLogger(__name__)

class PostgresMemoryManager(BaseMemoryManager):
    """
    PostgreSQL-based memory manager for storing structured lead data.
    Good for relational data like lead profiles, interaction history, preferences.
    """
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
    
    async def initialize(self) -> None:
        """Initialize the PostgreSQL connection (test connection)."""
        try:
            # Test the connection
            def _test_connection():
                conn = pg8000.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )
                conn.close()
            
            await asyncio.to_thread(_test_connection)
            
            # Create tables if they don't exist
            def _create_tables():
                conn = pg8000.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS lead_memory (
                                id SERIAL PRIMARY KEY,
                                lead_id VARCHAR(255) NOT NULL,
                                memory_type VARCHAR(100) NOT NULL,
                                data JSONB NOT NULL,
                                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE INDEX IF NOT EXISTS idx_lead_memory_lead_id_type 
                            ON lead_memory (lead_id, memory_type)
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS lead_interactions (
                                id SERIAL PRIMARY KEY,
                                lead_id VARCHAR(255) NOT NULL,
                                interaction_type VARCHAR(100) NOT NULL,
                                data JSONB NOT NULL,
                                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE INDEX IF NOT EXISTS idx_lead_interactions_lead_id 
                            ON lead_interactions (lead_id)
                        ''')
                    
                    conn.commit()
                finally:
                    conn.close()
            
            await asyncio.to_thread(_create_tables)
            
            logger.info("PostgreSQL memory manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL memory manager: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Close connections (nothing to do for connection-per-operation)."""
        logger.info("PostgreSQL memory manager shutdown")
    
    def _get_connection(self):
        """Get a new PostgreSQL connection."""
        return pg8000.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )
    
    async def store_lead_memory(self, lead_id: str, memory_type: str, data: Dict[str, Any]) -> bool:
        """
        Store or update memory associated with a lead.
        Uses UPSERT (INSERT ... ON CONFLICT) to avoid duplicates.
        """
        try:
            def _store():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            INSERT INTO lead_memory (lead_id, memory_type, data, updated_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (lead_id, memory_type)
                            DO UPDATE SET 
                                data = EXCLUDED.data,
                                updated_at = NOW()
                        ''', (lead_id, memory_type, json.dumps(data)))
                    
                    conn.commit()
                finally:
                    conn.close()
            
            await asyncio.to_thread(_store)
            return True
        except Exception as e:
            logger.error(f"Failed to store lead memory for {lead_id}: {e}")
            return False
    
    async def retrieve_lead_memory(self, lead_id: str, memory_type: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve memory associated with a lead.
        """
        try:
            def _retrieve():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            SELECT data FROM lead_memory 
                            WHERE lead_id = %s AND memory_type = %s
                        ''', (lead_id, memory_type))
                        
                        row = cur.fetchone()
                        if row:
                            return json.loads(row[0])
                        return None
                finally:
                    conn.close()
            
            return await asyncio.to_thread(_retrieve)
        except Exception as e:
            logger.error(f"Failed to retrieve lead memory for {lead_id}: {e}")
            return None
    
    async def store_interaction_history(self, lead_id: str, interaction_type: str, data: Dict[str, Any]) -> bool:
        """
        Store an interaction event (append-only history).
        """
        try:
            def _store():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            INSERT INTO lead_interactions (lead_id, interaction_type, data)
                            VALUES (%s, %s, %s)
                        ''', (lead_id, interaction_type, json.dumps(data)))
                    
                    conn.commit()
                finally:
                    conn.close()
            
            await asyncio.to_thread(_store)
            return True
        except Exception as e:
            logger.error(f"Failed to store interaction history for {lead_id}: {e}")
            return False
    
    async def retrieve_interaction_history(self, lead_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve interaction history for a lead.
        """
        try:
            def _retrieve():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            SELECT interaction_type, data, timestamp 
                            FROM lead_interactions 
                            WHERE lead_id = %s 
                            ORDER BY timestamp DESC 
                            LIMIT %s
                        ''', (lead_id, limit))
                        
                        rows = cur.fetchall()
                        
                        return [
                            {
                                "interaction_type": row[0],
                                "data": json.loads(row[1]),
                                "timestamp": row[2].isoformat()
                            }
                            for row in rows
                        ]
                finally:
                    conn.close()
            
            return await asyncio.to_thread(_retrieve)
        except Exception as e:
            logger.error(f"Failed to retrieve interaction history for {lead_id}: {e}")
            return []
    
    # ─── Abstract methods from BaseMemoryManager ──────────────────────────────

    async def cache_get(self, key: str) -> Optional[Any]:
        """PostgreSQL doesn't support key-value cache. Returns None."""
        logger.warning("PostgreSQL does not support key-value cache. Use Redis.")
        return None

    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """PostgreSQL doesn't support key-value cache."""
        logger.warning("PostgreSQL does not support key-value cache. Use Redis.")
        return False

    async def cache_delete(self, key: str) -> bool:
        """PostgreSQL doesn't support key-value cache."""
        logger.warning("PostgreSQL does not support key-value cache. Use Redis.")
        return False

    async def store(self, namespace: str, key: str, data: Dict[str, Any]) -> bool:
        """Store structured data in PostgreSQL using lead_memory table."""
        try:
            def _store():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        # Use namespace as memory_type, key as lead_id for compatibility
                        cur.execute('''
                            INSERT INTO lead_memory (lead_id, memory_type, data, updated_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (lead_id, memory_type)
                            DO UPDATE SET
                                data = EXCLUDED.data,
                                updated_at = NOW()
                        ''', (key, namespace, json.dumps(data)))
                    conn.commit()
                finally:
                    conn.close()

            await asyncio.to_thread(_store)
            return True
        except Exception as e:
            logger.error(f"Failed to store structured data {namespace}:{key}: {e}")
            return False

    async def retrieve(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve structured data from PostgreSQL."""
        try:
            def _retrieve():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            SELECT data FROM lead_memory
                            WHERE lead_id = %s AND memory_type = %s
                        ''', (key, namespace))
                        row = cur.fetchone()
                        if row:
                            return json.loads(row[0])
                        return None
                finally:
                    conn.close()

            return await asyncio.to_thread(_retrieve)
        except Exception as e:
            logger.error(f"Failed to retrieve structured data {namespace}:{key}: {e}")
            return None

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete structured data from PostgreSQL."""
        try:
            def _delete():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            DELETE FROM lead_memory
                            WHERE lead_id = %s AND memory_type = %s
                        ''', (key, namespace))
                    conn.commit()
                finally:
                    conn.close()

            await asyncio.to_thread(_delete)
            return True
        except Exception as e:
            logger.error(f"Failed to delete structured data {namespace}:{key}: {e}")
            return False

    async def search_by_text(self, namespace: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search structured data by text pattern in PostgreSQL."""
        try:
            query_lower = f"%{query.lower()}%"

            def _search():
                conn = self._get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute('''
                            SELECT data FROM lead_memory
                            WHERE memory_type = %s
                            AND data::text ILIKE %s
                            ORDER BY updated_at DESC
                            LIMIT %s
                        ''', (namespace, query_lower, limit))
                        rows = cur.fetchall()
                        return [
                            json.loads(row[0]) if isinstance(row[0], str) else row[0]
                            for row in rows
                        ]
                finally:
                    conn.close()

            return await asyncio.to_thread(_search)
        except Exception as e:
            logger.error(f"Failed to search by text in PostgreSQL: {e}")
            return []

    async def search_similar_memories(self, query_vector: List[float], memory_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError("Vector search requires Qdrant memory manager")

    async def store_conversation_context(self, lead_id: str, context: Dict[str, Any], ttl: int = 3600) -> bool:
        raise NotImplementedError("Short-term context with TTL requires Redis memory manager")

    async def retrieve_conversation_context(self, lead_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Short-term context retrieval requires Redis memory manager")
