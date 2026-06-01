"""
ProspectAgent for Kirin Pair.
Handles lead enrichment, scoring, and outreach generation for workspace prospects.
"""
from typing import Dict, Any, List, Optional
import logging
import os
from datetime import datetime

from agents.runtime import get_postgres_memory, get_qdrant_memory
from agents.memory.postgres_memory import PostgresMemoryManager
from agents.memory.qdrant_memory import QdrantMemoryManager
from agents.enricher import enrich_lead
from agents.scorer import score_lead
from agents.messenger import generate_message

logger = logging.getLogger(__name__)

class ProspectAgent:
    """
    Agent responsible for prospect-related operations including enrichment,
    scoring, and message generation for outreach campaigns.
    """
    
    def __init__(self):
        self.postgres: Optional[PostgresMemoryManager] = get_postgres_memory()
        self.qdrant: Optional[QdrantMemoryManager] = get_qdrant_memory()
        
    async def enrich_and_score_lead(
        self, 
        lead_data: Dict[str, Any],
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Enrich and score a lead using the kirin-platform enrichment and scoring pipelines.
        
        Args:
            lead_data: Basic lead information (name, email, company, etc.)
            workspace_id: The workspace this lead belongs to
            
        Returns:
            Dictionary containing enriched and scored lead data
        """
        if not self.postgres or not self.qdrant:
            logger.error("Memory managers not initialized")
            return lead_data
            
        try:
            # Add workspace context to the lead
            lead_data["workspace_id"] = workspace_id
            lead_data["created_at"] = datetime.utcnow().isoformat()
            
            # Get configuration for LiteLLM
            litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
            api_key = os.getenv("QWEN_VL_MAX_API_KEY", "")
            
            # Step 1: Enrich the lead using the kirin-platform enricher
            enriched_lead = await enrich_lead(lead_data, litellm_url, api_key)
            
            # Step 2: Score the enriched lead using the kirin-platform scorer
            scored_lead = await score_lead(enriched_lead, litellm_url, api_key)
            
            logger.info(f"Enriched and scored lead for workspace {workspace_id}")
            return scored_lead
            
        except Exception as e:
            logger.error(f"Error enriching and scoring lead: {e}")
            # Return original lead data on error
            return lead_data
    
    async def generate_outreach_message(
        self, 
        lead_data: Dict[str, Any],
        workspace_id: str,
        style_profile: Optional[Dict[str, Any]] = None,
        message_type: str = "initial_outreach"
    ) -> Dict[str, Any]:
        """
        Generate an outreach message for a lead based on workspace style and lead data.
        
        Args:
            lead_data: The lead data (should include enrichment and scoring)
            workspace_id: The workspace this lead belongs to
            style_profile: Optional style profile to guide message generation
            message_type: Type of message to generate (initial_outreach, follow_up, etc.)
            
        Returns:
            Dictionary containing the generated message and metadata
        """
        if not self.postgres:
            logger.error("PostgreSQL memory manager not initialized")
            return {"error": "Memory manager not initialized"}
            
        try:
            # Prepare context for message generation
            message_context = {
                "lead_data": lead_data,
                "workspace_id": workspace_id,
                "message_type": message_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add style profile if provided
            if style_profile:
                message_context["style_profile"] = style_profile
                
            # Generate message using the kirin-platform messenger
            # In a real implementation, we'd pass the context to generate_message
            # For now, we'll create a basic message structure
            
            generated_message = await self._create_outreach_message(
                lead_data, 
                workspace_id, 
                style_profile, 
                message_type
            )
            
            logger.info(f"Generated outreach message for lead {lead_data.get('id', 'unknown')}")
            return generated_message
            
        except Exception as e:
            logger.error(f"Error generating outreach message: {e}")
            return {"error": str(e)}
    
    async def _create_outreach_message(
        self, 
        lead_data: Dict[str, Any],
        workspace_id: str,
        style_profile: Optional[Dict[str, Any]],
        message_type: str
    ) -> Dict[str, Any]:
        """
        Create an outreach message based on lead data and style profile.
        
        This is a simplified implementation - in reality, this would
        use the kirin-platform messenger with appropriate context.
        """
        # Extract lead information
        lead_name = lead_data.get("name", "there")
        lead_company = lead_data.get("company", "")
        lead_title = lead_data.get("title", "")
        
        # Determine greeting based on style
        greeting = "Olá"  # Default
        if style_profile:
            formality = style_profile.get("formality_score", 0.5)
            if formality > 0.7:
                greeting = "Prezado"
            elif formality < 0.3:
                greeting = "Oi"
        
        # Determine closing based on style
        closing = "Abs"  # Default
        if style_profile:
            closing_variety = style_profile.get("closing_variety", ["abs"])
            if closing_variety:
                closing = closing_variety[0]
        
        # Build message content based on type
        if message_type == "initial_outreach":
            if lead_company and lead_title:
                content = f"{greeting} {lead_name},\n\n" \
                         f"Vi que você trabalha como {lead_title} na {lead_company} " \
                         f"e acredito que nossa solução poderia ajudar vocês a " \
                         f"melhorar seus resultados. Gostaria de marcar uma conversa " \
                         f"rápida para entender melhor seus desafios atuais?\n\n" \
                         f"{closing},\n[Seu Nome]"
            else:
                content = f"{greeting} {lead_name},\n\n" \
                         f"Estou entrando em contato porque acredito que podemos ajudar " \
                         f"seu negócio a alcançar melhores resultados. " \
                         f"Quando seria um bom momento para uma breve conversa?\n\n" \
                         f"{closing},\n[Seu Nome]"
        elif message_type == "follow_up":
            content = f"{greeting} {lead_name},\n\n" \
                     f"Queria seguir up na minha mensagem anterior sobre como podemos " \
                     f"ajudar {lead_company or 'seu negócio'} a melhorar performance. " \
                     f"Você teve chance de pensar nisso?\n\n" \
                     f"{closing},\n[Seu Nome]"
        else:
            # Generic message
            content = f"{greeting} {lead_name},\n\n" \
                     f"Mensagem sobre oportunidades de melhoria para {lead_company or 'seu negócio'}.\n\n" \
                     f"{closing},\n[Seu Nome]"
        
        return {
            "id": f"msg_{datetime.utcnow().timestamp()}",
            "lead_id": lead_data.get("id"),
            "workspace_id": workspace_id,
            "message_type": message_type,
            "content": content,
            "generated_at": datetime.utcnow().isoformat(),
            "style_used": style_profile is not None
        }
    
    async def process_new_lead(
        self, 
        lead_data: Dict[str, Any],
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Process a new lead through the full prospecting pipeline:
        enrichment -> scoring -> message generation.
        
        Args:
            lead_data: Basic lead information
            workspace_id: The workspace this lead belongs to
            
        Returns:
            Dictionary containing the processed lead with enrichment, scoring, and message
        """
        try:
            # Step 1: Enrich and score the lead
            processed_lead = await self.enrich_and_score_lead(lead_data, workspace_id)
            
            # Step 2: Get or generate style profile for the workspace
            # In a real implementation, we'd fetch from ProfileStudyAgent or cache
            style_profile = None  # Placeholder
            
            # Step 3: Generate outreach message
            message = await self.generate_outreach_message(
                processed_lead, 
                workspace_id, 
                style_profile,
                "initial_outreach"
            )
            
            # Combine results
            result = {
                "lead": processed_lead,
                "outreach_message": message,
                "processed_at": datetime.utcnow().isoformat(),
                "workspace_id": workspace_id
            }
            
            logger.info(f"Processed new lead for workspace {workspace_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing new lead: {e}")
            return {
                "error": str(e),
                "lead": lead_data,
                "workspace_id": workspace_id
            }

# Factory function to create agent instance
def get_prospect_agent() -> ProspectAgent:
    """Factory function to create a ProspectAgent instance."""
    return ProspectAgent()
