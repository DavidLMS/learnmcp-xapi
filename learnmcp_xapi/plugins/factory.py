"""Factory for creating LRS plugin instances."""

import logging
from typing import Dict, Any, Optional

from .base import LRSPlugin
from .registry import plugin_registry

logger = logging.getLogger(__name__)


class PluginFactory:
    """Factory for creating LRS plugin instances with configuration."""
    
    @staticmethod
    def create_plugin(
        plugin_name: str,
        config_path: Optional[str] = None,
        additional_config: Optional[Dict[str, Any]] = None
    ) -> LRSPlugin:
        """Create plugin instance with merged configuration.
        
        Configuration priority (highest to lowest):
        1. additional_config parameter
        2. Environment variables with plugin prefix
        3. Configuration file (if config_path provided)
        
        Args:
            plugin_name: Name of the plugin to create
            config_path: Base path for configuration files (optional)
            additional_config: Additional configuration to override (optional)
            
        Returns:
            Configured plugin instance
            
        Raises:
            ValueError: If plugin not found or configuration invalid
        """
        # Get plugin class
        plugin_class = plugin_registry.get(plugin_name)
        if not plugin_class:
            available = ", ".join(plugin_registry.list_plugins().keys())
            raise ValueError(
                f"Unknown plugin: '{plugin_name}'. Available plugins: {available}"
            )
        
        # Load configuration with priority merging
        config = {}
        
        # 1. Load from file if path provided
        if config_path:
            try:
                file_config = plugin_class.load_config_from_file(plugin_name, config_path)
                config.update(file_config)
                logger.debug(f"Loaded config from file for plugin '{plugin_name}'")
            except Exception as e:
                logger.warning(f"Failed to load config file for '{plugin_name}': {e}")
        
        # 2. Load from environment variables (overrides file config)
        env_config = plugin_class.load_config_from_env(plugin_name)
        if env_config:
            config.update(env_config)
            logger.debug(f"Loaded config from environment for plugin '{plugin_name}'")
        
        # 3. Apply additional config (highest priority)
        if additional_config:
            config.update(additional_config)
        
        # Create plugin instance
        logger.info(f"Creating plugin instance: {plugin_name}")
        return plugin_class(config)
    
    @staticmethod
    def create_from_config(config: 'Config') -> LRSPlugin:
        """Create plugin from application config.
        
        Args:
            config: Application configuration object
            
        Returns:
            Configured plugin instance
        """
        # For backward compatibility: if using legacy config, pass it as additional_config
        additional_config = None
        if config.LRS_ENDPOINT and config.LRS_KEY and config.LRS_SECRET:
            additional_config = {
                "endpoint": config.LRS_ENDPOINT,
                "key": config.LRS_KEY,
                "secret": config.LRS_SECRET
            }
            logger.info("Using legacy configuration from environment variables")
        
        return PluginFactory.create_plugin(
            plugin_name=config.LRS_PLUGIN,
            config_path=config.CONFIG_PATH,
            additional_config=additional_config
        )