"""Veracity LRS plugin implementation."""

import base64
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

import httpx
from pydantic import BaseModel, Field, SecretStr, field_validator
from fastapi import HTTPException, status

from .base import LRSPlugin, LRSPluginConfig

logger = logging.getLogger(__name__)


class VeracityConfig(LRSPluginConfig):
    """Configuration model for Veracity LRS plugin."""
    username: str = Field(..., description="Access key username for authentication")
    password: SecretStr = Field(..., description="Access key password for authentication")
    
    @field_validator('endpoint')
    @classmethod
    def validate_and_clean_endpoint(cls, v):
        """Validate endpoint and remove trailing /xapi to prevent duplication."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Endpoint must start with http:// or https://')
        
        # Remove trailing slash first
        v = v.rstrip('/')
        
        # Remove /xapi suffix if present to prevent duplication
        # This handles the common Veracity issue where endpoints come with /xapi
        if v.endswith('/xapi'):
            v = v[:-5]  # Remove '/xapi'
            logger.info("Removed /xapi suffix from endpoint to prevent duplication")
        
        return v
    
    class Config:
        env_prefix = "VERACITY_"


class VeracityPlugin(LRSPlugin):
    """Plugin for Veracity LRS implementation."""
    
    name = "veracity"
    description = "Veracity Learning - Cloud or self-hosted xAPI-compliant Learning Record Store"
    version = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Create HTTP client with Basic Authentication
        auth_string = f"{self.config.username}:{self.config.password.get_secret_value()}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        
        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "X-Experience-API-Version": "1.0.3"
        }
        
        # Veracity base URL is clean (without /xapi), we'll add it in requests
        self.client = httpx.AsyncClient(
            base_url=self.config.endpoint,
            headers=self.headers,
            timeout=self.config.timeout
        )
        
        logger.info(f"Initialized Veracity plugin with endpoint: {self.config.endpoint}")
    
    @classmethod
    def get_config_model(cls) -> type[BaseModel]:
        return VeracityConfig
    
    def validate_config(self) -> None:
        """Validate Veracity specific configuration."""
        if not self.config.username or not self.config.password:
            raise ValueError("Veracity requires 'username' and 'password' (access key credentials)")
    
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
                    logger.error(f"Veracity returned error {e.response.status_code}: {e.response.text}")
                    
                    # Log specific error details for debugging
                    if e.response.status_code == 401:
                        logger.error("Authentication failed - check access key credentials")
                    elif e.response.status_code == 404:
                        logger.error("Endpoint not found - verify LRS URL is correct")
                    
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Veracity LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Veracity error {e.response.status_code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    
            except httpx.RequestError as e:
                if attempt == max_attempts - 1:
                    logger.error(f"Request to Veracity failed: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Veracity LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Request error, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts}): {str(e)}"
                    )
                    await asyncio.sleep(delay)
    
    async def post_statement(self, statement: Dict[str, Any]) -> Dict[str, Any]:
        """Post statement to Veracity LRS."""
        # Veracity uses /xapi/statements (note: we add /xapi here)
        response = await self._retry_request(
            self.client.post, "/xapi/statements", json=statement
        )
        
        result = response.json()
        
        # Veracity typically returns an array of statement IDs
        if isinstance(result, list):
            statement_id = result[0] if result else "unknown"
            logger.info(f"Statement posted to Veracity, ID: {statement_id}")
            return {"id": statement_id, "stored": True}
        elif isinstance(result, dict):
            # Handle dict response format
            statement_id = result.get("id", "unknown")
            logger.info(f"Statement posted to Veracity, ID: {statement_id}")
            return result
        else:
            # Fallback for other response formats
            logger.info(f"Statement posted to Veracity, response: {result}")
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
        """Retrieve statements from Veracity LRS."""
        params = {
            "agent": f'{{"account":{{"homePage":"https://learnmcp.example.com","name":"{actor_uuid}"}}}}',
            "limit": min(limit, 50)  # Veracity supports standard xAPI limits
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
        
        # Sort by timestamp descending (most recent first)
        statements.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        
        logger.info(f"Retrieved {len(statements)} statements from Veracity")
        return statements
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
    
    @classmethod
    def load_config_from_env(cls, plugin_name: str) -> Dict[str, Any]:
        """Load plugin configuration from environment variables.
        
        Enhanced to support legacy VERACITY_ACCESS_KEY naming convention.
        """
        config = super().load_config_from_env(plugin_name)
        
        # Support legacy environment variable names for backward compatibility
        import os
        legacy_mappings = {
            "VERACITY_ACCESS_KEY": "username",
            "VERACITY_ACCESS_SECRET": "password",
            "VERACITY_LRS_ENDPOINT": "endpoint",
            "VERACITY_LRS_URL": "endpoint"
        }
        
        for legacy_key, modern_key in legacy_mappings.items():
            if legacy_key in os.environ and modern_key not in config:
                config[modern_key] = os.environ[legacy_key]
                logger.info(f"Using legacy environment variable {legacy_key}")
        
        return config