"""LRS SQL plugin implementation."""

import base64
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

import httpx
from pydantic import BaseModel, Field, SecretStr
from fastapi import HTTPException, status

from .base import LRSPlugin, LRSPluginConfig

logger = logging.getLogger(__name__)


class LRSSQLConfig(LRSPluginConfig):
    """Configuration model for LRS SQL plugin."""
    key: str = Field(..., description="API key for authentication")
    secret: SecretStr = Field(..., description="API secret for authentication")
    
    class Config:
        env_prefix = "LRSQL_"


class LRSSQLPlugin(LRSPlugin):
    """Plugin for LRS SQL implementation."""
    
    name = "lrsql"
    description = "LRS SQL - SQLite-based Learning Record Store"
    version = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Create HTTP client with authentication
        auth_string = f"{self.config.key}:{self.config.secret.get_secret_value()}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        
        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "X-Experience-API-Version": "1.0.3"
        }
        
        self.client = httpx.AsyncClient(
            base_url=self.config.endpoint,
            headers=self.headers,
            timeout=self.config.timeout
        )
    
    @classmethod
    def get_config_model(cls) -> type[BaseModel]:
        return LRSSQLConfig
    
    def validate_config(self) -> None:
        """Validate LRS SQL specific configuration."""
        if not self.config.key or not self.config.secret:
            raise ValueError("LRS SQL requires 'key' and 'secret' configuration")
    
    async def _retry_request(self, request_func, *args, **kwargs):
        """Execute request with exponential backoff retry logic."""
        max_attempts = self.config.retry_attempts
        backoff_delays = [0.5, 1.0, 2.0]
        
        for attempt in range(max_attempts):
            try:
                response = await request_func(*args, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 or attempt == max_attempts - 1:
                    logger.error(f"LRS returned error {e.response.status_code}: {e.response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        f"LRS error {e.response.status_code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    
            except httpx.RequestError as e:
                if attempt == max_attempts - 1:
                    logger.error(f"Request to LRS failed: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Request error, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts}): {str(e)}"
                    )
                    await asyncio.sleep(delay)
    
    async def post_statement(self, statement: Dict[str, Any]) -> Dict[str, Any]:
        """Post statement to LRS SQL."""
        response = await self._retry_request(
            self.client.post, "/xapi/statements", json=statement
        )
        
        result = response.json()
        
        # Handle different LRS response formats
        if isinstance(result, list):
            statement_id = result[0] if result else "unknown"
            logger.info(f"Statement posted successfully, ID: {statement_id}")
            return {"id": statement_id, "stored": True}
        elif isinstance(result, dict):
            statement_id = result.get("id", "unknown")
            logger.info(f"Statement posted successfully, ID: {statement_id}")
            return result
        else:
            logger.info(f"Statement posted successfully, response: {result}")
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
        """Retrieve statements from LRS SQL."""
        params = {
            "agent": f'{{"account":{{"homePage":"https://learnmcp.example.com","name":"{actor_uuid}"}}}}',
            "limit": min(limit, 50)
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
        
        logger.info(f"Retrieved {len(statements)} statements for actor")
        return statements
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()