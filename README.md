# Kirin Platform

A cognitive runtime platform for lead enrichment, scoring, messaging, and research with persistent memory capabilities.

## Overview

The Kirin platform is designed to process leads through a pipeline of specialized agents:
1. **Enricher**: Gathers additional information about leads from various sources
2. **Scorer**: Assigns a score to leads based on their enriched data
3. **Messenger**: Generates and sends personalized WhatsApp messages
4. **Researcher**: Conducts deep research on high-value leads

What makes Kirin unique is its cognitive runtime layer that provides persistent memory capabilities using:
- **PostgreSQL**: For structured lead memory and interaction history
- **Qdrant**: For vector storage and similarity search
- **Redis**: For short-term context and caching with TTL

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Lead Input    │───▶│   Enricher Agent │───▶│    Scorer Agent  │
└─────────────────┘    └──────────────────┘    └──────────────────┘
                                     │                       │
                                     ▼                       ▼
                           ┌──────────────────┐    ┌──────────────────┐
                           │ Messenger Agent  │───▶│ Researcher Agent │
                           └──────────────────┘    └──────────────────┘
                                     │                       │
                                     ▼                       ▼
                           ┌──────────────────┐    ┌──────────────────┐
                           │   WhatsApp       │    │   Deep Research  │
                           │   Message Sent   │    │     Results      │
                           └──────────────────┘    └──────────────────┘
                                     │                       │
                                     ▼                       ▼
                           ┌──────────────────┐    ┌──────────────────┐
                           │   PostgreSQL     │    │      Qdrant      │
                           │ (Lead Memory)    │    │ (Vector Store)   │
                           └──────────────────┘    └──────────────────┘
                                                    │
                                                    ▼
                                           ┌──────────────────┐
                                           │     Redis        │
                                           │ (Short-term Context)│
                                           └──────────────────┘
```

## Components

### Memory Managers

1. **PostgreSQL Memory Manager**
   - Stores structured lead memory (profiles, preferences)
   - Maintains interaction history (append-only)
   - Provides relational querying capabilities

2. **Qdrant Memory Manager**
   - Stores vector embeddings for similarity search
   - Enables finding similar leads based on characteristics
   - Used for lead enrichment and recommendation

3. **Redis Memory Manager**
   - Stores short-term conversation context with TTL
   - Implements rate limiting counters
   - Provides caching for frequently accessed data

### Agents

1. **Enricher Agent**
   - Uses Google Maps API to gather business information
   - Uses Instagram API to analyze social media presence
   - Creates a comprehensive dossiê for each lead
   - Stores enrichment results in PostgreSQL memory

2. **Scorer Agent**
   - Uses LLM to analyze the dossiê and assign a score (0-100)
   - Classifies leads into "frio" (cold), "morno" (warm), or "quente" (hot)
   - Stores scoring results in PostgreSQL memory

3. **Messenger Agent**
   - Generates personalized WhatsApp messages based on lead data
   - Respects daily message limits and rate constraints
   - Tracks message delivery and opt-out responses
   - Stores sent messages in PostgreSQL and context in Redis

4. **Researcher Agent**
   - Conducts deep research on leads with score >= 70
   - Uses multiple sources to gather competitive intelligence
   - Stores research results in PostgreSQL and Qdrant

### API Endpoints

- `POST /enrich` - Enrich a lead
- `POST /score` - Score a lead (requires dossiê)
- `POST /generate_message` - Generate WhatsApp message
- `POST /research` - Research a lead (score >= 70)
- `POST /crm_sync` - Synchronize lead with CRM
- `GET /memory/health` - Check memory manager status
- `GET /health` - General health check
- `GET /metrics` - Prometheus metrics

## Setup and Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.13+
- API keys for:
  - Google Maps Platform
  - Instagram Graph API
  - LiteLLM (for LLM access)
  - WhatsApp Evolution API
  - CRM provider (Notion, Airtable, or NocoDB)

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# LiteLLM Configuration
LITELLM_URL=http://litellm:4000
QWEN_VL_MAX_API_KEY=your_qwen_vl_max_key
DEEPSEEK_CHAT_API_KEY=your_deepseek_chat_key
MOONSHOT_V1_128K_API_KEY=your_moonshot_key

# WhatsApp Evolution API
EVOLUTION_API_URL=your_evolution_api_url
EVOLUTION_API_KEY=your_evolution_api_key
EVOLUTION_INSTANCE_ID=your_instance_id

# CRM Configuration
CRM_PROVIDER=notion  # or airtable, nocodb

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=kirin
POSTGRES_USER=kirin
POSTGRES_PASSWORD=your_secure_password_here

QDRANT_HOST=qdrant
QDRANT_PORT=6333

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # optional
REDIS_DB=0
```

