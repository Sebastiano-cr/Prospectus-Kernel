"""
Prometheus metrics for the Kirin platform agents.
"""
from prometheus_client import Counter, Histogram, Gauge

# Lead extraction metrics
kirin_leads_extracted_total = Counter(
    'kirin_leads_extracted_total',
    'Total number of leads extracted',
    ['source']
)

# Enrichment metrics
kirin_enrichment_success_total = Counter(
    'kirin_enrichment_success_total',
    'Total number of successful lead enrichments'
)

kirin_enrichment_failed_total = Counter(
    'kirin_enrichment_failed_total',
    'Total number of failed lead enrichments'
)

# Scoring metrics
kirin_lead_score = Histogram(
    'kirin_lead_score',
    'Distribution of lead scores',
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

# Messaging metrics
kirin_messages_sent_total = Counter(
    'kirin_messages_sent_total',
    'Total number of WhatsApp messages sent',
    ['status']  # enviado, falha, etc.
)

# Error metrics
kirin_errors_total = Counter(
    'kirin_errors_total',
    'Total number of errors in agents',
    ['component']  # enricher, scorer, messenger, etc.
)

# Active leads gauge
kirin_active_leads = Gauge(
    'kirin_active_leads',
    'Number of currently active leads in the system',
    ['status']  # novo, enriquecido, qualificado, etc.
)

# Discourse pipeline metrics
kirin_discourse_ingested_total = Counter(
    'kirin_discourse_ingested_total',
    'Total number of discourse fragments ingested',
    ['source']  # reddit, youtube, linkedin, telegram, sales_call, etc.
)

kirin_language_game_analyzed_total = Counter(
    'kirin_language_game_analyzed_total',
    'Total number of language game analyses completed'
)

kirin_resonance_lookup_total = Counter(
    'kirin_resonance_lookup_total',
    'Total number of resonance pattern lookups',
    ['market_cluster']
)

kirin_prospect_generated_total = Counter(
    'kirin_prospect_generated_total',
    'Total number of prospect profiles generated'
)

kirin_discourse_latency_seconds = Histogram(
    'kirin_discourse_latency_seconds',
    'Latency of the discourse analysis pipeline in seconds',
    ['layer']  # ingestion, language_game, resonance, prospect
)
