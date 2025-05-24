"""learnmcp-xapi main application."""

import logging
from typing import Dict, List, Any, Optional, Union

from fastmcp import FastMCP

from .config import config
from .mcp.core import record_statement, get_statements, get_available_verbs

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Validate configuration
config.validate()

# Create MCP server
mcp = FastMCP("learnmcp-xapi")


@mcp.tool()
async def record_xapi_statement(
    verb: str,
    object_id: str,
    level: Optional[Union[int, float]] = None,
    extras: Optional[Union[Dict[str, Any], str]] = None
) -> Dict[str, Any]:
    """Record an xAPI statement in the LRS.
    
    Args:
        verb: Verb alias (experienced, practiced, achieved, mastered)
        object_id: Activity object ID (must be valid IRI)
        level: Level (0-3 int) or raw score (float), optional
        extras: Additional data for result.extensions, optional
        
    Returns:
        LRS response with statement ID
    """
    # For MCP tools, we'll use a fixed actor UUID for now
    # In production, this would come from the MCP client authentication
    actor_uuid = "demo-user-12345"
    
    return await record_statement(
        actor_uuid=actor_uuid,
        verb=verb,
        object_id=object_id,
        level=level,
        extras=extras
    )


@mcp.tool()
async def get_xapi_statements(
    verb: Optional[str] = None,
    object_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieve xAPI statements for the authenticated actor.
    
    Args:
        verb: Verb alias to filter by, optional
        object_id: Object ID to filter by, optional  
        since: Start date (ISO format), optional
        until: End date (ISO format), optional
        limit: Maximum statements to return (max 50)
        
    Returns:
        List of xAPI statements ordered by timestamp desc
    """
    # For MCP tools, we'll use a fixed actor UUID for now
    actor_uuid = "demo-user-12345"
    
    return await get_statements(
        actor_uuid=actor_uuid,
        verb=verb,
        object_id=object_id,
        since=since,
        until=until,
        limit=limit
    )


@mcp.tool()
async def list_available_verbs() -> Dict[str, str]:
    """List available xAPI verb aliases and their URIs.
    
    Returns:
        Dict mapping verb alias to URI
    """
    return get_available_verbs()


if __name__ == "__main__":
    mcp.run()