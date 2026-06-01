"""
ProfileStudyAgent for Kirin Pair.
Analyzes communication history to build and update workspace style profiles.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from agents.runtime import get_postgres_memory, get_qdrant_memory
from agents.memory.postgres_memory import PostgresMemoryManager
from agents.memory.qdrant_memory import QdrantMemoryManager

logger = logging.getLogger(__name__)

class ProfileStudyAgent:
    """
    Agent responsible for studying communication patterns to build style profiles.
    This agent analyzes historical communications to understand a creator's style,
    preferences, and communication patterns.
    """
    
    def __init__(self):
        self.postgres: Optional[PostgresMemoryManager] = get_postgres_memory()
        self.qdrant: Optional[QdrantMemoryManager] = get_qdrant_memory()
        
    async def analyze_workspace_communications(
        self, 
        workspace_id: str, 
        days_back: int = 30,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Analyze workspace communications from the last N days to build a style profile.
        
        Args:
            workspace_id: The workspace to analyze
            days_back: How many days back to look for communications
            limit: Maximum number of communications to analyze
            
        Returns:
            Dictionary containing the analyzed style profile
        """
        if not self.postgres or not self.qdrant:
            logger.error("Memory managers not initialized")
            return {}
            
        try:
            # Calculate the cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # Get communications from the workspace
            # This would typically query a communications table or similar
            # For now, we'll simulate getting some data
            communications = await self._get_workspace_communications(
                workspace_id, cutoff_date, limit
            )
            
            if not communications:
                logger.warning(f"No communications found for workspace {workspace_id}")
                return self._get_default_profile()
                
            # Analyze the communications to extract style features
            style_profile = await self._extract_style_features(communications)
            
            # Add metadata
            style_profile.update({
                "workspace_id": workspace_id,
                "analyzed_at": datetime.utcnow().isoformat(),
                "communications_analyzed": len(communications),
                "days_back": days_back
            })
            
            logger.info(f"Analyzed {len(communications)} communications for workspace {workspace_id}")
            return style_profile
            
        except Exception as e:
            logger.error(f"Error analyzing workspace communications: {e}")
            return self._get_default_profile()
    
    async def _get_workspace_communications(
        self, 
        workspace_id: str, 
        cutoff_date: datetime, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve communications for a workspace from the database.
        
        In a real implementation, this would query a communications table.
        For now, we'll return mock data to demonstrate the structure.
        """
        # This is a placeholder - in reality, you'd query your communications table
        # Example SQL: SELECT * FROM communications WHERE workspace_id = $1 AND timestamp > $2 LIMIT $3
        
        # Mock data for demonstration
        mock_communications = [
            {
                "id": "comm_1",
                "workspace_id": workspace_id,
                "content": "Olá! Tudo bem? Espero que esteja tendo um ótimo dia. Gostaria de saber se você teve a chance de revisar a proposta que enviei na semana passada.",
                "timestamp": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "channel": "email",
                "direction": "outbound"
            },
            {
                "id": "comm_2", 
                "workspace_id": workspace_id,
                "content": "Oi! Tudo joia! A proposta ficou ótima, vamos seguir com o prazo de 15 dias? Me avisa se precisar de ajustes.",
                "timestamp": (datetime.utcnow() - timedelta(days=5)).isoformat(),
                "channel": "whatsapp",
                "direction": "inbound"
            },
            {
                "id": "comm_3",
                "workspace_id": workspace_id, 
                "content": "Prezado senhor,\n\nReferente ao nosso encontro de ontem, segue em anexo o documento solicitado.\n\nAtenciosamente,\n[Nome]",
                "timestamp": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "channel": "email",
                "direction": "outbound"
            }
        ]
        
        # Filter by cutoff date (in mock data, we assume all are recent enough)
        return mock_communications[:limit]
    
    async def _extract_style_features(
        self, 
        communications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract style features from a list of communications.
        
        Args:
            communications: List of communication dictionaries
            
        Returns:
            Dictionary containing style features
        """
        if not communications:
            return self._get_default_profile()
            
        # Initialize feature counters
        total_messages = len(communications)
        avg_length = 0
        formality_scores = []
        greeting_variety = set()
        closing_variety = set()
        question_count = 0
        exclamation_count = 0
        
        # Analyze each communication
        for comm in communications:
            content = comm.get("content", "").strip()
            if not content:
                continue
                
            # Length
            avg_length += len(content)
            
            # Formality indicators (simplified)
            formal_indicators = ["prezado", "senhor", "atenciosamente", "segue em anexo"]
            informal_indicators = ["oi", "olá", "tudo bem", "joia", "vlw", "abs"]
            
            formal_count = sum(1 for indicator in formal_indicators if indicator in content.lower())
            informal_count = sum(1 for indicator in informal_indicators if indicator in content.lower())
            
            # Simple formality score (0-1, where 1 is more formal)
            total_indicators = formal_count + informal_count
            if total_indicators > 0:
                formality_score = formal_count / total_indicators
            else:
                formality_score = 0.5  # Neutral
            formality_scores.append(formality_score)
            
            # Greetings
            greetings = ["oi", "olá", "bom dia", "boa tarde", "boa noite", "prezado", "prezada"]
            for greeting in greetings:
                if content.lower().startswith(greeting):
                    greeting_variety.add(greeting)
                    break
                    
            # Closings
            closings = ["atenciosamente", "abs", "abraços", "grato", "obrigado", "valeu", "[]s"]
            for closing in closings:
                if closing in content.lower():
                    closing_variety.add(closing)
                    break
                    
            # Questions and exclamations
            question_count += content.count("?")
            exclamation_count += content.count("!")
        
        # Calculate averages
        avg_length = avg_length / total_messages if total_messages > 0 else 0
        avg_formality = sum(formality_scores) / len(formality_scores) if formality_scores else 0.5
        
        # Determine primary style
        if avg_formality > 0.7:
            primary_style = "formal"
        elif avg_formality < 0.3:
            primary_style = "informal"
        else:
            primary_style = "balanced"
            
        # Build the style profile
        style_profile = {
            "primary_style": primary_style,
            "formality_score": round(avg_formality, 3),
            "average_message_length": round(avg_length, 1),
            "greeting_variety": list(greeting_variety),
            "closing_variety": list(closing_variety),
            "questions_per_message": round(question_count / total_messages, 2) if total_messages > 0 else 0,
            "exclamations_per_message": round(exclamation_count / total_messages, 2) if total_messages > 0 else 0,
            "communication_channels": list(set(comm.get("channel", "unknown") for comm in communications)),
            "communication_directions": list(set(comm.get("direction", "unknown") for comm in communications))
        }
        
        return style_profile
    
    def _get_default_profile(self) -> Dict[str, Any]:
        """Return a default style profile when no data is available."""
        return {
            "primary_style": "balanced",
            "formality_score": 0.5,
            "average_message_length": 100.0,
            "greeting_variety": ["oi", "olá"],
            "closing_variety": ["abs", "valeu"],
            "questions_per_message": 0.5,
            "exclamations_per_message": 0.5,
            "communication_channels": ["email", "whatsapp"],
            "communication_directions": ["inbound", "outbound"]
        }
    
    async def update_workspace_profile(
        self, 
        workspace_id: str, 
        style_profile: Dict[str, Any]
    ) -> bool:
        """
        Update or create a style profile for a workspace in the database.
        
        Args:
            workspace_id: The workspace ID
            style_profile: The style profile to save
            
        Returns:
            True if successful, False otherwise
        """
        if not self.postgres:
            logger.error("PostgreSQL memory manager not initialized")
            return False
            
        try:
            # In a real implementation, this would insert/update a style_profiles table
            # Example: INSERT INTO style_profiles (workspace_id, profile_data, updated_at) 
            #          VALUES ($1, $2, $3) ON CONFLICT (workspace_id) DO UPDATE SET ...
            
            logger.info(f"Style profile updated for workspace {workspace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating workspace profile: {e}")
            return False
    
    async def get_workspace_profile(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a workspace's style profile from the database.
        
        Args:
            workspace_id: The workspace ID
            
        Returns:
            The style profile if found, None otherwise
        """
        if not self.postgres:
            logger.error("PostgreSQL memory manager not initialized")
            return None
            
        try:
            # In a real implementation, this would query the style_profiles table
            # Example: SELECT profile_data FROM style_profiles WHERE workspace_id = $1
            
            # For now, return None to indicate not found (would trigger analysis)
            return None
            
        except Exception as e:
            logger.error(f"Error getting workspace profile: {e}")
            return None

# Factory function to create agent instance
def get_profile_study_agent() -> ProfileStudyAgent:
    """Factory function to create a ProfileStudyAgent instance."""
    return ProfileStudyAgent()
