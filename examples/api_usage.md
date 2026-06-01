# Kirin Platform API Usage Examples

This document shows how to interact with the Kirin platform using HTTP requests.

## Prerequisites

Make sure the Kirin platform is running:
```bash
docker-compose up -d
```

The API will be available at `http://localhost:8000`.

## Lead Processing Pipeline Example

### 1. Enrich a Lead

```bash
curl -X POST "http://localhost:8000/enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "google_maps_id_12345",
    "name": "Restaurante Sabor Mineiro",
    "address": "Rua das Flores, 123, Belo Horizonte, MG",
    "phone": "+55 31 9999-9999",
    "website": "",
    "instagram_username": "sabor_mineiro",
    "rating": 4.5,
    "google_maps_url": "https://maps.google.com/?cid=12345"
  }'
```

Expected response:
```json
{
  "id": "google_maps_id_12345",
  "name": "Restaurante Sabor Mineiro",
  "address": "Rua das Flores, 123, Belo Horizonte, MG",
  "phone": "+55 31 9999-9999",
  "website": "",
  "instagram_username": "sabor_mineiro",
  "rating": 4.5,
  "google_maps_url": "https://maps.google.com/?cid=12345",
  "enrichment_success": true,
  "dossie": {
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
}
```

### 2. Score the Enriched Lead

```bash
curl -X POST "http://localhost:8000/score" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "google_maps_id_12345",
    "name": "Restaurante Sabor Mineiro",
    "address": "Rua das Flores, 123, Belo Horizonte, MG",
    "phone": "+55 31 9999-9999",
    "website": "",
    "instagram_username": "sabor_mineiro",
    "rating": 4.5,
    "google_maps_url": "https://maps.google.com/?cid=12345",
    "enrichment_success": true,
    "dossie": {
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
  }'
```

Expected response:
```json
{
  "id": "google_maps_id_12345",
  "name": "Restaurante Sabor Mineiro",
  "address": "Rua das Flores, 123, Belo Horizonte, MG",
  "phone": "+55 31 9999-9999",
  "website": "",
  "instagram_username": "sabor_mineiro",
  "rating": 4.5,
  "google_maps_url": "https://maps.google.com/?cid=12345",
  "enrichment_success": true,
  "dossie": {
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
  },
  "score": 65,
  "justification": "O lead apresenta bom potencial devido à alta avaliação (4.5/5) e conceito de comida caseira, mas possui limitações digitais significativas que podem ser superadas com investimentos moderados em presença online e sistemas de pedido.",
  "faixa": "morno"
}
```

### 3. Generate a WhatsApp Message

```bash
curl -X POST "http://localhost:8000/generate_message" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "google_maps_id_12345",
    "name": "Restaurante Sabor Mineiro",
    "address": "Rua das Flores, 123, Belo Horizonte, MG",
    "phone": "+55 31 9999-9999",
    "website": "",
    "instagram_username": "sabor_mineiro",
    "rating": 4.5,
    "google_maps_url": "https://maps.google.com/?cid=12345",
    "enrichment_success": true,
    "dossie": {
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
    },
    "score": 65,
    "faixa": "morno"
  }'
```

Expected response:
```json
{
  "message": "Olá! Vi que o Restaurante Sabor Mineiro tem um potencial incrível para crescer ainda mais online. \n\nPercebi que vocês não têm website atualmente, o que está limitando seu alcance. Gostaria de sugerir algumas melhorias:\n1. Criar um site simples com menu, localização e horários\n2. Implementar um sistema de reservas online\n3. Começar a aceitar pedidos via delivery\n4. Melhorar a presença no Instagram com postagens regulares\n\nPosso ajudar a implementar essas soluções. Quando seria um bom horário para conversarmos?"
}
```

### 4. Research a High-Value Lead (Score >= 70)

For leads with score >= 70, you can trigger deep research:

```bash
curl -X POST "http://localhost:8000/research" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "google_maps_id_67890",
    "name": "Restaurante Bom Sabor",
    "address": "Av. Afonso Pena, 456, Belo Horizonte, MG",
    "phone": "+55 31 8888-8888",
    "website": "www.restaurantebomsabor.com.br",
    "instagram_username": "restaurantebomsabor",
    "rating": 4.8,
    "google_maps_url": "https://maps.google.com/?cid=67890",
    "enrichment_success": true,
    "dossie": {
      "resumo_perfil": "Restaurante sofisticado com cozinha contemporânea e excelente serviço",
      "pontos_fracos": [
        "Website não otimizado para mobile",
        "Pouco uso de reservas online",
        "Ausência de programa de fidelidade"
      ],
      "oportunidades": [
        "Otimizar website para dispositivos móveis",
        "Implementar sistema de reservas online integrado",
        "Criar programa de fidelidade para clientes frequentes",
        "Explorar parcerias com hotéis para pacotes de turismo gastronômico"
      ],
      "maturidade_digital": "médio"
    },
    "score": 85,
    "justification": "Este restaurante apresenta excelente potencial devido à alta avaliação, estabelecida presença digital e oportunidades claras de aprimoramento que podem aumentar significativamente receita e satisfação do cliente.",
    "faixa": "quente"
  }'
```