### Running with Docker Compose

```bash
# Start all services
docker-compose up -d

# The API will be available at http://localhost:8000
# API documentation at http://localhost:8000/docs
```

### Running Agents Directly

```bash
# Install dependencies
pip install -r agents/requirements.txt

# Set environment variables (copy from .env or set individually)
export LITELLM_URL=http://localhost:4000
# ... other variables

# Run the server
uvicorn agents.server:app --host 0.0.0.0 --port 8000
```

## Testing

Run the test suite to verify functionality:

```bash
# Run unit and property-based tests
cd tests && python -m pytest test_units.py test_properties.py -v -p no:asyncio
```

## Memory Layer Usage Examples

### Storing Lead Memory

```python
from agents.runtime import get_postgres_memory
from agents.memory.factory import MemoryFactory

# Get memory manager instance
postgres = get_postgres_memory()

# Store lead memory
await postgres.store_lead_memory(
    lead_id="google_maps_id_123",
    memory_type="dossie",
    data={
        "resumo_perfil": "Local restaurant with great reviews",
        "pontos_fracos": ["No website", "Limited social media"],
        "oportunidades": ["Create online ordering system"],
        "maturidade_digital": "baixo"
    }
)
```

### Retrieving Interaction History

```python
from agents.runtime import get_postgres_memory

postgres = get_postgres_memory()
history = await postgres.retrieve_interaction_history(
    lead_id="google_maps_id_123",
    limit=10
)
```

### Storing Conversation Context

```python
from agents.runtime import get_redis_memory

redis = get_redis_memory()
await redis.store_conversation_context(
    lead_id="google_maps_id_123",
    context={
        "last_message": "Hello, how can I help you today?",
        "timestamp": "2026-05-27T10:30:00Z",
        "user_intent": "inquiring_hours"
    },
    ttl=3600  # 1 hour
)
```

### Similarity Search

```python
from agents.runtime import get_qdrant_memory
import numpy as np

qdrant = get_qdrant_memory()
# Generate embedding for a lead (using your preferred method)
query_vector = np.random.rand(384).tolist()  # Example dimension

similar_leads = await qdrant.search_similar_memories(
    query_vector=query_vector,
    memory_type="lead_embedding",
    limit=5
)
```

## Extending the Platform

### Adding New Memory Types

To add a new type of memory storage:
1. Create a new manager class in `agents/memory/` inheriting from `BaseMemoryManager`
2. Implement the required abstract methods
3. Register the manager in `agents/memory/factory.py`
4. Initialize it in `agents/runtime.py`

### Adding New Agents

To add a new specialized agent:
1. Create a new module in `agents/` (e.g., `agents/new_agent.py`)
2. Implement the agent's core logic
3. Add API endpoints in `agents/server.py` if needed
4. Update the agent to use memory managers for persistence

## Monitoring and Metrics

The platform exposes Prometheus metrics at `/metrics` endpoint:
- `kirin_leads_extracted_total` - Number of leads extracted
- `kirin_enrichment_success_total` - Successful enrichments
- `kirin_enrichment_failed_total` - Failed enrichments
- `kirin_lead_score` - Distribution of lead scores
- `kirin_messages_sent_total` - Messages sent by status
- `kirin_errors_total` - Errors by component
- `kirin_active_leads` - Currently active leads in memory

Health checks:
- `/health` - Overall service health
- `/memory/health` - Individual memory manager status

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with FastAPI, Uvicorn, and Python 3.13
- Uses PostgreSQL, Qdrant, and Redis for memory storage
- Leverages LiteLLM for LLM abstraction
- Inspired by cognitive architecture patterns
