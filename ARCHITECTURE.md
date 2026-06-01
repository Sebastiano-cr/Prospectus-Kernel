# Kirin Platform Architecture

## Cognitive Runtime Layer

The Kirin platform implements a cognitive runtime layer that provides persistent memory capabilities to agents. This layer consists of three specialized memory managers:

### 1. PostgreSQL Memory Manager (`agents/memory/postgres_memory.py`)

**Purpose**: Structured data storage for lead profiles, interaction history, and relational data.

**Key Features**:
- Connection pooling using pg8000
- Automatic table creation on initialization
- UPSERT operations for lead memory (INSERT ... ON CONFLICT DO UPDATE)
- JSONB storage for flexible schema
- Indexing on lead_id and memory_type for efficient queries

**Tables**:
- `lead_memory`: Stores structured lead data (dossies, profiles, preferences)
- `lead_interactions`: Append-only history of lead interactions

**Methods**:
- `store_lead_memory(lead_id, memory_type, data)` - Upsert lead-specific data
- `retrieve_lead_memory(lead_id, memory_type)` - Retrieve lead-specific data
- `store_interaction_history(lead_id, interaction_type, data)` - Append interaction
- `retrieve_interaction_history(lead_id, limit)` - Get interaction history

**Limitations**: 
- No native vector search (delegated to Qdrant)
- Not ideal for short-term TTL data (delegated to Redis)

### 2. Qdrant Memory Manager (`agents/memory/qdrant_memory.py`)

**Purpose**: Vector storage and similarity search for lead embeddings and semantic matching.

**Key Features**:
- Connection to Qdrant vector database
- Automatic collection creation
- Vector payload storage for metadata
- Similarity search with filtering

**Collections**:
- Dynamically named based on memory_type parameter

**Methods**:
- `store_similar_memories(memory_type, vectors, payloads)` - Store vectors with metadata
- `search_similar_memories(query_vector, memory_type, limit)` - Find similar vectors
- (Other methods delegate to base class or raise NotImplementedError)

### 3. Redis Memory Manager (`agents/memory/redis_memory.py`)

**Purpose**: Short-term context, caching, and rate limiting with TTL support.

**Key Features**:
- Async Redis connection using redis.asyncio
- Automatic key expiration with TTL
- Pipeline operations for atomic increments
- Rate limiting implementation

**Key Patterns**:
- Lead context: `lead:{lead_id}:context` (JSON with TTL)
- Daily counters: `counter:{key}` (INCR with EXPIRE)
- Rate limits: `rate_limit:{lead_id}:{action}` (INCR with EXPIRE)
- Lead memory cache: `lead:{lead_id}:memory:{memory_type}` (optional caching)

**Methods**:
- `store_conversation_context(lead_id, context, ttl)` - Store short-term context
- `retrieve_conversation_context(lead_id)` - Retrieve short-term context
- `increment_daily_counter(key, expiry_seconds)` - Thread-safe counter increment
- `set_rate_limit(lead_id, action, limit, window_seconds)` - Rate limiting check

## Memory Factory Pattern

The platform uses a factory pattern (`agents/memory/factory.py`) to manage memory manager instances:

- Singleton-like behavior within the application lifecycle
- Lazy initialization of memory managers
- Centralized access to all memory manager types
- Configuration-driven initialization

## Runtime State Management

Global state is managed in `agents/runtime.py`:

- Thread-safe (actually, async-safe) global variables
- Async initialization and shutdown functions
- Accessor functions for each memory manager type
- Initialization state tracking

## Agent-Memory Integration

Agents interact with memory through the runtime module:

```python
from agents.runtime import get_postgres_memory, get_qdrant_memory, get_redis_memory

async def some_agent_function(lead_data):
    # Get memory manager instances
    postgres = get_postgres_memory()
    qdrant = get_qdrant_memory()
    redis = get_redis_memory()
    
    # Store results
    await postgres.store_lead_memory(lead_id, "enrichment", enrichment_data)
    
    # Retrieve context
    context = await redis.retrieve_conversation_context(lead_id)
    
    # Find similar leads
    similar = await qdrant.search_similar_memories(query_vector, "lead_profile", 5)
```

## Initialization Flow

1. Server startup triggers `@app.on_event("startup")`
2. `initialize_memory_managers()` called with configuration from environment
3. Each memory manager is instantiated and initialized asynchronously
4. Memory factory holds references to all initialized managers
5. Agents access managers through runtime accessors
6. On shutdown, `shutdown_memory_managers_async()` is called

## Error Handling and Resilience

- Memory manager initialization failures are logged but don't crash the application
- Agents gracefully handle missing memory managers (check for None)
- Connection errors during operations are caught and logged
- Fallback behaviors where appropriate (e.g., skipping memory storage if unavailable)

## Performance Considerations

- Connection pooling for PostgreSQL and Redis
- Asynchronous I/O for all memory operations
- Batch operations where possible (Redis pipelines)
- Proper indexing on query fields
- TTL-based automatic cleanup in Redis

## Security Considerations

- Environment variables for sensitive configuration
- No hardcoded credentials
- Network isolation possible via Docker Compose
- Principle of least privilege for database users

## Extensibility

Adding new memory types:
1. Create new manager class inheriting from BaseMemoryManager
2. Implement required abstract methods
3. Add to MemoryFactory.get_*_manager() methods
4. Update runtime initialization if needed
5. Agents can then access via runtime accessors

Adding new agent capabilities:
1. Access memory managers through runtime module
2. Implement storage/retrieval patterns as needed
3. Consider which memory type is appropriate for each data kind
4. Implement error handling for memory unavailability
