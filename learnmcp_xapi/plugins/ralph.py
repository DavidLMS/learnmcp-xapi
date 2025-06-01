"""Ralph LRS plugin implementation."""

import base64
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

import httpx
from pydantic import BaseModel, Field, SecretStr, field_validator
from fastapi import HTTPException, status

from .base import LRSPlugin, LRSPluginConfig

logger = logging.getLogger(__name__)


class AuthMethod(str, Enum):
    """Authentication methods supported by Ralph."""
    BASIC = "basic"
    OIDC = "oidc"


class RalphConfig(LRSPluginConfig):
    """Configuration model for Ralph LRS plugin."""
    # Basic auth fields
    username: Optional[str] = Field(None, description="Username for basic auth")
    password: Optional[SecretStr] = Field(None, description="Password for basic auth")
    
    # OIDC fields
    oidc_token_url: Optional[str] = Field(None, description="OIDC token endpoint URL")
    oidc_client_id: Optional[str] = Field(None, description="OIDC client ID")
    oidc_client_secret: Optional[SecretStr] = Field(None, description="OIDC client secret")
    oidc_scope: str = Field("openid", description="OIDC scope")
    
    # Auto-detected auth method
    auth_method: Optional[AuthMethod] = None
    
    @field_validator('auth_method', mode='before')
    @classmethod
    def detect_auth_method(cls, v, info):
        """Auto-detect authentication method based on provided credentials."""
        if v:
            return v
        
        values = info.data if hasattr(info, 'data') else {}
        
        # Check for OIDC configuration
        if values.get('oidc_token_url') or values.get('oidc_client_id'):
            return AuthMethod.OIDC
        
        # Default to basic auth
        return AuthMethod.BASIC
    
    @field_validator('username')
    @classmethod
    def validate_basic_auth(cls, v, info):
        """Validate basic auth configuration."""
        values = info.data if hasattr(info, 'data') else {}
        if values.get('auth_method') == AuthMethod.BASIC and not v:
            raise ValueError("Username required for basic authentication")
        return v
    
    @field_validator('oidc_token_url')
    @classmethod
    def validate_oidc_config(cls, v, info):
        """Validate OIDC configuration."""
        values = info.data if hasattr(info, 'data') else {}
        if values.get('auth_method') == AuthMethod.OIDC:
            if not v:
                raise ValueError("OIDC token URL required for OIDC authentication")
            if not values.get('oidc_client_id'):
                raise ValueError("OIDC client ID required for OIDC authentication")
        return v
    
    class Config:
        env_prefix = "RALPH_"


class RalphPlugin(LRSPlugin):
    """Plugin for Ralph LRS implementation."""
    
    name = "ralph"
    description = "Ralph LRS - Open-source Learning Record Store by France Université Numérique"
    version = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Initialize HTTP client based on auth method
        self.client = httpx.AsyncClient(
            base_url=self.config.endpoint,
            timeout=self.config.timeout
        )
        
        # Token cache for OIDC
        self._token_cache = None
        self._token_expires_at = None
        
        # Set up headers
        self._setup_headers()
    
    @classmethod
    def get_config_model(cls) -> type[BaseModel]:
        return RalphConfig
    
    def validate_config(self) -> None:
        """Validate Ralph specific configuration."""
        # Validation is handled by Pydantic model
        pass
    
    def _setup_headers(self) -> None:
        """Set up base headers for requests."""
        self.base_headers = {
            "Content-Type": "application/json",
            "X-Experience-API-Version": "1.0.3"
        }
        
        # Add basic auth header if using basic auth
        if self.config.auth_method == AuthMethod.BASIC:
            auth_string = f"{self.config.username}:{self.config.password.get_secret_value()}"
            auth_bytes = auth_string.encode("ascii")
            auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
            self.base_headers["Authorization"] = f"Basic {auth_b64}"
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers for Basic Auth (synchronous access)."""
        if self.config.auth_method == AuthMethod.BASIC:
            return self.base_headers.copy()
        else:
            raise AttributeError("headers property only available for Basic Auth. Use _get_headers() for OIDC.")
    
    async def _get_oidc_token(self) -> str:
        """Get OIDC token, using cache if valid."""
        # Check cache
        if self._token_cache and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at:
                return self._token_cache
        
        # Request new token
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.config.oidc_client_id,
            "client_secret": self.config.oidc_client_secret.get_secret_value(),
            "scope": self.config.oidc_scope
        }
        
        response = await self.client.post(
            self.config.oidc_token_url,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        
        token_response = response.json()
        self._token_cache = token_response["access_token"]
        
        # Calculate expiration (with 30 second buffer)
        expires_in = token_response.get("expires_in", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 30)
        
        logger.info("Obtained new OIDC token")
        return self._token_cache
    
    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication."""
        headers = self.base_headers.copy()
        
        if self.config.auth_method == AuthMethod.OIDC:
            token = await self._get_oidc_token()
            headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    async def _retry_request(self, request_func, *args, **kwargs):
        """Execute request with retry logic and OIDC token refresh."""
        max_attempts = self.config.retry_attempts
        backoff_delays = [0.5, 1.0, 2.0]
        
        for attempt in range(max_attempts):
            try:
                # Get fresh headers (may refresh OIDC token)
                if 'headers' not in kwargs:
                    kwargs['headers'] = await self._get_headers()
                
                response = await request_func(*args, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                # Handle 401 for OIDC - clear token cache and retry
                if e.response.status_code == 401 and self.config.auth_method == AuthMethod.OIDC:
                    logger.warning("Got 401, clearing OIDC token cache")
                    self._token_cache = None
                    self._token_expires_at = None
                    
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(0.5)
                        continue
                
                if e.response.status_code < 500 or attempt == max_attempts - 1:
                    logger.error(f"Ralph returned error {e.response.status_code}: {e.response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Ralph LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Ralph error {e.response.status_code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(delay)
                    
            except httpx.RequestError as e:
                if attempt == max_attempts - 1:
                    logger.error(f"Request to Ralph failed: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Ralph LRS unavailable"
                    )
                else:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        f"Request error, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_attempts}): {str(e)}"
                    )
                    await asyncio.sleep(delay)
    
    async def post_statement(self, statement: Dict[str, Any]) -> Dict[str, Any]:
        """Post statement to Ralph LRS."""
        # Ralph uses /xAPI/statements/ (note the capital X and trailing slash)
        response = await self._retry_request(
            self.client.post, "/xAPI/statements/", json=statement
        )
        
        result = response.json()
        
        # Ralph returns array of statement IDs
        if isinstance(result, list):
            statement_id = result[0] if result else "unknown"
            logger.info(f"Statement posted to Ralph, ID: {statement_id}")
            return {"id": statement_id, "stored": True}
        else:
            # Fallback for unexpected response format
            logger.info(f"Statement posted to Ralph, response: {result}")
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
        """Retrieve statements from Ralph LRS."""
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
            self.client.get, "/xAPI/statements/", params=params
        )
        
        result = response.json()
        statements = result.get("statements", [])
        
        # Sort by timestamp descending
        statements.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        
        logger.info(f"Retrieved {len(statements)} statements from Ralph")
        return statements
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()