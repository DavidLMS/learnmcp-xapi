"""Configuration management for learnmcp-xapi."""

import os
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
        # Plugin Configuration
        self.LRS_PLUGIN: str = os.getenv("LRS_PLUGIN", "lrsql")
        self.CONFIG_PATH: str = os.getenv("CONFIG_PATH", "./config")
        
        # Actor Configuration - each client sets their own UUID
        self.ACTOR_UUID: str = os.getenv("ACTOR_UUID", "")
        
        # Optional Configuration
        self.RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
        self.MAX_BODY_SIZE: int = int(os.getenv("MAX_BODY_SIZE", "16384"))  # 16 KiB
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
        # Environment
        self.ENV: str = os.getenv("ENV", "development")
        
        # Legacy LRS Configuration (for backward compatibility)
        # These will be used if present but CONFIG_PATH doesn't exist
        self.LRS_ENDPOINT: str = os.getenv("LRS_ENDPOINT", "")
        self.LRS_KEY: str = os.getenv("LRS_KEY", "")
        self.LRS_SECRET: str = os.getenv("LRS_SECRET", "")
    
    def validate(self) -> None:
        """Validate required configuration values."""
        if not self.ACTOR_UUID:
            raise ValueError("ACTOR_UUID is required - each client must set a unique student UUID")
        
        # Validate plugin exists (will be checked by factory)
        if not self.LRS_PLUGIN:
            raise ValueError("LRS_PLUGIN is required")
        
        # For backward compatibility: if using old-style config, validate it
        if self.LRS_ENDPOINT and not Path(self.CONFIG_PATH).exists():
            if not self.LRS_KEY or not self.LRS_SECRET:
                raise ValueError("LRS_KEY and LRS_SECRET are required when using legacy configuration")
            
            # Production security validations
            if self.ENV == "production":
                if not self.LRS_ENDPOINT.startswith("https://"):
                    raise ValueError("LRS_ENDPOINT must use HTTPS in production")


config = Config()