"""
Example usage of the Kirin platform agents and memory layer.
"""
import asyncio
import sys
import os

# Add the agents directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../agents'))

async def example_lead_processing():
    """Example showing how to process a lead through the Kirin pipeline."""
    from agents.pure_functions import normalize_score, classify_faixa
    from agents.runtime import initialize_memory_managers, get_postgres_memory, get_qdrant_memory, get_redis_memory
    
    # Initialize memory managers (in a real app, this would be done at startup)
    memory_config = {
        "postgres": {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "kirin"),
            "user": os.getenv("POSTGRES_USER", "kirin"),
            "password": os.getenv("POSTGRES_PASSWORD", "")
        },
        "qdrant": {
            "host": os.getenv("QDRANT_HOST", "localhost"),
            "port": int(os.getenv("QDRANT_PORT", "6333"))
        },
        "redis": {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "password": os.getenv("REDIS_PASSWORD"),
            "db": int(os.getenv("REDIS_DB", "0"))
        }
    }
    
    print("Initializing memory managers...")
    try:
        await initialize_memory_managers(memory_config)
        print("✓ Memory managers initialized")
    except Exception as e:
        print(f"⚠ Could not initialize memory managers (this is expected if services aren't running): {e}")
        # Continue anyway for demonstration purposes
    
    # Example lead data (as would come from Google Maps API)
    lead = {
        "id": "google_maps_id_12345",
        "name": "Restaurante Sabor Mineiro",
        "address": "Rua das Flores, 123, Belo Horizonte, MG",
        "phone": "+55 31 9999-9999",
        "website": "",  # No website
        "instagram_username": "sabor_mineiro",
        "rating": 4.5,
        "google_maps_url": "https://maps.google.com/?cid=12345"
    }
    
    print(f"\nProcessing lead: {lead['name']}")
    
    # 1. Enrichment (would normally call the enricher agent)
    # For demonstration, we'll simulate enrichment results
    dossie = {
        "resumo_perfil": "Restaurant tradicional mineiro com comida caseira e ambiente familiar",
        "pontos_fracos": [
            "Não possui website",
            "Pouca presença nas redes sociais",
            "Não aceita pedidos online"
        ],
        "oportunidades": [
            "Criar website para apresentar menu e aceitar reservas",
            "Implementar sistema de delivery próprio ou parceria com iFood/Uber Eats",
            "Aumentar frequência de posts no Instagram com fotos dos pratos"
        ],
        "maturidade_digital": "baixo"
    }
    
    lead["dossie"] = dossie
    print("✓ Lead enriched with dossiê")
    
    # 2. Scoring (would normally call the scorer agent)
    # Simulate scoring based on dossiê
    score = 65  # This would come from LLM analysis
    lead["score"] = score
    lead["faixa"] = classify_faixa(score)
    print(f"✓ Lead scored: {score}/100 ({lead['faixa']})")
    
    # 3. Store enrichment and scoring results in memory
    try:
        postgres = get_postgres_memory()
        if postgres:
            # Store dossiê in PostgreSQL
            await postgres.store_lead_memory(
                lead_id=lead["id"],
                memory_type="dossie",
                data=dossie
            )
            
            # Store score in PostgreSQL
            await postgres.store_lead_memory(
                lead_id=lead["id"],
                memory_type="score",
                data={
                    "score": score,
                    "faixa": lead["faixa"],
                    "timestamp": "2026-05-27T10:30:00Z"
                }
            )
            print("✓ Enrichment and scoring results stored in PostgreSQL")
    except Exception as e:
        print(f"⚠ Could not store in PostgreSQL: {e}")
    
    # 4. Generate message (would normally call the messenger agent)
    if score >= 20:  # Only generate message if score >= 20
        # Simulate message generation
        message = f"""Olá! Vi que o {lead['name']} tem um potencial incrível para crescer ainda mais online. 
        
Percebi que vocês não têm website atualmente, o que está limitando seu alcance. Gostaria de sugerir algumas melhorias:
1. Criar um site simples com menu, localização e horários
2. Implementar um sistema de reservas online
3. Começar a aceitar pedidos via delivery
4. Melhorar a presença no Instagram com postagens regulares

Posso ajudar a implementar essas soluções. Quando seria um bom horário para conversarmos?"""
        
        # Truncate message to WhatsApp limit
        from agents.pure_functions import truncate_message
        message = truncate_message(message)
        
        print(f"✓ Generated message ({len(message)} characters):")
        print(f"   {message[:100]}..." if len(message) > 100 else f"   {message}")
        
        # Store message in memory
        try:
            postgres = get_postgres_memory()
            if postgres:
                await postgres.store_interaction_history(
                    lead_id=lead["id"],
                    interaction_type="message_generated",
                    data={
                        "message": message,
                        "timestamp": "2026-05-27T10:35:00Z",
                        "channel": "whatsapp"
                    }
                )
                
                # Store short-term context in Redis
                redis = get_redis_memory()
                if redis:
                    await redis.store_conversation_context(
                        lead_id=lead["id"],
                        context={
                            "last_message": message,
                            "message_type": "initial_outreach",
                            "timestamp": "2026-05-27T10:35:00Z",
                            "next_step": "awaiting_response"
                        },
                        ttl=86400  # 24 hours
                    )
                print("✓ Message and context stored in memory")
        except Exception as e:
            print(f"⚠ Could not store message in memory: {e}")
        
        # 5. Research (for high-score leads)
        if score >= 70:
            print("✓ Lead qualifies for deep research (score >= 70)")
            # Would call researcher agent here
        else:
            print(f"○ Lead does not qualify for deep research (score < 70: {score})")
    else:
        print("✗ Lead score too low (< 20), not generating message")
        lead["status"] = "descartado"
    
    # 6. Demonstrate memory retrieval
    print("\n--- Demonstrating Memory Retrieval ---")
    try:
        postgres = get_postgres_memory()
        if postgres:
            # Retrieve dossiê
            dossie_from_memory = await postgres.retrieve_lead_memory(
                lead_id=lead["id"],
                memory_type="dossie"
            )
            if dossie_from_memory:
                print(f"✓ Retrieved dossiê from PostgreMemory: {dossie_from_memory['resumo_perfil'][:50]}...")
            
            # Retrieve score
            score_from_memory = await postgres.retrieve_lead_memory(
                lead_id=lead["id"],
                memory_type="score"
            )
            if score_from_memory:
                print(f"✓ Retrieved score from PostgreMemory: {score_from_memory['score']}/100")
            
            # Retrieve interaction history
            history = await postgres.retrieve_interaction_history(
                lead_id=lead["id"],
                limit=5
            )
            print(f"✓ Retrieved {len(history)} interaction(s) from history")
            
        # Retrieve conversation context from Redis
        redis = get_redis_memory()
        if redis:
            context = await redis.retrieve_conversation_context(lead_id=lead["id"])
            if context:
                print(f"✓ Retrieved conversation context from Redis: {context.get('last_message', '')[:50]}...")
    except Exception as e:
        print(f"⚠ Error during memory retrieval: {e}")
    
    # 7. Clean shutdown
    try:
        from agents.runtime import shutdown_memory_managers_async
        await shutdown_memory_managers_async()
        print("\n✓ Memory managers shut down")
    except Exception as e:
        print(f"⚠ Error during shutdown: {e}")
    
    print("\n=== Lead Processing Example Complete ===")
    return lead