Expected response:
```json
{
  "id": "google_maps_id_67890",
  "name": "Restaurante Bom Sabor",
  "address": "Av. Afonso Pena, 456, Belo Horizonte, MG",
  "phone": "+55 31 8888-8888",
  "website": "www.restaurantebomsabor.com.br",
  "instagram_username": "restaurantebomsabor",
  "rating": 4.8,
  "google_maps_url": "https://maps.google.com/?cid=67890",
  "enrichment_success": true,
  "dossie": {
    "resumo_perfil": "Restaurante sofisticado com cozinha contemporânea e excelente serviço",
    "pontos_fracos": [
      "Website não otimizado para mobile",
      "Pouco uso de reservas online",
      "Ausência de programa de fidelidade"
    ],
    "oportunidades": [
      "Otimizar website para dispositivos móveis",
      "Implementar sistema de reservas online integrado",
      "Criar programa de fidelidade para clientes frequentes",
      "Explorar parcerias com hotéis para pacotes de turismo gastronômico"
    ],
    "maturidade_digital": "médio"
  },
  "score": 85,
  "justification": "Este restaurante apresenta excelente potencial devido à alta avaliação, estabelecida presença digital e oportunidades claras de aprimoramento que podem aumentar significativamente receita e satisfação do cliente.",
  "faixa": "quente",
  "research_results": {
    "fontes_consultadas": [
      {
        "tipo": "site",
        "url": "www.restaurantebomsabor.com.br",
        "titulo": "Restaurante Bom Sabor - Site Oficial",
        "conteudo": "Site oficial do restaurante com menu, reservas e informações de contato."
      },
      {
        "tipo": "instagram",
        "url": "instagram.com/restaurantebomsabor",
        "titulo": "Instagram do Restaurante Bom Sabor",
        "conteudo": "Perfil do Instagram com fotos dos pratos, eventos e depoimentos de clientes."
      }
    ],
    "insights": [
      "O restaurante tem forte presença online mas pode melhorar a conversão de visitantes em clientes através de otimização mobile.",
      "Há oportunidade de aumentar o ticket médio através de harmonização de vinhos e sobremesas especiais.",
      "O público-alvo inclui tanto empresários em almoços rápidos quanto casais em jantares românticos."
    ],
    "recommendations": [
      "Implementar menu digital interativo com fotos dos pratos",
      "Criar combos executivos para o público empresarial",
      "Desenvolver programa de pontos que possa ser trocado por descontos ou experiências especiais",
      "Investir em anúncios segmentados no Facebook e Instagram para alcançar novos públicos"
    ]
  }
}
```

### 5. Sync with CRM

```bash
curl -X POST "http://localhost:8000/crm_sync" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "google_maps_id_12345",
    "name": "Restaurante Sabor Mineiro",
    "address": "Rua das Flores, 123, Belo Horizonte, MG",
    "phone": "+55 31 9999-9999",
    "website": "",
    "instagram_username": "sabor_mineiro",
    "rating": 4.5,
    "google_maps_url": "https://maps.google.com/?cid=12345",
    "enrichment_success": true,
    "dossie": {
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
    },
    "score": 65,
    "faixa": "morno",
    "status": "novo"
  }'
```

Expected response (will vary based on CRM provider):
```json
{
  "success": true,
  "id": "notion_google_maps_id_12345",
  "operation": "upserted",
  "lead": {
    "name": "Restaurante Sabor Mineiro",
    "phone": "+55 31 9999-9999",
    "address": "Rua das Flores, 123, Belo Horizonte, MG",
    "website": "",
    "instagram_username": "sabor_mineiro",
    "score": 65,
    "faixa": "morno",
    "dossie_resumo": "Restaurant tradicional mineiro com comida caseira e ambiente familiar",
    "status": "novo",
    "updated_at": "2026-05-27T10:45:00Z"
  }
}
```

## Memory Health Check

Check the status of all memory managers:

```bash
curl -X GET "http://localhost:8000/memory/health"
```

Expected response:
```json
{
  "postgres": true,
  "qdrant": true,
  "redis": true
}
```

## Metrics Endpoint

Access Prometheus metrics:

```bash
curl -X GET "http://localhost:8000/metrics"
```

This will return metrics in Prometheus text format, including:
- Lead processing counters
- Enrichment success/failure rates
- Lead score distribution
- Message sending statistics
- Error rates by component
- Active leads in memory

## Error Handling

All endpoints return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request (invalid input)
- 500: Internal Server Error
- 503: Service Unavailable (if dependencies are not available)

Error responses follow a structured format:
```json
{
  "detail": "Error description"
}
```

For MCP server errors (used internally), the format is:
```json
{
  "error_code": "ERROR_CODE",
  "error_message": "Human readable error message",
  "retry_after": 30  // optional, seconds to wait before retrying
}
```
