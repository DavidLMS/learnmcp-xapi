"""Configuration management for learnmcp-xapi."""

import os
from typing import Optional
from pathlib import Path

# Load .env file if it exists
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


class Config:
    """Application configuration loaded from environment variables."""
    
    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.LRS_ENDPOINT: str = os.getenv("LRS_ENDPOINT", "")
        self.LRS_KEY: str = os.getenv("LRS_KEY", "")
        self.LRS_SECRET: str = os.getenv("LRS_SECRET", "")
        
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "RS256")
        self.JWT_PUBLIC_KEY: Optional[str] = os.getenv("JWT_PUBLIC_KEY")
        self.JWT_SECRET: Optional[str] = os.getenv("JWT_SECRET")
        
        self.RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
        self.MAX_BODY_SIZE: int = int(os.getenv("MAX_BODY_SIZE", "16384"))  # 16 KiB
        
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def validate(self) -> None:
        """Validate required configuration values."""
        if not self.LRS_ENDPOINT:
            raise ValueError("LRS_ENDPOINT is required")
        if not self.LRS_KEY or not self.LRS_SECRET:
            raise ValueError("LRS_KEY and LRS_SECRET are required")
        
        if self.JWT_ALGORITHM == "RS256" and not self.JWT_PUBLIC_KEY:
            raise ValueError("JWT_PUBLIC_KEY is required for RS256")
        if self.JWT_ALGORITHM == "HS256" and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET is required for HS256")


config = Config()