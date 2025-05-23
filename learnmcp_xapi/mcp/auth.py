"""JWT authentication and validation."""

import hashlib
import logging
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status

from ..config import config

logger = logging.getLogger(__name__)


def verify_jwt(token: str) -> str:
    """Verify JWT token and extract actor UUID.
    
    Args:
        token: JWT token string
        
    Returns:
        Actor UUID from token subject
        
    Raises:
        HTTPException: 401 if token is invalid
    """
    try:
        if config.JWT_ALGORITHM == "RS256":
            if not config.JWT_PUBLIC_KEY:
                raise ValueError("JWT_PUBLIC_KEY not configured")
            payload = jwt.decode(
                token, 
                config.JWT_PUBLIC_KEY, 
                algorithms=["RS256"],
                audience="learnmcp-xapi"
            )
        elif config.JWT_ALGORITHM == "HS256":
            if not config.JWT_SECRET:
                raise ValueError("JWT_SECRET not configured")
            payload = jwt.decode(
                token,
                config.JWT_SECRET,
                algorithms=["HS256"], 
                audience="learnmcp-xapi"
            )
        else:
            raise ValueError(f"Unsupported JWT algorithm: {config.JWT_ALGORITHM}")
            
        actor_uuid = payload.get("sub")
        if not actor_uuid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing subject in token"
            )
            
        return actor_uuid
        
    except JWTError as e:
        logger.warning("JWT validation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def hash_actor_uuid(actor_uuid: str) -> str:
    """Hash actor UUID for privacy-compliant logging.
    
    Args:
        actor_uuid: Actor UUID to hash
        
    Returns:
        SHA-256 hash of UUID
    """
    return hashlib.sha256(actor_uuid.encode()).hexdigest()[:16]


def extract_bearer_token(authorization: Optional[str]) -> str:
    """Extract token from Authorization header.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        JWT token string
        
    Raises:
        HTTPException: 401 if header is missing or malformed
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format"
        )
    
    return authorization[7:]  # Remove "Bearer " prefix