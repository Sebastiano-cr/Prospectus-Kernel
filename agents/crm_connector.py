"""
CRM Connector for the Kirin platform.
Provides abstract base class and concrete implementations for various CRM systems.
"""
import abc
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import httpx
import os

logger = logging.getLogger(__name__)


class CRMAdapter(ABC):
    """Abstract base class for CRM adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def upsert_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert or update a lead in the CRM.
        
        Args:
            lead: Lead dictionary to upsert
            
        Returns:
            Result of the upsert operation
        """
        pass
    
    @abstractmethod
    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a lead from the CRM by ID.
        
        Args:
            lead_id: Unique identifier for the lead
            
        Returns:
            Lead dictionary if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update_status(self, lead_id: str, status: str) -> Dict[str, Any]:
        """
        Update the status of a lead in the CRM.
        
        Args:
            lead_id: Unique identifier for the lead
            status: New status to set
            
        Returns:
            Result of the update operation
        """
        pass


class NotionAdapter(CRMAdapter):
    """Notion CRM adapter implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config.get("NOTION_TOKEN") or os.getenv("NOTION_TOKEN", "")
        self.database_id = config.get("NOTION_DATABASE_ID") or os.getenv("NOTION_DATABASE_ID", "")
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    async def upsert_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert lead to Notion database."""
        async with httpx.AsyncClient() as client:
            # Build properties for Notion database
            properties = {
                "Name": {"title": [{"text": {"content": lead.get("name", "Unknown")}}]},
                "Phone": {"rich_text": [{"text": {"content": lead.get("phone", "")}}]},
                "Address": {"rich_text": [{"text": {"content": lead.get("address", "")}}]},
                "Website": {"url": lead.get("website") or None},
                "Instagram": {"rich_text": [{"text": {"content": lead.get("instagram_username", "")}}]},
                "Score": {"number": lead.get("score", 0)},
                "Faixa": {"select": {"name": lead.get("faixa", "morno")}},
                "Status": {"select": {"name": lead.get("status", "novo")}},
                "Dossie Resumo": {"rich_text": [{"text": {"content": lead.get("dossie", {}).get("resumo_perfil", "")[:2000]}}]}
            }
            
            # Remove None values
            properties = {k: v for k, v in properties.items() if v.get("url") is not None or "title" in v or "rich_text" in v or "number" in v or "select" in v}
            
            payload = {
                "parent": {"database_id": self.database_id},
                "properties": properties
            }
            
            response = await client.post(
                f"{self.base_url}/pages",
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "id": data.get("id"),
                    "operation": "created",
                    "lead": lead
                }
            else:
                logger.error(f"Notion API error: {response.status_code} - {response.text}")
                raise Exception(f"Notion API error: {response.status_code}")
    
    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve lead from Notion by page ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/pages/{lead_id}",
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                props = data.get("properties", {})
                return {
                    "id": data.get("id"),
                    "name": props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", ""),
                    "phone": props.get("Phone", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
                    "status": props.get("Status", {}).get("select", {}).get("name", "")
                }
            return None
    
    async def update_status(self, lead_id: str, status: str) -> Dict[str, Any]:
        """Update lead status in Notion."""
        async with httpx.AsyncClient() as client:
            payload = {
                "properties": {
                    "Status": {"select": {"name": status}}
                }
            }
            
            response = await client.patch(
                f"{self.base_url}/pages/{lead_id}",
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return {"success": True, "id": lead_id, "status": status}
            else:
                raise Exception(f"Notion API error: {response.status_code}")


class AirtableAdapter(CRMAdapter):
    """Airtable CRM adapter implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("AIRTABLE_API_KEY") or os.getenv("AIRTABLE_API_KEY", "")
        self.base_id = config.get("AIRTABLE_BASE_ID") or os.getenv("AIRTABLE_BASE_ID", "")
        self.table_name = config.get("AIRTABLE_TABLE", "Leads")
        self.base_url = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def upsert_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert lead to Airtable base."""
        async with httpx.AsyncClient() as client:
            fields = {
                "Name": lead.get("name", "Unknown"),
                "Phone": lead.get("phone", ""),
                "Address": lead.get("address", ""),
                "Website": lead.get("website", ""),
                "Instagram": lead.get("instagram_username", ""),
                "Score": lead.get("score", 0),
                "Faixa": lead.get("faixa", "morno"),
                "Status": lead.get("status", "novo"),
                "Dossie Resumo": lead.get("dossie", {}).get("resumo_perfil", "")[:2000]
            }
            
            payload = {"fields": fields}
            
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "id": data.get("id"),
                    "operation": "created",
                    "lead": lead
                }
            else:
                logger.error(f"Airtable API error: {response.status_code} - {response.text}")
                raise Exception(f"Airtable API error: {response.status_code}")
    
    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve lead from Airtable by record ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{lead_id}",
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                fields = data.get("fields", {})
                return {
                    "id": data.get("id"),
                    "name": fields.get("Name", ""),
                    "phone": fields.get("Phone", ""),
                    "status": fields.get("Status", "")
                }
            return None
    
    async def update_status(self, lead_id: str, status: str) -> Dict[str, Any]:
        """Update lead status in Airtable."""
        async with httpx.AsyncClient() as client:
            payload = {"fields": {"Status": status}}
            
            response = await client.patch(
                f"{self.base_url}/{lead_id}",
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return {"success": True, "id": lead_id, "status": status}
            else:
                raise Exception(f"Airtable API error: {response.status_code}")


class NocoDBAdapter(CRMAdapter):
    """NocoDB CRM adapter implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("NOCODB_URL") or os.getenv("NOCODB_URL", "")
        self.token = config.get("NOCODB_TOKEN") or os.getenv("NOCODB_TOKEN", "")
        self.table_id = config.get("NOCODB_TABLE_ID", "")
        self.headers = {
            "xc-token": self.token,
            "Content-Type": "application/json"
        }
    
    async def upsert_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert lead to NocoDB."""
        async with httpx.AsyncClient() as client:
            data = {
                "Name": lead.get("name", "Unknown"),
                "Phone": lead.get("phone", ""),
                "Address": lead.get("address", ""),
                "Website": lead.get("website", ""),
                "Instagram": lead.get("instagram_username", ""),
                "Score": lead.get("score", 0),
                "Faixa": lead.get("faixa", "morno"),
                "Status": lead.get("status", "novo"),
                "Dossie Resumo": lead.get("dossie", {}).get("resumo_perfil", "")[:2000]
            }
            
            response = await client.post(
                f"{self.base_url}/api/v1/db/meta/tables/{self.table_id}/records",
                json=data,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "id": result.get("id"),
                    "operation": "created",
                    "lead": lead
                }
            else:
                logger.error(f"NocoDB API error: {response.status_code} - {response.text}")
                raise Exception(f"NocoDB API error: {response.status_code}")
    
    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve lead from NocoDB by record ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/db/meta/tables/{self.table_id}/records/{lead_id}",
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "id": data.get("Id"),
                    "name": data.get("Name", ""),
                    "phone": data.get("Phone", ""),
                    "status": data.get("Status", "")
                }
            return None
    
    async def update_status(self, lead_id: str, status: str) -> Dict[str, Any]:
        """Update lead status in NocoDB."""
        async with httpx.AsyncClient() as client:
            data = {"Status": status}
            
            response = await client.patch(
                f"{self.base_url}/api/v1/db/meta/tables/{self.table_id}/records/{lead_id}",
                json=data,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return {"success": True, "id": lead_id, "status": status}
            else:
                raise Exception(f"NocoDB API error: {response.status_code}")


def get_crm_adapter(provider: str, config: Dict[str, Any]) -> CRMAdapter:
    """
    Factory function to get the appropriate CRM adapter.
    
    Args:
        provider: CRM provider name (notion, airtable, nocodb)
        config: Configuration dictionary for the CRM
        
    Returns:
        CRMAdapter instance
        
    Raises:
        ValueError: If provider is not supported
    """
    providers = {
        "notion": NotionAdapter,
        "airtable": AirtableAdapter,
        "nocodb": NocoDBAdapter
    }
    
    provider_lower = provider.lower()
    if provider_lower not in providers:
        raise ValueError(f"Unsupported CRM provider: {provider}")
    
    return providers[provider_lower](config)
