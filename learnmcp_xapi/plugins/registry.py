"""Plugin registry for dynamic plugin discovery and registration."""

from typing import Dict, Type, Optional
import logging

from .base import LRSPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for LRS plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, Type[LRSPlugin]] = {}
    
    def register(self, plugin_class: Type[LRSPlugin]) -> None:
        """Register a plugin class.
        
        Args:
            plugin_class: Plugin class to register
            
        Raises:
            ValueError: If plugin name is empty or already registered
        """
        if not plugin_class.name:
            raise ValueError(f"Plugin {plugin_class.__name__} must have a name")
        
        if plugin_class.name in self._plugins:
            logger.warning(f"Plugin '{plugin_class.name}' already registered, overwriting")
        
        self._plugins[plugin_class.name] = plugin_class
        logger.info(f"Registered plugin: {plugin_class.name} ({plugin_class.description})")
    
    def get(self, name: str) -> Optional[Type[LRSPlugin]]:
        """Get plugin class by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin class or None if not found
        """
        return self._plugins.get(name)
    
    def list_plugins(self) -> Dict[str, str]:
        """List all registered plugins.
        
        Returns:
            Dict mapping plugin names to descriptions
        """
        return {
            name: plugin_class.description
            for name, plugin_class in self._plugins.items()
        }
    
    def __contains__(self, name: str) -> bool:
        """Check if plugin is registered.
        
        Args:
            name: Plugin name
            
        Returns:
            True if plugin is registered
        """
        return name in self._plugins


# Global plugin registry instance
plugin_registry = PluginRegistry()