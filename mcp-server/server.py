"""
MCP Server for the Kirin platform.
Provides tools for scraping Google Maps and Instagram profiles.
"""
import asyncio
import os
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from agents.pure_functions import build_mcp_error

# Import tools
from tools.google_maps import search_google_maps
from tools.instagram import get_instagram_profile

app = FastAPI(title="MCP Server", description="Model Context Protocol Server for Kirin Platform")

# Semaphore to limit concurrent Playwright sessions
max_concurrent_sessions = int(os.getenv("MAX_CONCURRENT_SESSIONS", "3"))
semaphore = asyncio.Semaphore(max_concurrent_sessions)

class ToolRequest(BaseModel):
    """Request model for tool execution."""
    arguments: Dict[str, Any]

class ToolResponse(BaseModel):
    """Response model for tool execution."""
    result: Any

class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    timestamp: float
    version: str = "1.0.0"

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=time.time()
    )

@app.post("/tools/{tool_name}", response_model=ToolResponse)
async def execute_tool(tool_name: str, request: ToolRequest):
    """
    Execute a tool by name.
    
    Args:
        tool_name: Name of the tool to execute
        request: Tool request containing arguments
        
    Returns:
        Tool response with result
        
    Raises:
        HTTPException: If tool not found or execution fails
    """
    # Map tool names to functions
    tools = {
        "search_google_maps": search_google_maps,
        "get_instagram_profile": get_instagram_profile
    }
    
    if tool_name not in tools:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found"
        )
    
    # Execute tool with semaphore to limit concurrent sessions
    async with semaphore:
        try:
            tool_func = tools[tool_name]
            result = await tool_func(**request.arguments)
            return ToolResponse(result=result)
        except Exception as e:
            # Return structured error
            error = build_mcp_error(
                error_code="TOOL_EXECUTION_ERROR",
                error_message=str(e),
                retry_after=10  # Suggest retry after 10 seconds
            )
            raise HTTPException(
                status_code=500,
                detail=error
            )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MCP_PORT", "3100"))
    uvicorn.run(app, host="0.0.0.0", port=port)