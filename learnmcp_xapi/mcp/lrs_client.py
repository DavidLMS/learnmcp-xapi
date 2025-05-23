"""LRS client with retry logic and error handling."""

import base64
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

import httpx
from fastapi import HTTPException, status

from ..config import config

logger = logging.getLogger(__name__)


class LRSClient:
    """Client for communicating with xAPI Learning Record Store."""
    
    def __init__(self) -> None:
        """Initialize LRS client with authentication and retry logic."""
        auth_string = f"{config.LRS_KEY}:{config.LRS_SECRET}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        
        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "X-Experience-API-Version": "1.0.3"
        }
        
        self.client = httpx.AsyncClient(
            base_url=config.LRS_ENDPOINT,
            headers=self.headers,
            timeout=10.0
        )
    
    async def _retry_request(self, request_func, *args, **kwargs):
        """Execute request with exponential backoff retry logic.
        
        Args:
            request_func: HTTP request function to execute
            *args: Arguments for request function
            **kwargs: Keyword arguments for request function
            
        Returns:
            Response from successful request
            
        Raises:
            HTTPException: 503 if all retries fail
        """
        max_attempts = 4
        backoff_delays = [0.5, 1.0, 2.0]  # Exponential backoff
        
        for attempt in range(max_attempts):
            try:
                response = await request_func(*args, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 or attempt == max_attempts - 1:
                    # Don't retry client errors (4xx) or on last attempt
                    logger.error("LRS returned error %d: %s", e.response.status_code, e.response.text)
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="LRS unavailable"
                    )
                else:
                    # Server error - retry with backoff
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning("LRS error %d, retrying in %ds (attempt %d/%d)", 
                                 e.response.status_code, delay, attempt + 1, max_attempts)
                    await asyncio.sleep(delay)
                    
            except httpx.RequestError as e:
                if attempt == max_attempts - 1:
                    logger.error("Request to LRS failed: %s", str(e))
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning("Request error, retrying in %ds (attempt %d/%d): %s", 
                                 delay, attempt + 1, max_attempts, str(e))
                    await asyncio.sleep(delay)

    async def post_statement(self, statement: Dict[str, Any]) -> Dict[str, Any]:
        """Send statement to LRS.
        
        Args:
            statement: xAPI statement dictionary
            
        Returns:
            LRS response with statement ID
            
        Raises:
            HTTPException: 503 if LRS is unavailable after retries
        """
        response = await self._retry_request(
            self.client.post, "/xapi/statements", json=statement
        )
        
        result = response.json()
        
        # Handle different LRS response formats
        if isinstance(result, list):
            # Some LRS return array of statement IDs
            statement_id = result[0] if result else "unknown"
            logger.info("Statement posted successfully, ID: %s", statement_id)
            return {"id": statement_id, "stored": True}
        elif isinstance(result, dict):
            # Standard LRS response with ID
            statement_id = result.get("id", "unknown")
            logger.info("Statement posted successfully, ID: %s", statement_id)
            return result
        else:
            # Fallback for other response types
            logger.info("Statement posted successfully, response: %s", result)
            return {"id": str(result), "stored": True}
    
    async def get_statements(
        self,
        actor_uuid: str,
        verb: Optional[str] = None,
        object_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve statements from LRS.
        
        Args:
            actor_uuid: Actor UUID to filter by
            verb: Verb URI to filter by (optional)
            object_id: Object ID to filter by (optional)
            since: Start date filter (optional)
            until: End date filter (optional)
            limit: Maximum number of statements to return
            
        Returns:
            List of xAPI statements
            
        Raises:
            HTTPException: 503 if LRS is unavailable
        """
        params = {
            "agent": f'{{"account":{{"homePage":"https://learnmcp.example.com","name":"{actor_uuid}"}}}}',
            "limit": min(limit, 50)  # Enforce max limit
        }
        
        if verb:
            params["verb"] = verb
        if object_id:
            params["activity"] = object_id
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        
        response = await self._retry_request(
            self.client.get, "/xapi/statements", params=params
        )
        
        result = response.json()
        statements = result.get("statements", [])
        
        # Sort by timestamp descending
        statements.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        
        logger.info("Retrieved %d statements for actor", len(statements))
        return statements
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


# Global LRS client instance (lazy initialization)
lrs_client: Optional[LRSClient] = None


def get_lrs_client() -> LRSClient:
    """Get or create LRS client instance."""
    global lrs_client
    if lrs_client is None:
        lrs_client = LRSClient()
    return lrs_client