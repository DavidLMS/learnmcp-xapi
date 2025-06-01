"""Base plugin interface for LRS implementations."""

import os
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

from pydantic import BaseModel, Field, field_validator


class LRSPluginConfig(BaseModel):
    """Base configuration model for LRS plugins."""
    endpoint: str = Field(..., description="LRS endpoint URL")
    timeout: int = Field(30, description="Request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Endpoint must start with http:// or https://')
        return v.rstrip('/')  # Remove trailing slash for consistency


class LRSPlugin(ABC):
    """Abstract base class for LRS plugins."""
    
    # Plugin metadata
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize plugin with configuration.
        
        Args:
            config: Plugin configuration dictionary
        """
        self.raw_config = config
        self.config = self._parse_config(config)
        self.validate_config()
    
    @classmethod
    @abstractmethod
    def get_config_model(cls) -> type[BaseModel]:
        """Return Pydantic model for configuration validation.
        
        Returns:
            Pydantic BaseModel subclass for this plugin's configuration
        """
        pass
    
    def _parse_config(self, config: Dict[str, Any]) -> BaseModel:
        """Parse and validate configuration using Pydantic model.
        
        Args:
            config: Raw configuration dictionary
            
        Returns:
            Validated configuration model instance
            
        Raises:
            ValidationError: If configuration is invalid
        """
        config_model = self.get_config_model()
        return config_model(**config)
    
    @abstractmethod
    def validate_config(self) -> None:
        """Validate plugin-specific configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    async def post_statement(self, statement: Dict[str, Any]) -> Dict[str, Any]:
        """Post xAPI statement to LRS.
        
        Args:
            statement: xAPI statement dictionary
            
        Returns:
            Response from LRS with statement ID
            
        Raises:
            HTTPException: If LRS request fails
        """
        pass
    
    @abstractmethod
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
            limit: Maximum statements to return
            
        Returns:
            List of xAPI statements
            
        Raises:
            HTTPException: If LRS request fails
        """
        pass
    
    async def close(self) -> None:
        """Clean up plugin resources.
        
        Override if plugin needs cleanup (e.g., close HTTP clients).
        """
        pass
    
    @classmethod
    def load_config_from_file(cls, plugin_name: str, config_path: str) -> Dict[str, Any]:
        """Load plugin configuration from YAML file.
        
        Args:
            plugin_name: Name of the plugin
            config_path: Base configuration directory path
            
        Returns:
            Configuration dictionary with environment variables substituted
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist
        """
        config_file = Path(config_path) / "plugins" / f"{plugin_name}.yaml"
        
        if not config_file.exists():
            # Return empty dict to allow env-only configuration
            return {}
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        return cls._substitute_env_vars(config)
    
    @classmethod
    def load_config_from_env(cls, plugin_name: str) -> Dict[str, Any]:
        """Load plugin configuration from environment variables.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Configuration dictionary from environment variables
        """
        prefix = f"{plugin_name.upper()}_"
        config = {}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert PLUGIN_SOME_KEY to some_key
                config_key = key[len(prefix):].lower()
                config[config_key] = value
        
        return config
    
    @staticmethod
    def _substitute_env_vars(config: Any) -> Any:
        """Recursively substitute ${VAR} with environment variables.
        
        Args:
            config: Configuration value (dict, list, or string)
            
        Returns:
            Configuration with environment variables substituted
        """
        if isinstance(config, dict):
            return {k: LRSPlugin._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [LRSPlugin._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Replace ${VAR} or $VAR with environment variable value
            pattern = re.compile(r'\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)')
            
            def replacer(match):
                var_name = match.group(1) or match.group(2)
                return os.getenv(var_name, match.group(0))
            
            return pattern.sub(replacer, config)
        else:
            return config