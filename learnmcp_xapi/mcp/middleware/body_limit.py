"""Request body size limit middleware."""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from ...config import config


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request body size limits."""
    
    async def dispatch(self, request: Request, call_next):
        """Check request body size before processing.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from next handler
            
        Raises:
            HTTPException: 413 if body exceeds size limit
        """
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > config.MAX_BODY_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Request body too large (max {config.MAX_BODY_SIZE} bytes)"
                )
        
        response = await call_next(request)
        return response