"""Request logging middleware with privacy protection."""

import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..auth import hash_actor_uuid, extract_bearer_token, verify_jwt

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log requests with privacy-compliant actor hashing."""
    
    async def dispatch(self, request: Request, call_next):
        """Log request details with hashed actor UUID.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from next handler
        """
        start_time = time.time()
        
        # Extract and hash actor UUID if JWT is present
        actor_hash = "anonymous"
        auth_header = request.headers.get("authorization")
        if auth_header:
            try:
                token = extract_bearer_token(auth_header)
                actor_uuid = verify_jwt(token)
                actor_hash = hash_actor_uuid(actor_uuid)
            except Exception:
                pass  # Continue with "anonymous" if JWT parsing fails
        
        # Process request
        response = await call_next(request)
        
        # Log request details
        duration = time.time() - start_time
        logger.info(
            "Request: %s %s | Actor: %s | Status: %d | Duration: %.3fs | IP: %s",
            request.method,
            request.url.path,
            actor_hash,
            response.status_code,
            duration,
            request.client.host if request.client else "unknown"
        )
        
        return response