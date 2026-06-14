"""
Pure functions for the Kirin platform.
These functions are testable without external dependencies.
"""

# Constants
VALID_STATUSES = [
    "novo",
    "contato_inicial",
    "agendamento",
    "enriquecido",
    "qualificado",
    "mensagem_enviada",
    "respondeu",
    "vendido",
    "repassado",
    "descartado"
]

BLOCKED_STATUSES = {"vendido", "repassado", "descartado"}

def normalize_score(score: float) -> int:
    """
    Normalize score to integer in range [0, 100].
    
    Args:
        score: Raw score value
        
    Returns:
        Integer score between 0 and 100
    """
    normalized = max(0, min(100, round(score)))
    return normalized

def classify_faixa(score: int) -> str:
    """
    Classify lead into faixa based on score.
    
    Args:
        score: Integer score between 0 and 100
        
    Returns:
        Faixa classification: "frio", "morno", or "quente"
    """
    if score <= 39:
        return "frio"
    elif score <= 69:
        return "morno"
    else:
        return "quente"

def deduplicate_leads(leads: list) -> list:
    """
    Remove duplicate leads based on google_maps_id.
    
    Args:
        leads: List of lead dictionaries
        
    Returns:
        List of leads with duplicates removed
    """
    seen_ids = set()
    unique_leads = []
    
    for lead in leads:
        lead_id = lead.get("google_maps_id")
        if lead_id and lead_id not in seen_ids:
            seen_ids.add(lead_id)
            unique_leads.append(lead)
        elif not lead_id:
            # Leads without ID are kept (they'll be deduplicated by other means)
            unique_leads.append(lead)
            
    return unique_leads

def compute_instagram_inativo(last_post_date: str) -> bool:
    """
    Determine if Instagram profile is inactive (>90 days since last post).
    
    Args:
        last_post_date: Date string in ISO format (YYYY-MM-DD)
        
    Returns:
        True if inactive, False otherwise
    """
    from datetime import datetime, date
    
    try:
        last_post = datetime.fromisoformat(last_post_date.replace('Z', '+00:00')).date()
        today = date.today()
        delta = today - last_post
        return delta.days > 90
    except Exception:
        # If date parsing fails, assume active to avoid false positives
        return False

def truncate_message(message: str, max_length: int = 300) -> str:
    """
    Truncate message to maximum length.
    
    Args:
        message: Message to truncate
        max_length: Maximum allowed length
        
    Returns:
        Truncated message
    """
    if len(message) <= max_length:
        return message
    return message[:max_length]

def is_valid_status(status: str) -> bool:
    """
    Check if status is valid according to VALID_STATUSES.
    
    Args:
        status: Status string to validate
        
    Returns:
        True if status is valid, False otherwise
    """
    return status in VALID_STATUSES

def can_send_message_sync(lead: dict) -> bool:
    """
    Check if a message can be sent to the lead based on status.
    
    Args:
        lead: Lead dictionary
        
    Returns:
        True if message can be sent, False otherwise
    """
    status = lead.get("status", "")
    return status not in BLOCKED_STATUSES

def truncate_dossie_for_scoring(dossie: dict, max_resumo: int = 300) -> dict:
    """Reduz dossiê ao mínimo necessário para scoring — economiza 60-80% de tokens."""
    return {
        "resumo_perfil": dossie.get("resumo_perfil", "")[:max_resumo],
        "pontos_fracos": dossie.get("pontos_fracos", [])[:3],
        "oportunidades": dossie.get("oportunidades", [])[:2],
        "maturidade_digital": dossie.get("maturidade_digital", "médio"),
    }
