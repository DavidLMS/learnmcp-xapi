"""Core MCP tools implementation using plugin architecture."""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union

from fastapi import HTTPException, status
from jsonschema import ValidationError

from ..verbs import get_verb, list_verbs
from .validator import validate_xapi_statement, is_valid_iri
from ..plugins.base import LRSPlugin
from ..plugins.factory import PluginFactory
from ..config import config

logger = logging.getLogger(__name__)

# Global plugin instance
_lrs_plugin: Optional[LRSPlugin] = None


def get_lrs_plugin() -> LRSPlugin:
    """Get or create LRS plugin instance.
    
    Returns:
        LRS plugin instance
        
    Raises:
        ValueError: If plugin cannot be created
    """
    global _lrs_plugin
    if _lrs_plugin is None:
        _lrs_plugin = PluginFactory.create_from_config(config)
    return _lrs_plugin


def _build_score(level: Union[int, float], extras: Dict[str, Any]) -> Dict[str, Any]:
    """Build xAPI score object from level and extras.
    
    Args:
        level: Level (0-3 int) or raw score (float)
        extras: Additional parameters that may contain score_max
        
    Returns:
        xAPI score object with raw, min, max
    """
    if isinstance(level, int) and 0 <= level <= 3:
        # Integer level 0-3
        return {
            "raw": level,
            "min": 0,
            "max": 3
        }
    elif isinstance(level, (int, float)):
        # Decimal score
        score_max = extras.get("score_max", 100)
        return {
            "raw": float(level),
            "min": 0,
            "max": float(score_max)
        }
    else:
        raise ValueError(f"Invalid level type: {type(level)}")


def _calculate_success(score: Dict[str, Any]) -> bool:
    """Calculate success based on score.
    
    Args:
        score: Score object with raw, min, max
        
    Returns:
        True if successful based on thresholds
    """
    raw = score["raw"]
    max_score = score["max"]
    
    if max_score == 3:
        # Integer scale: success if level >= 2
        return raw >= 2
    else:
        # Decimal scale: success if raw >= 0.6 * max
        return raw >= (0.6 * max_score)


async def record_statement(
    actor_uuid: str,
    verb: str,
    object_id: str,
    level: Optional[Union[int, float]] = None,
    extras: Optional[Union[Dict[str, Any], str]] = None
) -> Dict[str, Any]:
    """Record xAPI statement in LRS.
    
    Args:
        actor_uuid: Actor UUID from JWT
        verb: Verb alias (e.g., 'practiced')
        object_id: Activity object ID (must be valid IRI)
        level: Level (0-3) or raw score (optional)
        extras: Additional data for result.extensions (optional)
        
    Returns:
        LRS response with statement ID
        
    Raises:
        HTTPException: 400 for invalid parameters
    """
    # Parse extras if it's a JSON string
    if isinstance(extras, str):
        try:
            extras = json.loads(extras)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="extras must be valid JSON"
            )
    
    if extras is None:
        extras = {}
    
    # Validate verb alias
    try:
        verb_def = get_verb(verb)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown verb: {verb}"
        )
    
    # Validate object ID as IRI
    if not is_valid_iri(object_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="object_id must be a valid IRI"
        )
    
    # Build xAPI statement
    statement = {
        "actor": {
            "objectType": "Agent",
            "account": {
                "homePage": "https://learnmcp.example.com",
                "name": actor_uuid
            }
        },
        "verb": verb_def,
        "object": {
            "id": object_id,
            "objectType": "Activity"
        },
        "context": {
            "platform": "learnmcp-xapi"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Add result if level is provided
    if level is not None:
        try:
            score = _build_score(level, extras)
            success = _calculate_success(score)
            
            statement["result"] = {
                "score": score,
                "success": success
            }
            
            # Add extensions from extras (exclude reserved keys)
            # Convert extension keys to URIs as required by xAPI spec
            extensions = {}
            for k, v in extras.items():
                if k != "score_max":
                    # Convert simple keys to URIs
                    if not k.startswith("http"):
                        extension_key = f"https://learnmcp.example.com/extensions/{k}"
                    else:
                        extension_key = k
                    extensions[extension_key] = v
            
            if extensions:
                statement["result"]["extensions"] = extensions
                
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    
    # Log the statement before sending to LRS
    logger.info("Generated xAPI statement: %s", json.dumps(statement, indent=2))
    
    # Validate against xAPI schema
    try:
        validate_xapi_statement(statement)
    except ValidationError as e:
        logger.error("Statement validation failed: %s", e.message)
        logger.error("Statement that failed validation: %s", json.dumps(statement, indent=2))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid xAPI statement: {e.message}"
        )
    
    # Send to LRS
    plugin = get_lrs_plugin()
    return await plugin.post_statement(statement)


async def get_statements(
    actor_uuid: str,
    verb: Optional[str] = None,
    object_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieve statements from LRS for actor.
    
    Args:
        actor_uuid: Actor UUID from JWT
        verb: Verb alias to filter by (optional)
        object_id: Object ID to filter by (optional)
        since: ISO datetime string for start filter (optional)
        until: ISO datetime string for end filter (optional)
        limit: Maximum statements to return (max 50)
        
    Returns:
        List of xAPI statements ordered by timestamp desc
        
    Raises:
        HTTPException: 400 for invalid parameters
    """
    # Validate and convert verb alias to URI
    verb_uri = None
    if verb:
        try:
            verb_def = get_verb(verb)
            verb_uri = verb_def["id"]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown verb: {verb}"
            )
    
    # Parse datetime strings
    since_dt = None
    until_dt = None
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid since datetime format"
            )
    
    if until:
        try:
            until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid until datetime format"
            )
    
    # Enforce limit
    if limit > 50:
        limit = 50
    
    plugin = get_lrs_plugin()
    return await plugin.get_statements(
        actor_uuid=actor_uuid,
        verb=verb_uri,
        object_id=object_id,
        since=since_dt,
        until=until_dt,
        limit=limit
    )


def get_available_verbs() -> Dict[str, str]:
    """Get list of available verb aliases and URIs.
    
    Returns:
        Dict mapping alias to URI
    """
    return list_verbs()