async def example_similarity_search():
    """Example showing how to use similarity search for lead matching."""
    print("\n=== Similarity Search Example ===")
    
    try:
        from agents.runtime import get_qdrant_memory
        import numpy as np
        
        # Get Qdrant memory manager
        qdrant = get_qdrant_memory()
        if not qdrant:
            print("⚠ Qdrant memory manager not available")
            return
        
        # In a real implementation, you would generate embeddings from lead data
        # For this example, we'll use random vectors
        print("Generating example lead embeddings...")
        
        # Store some example leads
        lead_ids = ["lead_001", "lead_002", "lead_003"]
        embeddings = [
            np.random.rand(384).tolist(),  # Restaurant embedding
            np.random.rand(384).tolist(),  # Similar restaurant embedding  
            np.random.rand(384).tolist()   # Different business embedding
        ]
        
        payloads = [
            {"name": "Restaurante A", "type": "restaurant", "rating": 4.2},
            {"name": "Restaurante B", "type": "restaurant", "rating": 4.5},
            {"name": "Loja de Roupas C", "type": "retail", "rating": 3.8}
        ]
        
        # Store in Qdrant (would normally be done by agents)
        await qdrant.store_similar_memories(
            memory_type="lead_embedding",
            vectors=embeddings,
            payloads=payloads
        )
        print("✓ Stored example lead embeddings in Qdrant")
        
        # Now search for similar leads to the first one
        query_vector = embeddings[0]  # Use first embedding as query
        similar_results = await qdrant.search_similar_memories(
            query_vector=query_vector,
            memory_type="lead_embedding",
            limit=3
        )
        
        print(f"✓ Found {len(similar_results)} similar leads:")
        for i, result in enumerate(similar_results):
            print(f"   {i+1}. {result['payload'].get('name', 'Unknown')} "
                  f"(similarity: {result['score']:.3f})")
                  
    except Exception as e:
        print(f"⚠ Similarity search example failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all examples."""
    print("Kirin Platform Usage Examples")
    print("=" * 50)
    
    # Run lead processing example
    lead = await example_lead_processing()
    
    # Run similarity search example
    await example_similarity_search()
    
    print("\n" + "=" * 50)
    print("All examples completed!")

if __name__ == "__main__":
    asyncio.run(main())
